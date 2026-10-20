---
name: python-idiomatic-code-reviewer
description: "Review Python code for non-idiomatic, unpythonic or risky patterns and rewrite it into clean modern Python: PEP 8 / PEP 20, EAFP vs LBYL, iteration idioms (enumerate, zip, comprehensions, any/all), unpacking, f-strings, pathlib, truthiness, `is None`, mutable defaults, walrus, match statements, collections / itertools / functools, logging instead of print, with-blocks and resource handling. Includes AI-engineering checks: hardcoded API keys, time.sleep or requests inside async def, missing HTTP timeouts, unbounded retry loops, model clients built at import time, prompt string concatenation, sequential awaits, eval() on LLM output. Ships a 46-rule AST reviewer with severities and suggested rewrites. Use when the user asks to review, clean up, modernise, make pythonic or idiomatic, refactor or code-review a .py file, LLM / RAG / agent / FastAPI / training code, a pull request diff, or asks 'is this good Python?' or 'how would a senior Python dev write this?'."
metadata:
  category: programming
  subcategory: python
  version: "1.0.0"
---

# Python Idiomatic Code Reviewer

Review Python the way a senior Python and AI engineer would: find the patterns that are wrong (mutable defaults, swallowed exceptions, blocking calls in async code, leaked keys), the patterns that are fragile (`== None`, `type(x) == T`, check-then-open, unbounded retries) and the patterns that are merely un-Pythonic (`range(len(x))`, manual counters, `%`-formatting, `os.path`). Then give a graded, line-referenced review and a rewritten version that keeps behaviour identical. Static checks come from `scripts/review_idioms.py`; judgement, context and the rewrite come from you.

## Trigger Conditions

Activate this skill when the user:
- Pastes Python and asks "review this", "make it pythonic", "clean this up", "modernise", "is this idiomatic?"
- Asks for a code review of a `.py` file, a PR diff or a notebook cell
- Works on LLM client wrappers, RAG pipelines, agents, tool calling, eval harnesses, FastAPI model services, training or batch inference loops and wants them production-ready
- Asks about a specific idiom: EAFP vs LBYL, walrus, `match`, `enumerate`/`zip`, `defaultdict`, `pathlib`, f-strings, `is None`
- Reports async code that is "slow" or "hangs" (often `time.sleep` / `requests` inside `async def`, or no timeouts)
- Wants to upgrade a codebase to a newer Python (3.9 baseline, 3.10 `match`, 3.11 `TaskGroup`, 3.12 type syntax)

## Workflow

```
1. SCOPE     -> Python version target? library, service, script, or notebook? hot path or one-off?
2. SCAN      -> python scripts/review_idioms.py <file|dir|-> (add --json for tooling)
3. TRIAGE    -> confirm each finding in context; drop false positives; add what static analysis misses
4. GRADE     -> high (bug/security/outage), medium (fragile/likely bug), low (style/idiom)
5. REWRITE   -> smallest behaviour-preserving change per finding; keep public signatures
6. VERIFY    -> re-run the script; run the tests; diff old vs new behaviour on edge cases
7. REPORT    -> findings table, rewritten code, notes on anything deliberately left alone
```

## Severity Model

| Severity | Meaning | Examples | Merge? |
|----------|---------|----------|--------|
| high | Wrong results, security hole, outage or data loss | mutable default, bare/swallowing except, hardcoded key, `time.sleep` in `async def`, `eval` on model output, unbounded retry | Block |
| medium | Fragile; correct today, breaks on edge cases or under load | `== None`, `type(x) == T`, `open()` without `with`, `range(len())`, missing HTTP timeout, client built at import | Fix before merge |
| low | Idiom, readability, consistency | `%`-format, `os.path`, manual counter, `len(x) == 0`, `typing.List` | Suggest; batch |

`--strict` fails (exit 1) on any medium or high finding, which makes it a reasonable CI gate. Full grading guidance and comment templates are in [review-checklist.md](references/review-checklist.md).

## Core Rules

### 1. Correctness first

```python
# Bad: one list shared by every call; chat histories bleed between users
def chat(prompt, history=[]):
    history.append({"role": "user", "content": prompt})
    return history

# Good
def chat(prompt: str, history: list[dict] | None = None) -> list[dict]:  # `X | None` in annotations: 3.10+, or 3.9 with `from __future__ import annotations`
    history = [] if history is None else history
    history.append({"role": "user", "content": prompt})
    return history
```

| Smell | Why it is wrong | Fix |
|-------|-----------------|-----|
| `except:` / `except Exception: pass` | Hides rate limits, auth errors, bugs; bare except also traps Ctrl-C | Catch the specific errors; log with `logger.exception`; re-raise |
| `raise NewError(...)` inside `except` | Original traceback is chained implicitly as "during handling"; intent unclear | `raise NewError(...) from err` (or `from None`) |
| `x == None` | `__eq__` can be overridden; numpy returns an array | `x is None` |
| `type(x) == dict` | Rejects subclasses (`OrderedDict`, pydantic types) | `isinstance(x, dict)` or `collections.abc.Mapping` |
| `f = open(p)` | Leaks the handle on exceptions | `with open(p, encoding="utf-8") as f:` or `Path(p).read_text(encoding="utf-8")` |
| `eval(llm_output)` | Remote code execution via prompt injection | `json.loads`, `ast.literal_eval`, pydantic `model_validate_json` |

### 2. EAFP over LBYL (when the check can race or duplicates work)

```python
# LBYL: file can disappear between exists() and open(); two syscalls
if os.path.exists(cache):
    with open(cache) as f:
        return json.load(f)
return {}

# EAFP
try:
    return json.loads(Path(cache).read_text(encoding="utf-8"))
except FileNotFoundError:
    return {}
```

Use LBYL when the check is cheap, has no race and the failure is the common case (e.g. `if key in mapping` in a tight loop where misses dominate). Use EAFP for I/O, external services, dict access where hits dominate, and duck typing.

### 3. Iteration idioms

| Instead of | Write |
|------------|-------|
| `for i in range(len(xs)): x = xs[i]` | `for x in xs:` |
| `i = 0` ... `i += 1` | `for i, x in enumerate(xs, start=1):` |
| `for i in range(len(a)): f(a[i], b[i])` | `for x, y in zip(a, b, strict=True):` (strict: 3.10+) |
| `for k in d.keys(): v = d[k]` | `for k, v in d.items():` |
| `out = []` + `for` + `append` | `out = [f(x) for x in xs if cond(x)]` |
| `for x in xs: if p(x): return True` / `return False` | `return any(p(x) for x in xs)` |
| `if k not in d: d[k] = []` then `d[k].append(v)` | `d = defaultdict(list); d[k].append(v)` |
| Nested loops over batches | `itertools.batched(xs, n)` (3.12+) or a slicing helper |
| `s += piece` in a loop | `"".join(pieces)` |
| `sorted(xs)[0]` / `sorted(xs)[-1]` | `min(xs)` / `max(xs)`; `heapq.nlargest(k, xs, key=...)` for top-k |

```python
# Top-k retrieval scores without sorting everything
import heapq
top = heapq.nlargest(5, zip(scores, doc_ids))          # [(score, id), ...]
```

### 4. Unpacking, truthiness, comparisons

```python
first, *rest = tokens                   # star unpacking
role, content = message["role"], message["content"]
(prompt_tokens, completion_tokens) = usage

if docs: ...                            # not: if len(docs) > 0
if not results: ...                     # not: if len(results) == 0
if value is None: ...                   # not: if value == None
if 0 < temperature <= 2: ...            # chained comparison
if model in {"gpt-4o", "claude-sonnet-4-5"}: ...   # set membership for literal choices
```

Truthiness caveat for AI code: `if embedding:` raises `ValueError` on a numpy array with more than one element, and `if df:` raises on a DataFrame. Use `arr.size`, `len(arr)`, `df.empty` or `tensor.numel()`. Same for `== True` on masks: use the mask itself.

### 5. Strings

- f-strings everywhere for interpolation; `f"{x!r}"`, `f"{n:,}"`, `f"{dt:%Y-%m-%d}"`, `f"{x = }"` (3.8+) for debug.
- Logging is the exception: `logger.info("loaded %d docs", n)` defers formatting.
- Build large text (context windows, CSV, prompts) with `"\n".join(parts)`.
- Prompt templates live in one constant with named fields (`str.format_map`, `string.Template`, Jinja) rather than in `+` chains spread over a function.
- `str.removeprefix` / `removesuffix` (3.9+) instead of slicing with `len(prefix)`.

### 6. Resources and context managers

```python
with open(src, encoding="utf-8") as fin, open(dst, "w", encoding="utf-8") as fout:
    for line in fin:
        fout.write(line)

# 3.10+: parenthesised context managers across lines
with (
    httpx.Client(timeout=30) as client,
    open("out.jsonl", "w", encoding="utf-8") as out,
):
    ...

# Variable number of resources
from contextlib import ExitStack
with ExitStack() as stack:
    files = [stack.enter_context(open(p, encoding="utf-8")) for p in paths]
```

Always pass `encoding="utf-8"` for text files (PEP 597; the default is the locale encoding, cp1252 on many Windows machines).

### 7. Structure

- `pathlib.Path` over `os.path` / `glob`: `Path(root) / "data" / "train.jsonl"`, `p.suffix`, `p.read_text()`, `p.glob("**/*.md")`.
- `@dataclass(slots=True, frozen=True)` (slots: 3.10+) for config/value objects; pydantic for validated I/O boundaries.
- `enum.Enum` / `StrEnum` (3.11+) for fixed choices instead of magic strings.
- `match` (3.10+) for structural dispatch (message roles, tool-call shapes, AST nodes); dicts for plain value-to-function maps.
- No `from x import *`, no `global`, no lambdas bound to names, no shadowing builtins (`id`, `type`, `input`, `list`).
- Builtin generics `list[str]`, `dict[str, int]` on 3.9+; `X | None` on 3.10+ (or with `from __future__ import annotations` in annotations only).

### 8. Logging, not print

```python
logger = logging.getLogger(__name__)           # module level, cheap, no handlers
logger.debug("retrieved %d chunks for %r", len(chunks), query)
logger.exception("tool call failed")           # inside except: includes the traceback
```

Configure handlers once in the entry point (`logging.basicConfig(level=...)`), never in library modules. `print` is fine in CLIs' `main()` and in notebooks.

## AI-Engineering Rules

| Id | Pattern | Why it matters | Fix |
|----|---------|----------------|-----|
| PY036 | `api_key = "sk-..."` | Keys leak via git, logs, notebooks; bots scrape GitHub within minutes | `os.environ["OPENAI_API_KEY"]`, pydantic-settings `SecretStr`; rotate the key |
| PY037 | `time.sleep()` in `async def` | Freezes every coroutine on the loop (all users of the service) | `await asyncio.sleep()` |
| PY038 | `requests` / `subprocess.run` in `async def` | Same: blocking I/O on the event loop | `httpx.AsyncClient`, `asyncio.create_subprocess_exec`, `asyncio.to_thread` |
| PY039 | `requests.post(url)` with no `timeout` | Default is no timeout; one stalled socket hangs a worker forever | `timeout=(5, 60)` |
| PY040 | `while True:` + `try/except` + `sleep` | A permanent 401/400 retries forever and burns quota | Bounded attempts, exponential backoff + jitter, retry only retryable errors |
| PY041 | `client = OpenAI()` / `SentenceTransformer(...)` at module level | Import-time network/GPU work; breaks tests, forked workers, config overrides | `functools.cache` factory or FastAPI `lifespan` + dependency |
| PY042 | `OpenAI()` without `timeout=` | SDK defaults to a 10-minute timeout with silent retries | `OpenAI(timeout=30, max_retries=3)` |
| PY043 | `prompt = "..." + ctx + "..."` | Hard to read, diff, test and version | Template constant with named fields |
| PY044 | `for x in xs: await call(x)` | N sequential round-trips | `asyncio.gather` / `TaskGroup` behind a `Semaphore` |
| PY004 | `eval(model_output)` | Prompt injection becomes code execution | `json.loads` + schema validation |
| PY034 | `print()` debugging in pipelines | No levels, no request ids, lost in workers | `logging` (structured where possible) |

```python
# Bounded retry with backoff and jitter, retrying only what is retryable
import random, time
from openai import APIConnectionError, RateLimitError

RETRYABLE = (RateLimitError, APIConnectionError)

def complete(client, **kwargs):
    for attempt in range(5):
        try:
            return client.chat.completions.create(**kwargs)
        except RETRYABLE:
            if attempt == 4:
                raise
            time.sleep(min(30, 2 ** attempt) + random.random())
```

Deeper patterns (lifespan-managed clients, streaming, fan-out with semaphores, structured output parsing, batching, settings) are in [ai-engineering-idioms.md](references/ai-engineering-idioms.md).

## What Static Analysis Misses (review by hand)

- Behaviour: is the rewrite actually equivalent? (`any()` short-circuits like the loop; a comprehension does not keep the loop variable after it; `dict.get(k, default)` differs from `try/except KeyError` when the stored value is `None`.)
- Naming and decomposition: 80-line functions, boolean flag parameters, unclear names.
- Concurrency: shared mutable state across threads/tasks, missing `await`, unawaited coroutines, sync SDK clients used from async code through method calls (`client.chat.completions.create` inside `async def`).
- Data: float equality on scores, off-by-one in chunk overlap, tokenizer vs character lengths.
- API contracts: returning `None` vs raising, mixed return types, mutable return values that callers mutate.
- Tests: is the risky path covered?

## Rewrite Discipline

1. Preserve behaviour first, style second. If a fix changes semantics (e.g. tightening `except Exception` to specific errors), say so explicitly.
2. Keep public names and signatures unless the user asked for an API change; deprecate rather than rename.
3. Match the project's minimum Python version. Do not introduce `match`, `X | Y` at runtime, `TaskGroup` or `itertools.batched` below their versions ([modern-python-by-version.md](references/modern-python-by-version.md)).
4. One concern per change; avoid drive-by reformatting that buries the real fix in a diff.
5. Prefer stdlib power tools before new dependencies ([stdlib-power-tools.md](references/stdlib-power-tools.md)).
6. Do not "fix" deliberate patterns: `print` in a CLI's `main`, LBYL in hot loops where misses dominate, `type(x) is bool` when bools must be excluded from ints, module-level clients when the team intends a singleton and has accepted the trade-off.

## Output Format

Return the review in this shape:

1. **Summary**: one or two sentences: overall quality, the most important risk, Python version assumed.
2. **Findings** table, most severe first:

   | # | Line | Rule | Severity | Issue | Fix |
   |---|------|------|----------|-------|-----|
   | 1 | 14 | PY036 | high | API key hardcoded | Read `OPENAI_API_KEY` from env; rotate key |

3. **Rewritten code**: the full revised file or function, behaviour-preserving, with short comments only where a change is non-obvious.
4. **Behaviour changes**: anything the rewrite changes on purpose (exceptions now propagate, timeouts now raise, etc.).
5. **Not changed**: findings deliberately left alone, with the reason.
6. **Next steps**: tests to add, CI gate (`--strict`), follow-up refactors.

For a quick question about one idiom, skip the table: give the before/after and one line of why.

## Scripts

Static review with 46 rules (PY001–PY046), AST + tokenize based, never executes the code:

```bash
python scripts/review_idioms.py app.py                       # human-readable, with suggested rewrites
python scripts/review_idioms.py src/                         # every *.py under a folder
cat app.py | python scripts/review_idioms.py -               # stdin
python scripts/review_idioms.py app.py --json                # {"files", "summary", "findings", "errors"}
python scripts/review_idioms.py app.py --strict              # exit 1 on any medium/high finding (CI gate)
python scripts/review_idioms.py app.py --min-severity medium # hide low findings
python scripts/review_idioms.py app.py --select PY036,PY037,PY038,PY039,PY040   # AI/production risks only
python scripts/review_idioms.py app.py --ignore PY03         # skip PY030-PY039 (prefixes and names work)
python scripts/review_idioms.py app.py --no-fix              # findings only, no rewrite snippets
python scripts/review_idioms.py --list-rules                 # id, severity, name, title for every rule
```

Each finding carries `path:line:col`, rule id, severity, a specific message and a before/after rewrite snippet. Suppress a single line with `# noqa: PY034` (or bare `# noqa`). Exit codes: 0 = done, 1 = `--strict` and a medium/high finding, 2 = usage error, unreadable file or syntax error.

Rule groups: PY001–PY011 correctness and risk; PY012–PY018 iteration idioms; PY019–PY035 and PY045–PY046 modern style; PY036–PY044 AI engineering.

## Additional Resources

| File | Content |
|------|---------|
| [idioms-catalog.md](references/idioms-catalog.md) | 60+ before/after idioms: iteration, unpacking, strings, dicts, comparisons, exceptions, functions, classes, files |
| [ai-engineering-idioms.md](references/ai-engineering-idioms.md) | LLM clients, secrets, async fan-out, retries, timeouts, streaming, prompts, structured output, batching, logging, training loops |
| [review-checklist.md](references/review-checklist.md) | How to run a review, severity grading, false positives per rule, writing review comments, CI setup |
| [modern-python-by-version.md](references/modern-python-by-version.md) | 3.8 → 3.13 features that change idiomatic style, with version gates |
| [stdlib-power-tools.md](references/stdlib-power-tools.md) | collections, itertools, functools, pathlib, contextlib, dataclasses, enum, operator, heapq, bisect quick wins |
