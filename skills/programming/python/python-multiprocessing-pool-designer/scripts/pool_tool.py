#!/usr/bin/env python3
"""Design and check process-based parallelism: a multiprocessing linter and a capacity planner.

Subcommands
-----------
check FILES...   Static AST linter for multiprocessing / ProcessPoolExecutor code.
                 The analysed code is parsed with `ast`, never imported or executed.
plan ...         Deterministic capacity planner: workers, chunksize, wall time vs
                 serial, IPC share, memory, warnings. Nothing is executed; the only
                 environment reads are CPU count / cgroup limits / meminfo when
                 --cores or --mem-limit-mb are not given.

Rules for `check` (run `check --list-rules` for the why and a fix snippet of each):

  MP001 pool-without-main-guard     Pool/executor/Process.start at import time (no __main__ guard)
  MP002 unpicklable-callable        lambda / nested function / bound method / partial(lambda) sent to workers
  MP003 pool-not-closed             Pool not closed+joined (or terminated); executor never shut down
  MP004 async-result-after-with     AsyncResult/imap read after `with Pool()` exits (terminate() killed it)
  MP005 missing-chunksize           imap/imap_unordered/executor.map over a non-literal iterable, chunksize=1
  MP006 lost-async-exception        apply_async/map_async result dropped and no error_callback; submit() dropped
  MP007 set-start-method-misuse     set_start_method at import time outside the guard, or called twice
  MP008 fork-with-gpu-framework     explicit fork start method in a module importing torch/tf/jax/cupy
  MP009 global-mutation-in-worker   worker mutates a module global the parent reads (child copy only)
  MP010 large-per-task-arg          big object (file read, dataset, model, huge literal) pickled per task
  MP011 manager-proxy-in-loop       Manager().dict()/list() proxy touched inside a loop (one IPC per access)
  MP012 join-before-drain           Process.join() before the multiprocessing.Queue it feeds is drained
  MP013 model-worker-no-recycle     workers load a model but no maxtasksperchild / max_tasks_per_child
  MP014 mp-queue-passed-to-pool     multiprocessing.Queue passed as a task argument (RuntimeError)
  MP015 os-fork                     os.fork() / os.forkpty() used directly
  MP016 keyboardinterrupt-unhandled pool map in a main() function with no Ctrl-C handling
  MP017 threads-before-fork         threads started before processes are forked
  MP018 nested-pool-in-worker       Pool worker creates a Pool/executor/Process (daemonic children)
  MP019 serialized-submit           apply_async(...).get() / submit(...).result() / apply() inside a loop
  MP020 pool-in-loop                Pool/executor created inside a loop
  MP021 thread-oversubscription     torch + process pool without set_num_threads(1) / OMP_NUM_THREADS

Suppress a finding on its line with `# noqa` or `# noqa: MP001,MP005`.

Usage:
    python pool_tool.py check src/ingest/ --strict
    python pool_tool.py check worker.py --json --select MP001,MP002 --ignore missing-chunksize
    cat job.py | python pool_tool.py check -
    python pool_tool.py check --list-rules
    python pool_tool.py plan --items 200000 --item-ms 4 --payload-kb 8 --result-kb 2 --cores 8
    python pool_tool.py plan --items 5000 --item-ms 120 --init-s 6 --mem-per-worker-mb 1800 \
        --mem-limit-mb 8192 --start-method spawn --json

Exit codes: 0 ok (or findings without --strict), 1 findings with --strict or a
failed --min-speedup gate, 2 usage error, or a file named on the command line
that cannot be read or parsed (directory walks warn and skip such files).

No dependencies (standard library only, Python 3.9+).
"""

import argparse
import ast
import json
import math
import os
import re
import sys

# ====================================================================== rules

RULES = {
    "MP001": {
        "name": "pool-without-main-guard", "severity": "high",
        "summary": "Pool / ProcessPoolExecutor / Process.start() at module level without `if __name__ == \"__main__\":`",
        "why": "spawn (macOS, Windows) and forkserver (Linux default since 3.14) re-import the main module in every "
               "child. Pool creation at import time then runs again in each child: RuntimeError 'An attempt has "
               "been made to start a new process before the current process has finished its bootstrapping phase', "
               "or a fork bomb of pools.",
        "fix": "def main() -> None:\n"
               "    with ProcessPoolExecutor(max_workers=8) as ex:\n"
               "        chunks = list(ex.map(parse_pdf, paths, chunksize=16))\n\n"
               "if __name__ == \"__main__\":\n"
               "    main()",
    },
    "MP002": {
        "name": "unpicklable-callable", "severity": "high",
        "summary": "lambda, nested function, bound method or partial(lambda) passed to a process pool",
        "why": "Tasks are pickled by reference (module + qualified name). Lambdas and nested functions cannot be "
               "found by name in the child: 'PicklingError: Can't pickle <function <lambda>>' / 'Can't get local "
               "object'. Bound methods pickle the whole instance with every task (slow, and fails if it holds a "
               "pool, lock, client or open file).",
        "fix": "def clean_doc(doc: str, *, lower: bool) -> str:      # module level\n"
               "    return normalize(doc, lower=lower)\n\n"
               "results = pool.map(functools.partial(clean_doc, lower=True), docs, chunksize=64)\n"
               "# need closures/lambdas? joblib (loky) uses cloudpickle: Parallel(n_jobs=8)(delayed(f)(x) for x in xs)",
    },
    "MP003": {
        "name": "pool-not-closed", "severity": "medium",
        "summary": "Pool never closed+joined (or terminated), or executor never shut down",
        "why": "Leaked pools keep worker processes, pipes and handler threads alive; in services each request leaks "
               "N processes until the box runs out of memory or PIDs. Relying on the GC/finalizer prints "
               "ResourceWarning (3.8+) and can hang at interpreter exit.",
        "fix": "with Pool(processes=8) as pool:            # __exit__ calls terminate()\n"
               "    out = pool.map(tokenize, shards)       # finish all work INSIDE the block\n"
               "# long-lived pool: pool.close(); pool.join() in finally / shutdown hook\n"
               "# executor: with ProcessPoolExecutor() as ex: ...   or   ex.shutdown(wait=True, cancel_futures=True)",
    },
    "MP004": {
        "name": "async-result-after-with", "severity": "high",
        "summary": "AsyncResult / imap iterator from a `with Pool()` block used after the block exits",
        "why": "Pool.__exit__ calls terminate(), not close()+join(): outstanding apply_async/map_async/imap work is "
               "killed. Reading the result afterwards raises or blocks until timeout (the classic 'hangs at "
               "r.get()' bug). ProcessPoolExecutor's __exit__ waits, Pool's does not.",
        "fix": "with Pool(8) as pool:\n"
               "    pending = [pool.apply_async(embed_cpu, (b,)) for b in batches]\n"
               "    vectors = [r.get(timeout=600) for r in pending]   # collect INSIDE the with block\n"
               "# or: pool.close(); pool.join() before leaving the block",
    },
    "MP005": {
        "name": "missing-chunksize", "severity": "medium",
        "summary": "imap / imap_unordered / ProcessPoolExecutor.map over a non-literal iterable with default chunksize=1",
        "why": "chunksize=1 sends one pickle message per item: for millisecond tasks the parent's IPC and the "
               "queue locks dominate and 16 workers run slower than 1. Pool.map/starmap pick a chunksize "
               "automatically; imap*, and ProcessPoolExecutor.map do not.",
        "fix": "chunksize = max(1, n_items // (workers * 4))   # or: pool_tool.py plan --items N --item-ms X\n"
               "for tokens in pool.imap(tokenize, lines, chunksize=chunksize):\n"
               "    sink.write(tokens)",
    },
    "MP006": {
        "name": "lost-async-exception", "severity": "high",
        "summary": "apply_async/map_async result discarded with no error_callback, or executor.submit() future dropped",
        "why": "Exceptions in the worker are stored on the AsyncResult/Future and only raised by get()/result(). "
               "Nobody calls it, so failed documents disappear silently and the job reports success.",
        "fix": "def on_error(exc: BaseException) -> None:\n"
               "    log.error(\"chunk failed\", exc_info=exc)\n\n"
               "pending = [pool.apply_async(parse, (p,), error_callback=on_error) for p in paths]\n"
               "results = [r.get(timeout=300) for r in pending]   # get() re-raises worker errors",
    },
    "MP007": {
        "name": "set-start-method-misuse", "severity": "medium",
        "summary": "set_start_method() at import time outside the main guard, or called more than once",
        "why": "set_start_method may be called once per program: a second call (or the module being imported by a "
               "spawned child) raises 'RuntimeError: context has already been set'. Libraries must never set the "
               "global start method; they should use get_context().",
        "fix": "ctx = multiprocessing.get_context(\"spawn\")          # local, composable, no global state\n"
               "with ctx.Pool(8) as pool: ...\n"
               "# or ProcessPoolExecutor(mp_context=ctx)\n"
               "# application entry point only:\n"
               "if __name__ == \"__main__\":\n"
               "    multiprocessing.set_start_method(\"forkserver\")\n"
               "    main()",
    },
    "MP008": {
        "name": "fork-with-gpu-framework", "severity": "high",
        "summary": "fork start method / os.fork in a module that imports torch, tensorflow, jax, cupy or vllm",
        "why": "CUDA cannot be re-initialised in a forked child: 'RuntimeError: Cannot re-initialize CUDA in "
               "forked subprocess'. Framework thread pools and locks are also copied mid-use, causing hangs.",
        "fix": "ctx = multiprocessing.get_context(\"spawn\")   # or torch.multiprocessing.get_context(\"spawn\")\n"
               "with ProcessPoolExecutor(max_workers=2, mp_context=ctx, initializer=load_model) as ex: ...\n"
               "# do not touch torch.cuda in the parent before starting workers",
    },
    "MP009": {
        "name": "global-mutation-in-worker", "severity": "high",
        "summary": "worker function mutates a module-level global that the parent reads",
        "why": "Each worker mutates its own copy of the module globals (fork copies memory, spawn re-imports). The "
               "parent's list/dict/counter stays empty - a silent wrong answer.",
        "fix": "def count_tokens(doc: str) -> collections.Counter:\n"
               "    return collections.Counter(tokenize(doc))     # return the data\n\n"
               "total = collections.Counter()\n"
               "for part in pool.imap_unordered(count_tokens, docs, chunksize=256):\n"
               "    total.update(part)                            # merge in the parent",
    },
    "MP010": {
        "name": "large-per-task-arg", "severity": "medium",
        "summary": "large object (file contents, dataset, model, huge literal) pickled into every task",
        "why": "partial(f, big), starmap over [(big, x)...] and submit(f, big, x) in a loop pickle `big` once per "
               "task/chunk: the parent spends its time pickling, IPC dominates and memory spikes N-fold.",
        "fix": "def init_worker(path: str) -> None:\n"
               "    global _vocab\n"
               "    _vocab = load_vocab(path)            # once per worker\n\n"
               "with Pool(8, initializer=init_worker, initargs=(vocab_path,)) as pool:\n"
               "    out = pool.map(encode, texts, chunksize=128)\n"
               "# numpy arrays: multiprocessing.shared_memory; files: pass the path, not the bytes",
    },
    "MP011": {
        "name": "manager-proxy-in-loop", "severity": "low",
        "summary": "Manager().dict()/list() proxy read or written inside a loop",
        "why": "Every proxy operation is a round trip to the manager process (~50-100 us). A per-token counter "
               "update turns a CPU-bound job into an IPC-bound one, and `d[k] += 1` on a proxy is not atomic.",
        "fix": "def count(docs: list[str]) -> Counter:\n"
               "    local = Counter()\n"
               "    for d in docs:\n"
               "        local.update(tokenize(d))       # plain dict inside the worker\n"
               "    return local                       # merge once in the parent",
    },
    "MP012": {
        "name": "join-before-drain", "severity": "high",
        "summary": "Process.join() before the multiprocessing.Queue it writes to is drained",
        "why": "A child that put() data waits at exit for its feeder thread to flush the pipe. If the parent joins "
               "before reading, the pipe buffer (~64 KiB) fills and both wait forever - documented 'joining "
               "processes that use queues' deadlock.",
        "fix": "for p in procs:\n"
               "    p.start()\n"
               "results = [q.get(timeout=600) for _ in range(n_items)]   # drain first\n"
               "for p in procs:\n"
               "    p.join()",
    },
    "MP013": {
        "name": "model-worker-no-recycle", "severity": "low",
        "summary": "workers load a model/tokenizer but the pool sets no maxtasksperchild / max_tasks_per_child",
        "why": "Long-lived inference workers grow (allocator fragmentation, caches, C-extension leaks) until the "
               "OOM killer takes one and the pool breaks. Recycling after a generous number of tasks caps RSS "
               "(trade-off: each recycle reloads the model).",
        "fix": "Pool(4, initializer=load_model, maxtasksperchild=2000)\n"
               "ProcessPoolExecutor(4, initializer=load_model, max_tasks_per_child=2000,   # 3.11+\n"
               "                    mp_context=multiprocessing.get_context(\"spawn\"))   # not with fork",
    },
    "MP014": {
        "name": "mp-queue-passed-to-pool", "severity": "high",
        "summary": "multiprocessing.Queue passed as a task argument to a Pool or ProcessPoolExecutor",
        "why": "multiprocessing.Queue can only be shared by inheritance: pickling it into a task raises "
               "'RuntimeError: Queue objects should only be shared between processes through inheritance'.",
        "fix": "with multiprocessing.Manager() as mgr:\n"
               "    progress = mgr.Queue()                      # proxy: picklable\n"
               "    futs = [ex.submit(work, item, progress) for item in items]\n"
               "# or pass the Queue once via initializer/initargs and keep it in a worker global",
    },
    "MP015": {
        "name": "os-fork", "severity": "medium",
        "summary": "os.fork() / os.forkpty() called directly",
        "why": "Raw fork copies every lock in whatever state other threads left it (logging, malloc, SDK clients), "
               "skips multiprocessing's at-fork hooks and bookkeeping, and is unavailable on Windows. 3.12+ warns "
               "when the process has threads.",
        "fix": "ctx = multiprocessing.get_context(\"spawn\")\n"
               "p = ctx.Process(target=run_shard, args=(shard_id,))\n"
               "p.start(); p.join()\n"
               "# need a subprocess? subprocess.run([...], check=True)",
    },
    "MP016": {
        "name": "keyboardinterrupt-unhandled", "severity": "low",
        "summary": "pool map in a main() function with no KeyboardInterrupt / SIGINT handling",
        "why": "Ctrl-C reaches every worker: you get N tracebacks, the parent may block in map(), and workers can "
               "be left running. Ignore SIGINT in workers and terminate the pool once in the parent.",
        "fix": "def init_worker() -> None:\n"
               "    signal.signal(signal.SIGINT, signal.SIG_IGN)\n\n"
               "pool = Pool(8, initializer=init_worker)\n"
               "try:\n"
               "    for r in pool.imap_unordered(score, prompts, chunksize=32):\n"
               "        sink.write(r)\n"
               "    pool.close()\n"
               "except KeyboardInterrupt:\n"
               "    pool.terminate()\n"
               "    raise\n"
               "finally:\n"
               "    pool.join()",
    },
    "MP017": {
        "name": "threads-before-fork", "severity": "high",
        "summary": "threads started before processes are created with the fork start method",
        "why": "fork copies only the calling thread; locks held by other threads (logging, queues, HTTP clients, "
               "BLAS pools) stay locked forever in the child. 3.12+ emits DeprecationWarning. fork was the Linux "
               "default before 3.14.",
        "fix": "ctx = multiprocessing.get_context(\"forkserver\")   # or \"spawn\"\n"
               "with ctx.Pool(8) as pool: ...\n"
               "# or create the process pool before starting any threads",
    },
    "MP018": {
        "name": "nested-pool-in-worker", "severity": "high",
        "summary": "function run by a multiprocessing.Pool creates a Pool, executor or Process",
        "why": "Pool workers are daemonic: 'AssertionError: daemonic processes are not allowed to have children'. "
               "Even when allowed, nested pools oversubscribe the CPU (N x M processes).",
        "fix": "# flatten: one pool over all (doc, page) work items\n"
               "items = [(doc, page) for doc in docs for page in range(n_pages(doc))]\n"
               "with Pool(8) as pool:\n"
               "    pages = pool.starmap(parse_page, items, chunksize=32)",
    },
    "MP019": {
        "name": "serialized-submit", "severity": "medium",
        "summary": "apply_async(...).get(), submit(...).result() or Pool.apply() inside a loop",
        "why": "Waiting for each task before submitting the next runs everything one at a time on one worker, "
               "plus IPC overhead: slower than the plain loop.",
        "fix": "futures = [ex.submit(score, p) for p in prompts]          # submit all\n"
               "for fut in concurrent.futures.as_completed(futures):     # then collect\n"
               "    handle(fut.result())",
    },
    "MP020": {
        "name": "pool-in-loop", "severity": "medium",
        "summary": "Pool / ProcessPoolExecutor created inside a loop",
        "why": "Every iteration pays process start-up (and model loading in the initializer): 50-500 ms with "
               "spawn, seconds with heavy imports. Create the pool once and feed it all batches.",
        "fix": "with ProcessPoolExecutor(8, initializer=load_tokenizer) as ex:\n"
               "    for shard in shards:\n"
               "        write(shard, list(ex.map(tokenize, read(shard), chunksize=256)))",
    },
    "MP021": {
        "name": "thread-oversubscription", "severity": "low",
        "summary": "module imports torch and starts a process pool but never limits intra-op threads",
        "why": "Each worker's torch/BLAS/OpenMP pool starts one thread per core: 8 workers x 8 threads = 64 "
               "threads fighting for 8 cores, often slower than 1 worker. (Also applies to numpy/MKL.)",
        "fix": "def init_worker() -> None:\n"
               "    torch.set_num_threads(1)              # and/or OMP_NUM_THREADS=1 before imports\n"
               "    global _model\n"
               "    _model = load_model()\n\n"
               "ProcessPoolExecutor(8, initializer=init_worker)",
    },
}

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

MP_PREFIXES = ("multiprocessing", "multiprocessing.pool", "multiprocessing.context", "multiprocessing.dummy",
               "torch.multiprocessing", "multiprocess", "billiard")
POOL_TASK_METHODS = {"map", "imap", "imap_unordered", "starmap", "map_async", "starmap_async",
                     "apply", "apply_async"}
EXEC_TASK_METHODS = {"submit", "map"}
MAP_LIKE = {"map", "imap", "imap_unordered", "starmap", "map_async", "starmap_async"}
ASYNC_METHODS = {"apply_async", "map_async", "starmap_async"}
ITER_RESULT_METHODS = {"apply_async", "map_async", "starmap_async", "imap", "imap_unordered"}
PROC_KINDS = {"pool", "executor"}
BATCHED_HINTS = ("batch", "shard", "partition")
GPU_MODULES = ("torch", "tensorflow", "jax", "cupy", "keras", "vllm", "pycuda", "sentence_transformers",
               "transformers")
MUTATORS = {"append", "extend", "add", "update", "insert", "setdefault", "remove", "pop", "clear",
            "appendleft", "extendleft", "discard", "popitem"}
MUTABLE_CTORS = {"list", "dict", "set", "Counter", "defaultdict", "deque", "OrderedDict"}
HEAVY_ATTRS = {"read", "read_bytes", "read_text", "readlines", "load_dataset", "fromfile", "read_csv",
               "read_parquet", "read_json", "read_pickle", "read_feather", "read_table", "from_pretrained",
               "SentenceTransformer", "CrossEncoder"}
HEAVY_CALLS = {"json.load", "pickle.load", "numpy.load", "torch.load", "joblib.load", "np.load"}
MODEL_LOAD_ATTRS = {"from_pretrained", "SentenceTransformer", "CrossEncoder", "load_model", "InferenceSession",
                    "create_model_and_transforms"}
MODEL_LOAD_CALLS = {"torch.load", "joblib.load", "spacy.load", "transformers.pipeline", "fasttext.load_model",
                    "whisper.load_model", "tiktoken.get_encoding", "tiktoken.encoding_for_model"}
PROXY_METHODS = {"dict", "list", "Namespace", "Value", "Array"}
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
LOOPS = (ast.For, ast.AsyncFor, ast.While, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)


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


def names_in(node, ctx=None):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and (ctx is None or isinstance(n.ctx, ctx))}


def parent(node):
    return getattr(node, "_mp_parent", None)


def is_main_guard(node):
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    t = node.test
    if len(t.ops) != 1 or not isinstance(t.ops[0], ast.Eq):
        return False
    sides = [t.left, t.comparators[0]]
    has_name = any(isinstance(s, ast.Name) and s.id == "__name__" for s in sides)
    has_main = any(isinstance(s, ast.Constant) and s.value == "__main__" for s in sides)
    return has_name and has_main


def kwarg(call, name):
    for k in call.keywords:
        if k.arg == name:
            return k.value
    return None


def const_str(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def is_literal_iterable(node):
    if isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
        return True
    if isinstance(node, ast.Call) and dotted(node.func) == "range" and node.args:
        last = node.args[0] if len(node.args) == 1 else node.args[1]
        return isinstance(last, ast.Constant) and isinstance(last.value, int) and last.value <= 1000
    return False


def enclosing(node, types, stop=FUNCS + (ast.ClassDef, ast.Lambda, ast.Module)):
    """Nearest ancestor of one of `types`, not crossing a function/class boundary."""
    p = parent(node)
    while p is not None and not isinstance(p, stop):
        if isinstance(p, types):
            return p
        p = parent(p)
    return None


def in_loop(node):
    p, child = parent(node), node
    while p is not None and not isinstance(p, FUNCS + (ast.ClassDef, ast.Lambda, ast.Module)):
        if isinstance(p, (ast.For, ast.AsyncFor)) and child is not p.iter and child not in p.orelse:
            return True
        if isinstance(p, ast.While) and child is not p.test:
            return True
        if isinstance(p, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            return True
        p, child = parent(p), p
    return False


def stmt_lists(node):
    for field in ("body", "orelse", "finalbody"):
        v = getattr(node, field, None)
        if isinstance(v, list) and v and isinstance(v[0], ast.stmt):
            yield v
    for h in getattr(node, "handlers", []) or []:
        yield h.body
    for c in getattr(node, "cases", []) or []:
        yield c.body


def large_literal(node):
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)) and len(node.elts) >= 500:
        return True
    if isinstance(node, ast.Dict) and len(node.keys) >= 500:
        return True
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)) and len(node.value) >= 100_000:
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        for a, b in ((node.left, node.right), (node.right, node.left)):
            if isinstance(a, (ast.List, ast.Constant)) and isinstance(b, ast.Constant) \
                    and isinstance(b.value, int) and b.value >= 100_000:
                return True
    return False


class Scope:
    def __init__(self, func, stmts):
        self.func = func                  # FunctionDef or None for the module
        self.stmts = stmts
        self.nodes = sorted(walk_local(stmts), key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0)))
        self.bindings = {}                # dotted key -> kind
        self.assign_sites = {}            # dotted key -> (node, kind) for Assign-bound pools
        self.local_defs = {}              # nested def name -> node
        self.lambdas = set()              # names bound to lambdas
        self.heavy = set()                # names bound to large objects
        self.params = set()
        if func is not None:
            a = func.args
            for arg in a.posonlyargs + a.args + a.kwonlyargs:
                self.params.add(arg.arg)
            for arg in (a.vararg, a.kwarg):
                if arg:
                    self.params.add(arg.arg)


# ====================================================================== analyzer

class Analyzer:
    def __init__(self, path, source, tree):
        self.path = path
        self.lines = source.splitlines()
        self.source = source
        self.tree = tree
        self.findings = []
        self.seen = set()
        self.imports = {}
        self.module_defs = {}
        self.context_methods = {}     # dotted ctx name -> start method or None
        self.explicit_methods = []    # (method, node) from set_start_method / get_context
        self.module_scope = None
        self.scopes = []
        self.worker_funcs = {}        # name -> set(receiver kinds) for module defs sent to workers
        self.init_funcs = set()
        self.daemon_targets = set()

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

    def is_mp_receiver(self, func):
        """True if `func` (the callee of X.Pool / X.Queue ...) hangs off multiprocessing or a context."""
        if isinstance(func, ast.Name):
            full = self.resolve(func)
            return "." in full and full.rsplit(".", 1)[0] in MP_PREFIXES
        if not isinstance(func, ast.Attribute):
            return False
        recv = func.value
        if isinstance(recv, ast.Call) and self.resolve(recv.func).endswith("get_context"):
            return True
        key = dotted(recv)
        if key and key in self.context_methods:
            return True
        return self.resolve(recv) in MP_PREFIXES

    def ctor_kind(self, call):
        if not isinstance(call, ast.Call):
            return None
        func = call.func
        last = func.attr if isinstance(func, ast.Attribute) else (func.id if isinstance(func, ast.Name) else "")
        full = self.resolve(func)
        if full.endswith("ProcessPoolExecutor") or (last == "get_reusable_executor" and "loky" in full):
            return "executor"
        if full.endswith("InterpreterPoolExecutor"):
            return "interp"
        if full.endswith("ThreadPoolExecutor"):
            return "texecutor"
        if full in ("threading.Thread", "threading.Timer"):
            return "thread"
        if last in ("Pool", "ThreadPool", "Process", "Queue", "SimpleQueue", "JoinableQueue", "Manager") \
                and self.is_mp_receiver(func):
            if last == "Pool":
                return "threadpool" if full.startswith("multiprocessing.dummy") else "pool"
            return {"ThreadPool": "threadpool", "Process": "process", "Manager": "manager"}.get(last, "mpqueue")
        return None

    def ctx_method_of(self, call):
        """Start method implied by a constructor call, or None if unknown/default."""
        func = call.func
        if isinstance(func, ast.Attribute):
            recv = func.value
            if isinstance(recv, ast.Call) and self.resolve(recv.func).endswith("get_context"):
                return self.method_arg(recv)
            key = dotted(recv)
            if key in self.context_methods:
                return self.context_methods[key]
        mc = kwarg(call, "mp_context")
        if mc is not None:
            if isinstance(mc, ast.Call):
                return self.method_arg(mc)
            return self.context_methods.get(dotted(mc))
        if kwarg(call, "max_tasks_per_child") is not None and self.ctor_kind(call) == "executor":
            return "spawn"
        return None

    @staticmethod
    def method_arg(call):
        v = call.args[0] if call.args else kwarg(call, "method")
        return const_str(v) if v is not None else None

    # ------------------------------------------------------------ indexing
    def index(self):
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                child._mp_parent = node
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.asname:
                        self.imports[a.asname] = a.name
                    else:
                        head = a.name.split(".")[0]
                        self.imports[head] = head
            elif isinstance(node, ast.ImportFrom):
                mod = ("." * node.level) + (node.module or "")
                for a in node.names:
                    if a.name != "*":
                        self.imports[a.asname or a.name] = mod + "." + a.name
        for stmt in self.tree.body:
            if isinstance(stmt, FUNCS):
                self.module_defs[stmt.name] = stmt
        # contexts and explicit start methods
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            full = self.resolve(node.func)
            if full.endswith("get_context") and (full.split(".")[0] in ("multiprocessing", "torch", "multiprocess")
                                                 or full == "get_context"):
                m = self.method_arg(node)
                p = parent(node)
                if isinstance(p, ast.Assign) and len(p.targets) == 1 and dotted(p.targets[0]):
                    self.context_methods[dotted(p.targets[0])] = m
                if m:
                    self.explicit_methods.append((m, node))
            elif full.endswith("set_start_method"):
                m = self.method_arg(node)
                if m:
                    self.explicit_methods.append((m, node))
        self.module_scope = Scope(None, self.tree.body)
        self.scopes = [self.module_scope]
        for node in ast.walk(self.tree):
            if isinstance(node, FUNCS):
                self.scopes.append(Scope(node, node.body))
        for sc in self.scopes:
            self.bind(sc)
        for sc in self.scopes:
            self.index_workers(sc)

    def bind(self, sc):
        conflict = set()

        def put(key, kind, node=None):
            if not key or kind is None:
                return
            if key in sc.bindings and sc.bindings[key] != kind:
                conflict.add(key)
            sc.bindings[key] = kind
            if node is not None and kind in ("pool", "threadpool", "executor"):
                sc.assign_sites[key] = (node, kind)

        for n in sc.nodes:
            if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None:
                targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                if len(targets) != 1:
                    continue
                key = dotted(targets[0])
                v = n.value
                kind = self.ctor_kind(v)
                if kind:
                    put(key, kind, n)
                elif isinstance(v, (ast.ListComp, ast.List)):
                    elt = v.elt if isinstance(v, ast.ListComp) else (v.elts[0] if v.elts else None)
                    k2 = self.ctor_kind(elt)
                    if k2 in ("process", "thread"):
                        put(key, k2 + "_list")
                elif isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) \
                        and v.func.attr in PROXY_METHODS:
                    rk = self.ctor_kind(v.func.value) or sc.bindings.get(dotted(v.func.value)) \
                        or self.module_scope.bindings.get(dotted(v.func.value))
                    if rk == "manager":
                        put(key, "proxy")
                if isinstance(targets[0], ast.Name):
                    if isinstance(v, ast.Lambda):
                        sc.lambdas.add(key)
                    if self.is_heavy(v):
                        sc.heavy.add(key)
            elif isinstance(n, (ast.With, ast.AsyncWith)):
                for item in n.items:
                    if item.optional_vars is not None:
                        put(dotted(item.optional_vars), self.ctor_kind(item.context_expr))
            elif isinstance(n, FUNCS) and sc.func is not None:
                sc.local_defs[n.name] = n
        for n in sc.nodes:
            if isinstance(n, (ast.For, ast.AsyncFor)) and isinstance(n.target, ast.Name):
                k = sc.bindings.get(dotted(n.iter)) or self.module_scope.bindings.get(dotted(n.iter))
                if k in ("process_list", "thread_list"):
                    put(n.target.id, k[:-5])
        for key in conflict:
            sc.bindings.pop(key, None)
            sc.assign_sites.pop(key, None)

    def is_heavy(self, v):
        if large_literal(v):
            return True
        if isinstance(v, ast.Call):
            full = self.resolve(v.func)
            last = full.rsplit(".", 1)[-1]
            if last in HEAVY_ATTRS or full in HEAVY_CALLS:
                return True
            if last in ("list", "bytearray") and v.args and isinstance(v.args[0], ast.Call) \
                    and dotted(v.args[0].func) == "range" and v.args[0].args \
                    and isinstance(v.args[0].args[-1], ast.Constant) \
                    and isinstance(v.args[0].args[-1].value, int) and v.args[0].args[-1].value >= 100_000:
                return True
        return False

    def kind_of(self, expr, sc):
        if isinstance(expr, ast.Call):
            return self.ctor_kind(expr)
        key = dotted(expr)
        if not key:
            return None
        if key in sc.bindings:
            return sc.bindings[key]
        if key in sc.params:
            return None
        if key.startswith("self.") or key.startswith("cls."):
            for other in self.scopes:
                if key in other.bindings:
                    return other.bindings[key]
            return None
        return self.module_scope.bindings.get(key)

    def task_calls(self, sc):
        """Yield (call, method, receiver_kind, func_expr) for work sent to pools/executors."""
        for n in sc.nodes:
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
                continue
            meth = n.func.attr
            kind = self.kind_of(n.func.value, sc)
            if kind in ("pool", "threadpool") and meth in POOL_TASK_METHODS:
                pass
            elif kind in ("executor", "texecutor", "interp") and meth in EXEC_TASK_METHODS:
                pass
            else:
                continue
            fn = n.args[0] if n.args else (kwarg(n, "func") or kwarg(n, "fn"))
            yield n, meth, kind, fn

    def callable_name(self, fn):
        """Module-level function name behind fn (unwrapping functools.partial), or None."""
        while isinstance(fn, ast.Call) and self.resolve(fn.func).endswith("partial") and fn.args:
            fn = fn.args[0]
        if isinstance(fn, ast.Name) and fn.id in self.module_defs:
            return fn.id
        return None

    def index_workers(self, sc):
        for call, meth, kind, fn in self.task_calls(sc):
            name = self.callable_name(fn)
            if name and kind in PROC_KINDS:
                self.worker_funcs.setdefault(name, set()).add(kind)
        for n in sc.nodes:
            if not isinstance(n, ast.Call):
                continue
            kind = self.ctor_kind(n)
            if kind in ("pool", "executor"):
                init = kwarg(n, "initializer")
                if init is None and kind == "pool" and len(n.args) >= 2:
                    init = n.args[1]
                name = self.callable_name(init) if init is not None else None
                if name:
                    self.init_funcs.add(name)
            elif kind == "process":
                name = self.callable_name(kwarg(n, "target"))
                if name:
                    self.worker_funcs.setdefault(name, set()).add("process")
                    d = kwarg(n, "daemon")
                    if isinstance(d, ast.Constant) and d.value is True:
                        self.daemon_targets.add(name)

    # ------------------------------------------------------------ driver
    def run(self):
        self.index()
        self.check_module_level()
        self.check_start_methods()
        for sc in self.scopes:
            self.check_unpicklable(sc)
            self.check_not_closed(sc)
            self.check_with_results(sc)
            self.check_chunksize(sc)
            self.check_lost_exceptions(sc)
            self.check_large_args(sc)
            self.check_proxies(sc)
            self.check_join_before_drain(sc)
            self.check_model_recycle(sc)
            self.check_queue_to_pool(sc)
            self.check_serialized(sc)
            self.check_pool_in_loop(sc)
            self.check_threads_before_fork(sc)
        self.check_ctrl_c()
        self.check_global_mutation()
        self.check_nested_pools()
        self.check_oversubscription()
        return self.findings

    # ------------------------------------------------------------ MP001 / MP015
    def toplevel_nodes(self):
        stack = [s for s in self.tree.body if not is_main_guard(s)]
        while stack:
            node = stack.pop()
            yield node
            if isinstance(node, SCOPES):
                continue
            for child in ast.iter_child_nodes(node):
                if not is_main_guard(child):
                    stack.append(child)

    def creates_processes(self, func):
        for n in walk_local(func.body):
            if isinstance(n, ast.Call):
                if self.ctor_kind(n) in ("pool", "executor"):
                    return True
                if isinstance(n.func, ast.Attribute) and n.func.attr == "start" \
                        and self.ctor_kind(n.func.value) == "process":
                    return True
        return False

    def check_module_level(self):
        sc = self.module_scope
        for n in self.toplevel_nodes():
            if not isinstance(n, ast.Call):
                continue
            kind = self.ctor_kind(n)
            if kind in ("pool", "executor"):
                self.add("MP001", n, f"{'Pool' if kind == 'pool' else 'ProcessPoolExecutor'} created at import "
                         "time: every spawn/forkserver child re-imports this module and runs it again")
            elif isinstance(n.func, ast.Attribute) and n.func.attr == "start" \
                    and self.kind_of(n.func.value, sc) == "process":
                self.add("MP001", n, "Process.start() at import time without an `if __name__ == \"__main__\":` "
                         "guard")
            elif isinstance(n.func, ast.Name) and n.func.id in self.module_defs \
                    and isinstance(parent(n), (ast.Expr, ast.Assign)) \
                    and self.creates_processes(self.module_defs[n.func.id]):
                self.add("MP001", n, f"`{n.func.id}()` starts processes and is called at import time; call it "
                         "under `if __name__ == \"__main__\":`")
        for n in ast.walk(self.tree):
            if isinstance(n, ast.Call) and self.resolve(n.func) in ("os.fork", "os.forkpty"):
                self.add("MP015", n, f"{self.resolve(n.func)}() used directly; use a multiprocessing context "
                         "(spawn/forkserver) or subprocess")

    # ------------------------------------------------------------ MP007 / MP008
    def check_start_methods(self):
        calls = [n for n in ast.walk(self.tree) if isinstance(n, ast.Call)
                 and self.resolve(n.func).endswith("set_start_method")]
        calls.sort(key=lambda c: (c.lineno, c.col_offset))
        top = set(id(n) for n in self.toplevel_nodes())
        for i, c in enumerate(calls):
            if id(c) in top:
                self.add("MP007", c, "set_start_method() runs at import time; spawned children re-import the "
                         "module and hit 'context has already been set'. Move it under the main guard or use "
                         "get_context()")
            elif i > 0 and not (isinstance(kwarg(c, "force"), ast.Constant) and kwarg(c, "force").value is True):
                self.add("MP007", c, f"set_start_method() called again (first call on line {calls[0].lineno}); "
                         "the second call raises RuntimeError")
        gpu = sorted({v.split(".")[0] for v in self.imports.values()} & set(GPU_MODULES))
        if not gpu:
            return
        for m, node in self.explicit_methods:
            if m == "fork":
                self.add("MP008", node, f"'fork' start method in a module that imports {', '.join(gpu)}: CUDA "
                         "cannot be initialised in a forked child; use 'spawn'")
        for n in ast.walk(self.tree):
            if isinstance(n, ast.Call) and self.resolve(n.func) == "os.fork":
                self.add("MP008", n, f"os.fork() in a module that imports {', '.join(gpu)}")

    # ------------------------------------------------------------ MP002
    def unpicklable_reason(self, fn, sc):
        if isinstance(fn, ast.Lambda):
            return "a lambda"
        if isinstance(fn, ast.Name):
            if fn.id in sc.local_defs:
                return f"nested function `{fn.id}`"
            if fn.id in sc.lambdas:
                return f"`{fn.id}` (bound to a lambda)"
            return None
        if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and sc.func is not None:
            args = sc.func.args.posonlyargs + sc.func.args.args
            if args and args[0].arg == "self" and fn.value.id == "self" \
                    and isinstance(parent(sc.func), ast.ClassDef):
                return f"bound method `self.{fn.attr}` (pickles the whole instance with every task)"
            return None
        if isinstance(fn, ast.Call) and self.resolve(fn.func).endswith("partial") and fn.args:
            inner = self.unpicklable_reason(fn.args[0], sc)
            return f"functools.partial of {inner}" if inner else None
        return None

    def check_unpicklable(self, sc):
        forked = {m for m, _ in self.explicit_methods} == {"fork"}
        for call, meth, kind, fn in self.task_calls(sc):
            if kind not in PROC_KINDS or fn is None:
                continue
            reason = self.unpicklable_reason(fn, sc)
            if reason:
                self.add("MP002", call, f"{reason} passed to {meth}(): tasks are pickled by qualified name; "
                         "move it to module level")
        for n in sc.nodes:
            if not isinstance(n, ast.Call):
                continue
            kind = self.ctor_kind(n)
            if kind in PROC_KINDS:
                init = kwarg(n, "initializer")
                if init is not None:
                    reason = self.unpicklable_reason(init, sc)
                    if reason and not (forked or self.ctx_method_of(n) == "fork"):
                        self.add("MP002", n, f"initializer is {reason}: it is pickled for spawn/forkserver workers")
            elif kind == "process":
                tgt = kwarg(n, "target")
                method = self.ctx_method_of(n)
                if tgt is not None and method != "fork" and not (forked and method is None):
                    reason = self.unpicklable_reason(tgt, sc)
                    if reason:
                        self.add("MP002", n, f"Process target is {reason}: works only with fork; spawn/forkserver "
                                 "(macOS, Windows, Linux 3.14+) must pickle it")

    # ------------------------------------------------------------ MP003
    def escapes(self, key, sc):
        for n in sc.nodes:
            if isinstance(n, (ast.Return, ast.Yield)) and n.value is not None and key in {
                    dotted(x) for x in ast.walk(n.value)}:
                return True
            if isinstance(n, ast.Call) and any(dotted(a) == key for a in list(n.args)
                                               + [k.value for k in n.keywords]):
                return True
            if isinstance(n, (ast.With, ast.AsyncWith)) and any(dotted(i.context_expr) == key for i in n.items):
                return True
            if isinstance(n, ast.Assign) and dotted(n.value) == key:
                return True
        return False

    def method_receivers(self, nodes, names):
        out = set()
        for n in nodes:
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in names:
                out.add(dotted(n.func.value))
        return out

    def check_not_closed(self, sc):
        all_nodes = list(ast.walk(self.tree))
        for key, (node, kind) in sc.assign_sites.items():
            nodes = all_nodes if "." in key else sc.nodes
            if self.escapes(key, sc):
                continue
            if kind == "executor":
                if key not in self.method_receivers(nodes, {"shutdown"}):
                    self.add("MP003", node, f"ProcessPoolExecutor `{key}` is never shut down; use `with` or "
                             f"{key}.shutdown()")
                continue
            if kind not in ("pool", "threadpool"):
                continue
            closed = key in self.method_receivers(nodes, {"close"})
            term = key in self.method_receivers(nodes, {"terminate"})
            joined = key in self.method_receivers(nodes, {"join"})
            if term or (closed and joined):
                continue
            what = "closed but never joined" if closed else "never closed or terminated"
            self.add("MP003", node, f"pool `{key}` is {what}; use `with Pool(...)` or close()+join() in finally")

    # ------------------------------------------------------------ MP004
    def check_with_results(self, sc):
        owners = [sc.func if sc.func is not None else self.tree] + [
            x for x in sc.nodes if not isinstance(x, SCOPES)]
        for owner in owners:
            for body in stmt_lists(owner):
                for i, st in enumerate(body):
                    if not isinstance(st, ast.With):
                        continue
                    pools = set()
                    for item in st.items:
                        k = self.ctor_kind(item.context_expr) or self.kind_of(item.context_expr, sc)
                        if k == "pool":
                            pools.add(dotted(item.optional_vars) if item.optional_vars is not None
                                      else dotted(item.context_expr))
                    pools.discard("")
                    if not pools:
                        continue
                    names = set()
                    for n in walk_local(st.body):
                        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                                and n.func.attr in ITER_RESULT_METHODS and dotted(n.func.value) in pools):
                            continue
                        p = parent(n)
                        while p is not None and p is not st and not isinstance(p, ast.stmt):
                            p = parent(p)
                        if isinstance(p, ast.Assign):
                            names |= {dotted(t) for t in p.targets if dotted(t)}
                        elif isinstance(p, ast.Expr) and isinstance(p.value, ast.Call) \
                                and isinstance(p.value.func, ast.Attribute) \
                                and p.value.func.attr in ("append", "extend"):
                            names.add(dotted(p.value.func.value))
                    names.discard("")
                    if not names:
                        continue
                    for later in body[i + 1:]:
                        hit = next((x for x in walk_local([later]) if isinstance(x, ast.Name)
                                    and isinstance(x.ctx, ast.Load) and x.id in names), None)
                        if hit is not None:
                            self.add("MP004", hit, f"`{hit.id}` holds pool results but is read after the `with "
                                     "Pool()` block exited: Pool.__exit__ calls terminate()")
                            names.discard(hit.id)
                        rebound = {dotted(t) for x in walk_local([later]) if isinstance(x, ast.Assign)
                                   for t in x.targets}
                        names -= rebound
                        if not names:
                            break

    # ------------------------------------------------------------ MP005
    def check_chunksize(self, sc):
        for call, meth, kind, fn in self.task_calls(sc):
            if kwarg(call, "chunksize") is not None or len(call.args) < 2:
                continue
            it = call.args[1]
            if is_literal_iterable(it):
                continue
            label = dotted(it.func if isinstance(it, ast.Call) else it).lower()
            if any(h in label for h in BATCHED_HINTS):
                continue                      # items are already batches/shards: chunksize 1 is right
            if kind == "pool" and meth in ("imap", "imap_unordered") and len(call.args) < 3:
                self.add("MP005", call, f"{meth}() without chunksize sends one IPC message per item; pass "
                         "chunksize (see `pool_tool.py plan`)")
            elif kind == "executor" and meth == "map":
                self.add("MP005", call, "ProcessPoolExecutor.map() defaults to chunksize=1; pass chunksize= "
                         "for many small tasks")

    # ------------------------------------------------------------ MP006
    def loaded_later(self, name, sc):
        return any(isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load) for n in sc.nodes)

    def check_lost_exceptions(self, sc):
        for call, meth, kind, fn in self.task_calls(sc):
            if kind not in PROC_KINDS:
                continue
            if kind == "pool" and meth in ASYNC_METHODS:
                if kwarg(call, "error_callback") is not None:
                    continue
                label = f"{meth}() result"
            elif kind == "executor" and meth == "submit":
                label = "submit() future"
            else:
                continue
            p = parent(call)
            holder = p
            if isinstance(p, (ast.ListComp, ast.GeneratorExp)) and p.elt is call:
                holder = parent(p)
            if isinstance(holder, ast.Expr):
                self.add("MP006", call, f"{label} is discarded: a worker exception is never raised or logged")
            elif isinstance(holder, ast.Assign) and len(holder.targets) == 1 \
                    and isinstance(holder.targets[0], ast.Name) \
                    and not self.loaded_later(holder.targets[0].id, sc):
                self.add("MP006", call, f"{label} stored in `{holder.targets[0].id}` is never read: worker "
                         "exceptions are lost")

    # ------------------------------------------------------------ MP009
    def module_mutables(self):
        out = set()
        for st in self.tree.body:
            if isinstance(st, (ast.Assign, ast.AnnAssign)) and st.value is not None:
                targets = st.targets if isinstance(st, ast.Assign) else [st.target]
                v = st.value
                mutable = isinstance(v, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp)) or (
                    isinstance(v, ast.Call) and self.resolve(v.func).rsplit(".", 1)[-1] in MUTABLE_CTORS)
                if mutable:
                    out |= {t.id for t in targets if isinstance(t, ast.Name)}
        return out

    def check_global_mutation(self):
        mutables = self.module_mutables()
        workers = set(self.worker_funcs) - self.init_funcs
        exempt_funcs = set(self.worker_funcs) | self.init_funcs
        for name in sorted(workers):
            func = self.module_defs[name]
            nodes = list(walk_local(func.body))
            declared = {g for n in nodes if isinstance(n, ast.Global) for g in n.names}
            params = {a.arg for a in func.args.posonlyargs + func.args.args + func.args.kwonlyargs}
            local = {t.id for n in nodes if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.For))
                     for t in ast.walk(n.targets[0] if isinstance(n, ast.Assign) else n.target)
                     if isinstance(t, ast.Name) and isinstance(t.ctx, ast.Store)} - declared
            tested_none = set()
            for n in nodes:
                if isinstance(n, ast.Compare) and isinstance(n.left, ast.Name) and any(
                        isinstance(c, ast.Constant) and c.value is None for c in n.comparators):
                    tested_none.add(n.left.id)
                if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not) and isinstance(n.operand, ast.Name):
                    tested_none.add(n.operand.id)
            hits = {}
            for n in nodes:
                g = None
                if isinstance(n, (ast.Assign, ast.AugAssign)):
                    for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                        if isinstance(t, ast.Name) and t.id in declared and t.id not in tested_none:
                            g = t.id
                        elif isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
                            g = t.value.id if t.value.id in mutables | declared else None
                elif isinstance(n, ast.Delete):
                    for t in n.targets:
                        if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) \
                                and t.value.id in mutables:
                            g = t.value.id
                elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                        and n.func.attr in MUTATORS and isinstance(n.func.value, ast.Name) \
                        and n.func.value.id in mutables | declared:
                    g = n.func.value.id
                if g and g not in params and g not in local and g not in hits:
                    hits[g] = n
            for g, node in hits.items():
                if self.read_outside(g, exempt_funcs):
                    self.add("MP009", node, f"worker `{name}()` mutates module global `{g}`, which the parent "
                             "reads: each worker changes its own copy; return results instead")

    def read_outside(self, name, exempt):
        for n in ast.walk(self.tree):
            if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load):
                f = n
                while f is not None and not isinstance(f, FUNCS):
                    f = parent(f)
                if f is None or (f.name not in exempt or parent(f) is not self.tree):
                    return True
        return False

    # ------------------------------------------------------------ MP010
    def heavy_names(self, sc):
        mod = self.module_scope.heavy - sc.params - set(sc.bindings)
        return sc.heavy | mod

    def check_large_args(self, sc):
        heavy = self.heavy_names(sc)
        if not heavy:
            return
        for call, meth, kind, fn in self.task_calls(sc):
            if kind not in PROC_KINDS:
                continue
            hit = None
            if isinstance(fn, ast.Call) and self.resolve(fn.func).endswith("partial"):
                hit = next((x for a in fn.args[1:] + [k.value for k in fn.keywords]
                            for x in names_in(a) if x in heavy), None)
                how = "bound into functools.partial (pickled with every chunk)"
            if hit is None and meth in MAP_LIKE:
                for it in call.args[1:]:
                    for x in ast.walk(it):
                        if isinstance(x, (ast.ListComp, ast.GeneratorExp)):
                            hit = next((h for h in names_in(x.elt) if h in heavy), None)
                        elif isinstance(x, ast.Call) and self.resolve(x.func).endswith("repeat"):
                            hit = next((h for a in x.args for h in names_in(a) if h in heavy), None)
                        if hit:
                            break
                    if hit:
                        break
                how = "repeated in every work item"
            if hit is None and meth in ("submit", "apply_async", "apply") and in_loop(call):
                rest = call.args[1:] + [k.value for k in call.keywords]
                hit = next((h for a in rest for h in names_in(a) if h in heavy), None)
                how = "sent with every task in a loop"
            if hit:
                self.add("MP010", call, f"large object `{hit}` {how}; load it once per worker (initializer) or "
                         "share it (shared_memory / path)")

    # ------------------------------------------------------------ MP011
    def positional_args(self, call, sc):
        """For a task/Process call return (worker_name, [arg exprs in parameter order]) or None."""
        kind = self.ctor_kind(call)
        if kind == "process":
            name = self.callable_name(kwarg(call, "target"))
            a = kwarg(call, "args")
            return (name, list(a.elts)) if name and isinstance(a, (ast.Tuple, ast.List)) else None
        if not isinstance(call.func, ast.Attribute):
            return None
        meth, rk = call.func.attr, self.kind_of(call.func.value, sc)
        if rk not in PROC_KINDS or not call.args:
            return None
        fn = call.args[0]
        pre = []
        if isinstance(fn, ast.Call) and self.resolve(fn.func).endswith("partial") and fn.args:
            pre, fn = list(fn.args[1:]), fn.args[0]
        name = fn.id if isinstance(fn, ast.Name) and fn.id in self.module_defs else None
        if not name:
            return None
        if meth == "submit":
            return name, pre + list(call.args[1:])
        if meth in ("apply_async", "apply") and len(call.args) > 1 and isinstance(call.args[1], (ast.Tuple, ast.List)):
            return name, pre + list(call.args[1].elts)
        if meth in ("starmap", "starmap_async") and len(call.args) > 1 and isinstance(call.args[1], ast.ListComp) \
                and isinstance(call.args[1].elt, ast.Tuple):
            return name, pre + list(call.args[1].elt.elts)
        if pre:
            return name, pre
        return None

    def proxy_uses_in_loops(self, nodes, names):
        for n in nodes:
            if isinstance(n, (ast.Subscript, ast.Attribute)) and isinstance(n.value, ast.Name) \
                    and n.value.id in names and in_loop(n):
                yield n

    def check_proxies(self, sc):
        proxies = {k for k, v in sc.bindings.items() if v == "proxy"}
        if not proxies:
            return
        for n in self.proxy_uses_in_loops(sc.nodes, proxies):
            self.add("MP011", n, f"Manager proxy `{n.value.id}` accessed inside a loop: one IPC round trip per "
                     "access")
        for n in sc.nodes:
            if not isinstance(n, ast.Call):
                continue
            pa = self.positional_args(n, sc)
            if not pa:
                continue
            name, exprs = pa
            func = self.module_defs[name]
            params = [a.arg for a in func.args.posonlyargs + func.args.args]
            targets = {params[i] for i, e in enumerate(exprs) if i < len(params) and dotted(e) in proxies}
            for use in self.proxy_uses_in_loops(walk_local(func.body), targets):
                self.add("MP011", use, f"`{use.value.id}` is a Manager proxy (passed from line {n.lineno}); "
                         "each access inside this loop is an IPC round trip")

    # ------------------------------------------------------------ MP012
    def check_join_before_drain(self, sc):
        queues = {k for k, v in sc.bindings.items() if v == "mpqueue"} | {
            k for k, v in self.module_scope.bindings.items() if v == "mpqueue" and k not in sc.bindings}
        if not queues:
            return
        fed = set()
        for n in sc.nodes:
            if isinstance(n, ast.Call) and self.ctor_kind(n) == "process":
                a = kwarg(n, "args")
                if a is not None:
                    fed |= {dotted(x) for x in ast.walk(a)} & queues
        if not fed:
            return
        gets = [n.lineno for n in sc.nodes if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in ("get", "get_nowait") and dotted(n.func.value) in fed]
        if not gets:
            return
        first_get = min(gets)
        for n in sc.nodes:
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "join" \
                    and not n.args and not n.keywords and n.lineno < first_get \
                    and self.kind_of(n.func.value, sc) == "process":
                self.add("MP012", n, f"process joined (line {n.lineno}) before its queue is drained (first get() on "
                         f"line {first_get}): deadlocks once the queue holds more than a pipe buffer")

    # ------------------------------------------------------------ MP013
    def loads_model(self, name):
        func = self.module_defs.get(name)
        if func is None:
            return False
        for n in walk_local(func.body):
            if isinstance(n, ast.Call):
                full = self.resolve(n.func)
                if full.rsplit(".", 1)[-1] in MODEL_LOAD_ATTRS or full in MODEL_LOAD_CALLS:
                    return True
        return False

    def check_model_recycle(self, sc):
        for n in sc.nodes:
            if not isinstance(n, ast.Call):
                continue
            kind = self.ctor_kind(n)
            if kind not in PROC_KINDS:
                continue
            if kwarg(n, "maxtasksperchild") is not None or kwarg(n, "max_tasks_per_child") is not None \
                    or (kind == "pool" and len(n.args) >= 4):
                continue
            funcs = set()
            init = kwarg(n, "initializer") or (n.args[1] if kind == "pool" and len(n.args) >= 2 else None)
            if init is not None and self.callable_name(init):
                funcs.add(self.callable_name(init))
            p = parent(n)
            key = None
            if isinstance(p, ast.Assign) and len(p.targets) == 1:
                key = dotted(p.targets[0])
            elif isinstance(p, ast.withitem) and p.optional_vars is not None:
                key = dotted(p.optional_vars)
            if key:
                for call, meth, k, fn in self.task_calls(sc):
                    if dotted(call.func.value) == key and self.callable_name(fn):
                        funcs.add(self.callable_name(fn))
            loader = next((f for f in sorted(funcs) if self.loads_model(f)), None)
            if loader:
                arg = "maxtasksperchild" if kind == "pool" else "max_tasks_per_child (3.11+)"
                self.add("MP013", n, f"workers load a model in `{loader}()` but the pool sets no {arg}; long-lived "
                         "workers grow until OOM-killed")

    # ------------------------------------------------------------ MP014
    def check_queue_to_pool(self, sc):
        queues = {k for k, v in sc.bindings.items() if v == "mpqueue"} | {
            k for k, v in self.module_scope.bindings.items() if v == "mpqueue" and k not in sc.bindings}
        if not queues:
            return
        for call, meth, kind, fn in self.task_calls(sc):
            if kind not in PROC_KINDS:
                continue
            exprs = list(call.args) + [k.value for k in call.keywords]
            hit = next((dotted(x) for e in exprs for x in ast.walk(e) if dotted(x) in queues), None)
            if hit:
                self.add("MP014", call, f"multiprocessing.Queue `{hit}` passed to {meth}(): RuntimeError 'Queue "
                         "objects should only be shared between processes through inheritance'")

    # ------------------------------------------------------------ MP016
    def check_ctrl_c(self):
        text = self.source
        if "KeyboardInterrupt" in text or "SIGINT" in text:
            return
        scopes = [(sc, sc.nodes) for sc in self.scopes if sc.func is not None and sc.func.name == "main"]
        for sc, nodes in scopes:
            for n in nodes:
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                        and n.func.attr in MAP_LIKE and self.kind_of(n.func.value, sc) in PROC_KINDS:
                    self.add("MP016", n, "pool map in main() without KeyboardInterrupt handling: Ctrl-C "
                             "prints a traceback per worker and can leave workers running")
                    break

    # ------------------------------------------------------------ MP017
    def thread_events(self, sc, nodes):
        out = []
        for n in nodes:
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
                continue
            recv = n.func.value
            if n.func.attr == "start" and self.kind_of(recv, sc) == "thread":
                out.append((n.lineno, dotted(recv), n))
            elif n.func.attr in ("submit", "map") and self.kind_of(recv, sc) == "texecutor" \
                    and not enclosing(n, (ast.With,)):
                out.append((n.lineno, dotted(recv), n))
        return out

    def check_threads_before_fork(self, sc):
        explicit = {m for m, _ in self.explicit_methods if self.is_global_method_node(_)}
        default_fork = not explicit
        module_threads = [] if sc is self.module_scope else self.thread_events(
            self.module_scope, [n for n in self.toplevel_nodes()])
        threads = self.thread_events(sc, sc.nodes)
        if not threads and not module_threads:
            return
        for n in sc.nodes:
            if not isinstance(n, ast.Call):
                continue
            kind = self.ctor_kind(n)
            is_proc = kind in PROC_KINDS or (
                isinstance(n.func, ast.Attribute) and n.func.attr == "start"
                and self.kind_of(n.func.value, sc) == "process")
            is_osfork = self.resolve(n.func) == "os.fork"
            if not (is_proc or is_osfork):
                continue
            if is_osfork:
                method = "fork"
            else:
                ctor = n if kind in PROC_KINDS else None
                if ctor is None:
                    v = n.func.value
                    ctor = v if isinstance(v, ast.Call) else None
                method = self.ctx_method_of(ctor) if ctor is not None else None
                if method is None:
                    method = "fork" if "fork" in explicit else (None if explicit else "default")
            if method not in ("fork", "default"):
                continue
            before = [t for t in module_threads] + [t for t in threads if t[0] < n.lineno]
            for line, key, tnode in before:
                joined = any(isinstance(j, ast.Call) and isinstance(j.func, ast.Attribute)
                             and j.func.attr in ("join", "shutdown") and dotted(j.func.value) == key
                             and line < j.lineno < n.lineno for j in sc.nodes)
                if joined:
                    continue
                note = "the fork start method" if method == "fork" else \
                    "the default start method (fork on Linux before 3.14)"
                self.add("MP017", n, f"processes created with {note} after a thread was started on line {line}: "
                         "locks held by that thread are copied locked into the child")
                return

    def is_global_method_node(self, node):
        return self.resolve(node.func).endswith("set_start_method")

    # ------------------------------------------------------------ MP018
    def check_nested_pools(self):
        for name, kinds in sorted(self.worker_funcs.items()):
            if "pool" not in kinds and name not in self.daemon_targets:
                continue
            for n in walk_local(self.module_defs[name].body):
                if isinstance(n, ast.Call) and self.ctor_kind(n) in ("pool", "executor", "process"):
                    self.add("MP018", n, f"`{name}()` runs inside a daemonic worker and creates child processes: "
                             "'daemonic processes are not allowed to have children'")
                    break

    # ------------------------------------------------------------ MP019 / MP020
    def check_serialized(self, sc):
        for n in sc.nodes:
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
                continue
            inner = n.func.value
            if n.func.attr in ("get", "result") and isinstance(inner, ast.Call) \
                    and isinstance(inner.func, ast.Attribute) and in_loop(n):
                rk = self.kind_of(inner.func.value, sc)
                if (rk == "pool" and inner.func.attr == "apply_async") or (rk == "executor"
                                                                           and inner.func.attr == "submit"):
                    self.add("MP019", n, f"{inner.func.attr}(...).{n.func.attr}() inside a loop waits for each task "
                             "before submitting the next: no parallelism")
            elif n.func.attr == "apply" and self.kind_of(inner, sc) == "pool" and in_loop(n):
                self.add("MP019", n, "Pool.apply() blocks until the task finishes; in a loop it runs tasks one at "
                         "a time")

    def check_pool_in_loop(self, sc):
        for n in sc.nodes:
            if isinstance(n, ast.Call) and self.ctor_kind(n) in PROC_KINDS:
                p, child = parent(n), n
                while p is not None and not isinstance(p, FUNCS + (ast.ClassDef, ast.Lambda, ast.Module)):
                    if (isinstance(p, (ast.For, ast.AsyncFor)) and child is not p.iter) or \
                            (isinstance(p, ast.While) and child is not p.test):
                        self.add("MP020", n, "process pool created inside a loop: worker start-up (and model "
                                 "loading) is paid on every iteration")
                        break
                    p, child = parent(p), p

    # ------------------------------------------------------------ MP021
    def check_oversubscription(self):
        if not any(v.split(".")[0] == "torch" for v in self.imports.values()):
            return
        if "set_num_threads" in self.source or "OMP_NUM_THREADS" in self.source:
            return
        first = None
        for n in ast.walk(self.tree):
            if isinstance(n, ast.Call) and self.ctor_kind(n) in ("pool", "executor", "process"):
                if first is None or n.lineno < first.lineno:
                    first = n
        if first is not None:
            self.add("MP021", first, "torch is imported and process workers are started, but intra-op threads are "
                     "never limited: N workers x N threads oversubscribe the CPU")


# ====================================================================== check CLI

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


def print_rules():
    for rid, info in RULES.items():
        print(f"{rid} [{info['severity']}] {info['name']}: {info['summary']}")
        print(f"    why: {info['why']}")
        print("    fix: " + info["fix"].replace("\n", "\n         "))
        print()


def cmd_check(args, ap):
    if args.list_rules:
        print_rules()
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
            print(f"No multiprocessing issues found in {files} file(s).")
    if errors:
        return 2
    return 1 if args.strict and findings else 0


# ====================================================================== planner

# Model constants (documented in references/sizing-chunksize-and-memory.md).
ITEM_OVERHEAD_US = 5.0        # parent bookkeeping per item (iterator, result slot)
CHUNK_OVERHEAD_US = 150.0     # per chunk message: queue locks, pipe syscalls, wakeups, pickling the call
IPC_US_PER_KB = 2.0           # pickle + pipe + unpickle per KB of payload/result (bytes-like data)
WORKER_CHUNK_US = 50.0        # worker-side cost per chunk (get, unpickle frame, put result)
LAUNCH_S = {"fork": 0.003, "forkserver": 0.005, "spawn": 0.02}     # parent-side, sequential, per worker
BOOT_S = {"fork": 0.0, "forkserver": 0.08, "spawn": 0.12}          # child boot, in parallel, once
SHUTDOWN_S = 0.05
MIN_CHUNK_S = 0.02           # preferred minimum chunk duration (20 ms of work per message)
TAIL_FRACTION = 0.5          # expected straggler cost, in chunk durations, from uneven item times
MEM_HEADROOM = 0.85           # fraction of the memory limit usable by workers (rest: parent, page cache)


def default_start_method():
    if sys.platform.startswith("linux"):
        return "forkserver" if sys.version_info >= (3, 14) else "fork"
    return "spawn"


def read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return None


def detect_cores():
    """Return (cores, source description)."""
    if hasattr(os, "process_cpu_count"):
        n, src = os.process_cpu_count(), "os.process_cpu_count()"
    elif hasattr(os, "sched_getaffinity"):
        n, src = len(os.sched_getaffinity(0)), "os.sched_getaffinity(0)"
    else:
        n, src = os.cpu_count(), "os.cpu_count()"
    n = n or 1
    quota = None
    v2 = read_text("/sys/fs/cgroup/cpu.max")
    if v2:
        parts = v2.split()
        if len(parts) == 2 and parts[0] != "max":
            try:
                quota = float(parts[0]) / float(parts[1])
            except ValueError:
                quota = None
    else:
        q, p = read_text("/sys/fs/cgroup/cpu/cpu.cfs_quota_us"), read_text("/sys/fs/cgroup/cpu/cpu.cfs_period_us")
        try:
            if q and p and int(q) > 0:
                quota = int(q) / int(p)
        except ValueError:
            quota = None
    if quota is not None and math.ceil(quota) < n:
        return max(1, math.ceil(quota)), f"cgroup CPU quota {quota:g} (affinity {n})"
    return n, src


def detect_mem_limit_mb():
    v2 = read_text("/sys/fs/cgroup/memory.max")
    if v2 and v2 != "max":
        try:
            return int(v2) / 2 ** 20, "cgroup memory.max"
        except ValueError:
            pass
    v1 = read_text("/sys/fs/cgroup/memory/memory.limit_in_bytes")
    if v1:
        try:
            if int(v1) < 2 ** 60:
                return int(v1) / 2 ** 20, "cgroup memory.limit_in_bytes"
        except ValueError:
            pass
    info = read_text("/proc/meminfo")
    if info:
        m = re.search(r"MemAvailable:\s+(\d+) kB", info)
        if m:
            return int(m.group(1)) / 1024, "/proc/meminfo MemAvailable"
    return None, "unknown"


def chunk_candidates(n, w):
    out = {1, max(1, math.ceil(n / (4 * w)))}
    c = 2
    while c <= max(1, math.ceil(n / w)):
        out.add(c)
        c *= 2
    return sorted(out)


def model(a, w, chunk, method):
    """Estimated wall time (seconds) and components for w workers and a chunksize."""
    n = a.items
    item_s = a.item_ms / 1000.0
    n_chunks = math.ceil(n / chunk)
    ipc_item_s = (a.payload_kb + a.result_kb) * IPC_US_PER_KB / 1e6
    parent_s = n * (ITEM_OVERHEAD_US / 1e6 + ipc_item_s) + n_chunks * CHUNK_OVERHEAD_US / 1e6
    worker_s = (n * (item_s + ipc_item_s) + n_chunks * WORKER_CHUNK_US / 1e6) / w
    rounds = math.ceil(n_chunks / w)
    balanced_s = rounds * chunk * (item_s + ipc_item_s) + rounds * WORKER_CHUNK_US / 1e6
    tail_s = TAIL_FRACTION * chunk * (item_s + ipc_item_s) if w > 1 and n_chunks > 1 else 0.0
    compute_s = max(worker_s, balanced_s, parent_s) + tail_s
    startup_s = w * LAUNCH_S[method] + BOOT_S[method] + a.init_s
    wall = startup_s + compute_s + SHUTDOWN_S
    overhead_s = n * ipc_item_s * 2 + n * ITEM_OVERHEAD_US / 1e6 + n_chunks * (
        CHUNK_OVERHEAD_US + WORKER_CHUNK_US) / 1e6
    return {
        "wall_s": wall, "startup_s": startup_s, "compute_s": compute_s, "parent_s": parent_s,
        "worker_s": worker_s, "n_chunks": n_chunks, "tail_s": tail_s,
        "ipc_share": overhead_s / (overhead_s + n * item_s) if n * item_s + overhead_s > 0 else 0.0,
    }


def plan(a):
    method = a.start_method or default_start_method()
    if a.cores:
        cores, core_src = a.cores, "--cores"
    else:
        cores, core_src = detect_cores()
    mem_limit, mem_src = (a.mem_limit_mb, "--mem-limit-mb") if a.mem_limit_mb else (None, "not set")
    if mem_limit is None and a.mem_per_worker_mb:
        mem_limit, mem_src = detect_mem_limit_mb()
    cap_cpu = cores
    cap_mem = None
    if a.mem_per_worker_mb and mem_limit:
        cap_mem = max(0, int(MEM_HEADROOM * mem_limit // a.mem_per_worker_mb))
    cap = max(1, min([cap_cpu, a.items] + ([cap_mem] if cap_mem is not None else [])))

    serial_s = a.items * a.item_ms / 1000.0 + a.init_s
    best = None
    table = []
    for w in range(1, cap + 1):
        runs = [(w, c, model(a, w, c, method)) for c in chunk_candidates(a.items, w)]
        fastest = min(r["wall_s"] for _, _, r in runs)
        # smallest chunksize within 1% of the fastest whose chunk lasts >= MIN_CHUNK_S: same speed, better
        # balance and progress granularity, and robust to underestimated per-message overhead
        near = [x for x in runs if x[2]["wall_s"] <= fastest * 1.01]
        long_enough = [x for x in near if x[1] * a.item_ms / 1000.0 >= MIN_CHUNK_S]
        w_best = (long_enough or near[-1:])[0]
        table.append(w_best)
        if best is None or w_best[2]["wall_s"] < best[2]["wall_s"]:
            best = w_best
    # prefer fewer workers when within 5% of the best wall time
    for w, c, r in table:
        if r["wall_s"] <= best[2]["wall_s"] * 1.05:
            best = (w, c, r)
            break
    w, chunk, r = best
    speedup = serial_s / r["wall_s"] if r["wall_s"] > 0 else 0.0
    mem_total = (a.mem_per_worker_mb or 0) * w + (a.parent_mem_mb or 0)

    warnings = []
    if speedup < 1.0:
        warnings.append(f"processes are slower than serial ({speedup:.2f}x): stay serial, vectorize (numpy, "
                        "batch the work), or use threads if the work releases the GIL")
    elif speedup < 1.5:
        warnings.append(f"only {speedup:.2f}x faster than serial: probably not worth the complexity")
    if a.item_ms < 1 and r["ipc_share"] > 0.3:
        warnings.append(f"task too small for processes: {a.item_ms:g} ms/item and {r['ipc_share']:.0%} of the "
                        "work is IPC/pickling; batch items (map over lists of rows) or use larger chunks")
    elif r["ipc_share"] > 0.5:
        warnings.append(f"IPC/pickling is {r['ipc_share']:.0%} of the work: send paths/ids instead of payloads, "
                        "return smaller results, or share arrays via multiprocessing.shared_memory")
    if r["parent_s"] >= r["compute_s"] * 0.95 and w > 1:
        warnings.append("the parent process is the bottleneck (pickling/dispatch); more workers will not help")
    if r["wall_s"] > 0 and r["startup_s"] / r["wall_s"] > 0.25:
        warnings.append(f"start-up/init is {r['startup_s'] / r['wall_s']:.0%} of the wall time: reuse one pool "
                        "across batches, keep workers alive (service), or use fewer workers")
    if cap_mem is not None and cap_mem < min(cores, a.items):
        if cap_mem == 0:
            warnings.append(f"memory limit {mem_limit:.0f} MB cannot fit even one worker of "
                            f"{a.mem_per_worker_mb:g} MB: shrink the model (quantize, ONNX) or raise the limit")
        else:
            warnings.append(f"memory limit caps workers at {cap_mem} (of {cores} cores): {a.mem_per_worker_mb:g} MB "
                            f"per worker x {cap_mem} within {MEM_HEADROOM:.0%} of {mem_limit:.0f} MB")
    if a.items < cores:
        warnings.append(f"only {a.items} items for {cores} cores: split items further to use all cores")
    if a.payload_kb >= 1024 or a.result_kb >= 1024:
        warnings.append("per-item payload/result >= 1 MB: use shared memory, memory-mapped files or paths")
    if method == "fork" and a.init_s > 0:
        warnings.append("fork: heavy read-only state loaded in the parent before the pool starts is shared "
                        "copy-on-write (call gc.freeze() first); never after CUDA init")
    if method in ("spawn", "forkserver") and a.init_s > 0:
        warnings.append(f"{method}: every worker pays --init-s itself; load it in the pool initializer, not per "
                        "task")

    scaling = []
    for tw, tc, tr in table:
        if tw in (1, 2, 4, 8, 16, 32, 64, 128) or tw in (w, cap):
            scaling.append({"workers": tw, "chunksize": tc, "wall_s": round(tr["wall_s"], 3),
                            "speedup": round(serial_s / tr["wall_s"], 2) if tr["wall_s"] else 0.0})
    return {
        "inputs": {"items": a.items, "item_ms": a.item_ms, "payload_kb": a.payload_kb, "result_kb": a.result_kb,
                   "init_s": a.init_s, "mem_per_worker_mb": a.mem_per_worker_mb, "parent_mem_mb": a.parent_mem_mb},
        "start_method": method, "cores": cores, "cores_source": core_src,
        "mem_limit_mb": round(mem_limit, 1) if mem_limit else None, "mem_limit_source": mem_src,
        "worker_caps": {"cpu": cap_cpu, "memory": cap_mem, "items": a.items},
        "recommended": {"workers": w, "chunksize": chunk, "chunks": r["n_chunks"]},
        "estimate": {"serial_s": round(serial_s, 3), "parallel_s": round(r["wall_s"], 3),
                     "speedup": round(speedup, 2), "efficiency": round(speedup / w, 2),
                     "startup_s": round(r["startup_s"], 3), "parent_dispatch_s": round(r["parent_s"], 3),
                     "ipc_share": round(r["ipc_share"], 3)},
        "memory_mb": {"per_worker": a.mem_per_worker_mb, "total": round(mem_total, 1)},
        "scaling": scaling,
        "warnings": warnings,
    }


def fmt_s(s):
    if s < 1:
        return f"{s * 1000:.0f} ms"
    if s < 120:
        return f"{s:.2f} s"
    if s < 7200:
        return f"{s / 60:.1f} min"
    return f"{s / 3600:.2f} h"


def cmd_plan(args, ap):
    for name in ("items",):
        if getattr(args, name) is None or getattr(args, name) <= 0:
            ap.print_usage(sys.stderr)
            print(f"error: --{name} must be a positive integer", file=sys.stderr)
            return 2
    checks = [("item_ms", args.item_ms, False), ("payload_kb", args.payload_kb, True),
              ("result_kb", args.result_kb, True), ("init_s", args.init_s, True),
              ("mem_per_worker_mb", args.mem_per_worker_mb, True), ("mem_limit_mb", args.mem_limit_mb, True),
              ("parent_mem_mb", args.parent_mem_mb, True)]
    for name, val, zero_ok in checks:
        if val is not None and (val < 0 or (val == 0 and not zero_ok) or math.isnan(val) or math.isinf(val)):
            ap.print_usage(sys.stderr)
            print(f"error: --{name.replace('_', '-')} must be {'>= 0' if zero_ok else '> 0'}", file=sys.stderr)
            return 2
    if args.cores is not None and args.cores <= 0:
        ap.print_usage(sys.stderr)
        print("error: --cores must be a positive integer", file=sys.stderr)
        return 2
    res = plan(args)
    gate_failed = args.min_speedup is not None and res["estimate"]["speedup"] < args.min_speedup
    if args.json:
        res["gate"] = None if args.min_speedup is None else {"min_speedup": args.min_speedup,
                                                              "passed": not gate_failed}
        print(json.dumps(res, indent=2))
    else:
        e, rec = res["estimate"], res["recommended"]
        print(f"Plan: {args.items} items x {args.item_ms:g} ms, payload {args.payload_kb:g} KB, "
              f"result {args.result_kb:g} KB, init {args.init_s:g} s/worker")
        print(f"Cores: {res['cores']} ({res['cores_source']})   start method: {res['start_method']}")
        caps = res["worker_caps"]
        cap_txt = f"cpu {caps['cpu']}" + (f", memory {caps['memory']}" if caps["memory"] is not None else "")
        print(f"Worker caps: {cap_txt}" + (f"   (memory limit {res['mem_limit_mb']:.0f} MB from "
                                           f"{res['mem_limit_source']})" if res["mem_limit_mb"] else ""))
        print()
        print(f"Recommended workers:   {rec['workers']}")
        print(f"Recommended chunksize: {rec['chunksize']}   ({rec['chunks']} chunks)")
        print(f"Estimated wall time:   {fmt_s(e['parallel_s'])} vs serial {fmt_s(e['serial_s'])}   "
              f"speedup {e['speedup']:.2f}x, efficiency {e['efficiency']:.0%}")
        print(f"Start-up + init:       {fmt_s(e['startup_s'])}")
        print(f"IPC/pickling share:    {e['ipc_share']:.1%} of total work "
              f"(parent dispatch {fmt_s(e['parent_dispatch_s'])})")
        if args.mem_per_worker_mb:
            print(f"Memory:                {res['memory_mb']['total']:.0f} MB total "
                  f"({args.mem_per_worker_mb:g} MB x {rec['workers']} workers"
                  + (f" + parent {args.parent_mem_mb:g} MB" if args.parent_mem_mb else "") + ")")
        print()
        print("Scaling (best chunksize per worker count):")
        print("  workers  chunksize      wall   speedup")
        for row in res["scaling"]:
            print(f"  {row['workers']:>7}  {row['chunksize']:>9}  {fmt_s(row['wall_s']):>8}  {row['speedup']:>7.2f}x")
        if res["warnings"]:
            print()
            print("Warnings:")
            for w in res["warnings"]:
                print(f"  - {w}")
        print()
        print(f"Code: ProcessPoolExecutor(max_workers={rec['workers']}, mp_context=get_context("
              f"\"{res['start_method']}\")) ... ex.map(fn, items, chunksize={rec['chunksize']})")
        if gate_failed:
            print(f"GATE FAILED: estimated speedup {e['speedup']:.2f}x < --min-speedup {args.min_speedup:g}")
    return 1 if gate_failed else 0


# ====================================================================== main

def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", metavar="{check,plan}")
    c = sub.add_parser("check", help="lint multiprocessing / ProcessPoolExecutor code (AST only, never executed)")
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
    p = sub.add_parser("plan", help="capacity planner: workers, chunksize, wall time, IPC share, memory")
    p.add_argument("--items", type=int, required=True, help="number of work items (N)")
    p.add_argument("--item-ms", type=float, required=True, help="serial CPU time per item in ms (measure it)")
    p.add_argument("--payload-kb", type=float, default=1.0, help="pickled argument size per item, KB (default 1)")
    p.add_argument("--result-kb", type=float, default=1.0, help="pickled result size per item, KB (default 1)")
    p.add_argument("--init-s", type=float, default=0.0,
                   help="per-worker initializer time in s (model/tokenizer load; default 0)")
    p.add_argument("--cores", type=int, help="usable cores (default: process_cpu_count/affinity/cgroup cpu.max)")
    p.add_argument("--mem-per-worker-mb", type=float, help="peak RSS per worker in MB (model + working set)")
    p.add_argument("--mem-limit-mb", type=float,
                   help="memory budget in MB (default when --mem-per-worker-mb is set: cgroup memory.max or "
                        "MemAvailable)")
    p.add_argument("--parent-mem-mb", type=float, default=0.0, help="parent process RSS in MB (default 0)")
    p.add_argument("--start-method", choices=["fork", "spawn", "forkserver"],
                   help="default: platform default (Linux: forkserver on 3.14+, fork before; else spawn)")
    p.add_argument("--min-speedup", type=float, help="exit 1 if the estimated speedup is below this (CI gate)")
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return ap, c, p


def main(argv=None):
    ap, c, p = build_parser()
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    if args.cmd == "check":
        return cmd_check(args, c)
    if args.cmd == "plan":
        return cmd_plan(args, p)
    ap.print_usage(sys.stderr)
    print("error: choose a subcommand: check or plan", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
