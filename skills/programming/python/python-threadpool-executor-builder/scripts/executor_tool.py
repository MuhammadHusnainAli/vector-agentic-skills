#!/usr/bin/env python3
"""Check and scaffold thread-pool (ThreadPoolExecutor / threading) code for I/O-bound work.

Subcommands
-----------
check FILES...       Static AST linter for concurrent.futures / threading code. The
                     analysed code is parsed with `ast`, never imported or executed.
scaffold --recipe R  Print a complete, typed, documented, runnable module for a
                     common thread-pool pattern. The generated code is verified with
                     ast.parse (exit 2 if it does not parse). Nothing is executed.

Rules for `check` (run `check --list-rules` for the why and a fix snippet of each):

  TPE001 future-never-read           submit() future dropped / never read: worker exceptions vanish
  TPE002 executor-not-shutdown       executor created without `with` and never shut down
  TPE003 unbounded-submit            submit() in a loop over a huge/unbounded iterable with no bound
  TPE004 map-over-generator          executor.map over a generator/file: submits everything up front
  TPE005 map-results-unconsumed      executor.map result never iterated (exceptions lost; timeout no-op)
  TPE006 shared-read-modify-write    worker does `+=` / check-then-set on shared state without a lock
  TPE007 shared-container-mutation   worker appends/sets items on a shared list/dict without a lock
  TPE008 shared-unsafe-client        requests.Session / sqlite3 connection created once, used by workers
  TPE009 executor-self-wait          task waits on a future of its own executor (pool self-deadlock)
  TPE010 pool-size-smell             max_workers constant > 64, 1 (serial pool) or <= 0
  TPE011 result-without-timeout      future.result() with no timeout in a loop inside a request handler
  TPE012 shutdown-nowait-at-exit     shutdown(wait=False) without cancel_futures on an exit path
  TPE013 daemon-thread-side-effects  daemon thread doing writes/uploads that die mid-way at exit
  TPE014 polling-future-done         time.sleep() loop polling future.done() instead of wait()
  TPE015 swallowed-future-exception  `except Exception` around result() that drops the error
  TPE016 executor-per-call           executor created per call in a loop, task or request handler
  TPE017 thread-not-joined           Thread started without join() and without daemon
  TPE018 cpu-bound-thread-pool       pure-Python arithmetic loops sent to a thread pool (GIL-bound)
  TPE019 contextvar-not-propagated   worker reads a ContextVar but was submitted without copy_context()

Suppress a finding on its line with `# noqa` or `# noqa: TPE001,TPE010`.

Usage:
    python executor_tool.py check src/ --strict
    python executor_tool.py check worker.py --json --select TPE001,TPE005 --ignore pool-size-smell
    cat job.py | python executor_tool.py check -
    python executor_tool.py check --list-rules
    python executor_tool.py scaffold --list
    python executor_tool.py scaffold --recipe llm-eval-harness > eval_harness.py
    python executor_tool.py scaffold --recipe bounded-map --json

Exit codes: 0 ok (or findings without --strict), 1 findings with --strict,
2 usage error, unknown recipe, generated code that fails ast.parse, or a file
named on the command line that cannot be read or parsed (directory walks warn
and skip such files).

No dependencies (standard library only, Python 3.9+).
"""

import argparse
import ast
import json
import os
import re
import sys

# ====================================================================== rules

RULES = {
    "TPE001": {
        "name": "future-never-read", "severity": "high",
        "summary": "Future from submit() is dropped or never read (add_done_callback alone does not count "
                   "unless the callback calls result()/exception())",
        "why": "An exception raised in the worker is stored on the Future and only re-raised by result(). A "
               "future nobody reads turns every failed LLM call, upload or upsert into silent data loss; the job "
               "still exits 0. Reassigning one `fut` variable in a loop keeps only the last future.",
        "fix": "futures = {ex.submit(embed_batch, b): i for i, b in enumerate(batches)}\n"
               "for fut in as_completed(futures):\n"
               "    try:\n"
               "        vectors[futures[fut]] = fut.result()\n"
               "    except Exception as exc:\n"
               "        errors.append((futures[fut], exc))      # keep it, log it, or re-raise",
    },
    "TPE002": {
        "name": "executor-not-shutdown", "severity": "medium",
        "summary": "Executor created without `with` and never shut down",
        "why": "Without shutdown() the worker threads live until interpreter exit, where an atexit hook joins "
               "them: queued work keeps the process alive, per-call executors leak threads in services, and "
               "there is no point where errors are collected. An executor chained as "
               "`ThreadPoolExecutor().submit(...)` can never be shut down.",
        "fix": "with ThreadPoolExecutor(max_workers=16, thread_name_prefix=\"embed\") as ex:\n"
               "    results = list(ex.map(embed_batch, batches))\n"
               "# long-lived (app-wide) executor: create once, shut down in the lifespan/atexit hook\n"
               "# atexit.register(EXECUTOR.shutdown, wait=True, cancel_futures=True)",
    },
    "TPE003": {
        "name": "unbounded-submit", "severity": "medium",
        "summary": "submit() in a loop over a file, generator, directory walk or huge range with no "
                   "semaphore or sliding window",
        "why": "submit() never blocks: the work queue is unbounded. Looping over 10 million JSONL lines submits "
               "10 million futures (plus their arguments and results) before the first one finishes: memory "
               "grows without limit, Ctrl-C has millions of queued items to drain, and progress is meaningless.",
        "fix": "inflight = set()\n"
               "for line in open(\"prompts.jsonl\"):\n"
               "    if len(inflight) >= 64:                       # sliding window\n"
               "        done, inflight = wait(inflight, return_when=FIRST_COMPLETED)\n"
               "        handle(done)\n"
               "    inflight.add(ex.submit(score, line))\n"
               "handle(wait(inflight).done)\n"
               "# or: executor_tool.py scaffold --recipe bounded-map",
    },
    "TPE004": {
        "name": "map-over-generator", "severity": "medium",
        "summary": "executor.map() over a generator, file object or huge range (eager submission before 3.14)",
        "why": "Executor.map() calls submit() for every element before returning the iterator: a generator over "
               "a 50 GB corpus is fully drained into the queue up front, so laziness and memory bounds are lost. "
               "Python 3.14 added map(..., buffersize=N) to bound it; before 3.14 use a sliding window.",
        "fix": "# 3.14+\n"
               "for res in ex.map(parse_doc, iter_docs(path), buffersize=64):\n"
               "    sink.write(res)\n"
               "# 3.9-3.13: executor_tool.py scaffold --recipe bounded-map (sliding window of futures)",
    },
    "TPE005": {
        "name": "map-results-unconsumed", "severity": "high",
        "summary": "executor.map() result never iterated, or its timeout made meaningless",
        "why": "Executor.map() re-raises a worker exception only when that result is reached during iteration. "
               "Discarding the iterator discards every exception. Its timeout= is a deadline for the whole "
               "iteration measured from the map() call, enforced only while you iterate: if you iterate after "
               "the `with` block (which already waited for all tasks), the timeout does nothing.",
        "fix": "with ThreadPoolExecutor(16) as ex:\n"
               "    for doc_id, ok in zip(ids, ex.map(upsert, batches, timeout=600)):   # iterate INSIDE\n"
               "        log.info(\"upserted %s\", doc_id)\n"
               "# fire-and-forget is never right for work that can fail: collect results",
    },
    "TPE006": {
        "name": "shared-read-modify-write", "severity": "high",
        "summary": "Worker does `+=`, `x[k] = x.get(k) + 1` or check-then-set on shared state without a lock",
        "why": "`counter += 1` and `d[k] = d.get(k, 0) + 1` are a read, a computation and a write: two threads "
               "can read the same old value and one update is lost. The GIL does not make these atomic, and "
               "free-threaded 3.13t/3.14t builds lose updates far more often. `if k not in cache: cache[k] = ...` "
               "computes the value twice.",
        "fix": "_stats_lock = threading.Lock()\n"
               "def record(tokens: int) -> None:\n"
               "    with _stats_lock:\n"
               "        STATS[\"tokens\"] += tokens\n"
               "# better: return the value from the task and aggregate in the caller",
    },
    "TPE007": {
        "name": "shared-container-mutation", "severity": "low",
        "summary": "Worker appends to / assigns items in a module-level list/dict/set without a lock",
        "why": "A single list.append or dict item assignment is atomic in CPython (and internally locked on "
               "free-threaded builds), but the order is nondeterministic, results are silently missing when a "
               "task fails, and the moment the code grows into a compound update it races. Returning values "
               "from tasks keeps ownership in one thread.",
        "fix": "def embed(chunk: str) -> list[float]:\n"
               "    return client.embed(chunk)                   # return, do not append to a global\n"
               "vectors = list(ex.map(embed, chunks))            # ordered, exceptions propagate\n"
               "# if you must share: with RESULTS_LOCK: RESULTS.append(v)",
    },
    "TPE008": {
        "name": "shared-unsafe-client", "severity": "high",
        "summary": "requests.Session or sqlite3 connection created once and used from worker threads",
        "why": "requests documents no thread-safety guarantee for Session (shared cookie jar, adapters and "
               "redirect state mutate per request). sqlite3 connections refuse cross-thread use by default "
               "(ProgrammingError: SQLite objects created in a thread can only be used in that same thread); "
               "with check_same_thread=False you must serialize every use yourself.",
        "fix": "_local = threading.local()\n"
               "def session() -> requests.Session:\n"
               "    if not hasattr(_local, \"s\"):\n"
               "        _local.s = requests.Session()            # one Session per worker thread\n"
               "    return _local.s\n"
               "# or httpx.Client (documented thread-safe), or one sqlite3.connect() per thread / a writer thread",
    },
    "TPE009": {
        "name": "executor-self-wait", "severity": "high",
        "summary": "Task submitted to an executor submits to the same executor and blocks on the result",
        "why": "Each outer task holds a worker while it waits for inner tasks that need a free worker. With N "
               "outer tasks >= max_workers every worker is waiting and nothing runs: a permanent hang that only "
               "appears under load. See python-async-deadlock-debugger (DLK012).",
        "fix": "outer_pool = ThreadPoolExecutor(8, thread_name_prefix=\"doc\")\n"
               "inner_pool = ThreadPoolExecutor(32, thread_name_prefix=\"chunk\")   # separate pool per level\n"
               "# or flatten: submit all leaf tasks (chunks) from the caller, then group results",
    },
    "TPE010": {
        "name": "pool-size-smell", "severity": "low",
        "summary": "ThreadPoolExecutor(max_workers=C) with a constant > 64, exactly 1, or <= 0",
        "why": "Hundreds of threads rarely beat the real ceiling (API rate limits, connection pool size, server "
               "capacity) and cost ~8 MB virtual stack each plus contention. max_workers=1 is a serial loop with "
               "extra overhead unless you deliberately serialize access to one resource. <= 0 raises ValueError.",
        "fix": "# size from Little's law and the rate limit: workers ~= target_rps * p95_latency_s\n"
               "workers = min(64, max(4, int(rpm / 60 * p95_latency_s * 1.2)))\n"
               "ex = ThreadPoolExecutor(max_workers=workers, thread_name_prefix=\"llm\")",
    },
    "TPE011": {
        "name": "result-without-timeout", "severity": "low",
        "summary": "future.result() with no timeout inside a loop in a request handler",
        "why": "One stuck upstream call (no socket timeout, a hung DNS lookup) pins the request handler forever, "
               "and the timed-out request still holds a worker. Handlers need a deadline.",
        "fix": "deadline = time.monotonic() + 10\n"
               "for fut in futures:\n"
               "    out.append(fut.result(timeout=max(0.0, deadline - time.monotonic())))",
    },
    "TPE012": {
        "name": "shutdown-nowait-at-exit", "severity": "medium",
        "summary": "shutdown(wait=False) without cancel_futures=True on an exit / Ctrl-C path",
        "why": "wait=False only returns early; every queued task still runs, and the interpreter's exit hook "
               "joins the worker threads, so the process keeps calling the API for minutes after Ctrl-C. "
               "cancel_futures=True (3.9+) drops the queued items; running tasks still need a stop event.",
        "fix": "except KeyboardInterrupt:\n"
               "    stop.set()                                   # cooperative stop for running tasks\n"
               "    ex.shutdown(wait=True, cancel_futures=True)  # drop queued work, wait for running\n"
               "    raise",
    },
    "TPE013": {
        "name": "daemon-thread-side-effects", "severity": "medium",
        "summary": "daemon=True thread whose target writes/uploads/commits and is never joined",
        "why": "Daemon threads are killed abruptly at interpreter exit: a half-written JSONL file, an S3 "
               "multipart upload that never completes, a batch of vectors never committed. No exception, no "
               "log line. Daemon is for heartbeats and watchdogs, not for work whose results matter.",
        "fix": "t = threading.Thread(target=flush_results, args=(q,), name=\"writer\")   # non-daemon\n"
               "t.start()\n"
               "...\n"
               "q.put(None)      # sentinel\n"
               "t.join()",
    },
    "TPE014": {
        "name": "polling-future-done", "severity": "medium",
        "summary": "Loop with time.sleep() polling future.done() instead of wait()/as_completed()",
        "why": "Polling adds up to one sleep interval of latency per result, burns CPU when the interval is short, "
               "and usually never reads result(), so exceptions are lost. wait() and as_completed() block on "
               "a condition variable and wake exactly when a future completes.",
        "fix": "for fut in as_completed(futures, timeout=600):\n"
               "    handle(fut.result())\n"
               "# or: done, pending = wait(futures, timeout=5, return_when=FIRST_COMPLETED)",
    },
    "TPE015": {
        "name": "swallowed-future-exception", "severity": "high",
        "summary": "`except Exception` (or bare except) around future.result() that drops the exception",
        "why": "This is where the worker's error finally surfaces; `pass`/`continue` here deletes the traceback "
               "of every failed task. The job looks healthy while a quarter of the prompts were never scored.",
        "fix": "try:\n"
               "    results[key] = fut.result()\n"
               "except Exception as exc:\n"
               "    log.warning(\"task %s failed\", key, exc_info=exc)\n"
               "    errors[key] = exc                            # report counts at the end",
    },
    "TPE016": {
        "name": "executor-per-call", "severity": "medium",
        "summary": "Executor created inside a loop, a task, a request handler or a function called in a loop",
        "why": "Each executor starts its own threads and tears them down; per-request executors multiply "
               "threads by concurrent requests (thread explosion, connection-pool exhaustion), and per-batch "
               "executors pay start-up and shutdown every iteration.",
        "fix": "EXECUTOR = ThreadPoolExecutor(max_workers=32, thread_name_prefix=\"io\")   # once, app-wide\n"
               "def embed_all(batches):\n"
               "    return list(EXECUTOR.map(embed_batch, batches))\n"
               "# shut it down in the app lifespan / atexit",
    },
    "TPE017": {
        "name": "thread-not-joined", "severity": "medium",
        "summary": "threading.Thread (or subclass) started without join() and without daemon",
        "why": "An exception in the thread is only printed by threading.excepthook; the caller never learns "
               "the work failed, cannot know when it finished, and the process silently waits for it at exit.",
        "fix": "threads = [threading.Thread(target=crawl, args=(shard,), name=f\"crawl-{i}\") for i, shard in "
               "enumerate(shards)]\n"
               "for t in threads: t.start()\n"
               "for t in threads: t.join()\n"
               "# better: ThreadPoolExecutor + futures, which carry results and exceptions",
    },
    "TPE018": {
        "name": "cpu-bound-thread-pool", "severity": "low",
        "summary": "Thread pool worker is only pure-Python arithmetic loops (GIL-bound on the default build)",
        "why": "On the default (GIL) build only one thread runs Python bytecode at a time: N threads doing pure "
               "arithmetic take as long as one, plus switching overhead. Use processes, vectorize, or a "
               "free-threaded build. See python-gil-bottleneck-analyzer.",
        "fix": "with ProcessPoolExecutor() as ex:              # or numpy / a C extension that releases the GIL\n"
               "    scores = list(ex.map(score_chunk, chunks, chunksize=64))",
    },
    "TPE019": {
        "name": "contextvar-not-propagated", "severity": "medium",
        "summary": "Worker reads a ContextVar but was submitted without contextvars.copy_context().run",
        "why": "Worker threads run tasks in their own context: request ids, trace spans and tenant ids set by "
               "the caller are not visible (ContextVar.get() returns the default or raises LookupError). "
               "asyncio.to_thread copies the context; executor.submit, executor.map, run_in_executor and "
               "Thread(target=...) do not.",
        "fix": "ctx = contextvars.copy_context()\n"
               "fut = ex.submit(ctx.run, call_llm, prompt)       # one copy per task\n"
               "# Thread: threading.Thread(target=copy_context().run, args=(work,)) or context= (3.14)",
    },
}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)
SCOPES = FUNCS + (ast.ClassDef, ast.Lambda)
COMPS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
EXECUTOR_CTORS = {"ThreadPoolExecutor": "thread", "ProcessPoolExecutor": "process",
                  "InterpreterPoolExecutor": "interp"}
STRONG_EXECUTOR = {"thread", "process", "interp", "executor"}
CONTAINER_CTORS = {"list", "dict", "set", "defaultdict", "Counter", "OrderedDict", "deque"}
MUTATORS = {"append", "extend", "insert", "pop", "remove", "clear", "update", "setdefault", "add", "discard",
            "appendleft", "extendleft", "popleft", "popitem", "sort", "reverse"}
SIDE_EFFECTS = {"write", "writelines", "put", "put_nowait", "commit", "upsert", "upload", "upload_file",
                "upload_fileobj", "put_object", "save", "insert", "insert_many", "insert_one", "send", "sendall",
                "flush", "dump", "executemany", "execute", "add_documents", "add_texts", "index", "bulk"}
CONSOLE = re.compile(r"^(self|cls)$|std(out|err)$|console|log(ger)?$", re.I)   # harmless output targets
LOCKISH = re.compile(r"lock|mutex|cond|sem|guard", re.I)
LOCK_CTORS = {"Lock", "RLock", "Condition", "Semaphore", "BoundedSemaphore"}
UNSAFE_CLIENTS = {"requests.Session": "requests.Session", "requests.session": "requests.Session",
                  "requests.sessions.Session": "requests.Session", "sqlite3.connect": "sqlite3 connection",
                  "sqlite3.dbapi2.connect": "sqlite3 connection"}
UNBOUNDED_FUNCS = {"open", "io.open", "gzip.open", "bz2.open", "lzma.open", "itertools.count", "itertools.cycle",
                   "itertools.repeat", "os.scandir", "os.walk", "glob.iglob", "csv.reader", "csv.DictReader",
                   "fileinput.input", "iter"}
UNBOUNDED_ATTRS = {"iterdir", "glob", "rglob", "iter_lines", "iter_content", "iterrows", "itertuples",
                   "scan_iter", "paginate", "stream", "readlines", "iter_batches"}
UNBOUNDED_PREFIXES = ("iter_", "stream_", "read_jsonl", "scan_", "paginate", "generate_", "gen_")
PURE_CALLS = {"range", "len", "abs", "min", "max", "sum", "pow", "int", "float", "divmod", "round",
              "enumerate", "zip", "bool", "reversed", "complex"}
ARITH = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.BitXor, ast.BitAnd,
         ast.BitOr, ast.LShift, ast.RShift)
HANDLER_DECORATORS = {"get", "post", "put", "patch", "delete", "route", "api_route", "websocket", "head",
                      "options", "api_view"}
LOG_ATTRS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log", "print_exc",
             "print_exception", "capture_exception", "record_exception", "showtraceback", "format_exc",
             "print_tb", "excepthook"}
EXIT_CALLS = {"sys.exit", "exit", "quit", "os._exit"}
MAIN_FUNC = re.compile(r"^_?(main|cli|.*exit.*|.*signal.*|.*interrupt.*|.*sigint.*)$")


# ====================================================================== helpers

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


def walk_local(stmts):
    """ast.walk over statements without descending into nested functions, classes or lambdas."""
    stack = list(stmts)
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, SCOPES):
            continue
        stack.extend(ast.iter_child_nodes(node))


def parent(node):
    return getattr(node, "_tpe_parent", None)


def kwarg(call, name):
    for k in call.keywords:
        if k.arg == name:
            return k.value
    return None


def is_const(node, value):
    return isinstance(node, ast.Constant) and node.value is value


def is_main_guard(node):
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    t = node.test
    if len(t.ops) != 1 or not isinstance(t.ops[0], ast.Eq):
        return False
    sides = [t.left, t.comparators[0]]
    return any(isinstance(s, ast.Name) and s.id == "__name__" for s in sides) and \
        any(isinstance(s, ast.Constant) and s.value == "__main__" for s in sides)


def enclosing_func(node):
    p = parent(node)
    while p is not None and not isinstance(p, FUNCS + (ast.Lambda, ast.Module)):
        p = parent(p)
    return p if isinstance(p, FUNCS) else None


def loop_of(node):
    """Nearest enclosing For/While/comprehension (not crossing a function), or None."""
    p, child = parent(node), node
    while p is not None and not isinstance(p, SCOPES + (ast.Module,)):
        if isinstance(p, (ast.For, ast.AsyncFor)) and child is not p.iter and child not in p.orelse:
            return p
        if isinstance(p, ast.While) and child is not p.test and child not in p.orelse:
            return p
        if isinstance(p, COMPS):
            return p
        p, child = parent(p), p
    return None


def inside(node, container):
    p = node
    while p is not None:
        if p is container:
            return True
        p = parent(p)
    return False


def names_loaded(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}


def is_thread_join(call):
    """`x.join()`, `x.join(5)`, `x.join(timeout=...)` -- not `", ".join(parts)`."""
    f = call.func
    if not (isinstance(f, ast.Attribute) and f.attr == "join") or isinstance(f.value, ast.Constant):
        return False
    if call.keywords:
        return all(k.arg == "timeout" for k in call.keywords) and not call.args
    if not call.args:
        return True
    return len(call.args) == 1 and isinstance(call.args[0], ast.Constant) and \
        isinstance(call.args[0].value, (int, float)) and not isinstance(call.args[0].value, bool)


def is_handler_func(func):
    if func is None:
        return False
    for d in func.decorator_list:
        target = d.func if isinstance(d, ast.Call) else d
        name = dotted(target)
        if name and name.rsplit(".", 1)[-1] in HANDLER_DECORATORS and "." in name:
            return True
    n = func.name.lower()
    return n.startswith("handle") or n.endswith("_handler") or n.endswith("_view") or n.endswith("_endpoint")


def logs_or_raises(stmts):
    for n in walk_local(stmts):
        if isinstance(n, ast.Raise):
            return True
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr in LOG_ATTRS:
                return True
            if isinstance(f, ast.Name) and f.id in ("print", "warn"):
                return True
            if dotted(f) in EXIT_CALLS:
                return True
    return False


class Scope:
    def __init__(self, func, stmts, cls=None):
        self.func = func                  # FunctionDef / AsyncFunctionDef, or None for the module
        self.cls = cls                    # enclosing ClassDef for methods
        self.stmts = stmts
        self.nodes = list(walk_local(stmts))
        self.assigned = {}                # name -> [value nodes]
        self.local_defs = {}              # nested def name -> node
        self.params = {}                  # name -> annotation string
        self.globals = set()
        if func is not None:
            a = func.args
            for arg in a.posonlyargs + a.args + a.kwonlyargs + [x for x in (a.vararg, a.kwarg) if x]:
                ann = ast.unparse(arg.annotation) if (arg.annotation is not None and
                                                     hasattr(ast, "unparse")) else ""
                self.params[arg.arg] = ann
        for n in self.nodes:
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, (ast.Name, ast.Attribute)) and dotted(t):
                        self.assigned.setdefault(dotted(t), []).append(n.value)
            elif isinstance(n, ast.AnnAssign) and n.value is not None and dotted(n.target):
                self.assigned.setdefault(dotted(n.target), []).append(n.value)
            elif isinstance(n, (ast.With, ast.AsyncWith)):
                for item in n.items:
                    if item.optional_vars is not None and dotted(item.optional_vars):
                        self.assigned.setdefault(dotted(item.optional_vars), []).append(item.context_expr)
            elif isinstance(n, FUNCS) and n is not func:
                self.local_defs[n.name] = n
            elif isinstance(n, ast.Global):
                self.globals.update(n.names)

    def lineno_end(self):
        return getattr(self.func, "end_lineno", 10 ** 9) if self.func else 10 ** 9


class Submission:
    """One place where a callable is handed to another thread."""

    def __init__(self, call, kind, scope, executor_key, executor_kind, fn, extra, wrapped):
        self.call = call
        self.kind = kind                  # submit | map | thread | to_thread | run_in_executor
        self.scope = scope
        self.executor_key = executor_key  # dotted receiver ('ex', 'self._pool') or ''
        self.executor_kind = executor_kind
        self.fn = fn                      # the callable expression
        self.extra = extra                # positional argument nodes passed to the callable
        self.wrapped = wrapped            # submitted via ctx.run / copy_context().run / to_thread
        self.worker = None                # resolved FunctionDef / Lambda


# ====================================================================== analyzer

class Analyzer:
    def __init__(self, path, source, tree):
        self.path = path
        self.lines = source.splitlines()
        self.tree = tree
        self.findings = []
        self.seen = set()
        self.imports = {}
        self.module_defs = {}
        self.classes = {}
        self.thread_classes = set()
        self.executor_classes = {}        # local ThreadPoolExecutor subclasses -> kind
        self.context_executors = set()    # subclasses whose submit() uses copy_context()
        self.self_executor_attrs = {}     # attr -> kind, from `self.x = ThreadPoolExecutor()`
        self.scopes = []
        self.module_scope = None
        self.subs = []
        self.called_in_loop = set()

    # ------------------------------------------------------------ plumbing
    def add(self, rule, node, message):
        line = getattr(node, "lineno", 1)
        if (rule, line) in self.seen:
            return
        self.seen.add((rule, line))
        src = self.lines[line - 1] if 0 < line <= len(self.lines) else ""
        m = re.search(r"#\s*noqa(?::\s*([A-Za-z0-9_, ]+))?", src)
        if m and (not m.group(1) or rule in [c.strip().upper() for c in m.group(1).split(",")]):
            return
        info = RULES[rule]
        self.findings.append({
            "path": self.path, "line": line, "col": getattr(node, "col_offset", 0) + 1,
            "rule": rule, "name": info["name"], "severity": info["severity"], "message": message,
            "code": src.strip(), "why": info["why"], "fix": info["fix"],
        })

    def resolve(self, node):
        d = dotted(node)
        if not d:
            return ""
        head, _, rest = d.partition(".")
        full = self.imports.get(head)
        if full:
            return full + ("." + rest if rest else "")
        return d

    def ctor_kind(self, node):
        if not isinstance(node, ast.Call):
            return None
        r = self.resolve(node.func)
        if not r:
            return None
        last = r.rsplit(".", 1)[-1]
        return EXECUTOR_CTORS.get(last) or self.executor_classes.get(last)

    def ctor_class(self, recv, sc):
        """Class name of the executor bound to `recv` (via a constructor call), or ''."""
        values = [recv] if isinstance(recv, ast.Call) else self.lookup(dotted(recv), sc) if dotted(recv) else []
        for v in values:
            if self.ctor_kind(v):
                return self.resolve(v.func).rsplit(".", 1)[-1]
        ann = sc.params.get(dotted(recv), "")
        for name in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", ann):
            if name in self.executor_classes:
                return name
        return ""

    def is_thread_ctor(self, node):
        if not isinstance(node, ast.Call):
            return False
        r = self.resolve(node.func)
        return r in ("threading.Thread", "Thread") or r.rsplit(".", 1)[-1] in self.thread_classes

    def is_lock_ctor(self, node):
        return isinstance(node, ast.Call) and self.resolve(node.func).rsplit(".", 1)[-1] in LOCK_CTORS and \
            self.resolve(node.func).split(".")[0] in ("threading", "Lock", "RLock", "Condition", "Semaphore",
                                                      "BoundedSemaphore", "multiprocessing")

    def is_container(self, node):
        if isinstance(node, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)):
            return True
        return isinstance(node, ast.Call) and self.resolve(node.func).rsplit(".", 1)[-1] in CONTAINER_CTORS

    # ------------------------------------------------------------ indexing
    def link_parents(self):
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                child._tpe_parent = node

    def index(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.asname:
                        self.imports[a.asname] = a.name
                    else:
                        self.imports.setdefault(a.name.split(".")[0], a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                for a in node.names:
                    self.imports[a.asname or a.name] = f"{node.module}.{a.name}"
        for node in self.tree.body:
            if isinstance(node, FUNCS):
                self.module_defs[node.name] = node
            elif isinstance(node, ast.ClassDef):
                self.classes[node.name] = node
        changed = True
        while changed:                    # Thread subclasses, including subclasses of subclasses
            changed = False
            for c in self.classes.values():
                if c.name in self.thread_classes:
                    continue
                for b in c.bases:
                    r = self.resolve(b)
                    if r in ("threading.Thread", "Thread") or r in self.thread_classes:
                        self.thread_classes.add(c.name)
                        changed = True
        for _ in range(3):                # executor subclasses (e.g. a context-propagating executor)
            for c in self.classes.values():
                for b in c.bases:
                    last = self.resolve(b).rsplit(".", 1)[-1]
                    kind = EXECUTOR_CTORS.get(last) or self.executor_classes.get(last)
                    if kind:
                        self.executor_classes[c.name] = kind
                        if last in self.context_executors or any(
                                isinstance(m, FUNCS) and m.name == "submit" and any(
                                    isinstance(x, ast.Call) and self.resolve(x.func).endswith("copy_context")
                                    for x in ast.walk(m)) for m in c.body):
                            self.context_executors.add(c.name)
        self.module_scope = Scope(None, self.tree.body)
        self.scopes.append(self.module_scope)
        for node in ast.walk(self.tree):
            if isinstance(node, FUNCS):
                p = parent(node)
                self.scopes.append(Scope(node, node.body, p if isinstance(p, ast.ClassDef) else None))
        for sc in self.scopes:
            for key, values in sc.assigned.items():
                if key.startswith("self."):
                    for v in values:
                        k = self.ctor_kind(v)
                        if k:
                            self.self_executor_attrs[key[5:]] = k
            for n in sc.nodes:
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and loop_of(n) is not None:
                    self.called_in_loop.add(n.func.id)

    def scope_of(self, func):
        for sc in self.scopes:
            if sc.func is func:
                return sc
        return self.module_scope

    def lookup(self, name, sc):
        """Values bound to `name` in the scope, enclosing function scopes, or the module."""
        if name in sc.assigned and name not in sc.globals:
            return sc.assigned[name]
        f = sc.func
        while f is not None:
            f = enclosing_func(f)
            if f is None:
                break
            outer = self.scope_of(f)
            if name in outer.assigned:
                return outer.assigned[name]
        return self.module_scope.assigned.get(name, [])

    def executor_kind(self, recv, sc):
        """'thread'/'process'/'interp'/'executor' when known, 'maybe' by name, else None."""
        k = self.ctor_kind(recv)
        if k:
            return k
        d = dotted(recv)
        if not d:
            return None
        values = self.lookup(d, sc)
        if values:
            for v in values:
                k = self.ctor_kind(v)
                if k:
                    return k
            if all(isinstance(v, ast.Call) and self.resolve(v.func).rsplit(".", 1)[-1] in ("Pool", "ThreadPool")
                   for v in values):
                return None
        if d.startswith(("self.", "cls.")) and d.split(".", 1)[1] in self.self_executor_attrs:
            return self.self_executor_attrs[d.split(".", 1)[1]]
        ann = sc.params.get(d, "")
        if "ThreadPoolExecutor" in ann:
            return "thread"
        if "ProcessPoolExecutor" in ann:
            return "process"
        if "Executor" in ann:
            return "executor"
        last = d.rsplit(".", 1)[-1].lower().lstrip("_")
        if "executor" in last:
            return "executor"
        if last in ("pool", "ex", "tpe", "threadpool", "thread_pool", "workers") or last.endswith("_pool"):
            return "maybe"
        return None

    def resolve_callable(self, fn, sc):
        """(worker node or None, extra bound arg nodes) for a callable expression."""
        extra = []
        for _ in range(3):
            if isinstance(fn, ast.Call) and self.resolve(fn.func).rsplit(".", 1)[-1] == "partial" and fn.args:
                extra.extend(fn.args[1:])
                extra.extend(k.value for k in fn.keywords)
                fn = fn.args[0]
            else:
                break
        if isinstance(fn, ast.Lambda):
            return fn, extra
        if isinstance(fn, ast.Name):
            f = sc.func
            s = sc
            while True:
                if fn.id in s.local_defs:
                    return s.local_defs[fn.id], extra
                if f is None:
                    break
                f = enclosing_func(f)
                if f is None:
                    break
                s = self.scope_of(f)
            return self.module_defs.get(fn.id), extra
        d = dotted(fn)
        if d.startswith("self.") and sc.cls is not None and d.count(".") == 1:
            for n in sc.cls.body:
                if isinstance(n, FUNCS) and n.name == d[5:]:
                    return n, extra
        return None, extra

    def find_submissions(self):
        for sc in self.scopes:
            for n in sc.nodes:
                if not isinstance(n, ast.Call):
                    continue
                f = n.func
                sub = None
                if isinstance(f, ast.Attribute) and f.attr in ("submit", "map") and n.args:
                    k = self.executor_kind(f.value, sc)
                    if k and (f.attr == "submit" or k in STRONG_EXECUTOR):
                        sub = Submission(n, f.attr, sc, dotted(f.value), k, n.args[0], list(n.args[1:]),
                                         self.ctor_class(f.value, sc) in self.context_executors)
                elif self.is_thread_ctor(n):
                    target = kwarg(n, "target")
                    if target is None and len(n.args) >= 2:
                        target = n.args[1]
                    args = kwarg(n, "args")
                    extra = list(args.elts) if isinstance(args, (ast.Tuple, ast.List)) else []
                    if target is not None:
                        sub = Submission(n, "thread", sc, "", "thread", target, extra,
                                         kwarg(n, "context") is not None)
                elif self.resolve(f) == "asyncio.to_thread" and n.args:
                    sub = Submission(n, "to_thread", sc, "", "thread", n.args[0], list(n.args[1:]), True)
                elif isinstance(f, ast.Attribute) and f.attr == "run_in_executor" and len(n.args) >= 2:
                    k = "thread" if is_const(n.args[0], None) else (self.executor_kind(n.args[0], sc) or "executor")
                    sub = Submission(n, "run_in_executor", sc, dotted(n.args[0]), k, n.args[1],
                                     list(n.args[2:]), False)
                if sub is None:
                    continue
                fn = sub.fn
                if isinstance(fn, ast.Attribute) and fn.attr == "run" and \
                        ("ctx" in dotted(fn.value).lower() or "context" in dotted(fn.value).lower() or
                         (isinstance(fn.value, ast.Call) and
                          self.resolve(fn.value.func).endswith("copy_context"))):
                    sub.wrapped = True
                    if sub.extra:
                        fn = sub.extra[0]
                        sub.extra = sub.extra[1:]
                worker, bound = self.resolve_callable(fn, sc)
                sub.worker = worker
                sub.extra = bound + sub.extra
                self.subs.append(sub)

    def worker_nodes(self, w):
        if isinstance(w, ast.Lambda):
            return list(ast.walk(w.body))
        return list(walk_local(w.body))

    def worker_name(self, w):
        return "<lambda>" if isinstance(w, ast.Lambda) else w.name

    # ------------------------------------------------------------ run
    def run(self):
        self.link_parents()
        self.index()
        self.find_submissions()
        for sc in self.scopes:
            self.check_futures(sc)
            self.check_shutdown(sc)
            self.check_unbounded(sc)
            self.check_map(sc)
            self.check_pool_size(sc)
            self.check_handler_results(sc)
            self.check_shutdown_nowait(sc)
            self.check_threads(sc)
            self.check_polling(sc)
            self.check_swallowed(sc)
            self.check_per_call(sc)
        self.check_shared_state()
        self.check_unsafe_clients()
        self.check_self_wait()
        self.check_cpu_bound()
        self.check_contextvars()
        return self.findings

    # ------------------------------------------------------------ TPE001
    def callback_handles(self, cb, sc):
        w, _ = self.resolve_callable(cb, sc)
        if w is None:
            return True                   # cannot see it: assume it reads the future
        for n in self.worker_nodes(w):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and \
                    n.func.attr in ("result", "exception"):
                return True
        return False

    def name_reads(self, name, sc, after_node):
        """Load sites of `name` in the scope (including nested functions), excluding the binding itself."""
        root = sc.func if sc.func is not None else self.tree
        out = []
        for n in ast.walk(root):
            if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load) and n is not after_node:
                out.append(n)
        return out

    def unhandled_reads(self, reads, sc):
        """Drop reads that are only `name.add_done_callback(cb)` with a callback that never reads it."""
        real = []
        for r in reads:
            p = parent(r)
            if isinstance(p, ast.Attribute) and p.attr == "add_done_callback" and \
                    isinstance(parent(p), ast.Call) and parent(p).args and \
                    not self.callback_handles(parent(p).args[0], sc):
                continue
            real.append(r)
        return real

    def check_futures(self, sc):
        for sub in self.subs:
            if sub.scope is not sc or sub.kind != "submit":
                continue
            node = sub.call
            holder = node
            p = parent(node)
            if isinstance(p, COMPS) and (getattr(p, "elt", None) is node or getattr(p, "key", None) is node
                                         or getattr(p, "value", None) is node):
                holder, p = p, parent(p)
            if isinstance(p, ast.Expr):
                what = "list of futures" if holder is not node else "future"
                self.add("TPE001", node, f"{what} from `{sub.executor_key}.submit(...)` is discarded: exceptions "
                         "raised by the task are never seen")
                continue
            if isinstance(p, ast.Attribute) and p.attr == "add_done_callback" and isinstance(parent(p), ast.Call):
                cb_call = parent(p)
                if cb_call.args and not self.callback_handles(cb_call.args[0], sc) and \
                        isinstance(parent(cb_call), ast.Expr):
                    self.add("TPE001", node, "add_done_callback() whose callback never calls result()/exception(): "
                             "the task's exception is still lost")
                continue
            if isinstance(p, (ast.Assign, ast.AnnAssign)):
                targets = p.targets if isinstance(p, ast.Assign) else [p.target]
                if len(targets) != 1 or not isinstance(targets[0], ast.Name):
                    continue
                name = targets[0].id
                reads = self.unhandled_reads(self.name_reads(name, sc, targets[0]), sc)
                if not reads:
                    self.add("TPE001", node, f"`{name}` holds the future(s) but is never read: worker exceptions "
                             "are silently lost")
                    continue
                loop = loop_of(p)
                if holder is node and loop is not None and not isinstance(loop, COMPS) and \
                        all(not inside(r, loop) for r in reads):
                    self.add("TPE001", node, f"`{name}` is reassigned on every loop iteration and only read after "
                             "the loop: all futures but the last are dropped")

    # ------------------------------------------------------------ TPE002
    def escapes(self, name, sc, binding):
        for r in self.name_reads(name, sc, binding):
            p = parent(r)
            if isinstance(p, ast.Attribute):
                if p.attr == "shutdown":
                    return True
                continue
            if isinstance(p, ast.withitem):
                return True
            return True                   # returned, passed, stored: someone else owns it
        return False

    def check_shutdown(self, sc):
        for n in sc.nodes:
            k = self.ctor_kind(n)
            if not k:
                continue
            p = parent(n)
            if isinstance(p, ast.withitem):
                continue
            if isinstance(p, ast.Attribute) and p.attr in ("submit", "map"):
                self.add("TPE002", n, f"anonymous `{self.resolve(n.func).rsplit('.', 1)[-1]}()` used inline: it "
                         "can never be shut down or used as a context manager")
                continue
            if not isinstance(p, (ast.Assign, ast.AnnAssign)):
                continue
            targets = p.targets if isinstance(p, ast.Assign) else [p.target]
            if len(targets) != 1:
                continue
            t = targets[0]
            if isinstance(t, ast.Name):
                if sc.func is not None and t.id not in sc.globals:
                    if not self.escapes(t.id, sc, t):
                        self.add("TPE002", n, f"`{t.id}` is never shut down and never used with `with`: threads "
                                 "leak on every call and errors have no collection point")
                elif not self.module_refs_shutdown(t.id):
                    self.add("TPE002", n, f"module-level executor `{t.id}` is never shut down: its threads are only "
                             "joined by the interpreter's exit hook, after every queued task has run")
            elif dotted(t).startswith("self.") and not self.module_refs_shutdown(dotted(t)[5:]):
                self.add("TPE002", n, f"`{dotted(t)}` is never shut down: add a close()/__exit__ that calls "
                         "shutdown()")

    def module_refs_shutdown(self, name):
        for n in ast.walk(self.tree):
            if isinstance(n, ast.Attribute) and n.attr == "shutdown":
                d = dotted(n.value)
                if d == name or d.endswith("." + name):
                    return True
            if isinstance(n, ast.withitem) and dotted(n.context_expr).rsplit(".", 1)[-1] == name:
                return True
        return False

    # ------------------------------------------------------------ TPE003 / TPE004
    def is_unbounded(self, it, sc, depth=0):
        if isinstance(it, ast.GeneratorExp):
            return "a generator expression"
        if isinstance(it, ast.Attribute) and self.resolve(it) == "sys.stdin":
            return "sys.stdin"
        if isinstance(it, ast.Call):
            r = self.resolve(it.func)
            last = r.rsplit(".", 1)[-1]
            if r == "range" and it.args:
                end = it.args[0] if len(it.args) == 1 else it.args[1]
                if isinstance(end, ast.Constant) and isinstance(end.value, int) and end.value > 10000:
                    return f"range({end.value})"
                return None
            if r in UNBOUNDED_FUNCS and not (r == "itertools.repeat" and len(it.args) > 1):
                return f"{r}()"
            if isinstance(it.func, ast.Attribute) and it.func.attr in UNBOUNDED_ATTRS:
                return f".{it.func.attr}()"
            if last.startswith(UNBOUNDED_PREFIXES):
                return f"{last}()"
            if last in ("enumerate", "zip", "islice") and it.args:
                if last == "islice":
                    return None
                for a in it.args:
                    why = self.is_unbounded(a, sc, depth + 1)
                    if why:
                        return why
                return None
            fdef = self.module_defs.get(r)
            if fdef is not None and any(isinstance(x, (ast.Yield, ast.YieldFrom)) for x in walk_local(fdef.body)):
                return f"generator function {r}()"
            return None
        if isinstance(it, ast.Name) and depth < 3:
            for v in self.lookup(it.id, sc):
                why = self.is_unbounded(v, sc, depth + 1)
                if why:
                    return f"`{it.id}` ({why})"
        return None

    def bounded_body(self, loop):
        for n in walk_local(loop.body if hasattr(loop, "body") and isinstance(loop.body, list) else []):
            if isinstance(n, ast.Call):
                d = dotted(n.func)
                last = d.rsplit(".", 1)[-1]
                if last in ("acquire", "wait", "as_completed", "result", "join"):
                    return True
            if isinstance(n, (ast.With, ast.AsyncWith)):
                for item in n.items:
                    if re.search(r"sem|slot|limit|bound|throttle", dotted(item.context_expr) or
                                 (dotted(item.context_expr.func) if isinstance(item.context_expr, ast.Call) else ""),
                                 re.I):
                        return True
            if isinstance(n, ast.Compare) and isinstance(n.left, ast.Call) and dotted(n.left.func) == "len":
                return True
        return False

    def check_unbounded(self, sc):
        for sub in self.subs:
            if sub.scope is not sc or sub.kind != "submit":
                continue
            loop = loop_of(sub.call)
            if loop is None:
                continue
            if isinstance(loop, COMPS):
                for g in loop.generators:
                    why = self.is_unbounded(g.iter, sc)
                    if why:
                        self.add("TPE003", sub.call, f"comprehension submits one future per element of {why}: "
                                 "nothing limits how many are queued")
                        break
                continue
            if isinstance(loop, ast.While):
                t = loop.test
                unbounded = (isinstance(t, ast.Constant) and bool(t.value)) or \
                    any(isinstance(x, ast.Call) and dotted(x.func).rsplit(".", 1)[-1] in
                        ("readline", "get", "is_set") for x in ast.walk(t))
                why = "a `while` loop" if unbounded else None
            else:
                why = self.is_unbounded(loop.iter, sc)
            if why and not self.bounded_body(loop):
                self.add("TPE003", sub.call, f"submit() inside a loop over {why} with no semaphore, sliding "
                         "window or wait(): the work queue grows without bound")

    def check_map(self, sc):
        for sub in self.subs:
            if sub.scope is not sc or sub.kind != "map":
                continue
            node = sub.call
            if kwarg(node, "buffersize") is None:
                for it in node.args[1:]:
                    why = self.is_unbounded(it, sc)
                    if why:
                        self.add("TPE004", node, f"`{sub.executor_key}.map()` over {why} submits every element "
                                 "before yielding the first result (pass buffersize= on 3.14+, or use a window)")
                        break
            timeout = kwarg(node, "timeout")
            p = parent(node)
            if isinstance(p, ast.Expr):
                extra = " (and its timeout= is never enforced)" if timeout is not None else ""
                self.add("TPE005", node, f"result of `{sub.executor_key}.map()` is discarded: worker exceptions "
                         f"are never raised{extra}")
                continue
            if isinstance(p, ast.Assign) and len(p.targets) == 1 and isinstance(p.targets[0], ast.Name):
                name = p.targets[0].id
                reads = self.name_reads(name, sc, p.targets[0])
                if not reads:
                    self.add("TPE005", node, f"`{name}` holds the map() iterator but is never iterated: "
                             "worker exceptions are never raised")
                    continue
                if timeout is not None:
                    w = parent(p)
                    while w is not None and not isinstance(w, (ast.With,) + SCOPES + (ast.Module,)):
                        w = parent(w)
                    if isinstance(w, ast.With) and any(self.ctor_kind(i.context_expr) or
                                                       dotted(i.optional_vars) == sub.executor_key
                                                       for i in w.items if i.optional_vars is not None) and \
                            all(r.lineno > getattr(w, "end_lineno", 10 ** 9) for r in reads):
                        self.add("TPE005", node, f"`{name}` is iterated after the executor's `with` block, which "
                                 "already waited for every task: the map() timeout can never fire")

    # ------------------------------------------------------------ TPE006 / TPE007
    def shared_containers(self, w):
        """name -> 'module'|'enclosing' for containers/counters the worker can reach."""
        out = {}
        for name, values in self.module_scope.assigned.items():
            if "." in name:
                continue
            if any(self.is_container(v) for v in values):
                out[name] = ("module", "container")
            elif any(isinstance(v, ast.Constant) and isinstance(v.value, (int, float)) and
                     not isinstance(v.value, bool) for v in values):
                out[name] = ("module", "counter")
        f = enclosing_func(w) if not isinstance(w, ast.Lambda) else enclosing_func(w)
        if f is not None:
            for name, values in self.scope_of(f).assigned.items():
                if "." in name:
                    continue
                if any(self.is_container(v) for v in values):
                    out[name] = ("enclosing", "container")
                elif any(isinstance(v, ast.Constant) and isinstance(v.value, (int, float)) for v in values):
                    out[name] = ("enclosing", "counter")
        return out

    def lockish(self, expr):
        target = expr.func if isinstance(expr, ast.Call) else expr
        d = dotted(target)
        if d and LOCKISH.search(d.rsplit(".", 1)[-1]):
            return True
        if d:
            for v in self.module_scope.assigned.get(d, []):
                if self.is_lock_ctor(v):
                    return True
        return False

    def under_lock(self, node, w):
        p = parent(node)
        while p is not None and p is not w:
            if isinstance(p, (ast.With, ast.AsyncWith)) and any(self.lockish(i.context_expr) for i in p.items):
                return True
            p = parent(p)
        return False

    def worker_acquires(self, nodes):
        return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "acquire"
                   and self.lockish(n.func.value) for n in nodes)

    def check_shared_state(self):
        done = set()
        for sub in self.subs:
            w = sub.worker
            if w is None or id(w) in done:
                continue
            done.add(id(w))
            nodes = self.worker_nodes(w)
            if self.worker_acquires(nodes):
                continue
            shared = self.shared_containers(w)
            declared = set()
            local = set()
            if not isinstance(w, ast.Lambda):
                a = w.args
                local.update(x.arg for x in a.posonlyargs + a.args + a.kwonlyargs)
            for n in nodes:
                if isinstance(n, (ast.Global, ast.Nonlocal)):
                    declared.update(n.names)
            for n in nodes:
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id not in declared:
                    local.add(n.id)
            reach = {k: v for k, v in shared.items() if k not in local}
            wname = self.worker_name(w)
            for n in nodes:
                if self.under_lock(n, w):
                    continue
                if isinstance(n, ast.AugAssign):
                    t = n.target
                    if isinstance(t, ast.Name) and t.id in declared and t.id in reach:
                        self.add("TPE006", n, f"worker {wname}() does `{t.id} {self.op(n)}= ...` on shared state "
                                 "without a lock: concurrent updates are lost")
                    elif isinstance(t, ast.Subscript) and dotted(t.value) in reach:
                        self.add("TPE006", n, f"worker {wname}() does `{dotted(t.value)}[...] {self.op(n)}= ...` "
                                 "without a lock: read-modify-write races lose updates")
                elif isinstance(n, ast.Assign) and len(n.targets) == 1:
                    t = n.targets[0]
                    if isinstance(t, ast.Subscript) and dotted(t.value) in reach:
                        name = dotted(t.value)
                        guard = self.check_then_set(n, name)
                        if name in names_loaded(n.value) or guard:
                            what = "check-then-set" if guard else "read-modify-write"
                            self.add("TPE006", n, f"worker {wname}() does a {what} on `{name}[...]` without a "
                                     "lock: two threads can both read the old value")
                        elif reach[name][0] == "module":
                            self.add("TPE007", n, f"worker {wname}() assigns into module-level `{name}` without a "
                                     "lock; return the value from the task instead")
                    elif isinstance(t, ast.Name) and t.id in declared and t.id in reach and \
                            t.id in names_loaded(n.value):
                        self.add("TPE006", n, f"worker {wname}() rebinds shared `{t.id}` from its old value "
                                 "without a lock: concurrent updates are lost")
                elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and \
                        n.func.attr in MUTATORS and isinstance(n.func.value, ast.Name) and \
                        n.func.value.id in reach and reach[n.func.value.id] == ("module", "container"):
                    self.add("TPE007", n, f"worker {wname}() calls `{n.func.value.id}.{n.func.attr}()` on a "
                             "module-level container without a lock")

    @staticmethod
    def op(n):
        return {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.BitOr: "|"}.get(type(n.op), "op")

    def check_then_set(self, assign, name):
        p = parent(assign)
        while p is not None and not isinstance(p, SCOPES):
            if isinstance(p, ast.If) and name in names_loaded(p.test):
                return True
            p = parent(p)
        return False

    # ------------------------------------------------------------ TPE008
    def unsafe_kind(self, v):
        if isinstance(v, ast.Call):
            return UNSAFE_CLIENTS.get(self.resolve(v.func))
        return None

    def check_unsafe_clients(self):
        module_unsafe = {}
        for name, values in self.module_scope.assigned.items():
            for v in values:
                k = self.unsafe_kind(v)
                if k and "." not in name:
                    module_unsafe[name] = (k, v)
        for sub in self.subs:
            w = sub.worker
            sc = sub.scope
            # module-level client referenced inside the worker body
            if w is not None and module_unsafe:
                nodes = self.worker_nodes(w)
                local = set()
                if not isinstance(w, ast.Lambda):
                    local.update(x.arg for x in w.args.args + w.args.kwonlyargs)
                    local.update(n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
                for n in nodes:
                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in module_unsafe and \
                            n.id not in local and not self.under_lock(n, w):
                        kind, ctor = module_unsafe[n.id]
                        self.add("TPE008", ctor, f"{kind} `{n.id}` is created once at module level and used from "
                                 f"worker thread function {self.worker_name(w)}() (line {n.lineno})")
                        break
            # local client passed to / captured by the worker
            candidates = {}
            for name, values in sc.assigned.items():
                for v in values:
                    k = self.unsafe_kind(v)
                    if k and "." not in name and name not in module_unsafe:
                        candidates[name] = (k, v)
            if not candidates:
                continue
            passed = set()
            for a in sub.extra:
                passed |= names_loaded(a) & set(candidates)
            for k in sub.call.keywords:
                if k.arg not in ("target", "name", "daemon"):
                    passed |= names_loaded(k.value) & set(candidates)
            if w is not None and (isinstance(w, ast.Lambda) or enclosing_func(w) is sc.func):
                body = w.body if isinstance(w, ast.Lambda) else w
                passed |= names_loaded(body) & set(candidates)
            for name in sorted(passed):
                kind, ctor = candidates[name]
                self.add("TPE008", ctor, f"{kind} `{name}` is created once and shared with worker threads via "
                         f"{sub.kind}() at line {sub.call.lineno}")

    # ------------------------------------------------------------ TPE009
    def check_self_wait(self):
        for sub in self.subs:
            w = sub.worker
            if w is None or isinstance(w, ast.Lambda) or sub.kind not in ("submit", "map") or not sub.executor_key:
                continue
            keys = {sub.executor_key}
            params = [x.arg for x in w.args.posonlyargs + w.args.args]
            if params and params[0] in ("self", "cls") and isinstance(parent(w), ast.ClassDef):
                params = params[1:]
            for i, a in enumerate(sub.extra):
                if dotted(a) == sub.executor_key and i < len(params):
                    keys.add(params[i])
            nodes = self.worker_nodes(w)
            inner = [n for n in nodes if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and
                     n.func.attr in ("submit", "map") and dotted(n.func.value) in keys]
            if not inner:
                continue
            waits = any(isinstance(n, ast.Call) and (
                (isinstance(n.func, ast.Attribute) and n.func.attr == "result") or
                dotted(n.func).rsplit(".", 1)[-1] in ("wait", "as_completed", "list")) for n in nodes) or \
                any(isinstance(n, (ast.For, ast.comprehension)) and isinstance(n.iter, ast.Call) and
                    n.iter in inner for n in nodes)
            if waits:
                self.add("TPE009", inner[0], f"{w.name}() runs on `{sub.executor_key}` and blocks on work it submits "
                         "to the same executor: deadlocks once every worker is waiting")

    # ------------------------------------------------------------ TPE010
    def check_pool_size(self, sc):
        for n in sc.nodes:
            if self.ctor_kind(n) != "thread":
                continue
            mw = kwarg(n, "max_workers")
            if mw is None and n.args:
                mw = n.args[0]
            if not (isinstance(mw, ast.Constant) and isinstance(mw.value, int)) or isinstance(mw.value, bool):
                continue
            v = mw.value
            if v <= 0:
                self.add("TPE010", n, f"max_workers={v} raises ValueError")
            elif v == 1:
                self.add("TPE010", n, "max_workers=1 is a serial loop with thread overhead; fine only to serialize "
                         "access to one resource (say so in a comment and add # noqa: TPE010)")
            elif v > 64:
                self.add("TPE010", n, f"max_workers={v}: size from the rate limit and latency (Little's law), not a "
                         "big constant")

    # ------------------------------------------------------------ TPE011
    def check_handler_results(self, sc):
        if not is_handler_func(sc.func):
            return
        for n in sc.nodes:
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "result" and \
                    not n.args and kwarg(n, "timeout") is None and loop_of(n) is not None:
                self.add("TPE011", n, f"request handler {sc.func.name}() waits on .result() with no timeout in a "
                         "loop: one hung upstream call hangs the request")

    # ------------------------------------------------------------ TPE012
    def check_shutdown_nowait(self, sc):
        for n in sc.nodes:
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "shutdown"):
                continue
            wait = kwarg(n, "wait")
            if wait is None and n.args:
                wait = n.args[0]
            if not is_const(wait, False):
                continue
            cf = kwarg(n, "cancel_futures")
            if cf is not None and not is_const(cf, False):
                continue
            if self.on_exit_path(n, sc):
                self.add("TPE012", n, "shutdown(wait=False) without cancel_futures=True on an exit path: queued "
                         "tasks still run and the interpreter waits for them at exit")

    def on_exit_path(self, node, sc):
        if sc.func is not None and MAIN_FUNC.match(sc.func.name):
            return True
        p = parent(node)
        while p is not None and not isinstance(p, SCOPES):
            if is_main_guard(p):
                return True
            if isinstance(p, ast.ExceptHandler) and p.type is not None and \
                    any(dotted(t).rsplit(".", 1)[-1] in ("KeyboardInterrupt", "SystemExit", "BaseException")
                        for t in (p.type.elts if isinstance(p.type, ast.Tuple) else [p.type])):
                return True
            p = parent(p)
        return any(isinstance(x, ast.Call) and dotted(x.func) in EXIT_CALLS and x.lineno > node.lineno
                   for x in sc.nodes)

    # ------------------------------------------------------------ TPE013 / TPE017
    def daemon_set(self, call, name, sc):
        d = kwarg(call, "daemon")
        if d is not None:
            return is_const(d, True)
        if name is None:
            return False
        for n in sc.nodes:
            if isinstance(n, ast.Assign) and any(dotted(t) == f"{name}.daemon" for t in n.targets):
                return is_const(n.value, True)
            if isinstance(n, ast.Call) and dotted(n.func) == f"{name}.setDaemon" and n.args:
                return is_const(n.args[0], True)
        return False

    def check_threads(self, sc):
        any_join = any(isinstance(n, ast.Call) and is_thread_join(n) for n in sc.nodes)
        for n in sc.nodes:
            if not self.is_thread_ctor(n):
                continue
            p = parent(n)
            name = None
            chained_start = isinstance(p, ast.Attribute) and p.attr == "start"
            if isinstance(p, ast.Assign) and len(p.targets) == 1 and isinstance(p.targets[0], ast.Name):
                name = p.targets[0].id
            elif not chained_start:
                if isinstance(p, ast.Assign) and dotted(p.targets[0]).startswith("self."):
                    continue
                if isinstance(p, (ast.ListComp, ast.List)) and isinstance(parent(p), ast.Assign) and \
                        any(not isinstance(t, ast.Name) for t in parent(p).targets):
                    continue
                if isinstance(p, (ast.Return, ast.Call, ast.keyword)):
                    continue
            daemon = self.daemon_set(n, name, sc)
            joined = any_join
            if name is not None:
                joined = any(isinstance(x, ast.Call) and is_thread_join(x) and
                             (dotted(x.func.value) == name) for x in sc.nodes) or any_join
            if daemon:
                sub = next((s for s in self.subs if s.call is n), None)
                w = sub.worker if sub else None
                if w is None and self.resolve(n.func).rsplit(".", 1)[-1] in self.thread_classes:
                    cls = self.classes.get(self.resolve(n.func).rsplit(".", 1)[-1])
                    w = next((m for m in cls.body if isinstance(m, FUNCS) and m.name == "run"), None) if cls else None
                if w is not None and not joined:
                    effects = sorted({x.func.attr for x in self.worker_nodes(w) if isinstance(x, ast.Call) and
                                      isinstance(x.func, ast.Attribute) and x.func.attr in SIDE_EFFECTS and
                                      not CONSOLE.search(dotted(x.func.value) or "-")})
                    if effects:
                        self.add("TPE013", n, f"daemon thread runs {self.worker_name(w)}() which calls "
                                 f"{', '.join(effects[:3])}(): it is killed mid-write at interpreter exit")
                continue
            started = chained_start or (name is not None and any(
                isinstance(x, ast.Call) and dotted(x.func) == f"{name}.start" for x in sc.nodes))
            if not started:
                if isinstance(p, (ast.ListComp, ast.List)) or isinstance(parent(p), ast.Assign):
                    started = any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and
                                  x.func.attr == "start" for x in sc.nodes)
                if not started:
                    continue
            if chained_start:
                self.add("TPE017", n, "`Thread(...).start()` keeps no reference: the thread can never be joined "
                         "and its failure is never observed")
            elif not joined:
                if name is not None and self.thread_escapes(name, sc):
                    continue
                self.add("TPE017", n, "thread is started but never joined (and is not a daemon): its exception "
                         "only reaches threading.excepthook and nobody knows when it finished")

    def thread_escapes(self, name, sc):
        for r in self.name_reads(name, sc, None):
            p = parent(r)
            if isinstance(p, (ast.Return, ast.Yield)):
                return True
            if isinstance(p, ast.Assign) and any(not isinstance(t, ast.Name) for t in p.targets):
                return True
            if isinstance(p, ast.Call) and r in p.args:
                f = p.func
                if not (isinstance(f, ast.Attribute) and f.attr in ("append", "add", "extend")):
                    return True                   # handed to someone else
                if not isinstance(f.value, ast.Name) or f.value.id not in sc.assigned:
                    return True                   # stored on self / a non-local registry that may join it
        return False

    # ------------------------------------------------------------ TPE014
    def check_polling(self, sc):
        for n in sc.nodes:
            if not isinstance(n, ast.While):
                continue
            inner = list(walk_local([n]))
            done = any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr == "done"
                       and not x.args for x in inner)
            sleeps = any(isinstance(x, ast.Call) and self.resolve(x.func) in ("time.sleep", "sleep") and
                         not isinstance(parent(x), ast.Await) for x in inner)
            if done and sleeps:
                self.add("TPE014", n, "loop polls future.done() with time.sleep(): use wait()/as_completed(), which "
                         "wake on completion and surface exceptions")

    # ------------------------------------------------------------ TPE015
    def check_swallowed(self, sc):
        for n in sc.nodes:
            if not isinstance(n, ast.Try):
                continue
            reads = any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and
                        x.func.attr in ("result", "exception") for x in walk_local(n.body))
            if not reads:
                continue
            for h in n.handlers:
                types = [] if h.type is None else (h.type.elts if isinstance(h.type, ast.Tuple) else [h.type])
                broad = h.type is None or any(dotted(t).rsplit(".", 1)[-1] in ("Exception", "BaseException")
                                              for t in types)
                if not broad or logs_or_raises(h.body):
                    continue
                if h.name and any(isinstance(x, ast.Name) and x.id == h.name for x in walk_local(h.body)):
                    continue
                if any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and
                       x.func.attr in ("exception", "result") for x in walk_local(h.body)):
                    continue
                label = "bare except" if h.type is None else f"except {ast.unparse(h.type)}" \
                    if hasattr(ast, "unparse") else "except Exception"
                self.add("TPE015", h, f"`{label}` around future.result() discards the task's exception")

    # ------------------------------------------------------------ TPE016
    def check_per_call(self, sc):
        if sc.func is None:
            return
        worker_ids = {id(s.worker) for s in self.subs if s.worker is not None}
        for n in sc.nodes:
            if not self.ctor_kind(n):
                continue
            if loop_of(n) is not None:
                where = "inside a loop"
            elif id(sc.func) in worker_ids:
                where = f"inside {sc.func.name}(), which itself runs as a pool task"
            elif is_handler_func(sc.func):
                where = f"per request in handler {sc.func.name}()"
            elif sc.func.name in self.called_in_loop and sc.cls is None:
                where = f"in {sc.func.name}(), which is called inside a loop"
            else:
                continue
            self.add("TPE016", n, f"executor created {where}: create it once and reuse it")

    # ------------------------------------------------------------ TPE018
    def check_cpu_bound(self):
        done = set()
        for sub in self.subs:
            w = sub.worker
            if w is None or isinstance(w, ast.Lambda) or id(w) in done or sub.executor_kind not in ("thread",):
                continue
            done.add(id(w))
            nodes = self.worker_nodes(w)
            loops = [n for n in nodes if isinstance(n, (ast.For, ast.While))]
            arith = [n for n in nodes if (isinstance(n, ast.BinOp) and isinstance(n.op, ARITH)) or
                     (isinstance(n, ast.AugAssign) and isinstance(n.op, ARITH))]
            if not loops or not arith or any(isinstance(n, (ast.Await, ast.Yield, ast.YieldFrom)) for n in nodes):
                continue
            pure = True
            for n in nodes:
                if isinstance(n, ast.Call):
                    r = self.resolve(n.func)
                    if not (r in PURE_CALLS or r.startswith(("math.", "cmath."))):
                        pure = False
                        break
            if pure:
                self.add("TPE018", sub.call, f"{w.name}() is pure-Python arithmetic: threads cannot run it in "
                         "parallel on a GIL build; use processes or vectorize (see python-gil-bottleneck-analyzer)")

    # ------------------------------------------------------------ TPE019
    def check_contextvars(self):
        cvars = {name for name, values in self.module_scope.assigned.items()
                 if any(isinstance(v, ast.Call) and self.resolve(v.func).rsplit(".", 1)[-1] == "ContextVar"
                        for v in values)}
        if not cvars:
            return

        def reads_var(nodes):
            for n in nodes:
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "get" and \
                        isinstance(n.func.value, ast.Name) and n.func.value.id in cvars:
                    return n.func.value.id
            return None

        for sub in self.subs:
            if sub.wrapped or sub.worker is None or sub.kind == "to_thread":
                continue
            nodes = self.worker_nodes(sub.worker)
            var = reads_var(nodes)
            if var is None:
                for n in nodes:
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in self.module_defs:
                        var = reads_var(walk_local(self.module_defs[n.func.id].body))
                        if var:
                            break
            if var:
                self.add("TPE019", sub.call, f"{self.worker_name(sub.worker)}() reads ContextVar `{var}` but is "
                         f"started with {sub.kind}() without copy_context().run: it sees the default, not the "
                         "caller's value")


# ====================================================================== check driver

def lint_source(source, path):
    tree = ast.parse(source, filename=path)
    return Analyzer(path, source, tree).run()


def collect(paths):
    skip = {".git", ".venv", "venv", "__pycache__", "node_modules", ".tox", ".mypy_cache", "build", "dist"}
    for p in paths:
        if p != "-" and os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d not in skip)
                for f in sorted(files):
                    if f.endswith(".py"):
                        yield os.path.join(root, f), False
        else:
            yield p, True


def parse_rule_list(values):
    out = set()
    for v in values or []:
        for tok in v.split(","):
            tok = tok.strip()
            if not tok:
                continue
            matched = [rid for rid, info in RULES.items() if rid.startswith(tok.upper()) or info["name"] == tok]
            if not matched:
                raise ValueError(f"unknown rule {tok!r}; run `check --list-rules`")
            out.update(matched)
    return out


def print_rules(as_json):
    if as_json:
        print(json.dumps(RULES, indent=2))
        return
    for rid, info in RULES.items():
        print(f"{rid} [{info['severity']}] {info['name']}: {info['summary']}")
        print(f"    why: {info['why']}")
        print("    fix: " + info["fix"].replace("\n", "\n         "))
        print()


def cmd_check(args, ap):
    if args.list_rules:
        print_rules(args.json)
        return 0
    if not args.paths:
        ap.print_usage(sys.stderr)
        print("error: give at least one file, directory or - for stdin", file=sys.stderr)
        return 2
    try:
        select = parse_rule_list(args.select) or set(RULES)
        select -= parse_rule_list(args.ignore)
    except ValueError as err:
        ap.print_usage(sys.stderr)
        print(f"error: {err}", file=sys.stderr)
        return 2

    findings, errors, warnings, files = [], [], [], 0
    for path, explicit in collect(args.paths):
        label = "<stdin>" if path == "-" else path
        try:
            if path == "-":
                source = sys.stdin.read()
            else:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
            findings.extend(lint_source(source, label))
            files += 1
        except SyntaxError as err:
            (errors if explicit else warnings).append(f"{label}:{err.lineno}: cannot parse: {err.msg}")
        except (OSError, UnicodeDecodeError, ValueError, RecursionError) as err:
            (errors if explicit else warnings).append(f"{label}: cannot read: {err}")

    floor = SEVERITY_ORDER[args.min_severity]
    findings = [f for f in findings if f["rule"] in select and SEVERITY_ORDER[f["severity"]] <= floor]
    findings.sort(key=lambda f: (f["path"], f["line"], f["col"], f["rule"]))
    counts = {s: sum(f["severity"] == s for f in findings) for s in SEVERITY_ORDER}

    if args.json:
        print(json.dumps({"files": files, "summary": counts, "errors": errors, "warnings": warnings,
                          "findings": findings}, indent=2))
    else:
        for w in warnings:
            print(f"warning: skipped {w}", file=sys.stderr)
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        for f in findings:
            print(f"{f['path']}:{f['line']}:{f['col']}: {f['rule']} [{f['severity']}] {f['name']}: {f['message']}")
            if f["code"]:
                print(f"    > {f['code']}")
            print("    fix: " + f["fix"].replace("\n", "\n         "))
            print()
        if findings:
            print(f"{len(findings)} finding(s) in {files} file(s): {counts['high']} high, "
                  f"{counts['medium']} medium, {counts['low']} low")
        elif not errors:
            print(f"No thread-pool issues found in {files} file(s).")
    if errors:
        return 2
    return 1 if args.strict and findings else 0


# ====================================================================== scaffold recipes
#
# Each recipe is a complete module: typed, documented, stdlib-only, with stub work
# functions so it runs offline (`python generated.py`) in a few seconds. Recipes are
# checked with ast.parse before printing, and are clean under `check`.

RECIPES = {}


def recipe(name, summary):
    def deco(fn):
        RECIPES[name] = (summary, fn)
        return fn
    return deco


@recipe("bounded-map", "sliding window of futures: lazy input, max in-flight count, fail fast")
def _bounded_map():
    return r'''"""Bounded map over a huge iterable with a ThreadPoolExecutor (sliding window of futures).

Generated by executor_tool.py scaffold --recipe bounded-map.

Executor.map() submits every input before yielding anything (until Python 3.14 added
``buffersize=``), so a generator over millions of prompts or files is drained into the
work queue up front. ``bounded_map`` keeps at most ``max_in_flight`` futures alive,
reads the input lazily, yields results in completion order, and on the first task
exception cancels everything still queued and re-raises.

Offline demo (stub I/O, about 1 s):  python bounded_map.py
"""

from __future__ import annotations

import itertools
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import Callable, Dict, Iterable, Iterator, Optional, Tuple, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def bounded_map(
    fn: Callable[[T], R],
    items: Iterable[T],
    *,
    executor: ThreadPoolExecutor,
    max_in_flight: int,
    timeout: Optional[float] = None,
) -> Iterator[Tuple[int, R]]:
    """Yield ``(index, fn(item))`` in completion order, with at most ``max_in_flight`` tasks pending.

    The input is read lazily: a new item is pulled only when a slot frees up, so memory
    stays O(max_in_flight) however long the iterable is. ``timeout`` bounds the wait for
    the *next* completion (not the whole run). On a task exception or timeout the
    remaining queued futures are cancelled and the error propagates; running tasks
    finish in the background (threads cannot be killed).
    """
    if max_in_flight < 1:
        raise ValueError("max_in_flight must be >= 1")
    pending: Dict[Future, int] = {}
    source = enumerate(items)
    try:
        for index, item in itertools.islice(source, max_in_flight):
            pending[executor.submit(fn, item)] = index
        while pending:
            done, _ = wait(pending, timeout=timeout, return_when=FIRST_COMPLETED)
            if not done:
                raise TimeoutError(f"no task finished within {timeout} s")
            for fut in done:
                index = pending.pop(fut)
                yield index, fut.result()          # re-raises the task's exception here
            for index, item in itertools.islice(source, len(done)):
                pending[executor.submit(fn, item)] = index
    finally:
        for fut in pending:                        # early break, error or timeout
            fut.cancel()


# ---------------------------------------------------------------- offline demo

_stats_lock = threading.Lock()
_running = 0
_peak_running = 0


def fake_embed(text: str) -> int:
    """Stand-in for an embedding API call: ~5 ms of network wait, returns a token count."""
    global _running, _peak_running
    with _stats_lock:
        _running += 1
        _peak_running = max(_peak_running, _running)
    try:
        time.sleep(0.005)
        return len(text.split())
    finally:
        with _stats_lock:
            _running -= 1


def read_corpus(n: int) -> Iterator[str]:
    """Lazily produce documents, like iterating a JSONL file with millions of lines."""
    for i in range(n):
        yield f"document {i} " + "token " * (i % 7)


def main() -> None:
    started = time.perf_counter()
    count = tokens = 0
    with ThreadPoolExecutor(max_workers=16, thread_name_prefix="embed") as ex:
        for _, n_tokens in bounded_map(fake_embed, read_corpus(2000), executor=ex, max_in_flight=32):
            count += 1
            tokens += n_tokens
    elapsed = time.perf_counter() - started
    print(f"processed {count} documents ({tokens} tokens) in {elapsed:.2f} s")
    print(f"peak tasks running at once: {_peak_running} (max_workers=16, max_in_flight=32)")


if __name__ == "__main__":
    main()
'''


@recipe("rate-limited", "thread-safe token bucket (requests per minute + burst) shared by all workers")
def _rate_limited():
    return r'''"""Thread-safe token-bucket rate limiter (requests per minute) for ThreadPoolExecutor workers.

Generated by executor_tool.py scaffold --recipe rate-limited.

The provider's RPM/TPM limit, not your thread count, is the real ceiling for LLM and
embedding APIs. One ``TokenBucket`` is shared by every worker: ``acquire()`` blocks
(sleeping outside the lock) until a token is available, so all threads together stay
under ``rate_per_minute`` with at most ``burst`` calls back to back. Use ``tokens=`` to
spend estimated LLM tokens against a TPM bucket, and ``pause()`` to honour Retry-After.

Offline demo (about 2 s):  python rate_limited.py
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional


class TokenBucket:
    """A token bucket safe to share between threads.

    Tokens refill continuously at ``rate_per_minute / 60`` per second up to ``burst``.
    Over any window of T seconds at most ``burst + rate * T`` tokens are handed out.
    """

    def __init__(self, rate_per_minute: float, burst: Optional[int] = None) -> None:
        if rate_per_minute <= 0:
            raise ValueError("rate_per_minute must be > 0")
        self.rate = rate_per_minute / 60.0                 # tokens per second
        self.capacity = float(burst if burst is not None else max(1, int(self.rate)))
        self._tokens = self.capacity
        self._updated = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self, now: float) -> None:
        self._tokens = min(self.capacity, self._tokens + (now - self._updated) * self.rate)
        self._updated = now

    def acquire(self, tokens: float = 1.0, timeout: Optional[float] = None,
                stop: Optional[threading.Event] = None) -> bool:
        """Take ``tokens``; block until available. False on timeout or when ``stop`` is set."""
        if tokens > self.capacity:
            raise ValueError(f"asked for {tokens} tokens; bucket capacity is {self.capacity}")
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            with self._lock:
                self._refill(time.monotonic())
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True
                wait_s = (tokens - self._tokens) / self.rate
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                wait_s = min(wait_s, remaining)
            if stop is not None:
                if stop.wait(wait_s):                       # wakes immediately on shutdown
                    return False
            else:
                time.sleep(wait_s)

    def pause(self, seconds: float) -> None:
        """Server said Retry-After: drain the bucket so nobody calls for ``seconds``."""
        with self._lock:
            self._refill(time.monotonic())
            self._tokens = min(self._tokens, 0.0) - seconds * self.rate


# ---------------------------------------------------------------- offline demo

limiter = TokenBucket(rate_per_minute=1200, burst=5)      # 20 requests/s, 5 back to back
_calls_lock = threading.Lock()
_call_times: List[float] = []


def call_llm(prompt: str) -> str:
    """Stub LLM call: waits for a rate-limit token, then ~50 ms of 'network'."""
    limiter.acquire()
    with _calls_lock:
        _call_times.append(time.monotonic())
    time.sleep(0.05)
    return prompt.upper()


def max_in_window(times: List[float], window: float) -> int:
    times = sorted(times)
    best, j = 0, 0
    for i, t in enumerate(times):
        while times[j] <= t - window:
            j += 1
        best = max(best, i - j + 1)
    return best


def main() -> None:
    prompts = [f"prompt {i}" for i in range(40)]
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=16, thread_name_prefix="llm") as ex:
        futures = [ex.submit(call_llm, p) for p in prompts]
        answers = [f.result() for f in as_completed(futures)]
    elapsed = time.monotonic() - started
    print(f"{len(answers)} calls with 16 threads in {elapsed:.2f} s "
          f"(limit 20/s + burst 5 -> expected >= {(40 - 5) / 20:.2f} s)")
    print(f"max calls started in any 1 s window: {max_in_window(_call_times, 1.0)} (bound: 25)")


if __name__ == "__main__":
    main()
'''


@recipe("retrying", "retry with exponential backoff + full jitter, Retry-After, retryable exception types")
def _retrying():
    return r'''"""Retries with exponential backoff, full jitter and Retry-After for thread-pool tasks.

Generated by executor_tool.py scaffold --recipe retrying.

Retry only what is transient (429 rate limits, 5xx, timeouts, dropped connections);
never retry a 400/invalid prompt. Backoff uses "full jitter" (sleep a random amount in
[0, min(cap, base * 2**attempt)]) so N threads that failed together do not retry in
lock-step, and a server-provided Retry-After wins when it is longer. Sleeping on a
``threading.Event`` makes retries stop immediately on shutdown.

Offline demo (about 1 s):  python retrying.py
"""

from __future__ import annotations

import logging
import random
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, Optional, Tuple, Type, TypeVar

R = TypeVar("R")
log = logging.getLogger("retrying")


class RetryableError(Exception):
    """A transient failure. ``retry_after`` carries the server's hint in seconds, if any."""

    def __init__(self, message: str, retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class RateLimitError(RetryableError):
    """HTTP 429."""


class ServerError(RetryableError):
    """HTTP 5xx / overloaded."""


class BadRequestError(Exception):
    """HTTP 400: retrying cannot help."""


RETRYABLE: Tuple[Type[BaseException], ...] = (RetryableError, TimeoutError, ConnectionError)


def retry_call(
    fn: Callable[..., R],
    *args: object,
    attempts: int = 5,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    retryable: Tuple[Type[BaseException], ...] = RETRYABLE,
    stop: Optional[threading.Event] = None,
    on_retry: Optional[Callable[[int, BaseException, float], None]] = None,
) -> R:
    """Call ``fn(*args)``; retry ``retryable`` errors with backoff + full jitter.

    Raises the last error after ``attempts`` tries, or immediately for anything not in
    ``retryable``. If ``stop`` is set while waiting, the pending error is raised at once.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    for attempt in range(1, attempts + 1):
        try:
            return fn(*args)
        except retryable as exc:
            if attempt == attempts:
                raise
            delay = random.uniform(0.0, min(max_delay, base_delay * 2 ** (attempt - 1)))
            hint = getattr(exc, "retry_after", None)
            if hint is not None:
                delay = max(delay, float(hint))
            if on_retry is not None:
                on_retry(attempt, exc, delay)
            log.debug("attempt %d failed (%r); retrying in %.2fs", attempt, exc, delay)
            if stop is not None:
                if stop.wait(delay):
                    raise
            else:
                time.sleep(delay)
    raise AssertionError("unreachable")


# ---------------------------------------------------------------- offline demo

_attempts_lock = threading.Lock()
_attempts: Counter = Counter()


def flaky_completion(item: int) -> str:
    """Stub API: every 4th item gets two 429s, every 5th one 503, every 10th is a bad request."""
    with _attempts_lock:
        _attempts[item] += 1
        attempt = _attempts[item]
    time.sleep(0.01)
    if item % 10 == 9:
        raise BadRequestError(f"item {item}: prompt too long")
    if item % 4 == 0 and attempt <= 2:
        raise RateLimitError("429 Too Many Requests", retry_after=0.02)
    if item % 5 == 0 and attempt == 1:
        raise ServerError("503 overloaded")
    return f"answer-{item}"


def main() -> None:
    ok: Dict[int, str] = {}
    failed: Dict[int, BaseException] = {}
    with ThreadPoolExecutor(max_workers=8, thread_name_prefix="llm") as ex:
        futures = {ex.submit(retry_call, flaky_completion, i, attempts=4, base_delay=0.02): i
                   for i in range(40)}
        for fut in as_completed(futures):
            item = futures[fut]
            try:
                ok[item] = fut.result()
            except Exception as exc:                   # kept, not swallowed
                failed[item] = exc
    histogram = Counter(_attempts.values())
    print(f"ok={len(ok)} failed={len(failed)} total calls={sum(_attempts.values())}")
    print("attempts per item:", dict(sorted(histogram.items())))
    for item, exc in sorted(failed.items())[:2]:
        print(f"  item {item}: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
'''


@recipe("progress", "as_completed with ok/failed counts, rate and ETA; tqdm when installed")
def _progress():
    return r'''"""Progress reporting for a ThreadPoolExecutor job: as_completed + counts, optional tqdm.

Generated by executor_tool.py scaffold --recipe progress.

``run_with_progress`` submits the items, consumes futures with ``as_completed`` (so
progress moves as soon as any task finishes), keeps every result and every exception,
and reports done/ok/failed, rate and ETA. It uses tqdm when it is installed and falls
back to a log line every ``report_every`` percent, so it works in CI logs too.

Offline demo (about 1 s):  python progress.py
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

try:                                    # optional dependency
    from tqdm import tqdm as _tqdm
except ImportError:                     # pragma: no cover - depends on the environment
    _tqdm = None


def run_with_progress(
    fn: Callable[[Any], Any],
    items: Sequence[Any],
    *,
    max_workers: int = 8,
    desc: str = "tasks",
    report_every: int = 25,
    use_tqdm: Optional[bool] = None,
) -> Tuple[Dict[int, Any], Dict[int, BaseException]]:
    """Run ``fn`` over ``items``; return ``(results, errors)`` keyed by item index."""
    results: Dict[int, Any] = {}
    errors: Dict[int, BaseException] = {}
    total = len(items)
    bar = _tqdm(total=total, desc=desc, unit="task") if (use_tqdm is not False and _tqdm) else None
    started = time.monotonic()
    next_report = report_every
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=desc) as ex:
        futures = {ex.submit(fn, item): i for i, item in enumerate(items)}
        for done, fut in enumerate(as_completed(futures), start=1):
            index = futures[fut]
            try:
                results[index] = fut.result()
            except Exception as exc:
                errors[index] = exc
            if bar is not None:
                bar.update(1)
                bar.set_postfix(ok=len(results), failed=len(errors))
            elif done * 100 >= next_report * total or done == total:
                elapsed = time.monotonic() - started
                rate = done / elapsed if elapsed > 0 else 0.0
                eta = (total - done) / rate if rate > 0 else 0.0
                print(f"[{desc}] {done}/{total} ({done * 100 // total}%) ok={len(results)} "
                      f"failed={len(errors)} {rate:.0f}/s eta {eta:.1f}s", flush=True)
                while next_report * total <= done * 100:
                    next_report += report_every
    if bar is not None:
        bar.close()
    return results, errors


# ---------------------------------------------------------------- offline demo

def score_answer(i: int) -> float:
    """Stub grader call (~10 ms); every 17th item fails like a malformed model response."""
    time.sleep(0.01)
    if i % 17 == 16:
        raise ValueError(f"item {i}: could not parse JSON from model output")
    return (i % 10) / 10


def main() -> None:
    results, errors = run_with_progress(score_answer, list(range(100)), max_workers=8, desc="grade")
    mean = sum(results.values()) / max(1, len(results))
    print(f"done: {len(results)} scored (mean {mean:.3f}), {len(errors)} failed")
    for index, exc in sorted(errors.items()):
        print(f"  {index}: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
'''


@recipe("thread-local-client", "one requests.Session per worker thread via threading.local + initializer")
def _thread_local_client():
    return r'''"""One HTTP session per worker thread (threading.local + executor initializer).

Generated by executor_tool.py scaffold --recipe thread-local-client.

requests documents no thread-safety guarantee for ``Session`` (its cookie jar,
adapters and redirect handling mutate per request), so sharing one Session between
pool threads is a latent bug. Give each worker thread its own Session, created by the
executor ``initializer`` and reused for every task that thread runs (connection reuse
is kept), and close them all at the end. httpx.Client is documented as thread-safe
and can be shared instead.

Offline demo (stub:// URLs, no network, about 0.2 s):  python thread_local_client.py
Works without requests installed (a stub session is used).
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Tuple

try:
    import requests
    from requests.adapters import HTTPAdapter
except ImportError:                       # offline / minimal environments
    requests = None
    HTTPAdapter = None

_local = threading.local()
_sessions_lock = threading.Lock()
_sessions: List[Any] = []


class _StubSession:
    """Used when requests is not installed; supports only what the demo needs."""

    def get(self, url: str, timeout: Any = None) -> Any:
        raise RuntimeError("requests is not installed")

    def close(self) -> None:
        pass


def _new_session() -> Any:
    if requests is not None:
        session = requests.Session()
        session.headers["User-Agent"] = "corpus-fetcher/1.0"
        adapter = HTTPAdapter(pool_connections=4, pool_maxsize=4, max_retries=0)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
    else:
        session = _StubSession()
    with _sessions_lock:
        _sessions.append(session)          # remembered so close_all() can close it
    return session


def get_session() -> Any:
    """Return this thread's Session, creating it on first use."""
    session = getattr(_local, "session", None)
    if session is None:
        session = _local.session = _new_session()
    return session


def init_worker() -> None:
    """Executor initializer: runs once in each worker thread before any task."""
    get_session()


def close_all() -> None:
    with _sessions_lock:
        for session in _sessions:
            session.close()
        _sessions.clear()


def fetch(url: str) -> Tuple[str, int, str]:
    """Fetch one URL with this thread's session. ``stub://`` URLs never touch the network."""
    session = get_session()
    if url.startswith("stub://"):
        time.sleep(0.01)
        return url, 200, threading.current_thread().name
    resp = session.get(url, timeout=(3.05, 30))       # (connect, read) timeouts: always set them
    return url, resp.status_code, threading.current_thread().name


def main() -> None:
    urls = [f"stub://corpus.example/page/{i}" for i in range(60)]
    try:
        with ThreadPoolExecutor(max_workers=6, thread_name_prefix="fetch", initializer=init_worker) as ex:
            rows = list(ex.map(fetch, urls))
        threads = {name for _, _, name in rows}
        ok = sum(1 for _, status, _ in rows if status == 200)
        with _sessions_lock:
            n_sessions = len(_sessions)
        print(f"{ok}/{len(urls)} fetched by {len(threads)} threads using {n_sessions} sessions "
              f"(one per thread; requests installed: {requests is not None})")
    finally:
        close_all()


if __name__ == "__main__":
    main()
'''


@recipe("graceful-shutdown", "Ctrl-C: stop event + shutdown(cancel_futures=True) + partial results report")
def _graceful_shutdown():
    return r'''"""Ctrl-C-safe ThreadPoolExecutor job: stop event, cancel_futures and a partial-results report.

Generated by executor_tool.py scaffold --recipe graceful-shutdown.

Threads cannot be killed, and ``shutdown(wait=False)`` alone lets every queued task
run anyway. The pattern:
  1. wait for futures with a timeout so the main thread notices KeyboardInterrupt fast;
  2. on Ctrl-C set a ``threading.Event`` that long tasks check between steps;
  3. ``shutdown(wait=True, cancel_futures=True)`` (3.9+) drops queued tasks and waits
     only for the ones already running;
  4. report what finished, what stopped mid-way and what never started; exit 130.

Offline demo: python graceful_shutdown.py                 # simulates Ctrl-C after 0.5 s
              python graceful_shutdown.py --no-interrupt  # runs to completion (~2.5 s)
"""

from __future__ import annotations

import _thread
import argparse
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, CancelledError, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Dict, List, Optional


class Stopped(Exception):
    """Raised inside a task that noticed the stop event."""


@dataclass
class Report:
    uploaded: List[int] = field(default_factory=list)
    stopped: List[int] = field(default_factory=list)
    failed: Dict[int, BaseException] = field(default_factory=dict)
    cancelled: int = 0


def upload_chunk(chunk_id: int, stop: threading.Event) -> int:
    """Stub multipart upload: 5 parts of 20 ms; checks the stop event between parts."""
    for _part in range(5):
        if stop.is_set():
            raise Stopped(f"chunk {chunk_id} stopped")
        time.sleep(0.02)
    return chunk_id


def collect(fut: Future, chunk_id: int, report: Report) -> None:
    try:
        report.uploaded.append(fut.result())
    except CancelledError:
        report.cancelled += 1
    except Stopped:
        report.stopped.append(chunk_id)
    except Exception as exc:
        report.failed[chunk_id] = exc


def run(chunks: List[int], stop: threading.Event, report: Report, max_workers: int = 8) -> None:
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="upload") as ex:
        futures = {ex.submit(upload_chunk, c, stop): c for c in chunks}
        pending = set(futures)
        try:
            while pending:
                # a timeout keeps the main thread responsive to Ctrl-C on every platform
                done, pending = wait(pending, timeout=0.25, return_when=FIRST_COMPLETED)
                for fut in done:
                    collect(fut, futures[fut], report)
        except KeyboardInterrupt:
            stop.set()                                    # running tasks stop at their next check
            ex.shutdown(wait=True, cancel_futures=True)   # queued tasks are cancelled, not run
            for fut in pending:
                collect(fut, futures[fut], report)
            raise


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-interrupt", action="store_true", help="do not simulate Ctrl-C")
    ap.add_argument("--interrupt-after", type=float, default=0.5, help="seconds before simulated Ctrl-C")
    args = ap.parse_args(argv)

    stop = threading.Event()
    report = Report()
    chunks = list(range(200))
    timer: Optional[threading.Timer] = None
    if not args.no_interrupt:
        timer = threading.Timer(args.interrupt_after, _thread.interrupt_main)   # demo only
        timer.start()
    started = time.monotonic()
    try:
        run(chunks, stop, report)
    except KeyboardInterrupt:
        print(f"interrupted after {time.monotonic() - started:.2f} s: {len(report.uploaded)} uploaded, "
              f"{len(report.stopped)} stopped mid-task, {report.cancelled} cancelled before starting, "
              f"{len(report.failed)} failed")
        return 130
    finally:
        if timer is not None:
            timer.cancel()
            timer.join()
    print(f"all {len(report.uploaded)} chunks uploaded in {time.monotonic() - started:.2f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


@recipe("context-propagation", "contextvars (request id / trace) propagated into worker threads + log filter")
def _context_propagation():
    return r'''"""Propagate contextvars (request ids, trace spans, tenant) into ThreadPoolExecutor tasks.

Generated by executor_tool.py scaffold --recipe context-propagation.

Worker threads run tasks in their own context, so a ContextVar set by the caller
(request id, OpenTelemetry span, tenant) is invisible there: ``.get()`` returns the
default. ``asyncio.to_thread`` copies the context for you; ``executor.submit``,
``executor.map``, ``loop.run_in_executor`` and ``threading.Thread`` do not.
``ContextThreadPoolExecutor`` runs every task in a copy of the submitter's context
(``map`` goes through ``submit``, so it is covered too), and ``RequestIdFilter`` puts
the id on every log record.

Offline demo (about 0.1 s):  python context_propagation.py
"""

from __future__ import annotations

import contextvars
import logging
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, List

request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class ContextThreadPoolExecutor(ThreadPoolExecutor):
    """ThreadPoolExecutor that runs each task in a copy of the caller's contextvars context."""

    def submit(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Future:
        ctx = contextvars.copy_context()          # one copy per task: tasks cannot leak values
        return super().submit(ctx.run, fn, *args, **kwargs)


class RequestIdFilter(logging.Filter):
    """Adds ``record.request_id`` so formats can use %(request_id)s."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id.get()
        return True


log = logging.getLogger("rag")


def summarize(doc: str) -> str:
    """Stub LLM call that logs with the caller's request id."""
    time.sleep(0.005)
    log.info("summarized %s", doc)
    return f"{doc}:{request_id.get()}"


def handle_request(rid: str, docs: List[str], plain: ThreadPoolExecutor,
                   ctx_pool: ContextThreadPoolExecutor) -> None:
    token = request_id.set(rid)
    try:
        naive = [plain.submit(summarize, d) for d in docs]   # noqa: TPE019 - deliberately wrong, for contrast
        good = list(ctx_pool.map(summarize, docs))
        print(f"{rid}: plain submit saw {[f.result(timeout=5).split(':')[1] for f in naive]}, "
              f"context executor saw {[g.split(':')[1] for g in good]}")
    finally:
        request_id.reset(token)


def main() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(logging.Formatter("%(threadName)-10s [%(request_id)s] %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="plain") as plain, \
            ContextThreadPoolExecutor(max_workers=2, thread_name_prefix="ctx") as ctx_pool:
        handle_request("req-1", ["a.pdf", "b.pdf"], plain, ctx_pool)
        handle_request("req-2", ["c.pdf"], plain, ctx_pool)


if __name__ == "__main__":
    main()
'''


@recipe("llm-eval-harness", "eval harness: sliding window + RPM bucket + retries + results/errors + Ctrl-C")
def _llm_eval_harness():
    return r'''"""Sync LLM eval harness: thousands of prompts through a thread pool, within an RPM limit.

Generated by executor_tool.py scaffold --recipe llm-eval-harness.

Combines the production pieces:
  * sliding window of futures (bounded memory over a lazy prompt source),
  * a thread-safe token bucket for the provider's requests-per-minute limit,
  * retries with exponential backoff + full jitter for 429/5xx/timeouts only,
  * per-item results AND errors collected (nothing silently dropped),
  * Ctrl-C: stop event + cancel queued work + write what finished.
``call_model`` is an offline stub; replace it with your client call (a thread-safe
client such as openai.OpenAI / anthropic.Anthropic / httpx.Client can be shared).

Offline demo (about 3 s):  python llm_eval_harness.py --n 300 --rpm 6000 --workers 16
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import statistics
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass
from typing import Dict, Iterator, List, Optional, Tuple, Type


# ---------------------------------------------------------------- stub client

class RateLimitError(Exception):
    def __init__(self, message: str, retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class BadRequestError(Exception):
    """Permanent: never retried."""


_attempt_lock = threading.Lock()
_attempts: Dict[str, int] = {}


def call_model(prompt: str) -> str:
    """Offline stand-in for a chat completion: 10-40 ms latency, deterministic failures."""
    with _attempt_lock:
        _attempts[prompt] = _attempts.get(prompt, 0) + 1
        attempt = _attempts[prompt]
    item = int(prompt.split("#")[1].split(":")[0])
    time.sleep(random.Random(prompt).uniform(0.01, 0.04))
    if item % 23 == 0:
        raise BadRequestError(f"prompt #{item} exceeds the context window")
    if item % 7 == 0 and attempt == 1:
        raise RateLimitError("429 Too Many Requests", retry_after=0.05)
    return str(item % 10) if item % 11 else "?"


RETRYABLE: Tuple[Type[BaseException], ...] = (RateLimitError, TimeoutError, ConnectionError)


# ---------------------------------------------------------------- rate limit + retry

class TokenBucket:
    """Thread-safe token bucket: ``rate_per_minute`` sustained, ``burst`` back to back."""

    def __init__(self, rate_per_minute: float, burst: int) -> None:
        self.rate = rate_per_minute / 60.0
        self.capacity = float(burst)
        self._tokens = float(burst)
        self._updated = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, stop: threading.Event) -> bool:
        while True:
            with self._lock:
                now = time.monotonic()
                self._tokens = min(self.capacity, self._tokens + (now - self._updated) * self.rate)
                self._updated = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return True
                wait_s = (1 - self._tokens) / self.rate
            if stop.wait(wait_s):
                return False


@dataclass
class Result:
    index: int
    prompt: str
    expected: str
    output: Optional[str] = None
    error: Optional[str] = None
    attempts: int = 0
    latency_s: float = 0.0

    @property
    def correct(self) -> bool:
        return self.output == self.expected


def evaluate_one(index: int, prompt: str, expected: str, bucket: TokenBucket, stop: threading.Event,
                 attempts: int = 4, base_delay: float = 0.05) -> Result:
    """One prompt: rate-limited call with retries. Errors are returned in the Result, not raised."""
    result = Result(index, prompt, expected)
    started = time.monotonic()
    for attempt in range(1, attempts + 1):
        result.attempts = attempt
        if not bucket.acquire(stop):
            result.error = "stopped"
            break
        try:
            result.output = call_model(prompt)
            break
        except RETRYABLE as exc:
            if attempt == attempts:
                result.error = f"{type(exc).__name__}: {exc}"
                break
            delay = random.uniform(0, base_delay * 2 ** (attempt - 1))
            delay = max(delay, getattr(exc, "retry_after", None) or 0.0)
            if stop.wait(delay):
                result.error = "stopped"
                break
        except Exception as exc:                    # permanent: record and move on
            result.error = f"{type(exc).__name__}: {exc}"
            break
    result.latency_s = time.monotonic() - started
    return result


# ---------------------------------------------------------------- harness

def load_dataset(n: int) -> Iterator[Tuple[str, str]]:
    """Lazy (prompt, expected) pairs; replace with a JSONL reader."""
    for i in range(n):
        yield f"question #{i}: what is {i} mod 10?", str(i % 10)


def run_eval(dataset: Iterator[Tuple[str, str]], *, workers: int, rpm: float, max_in_flight: int,
             stop: threading.Event) -> List[Result]:
    bucket = TokenBucket(rpm, burst=max(1, workers))
    results: List[Result] = []
    pending: Dict[Future, int] = {}
    source = enumerate(dataset)
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="eval") as ex:
        try:
            for index, (prompt, expected) in itertools.islice(source, max_in_flight):
                pending[ex.submit(evaluate_one, index, prompt, expected, bucket, stop)] = index
            while pending:
                done, _ = wait(pending, timeout=0.5, return_when=FIRST_COMPLETED)
                for fut in done:
                    pending.pop(fut)
                    results.append(fut.result())    # evaluate_one never raises; a bug here should surface
                    if len(results) % 100 == 0:
                        print(f"  {len(results)} done", flush=True)
                for index, (prompt, expected) in itertools.islice(source, len(done)):
                    pending[ex.submit(evaluate_one, index, prompt, expected, bucket, stop)] = index
        except KeyboardInterrupt:
            stop.set()
            ex.shutdown(wait=True, cancel_futures=True)
            for fut in pending:
                if fut.done() and not fut.cancelled():
                    results.append(fut.result())
            print(f"interrupted: keeping {len(results)} finished results", file=sys.stderr)
    return sorted(results, key=lambda r: r.index)


def summarize(results: List[Result], elapsed: float) -> str:
    ok = [r for r in results if r.error is None]
    stopped = [r for r in results if r.error == "stopped"]
    failed = [r for r in results if r.error is not None and r.error != "stopped"]
    latencies = sorted(r.latency_s for r in ok) or [0.0]
    p95 = latencies[min(len(latencies) - 1, int(0.95 * len(latencies)))]
    retried = sum(1 for r in results if r.attempts > 1)
    accuracy = sum(r.correct for r in ok) / max(1, len(ok))
    lines = [
        f"evaluated {len(results)} prompts in {elapsed:.2f} s ({len(results) / max(elapsed, 1e-9):.0f}/s)",
        f"ok={len(ok)} failed={len(failed)} stopped={len(stopped)} retried={retried} accuracy={accuracy:.3f}",
        f"latency incl. rate-limit wait: p50={statistics.median(latencies) * 1000:.0f} ms "
        f"p95={p95 * 1000:.0f} ms",
    ]
    for r in failed[:3]:
        lines.append(f"  #{r.index}: {r.error}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="offline LLM eval harness demo")
    ap.add_argument("--n", type=int, default=300, help="number of prompts")
    ap.add_argument("--workers", type=int, default=16, help="worker threads")
    ap.add_argument("--rpm", type=float, default=6000, help="requests per minute limit")
    ap.add_argument("--max-in-flight", type=int, default=32, help="sliding window size")
    ap.add_argument("--out", help="write results as JSONL here")
    args = ap.parse_args(argv)
    stop = threading.Event()
    started = time.monotonic()
    results = run_eval(load_dataset(args.n), workers=args.workers, rpm=args.rpm,
                       max_in_flight=args.max_in_flight, stop=stop)
    print(summarize(results, time.monotonic() - started))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            for r in results:
                fh.write(json.dumps(asdict(r)) + "\n")
    return 130 if stop.is_set() else 0


if __name__ == "__main__":
    sys.exit(main())
'''


def cmd_scaffold(args):
    if args.list:
        if args.json:
            print(json.dumps({k: v[0] for k, v in RECIPES.items()}, indent=2))
        else:
            for name, (summary, _) in RECIPES.items():
                print(f"{name:22} {summary}")
        return 0
    if not args.recipe:
        print("error: scaffold needs --recipe NAME (see --list)", file=sys.stderr)
        return 2
    if args.recipe not in RECIPES:
        print(f"error: unknown recipe {args.recipe!r}; choose from: {', '.join(RECIPES)}", file=sys.stderr)
        return 2
    code = RECIPES[args.recipe][1]()
    try:
        ast.parse(code, feature_version=(3, 9))
    except SyntaxError as err:
        print(f"error: generated code does not parse (line {err.lineno}): {err.msg}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"recipe": args.recipe, "summary": RECIPES[args.recipe][0], "code": code,
                          "verified": "ast.parse(feature_version=(3, 9))"}, indent=2))
    else:
        sys.stdout.write(code)
    return 0


# ====================================================================== CLI

def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", metavar="{check,scaffold}")
    c = sub.add_parser("check", help="lint ThreadPoolExecutor / threading code (AST only, never executed)")
    c.add_argument("paths", nargs="*", help="Python files or directories, or - for stdin")
    c.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    c.add_argument("--strict", action="store_true", help="exit 1 if any finding is reported")
    c.add_argument("--select", action="append", metavar="IDS",
                   help="only these rules (ids, id prefixes or names; comma list)")
    c.add_argument("--ignore", action="append", metavar="IDS",
                   help="skip these rules (ids, id prefixes or names; comma list)")
    c.add_argument("--min-severity", choices=["low", "medium", "high"], default="low",
                   help="hide findings below this severity (default: low)")
    c.add_argument("--list-rules", action="store_true", help="print every rule with why and fix, then exit")
    s = sub.add_parser("scaffold", help="print a runnable thread-pool recipe (verified with ast.parse, not run)")
    s.add_argument("--recipe", metavar="NAME", help="recipe to print: " + ", ".join(RECIPES))
    s.add_argument("--list", action="store_true", help="list recipes and exit")
    s.add_argument("--json", action="store_true", help="emit {recipe, summary, code} as JSON")
    return ap, c, s


def main(argv=None):
    ap, c, s = build_parser()
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    if args.cmd == "check":
        return cmd_check(args, c)
    if args.cmd == "scaffold":
        return cmd_scaffold(args)
    ap.print_usage(sys.stderr)
    print("error: choose a subcommand: check or scaffold", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
