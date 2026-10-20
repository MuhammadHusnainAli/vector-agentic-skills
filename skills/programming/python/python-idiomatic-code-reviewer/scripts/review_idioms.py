#!/usr/bin/env python3
"""Review Python source for non-idiomatic, unpythonic or risky patterns.

AST + token based static reviewer with 46 rules (PY001-PY046). Each finding
has a rule id, severity (high / medium / low), line:col, the offending source
line and a suggested rewrite. Rules cover general idioms (mutable defaults,
bare except, == None, range(len()), manual counters, append loops, any/all,
setdefault, f-strings, pathlib, truthiness, match, walrus, builtin shadowing,
open() without with/encoding, typing generics) and AI-engineering risks
(hardcoded API keys, time.sleep / requests inside async def, HTTP calls with
no timeout, unbounded retry loops, model clients built at import time, LLM
clients without timeout, prompt concatenation, sequential awaits in loops,
print debugging, eval() on model output).

The analysed code is parsed, never imported or executed.

Usage:
    python review_idioms.py app.py
    python review_idioms.py src/                      # every *.py under a folder
    cat app.py | python review_idioms.py -            # read stdin
    python review_idioms.py app.py --json             # machine-readable output
    python review_idioms.py app.py --strict           # exit 1 on any medium/high finding
    python review_idioms.py app.py --min-severity medium
    python review_idioms.py app.py --select PY036,PY037,PY038   # only these rules
    python review_idioms.py app.py --ignore PY03                # id prefixes work too
    python review_idioms.py --list-rules

Suppress a finding on one line with a trailing `# noqa: PY001` (or bare `# noqa`).

Exit codes: 0 = done (findings are not failures unless --strict),
            1 = --strict and at least one finding at medium or high,
            2 = usage error, unreadable file or Python syntax error.

No dependencies (standard library only, Python 3.9+).
"""

import argparse
import ast
import io
import json
import re
import sys
import tokenize
from pathlib import Path

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

# id -> (name, severity, title, suggested rewrite)
RULES = {
    "PY001": ("mutable-default", "high", "Mutable default argument is shared between calls",
              "def chat(prompt, history=None):\n    history = [] if history is None else history"),
    "PY002": ("bare-except", "high", "Bare `except:` also catches KeyboardInterrupt and SystemExit",
              "except (TimeoutError, ConnectionError) as err:\n    logger.warning(\"retrying: %s\", err)"),
    "PY003": ("swallowed-exception", "high", "Broad exception silently swallowed",
              "except Exception:\n    logger.exception(\"embedding batch failed\")\n    raise"),
    "PY004": ("eval-exec", "high", "eval()/exec() runs arbitrary code (never on model output)",
              "data = json.loads(text)            # JSON from an LLM\nvalue = ast.literal_eval(text)    # Python literals only"),
    "PY005": ("shell-injection", "high", "Shell command built from a string (shell=True / os.system)",
              "subprocess.run([\"git\", \"clone\", url], check=True, timeout=60)"),
    "PY006": ("compare-none", "medium", "Comparison to None with == / !=",
              "if result is None: ...\nif result is not None: ..."),
    "PY007": ("compare-bool", "low", "Comparison to True/False with == / !=",
              "if done: ...\nif not done: ...\n# numpy/pandas masks: use the mask directly, or mask.astype(bool)"),
    "PY008": ("type-compare", "medium", "type(x) == T comparison ignores subclasses",
              "if isinstance(value, (int, float)): ..."),
    "PY009": ("open-without-with", "medium", "File opened without a with-block (may leak the handle)",
              "with open(path, encoding=\"utf-8\") as fh:\n    data = fh.read()\n# or: Path(path).read_text(encoding=\"utf-8\")"),
    "PY010": ("star-import", "medium", "Wildcard import hides where names come from",
              "from mypkg.prompts import SYSTEM_PROMPT, render_prompt"),
    "PY011": ("raise-without-from", "low", "New exception raised in except without `from`",
              "except KeyError as err:\n    raise ConfigError(f\"missing key {err}\") from err"),
    "PY012": ("range-len", "medium", "range(len(x)) loop instead of direct iteration",
              "for item in items: ...\nfor i, item in enumerate(items): ...\nfor q, a in zip(questions, answers, strict=True): ...  # strict: 3.10+"),
    "PY013": ("manual-counter", "low", "Manual index counter; use enumerate()",
              "for i, chunk in enumerate(chunks, start=1): ..."),
    "PY014": ("dict-keys", "low", "Iterating or testing membership on .keys()",
              "for key in config: ...\nif key in config: ...\nfor key, value in config.items(): ..."),
    "PY015": ("append-loop", "low", "Loop that only appends/assigns can be a comprehension",
              "texts = [doc.text for doc in docs if doc.text]\nby_id = {doc.id: doc for doc in docs}"),
    "PY016": ("any-all-loop", "low", "Loop returning True/False can be any()/all()",
              "return any(tok in text for tok in STOP_TOKENS)"),
    "PY017": ("setdefault", "low", "Manual 'if key not in d: d[key] = ...' initialisation",
              "groups = defaultdict(list)\ngroups[key].append(item)\n# or: groups.setdefault(key, []).append(item)"),
    "PY018": ("str-concat-loop", "low", "String built with += in a loop (quadratic)",
              "parts = [f\"[{i}] {c.text}\" for i, c in enumerate(chunks, 1)]\ncontext = \"\\n\\n\".join(parts)"),
    "PY019": ("old-format", "low", "%-formatting or str.format(); prefer f-strings",
              "msg = f\"{model}: {tokens:,} tokens in {elapsed:.2f}s\""),
    "PY020": ("len-truthiness", "low", "len() compared to 0; use truthiness",
              "if docs: ...\nif not docs: ...\n# numpy arrays / DataFrames: keep `arr.size == 0` / `df.empty`"),
    "PY021": ("not-in", "low", "`not x in y` / `not x is y`",
              "if token not in vocab: ...\nif value is not None: ..."),
    "PY022": ("isinstance-chain", "low", "Chained isinstance() calls",
              "if isinstance(x, (list, tuple)): ...\n# 3.10+: isinstance(x, list | tuple)"),
    "PY023": ("lambda-assign", "low", "Lambda assigned to a name (PEP 8 E731)",
              "def score(doc: Doc) -> float:\n    return doc.similarity"),
    "PY024": ("shadow-builtin", "low", "Name shadows a builtin",
              "ids = [...]\ndoc_type = ...\ninput_text = ..."),
    "PY025": ("os-path", "low", "os.path / os.listdir / glob; prefer pathlib",
              "path = Path(base) / \"data\" / \"train.jsonl\"\nfor p in Path(\"docs\").glob(\"**/*.md\"): ..."),
    "PY026": ("open-encoding", "low", "Text file opened without an explicit encoding (PEP 597)",
              "open(path, encoding=\"utf-8\")\nPath(path).read_text(encoding=\"utf-8\")"),
    "PY027": ("utcnow", "low", "datetime.utcnow()/utcfromtimestamp() return naive datetimes (deprecated 3.12)",
              "from datetime import datetime, timezone\nnow = datetime.now(timezone.utc)   # 3.11+: datetime.UTC"),
    "PY028": ("global-stmt", "low", "`global` statement mutates module state",
              "@functools.cache\ndef get_client() -> OpenAI:\n    return OpenAI(timeout=30)"),
    "PY029": ("elif-chain", "low", "Long if/elif chain on one value; use match (3.10+) or a dict",
              "match role:\n    case \"system\": ...\n    case \"user\" | \"assistant\": ...\n    case _: raise ValueError(role)"),
    "PY030": ("lbyl-exists", "low", "Check-then-open (LBYL) races; prefer EAFP",
              "try:\n    text = path.read_text(encoding=\"utf-8\")\nexcept FileNotFoundError:\n    text = \"\""),
    "PY031": ("typing-generics", "low", "typing.List/Dict/... are deprecated aliases (3.9+)",
              "def batch(items: list[str]) -> dict[str, list[float]]: ..."),
    "PY032": ("semicolon", "low", "Multiple statements on one line with `;`",
              "x = 1\ny = 2"),
    "PY033": ("backslash", "low", "Backslash line continuation; use parentheses",
              "total = (prompt_tokens\n         + completion_tokens)"),
    "PY034": ("print-debug", "low", "print() in library/pipeline code; use logging",
              "logger = logging.getLogger(__name__)\nlogger.debug(\"retrieved %d chunks\", len(chunks))"),
    "PY035": ("logging-format", "low", "Eagerly formatted log message",
              "logger.info(\"embedded %d docs in %.2fs\", n, elapsed)"),
    "PY036": ("hardcoded-secret", "high", "Hardcoded API key / secret",
              "api_key = os.environ[\"OPENAI_API_KEY\"]\n# or pydantic-settings: SecretStr loaded from env / .env (gitignored)"),
    "PY037": ("sleep-in-async", "high", "time.sleep() inside async def blocks the event loop",
              "await asyncio.sleep(delay)"),
    "PY038": ("blocking-in-async", "high", "Blocking I/O call inside async def",
              "async with httpx.AsyncClient(timeout=30) as client:\n    resp = await client.post(url, json=payload)\n# or: await asyncio.to_thread(blocking_fn, arg)"),
    "PY039": ("http-no-timeout", "medium", "HTTP call without a timeout can hang forever",
              "requests.post(url, json=payload, timeout=(5, 60))"),
    "PY040": ("unbounded-retry", "high", "while True retry loop with no attempt limit",
              "for attempt in range(MAX_RETRIES):\n    try:\n        return call()\n    except RateLimitError:\n        time.sleep(min(60, 2 ** attempt) + random.random())\nraise RuntimeError(\"gave up\")"),
    "PY041": ("import-time-client", "medium", "Model / API client created at import time",
              "@functools.cache\ndef get_embedder() -> SentenceTransformer:\n    return SentenceTransformer(MODEL_NAME)\n# FastAPI: build it in lifespan() and inject"),
    "PY042": ("llm-client-no-timeout", "low", "LLM client constructed without explicit timeout",
              "client = AsyncOpenAI(timeout=30.0, max_retries=3)"),
    "PY043": ("prompt-concat", "low", "Prompt built by string concatenation",
              "PROMPT = \"\"\"\\\nAnswer using only the context.\n\nContext:\n{context}\n\nQuestion: {question}\"\"\"\nprompt = PROMPT.format(context=context, question=question)"),
    "PY044": ("sequential-await", "low", "await inside a for loop runs requests one at a time",
              "sem = asyncio.Semaphore(8)\nasync def one(x):\n    async with sem:\n        return await embed(x)\nresults = await asyncio.gather(*(one(x) for x in batch))"),
    "PY045": ("suppress", "low", "`except SomeError: pass`; use contextlib.suppress",
              "with contextlib.suppress(FileNotFoundError):\n    cache_path.unlink()"),
    "PY046": ("walrus", "low", "Assign-then-test can use the walrus operator (3.8+)",
              "if m := re.search(r\"```json(.*?)```\", text, re.S):\n    payload = m.group(1)"),
}

BUILTINS = {"list", "dict", "set", "str", "id", "type", "input", "max", "min", "sum", "len", "filter", "map",
            "object", "format", "hash", "iter", "next", "range", "vars", "bytes", "all", "any", "open", "zip",
            "compile", "tuple", "int", "float", "bool", "sorted", "slice", "round", "dir", "help", "ord", "chr"}
MUTABLE_CALLS = {"list", "dict", "set", "defaultdict", "OrderedDict", "Counter", "deque", "bytearray"}
TYPING_ALIASES = {"List", "Dict", "Tuple", "Set", "FrozenSet", "Type", "Deque", "DefaultDict", "OrderedDict",
                  "Counter", "ChainMap"}
LLM_CLIENTS = {"OpenAI", "AsyncOpenAI", "AzureOpenAI", "AsyncAzureOpenAI", "Anthropic", "AsyncAnthropic",
               "AnthropicBedrock", "AsyncAnthropicBedrock", "Groq", "AsyncGroq", "Mistral"}
MODEL_LOADERS = {"SentenceTransformer", "CrossEncoder", "pipeline", "PersistentClient", "QdrantClient", "Pinecone",
                 "Llama", "LLM"} | LLM_CLIENTS
REQUESTS_VERBS = {"get", "post", "put", "patch", "delete", "head", "options", "request"}
BLOCKING_IN_ASYNC = ({f"requests.{v}" for v in REQUESTS_VERBS} | {f"httpx.{v}" for v in REQUESTS_VERBS | {"stream"}}
                     | {"urllib.request.urlopen", "subprocess.run", "subprocess.call", "subprocess.check_call",
                        "subprocess.check_output", "os.system"})
OS_PATH_CALLS = {"os.listdir", "os.makedirs", "os.mkdir", "os.getcwd", "os.remove", "os.unlink", "os.rename",
                 "glob.glob", "glob.iglob"}
LOG_METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}
PRINT_OK_FUNCS = re.compile(r"^(main|_main|cli|run_cli|print\w*|_print\w*|show\w*|display\w*|report\w*|render\w*|dump\w*)$")
SECRET_NAME = re.compile(r"(api_?key|secret|token|passw(or)?d|passwd|access_?key|auth_?key|private_?key|bearer)",
                         re.I)
SECRET_VALUE = re.compile(r"(sk-(ant-|proj-)?[A-Za-z0-9_\-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|"
                          r"hf_[A-Za-z0-9]{30,}|xox[abprs]-[A-Za-z0-9\-]{10,}|AIza[0-9A-Za-z_\-]{35}|"
                          r"gsk_[A-Za-z0-9]{30,})")
PLACEHOLDER = re.compile(r"^(<.*>|\$\{.*\}|your[-_ ].*|x{3,}|\*+|changeme|dummy|test|example.*|none|null|\.\.\.)$",
                         re.I)
NOQA = re.compile(r"#\s*noqa(?::\s*(?P<ids>[A-Z0-9, ]+))?", re.I)
FUNC_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
LOOP_TYPES = (ast.For, ast.AsyncFor, ast.While)


def dotted(node):
    """Return 'a.b.c' for Name/Attribute chains, else None."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def is_str(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def is_call_to(node, *names):
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in names


def same(a, b):
    return ast.dump(a) == ast.dump(b)


def has_star_kwargs(call):
    return any(k.arg is None for k in call.keywords)


def kwarg(call, name):
    return next((k for k in call.keywords if k.arg == name), None)


class Reviewer:
    def __init__(self, source, path):
        self.source = source
        self.path = path
        self.lines = source.splitlines()
        self.tree = ast.parse(source, filename=path)
        self.aliases = {}
        self.findings = []
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                child._parent = node
        self._collect_imports()

    # ---------- helpers ----------
    def _collect_imports(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    self.aliases[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
            elif isinstance(node, ast.ImportFrom) and node.module:
                for a in node.names:
                    if a.name != "*":
                        self.aliases[a.asname or a.name] = f"{node.module}.{a.name}"

    def qualname(self, node):
        name = dotted(node)
        if not name:
            return None
        head, _, rest = name.partition(".")
        head = self.aliases.get(head, head)
        return f"{head}.{rest}" if rest else head

    def parents(self, node):
        while hasattr(node, "_parent"):
            node = node._parent
            yield node

    def enclosing_func(self, node):
        return next((p for p in self.parents(node) if isinstance(p, FUNC_TYPES)), None)

    def in_async(self, node):
        return isinstance(self.enclosing_func(node), ast.AsyncFunctionDef)

    def in_loop(self, node):
        for p in self.parents(node):
            if isinstance(p, FUNC_TYPES):
                return False
            if isinstance(p, LOOP_TYPES):
                return True
        return False

    def in_handler(self, node):
        for p in self.parents(node):
            if isinstance(p, FUNC_TYPES):
                return None
            if isinstance(p, ast.ExceptHandler):
                return p
        return None

    def in_main_guard(self, node):
        return any(isinstance(p, ast.If) and "__main__" in ast.dump(p.test) and "__name__" in ast.dump(p.test)
                   for p in self.parents(node))

    def add(self, rid, node, message=None, line=None, col=None):
        line = line if line is not None else getattr(node, "lineno", 1)
        col = col if col is not None else getattr(node, "col_offset", 0)
        name, sev, title, fix = RULES[rid]
        self.findings.append({"path": self.path, "line": line, "col": col + 1, "rule": rid, "name": name,
                              "severity": sev, "message": message or title,
                              "source": self.lines[line - 1].strip() if 0 < line <= len(self.lines) else "",
                              "fix": fix})

    @staticmethod
    def walk_local(node):
        """ast.walk that does not descend into nested functions/classes."""
        stack = list(ast.iter_child_nodes(node))
        while stack:
            n = stack.pop()
            yield n
            if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                stack.extend(ast.iter_child_nodes(n))

    # ---------- main entry ----------
    def run(self):
        for node in ast.walk(self.tree):
            meth = getattr(self, "visit_" + type(node).__name__, None)
            if meth:
                meth(node)
            for field in ("body", "orelse", "finalbody"):
                block = getattr(node, field, None)
                if isinstance(block, list) and block and isinstance(block[0], ast.stmt):
                    self.scan_block(block)
        self.module_level()
        self.token_rules()
        self.apply_noqa()
        seen, unique = set(), []
        for f in sorted(self.findings, key=lambda f: (f["line"], f["col"], f["rule"])):
            key = (f["line"], f["rule"])
            if key not in seen:
                seen.add(key)
                unique.append(f)
        return unique

    # ---------- statement-sequence rules ----------
    def scan_block(self, block):
        for i, stmt in enumerate(block):
            nxt = block[i + 1] if i + 1 < len(block) else None
            # PY015 append loop: out = [] ; for x in y: out.append(...)
            if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name)
                    and isinstance(nxt, ast.For) and not nxt.orelse):
                name = stmt.targets[0].id
                body = nxt.body
                if len(body) == 1 and isinstance(body[0], ast.If) and not body[0].orelse and len(body[0].body) == 1:
                    body = body[0].body
                if len(body) == 1:
                    b = body[0]
                    if (isinstance(stmt.value, ast.List) and not stmt.value.elts and isinstance(b, ast.Expr)
                            and isinstance(b.value, ast.Call) and dotted(b.value.func) == f"{name}.append"):
                        self.add("PY015", nxt, f"`{name}` is built by a for/append loop; use a list comprehension")
                    elif (isinstance(stmt.value, ast.Dict) and not stmt.value.keys and isinstance(b, ast.Assign)
                          and isinstance(b.targets[0], ast.Subscript) and dotted(b.targets[0].value) == name):
                        self.add("PY015", nxt, f"`{name}` is built by a for loop; use a dict comprehension")
            # PY013 manual counter: i = 0 ; for ...: ... i += 1
            if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name)
                    and isinstance(stmt.value, ast.Constant) and stmt.value.value in (0, 1)
                    and isinstance(nxt, ast.For)):
                name = stmt.targets[0].id
                for b in nxt.body:
                    if (isinstance(b, ast.AugAssign) and isinstance(b.op, ast.Add) and isinstance(b.target, ast.Name)
                            and b.target.id == name and isinstance(b.value, ast.Constant) and b.value.value == 1):
                        self.add("PY013", nxt, f"`{name}` is a hand-rolled counter; use enumerate()")
                        break
            # PY016 any/all
            if (isinstance(stmt, ast.For) and not stmt.orelse and len(stmt.body) == 1
                    and isinstance(stmt.body[0], ast.If) and not stmt.body[0].orelse
                    and len(stmt.body[0].body) == 1 and isinstance(stmt.body[0].body[0], ast.Return)
                    and isinstance(nxt, ast.Return)):
                inner, outer = stmt.body[0].body[0].value, nxt.value
                if (isinstance(inner, ast.Constant) and isinstance(outer, ast.Constant)
                        and isinstance(inner.value, bool) and isinstance(outer.value, bool)
                        and inner.value != outer.value):
                    fn = "any" if inner.value else "all (with the condition negated)"
                    self.add("PY016", stmt, f"loop + early return of a bool; use {fn}()")
            # PY046 walrus: m = re.search(...); if m:
            if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name)
                    and isinstance(stmt.value, ast.Call) and isinstance(nxt, ast.If)):
                name = stmt.targets[0].id
                q = self.qualname(stmt.value.func) or ""
                is_candidate = (q in ("re.match", "re.search", "re.fullmatch") or q.endswith(".get")
                    or q.endswith((".match", ".search", ".fullmatch")))
                t = nxt.test
                tests_name = (isinstance(t, ast.Name) and t.id == name) or (
                    isinstance(t, ast.Compare) and isinstance(t.left, ast.Name) and t.left.id == name
                    and isinstance(t.ops[0], ast.IsNot) and isinstance(t.comparators[0], ast.Constant)
                    and t.comparators[0].value is None)
                if is_candidate and tests_name:
                    self.add("PY046", stmt, f"`{name} = ...` followed by `if {name}`; use `if {name} := ...:`")

    # ---------- node rules ----------
    def visit_FunctionDef(self, node):
        args = node.args
        defaults = list(args.defaults) + [d for d in args.kw_defaults if d is not None]
        for d in defaults:
            if (isinstance(d, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp))
                    or (isinstance(d, ast.Call) and (dotted(d.func) or "").split(".")[-1] in MUTABLE_CALLS)):
                self.add("PY001", d, f"mutable default `{ast.unparse(d)}` in {node.name}() is created once and shared "
                                     "across calls")
        for a in args.posonlyargs + args.args + args.kwonlyargs + [args.vararg, args.kwarg]:
            if a is not None and a.arg in BUILTINS:
                self.add("PY024", a, f"parameter `{a.arg}` shadows the builtin {a.arg}()")
        # PY038/37 checked in visit_Call. PY044 sequential await
        if isinstance(node, ast.AsyncFunctionDef):
            for n in self.walk_local(node):
                if isinstance(n, ast.For):
                    for b in n.body:
                        val = getattr(b, "value", None)
                        if isinstance(val, ast.Await) and not (
                                isinstance(val.value, ast.Call) and self.qualname(val.value.func) == "asyncio.sleep"):
                            self.add("PY044", n, "each iteration awaits before starting the next; fan out with "
                                                 "asyncio.gather / TaskGroup (3.11+) behind a Semaphore")
                            break

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ExceptHandler(self, node):
        only_pass = all(isinstance(b, (ast.Pass, ast.Continue)) or (
            isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant) and b.value.value is Ellipsis)
            for b in node.body)
        if node.type is None:
            self.add("PY002", node, "bare `except:`" + (" that silently swallows every error" if only_pass else
                                                         " catches KeyboardInterrupt/SystemExit too"))
            return
        types = node.type.elts if isinstance(node.type, ast.Tuple) else [node.type]
        broad = any(dotted(t) in ("Exception", "BaseException") for t in types)
        if broad and only_pass:
            self.add("PY003", node, f"`except {ast.unparse(node.type)}: pass` hides every failure "
                                    "(rate limits, bad JSON, auth errors)")
        elif broad and all(isinstance(b, ast.Expr) and is_call_to(b.value, "print") for b in node.body):
            self.add("PY003", node, f"`except {ast.unparse(node.type)}` only prints; log with logger.exception() "
                                    "and re-raise or return a typed error")
        elif not broad and only_pass:
            self.add("PY045", node, f"`except {ast.unparse(node.type)}: pass`; use "
                                    f"`with contextlib.suppress({ast.unparse(node.type).strip('()')}):`")

    def visit_Raise(self, node):
        handler = self.in_handler(node)
        if handler is not None and node.exc is not None and node.cause is None and isinstance(node.exc, ast.Call):
            hint = f" from {handler.name}" if handler.name else " from err"
            self.add("PY011", node, f"raising {ast.unparse(node.exc.func)}(...) inside except loses the cause; "
                                    f"add `{hint.strip()}` (or `from None` to hide it deliberately)")

    def visit_Compare(self, node):
        operands = [node.left] + node.comparators
        for op, left, right in zip(node.ops, operands, operands[1:]):
            if isinstance(op, (ast.Eq, ast.NotEq)):
                for side in (left, right):
                    if isinstance(side, ast.Constant) and side.value is None:
                        word = "is" if isinstance(op, ast.Eq) else "is not"
                        self.add("PY006", node, f"`{ast.unparse(node)}`; use `{word} None` (== can be overridden, "
                                                "e.g. numpy/pandas return arrays)")
                    elif isinstance(side, ast.Constant) and isinstance(side.value, bool):
                        self.add("PY007", node, f"`{ast.unparse(node)}`; test truthiness directly")
                for side in (left, right):
                    if is_call_to(side, "type") and len(side.args) == 1:
                        self.add("PY008", node, f"`{ast.unparse(node)}`; use isinstance()")
            if isinstance(op, (ast.Is, ast.IsNot)) and is_call_to(left, "type"):
                self.add("PY008", node, f"`{ast.unparse(node)}`; use isinstance() unless exact type is required")
            if (isinstance(op, (ast.In, ast.NotIn)) and isinstance(right, ast.Call)
                    and isinstance(right.func, ast.Attribute) and right.func.attr == "keys" and not right.args):
                self.add("PY014", node, f"`{ast.unparse(node)}`; test membership on the dict itself")
        if (len(node.ops) == 1 and is_call_to(node.left, "len") and isinstance(node.comparators[0], ast.Constant)):
            op, val = node.ops[0], node.comparators[0].value
            if ((isinstance(op, (ast.Eq, ast.NotEq, ast.Gt)) and val == 0) or (isinstance(op, ast.GtE) and val == 1)
                    or (isinstance(op, ast.Lt) and val == 1)):
                self.add("PY020", node, f"`{ast.unparse(node)}`; use the sequence's truthiness (not for numpy "
                                        "arrays / DataFrames)")

    def _truth_test(self, test):
        if is_call_to(test, "len"):
            self.add("PY020", test, f"`if {ast.unparse(test)}:`; use `if {ast.unparse(test.args[0])}:` "
                                    "(not for numpy arrays / DataFrames)")
        elif isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not) and is_call_to(test.operand, "len"):
            self.add("PY020", test, f"`{ast.unparse(test)}`; use `not {ast.unparse(test.operand.args[0])}`")

    def visit_If(self, node):
        self._truth_test(node.test)
        t = node.test
        # PY017 setdefault / defaultdict
        if (isinstance(t, ast.Compare) and len(t.ops) == 1 and isinstance(t.ops[0], ast.NotIn) and node.body
                and isinstance(node.body[0], ast.Assign) and isinstance(node.body[0].targets[0], ast.Subscript)):
            tgt, val = node.body[0].targets[0], node.body[0].value
            empty = (isinstance(val, (ast.List, ast.Set)) and not val.elts) or (
                isinstance(val, ast.Dict) and not val.keys) or (isinstance(val, ast.Constant) and val.value == 0)
            if empty and same(tgt.value, t.comparators[0]) and same(tgt.slice, t.left):
                self.add("PY017", node, f"`if {ast.unparse(t)}: {ast.unparse(tgt)} = {ast.unparse(val)}`; use "
                                        "collections.defaultdict / Counter or dict.setdefault()")
        # PY029 elif chain on the same subject
        parent = getattr(node, "_parent", None)
        is_elif = isinstance(parent, ast.If) and parent.orelse == [node]
        if not is_elif:
            subject, count, cur = None, 0, node
            while isinstance(cur, ast.If):
                ct = cur.test
                if not (isinstance(ct, ast.Compare) and len(ct.ops) == 1 and isinstance(ct.ops[0], (ast.Eq, ast.In))
                        and isinstance(ct.comparators[0], (ast.Constant, ast.Tuple, ast.List, ast.Set))):
                    break
                if subject is None:
                    subject = ast.dump(ct.left)
                elif ast.dump(ct.left) != subject:
                    break
                count += 1
                cur = cur.orelse[0] if len(cur.orelse) == 1 else None
            if count >= 4:
                self.add("PY029", node, f"{count}-branch if/elif chain on `{ast.unparse(node.test.left)}`; "
                                        "use match/case (3.10+) or a dict dispatch table")
        # PY030 LBYL exists-then-open
        exists = any(isinstance(n, ast.Call) and (
            self.qualname(n.func) in ("os.path.exists", "os.path.isfile")
            or (isinstance(n.func, ast.Attribute) and n.func.attr in ("exists", "is_file")))
            for n in ast.walk(t))
        if exists:
            for n in (x for b in node.body for x in ast.walk(b)):
                if isinstance(n, ast.Call) and (is_call_to(n, "open") or (
                        isinstance(n.func, ast.Attribute) and n.func.attr in ("read_text", "read_bytes", "open"))):
                    self.add("PY030", node, "exists() check followed by open(); the file can vanish in between - "
                                            "try/except FileNotFoundError instead")
                    break

    def visit_While(self, node):
        self._truth_test(node.test)
        if isinstance(node.test, ast.Constant) and node.test.value in (True, 1):
            tries = [n for n in self.walk_local(node) if isinstance(n, ast.Try)]
            sleeps = [n for n in self.walk_local(node) if isinstance(n, ast.Call)
                      and (self.qualname(n.func) or "").endswith("sleep")]
            open_handler = any(not any(isinstance(x, ast.Raise) for x in ast.walk(h)) for t in tries
                               for h in t.handlers)
            if tries and sleeps and open_handler:
                self.add("PY040", node, "`while True` retries on error with no max attempts - a persistent 429/500 "
                                        "or bad key loops forever; bound it (or use tenacity stop_after_attempt)")

    def visit_IfExp(self, node):
        self._truth_test(node.test)

    def visit_For(self, node):
        it = node.iter
        if (is_call_to(it, "range") and it.args and is_call_to(it.args[-1], "len") and len(it.args) <= 2
                and (len(it.args) == 1 or (isinstance(it.args[0], ast.Constant) and it.args[0].value == 0))):
            seq = ast.unparse(it.args[-1].args[0])
            self.add("PY012", node, f"`for ... in {ast.unparse(it)}`; iterate `{seq}` directly, or use "
                                    "enumerate()/zip()")
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute) and it.func.attr == "keys" and not it.args:
            self.add("PY014", node, f"`for ... in {ast.unparse(it)}`; iterate the dict directly (or .items())")
        self._shadow_targets(node.target)

    visit_AsyncFor = visit_For

    def _shadow_targets(self, target):
        for n in ast.walk(target):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id in BUILTINS:
                self.add("PY024", n, f"`{n.id}` shadows the builtin {n.id}()")

    def visit_Assign(self, node):
        if not isinstance(getattr(node, "_parent", None), ast.ClassDef):
            for t in node.targets:
                self._shadow_targets(t)
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Lambda):
            self.add("PY023", node, f"`{node.targets[0].id} = lambda ...`; use a def (better tracebacks, docstring)")
        for t in node.targets:
            self._secret(t, node.value, node)
            self._prompt_concat(t, node.value, node)

    def visit_AnnAssign(self, node):
        if node.value is not None:
            self._secret(node.target, node.value, node)
            self._prompt_concat(node.target, node.value, node)

    def visit_AugAssign(self, node):
        if isinstance(node.op, ast.Add) and isinstance(node.target, ast.Name):
            name = node.target.id
            strish = is_str(node.value) or isinstance(node.value, ast.JoinedStr) or (
                isinstance(node.value, ast.BinOp) and any(is_str(x) or isinstance(x, ast.JoinedStr)
                                                          for x in ast.walk(node.value)))
            if not strish:
                scope = self.enclosing_func(node) or self.tree
                strish = any(isinstance(a, ast.Assign) and is_str(a.value)
                             and any(isinstance(t, ast.Name) and t.id == name for t in a.targets)
                             for a in self.walk_local(scope))
            if strish and self.in_loop(node):
                self.add("PY018", node, f"`{name} += ...` in a loop builds the string quadratically; collect parts "
                                        "in a list and str.join() them")
            elif strish and "prompt" in name.lower():
                self.add("PY043", node, f"`{name}` is assembled piecemeal; use one template with named fields")

    def _secret(self, target, value, node):
        name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", None)
        if (name and SECRET_NAME.search(name) and is_str(value) and len(value.value) >= 8
                and not PLACEHOLDER.match(value.value) and not re.fullmatch(r"[A-Z0-9_]+", value.value)
                and " " not in value.value):
            self.add("PY036", node, f"`{name}` is assigned a literal secret; load it from the environment or a "
                                    "secrets manager and rotate the leaked key")

    def _prompt_concat(self, target, value, node):
        name = getattr(target, "id", None) or getattr(target, "attr", None) or ""
        if "prompt" in name.lower() and isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add):
            leaves, stack = [], [value]
            while stack:
                n = stack.pop()
                if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
                    stack += [n.left, n.right]
                else:
                    leaves.append(n)
            if any(is_str(x) for x in leaves) and any(not isinstance(x, ast.Constant) for x in leaves):
                self.add("PY043", node, f"`{name}` is built with + concatenation; use a template "
                                        "(f-string, str.format_map or a Jinja/prompt template) with named fields")

    def visit_keyword(self, node):
        if (node.arg and SECRET_NAME.search(node.arg) and is_str(node.value) and len(node.value.value) >= 8
                and not PLACEHOLDER.match(node.value.value) and " " not in node.value.value):
            self.add("PY036", node.value, f"`{node.arg}=` is passed a literal secret; read it from os.environ")

    def visit_Constant(self, node):
        if isinstance(node.value, str) and SECRET_VALUE.search(node.value):
            self.add("PY036", node, "string literal looks like a live API key; move it to the environment and "
                                    "revoke it")

    def visit_BinOp(self, node):
        if isinstance(node.op, ast.Mod) and is_str(node.left) and "%" in node.left.value:
            self.add("PY019", node, "%-formatting; use an f-string")

    def visit_Dict(self, node):
        for k, v in zip(node.keys, node.values):
            if (is_str(k) and SECRET_NAME.search(k.value) and is_str(v) and len(v.value) >= 8
                    and not PLACEHOLDER.match(v.value) and " " not in v.value and not v.value.startswith("Bearer {")):
                self.add("PY036", v, f"dict key {k.value!r} holds a literal secret; read it from os.environ")

    def visit_UnaryOp(self, node):
        if isinstance(node.op, ast.Not) and isinstance(node.operand, ast.Compare) and len(node.operand.ops) == 1:
            op = node.operand.ops[0]
            if isinstance(op, (ast.In, ast.Is)):
                better = "not in" if isinstance(op, ast.In) else "is not"
                c = node.operand
                self.add("PY021", node, f"`{ast.unparse(node)}`; write "
                                        f"`{ast.unparse(c.left)} {better} {ast.unparse(c.comparators[0])}`")

    def visit_BoolOp(self, node):
        if isinstance(node.op, ast.Or):
            firsts = [ast.dump(v.args[0]) for v in node.values if is_call_to(v, "isinstance") and len(v.args) == 2]
            if any(firsts.count(f) > 1 for f in firsts):
                self.add("PY022", node, "several isinstance() calls on the same object; pass a tuple of types")

    def visit_ImportFrom(self, node):
        if any(a.name == "*" for a in node.names):
            self.add("PY010", node, f"`from {node.module} import *`; import the names you use")
        if node.module == "typing":
            old = [a.name for a in node.names if a.name in TYPING_ALIASES]
            if old:
                self.add("PY031", node, f"typing.{', typing.'.join(old)}; use builtin/collections generics "
                                        "(list[str], dict[str, int]) on 3.9+")

    def visit_Global(self, node):
        self.add("PY028", node, f"`global {', '.join(node.names)}`; prefer a cached factory, a class, or "
                                "dependency injection")

    def visit_Call(self, node):
        q = self.qualname(node.func) or ""
        last = q.split(".")[-1]
        if is_call_to(node, "eval", "exec"):
            self.add("PY004", node, f"{node.func.id}() executes arbitrary code; parse model/user output with "
                                    "json.loads, ast.literal_eval or a pydantic model")
        if q.startswith("subprocess.") and any(k.arg == "shell" and isinstance(k.value, ast.Constant)
                                               and k.value.value is True for k in node.keywords):
            self.add("PY005", node, "shell=True with a built string allows injection; pass an argument list")
        if q in ("os.system", "os.popen"):
            self.add("PY005", node, f"{q}() runs through the shell; use subprocess.run([...], check=True)")
        # open()
        if is_call_to(node, "open") or q == "io.open":
            parent = getattr(node, "_parent", None)
            if isinstance(parent, (ast.Assign, ast.AnnAssign)) or (
                    isinstance(parent, ast.Attribute) and parent.value is node):
                self.add("PY009", node, "open() outside a with-block; the handle is closed only when garbage "
                                        "collected (and never on error)")
            mode = node.args[1] if len(node.args) > 1 else getattr(kwarg(node, "mode"), "value", None)
            binary = is_str(mode) and "b" in mode.value
            dynamic_mode = mode is not None and not is_str(mode)
            if (not binary and not dynamic_mode and kwarg(node, "encoding") is None and len(node.args) < 4
                    and not has_star_kwargs(node)):
                self.add("PY026", node, "open() in text mode without encoding= uses the platform default "
                                        "(cp1252 on Windows); pass encoding=\"utf-8\"")
        if (isinstance(node.func, ast.Attribute) and node.func.attr in ("read_text", "write_text")
                and kwarg(node, "encoding") is None and not has_star_kwargs(node)
                and len(node.args) < (1 if node.func.attr == "read_text" else 2)):
            self.add("PY026", node, f".{node.func.attr}() without encoding=; pass encoding=\"utf-8\"")
        # format
        if isinstance(node.func, ast.Attribute) and node.func.attr == "format" and is_str(node.func.value):
            self.add("PY019", node, "str.format() on a literal; use an f-string")
        # os.path / glob
        if q.startswith("os.path.") or q in OS_PATH_CALLS:
            self.add("PY025", node, f"{q}(); pathlib.Path does this with operators and methods")
        if last in ("utcnow", "utcfromtimestamp") and "datetime" in q:
            self.add("PY027", node, f"{q}() returns a naive datetime; use datetime.now(timezone.utc)")
        # print
        if is_call_to(node, "print") and kwarg(node, "file") is None:
            fn = self.enclosing_func(node)
            if (isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and not PRINT_OK_FUNCS.match(fn.name)
                    and not self.in_main_guard(node)):
                self.add("PY034", node, f"print() inside {fn.name}(); use logging so level, format and "
                                        "destination are configurable")
        # logging eager formatting
        if isinstance(node.func, ast.Attribute) and node.func.attr in LOG_METHODS and node.args:
            owner = (dotted(node.func.value) or "").lower()
            if "log" in owner.split(".")[-1]:
                first = node.args[1] if node.func.attr == "log" and len(node.args) > 1 else node.args[0]
                eager = isinstance(first, ast.JoinedStr) or (
                    isinstance(first, ast.BinOp) and isinstance(first.op, (ast.Mod, ast.Add))) or (
                    isinstance(first, ast.Call) and isinstance(first.func, ast.Attribute)
                    and first.func.attr == "format")
                if eager:
                    self.add("PY035", node, f"{ast.unparse(node.func)}() with a pre-formatted message; pass "
                                            "%-style args so formatting is skipped when the level is off")
        # async blocking
        if self.in_async(node):
            if q == "time.sleep":
                self.add("PY037", node, "time.sleep() in async def stalls every coroutine; use await "
                                        "asyncio.sleep()")
            elif q in BLOCKING_IN_ASYNC:
                self.add("PY038", node, f"{q}() is blocking inside async def; use an async client "
                                        "(httpx.AsyncClient, asyncio.create_subprocess_exec) or asyncio.to_thread")
        # timeouts
        if ((q in {f"requests.{v}" for v in REQUESTS_VERBS} or q == "urllib.request.urlopen")
                and kwarg(node, "timeout") is None and not has_star_kwargs(node)
                and not (q == "urllib.request.urlopen" and len(node.args) >= 3)):
            self.add("PY039", node, f"{q}() without timeout= waits forever on a stalled connection; "
                                    "pass timeout=(connect, read)")
        if (last in LLM_CLIENTS and q.split(".")[0] in ("openai", "anthropic", "groq", "mistralai", last)
                and kwarg(node, "timeout") is None and not has_star_kwargs(node)):
            self.add("PY042", node, f"{last}() uses the SDK default timeout (up to 10 minutes); set "
                                    "timeout= and max_retries= explicitly")

    # ---------- module-level rules ----------
    def module_level(self):
        for stmt in self.tree.body:
            value = getattr(stmt, "value", None)
            if isinstance(stmt, (ast.Assign, ast.AnnAssign)) and isinstance(value, ast.Call):
                q = self.qualname(value.func) or ""
                last = q.split(".")[-1]
                if last in MODEL_LOADERS or last == "from_pretrained" or q.endswith(".from_pretrained"):
                    self.add("PY041", stmt, f"{last}(...) runs at import time: slow imports, network/GPU work in "
                                            "every test and worker; build it lazily (functools.cache) or in an "
                                            "app lifespan")

    # ---------- token rules ----------
    def token_rules(self):
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(self.source).readline))
        except (tokenize.TokenError, IndentationError, SyntaxError):
            return
        string_rows, comment_rows = set(), set()
        self.comments = {}
        for tok in tokens:
            if tok.type == tokenize.STRING or tok.type == getattr(tokenize, "FSTRING_MIDDLE", -1):
                string_rows.update(range(tok.start[0], tok.end[0]))
            elif tok.type == tokenize.COMMENT:
                comment_rows.add(tok.start[0])
                self.comments[tok.start[0]] = tok.string
            elif tok.type == tokenize.OP and tok.string == ";":
                self.add("PY032", None, "`;` joins statements; put each on its own line",
                         line=tok.start[0], col=tok.start[1])
        for i, raw in enumerate(self.lines, 1):
            if raw.rstrip().endswith("\\") and i not in string_rows and i not in comment_rows:
                self.add("PY033", None, "backslash continuation breaks on trailing whitespace; wrap in parentheses",
                         line=i, col=len(raw.rstrip()) - 1)

    def apply_noqa(self):
        comments = getattr(self, "comments", {})
        kept = []
        for f in self.findings:
            m = NOQA.search(comments.get(f["line"], ""))
            if m and (not m.group("ids") or f["rule"] in re.split(r"[,\s]+", m.group("ids").upper())):
                continue
            kept.append(f)
        self.findings = kept


def resolve_rule_filter(values):
    """Expand comma-separated ids/prefixes into a set of rule ids; raise ValueError on unknown."""
    out = set()
    for v in values or []:
        for tok in filter(None, (t.strip().upper() for t in v.split(","))):
            matched = {rid for rid in RULES if rid.startswith(tok)} or {
                rid for rid, r in RULES.items() if r[0].upper() == tok}
            if not matched:
                raise ValueError(f"unknown rule id or prefix: {tok}")
            out |= matched
    return out


def collect_files(paths):
    files = []
    for p in paths:
        if p == "-":
            files.append("-")
            continue
        path = Path(p)
        if path.is_dir():
            skip = {".git", ".venv", "venv", "__pycache__", "node_modules", ".tox", "build", "dist"}
            files += sorted(f for f in path.rglob("*.py") if not skip & set(f.parts))
        elif path.exists():
            files.append(path)
        else:
            raise FileNotFoundError(f"no such file or directory: {p}")
    return files


def review_source(source, name):
    return Reviewer(source, name).run()


def print_rules():
    print(f"{'ID':6} {'SEVERITY':8} {'NAME':22} TITLE")
    for rid, (name, sev, title, _) in RULES.items():
        print(f"{rid:6} {sev:8} {name:22} {title}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="Python files or folders to review, or - for stdin")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any finding is medium or high severity")
    ap.add_argument("--min-severity", choices=["low", "medium", "high"], default="low",
                    help="hide findings below this severity (default: low)")
    ap.add_argument("--select", action="append", metavar="IDS",
                    help="only run these rule ids/prefixes/names, comma-separated (e.g. PY036,PY04)")
    ap.add_argument("--ignore", action="append", metavar="IDS", help="skip these rule ids/prefixes/names")
    ap.add_argument("--no-fix", action="store_true", help="text mode: do not print suggested rewrites")
    ap.add_argument("--list-rules", action="store_true", help="list every rule and exit")
    args = ap.parse_args(argv)

    if args.list_rules:
        print_rules()
        return 0
    if not args.paths:
        ap.print_usage(sys.stderr)
        print("error: give at least one file, folder or - for stdin", file=sys.stderr)
        return 2
    try:
        selected = resolve_rule_filter(args.select) if args.select else set(RULES)
        selected -= resolve_rule_filter(args.ignore)
        files = collect_files(args.paths)
    except (ValueError, FileNotFoundError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    findings, errors = [], []
    floor = SEVERITY_ORDER[args.min_severity]
    for f in files:
        name = "<stdin>" if f == "-" else str(f)
        try:
            source = sys.stdin.read() if f == "-" else f.read_text(encoding="utf-8")
            results = review_source(source, name)
        except SyntaxError as err:
            errors.append(f"{name}:{err.lineno}: syntax error: {err.msg}")
            continue
        except (OSError, UnicodeDecodeError, ValueError) as err:
            errors.append(f"{name}: cannot read: {err}")
            continue
        findings += [r for r in results if r["rule"] in selected and SEVERITY_ORDER[r["severity"]] <= floor]

    counts = {s: sum(f["severity"] == s for f in findings) for s in SEVERITY_ORDER}
    if args.json:
        print(json.dumps({"files": len(files), "summary": counts, "findings": findings, "errors": errors}, indent=2))
    else:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        for f in findings:
            print(f"{f['path']}:{f['line']}:{f['col']}: {f['rule']} [{f['severity']}] {f['message']}")
            if f["source"]:
                print(f"    {f['line']:>4} | {f['source']}")
            if not args.no_fix:
                fix = f["fix"].splitlines()
                print("    fix: " + fix[0])
                for line in fix[1:]:
                    print("         " + line)
            print()
        if findings:
            print(f"{len(findings)} finding(s) in {len(files)} file(s): {counts['high']} high, "
                  f"{counts['medium']} medium, {counts['low']} low")
        elif not errors:
            print(f"No findings in {len(files)} file(s). Idiomatic as far as static checks can tell.")
    if errors:
        return 2
    if args.strict and (counts["high"] or counts["medium"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
