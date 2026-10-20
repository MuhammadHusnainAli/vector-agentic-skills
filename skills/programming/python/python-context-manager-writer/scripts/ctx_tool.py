#!/usr/bin/env python3
"""Find resource-handling bugs and scaffold correct context managers.

`leaks` statically analyses Python source (it never imports or runs it) and
reports resources opened outside `with` (files, sqlite3/psycopg connections,
sockets, temp files/dirs, zip/tar archives, subprocess.Popen, thread/process
pools, httpx/aiohttp/requests clients, urlopen), Lock/Semaphore .acquire()
without a try/finally release, @contextmanager generators whose cleanup is
skipped on exceptions or that yield more than once, except-blocks around
`yield` that silently swallow errors, __exit__ methods that always return a
truthy value (swallowing every exception), wrong __exit__ signatures,
sync/async protocol mix-ups, `with threading.Lock():` on a fresh lock, and
torch.no_grad()/suppress() objects created but never entered.

`scaffold` prints a complete, typed, documented context manager (class,
generator, async class, async generator, or a ready-made AI-engineering
recipe) and verifies it with ast.parse before printing.

Usage:
    python ctx_tool.py leaks app.py
    python ctx_tool.py leaks src/ --json
    cat app.py | python ctx_tool.py leaks - --strict          # exit 1 on medium/high findings
    python ctx_tool.py leaks app.py --strict --fail-on high
    python ctx_tool.py rules                                   # list rule ids
    python ctx_tool.py scaffold vector_tx --kind generator \\
        --setup "conn = pool.getconn()" --teardown "pool.putconn(conn)" --yields conn
    python ctx_tool.py scaffold ModelSession --kind async-class \\
        --setup "self.client = httpx.AsyncClient()" --teardown "await self.client.aclose()" \\
        --import "import httpx"
    python ctx_tool.py scaffold --recipe atomic-write
    python ctx_tool.py scaffold --list-recipes

Exit codes:
    0  no findings (or findings without --strict), scaffold printed
    1  --strict and at least one finding at or above --fail-on (default: medium)
    2  usage error, unreadable file, Python syntax error, or generated code failed ast.parse

Standard library only. Python 3.9+.
"""

import argparse
import ast
import json
import os
import re
import sys
import textwrap

# ---------------------------------------------------------------------------
# Rule catalogue
# ---------------------------------------------------------------------------

RULES = {
    "CTX001": ("resource-outside-with", "Resource opened outside `with` and not closed in a finally block"),
    "CTX002": ("acquire-without-finally", "Lock/Semaphore .acquire() without a try/finally release"),
    "CTX003": ("cm-yield-not-protected", "@contextmanager yield not inside try/finally: cleanup skipped on exception"),
    "CTX004": ("cm-yield-count", "@contextmanager generator must yield exactly once on every path"),
    "CTX005": ("exit-always-suppresses", "__exit__/__aexit__ returns a truthy value unconditionally (swallows all exceptions)"),
    "CTX006": ("enter-returns-none", "__enter__/__aenter__ returns None, so `with X() as x` binds None"),
    "CTX007": ("cm-except-swallows", "except around `yield` in @contextmanager does not re-raise (suppresses the body's exception)"),
    "CTX008": ("exit-signature", "__exit__/__aexit__ must accept (self, exc_type, exc, tb)"),
    "CTX009": ("sync-async-mismatch", "Sync/async protocol mix-up (async def __exit__, def __aenter__, @contextmanager on async def...)"),
    "CTX010": ("sync-with-async-resource", "Async-only resource used with plain `with` (needs `async with`)"),
    "CTX011": ("fresh-lock-in-with", "`with Lock():` creates a new lock each time and provides no mutual exclusion"),
    "CTX012": ("cm-never-entered", "Context manager object created as a bare statement and never entered (no effect)"),
}
SEV_RANK = {"low": 1, "medium": 2, "high": 3}

# fully-qualified constructor -> (label, cleanup method, async-only)
RESOURCES = {
    "open": ("file", "close", False),
    "io.open": ("file", "close", False),
    "codecs.open": ("file", "close", False),
    "gzip.open": ("gzip file", "close", False),
    "gzip.GzipFile": ("gzip file", "close", False),
    "bz2.open": ("bz2 file", "close", False),
    "lzma.open": ("lzma file", "close", False),
    "sqlite3.connect": ("sqlite3 connection", "close", False),
    "psycopg.connect": ("psycopg connection", "close", False),
    "psycopg2.connect": ("psycopg2 connection", "close", False),
    "socket.socket": ("socket", "close", False),
    "socket.create_connection": ("socket", "close", False),
    "socket.create_server": ("socket", "close", False),
    "tempfile.NamedTemporaryFile": ("temporary file", "close", False),
    "tempfile.TemporaryFile": ("temporary file", "close", False),
    "tempfile.SpooledTemporaryFile": ("temporary file", "close", False),
    "tempfile.TemporaryDirectory": ("temporary directory", "cleanup", False),
    "tempfile.mkdtemp": ("temporary directory (mkdtemp, not a context manager)", "shutil.rmtree", False),
    "zipfile.ZipFile": ("zip archive", "close", False),
    "tarfile.open": ("tar archive", "close", False),
    "tarfile.TarFile": ("tar archive", "close", False),
    "subprocess.Popen": ("subprocess", "wait", False),
    "concurrent.futures.ThreadPoolExecutor": ("thread pool", "shutdown", False),
    "concurrent.futures.ProcessPoolExecutor": ("process pool", "shutdown", False),
    "concurrent.futures.thread.ThreadPoolExecutor": ("thread pool", "shutdown", False),
    "multiprocessing.Pool": ("process pool", "close", False),
    "multiprocessing.pool.Pool": ("process pool", "close", False),
    "multiprocessing.pool.ThreadPool": ("thread pool", "close", False),
    "httpx.Client": ("httpx client", "close", False),
    "httpx.AsyncClient": ("httpx async client", "aclose", True),
    "aiohttp.ClientSession": ("aiohttp session", "close", True),
    "requests.Session": ("requests session", "close", False),
    "requests.session": ("requests session", "close", False),
    "requests.sessions.Session": ("requests session", "close", False),
    "urllib.request.urlopen": ("HTTP response", "close", False),
}
# Bare names recognised even when the import is not visible (snippets).
BARE_FALLBACK = {
    "ThreadPoolExecutor": "concurrent.futures.ThreadPoolExecutor",
    "ProcessPoolExecutor": "concurrent.futures.ProcessPoolExecutor",
    "NamedTemporaryFile": "tempfile.NamedTemporaryFile",
    "TemporaryDirectory": "tempfile.TemporaryDirectory",
    "Popen": "subprocess.Popen",
    "AsyncClient": "httpx.AsyncClient",
    "ClientSession": "aiohttp.ClientSession",
}
CLOSERS = {
    "close", "aclose", "cleanup", "shutdown", "terminate", "kill", "wait", "communicate", "release",
    "rmtree", "remove", "unlink", "join", "__exit__", "__aexit__", "stop", "dispose", "disconnect",
}
OWNERSHIP_WRAPPERS = {"closing", "aclosing", "enter_context", "enter_async_context", "push", "push_async_exit"}
LOCK_FACTORIES = {
    "threading.Lock", "threading.RLock", "threading.Semaphore", "threading.BoundedSemaphore",
    "threading.Condition", "asyncio.Lock", "asyncio.Semaphore", "asyncio.BoundedSemaphore",
    "asyncio.Condition", "multiprocessing.Lock", "multiprocessing.RLock",
}
NEVER_ENTERED = {
    "torch.no_grad", "torch.inference_mode", "torch.enable_grad", "torch.autocast", "torch.amp.autocast",
    "torch.cuda.amp.autocast", "torch.cpu.amp.autocast", "torch.autograd.profiler.profile",
    "torch.profiler.profile", "contextlib.suppress", "contextlib.redirect_stdout",
    "contextlib.redirect_stderr", "contextlib.nullcontext", "contextlib.chdir", "contextlib.ExitStack",
    "contextlib.AsyncExitStack", "warnings.catch_warnings", "decimal.localcontext",
    "numpy.errstate", "unittest.mock.patch", "unittest.mock.patch.object", "unittest.mock.patch.dict",
}
FUNC_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)
SCOPE_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module, ast.Lambda)


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

ALIASES = (("directory", "tmpdir"), ("client", "client"), ("session", "session"), ("connection", "conn"),
           ("socket", "sock"), ("pool", "pool"), ("subprocess", "proc"), ("archive", "archive"),
           ("response", "resp"))


def alias_for(label, parent):
    """Variable name for the suggested `with ... as NAME` rewrite."""
    if isinstance(parent, (ast.Assign, ast.AnnAssign)):
        tgt = parent.targets[0] if isinstance(parent, ast.Assign) else parent.target
        if isinstance(tgt, ast.Name):
            return tgt.id
    for key, alias in ALIASES:
        if key in label:
            return alias
    return "f"


def unparse(node):
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover - defensive
        return "<expr>"


def dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return list(reversed(parts))
    return None


class Analyzer:
    def __init__(self, tree, source, filename):
        self.tree = tree
        self.lines = source.splitlines()
        self.filename = filename
        self.findings = []
        self.parents = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                self.parents[child] = node
        self.aliases = {}
        self.local_defs = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.asname:
                        self.aliases[a.asname] = a.name
                    else:
                        top = a.name.split(".")[0]
                        self.aliases[top] = top
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                for a in node.names:
                    if a.name != "*":
                        self.aliases[a.asname or a.name] = node.module + "." + a.name
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.local_defs.add(node.name)

    # -- generic helpers ---------------------------------------------------
    def resolve(self, func):
        parts = dotted(func)
        if not parts:
            return None
        head = parts[0]
        if head in self.aliases:
            return ".".join([self.aliases[head]] + parts[1:])
        if len(parts) == 1 and head in BARE_FALLBACK and head not in self.local_defs:
            return BARE_FALLBACK[head]
        return ".".join(parts)

    def add(self, rule, node, severity, message, fix=None):
        self.findings.append({
            "file": self.filename,
            "line": getattr(node, "lineno", 0),
            "col": getattr(node, "col_offset", 0) + 1,
            "rule": rule,
            "name": RULES[rule][0],
            "severity": severity,
            "message": message,
            "fix": fix,
        })

    def ancestors(self, node):
        while node in self.parents:
            node = self.parents[node]
            yield node

    def enclosing(self, node, types):
        for anc in self.ancestors(node):
            if isinstance(anc, types):
                return anc
        return None

    def stmt_of(self, node):
        cur = node
        while cur is not None and not isinstance(cur, ast.stmt):
            cur = self.parents.get(cur)
        return cur

    def walk_local(self, root):
        """Walk `root` without descending into nested functions/classes/lambdas."""
        stack = list(ast.iter_child_nodes(root))
        while stack:
            node = stack.pop()
            yield node
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            stack.extend(ast.iter_child_nodes(node))

    def in_field(self, node, owner, field):
        """True if `node` sits (transitively) inside owner.<field>."""
        children = getattr(owner, field, None) or []
        if not isinstance(children, list):
            children = [children]
        targets = set()
        for child in children:
            targets.add(child)
        cur = node
        while cur is not None and cur is not owner:
            if cur in targets:
                return True
            cur = self.parents.get(cur)
        return False

    # -- run ---------------------------------------------------------------
    def run(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                self.check_call(node)
            elif isinstance(node, FUNC_TYPES):
                self.check_function(node)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                self.check_with(node)
        self.findings.sort(key=lambda f: (f["line"], f["col"], f["rule"]))
        return self.findings

    # -- calls -------------------------------------------------------------
    def resource_of(self, call):
        name = self.resolve(call.func)
        if name in RESOURCES:
            return name, RESOURCES[name]
        # Path(...).open() / some_path.open()
        if isinstance(call.func, ast.Attribute) and call.func.attr == "open":
            recv = call.func.value
            if isinstance(recv, ast.Call) and (self.resolve(recv.func) or "").split(".")[-1] in ("Path", "PurePath"):
                return "pathlib.Path.open", ("file", "close", False)
            parts = dotted(recv)
            if parts and re.search(r"path$", parts[-1], re.I):
                return "pathlib.Path.open", ("file", "close", False)
        return None, None

    def check_call(self, call):
        name = self.resolve(call.func)
        if isinstance(call.func, ast.Attribute) and call.func.attr == "acquire":
            self.check_acquire(call)
            return
        if name in NEVER_ENTERED:
            parent = self.parents.get(call)
            if isinstance(parent, ast.Expr):
                self.add("CTX012", call, "medium",
                         f"`{unparse(call)}` builds a context manager and throws it away; it has no effect "
                         "unless entered.",
                         f"with {unparse(call)}:\n    ...  # code that should run under it")
            return
        rname, info = self.resource_of(call)
        if info:
            self.check_resource(call, rname, info)

    def check_resource(self, call, rname, info):
        label, closer, async_only = info
        node, parent = call, self.parents.get(call)
        if isinstance(parent, ast.Await):
            node, parent = parent, self.parents.get(parent)
        text = unparse(call)
        kw = "async with" if async_only else "with"
        alias = alias_for(label, parent)

        if isinstance(parent, ast.withitem):
            with_node = self.parents.get(parent)
            if async_only and isinstance(with_node, ast.With):
                self.add("CTX010", call, "high",
                         f"{label} `{text}` only supports `async with`; plain `with` raises at runtime.",
                         f"async with {text} as {alias}:\n    ...")
            return
        if isinstance(parent, ast.keyword):
            parent = self.parents.get(parent)
        if isinstance(parent, ast.Call) and parent is not call:
            pname = (dotted(parent.func) or [""])[-1]
            if pname in OWNERSHIP_WRAPPERS:
                return
            if isinstance(self.parents.get(parent), ast.withitem):
                return  # wrapper such as io.TextIOWrapper(open(...)) owned by the with
        if isinstance(parent, (ast.Return, ast.Yield, ast.YieldFrom, ast.Lambda)):
            return  # ownership handed to the caller
        if rname == "tempfile.mkdtemp":
            fix = "with tempfile.TemporaryDirectory() as tmpdir:\n    ...  # removed automatically, even on error"
        else:
            fix = f"{kw} {text} as {alias}:\n    ..."

        if isinstance(parent, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            targets = parent.targets if isinstance(parent, ast.Assign) else [parent.target]
            for tgt in targets:
                self.check_owned(call, tgt, label, closer, fix, rname)
            return
        if isinstance(parent, ast.Expr):
            self.add("CTX001", call, "high",
                     f"{label} `{text}` is created and discarded; it is never closed.", fix)
        elif isinstance(parent, ast.Attribute):
            self.add("CTX001", call, "medium",
                     f"{label} `{text}` is used inline (`.{parent.attr}`) and left for the garbage collector "
                     "to close (ResourceWarning; leaks on PyPy and in long-running workers).", fix)
        else:
            self.add("CTX001", call, "medium",
                     f"{label} `{text}` is passed along without an owner that closes it.", fix)

    def check_owned(self, call, target, label, closer, fix, rname=""):
        names = []
        if isinstance(target, (ast.Tuple, ast.List)):
            names = [unparse(e) for e in target.elts if isinstance(e, (ast.Name, ast.Attribute))]
        elif isinstance(target, (ast.Name, ast.Attribute)):
            names = [unparse(target)]
        if not names:
            self.add("CTX001", call, "low",
                     f"{label} stored in `{unparse(target)}`; make sure some owner closes it.", fix)
            return
        is_self_attr = all(n.startswith("self.") for n in names)
        func = self.enclosing(call, FUNC_TYPES)
        if is_self_attr:
            scope = self.enclosing(call, ast.ClassDef) or func or self.tree
        else:
            scope = func or self.tree
        status = self.cleanup_status(scope, names, call)
        if status == "escapes" and rname == "tempfile.mkdtemp":
            status = "none"  # passing a path string around does not transfer cleanup duty
        if status == "unsafe" and is_self_attr:
            status = "safe"  # released by a close()/__exit__ method of the owning class
        shown = ", ".join(names)
        if status == "safe":
            return
        if status == "escapes":
            self.add("CTX001", call, "low",
                     f"{label} `{shown}` is handed to another object/function; confirm that owner closes it.", fix)
            return
        if status == "unsafe":
            self.add("CTX001", call, "medium",
                     f"{label} `{shown}` is closed, but not in a finally block: an exception before the "
                     f"close leaks it.", fix)
            return
        if is_self_attr:
            self.add("CTX001", call, "medium",
                     f"{label} `{shown}` is owned by the class but no close()/__exit__/__aexit__ releases it.",
                     "def close(self) -> None:\n    " + names[0] + "." + closer + "()\n\n"
                     "def __enter__(self):\n    return self\n\n"
                     "def __exit__(self, exc_type, exc, tb) -> None:\n    self.close()")
        elif scope is self.tree:
            self.add("CTX001", call, "low",
                     f"module-level {label} `{shown}` is never closed; close it on shutdown "
                     "(FastAPI lifespan, atexit) or create it inside a `with`.", fix)
        else:
            self.add("CTX001", call, "high", f"{label} `{shown}` is never closed (no {closer}() / with).", fix)

    def closes(self, call, names):
        """Does this Call release one of `names`?"""
        func = call.func
        if isinstance(func, ast.Attribute):
            if func.attr in CLOSERS and unparse(func.value) in names:
                return True
            if func.attr in CLOSERS and any(unparse(a) in names for a in call.args):
                return True
            if func.attr in ("enter_context", "enter_async_context", "callback", "push_async_callback", "finalize"):
                for a in call.args:
                    t = unparse(a)
                    if t in names or any(t.startswith(n + ".") for n in names):
                        return True
        elif isinstance(func, ast.Name):
            if func.id in CLOSERS and any(unparse(a) in names for a in call.args):
                return True
            if func.id in ("closing", "aclosing", "finalize"):
                return any(unparse(a) in names or any(unparse(a).startswith(n + ".") for n in names)
                           for a in call.args)
        return False

    def cleanup_status(self, scope, names, origin):
        status = "none"
        for node in ast.walk(scope):
            if isinstance(node, ast.Try) and node.finalbody:
                for stmt in node.finalbody:
                    for sub in ast.walk(stmt):
                        if isinstance(sub, ast.Call) and self.closes(sub, names):
                            return "safe"
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    ce = item.context_expr
                    if unparse(ce) in names:
                        return "safe"
                    if isinstance(ce, ast.Call) and self.closes(ce, names):
                        return "safe"
                    if isinstance(ce, ast.Call) and any(unparse(a) in names for a in ce.args):
                        return "safe"
            elif isinstance(node, ast.Return) and node.value is not None:
                vals = node.value.elts if isinstance(node.value, ast.Tuple) else [node.value]
                if any(unparse(v) in names for v in vals):
                    return "safe"
            elif isinstance(node, ast.Assign) and unparse(node.value) in names:
                if any(unparse(t).startswith("self.") or isinstance(t, (ast.Attribute, ast.Subscript))
                       for t in node.targets):
                    return "safe"  # ownership moved to an object attribute/container
            elif isinstance(node, ast.Call) and node is not origin:
                if self.closes(node, names):
                    if self.closing_in_handler(node):
                        status = "unsafe" if status != "escapes" else status
                    elif status == "none":
                        status = "unsafe"
                elif status == "none" and any(unparse(a) in names for a in node.args) \
                        and not (isinstance(node.func, ast.Attribute) and unparse(node.func.value) in names):
                    status = "escapes"
        return status

    def closing_in_handler(self, node):
        return any(isinstance(a, ast.ExceptHandler) for a in self.ancestors(node))

    def check_acquire(self, call):
        recv = unparse(call.func.value)
        if isinstance(self.parents.get(call), ast.withitem):
            return
        node = call
        if isinstance(self.parents.get(node), ast.Await):
            node = self.parents[node]
        stmt = self.stmt_of(node)
        if stmt is None:
            return
        scope = self.enclosing(call, FUNC_TYPES) or self.tree
        if getattr(scope, "name", "") in ("__enter__", "__aenter__"):
            cls = self.parents.get(scope)
            if isinstance(cls, ast.ClassDef) and self.class_releases(cls, recv):
                return  # acquired on enter, released on exit: the protocol is the try/finally
        names = {recv}
        if isinstance(stmt, (ast.Assign, ast.AnnAssign)) and self.parents.get(node) is stmt:
            tgts = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            names |= {unparse(t) for t in tgts}
        released_in_finally, released_anywhere, inside_try = False, False, False
        for t in ast.walk(scope):
            if isinstance(t, ast.Try) and t.finalbody:
                for s in t.finalbody:
                    for sub in ast.walk(s):
                        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                                and sub.func.attr == "release" \
                                and (unparse(sub.func.value) in names or any(unparse(a) in names for a in sub.args)):
                            released_in_finally = True
                            if self.in_field(stmt, t, "body"):
                                inside_try = True
            if isinstance(t, ast.Call) and isinstance(t.func, ast.Attribute) and t.func.attr == "release" \
                    and unparse(t.func.value) in names:
                released_anywhere = True
        fix = (f"async with {recv}:\n    ..." if isinstance(node, ast.Await) else f"with {recv}:\n    ...")
        if released_in_finally and inside_try:
            self.add("CTX002", call, "low",
                     f"`{recv}.acquire()` is inside the try whose finally releases it: if acquire() raises "
                     "(timeout, cancellation) the finally releases a lock you never held. Acquire before `try:`.",
                     fix)
        elif released_in_finally:
            return
        elif released_anywhere:
            self.add("CTX002", call, "high",
                     f"`{recv}` is released, but not in a finally block: an exception between acquire and "
                     "release deadlocks every later caller.", fix)
        else:
            self.add("CTX002", call, "high", f"`{recv}.acquire()` has no matching release() in a finally block.",
                     fix)

    def class_releases(self, cls, recv):
        for item in cls.body:
            if isinstance(item, FUNC_TYPES) and item.name in ("__exit__", "__aexit__"):
                for sub in ast.walk(item):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                            and sub.func.attr == "release" and unparse(sub.func.value) == recv:
                        return True
        return False

    # -- with statements ---------------------------------------------------
    def check_with(self, node):
        for item in node.items:
            ce = item.context_expr
            if isinstance(ce, ast.Call):
                name = self.resolve(ce.func)
                if name in LOCK_FACTORIES:
                    kw = "async with" if name.startswith("asyncio.") else "with"
                    self.add("CTX011", ce, "high",
                             f"`{unparse(ce)}` creates a brand-new lock on every entry, so nothing is ever "
                             "excluded. Create the lock once (module, __init__, or app state) and reuse it.",
                             f"_lock = {unparse(ce)}  # once, shared\n...\n{kw} _lock:\n    ...")

    # -- functions ---------------------------------------------------------
    def decorator_names(self, fn):
        out = []
        for d in fn.decorator_list:
            target = d.func if isinstance(d, ast.Call) else d
            parts = dotted(target)
            if parts:
                out.append(parts[-1])
        return out

    def check_function(self, fn):
        decos = self.decorator_names(fn)
        is_async = isinstance(fn, ast.AsyncFunctionDef)
        if "contextmanager" in decos or "asynccontextmanager" in decos:
            if "contextmanager" in decos and is_async:
                self.add("CTX009", fn, "high",
                         f"`{fn.name}` is `async def` but decorated with @contextmanager; use "
                         "@asynccontextmanager and `async with`.", "@asynccontextmanager\nasync def " + fn.name + "(...):")
            if "asynccontextmanager" in decos and not is_async:
                self.add("CTX009", fn, "high",
                         f"`{fn.name}` is a plain def decorated with @asynccontextmanager; make it `async def` "
                         "or use @contextmanager.", "@contextmanager\ndef " + fn.name + "(...):")
            self.check_cm_generator(fn)
        cls = self.parents.get(fn)
        if isinstance(cls, ast.ClassDef):
            self.check_dunder(fn, cls, is_async)

    def check_cm_generator(self, fn):
        yields = sorted((n for n in self.walk_local(fn) if isinstance(n, (ast.Yield, ast.YieldFrom))),
                        key=lambda n: (n.lineno, n.col_offset))
        if not yields:
            self.add("CTX004", fn, "high",
                     f"@contextmanager `{fn.name}` never yields: entering it raises "
                     "\"generator didn't yield\" (or TypeError).",
                     "try:\n    yield resource\nfinally:\n    cleanup()")
            return
        for y in yields:
            loop = None
            for anc in self.ancestors(y):
                if anc is fn:
                    break
                if isinstance(anc, (ast.For, ast.AsyncFor, ast.While)):
                    loop = anc
                    break
            if loop is not None:
                self.add("CTX004", y, "high",
                         f"`yield` inside a loop in @contextmanager `{fn.name}`: a second iteration raises "
                         "RuntimeError(\"generator didn't stop\").",
                         "Build the value first, then yield exactly once outside the loop.")
        reported = False
        for i, a in enumerate(yields):
            for b in yields[i + 1:]:
                if not self.exclusive(a, b, fn) and not reported:
                    reported = True
                    self.add("CTX004", b, "high",
                             f"@contextmanager `{fn.name}` can yield twice (lines {a.lineno} and {b.lineno}); "
                             "a yield in an except/finally after the main yield raises "
                             "RuntimeError(\"generator didn't stop after throw()\").",
                             "try:\n    yield value\nexcept SomeError:\n    handle()\n    raise\nfinally:\n    cleanup()")
        for y in yields:
            self.check_yield_protection(fn, y)

    def exclusive(self, a, b, fn):
        pa = [a] + [x for x in self.ancestors(a)]
        pb = [b] + [x for x in self.ancestors(b)]
        set_b = {id(x): x for x in pb}
        lca, child_a = None, None
        prev = a
        for x in pa[1:]:
            if id(x) in set_b:
                lca = x
                child_a = prev
                break
            prev = x
        if lca is None:
            return False
        child_b = b
        for x in pb[1:]:
            if x is lca:
                break
            child_b = x
        if isinstance(lca, ast.If):
            return (child_a in lca.body) != (child_b in lca.body)
        if isinstance(lca, ast.IfExp):
            return child_a is not child_b and lca.test not in (child_a, child_b)
        match_case = getattr(ast, "match_case", None)
        if match_case is not None and isinstance(child_a, match_case) and isinstance(child_b, match_case):
            return child_a is not child_b
        return False

    def check_yield_protection(self, fn, y):
        stmt = self.stmt_of(y)
        protected = False
        for anc in self.ancestors(y):
            if anc is fn:
                break
            if isinstance(anc, ast.Try) and self.in_field(y, anc, "body"):
                if anc.finalbody:
                    protected = True
                if anc.handlers:
                    protected = True
                    self.check_handlers(fn, anc, y)
            elif isinstance(anc, (ast.With, ast.AsyncWith)) and self.in_field(y, anc, "body"):
                protected = True
        if protected:
            return
        # Is there any code that runs after the yield (i.e., cleanup)?
        after = []
        cur = stmt
        while cur is not None and cur is not fn:
            parent = self.parents.get(cur)
            for field in ("body", "orelse", "finalbody"):
                block = getattr(parent, field, None)
                if isinstance(block, list) and cur in block:
                    after.extend(block[block.index(cur) + 1:])
            cur = parent
        after = [s for s in after if not (isinstance(s, ast.Return) and s.value is None)
                 and not isinstance(s, (ast.Pass, ast.Raise))]
        if not after:
            return
        cleanup = "\n".join("    " + unparse(s).splitlines()[0] for s in after[:3])
        yv = unparse(y.value) if getattr(y, "value", None) is not None else ""
        self.add("CTX003", y, "high",
                 f"cleanup after `yield` in `{fn.name}` (line {after[0].lineno}) is skipped when the with-body "
                 "raises: the exception is thrown in at the yield and never reaches it.",
                 f"try:\n    yield {yv}".rstrip() + f"\nfinally:\n{cleanup}")

    def check_handlers(self, fn, try_node, y):
        for h in try_node.handlers:
            reraises = any(isinstance(n, ast.Raise) for n in self.walk_local(h))
            if reraises:
                continue
            caught = unparse(h.type) if h.type is not None else "everything"
            self.add("CTX007", h, "medium",
                     f"`except {caught}` around the yield in `{fn.name}` does not re-raise, so exceptions "
                     "raised inside the with-block are silently suppressed. Intentional only for "
                     "suppress()-style managers.",
                     f"except {unparse(h.type) if h.type is not None else 'BaseException'}:\n    rollback()\n    raise")

    def check_dunder(self, fn, cls, is_async):
        name = fn.name
        if name in ("__enter__", "__exit__") and is_async:
            self.add("CTX009", fn, "high",
                     f"`async def {name}` in `{cls.name}`: the sync protocol never awaits it. Use "
                     f"`{name.replace('__', '__a', 1)}` and `async with`.",
                     f"async def {name.replace('__', '__a', 1)}(self, ...):")
        if name in ("__aenter__", "__aexit__") and not is_async:
            self.add("CTX009", fn, "high",
                     f"`{name}` in `{cls.name}` must be `async def`; `async with` awaits its result.",
                     f"async def {name}(self, ...):")
        if name in ("__exit__", "__aexit__"):
            npos = len(getattr(fn.args, "posonlyargs", [])) + len(fn.args.args)
            if fn.args.vararg is None and npos != 4:
                self.add("CTX008", fn, "high",
                         f"`{cls.name}.{name}` takes {npos} positional parameters; Python calls it with "
                         "(self, exc_type, exc, tb), so leaving the with-block raises TypeError.",
                         f"def {name}(self, exc_type, exc, tb) -> None:")
            for r in self.walk_local(fn):
                if isinstance(r, ast.Return) and r.value is not None and self.truthy(r.value) \
                        and self.unconditional(r, fn):
                    self.add("CTX005", r, "high",
                             f"`{cls.name}.{name}` always returns `{unparse(r.value)}`, which suppresses every "
                             "exception from the with-body (including real bugs such as KeyError, and "
                             "KeyboardInterrupt). Return None/False, or True only for specific handled types.",
                             "def __exit__(self, exc_type, exc, tb) -> bool:\n    self.close()\n"
                             "    return exc_type is not None and issubclass(exc_type, ExpectedError)")
        if name in ("__enter__", "__aenter__"):
            returns_value = any(isinstance(r, ast.Return) and r.value is not None for r in self.walk_local(fn))
            has_yield = any(isinstance(r, (ast.Yield, ast.YieldFrom)) for r in self.walk_local(fn))
            if not returns_value and not has_yield:
                used_as = self.bound_with_as(cls.name)
                sev = "medium" if used_as else "low"
                where = f" (line {used_as} binds it with `as`)" if used_as else ""
                self.add("CTX006", fn, sev,
                         f"`{cls.name}.{name}` returns None, so `with {cls.name}(...) as x` binds x to None{where}.",
                         f"{'async ' if is_async else ''}def {name}(self) -> \"{cls.name}\":\n    ...\n    return self")

    def bound_with_as(self, cls_name):
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    ce = item.context_expr
                    if item.optional_vars is not None and isinstance(ce, ast.Call) \
                            and (dotted(ce.func) or [""])[-1] == cls_name:
                        return node.lineno
        return 0

    @staticmethod
    def truthy(value):
        if isinstance(value, ast.Constant):
            return bool(value.value)
        return isinstance(value, ast.Name) and value.id == "self"

    def unconditional(self, node, fn):
        for anc in self.ancestors(node):
            if anc is fn:
                return True
            if isinstance(anc, (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler)):
                return False
            if isinstance(anc, ast.Try) and not self.in_field(node, anc, "finalbody") and anc.handlers:
                return False
            if type(anc).__name__ in ("Match", "match_case"):
                return False
        return True


# ---------------------------------------------------------------------------
# leaks command
# ---------------------------------------------------------------------------

def iter_files(paths):
    for p in paths:
        if p == "-" or os.path.isfile(p):
            yield p, True
        elif os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "node_modules", "venv", ".venv"))
                for f in sorted(files):
                    if f.endswith(".py"):
                        yield os.path.join(root, f), False
        else:
            raise FileNotFoundError(p)


def analyse_source(source, filename):
    tree = ast.parse(source, filename=filename)
    return Analyzer(tree, source, filename).run()


def cmd_leaks(args):
    findings, warnings, scanned = [], [], 0
    try:
        files = list(iter_files(args.paths))
    except FileNotFoundError as e:
        print(f"error: no such file or directory: {e}", file=sys.stderr)
        return 2
    for path, explicit in files:
        try:
            if path == "-":
                source = sys.stdin.read()
            else:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
        except (OSError, UnicodeDecodeError) as e:
            if explicit:
                print(f"error: cannot read {path}: {e}", file=sys.stderr)
                return 2
            warnings.append(f"skipped {path}: {e}")
            continue
        name = "<stdin>" if path == "-" else path
        try:
            findings.extend(analyse_source(source, name))
        except SyntaxError as e:
            msg = f"{name}:{e.lineno}: syntax error: {e.msg}"
            if explicit:
                print(f"error: {msg}", file=sys.stderr)
                return 2
            warnings.append("skipped " + msg)
            continue
        scanned += 1
    if args.min_severity:
        findings = [f for f in findings if SEV_RANK[f["severity"]] >= SEV_RANK[args.min_severity]]
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in ("high", "medium", "low")}
    failing = [f for f in findings if SEV_RANK[f["severity"]] >= SEV_RANK[args.fail_on]]

    if args.json:
        print(json.dumps({"files_scanned": scanned, "findings": findings, "summary": counts,
                          "warnings": warnings}, indent=2))
    else:
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
        for f in findings:
            print(f"{f['file']}:{f['line']}:{f['col']}  {f['severity'].upper():<6} {f['rule']} {f['name']}")
            for line in textwrap.wrap(f["message"], 96):
                print(f"    {line}")
            if f["fix"]:
                print("    suggested fix:")
                print(textwrap.indent(f["fix"], "        "))
            print()
        if findings:
            print(f"{len(findings)} finding(s) in {scanned} file(s): "
                  f"{counts['high']} high, {counts['medium']} medium, {counts['low']} low")
        else:
            print(f"No resource-handling issues found in {scanned} file(s).")
    return 1 if (args.strict and failing) else 0


def cmd_rules(args):
    if args.json:
        print(json.dumps({rid: {"name": n, "summary": s} for rid, (n, s) in RULES.items()}, indent=2))
    else:
        for rid, (n, s) in RULES.items():
            print(f"{rid}  {n:<26} {s}")
    return 0


# ---------------------------------------------------------------------------
# scaffold command
# ---------------------------------------------------------------------------

def camel(name):
    if "_" not in name and name[:1].isupper():
        return name
    return "".join(p[:1].upper() + p[1:] for p in name.split("_") if p)


def snake(name):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def block(code, indent):
    code = (code or "").replace("\\n", "\n").strip("\n")
    if not code.strip():
        code = "pass"
    return textwrap.indent(textwrap.dedent(code), " " * indent)


def scaffold_kind(name, kind, setup, teardown, yields, imports):
    setup_desc = (setup or "nothing").replace("\\n", "; ").strip()
    teardown_desc = (teardown or "nothing").replace("\\n", "; ").strip()
    header = ['"""Generated by ctx_tool.py scaffold."""', "", "from __future__ import annotations", ""]
    if kind in ("class", "async-class"):
        cls = camel(name)
        is_async = kind == "async-class"
        a = "a" if is_async else ""
        adef = "async def" if is_async else "def"
        aw = "async with" if is_async else "with"
        ret = yields or "self"
        ret_type = '"' + cls + '"' if ret == "self" else "Any"
        header += ["from types import TracebackType", "from typing import Any, Optional, Type"]
        header += list(imports) + ["", "", ""]
        body = f'''class {cls}:
    """Run setup on entry and teardown on exit, even if the body raises.

    Setup:    {setup_desc}
    Teardown: {teardown_desc}

    Exceptions from the body are never suppressed (``__{a}exit__`` returns None).
    Single use and not re-entrant: create a new instance for every ``{aw}``.

    Example::

        {aw} {cls}() as cm:
            ...
    """

    def __init__(self) -> None:
        self._active = False

    {adef} __{a}enter__(self) -> {ret_type}:
        if self._active:
            raise RuntimeError("{cls} is not re-entrant; create a new instance")
{block(setup, 8)}
        self._active = True
        return {ret}

    {adef} __{a}exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        try:
{block(teardown, 12)}
        finally:
            self._active = False
'''
        return "\n".join(header) + body
    is_async = kind == "async-generator"
    deco = "asynccontextmanager" if is_async else "contextmanager"
    it = "AsyncIterator" if is_async else "Iterator"
    adef = "async def" if is_async else "def"
    aw = "async with" if is_async else "with"
    fn = snake(name) if name[:1].isupper() else name
    ytype = "Any" if yields else "None"
    header += [f"from contextlib import {deco}", f"from typing import Any, {it}"] + list(imports) + ["", "", ""]
    body = f'''@{deco}
{adef} {fn}() -> {it}[{ytype}]:
    """Run setup, yield {yields or 'None'}, and always run teardown.

    Setup:    {setup_desc}
    Teardown: {teardown_desc}

    Setup runs before ``try`` so a failed setup does not trigger teardown of
    something that was never acquired. The body's exception is re-raised.

    Example::

        {aw} {fn}(){' as value' if yields else ''}:
            ...
    """
{block(setup, 4)}
    try:
        yield {yields or 'None'}
    finally:
{block(teardown, 8)}
'''
    return "\n".join(header) + body


RECIPES = {}


def recipe(name, default):
    def deco(fn):
        RECIPES[name] = (default, fn.__doc__.strip(), fn)
        return fn
    return deco


@recipe("timer", "Timer")
def _r_timer():
    """Wall-clock timer (sync class, also usable as a decorator) for LLM calls, retrieval, batches."""
    return '''"""Timer context manager / decorator for latency measurements."""

from __future__ import annotations

import logging
import time
from contextlib import ContextDecorator
from types import TracebackType
from typing import Optional, Type

logger = logging.getLogger(__name__)


class __NAME__(ContextDecorator):
    """Measure elapsed wall time with time.perf_counter().

    ``elapsed`` is set even when the body raises, and the exception propagates.

    Example::

        with __NAME__("retrieval") as t:
            docs = retriever.search(query, k=8)
        print(f"{t.label}: {t.elapsed * 1000:.1f} ms")

        @__NAME__("embed_batch")
        def embed_batch(texts: list[str]) -> list[list[float]]: ...
    """

    def __init__(self, label: str = "block", log: bool = True) -> None:
        self.label = label
        self.log = log
        self.start: Optional[float] = None
        self.elapsed: float = 0.0

    def __enter__(self) -> "__NAME__":
        self.start = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        assert self.start is not None
        self.elapsed = time.perf_counter() - self.start
        if self.log:
            status = "error" if exc_type else "ok"
            logger.info("%s took %.1f ms (%s)", self.label, self.elapsed * 1000, status)
'''


@recipe("temp-env", "temp_env")
def _r_env():
    """Temporarily set/unset environment variables (API keys, model endpoints) and restore them."""
    return '''"""Temporarily override environment variables."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Optional


@contextmanager
def __NAME__(**overrides: Optional[str]) -> Iterator[None]:
    """Set env vars for the duration of the block; ``None`` unsets a variable.

    The previous values (including "was not set") are restored in ``finally``.
    os.environ is process-global: do not use this from concurrent threads/tasks.

    Example::

        with __NAME__(OPENAI_API_KEY="sk-test", HTTPS_PROXY=None):
            client = make_client()
    """
    saved = {key: os.environ.get(key) for key in overrides}
    try:
        for key, value in overrides.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, old in saved.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
'''


@recipe("cwd", "working_directory")
def _r_cwd():
    """Temporarily change the working directory (contextlib.chdir on 3.11+), e.g. for agent sandboxes."""
    return '''"""Temporarily change the current working directory."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Union


@contextmanager
def __NAME__(path: Union[str, "os.PathLike[str]"]) -> Iterator[Path]:
    """chdir into ``path`` and always chdir back.

    Python 3.11+ ships ``contextlib.chdir`` with the same behaviour. The cwd is
    process-global, so do not use this from concurrent threads or asyncio tasks;
    pass ``cwd=`` to subprocess.run instead where you can.

    Example::

        with __NAME__(sandbox_dir) as here:
            subprocess.run(["python", "tool.py"], check=True)
    """
    previous = os.getcwd()
    os.chdir(path)
    try:
        yield Path(os.getcwd())
    finally:
        os.chdir(previous)
'''


@recipe("gpu-inference", "inference_session")
def _r_gpu():
    """eval() + torch.inference_mode() + optional autocast, restoring train mode and freeing CUDA cache."""
    return '''"""Inference context for PyTorch models."""

from __future__ import annotations

import gc
from contextlib import ExitStack, contextmanager
from typing import Iterator, Optional

import torch


@contextmanager
def __NAME__(
    model: torch.nn.Module,
    *,
    amp_dtype: Optional[torch.dtype] = None,
    empty_cache: bool = False,
) -> Iterator[torch.nn.Module]:
    """Put ``model`` in eval mode under inference_mode (and autocast), then restore.

    - The original ``model.training`` flag is restored even on error, so a
      validation pass inside a training loop does not leave dropout disabled.
    - ``amp_dtype`` (torch.float16 / torch.bfloat16) enables autocast on the
      model's device type.
    - ``empty_cache`` runs gc + torch.cuda.empty_cache() on exit; this returns
      cached blocks to the driver but does not free tensors you still reference.

    Example::

        with __NAME__(model, amp_dtype=torch.bfloat16) as m:
            logits = m(input_ids)
    """
    was_training = model.training
    first_param = next(model.parameters(), None)
    device_type = first_param.device.type if first_param is not None else "cpu"
    with ExitStack() as stack:
        model.eval()
        stack.callback(model.train, was_training)
        if empty_cache:
            stack.callback(_free_cuda_cache)
        stack.enter_context(torch.inference_mode())
        if amp_dtype is not None:
            stack.enter_context(torch.autocast(device_type=device_type, dtype=amp_dtype))
        yield model


def _free_cuda_cache() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
'''


@recipe("atomic-write", "atomic_write")
def _r_atomic():
    """Write a file atomically (temp file in same dir + fsync + os.replace) for checkpoints and indexes."""
    return '''"""Atomic file writes: readers never see a half-written file."""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any, Iterator, Union


@contextmanager
def __NAME__(
    path: Union[str, "os.PathLike[str]"],
    mode: str = "w",
    encoding: Union[str, None] = "utf-8",
) -> Iterator[IO[Any]]:
    """Yield a temp file next to ``path``; on success fsync and os.replace it into place.

    On any exception the temp file is deleted and ``path`` is untouched, so a
    crash mid-save never corrupts the previous checkpoint/index/manifest.
    Use ``mode="wb"`` (encoding is then ignored) for torch.save / numpy.save.

    Example::

        with __NAME__("ckpt/model.pt", mode="wb") as f:
            torch.save(model.state_dict(), f)
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    binary = "b" in mode
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, mode, encoding=None if binary else encoding) as fh:
            yield fh
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
'''


@recipe("semaphore", "RateLimiter")
def _r_sem():
    """Async concurrency + rate limiter (asyncio.Semaphore with min spacing) for LLM/embedding fan-out."""
    return '''"""Async concurrency limiter for API fan-out."""

from __future__ import annotations

import asyncio
import time
from types import TracebackType
from typing import Optional, Type


class __NAME__:
    """Cap in-flight requests and enforce a minimum interval between starts.

    Create ONE instance and share it across tasks; ``async with`` it around each
    call. The slot is released even if the call raises or the task is cancelled.

    Example::

        limiter = __NAME__(max_concurrency=8, min_interval=0.05)

        async def embed(text: str) -> list[float]:
            async with limiter:
                resp = await client.embeddings.create(model="text-embedding-3-small", input=text)
                return resp.data[0].embedding

        vectors = await asyncio.gather(*(embed(t) for t in texts))
    """

    def __init__(self, max_concurrency: int = 8, min_interval: float = 0.0) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")
        self._sem = asyncio.Semaphore(max_concurrency)
        self._min_interval = min_interval
        self._last_start = 0.0
        self._start_lock = asyncio.Lock()

    async def __aenter__(self) -> "__NAME__":
        await self._sem.acquire()
        try:
            if self._min_interval:
                async with self._start_lock:
                    wait = self._last_start + self._min_interval - time.monotonic()
                    if wait > 0:
                        await asyncio.sleep(wait)
                    self._last_start = time.monotonic()
        except BaseException:
            self._sem.release()
            raise
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        self._sem.release()
'''


@recipe("span", "span")
def _r_span():
    """OpenTelemetry-style tracing span with nesting via contextvars, attributes, error status, duration."""
    return '''"""Minimal tracing spans (OpenTelemetry-style) for LLM pipelines."""

from __future__ import annotations

import contextvars
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional


@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_id: Optional[str]
    attributes: Dict[str, Any] = field(default_factory=dict)
    start: float = 0.0
    duration_ms: float = 0.0
    status: str = "ok"
    error: Optional[str] = None

    def set(self, key: str, value: Any) -> None:
        self.attributes[key] = value


_current: contextvars.ContextVar[Optional[Span]] = contextvars.ContextVar("current_span", default=None)
FINISHED: List[Span] = []


@contextmanager
def __NAME__(
    name: str,
    exporter: Callable[[Span], None] = FINISHED.append,
    **attributes: Any,
) -> Iterator[Span]:
    """Open a child of the current span; record duration, attributes and errors.

    contextvars makes nesting correct across threads and asyncio tasks. The
    exception is recorded and re-raised, never swallowed.

    Example::

        with __NAME__("rag.answer", query=q) as s:
            with __NAME__("retrieve", k=8):
                docs = retriever.search(q, k=8)
            with __NAME__("llm.generate", model="gpt-4o-mini") as g:
                resp = llm(prompt)
                g.set("tokens.total", resp.usage.total_tokens)
    """
    parent = _current.get()
    s = Span(
        name=name,
        trace_id=parent.trace_id if parent else uuid.uuid4().hex,
        span_id=uuid.uuid4().hex[:16],
        parent_id=parent.span_id if parent else None,
        attributes=dict(attributes),
        start=time.perf_counter(),
    )
    token = _current.set(s)
    try:
        yield s
    except BaseException as exc:
        s.status = "error"
        s.error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        s.duration_ms = (time.perf_counter() - s.start) * 1000
        _current.reset(token)
        exporter(s)
'''


@recipe("seed", "seeded")
def _r_seed():
    """Deterministic seeds for random/numpy/torch inside a block, restoring the previous RNG state."""
    return '''"""Deterministic RNG block for evals and tests."""

from __future__ import annotations

import random
from contextlib import contextmanager
from typing import Any, Dict, Iterator


@contextmanager
def __NAME__(seed: int = 0) -> Iterator[int]:
    """Seed Python, NumPy and PyTorch (if installed); restore their states on exit.

    Restoring keeps the rest of the program's randomness unaffected, so a seeded
    eval block inside a training loop does not change later shuffles.
    Note: full GPU determinism also needs torch.use_deterministic_algorithms(True)
    and CUBLAS_WORKSPACE_CONFIG; that is process-wide and not toggled here.

    Example::

        with __NAME__(1234):
            sample = random.sample(dataset, 100)
    """
    saved: Dict[str, Any] = {"random": random.getstate()}
    try:
        import numpy as np
    except ImportError:
        np = None
    try:
        import torch
    except ImportError:
        torch = None
    if np is not None:
        saved["numpy"] = np.random.get_state()
    if torch is not None:
        saved["torch"] = torch.random.get_rng_state()
        if torch.cuda.is_available():
            saved["cuda"] = torch.cuda.get_rng_state_all()
    try:
        random.seed(seed)
        if np is not None:
            np.random.seed(seed)
        if torch is not None:
            torch.manual_seed(seed)  # also seeds all CUDA devices
        yield seed
    finally:
        random.setstate(saved["random"])
        if np is not None:
            np.random.set_state(saved["numpy"])
        if torch is not None:
            torch.random.set_rng_state(saved["torch"])
            if "cuda" in saved:
                torch.cuda.set_rng_state_all(saved["cuda"])
'''


def cmd_scaffold(args):
    if args.list_recipes:
        if args.json:
            print(json.dumps({k: {"default_name": v[0], "summary": v[1]} for k, v in RECIPES.items()}, indent=2))
        else:
            for k, (default, doc, _) in RECIPES.items():
                print(f"{k:<14} {default:<20} {doc}")
        return 0
    if args.recipe:
        default, _, fn = RECIPES[args.recipe]
        name = args.name or default
        if not name.isidentifier():
            print(f"error: NAME {name!r} is not a valid Python identifier", file=sys.stderr)
            return 2
        if default[:1].isupper():
            name = camel(name)
        code = fn().replace("__NAME__", name)
        kind = "recipe:" + args.recipe
    else:
        if not args.name:
            print("error: scaffold needs NAME (or --recipe / --list-recipes)", file=sys.stderr)
            return 2
        if not args.name.isidentifier():
            print(f"error: NAME {args.name!r} is not a valid Python identifier", file=sys.stderr)
            return 2
        code = scaffold_kind(args.name, args.kind, args.setup, args.teardown, args.yields, args.imports or [])
        kind = args.kind
    try:
        ast.parse(code)
    except SyntaxError as e:
        print(f"error: generated code does not parse (line {e.lineno}: {e.msg}); check --setup/--teardown/"
              f"--yields/--import snippets.\n\n{code}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"kind": kind, "code": code, "verified": "ast.parse"}, indent=2))
    else:
        print(code, end="" if code.endswith("\n") else "\n")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command")

    lk = sub.add_parser("leaks", help="find resource leaks and context-manager bugs (static, never runs code)")
    lk.add_argument("paths", nargs="+", help="Python files, directories (recursed), or - for stdin")
    lk.add_argument("--json", action="store_true", help="machine-readable output")
    lk.add_argument("--strict", action="store_true", help="exit 1 if any finding is at or above --fail-on")
    lk.add_argument("--fail-on", choices=["low", "medium", "high"], default="medium",
                    help="severity that fails --strict (default: medium)")
    lk.add_argument("--min-severity", choices=["low", "medium", "high"], help="hide findings below this severity")

    ru = sub.add_parser("rules", help="list rule ids")
    ru.add_argument("--json", action="store_true")

    sc = sub.add_parser("scaffold", help="print a typed, documented context manager (verified with ast.parse)")
    sc.add_argument("name", nargs="?", help="function or class name (CamelCase is applied for class kinds)")
    sc.add_argument("--kind", choices=["class", "generator", "async-class", "async-generator"], default="generator")
    sc.add_argument("--setup", default="", help="code run on entry (use \\n for several lines)")
    sc.add_argument("--teardown", default="", help="code always run on exit (use \\n for several lines)")
    sc.add_argument("--yields", default="", help="expression yielded / returned from __enter__ (default: None / self)")
    sc.add_argument("--import", dest="imports", action="append", help="import line to add (repeatable)")
    sc.add_argument("--recipe", choices=sorted(RECIPES), help="emit a ready-made recipe instead")
    sc.add_argument("--list-recipes", action="store_true", help="list recipes")
    sc.add_argument("--json", action="store_true", help="wrap output in JSON")
    return ap


def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.command == "leaks":
        return cmd_leaks(args)
    if args.command == "rules":
        return cmd_rules(args)
    if args.command == "scaffold":
        return cmd_scaffold(args)
    ap.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
