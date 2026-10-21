#!/usr/bin/env python3
"""Find deadlock, hang and starvation risks in asyncio and threaded Python code.

Static analysis only: files are parsed with `ast`, never imported or executed.
The scanner builds a per-module lock-order graph from nested `with lock:` /
`async with lock:` blocks and `.acquire()` calls (following one level of calls
to functions and methods defined in the same module), then reports cycles,
re-entrant acquisitions and the classic blocking mistakes listed below.

  DLK001 lock-order-cycle          two code paths take the same locks in opposite order
  DLK002 reentrant-acquire         a non-reentrant Lock is acquired again while held
                                   (directly or via a call one level deep)
  DLK003 thread-lock-in-async      threading/multiprocessing lock taken inside `async def`
  DLK004 sleep-in-async            time.sleep() inside `async def` freezes the event loop
  DLK005 blocking-wait-in-async    .result() on an executor future, .join(), sync queue get/put,
                                   Event/Condition .wait() or futures.wait() inside `async def`
  DLK006 threadsafe-result-in-loop run_coroutine_threadsafe(...).result() inside `async def`
  DLK007 nested-event-loop         asyncio.run / run_until_complete / run_forever inside `async def`
  DLK008 join-without-task-done    Queue.join() in a module that never calls task_done()
  DLK009 acquire-without-finally   Lock/Semaphore .acquire() not paired with release() in finally
  DLK010 condition-wait-no-loop    Condition.wait() not inside a `while` predicate loop
  DLK011 wait-without-timeout      sync queue get/join or Event/Condition wait with no timeout (low)
  DLK012 executor-self-wait        a task running in an executor submits to the same executor
                                   and waits for the result (pool exhaustion deadlock)
  DLK013 thread-never-joined       non-daemon Thread started and never joined (shutdown hang)
  DLK014 process-join-before-drain Process.join() before draining its multiprocessing Queue
  DLK015 bounded-put-no-consumer   bounded queue filled in a scope that never reads it (low)
  DLK016 unresolved-future         `await fut` on a create_future() result nothing ever sets
  DLK017 fork-with-threads         os.fork / "fork" start method in a module that starts threads
  DLK018 lock-in-signal-handler    signal handler takes a lock or logs (re-entrancy deadlock)

Suppress a finding on its line with `# noqa` or `# noqa: DLK001,DLK009`.

Usage:
    python hang_scan.py app/worker.py
    python hang_scan.py src/ tests/ --json
    cat agent_loop.py | python hang_scan.py -
    python hang_scan.py src/ --strict --ignore DLK011,DLK015
    python hang_scan.py src/ --select DLK001,DLK002,lock-order-cycle
    python hang_scan.py --list-rules

Exit codes: 0 no findings (or findings without --strict), 1 findings with
--strict, 2 usage error, unreadable file or syntax error in a file named on
the command line (files found by walking a directory are warned about and
skipped).

No dependencies (standard library only, Python 3.9+).
"""

import argparse
import ast
import json
import os
import re
import sys

# ---------------------------------------------------------------- rules

RULES = {
    "DLK001": ("lock-order-cycle", "high",
               "Locks acquired in inconsistent order across code paths (classic AB/BA deadlock)",
               "Two tasks/threads each hold one lock and wait forever for the other.",
               "Pick one global order and always take locks in it, e.g. sorted by name:\n"
               "    first, second = sorted((a, b), key=id)\n"
               "    with first, second:\n        ...\n"
               "or merge them into one lock, or never hold one lock while taking another."),
    "DLK002": ("reentrant-acquire", "high",
               "Non-reentrant lock acquired again by the code that already holds it",
               "threading.Lock and asyncio.Lock are not reentrant: the second acquire waits for itself forever.",
               "Split the helper into a locked public method and an unlocked `_helper_locked()` that\n"
               "assumes the caller holds the lock; call the unlocked one while holding it.\n"
               "(threading.RLock is reentrant; asyncio has no RLock by design.)"),
    "DLK003": ("thread-lock-in-async", "medium",
               "threading/multiprocessing lock used inside async def",
               "A contended threading lock blocks the whole event loop thread; if the holder is another\n"
               "task on the same loop it can never release it, so the loop deadlocks.",
               "Use asyncio.Lock for state shared between tasks:\n"
               "    lock = asyncio.Lock()\n    async with lock:\n        ...\n"
               "For state shared with threads, take the threading lock in a thread:\n"
               "    await asyncio.to_thread(update_shared_state)  # 3.9+"),
    "DLK004": ("sleep-in-async", "high",
               "time.sleep() inside async def",
               "time.sleep blocks the event loop thread: every other task (heartbeats, streams, timeouts) stops.",
               "await asyncio.sleep(delay)"),
    "DLK005": ("blocking-wait-in-async", "high",
               "Blocking wait (future.result(), .join(), sync queue, Event.wait) inside async def",
               "The event loop thread blocks; if the thing being waited for needs the loop, it never finishes.",
               "Await an asyncio equivalent or move the wait off the loop:\n"
               "    result = await asyncio.wrap_future(fut)          # concurrent.futures.Future\n"
               "    await asyncio.to_thread(worker.join, 30)          # thread/process join\n"
               "    item = await asyncio.to_thread(sync_q.get, timeout=5)"),
    "DLK006": ("threadsafe-result-in-loop", "high",
               "run_coroutine_threadsafe(...).result() called from inside async def",
               "If the target loop is the current loop, .result() blocks the very loop that must run the\n"
               "coroutine: a guaranteed deadlock. Even for another loop it freezes this one.",
               "Inside the loop just await the coroutine (or a task):\n    result = await coro\n"
               "Across loops: result = await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coro, other))"),
    "DLK007": ("nested-event-loop", "high",
               "asyncio.run / run_until_complete / run_forever inside async def",
               "A loop is already running in this thread: asyncio.run raises RuntimeError, and\n"
               "run_until_complete raises 'This event loop is already running' (or deadlocks with nest_asyncio).",
               "Await the coroutine directly:  result = await main_step()\n"
               "In Jupyter use top-level `await`; in sync code called from a loop, use\n"
               "asyncio.run_coroutine_threadsafe from a worker thread."),
    "DLK008": ("join-without-task-done", "high",
               "Queue.join() but the module never calls task_done()",
               "join() waits until unfinished_tasks reaches 0; without task_done() it never does.",
               "Call task_done() exactly once per get(), in finally:\n"
               "    item = await queue.get()\n    try:\n        await handle(item)\n"
               "    finally:\n        queue.task_done()"),
    "DLK009": ("acquire-without-finally", "high",
               "acquire() without a matching release() in finally",
               "An exception (429, timeout, cancellation) between acquire and release leaks the permit;\n"
               "after N leaks every caller waits forever (rate limiter starvation).",
               "Use the context manager:\n    async with sem:\n        return await call_llm(prompt)\n"
               "or acquire immediately before try/finally:\n"
               "    lock.acquire()\n    try:\n        ...\n    finally:\n        lock.release()"),
    "DLK010": ("condition-wait-no-loop", "medium",
               "Condition.wait() not inside a while-predicate loop",
               "Wakeups can be spurious, stolen by another consumer, or arrive before wait() starts\n"
               "(lost wakeup): re-check the predicate in a loop.",
               "with cond:\n    while not ready():\n        cond.wait(timeout=1.0)\n"
               "or simply: cond.wait_for(ready, timeout=30)"),
    "DLK011": ("wait-without-timeout", "low",
               "Blocking queue get/join or Event/Condition wait without a timeout",
               "If the producer/notifier dies, this thread blocks forever and shutdown hangs.",
               "Pass a timeout and handle it:\n    try:\n        item = q.get(timeout=1.0)\n"
               "    except queue.Empty:\n        if stop.is_set():\n            return\n"
               "or use Queue.shutdown() (3.13+) to wake blocked getters."),
    "DLK012": ("executor-self-wait", "high",
               "Executor task submits to its own executor and waits for the result",
               "Once all workers run outer tasks that wait on inner tasks, no worker is free to run\n"
               "the inner ones: thread pool exhaustion deadlock.",
               "Use a separate executor for inner work, run the inner work inline, or restructure so\n"
               "the caller fans out all leaf tasks itself (no waiting inside workers)."),
    "DLK013": ("thread-never-joined", "medium",
               "Non-daemon Thread started and never joined",
               "Interpreter shutdown waits for every non-daemon thread; a worker blocked on a queue\n"
               "makes the program hang at exit (Ctrl+C appears to do nothing).",
               "Keep a handle, signal it to stop, and join with a timeout:\n"
               "    stop.set(); worker.join(timeout=5)\n"
               "or mark truly disposable helpers daemon=True."),
    "DLK014": ("process-join-before-drain", "high",
               "Process.join() before the multiprocessing Queue it writes to is drained",
               "A child that put() large items does not exit until its feeder thread flushes the pipe;\n"
               "the parent waits in join() and never reads: deadlock (documented in multiprocessing).",
               "Drain first, then join:\n    results = [q.get(timeout=60) for _ in procs]\n"
               "    for p in procs:\n        p.join(timeout=10)"),
    "DLK015": ("bounded-put-no-consumer", "low",
               "Bounded queue is filled in a scope that never reads it and never hands it to a consumer",
               "After maxsize items put() blocks forever.",
               "Start the consumer before producing (and pass it the queue), or use an unbounded queue:\n"
               "    async with asyncio.TaskGroup() as tg:\n        tg.create_task(consume(q))\n"
               "        for doc in docs:\n            await q.put(doc)"),
    "DLK016": ("unresolved-future", "high",
               "await on a Future created with create_future() that nothing in the module resolves",
               "Nobody calls set_result/set_exception/cancel on it, so the awaiting task waits forever.",
               "Resolve it on every path (including errors) and bound the wait:\n"
               "    fut = loop.create_future()\n    pending[req_id] = fut          # resolver: fut.set_result(...)\n"
               "    return await asyncio.wait_for(fut, timeout=30)"),
    "DLK017": ("fork-with-threads", "medium",
               "os.fork / 'fork' start method in a module that also starts threads",
               "fork copies only the calling thread; locks held by other threads (logging, allocator, CUDA,\n"
               "gRPC, BLAS) stay locked forever in the child. 3.12+ warns with DeprecationWarning.",
               "Use the 'spawn' or 'forkserver' start method (forkserver is the Linux default since 3.14):\n"
               "    ctx = multiprocessing.get_context(\"spawn\")\n    with ctx.Pool(4) as pool:\n        ..."),
    "DLK018": ("lock-in-signal-handler", "medium",
               "Signal handler acquires a lock or logs",
               "Python signal handlers run in the main thread between bytecodes, possibly while that thread\n"
               "already holds the same lock: a non-reentrant lock deadlocks, buffered I/O raises.",
               "Only set a flag in the handler and do the work elsewhere:\n"
               "    stop = threading.Event()\n    signal.signal(signal.SIGTERM, lambda *_: stop.set())\n"
               "In asyncio: loop.add_signal_handler(signal.SIGTERM, stop_event.set)"),
}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

PRIMS = {"Lock", "RLock", "Semaphore", "BoundedSemaphore", "Condition", "Event", "Barrier",
         "Queue", "LifoQueue", "PriorityQueue", "SimpleQueue", "JoinableQueue", "CapacityLimiter"}
LOCK_PRIMS = {"Lock", "RLock", "Condition"}
SEM_PRIMS = {"Semaphore", "BoundedSemaphore", "CapacityLimiter"}
QUEUE_PRIMS = {"Queue", "LifoQueue", "PriorityQueue", "SimpleQueue", "JoinableQueue"}
JOINABLE_QUEUES = {"Queue", "LifoQueue", "PriorityQueue", "JoinableQueue"}
EXECUTORS = {"ThreadPoolExecutor", "ProcessPoolExecutor", "InterpreterPoolExecutor"}
ASYNC_FAMILIES = {"asyncio", "anyio", "trio"}
SPAWN_CALLS = {"create_task", "ensure_future", "start_soon", "run_coroutine_threadsafe", "submit",
               "run_in_executor", "to_thread", "call_soon", "call_soon_threadsafe", "call_later"}
LOG_METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}

LOCK_NAME = re.compile(r"(?:^|_)(?:r?lock|mutex)(?:_|$|\d)|^r?lock")
COND_NAME = re.compile(r"(?:^|_)(?:cond|cv|condition|not_empty|not_full)(?:_|$|\d)")
SEM_NAME = re.compile(r"(?:^|_)(?:sem|semaphore|limiter|slots?|permits?)(?:_|$|\d)")
QUEUE_NAME = re.compile(r"(?:^|_)q$|queue")
FUNC_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)
SCOPE_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def dotted(node):
    """Return 'a.b.c' for Name/Attribute chains, else ''."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


def last(name):
    return name.rsplit(".", 1)[-1]


def walk_local(nodes):
    """Walk nodes without descending into nested functions, classes or lambdas."""
    stack = list(nodes)
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, SCOPE_TYPES):
                stack.append(child)


def walk_no_spawn(node):
    """Walk an expression, skipping arguments of calls that run code elsewhere (create_task, submit...)."""
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        if isinstance(n, SCOPE_TYPES):
            continue
        if isinstance(n, ast.Call) and last(dotted(n.func)) in SPAWN_CALLS:
            stack.append(n.func)
            continue
        stack.extend(ast.iter_child_nodes(n))


def header_exprs(st):
    """Expressions evaluated by statement `st` itself (not by its nested blocks)."""
    if isinstance(st, (ast.If, ast.While)):
        return [st.test]
    if isinstance(st, (ast.For, ast.AsyncFor)):
        return [st.iter]
    if isinstance(st, (ast.With, ast.AsyncWith)):
        return [i.context_expr for i in st.items]
    if isinstance(st, SCOPE_TYPES) or type(st).__name__ in ("Try", "TryStar"):
        return []
    if hasattr(st, "cases"):  # match statement (3.10+)
        return [st.subject]
    return [st]


def sub_blocks(st):
    out = []
    for field in ("body", "orelse", "finalbody"):
        block = getattr(st, field, None)
        if isinstance(block, list):
            out.append(block)
    for h in getattr(st, "handlers", []) or []:
        out.append(h.body)
    for c in getattr(st, "cases", []) or []:
        out.append(c.body)
    return out


def kw(call, name):
    for k in call.keywords:
        if k.arg == name:
            return k.value
    return None


def is_true(node):
    return isinstance(node, ast.Constant) and node.value is True


def is_false(node):
    return isinstance(node, ast.Constant) and node.value is False


class FuncInfo:
    def __init__(self, node, cls):
        self.node = node
        self.cls = cls
        self.name = node.name
        self.qual = (cls or "", node.name)
        self.display = f"{cls}.{node.name}" if cls else node.name
        self.is_async = isinstance(node, ast.AsyncFunctionDef)
        self.acq = []    # (lock key, line, held tuple of (key, line))
        self.calls = []  # (callee qual, line, held)


class Module:
    """All module-wide facts the rules need."""

    def __init__(self, path, source, tree):
        self.path = path
        self.lines = source.splitlines()
        self.tree = tree
        self.findings = []
        self.aliases = {}       # local name -> dotted origin
        self.kinds = {}         # normalized key -> (family, prim)
        self.bases = {}         # class name -> base class names (last segment)
        self.funcs = {}         # qual -> FuncInfo
        self.parents = {}
        self.has_task_done = False
        self.resolvers = set()  # last segment of receivers of set_result/set_exception/cancel
        self.threads_started = False
        self.thread_joins = False
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                self.parents[child] = parent

    # ------------------------------------------------------------ helpers
    def add(self, rule, node, message, fix=None):
        line = getattr(node, "lineno", 1)
        src = self.lines[line - 1] if 0 < line <= len(self.lines) else ""
        m = re.search(r"#\s*noqa(?::\s*([A-Z0-9, ]+))?", src)
        if m and (not m.group(1) or rule in [c.strip() for c in m.group(1).split(",")]):
            return
        slug, sev, _title, why, default_fix = RULES[rule]
        key = (rule, line, getattr(node, "col_offset", 0))
        if any((f["rule"], f["line"], f["col"] - 1) == key for f in self.findings):
            return
        self.findings.append({
            "path": self.path, "line": line, "col": getattr(node, "col_offset", 0) + 1,
            "rule": rule, "name": slug, "severity": sev, "message": message, "why": why,
            "code": src.strip(), "fix": fix or default_fix,
        })

    def resolve(self, name):
        if not name:
            return ""
        head, _, rest = name.partition(".")
        origin = self.aliases.get(head)
        if origin:
            return origin + ("." + rest if rest else "")
        return name

    def norm(self, expr, cls):
        d = dotted(expr)
        if not d:
            return ""
        head, _, rest = d.partition(".")
        if cls and head in ("self", "cls") and rest:
            return f"{cls}.{rest}"
        return d

    def classify(self, func_expr):
        """(family, prim) for a constructor reference like threading.Lock / asyncio.Queue."""
        name = self.resolve(dotted(func_expr))
        if not name:
            return None
        parts = name.split(".")
        prim = parts[-1]
        fam = parts[0]
        if prim in EXECUTORS:
            return ("concurrent", prim)
        if prim in ("Thread", "Timer") and fam == "threading":
            return ("threading", prim)
        if prim == "Process" and fam == "multiprocessing":
            return ("multiprocessing", prim)
        if prim == "Future" and fam in ("asyncio", "concurrent"):
            return (fam, "Future")
        if prim not in PRIMS or len(parts) < 2:
            return None
        if fam in ASYNC_FAMILIES:
            return ("asyncio", prim)
        if fam in ("threading", "queue"):
            return ("threading", prim)
        if fam == "multiprocessing":
            return ("multiprocessing", prim)
        return None

    def lookup(self, key):
        """kinds[key], following base classes defined in this module for 'Class.attr' keys."""
        if key in self.kinds:
            return self.kinds[key]
        head, _, attr = key.partition(".")
        seen = set()
        todo = list(self.bases.get(head, ()))
        while todo and attr:
            b = todo.pop()
            if b in seen:
                continue
            seen.add(b)
            if f"{b}.{attr}" in self.kinds:
                return self.kinds[f"{b}.{attr}"]
            todo.extend(self.bases.get(b, ()))
        return None

    def kind(self, expr, cls):
        return self.lookup(self.norm(expr, cls))

    def is_lockish(self, expr, cls):
        """Key when expr is a lock usable for ordering analysis, else ''."""
        if isinstance(expr, ast.Call):
            return ""
        key = self.norm(expr, cls)
        if not key:
            return ""
        k = self.lookup(key)
        if k:
            return key if k[1] in LOCK_PRIMS else ""
        return key if LOCK_NAME.search(last(key).lower()) else ""

    def reentrant(self, key):
        k = self.lookup(key)
        if k:
            return k[1] == "RLock" or (k[1] == "Condition" and k[0] in ("threading", "multiprocessing"))
        return "rlock" in last(key).lower()

    def sync_queue(self, expr, cls):
        k = self.kind(expr, cls)
        return bool(k and k[0] in ("threading", "multiprocessing") and k[1] in QUEUE_PRIMS)

    # ------------------------------------------------------------ pass 1: facts
    def collect(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.asname:
                        self.aliases[a.asname] = a.name
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                for a in node.names:
                    self.aliases[a.asname or a.name] = f"{node.module}.{a.name}"
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                self.bases[node.name] = [last(dotted(b)) for b in node.bases if dotted(b)]
        self._collect_scope(self.tree.body, None)
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "task_done":
                    self.has_task_done = True
                if node.func.attr in ("set_result", "set_exception", "cancel"):
                    self.resolvers.add(last(dotted(node.func.value)))

    def _record_assign(self, target, value, cls, in_class_body):
        if not isinstance(value, ast.Call):
            return
        kind = self.classify(value.func)
        if kind is None and self.resolve(dotted(value.func)) == "multiprocessing.get_context" \
                and isinstance(target, ast.Name):
            self.aliases[target.id] = "multiprocessing"
            return
        if kind is None and last(dotted(value.func)) == "create_future":
            kind = ("asyncio", "Future")
        if kind is None and last(dotted(value.func)) == "field":
            fac = kw(value, "default_factory")
            if fac is not None:
                kind = self.classify(fac)
        if kind is None and isinstance(value.func, ast.Attribute) and value.func.attr in PRIMS \
                and self.aliases.get(dotted(value.func.value)) == "multiprocessing":
            kind = ("multiprocessing", value.func.attr)
        if kind is None:
            return
        if in_class_body and isinstance(target, ast.Name):
            key = f"{cls}.{target.id}"
        else:
            key = self.norm(target, cls)
        if key:
            self.kinds[key] = kind

    def _collect_scope(self, stmts, cls, in_class_body=False):
        for st in stmts:
            if isinstance(st, ast.ClassDef):
                self._collect_scope(st.body, st.name, True)
                continue
            if isinstance(st, FUNC_TYPES):
                info = FuncInfo(st, cls if in_class_body else None)
                self.funcs.setdefault(info.qual, info)
                a = st.args
                for arg in getattr(a, "posonlyargs", []) + a.args + a.kwonlyargs:
                    ann = arg.annotation
                    if isinstance(ann, ast.Subscript):  # asyncio.Queue[str]
                        ann = ann.value
                    if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
                        try:
                            ann = ast.parse(ann.value, mode="eval").body
                        except SyntaxError:
                            ann = None
                    kind = self.classify(ann) if isinstance(ann, (ast.Name, ast.Attribute)) else None
                    if kind and arg.arg not in self.kinds:
                        self.kinds[arg.arg] = kind
                self._collect_scope(st.body, cls, False)
                continue
            for node in walk_local([st]):
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        self._record_assign(t, node.value, cls, in_class_body and node is st)
                elif isinstance(node, ast.AnnAssign) and node.value is not None:
                    self._record_assign(node.target, node.value, cls, in_class_body and node is st)
                elif isinstance(node, (ast.With, ast.AsyncWith)):
                    for item in node.items:
                        if item.optional_vars is not None:
                            self._record_assign(item.optional_vars, item.context_expr, cls, False)
            for block in sub_blocks(st):
                nested = [s for s in block if isinstance(s, (ast.ClassDef,) + FUNC_TYPES)]
                if nested:
                    self._collect_scope(nested, cls, False)

    # ------------------------------------------------------------ pass 2: lock graph
    def callee(self, call, cls):
        f = call.func
        if isinstance(f, ast.Name) and ("", f.id) in self.funcs:
            return ("", f.id)
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in ("self", "cls") \
                and cls and (cls, f.attr) in self.funcs:
            return (cls, f.attr)
        return None

    def scan_block(self, stmts, held, info):
        held = list(held)
        cls = info.cls
        for st in stmts:
            if isinstance(st, SCOPE_TYPES):
                continue
            for expr in header_exprs(st):
                for n in walk_no_spawn(expr):
                    if not isinstance(n, ast.Call):
                        continue
                    if isinstance(n.func, ast.Attribute) and n.func.attr == "acquire":
                        k = self.is_lockish(n.func.value, cls)
                        if k:
                            info.acq.append((k, n.lineno, tuple(held)))
                            held.append((k, n.lineno))
                        continue
                    target = self.callee(n, cls)
                    if target:
                        info.calls.append((target, n.lineno, tuple(held)))
            if isinstance(st, (ast.With, ast.AsyncWith)):
                inner = list(held)
                for item in st.items:
                    k = self.is_lockish(item.context_expr, cls)
                    if k:
                        info.acq.append((k, item.context_expr.lineno, tuple(inner)))
                        inner.append((k, item.context_expr.lineno))
                self.scan_block(st.body, inner, info)
            else:
                for block in sub_blocks(st):
                    self.scan_block(block, held, info)
            released = {self.is_lockish(n.func.value, cls) for n in walk_local([st])
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                        and n.func.attr == "release"}
            if released:
                held = [h for h in held if h[0] not in released]

    def lock_graph(self):
        for info in self.funcs.values():
            self.scan_block(info.node.body, [], info)
        owned = {}
        for q, info in self.funcs.items():
            first = {}
            for k, line, _ in info.acq:
                first.setdefault(k, line)
            owned[q] = first
        edges = {}

        def edge(a, b, text, node_line):
            edges.setdefault((a, b), (text, node_line))

        for q, info in self.funcs.items():
            for k, line, held in info.acq:
                for hk, hl in held:
                    if hk == k:
                        if not self.reentrant(k):
                            self.add("DLK002", _Pos(line), f"`{k}` is acquired again on line {line} in "
                                     f"{info.display}() while already held since line {hl}; a non-reentrant "
                                     "lock waits for itself forever")
                    else:
                        edge(hk, k, f"{info.display}() takes {hk} (line {hl}) then {k} (line {line})", line)
            for target, line, held in info.calls:
                if not held:
                    continue
                cinfo = self.funcs[target]
                for k, kl in owned.get(target, {}).items():
                    for hk, hl in held:
                        if hk == k:
                            if not self.reentrant(k):
                                self.add("DLK002", _Pos(line), f"{info.display}() holds `{k}` (line {hl}) and "
                                         f"calls {cinfo.display}(), which acquires `{k}` again (line {kl}); "
                                         "the lock is not reentrant, so this deadlocks")
                        else:
                            edge(hk, k, f"{info.display}() holds {hk} (line {hl}) and calls "
                                 f"{cinfo.display}() on line {line}, which takes {k} (line {kl})", line)
        self.report_cycles(edges)

    def report_cycles(self, edges):
        adj = {}
        for a, b in edges:
            adj.setdefault(a, set()).add(b)
        seen = set()
        nodes = sorted(adj)
        for start in nodes:
            stack = [(start, [start])]
            while stack:
                node, path = stack.pop()
                for nxt in sorted(adj.get(node, ())):
                    if nxt == start and len(path) >= 2:
                        cyc = path[:]
                        canon = tuple(sorted(cyc))
                        if canon in seen:
                            continue
                        seen.add(canon)
                        pairs = list(zip(cyc, cyc[1:] + [cyc[0]]))
                        evid = [edges[p] for p in pairs]
                        line = max(e[1] for e in evid)
                        chain = " -> ".join(cyc + [cyc[0]])
                        self.add("DLK001", _Pos(line), f"lock-order cycle {chain}: "
                                 + "; ".join(e[0] for e in evid))
                    elif nxt not in path and nxt > start and len(path) < 5:
                        stack.append((nxt, path + [nxt]))

    # ------------------------------------------------------------ pass 3: per-node rules
    def check(self):
        self.collect()
        self.lock_graph()
        Checker(self).visit(self.tree)
        self.check_threads()
        self.check_executor_self_wait()
        self.check_fork()
        self.check_signal_handlers()
        self.check_futures()
        for info in self.funcs.values():
            self.check_acquire_finally(info.node.body, info, set())
            self.check_process_drain(info)
            self.check_bounded_put(info)
        return self.findings

    def check_acquire_finally(self, stmts, info, guarded):
        cls = info.cls
        if info.name in ("__enter__", "__aenter__", "acquire", "__exit__", "__aexit__", "release"):
            return
        released_here = {self.norm(n.func.value, cls) for n in walk_local(info.node.body)
                         if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                         and n.func.attr == "release"}
        for i, st in enumerate(stmts):
            if isinstance(st, SCOPE_TYPES):
                continue
            for expr in header_exprs(st):
                for n in walk_local([expr]):
                    if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                            and n.func.attr == "acquire"):
                        continue
                    recv = n.func.value
                    key = self.norm(recv, cls)
                    k = self.lookup(key)
                    lockish = (k and (k[1] in LOCK_PRIMS or k[1] in SEM_PRIMS)) or (
                        not k and key and (LOCK_NAME.search(last(key).lower())
                                           or SEM_NAME.search(last(key).lower())))
                    if not lockish or key in guarded or key not in released_here:
                        continue  # released elsewhere: ownership handed off (e.g. paired acquire/release methods)
                    later = stmts[i + 1:]
                    if isinstance(st, ast.If):
                        later = st.body + st.orelse + later
                    if any(self._finally_releases(s, key, cls) for s in later):
                        continue
                    if later and self._is_release(later[0], key, cls):
                        continue  # released immediately: nothing in between can raise
                    self.add("DLK009", n, f"`{dotted(recv)}.acquire()` in {info.display}() has no "
                             f"`{dotted(recv)}.release()` in a finally block: any exception leaks the "
                             "lock/permit and later callers wait forever")
            if type(st).__name__ in ("Try", "TryStar"):
                rel = {self.norm(n.func.value, cls) for n in walk_local(st.finalbody)
                       if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                       and n.func.attr == "release"}
                self.check_acquire_finally(st.body, info, guarded | rel)
                for h in st.handlers:
                    self.check_acquire_finally(h.body, info, guarded)
                self.check_acquire_finally(st.orelse, info, guarded | rel)
                self.check_acquire_finally(st.finalbody, info, guarded)
            else:
                for block in sub_blocks(st):
                    self.check_acquire_finally(block, info, guarded)

    def _is_release(self, st, key, cls):
        return isinstance(st, ast.Expr) and isinstance(st.value, ast.Call) \
            and isinstance(st.value.func, ast.Attribute) and st.value.func.attr == "release" \
            and self.norm(st.value.func.value, cls) == key

    def _finally_releases(self, st, key, cls):
        if type(st).__name__ not in ("Try", "TryStar"):
            return False
        blocks = list(st.finalbody)
        for h in st.handlers:  # `except BaseException: lock.release(); raise` also covers every error path
            if h.type is None or last(dotted(h.type)) == "BaseException":
                blocks.extend(h.body)
        return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "release"
                   and self.norm(n.func.value, cls) == key for n in walk_local(blocks))

    def check_threads(self):
        thread_join_any = False
        for n in ast.walk(self.tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "join":
                if not n.args or kw(n, "timeout") is not None or (
                        len(n.args) == 1 and isinstance(n.args[0], ast.Constant)
                        and isinstance(n.args[0].value, (int, float))):
                    if not isinstance(n.func.value, ast.Constant):
                        thread_join_any = True
        for info_cls, call in self._calls_with_class():
            kind = self.classify(call.func)
            if not kind or kind[1] != "Thread":
                continue
            self.threads_started = True
            if is_true(kw(call, "daemon")):
                continue
            parent = self.parents.get(call)
            if isinstance(parent, ast.Attribute) and parent.attr == "start":
                self.add("DLK013", call, "non-daemon Thread is started without keeping a handle, so it can "
                         "never be joined; interpreter exit waits for it forever if it blocks")
                continue
            if isinstance(parent, (ast.Assign, ast.AnnAssign)):
                target = parent.targets[0] if isinstance(parent, ast.Assign) else parent.target
                key = self.norm(target, info_cls)
                if not key:
                    continue
                if self._daemon_set(key, info_cls) or self._joined(key, info_cls):
                    continue
                if not self._started(key, info_cls):
                    continue
                esc = self._escapes(key, info_cls)
                if esc == "handed-off" or (esc and thread_join_any):
                    continue
                self.add("DLK013", call, f"non-daemon Thread `{key}` is started but never joined; a worker "
                         "blocked on a queue or lock makes interpreter shutdown hang")
            elif not thread_join_any:
                self.add("DLK013", call, "non-daemon Threads are created here but nothing in the module "
                         "joins a thread; shutdown waits for them forever if one blocks")

    def _calls_with_class(self):
        def rec(node, cls):
            for child in ast.iter_child_nodes(node):
                c = child.name if isinstance(child, ast.ClassDef) else cls
                if isinstance(child, ast.Call):
                    yield cls, child
                yield from rec(child, c)
        yield from rec(self.tree, None)

    def _method_calls(self, key, attr, cls_hint):
        for c, n in self._calls_with_class():
            if isinstance(n.func, ast.Attribute) and n.func.attr == attr and self.norm(n.func.value, c) == key:
                yield n

    def _daemon_set(self, key, cls):
        for n in ast.walk(self.tree):
            if isinstance(n, ast.Assign) and is_true(n.value):
                for t in n.targets:
                    if isinstance(t, ast.Attribute) and t.attr == "daemon" and \
                            (self.norm(t.value, cls) == key or dotted(t.value) == key):
                        return True
        return any(n.args and is_true(n.args[0]) for n in self._method_calls(key, "setDaemon", cls))

    def _joined(self, key, cls):
        return any(True for _ in self._method_calls(key, "join", cls))

    def _started(self, key, cls):
        return any(True for _ in self._method_calls(key, "start", cls))

    def _escapes(self, key, cls):
        name = last(key)
        for n in ast.walk(self.tree):
            if isinstance(n, (ast.Name, ast.Attribute)) and isinstance(getattr(n, "ctx", None), ast.Load) \
                    and (dotted(n) == key or (isinstance(n, ast.Name) and n.id == name)):
                parent = self.parents.get(n)
                if isinstance(parent, ast.Attribute):
                    continue
                if isinstance(parent, (ast.Return, ast.Yield, ast.YieldFrom)):
                    return "handed-off"  # the caller owns the thread now
                return "escaped"
        return ""

    def check_executor_self_wait(self):
        submitted = {}
        for c, n in self._calls_with_class():
            if not isinstance(n.func, ast.Attribute):
                continue
            if n.func.attr in ("submit", "map") and n.args:
                pool, fn = n.func.value, n.args[0]
            elif n.func.attr == "run_in_executor" and len(n.args) >= 2:
                pool, fn = n.args[0], n.args[1]
            else:
                continue
            pkey = self.norm(pool, c)
            k = self.kinds.get(pkey)
            if not k or k[1] != "ThreadPoolExecutor":
                continue
            target = None
            if isinstance(fn, ast.Name) and ("", fn.id) in self.funcs:
                target = ("", fn.id)
            elif isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id == "self" \
                    and c and (c, fn.attr) in self.funcs:
                target = (c, fn.attr)
            if target:
                submitted.setdefault(target, set()).add(pkey)
        for target, pools in submitted.items():
            info = self.funcs[target]
            nodes = list(walk_local(info.node.body))
            waits = any(isinstance(n, ast.Call) and (
                (isinstance(n.func, ast.Attribute) and n.func.attr == "result")
                or last(self.resolve(dotted(n.func))) in ("wait", "as_completed")
                or (isinstance(n.func, ast.Name) and n.func.id in ("list", "tuple", "sorted")
                    and n.args and isinstance(n.args[0], ast.Call)
                    and isinstance(n.args[0].func, ast.Attribute) and n.args[0].func.attr == "map"))
                for n in nodes) or any(isinstance(n, (ast.For, ast.comprehension)) and isinstance(n.iter, ast.Call)
                                       and isinstance(n.iter.func, ast.Attribute) and n.iter.func.attr == "map"
                                       for n in nodes)
            if not waits:
                continue
            for n in nodes:
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                        and n.func.attr in ("submit", "map") and self.norm(n.func.value, info.cls) in pools:
                    self.add("DLK012", n, f"{info.display}() runs inside executor `{dotted(n.func.value)}` and "
                             "submits more work to the same executor, then waits for it: when every worker "
                             "is busy in an outer call, the inner tasks can never start")
                    break

    def check_fork(self):
        forks = []
        for n in ast.walk(self.tree):
            if not isinstance(n, ast.Call):
                continue
            name = self.resolve(dotted(n.func))
            if name in ("os.fork", "os.forkpty"):
                forks.append(n)
            elif last(name) in ("set_start_method", "get_context") and n.args \
                    and isinstance(n.args[0], ast.Constant) and n.args[0].value == "fork":
                forks.append(n)
        if not forks:
            return
        threaded = False
        for n in ast.walk(self.tree):
            if isinstance(n, ast.Call):
                k = self.classify(n.func)
                if k and k[1] in ("Thread", "Timer", "ThreadPoolExecutor"):
                    threaded = True
                if last(self.resolve(dotted(n.func))) in ("to_thread", "run_in_executor"):
                    threaded = True
        if threaded:
            for n in forks:
                self.add("DLK017", n, "fork in a process that also runs threads: a lock held by another "
                         "thread at fork time (logging handler, allocator, CUDA, gRPC, a queue) stays locked "
                         "forever in the child")

    def check_signal_handlers(self):
        for c, n in self._calls_with_class():
            if self.resolve(dotted(n.func)) != "signal.signal" or len(n.args) < 2:
                continue
            h = n.args[1]
            target = None
            if isinstance(h, ast.Name) and ("", h.id) in self.funcs:
                target = ("", h.id)
            elif isinstance(h, ast.Attribute) and isinstance(h.value, ast.Name) and h.value.id == "self" \
                    and c and (c, h.attr) in self.funcs:
                target = (c, h.attr)
            if not target:
                continue
            info = self.funcs[target]
            for m in walk_local(info.node.body):
                bad = None
                if isinstance(m, ast.With):
                    for item in m.items:
                        if self.is_lockish(item.context_expr, info.cls):
                            bad = f"takes `{dotted(item.context_expr)}`"
                elif isinstance(m, ast.Call) and isinstance(m.func, ast.Attribute):
                    recv = dotted(m.func.value)
                    if m.func.attr == "acquire" and self.is_lockish(m.func.value, info.cls):
                        bad = f"acquires `{recv}`"
                    elif m.func.attr in LOG_METHODS and ("log" in recv.lower()):
                        bad = f"calls `{recv}.{m.func.attr}()` (logging handlers hold locks)"
                if bad:
                    self.add("DLK018", m, f"signal handler {info.display}() {bad}; it runs in the main thread "
                             "between bytecodes, possibly while that thread already holds the same lock")
                    break

    def check_futures(self):
        futs = {k for k, v in self.kinds.items() if v[1] == "Future"}
        if not futs:
            return
        for c, n in self._awaits_with_class():
            key = self.norm(n.value, c)
            if key not in futs or last(key) in self.resolvers:
                continue
            if self._future_escapes(key):
                continue
            self.add("DLK016", n, f"`await {dotted(n.value)}` waits on a Future that nothing in this module "
                     "resolves (no set_result/set_exception/cancel, never handed to another object)")

    def _awaits_with_class(self):
        def rec(node, cls):
            for child in ast.iter_child_nodes(node):
                c = child.name if isinstance(child, ast.ClassDef) else cls
                if isinstance(child, ast.Await):
                    yield cls, child
                yield from rec(child, c)
        yield from rec(self.tree, None)

    def _future_escapes(self, key):
        name = last(key)
        for c, node in self._loads_with_class():
            if self.norm(node, c) != key and not (isinstance(node, ast.Name) and node.id == name):
                continue
            parent = self.parents.get(node)
            if isinstance(parent, (ast.Attribute, ast.Await)):
                continue
            return True
        return False

    def _loads_with_class(self):
        def rec(node, cls):
            for child in ast.iter_child_nodes(node):
                c = child.name if isinstance(child, ast.ClassDef) else cls
                if isinstance(child, (ast.Name, ast.Attribute)) and isinstance(child.ctx, ast.Load):
                    yield cls, child
                yield from rec(child, c)
        yield from rec(self.tree, None)

    def check_process_drain(self, info):
        cls = info.cls
        nodes = sorted((n for n in walk_local(info.node.body) if isinstance(n, ast.Call)),
                       key=lambda n: (n.lineno, n.col_offset))
        mp_queues = {k for k, v in self.kinds.items() if v[0] == "multiprocessing" and v[1] in QUEUE_PRIMS}
        if not mp_queues:
            return
        has_proc = any((self.classify(n.func) or ("", ""))[1] == "Process"
                       or (isinstance(n.func, ast.Attribute) and n.func.attr == "Process") for n in nodes)
        if not has_proc:
            return
        first_join = first_get = None
        for n in nodes:
            if not isinstance(n.func, ast.Attribute):
                continue
            key = self.norm(n.func.value, cls)
            if n.func.attr == "join" and key not in mp_queues and not isinstance(n.func.value, ast.Constant) \
                    and len(n.args) <= 1 and first_join is None:
                first_join = n
            if n.func.attr in ("get", "get_nowait") and key in mp_queues and first_get is None:
                first_get = n
        if first_join is not None and first_get is not None and \
                (first_join.lineno, first_join.col_offset) < (first_get.lineno, first_get.col_offset):
            self.add("DLK014", first_join, f"`{dotted(first_join.func.value)}.join()` runs before "
                     f"`{dotted(first_get.func.value)}.get()` (line {first_get.lineno}) drains the queue: a child "
                     "with unflushed queue data cannot exit, so join() waits forever")

    def check_bounded_put(self, info):
        cls = info.cls
        bounded = {}
        for n in walk_local(info.node.body):
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) \
                    and isinstance(n.value, ast.Call):
                k = self.classify(n.value.func)
                if not k or k[1] not in JOINABLE_QUEUES:
                    continue
                size = kw(n.value, "maxsize") or (n.value.args[0] if n.value.args else None)
                if isinstance(size, ast.Constant) and isinstance(size.value, int) and size.value > 0:
                    bounded[n.targets[0].id] = n
        for name in bounded:
            puts, reads, escaped = [], False, False
            for n in ast.walk(info.node):
                if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load):
                    parent = self.parents.get(n)
                    if isinstance(parent, ast.Attribute):
                        if parent.attr in ("put", "put_nowait"):
                            puts.append(parent)
                        elif parent.attr.startswith("get"):
                            reads = True
                    else:
                        escaped = True
            if puts and not reads and not escaped:
                self.add("DLK015", puts[0], f"bounded queue `{name}` is filled here but nothing in "
                         f"{info.display}() reads it or hands it to a consumer: put() blocks forever once full")


class _Pos:
    def __init__(self, line):
        self.lineno = line
        self.col_offset = 0


class Checker(ast.NodeVisitor):
    """Rules that depend on the enclosing function (async or not) and loop nesting."""

    def __init__(self, mod):
        self.m = mod
        self.scopes = [(False, None, 0)]  # (is_async, cls, while depth)
        self.cls = None
        self.awaited = set()
        self.threadsafe_futs = []
        self.submit_futs = []

    @property
    def in_async(self):
        return self.scopes[-1][0]

    def visit_ClassDef(self, node):
        saved, self.cls = self.cls, node.name
        self.generic_visit(node)
        self.cls = saved

    def _func(self, node, is_async):
        self.scopes.append((is_async, self.cls, 0))
        saved = (self.threadsafe_futs, self.submit_futs)
        self.threadsafe_futs, self.submit_futs = set(), set()
        for n in walk_local(node.body):
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.value, ast.Call):
                fname = last(self.m.resolve(dotted(n.value.func)))
                key = self.m.norm(n.targets[0], self.cls)
                if fname == "run_coroutine_threadsafe":
                    self.threadsafe_futs.add(key)
                elif fname == "submit":
                    self.submit_futs.add(key)
            if isinstance(n, (ast.For, ast.comprehension)) and isinstance(n.iter, ast.Call) \
                    and self.m.resolve(dotted(n.iter.func)) in ("concurrent.futures.as_completed",):
                self.submit_futs.add(dotted(n.target))
        self.generic_visit(node)
        self.threadsafe_futs, self.submit_futs = saved
        self.scopes.pop()

    def visit_FunctionDef(self, node):
        self._func(node, False)

    def visit_AsyncFunctionDef(self, node):
        self._func(node, True)

    def visit_Lambda(self, node):
        self.scopes.append((False, self.cls, 0))
        self.generic_visit(node)
        self.scopes.pop()

    def visit_While(self, node):
        a, c, d = self.scopes[-1]
        self.visit(node.test)
        self.scopes[-1] = (a, c, d + 1)
        for s in node.body:
            self.visit(s)
        self.scopes[-1] = (a, c, d)
        for s in node.orelse:
            self.visit(s)

    def visit_Await(self, node):
        if isinstance(node.value, ast.Call):
            self.awaited.add(id(node.value))
        self.generic_visit(node)

    def visit_With(self, node):
        if self.in_async:
            for item in node.items:
                e = item.context_expr
                if isinstance(e, ast.Call):
                    continue
                k = self.m.kind(e, self.cls)
                if (k and k[0] in ("threading", "multiprocessing") and (k[1] in LOCK_PRIMS or k[1] in SEM_PRIMS)) \
                        or (not k and LOCK_NAME.search(last(dotted(e)).lower() or "-")):
                    held_await = any(isinstance(n, ast.Await) for n in walk_local(node.body))
                    extra = " and awaits while holding it (other tasks on this loop can never release it)" \
                        if held_await else ""
                    self.m.add("DLK003", e, f"`with {dotted(e)}:` takes a threading lock inside async def"
                               f"{extra}; a contended acquire blocks the whole event loop")
        self.generic_visit(node)

    def visit_Call(self, node):
        m, cls = self.m, self.cls
        f = node.func
        name = m.resolve(dotted(f))
        attr = f.attr if isinstance(f, ast.Attribute) else ""
        recv = f.value if isinstance(f, ast.Attribute) else None
        awaited = id(node) in self.awaited
        rk = m.kind(recv, cls) if recv is not None else None
        rkey = m.norm(recv, cls) if recv is not None else ""
        if self.in_async and not awaited:
            if name == "time.sleep":
                m.add("DLK004", node, "time.sleep() inside async def blocks the event loop; every other task "
                      "(streams, heartbeats, timeouts) stops")
            elif name in ("asyncio.run",) or attr in ("run_until_complete", "run_forever"):
                m.add("DLK007", node, f"`{dotted(f)}()` inside async def: a loop is already running in this "
                      "thread (RuntimeError, or a deadlock under nest_asyncio)")
            elif attr == "result":
                src = recv.func if isinstance(recv, ast.Call) else None
                src_name = last(m.resolve(dotted(src))) if src is not None else ""
                if src_name == "run_coroutine_threadsafe" or rkey in self.threadsafe_futs:
                    m.add("DLK006", node, "run_coroutine_threadsafe(...).result() inside async def: when the "
                          "target loop is this loop, it waits for work that can only run after it returns")
                elif src_name == "submit" or (rkey and rkey in self.submit_futs):
                    m.add("DLK005", node, f"`{ast.unparse(node)}` blocks the event loop until the executor "
                          "finishes; await asyncio.wrap_future(...) instead")
            elif attr == "join" and (not node.args or kw(node, "timeout") is not None) \
                    and not (rk and rk[0] == "asyncio") and not isinstance(recv, ast.Constant):
                m.add("DLK005", node, f"`{dotted(f)}()` inside async def blocks the event loop until the "
                      "thread/process/queue finishes; if it needs this loop, it never will")
            elif attr in ("get", "put") and m.sync_queue(recv, cls) and not is_false(kw(node, "block")) \
                    and not (node.args[1:2] and is_false(node.args[1])) \
                    and not (attr == "get" and node.args and is_false(node.args[0])):
                m.add("DLK005", node, f"`{dotted(f)}()` on a thread/process queue inside async def blocks "
                      "the event loop; use asyncio.Queue or await asyncio.to_thread(...)")
            elif attr == "wait" and rk and rk[0] in ("threading", "multiprocessing") \
                    and rk[1] in ("Event", "Condition", "Barrier"):
                m.add("DLK005", node, f"`{dotted(f)}()` on a threading {rk[1]} inside async def blocks the "
                      "event loop; use asyncio.Event or await asyncio.to_thread(...)")
            elif name in ("concurrent.futures.wait",):
                m.add("DLK005", node, "concurrent.futures.wait() inside async def blocks the event loop; use "
                      "await asyncio.wait([asyncio.wrap_future(f) for f in futs])")
            elif attr == "acquire" and rk and rk[0] in ("threading", "multiprocessing"):
                m.add("DLK003", node, f"`{dotted(f)}()` acquires a threading lock inside async def; a "
                      "contended acquire blocks the whole event loop")
        if attr == "join" and m.has_task_done is False and (
                (rk and rk[1] in JOINABLE_QUEUES) or (not rk and recv is not None and not node.args
                                                       and QUEUE_NAME.search(last(dotted(recv)).lower() or "-"))):
            m.add("DLK008", node, f"`{dotted(f)}()` waits for every item to be marked done, but nothing in this "
                  "module calls task_done(): it never returns")
        if attr == "wait" and recv is not None and self.scopes[-1][2] == 0 and not node.args \
                and kw(node, "timeout") is None:
            is_cond = (rk and rk[1] == "Condition") or (not rk and COND_NAME.search(last(dotted(recv)).lower() or "-"))
            if is_cond:
                m.add("DLK010", node, f"`{dotted(f)}()` is not inside a `while not predicate:` loop: a "
                      "spurious, stolen or early notify leaves the waiter acting on stale state or "
                      "waiting forever; use wait_for(predicate)")
        if not self.in_async and not awaited and rk and rk[0] in ("threading", "multiprocessing"):
            no_timeout = kw(node, "timeout") is None
            if attr == "get" and rk[1] in QUEUE_PRIMS and no_timeout and not node.args[:1] \
                    and not is_false(kw(node, "block")):
                m.add("DLK011", node, f"`{dotted(f)}()` blocks forever if the producer dies; pass "
                      "timeout= and re-check a stop flag (or use Queue.shutdown() on 3.13+)")
            elif attr == "wait" and rk[1] in ("Event", "Condition", "Barrier") and no_timeout and not node.args \
                    and not (rk[1] == "Condition" and self.scopes[-1][2] == 0):
                m.add("DLK011", node, f"`{dotted(f)}()` without a timeout blocks forever if nobody ever "
                      "sets/notifies it")
            elif attr == "join" and rk[1] in JOINABLE_QUEUES and m.has_task_done:
                m.add("DLK011", node, f"`{dotted(f)}()` has no timeout parameter; if a worker dies before "
                      "task_done() it waits forever. Join the workers with a timeout instead, or poll "
                      "unfinished_tasks with a deadline")
        self.generic_visit(node)


# ---------------------------------------------------------------- driver

def scan_source(source, path):
    tree = ast.parse(source, filename=path)
    return Module(path, source, tree).check()


def expand(paths):
    skip = {".git", ".venv", "venv", "__pycache__", "node_modules", ".tox", ".mypy_cache", "build", "dist"}
    for p in paths:
        if p != "-" and os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d not in skip)
                for f in sorted(files):
                    if f.endswith(".py"):
                        yield os.path.join(root, f), True
        else:
            yield p, False


def parse_rule_list(values):
    out = set()
    for v in values or []:
        for tok in v.split(","):
            tok = tok.strip()
            if not tok:
                continue
            matched = [rid for rid, meta in RULES.items() if rid.startswith(tok.upper()) or meta[0] == tok]
            if not matched:
                raise ValueError(f"unknown rule {tok!r}; run --list-rules")
            out.update(matched)
    return out


def list_rules():
    for rid, (slug, sev, title, why, fix) in RULES.items():
        print(f"{rid} {slug} [{sev}]\n    {title}\n    why: " + why.replace("\n", "\n         "))
        print("    fix: " + fix.replace("\n", "\n         ") + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="Python files or directories, or - for stdin")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any finding is reported")
    ap.add_argument("--select", action="append", help="only these rules (ids, id prefixes or names; comma list)")
    ap.add_argument("--ignore", action="append", help="skip these rules (ids, id prefixes or names; comma list)")
    ap.add_argument("--list-rules", action="store_true", help="print every rule with why/fix and exit")
    args = ap.parse_args(argv)

    if args.list_rules:
        list_rules()
        return 0
    if not args.paths:
        ap.error("at least one path (or -) is required")
    try:
        select = parse_rule_list(args.select) or set(RULES)
        ignore = parse_rule_list(args.ignore)
    except ValueError as err:
        ap.error(str(err))

    findings, errors, warnings, files = [], [], [], 0
    for path, walked in expand(args.paths):
        label = "<stdin>" if path == "-" else path
        try:
            if path == "-":
                source = sys.stdin.read()
            else:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
            findings.extend(scan_source(source, label))
            files += 1
        except SyntaxError as err:
            msg = f"{label}:{err.lineno}: cannot parse: {err.msg}"
            (warnings if walked else errors).append(msg)
        except (OSError, UnicodeDecodeError, ValueError) as err:
            msg = f"{label}: cannot read: {err}"
            (warnings if walked else errors).append(msg)

    findings = [f for f in findings if f["rule"] in select and f["rule"] not in ignore]
    findings.sort(key=lambda f: (f["path"], f["line"], f["col"], f["rule"]))
    counts = {s: sum(f["severity"] == s for f in findings) for s in SEVERITY_ORDER}

    if args.json:
        print(json.dumps({"files": files, "summary": counts, "errors": errors, "warnings": warnings,
                          "findings": findings}, indent=2))
    else:
        for w in warnings:
            print(f"warning: {w} (skipped)", file=sys.stderr)
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        if not findings:
            if files:
                print(f"No hang risks found in {files} file(s).")
        else:
            print(f"{len(findings)} finding(s) in {files} file(s): {counts['high']} high, "
                  f"{counts['medium']} medium, {counts['low']} low\n")
            for f in findings:
                print(f"{f['path']}:{f['line']}:{f['col']}: {f['rule']} [{f['severity']}] {f['name']}: "
                      f"{f['message']}")
                if f["code"]:
                    print(f"    > {f['code']}")
                print("    fix: " + f["fix"].replace("\n", "\n         "))
                print()
    if errors:
        return 2
    return 1 if args.strict and findings else 0


if __name__ == "__main__":
    sys.exit(main())
