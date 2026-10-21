---
name: python-multiprocessing-pool-designer
description: "Design correct, fast process-based parallelism in Python: when processes beat threads/asyncio for CPU-bound code (and when free-threaded 3.13t/3.14t wins), multiprocessing.Pool (map, imap_unordered, starmap, apply_async callbacks), ProcessPoolExecutor (as_completed, max_tasks_per_child, mp_context, initializer), InterpreterPoolExecutor, fork vs spawn vs forkserver (3.14 Linux default), the __main__ guard, pickling rules, chunksize and IPC math, sizing workers to cores, cgroups and memory, per-worker model loading, copy-on-write and gc.freeze, shared_memory with numpy, Manager proxies, worker tracebacks, BrokenProcessPool, timeouts, Ctrl-C, worker logging, seeds, joblib/Ray/Dask/DataLoader. Ships a linter and a capacity planner. Use when parallelizing PDF/HTML parsing, chunking, tokenization, CPU embedding, image preprocessing, eval scoring or minhash dedup, or on PicklingError, BrokenProcessPool, 'bootstrapping phase', 'Cannot re-initialize CUDA in forked subprocess', or a pool slower than serial."
metadata:
  category: programming
  subcategory: python
  version: "1.0.0"
---

# Python Multiprocessing Pool Designer

Design process pools that are correct first and fast second: decide whether processes are the right tool at
all, pick the API and start method, make every task picklable and cheap to ship, size workers and chunksize
from measured numbers instead of guesses, load heavy state once per worker, share big data without copying it,
and make failure loud (exceptions, crashed workers, timeouts, Ctrl-C). `scripts/pool_tool.py check` finds the
mechanical mistakes statically; `scripts/pool_tool.py plan` turns "N items at X ms each" into workers,
chunksize, expected wall time and warnings before you write the code.

## Trigger Conditions

Activate this skill when the user:
- Wants to speed up CPU-bound Python: document parsing (PDF, HTML, DOCX), chunking, tokenizing a corpus,
  regex/feature extraction, CPU embedding or reranking, image resizing, eval scoring, minhash/dedup
- Uses or reviews `multiprocessing.Pool`, `ProcessPoolExecutor`, `Process`, `Queue`, `Manager`,
  `shared_memory`, `joblib.Parallel`, `torch.multiprocessing` or `DataLoader(num_workers=...)`
- Sees `PicklingError: Can't pickle <function <lambda>>`, `Can't pickle local object`, `BrokenProcessPool`,
  `An attempt has been made to start a new process before ... bootstrapping phase`,
  `RuntimeError: context has already been set`, `Cannot re-initialize CUDA in forked subprocess`,
  `daemonic processes are not allowed to have children`, or `Queue objects should only be shared between
  processes through inheritance`
- Has a pool that is slower than serial, uses one core, runs out of memory, loses exceptions, or never exits
- Asks how many workers to use, what chunksize to pass, fork vs spawn, or how to load a model once per worker

## Workflow

```
1. CLASSIFY  -> Is the hot path CPU-bound Python? (profile; see the GIL skill). I/O-bound -> asyncio/threads.
2. MEASURE   -> item count N, ms per item, pickled arg/result KB, init seconds, RSS per worker
3. PLAN      -> python scripts/pool_tool.py plan --items N --item-ms X ... -> workers, chunksize, warnings
4. CHOOSE    -> API (executor vs Pool vs joblib/Ray/Dask) and start method (spawn/forkserver by default)
5. SHAPE     -> module-level task functions, initializer for heavy state, small args (paths/ids), chunks
6. HARDEN    -> main guard, error handling, timeouts, Ctrl-C, BrokenProcessPool, logging, seeds
7. CHECK     -> python scripts/pool_tool.py check src/ --strict
8. VERIFY    -> benchmark vs serial on real data, results identical, memory within limit, clean exit
```

## Step 1: Is a Process Pool the Right Tool?

The GIL lets one thread run Python bytecode at a time (on the default build). Processes side-step it, at the
price of start-up, pickling every argument and result, and one interpreter's memory per worker.

| Situation | Right tool | Why |
|-----------|-----------|-----|
| Pure-Python CPU work per item >= ~1 ms (parsing, chunking, regex, tokenizing with a Python tokenizer) | `ProcessPoolExecutor` / `Pool` | Real parallelism across cores |
| Work inside numpy / torch / polars / tokenizers (Rust) / PIL that releases the GIL | Threads, or the library's own parallelism | No pickling; threads already run in parallel |
| Network or disk I/O (LLM API calls, vector-DB writes, scraping) | asyncio (see `python-asyncio-pattern-advisor`) or threads | Waiting does not need cores |
| Tiny items (< 0.1 ms) in huge numbers | Vectorize or batch first, then maybe processes | IPC per item costs more than the work |
| CPU-bound and you control the interpreter | Free-threaded 3.13t / 3.14t + threads (see the `python-gil-bottleneck-analyzer` skill) | Shared memory, no pickling; 3.14 makes the build officially supported, but C extensions must support it |
| Need isolation per task in one process (3.14) | `InterpreterPoolExecutor` | Sub-interpreters with their own GIL; fewer libraries work there |
| Multi-machine, or data larger than RAM | Ray / Dask | Cluster scheduling, spilling |
| GPU inference | One process per GPU, batch inside it | Pools of GPU workers multiply CUDA contexts and VRAM |

Profile before parallelizing: if 80% of time is one numpy call, a pool will not help. For a hang, freeze or
"stuck at 99%", switch to [python-async-deadlock-debugger](../python-async-deadlock-debugger/SKILL.md).

## Step 2: Choose the API

| API | Use when | Watch out |
|-----|----------|-----------|
| `concurrent.futures.ProcessPoolExecutor` | Default choice: futures, `as_completed`, `BrokenProcessPool` on crashes, `max_tasks_per_child` (3.11) | `map` defaults to `chunksize=1`; `map` submits everything up front (3.14 adds `buffersize=`) |
| `multiprocessing.Pool` | `imap`/`imap_unordered` streaming with chunks, `maxtasksperchild`, callbacks | `with Pool()` exits with `terminate()`; a killed worker makes `map` hang forever |
| `multiprocessing.Process` + `Queue` | Long-lived pipeline stages (reader -> parsers -> writer) | Drain queues before `join()`; send sentinels |
| `InterpreterPoolExecutor` (3.14) | Isolated CPU work in one process | Many C extensions are not yet sub-interpreter safe |
| `joblib.Parallel` (loky) | Notebooks, lambdas/closures (cloudpickle), numpy memmapping | Reusable executor, different defaults |
| Ray / Dask | Clusters, object store, retries, out-of-core | Heavier operational footprint |
| `torch.utils.data.DataLoader(num_workers=k)` | Training/inference data loading | Seeds per worker, `persistent_workers`, `worker_init_fn` |

API details, signatures and version tags: [pool-api-reference.md](references/pool-api-reference.md).

## Step 3: Choose the Start Method

| Method | Default on | Start cost | Inherits parent memory | Safe with threads / CUDA / open clients |
|--------|-----------|-----------|------------------------|------------------------------------------|
| `fork` | Linux <= 3.13 | ~ms | Yes (copy-on-write) | No: locks copied mid-use; CUDA cannot re-init |
| `spawn` | macOS (3.8+), Windows | 50-500 ms + your imports | No: re-imports `__main__` | Yes |
| `forkserver` | Linux and other POSIX except macOS, 3.14+ | ~ms after the server starts | Only what the server preloaded | Yes (the server is single-threaded) |

Rules:
1. **Always guard the entry point.** spawn and forkserver re-import the main module in every child; pool
   creation at import time fails with the "bootstrapping phase" `RuntimeError`, and a `Pool` keeps
   respawning the failing workers forever.
2. **Prefer `get_context()` over `set_start_method()`.** A context is local and composable; the global
   setter may be called once per program and never from a library.
3. **Never fork after CUDA init, gRPC/HTTP client creation, or starting threads.** Use spawn/forkserver; 3.12+
   warns `DeprecationWarning: This process ... is multi-threaded, use of fork() may lead to deadlocks`.
4. **Write code that works under spawn** even on Linux: then 3.14's forkserver default and macOS just work.

```python
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor


def parse(path: str) -> int:
    return len(path)


def main() -> None:
    ctx = mp.get_context("spawn")                     # explicit, same on every OS
    with ProcessPoolExecutor(max_workers=4, mp_context=ctx) as ex:
        print(list(ex.map(parse, ["a.pdf", "bb.pdf"], chunksize=1)))   # [5, 6]


if __name__ == "__main__":
    main()
```

Full treatment (fork safety, preload, pickling protocol): [start-methods-and-pickling.md](references/start-methods-and-pickling.md).

## Step 4: Make Tasks Picklable and Cheap

Every task ships `(function reference, args)` to a worker and the result back, pickled. Functions travel by
qualified name, so the child must be able to import them.

| You pass | Result | Fix |
|----------|--------|-----|
| `lambda x: ...` | `PicklingError: ... not found as __main__.<lambda>` | Module-level `def` |
| Function defined inside a function | `Can't pickle local object` | Module-level `def` + `functools.partial` for parameters |
| `self.method` | Works, but pickles `self` with every task; fails if `self` holds a pool, lock, client or file | Module-level function taking only the data it needs |
| `partial(f, big_object)` | Pickles `big_object` with every chunk | Load it in the `initializer`, or share it |
| Open file, socket, DB/HTTP client, `threading.Lock` | `TypeError: cannot pickle '...' object` | Pass a path/URL, open in the worker |
| `multiprocessing.Queue` as a task arg | `RuntimeError: Queue objects should only be shared ... through inheritance` | Pass it via `initargs`, or use `Manager().Queue()` |
| Closures you cannot rewrite | Fails with stdlib pickle | `joblib` / `loky` (cloudpickle) |

Send **paths, ids or offsets, not payloads**; return compact results (ids + numbers, not full documents).

### Load heavy state once per worker

```python
import os
from concurrent.futures import ProcessPoolExecutor

_tokenizer = None                                    # one per worker process


def init_worker(vocab_path: str) -> None:
    global _tokenizer
    os.environ.setdefault("OMP_NUM_THREADS", "1")     # before importing torch/numpy in the worker
    _tokenizer = {w: i for i, w in enumerate(["the", "cat", "sat"])}   # stand-in for load(vocab_path)


def encode(text: str) -> list:
    return [_tokenizer.get(w, -1) for w in text.split()]


if __name__ == "__main__":
    with ProcessPoolExecutor(max_workers=2, initializer=init_worker, initargs=("vocab.json",)) as ex:
        print(list(ex.map(encode, ["the cat", "sat on"], chunksize=1)))   # [[0, 1], [2, -1]]
```

With torch in the worker add `torch.set_num_threads(1)` in the initializer, otherwise each worker starts one
intra-op thread per core and 8 workers fight over 8 cores with 64 threads.

## Step 5: Size Workers and Chunksize

Measure, then plan: `python scripts/pool_tool.py plan --items 120000 --item-ms 6 --payload-kb 4 --result-kb 1`.

- **Cores:** `os.process_cpu_count()` (3.13+) respects affinity; before that use `len(os.sched_getaffinity(0))`
  (Linux). Neither knows about a container's CPU quota: read cgroup `cpu.max` (the planner does). Never trust
  `os.cpu_count()` inside Kubernetes.
- **Hyperthreads:** CPU-bound numeric code often peaks at the number of physical cores; benchmark both.
- **Memory:** workers <= 0.85 x memory limit / peak RSS per worker. A model of 1.5 GB x 16 workers is 24 GB.
- **Chunksize:** each chunk costs one message round trip (~35-90 us measured, plus pickling ~0.5-13 us/KB
  depending on object shape). Aim for chunks of >= 20 ms of work and >= 4 chunks per worker for balance.
  `Pool.map` picks `ceil(N / (4 x workers))` itself; `imap`, `imap_unordered` and `ProcessPoolExecutor.map`
  default to 1.
- **Expectation:** speedup = serial / (start-up + init + max(work/workers, parent dispatch) + stragglers).
  If the parent's pickling time exceeds the per-worker work, more workers do nothing.

Formulas, constants and their measurement: [sizing-chunksize-and-memory.md](references/sizing-chunksize-and-memory.md).

## Canonical Template

```python
import concurrent.futures as cf
import logging
import multiprocessing as mp
from concurrent.futures.process import BrokenProcessPool

log = logging.getLogger("ingest")


def parse_doc(path: str) -> dict:
    if path.endswith(".bad"):
        raise ValueError(f"cannot parse {path}")
    return {"path": path, "chunks": len(path)}


def run(paths: list, workers: int = 4) -> tuple:
    ok, failed = [], []
    ctx = mp.get_context("spawn")
    with cf.ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as ex:
        futures = {ex.submit(parse_doc, p): p for p in paths}
        try:
            for fut in cf.as_completed(futures, timeout=3600):   # overall deadline
                path = futures[fut]
                try:
                    ok.append(fut.result())
                except BrokenProcessPool:
                    raise                                         # a worker died (OOM-kill, segfault)
                except Exception as exc:                          # task error: keep going, record it
                    log.warning("failed %s: %r", path, exc)
                    failed.append(path)
        except KeyboardInterrupt:
            ex.shutdown(wait=False, cancel_futures=True)
            raise
    return ok, failed


if __name__ == "__main__":
    good, bad = run(["a.pdf", "b.bad", "c.html"])
    print(sorted(d["path"] for d in good), bad)   # ['a.pdf', 'c.html'] ['b.bad']
```

For streaming with bounded memory use `Pool.imap_unordered(fn, iterable, chunksize=k)` (consumes the input
lazily) or submit in windows; `ProcessPoolExecutor.map` materializes all futures first (3.14: `buffersize=`).

## Sharing Data Between Processes

| Need | Use | Cost |
|------|-----|------|
| Large read-only numpy array | `multiprocessing.shared_memory` + `np.ndarray(buffer=shm.buf)` | Zero-copy; you manage `close()`/`unlink()` |
| Many shared blocks with automatic cleanup | `SharedMemoryManager` | Extra manager process |
| Large read-only data on Linux with fork | Load before the pool, `gc.freeze()`, fork | COW pages, dirtied by refcount writes on Python objects |
| On-disk arrays / embeddings | `np.memmap` / `np.load(mmap_mode="r")`, Arrow/Parquet memory map | OS page cache shared by all workers |
| Progress counters, small shared dict | `Manager().dict()` / `Value` | ~50-100 us per access: never in hot loops |
| Stream of results between stages | `multiprocessing.Queue` / `Pipe` | Drain before join; sentinels to stop |

Details and runnable examples: [sharing-data-between-processes.md](references/sharing-data-between-processes.md).

## Errors, Crashes and Shutdown

| Symptom | Cause | Fix |
|---------|-------|-----|
| Error shows only the parent stack | Traceback objects cannot be pickled | The worker stack is in `exc.__cause__` (`RemoteTraceback`); log with `exc_info` or catch and format in the worker |
| `BrokenProcessPool` after one bad document | A custom exception whose `__init__` signature differs from `args` failed to unpickle, or a worker died | Call `super().__init__(*all_args)` or define `__reduce__`; find the crash (OOM `dmesg`, segfault) |
| `Pool.map` never returns | A worker was killed (OOM) - Pool replaces it and waits forever; or an exception failed to unpickle | Use `ProcessPoolExecutor`, or `map_async(...).get(timeout=...)` |
| Results "disappear" | `apply_async` without `get()`/`error_callback`, `submit` without `result()` | Keep handles and collect; add `error_callback` |
| `r.get()` hangs after `with Pool()` | `__exit__` called `terminate()` | Collect results inside the block |
| Ctrl-C prints N tracebacks and hangs | SIGINT reaches every worker | Ignore SIGINT in the initializer; `terminate()`/`shutdown(cancel_futures=True)` in the parent |
| Memory grows until OOM | Leaks/fragmentation in long-lived workers | `maxtasksperchild` / `max_tasks_per_child` (3.11, not with fork) |
| Logs from workers missing or interleaved | Each process has its own handlers | `QueueHandler` in workers, `QueueListener` in the parent |
| Hangs on exit / at 99% | Unjoined processes, undrained queues, killed worker | See [python-async-deadlock-debugger](../python-async-deadlock-debugger/SKILL.md) |

There is no per-task timeout that kills a running task in either stdlib pool: `future.result(timeout=...)`
only stops waiting. To bound a task, run it in its own `Process` and `kill()` it, or recycle the pool
(3.14: `ProcessPoolExecutor.terminate_workers()` / `kill_workers()`). Recipes:
[debugging-and-failure-modes.md](references/debugging-and-failure-modes.md).

## Determinism and Seeds

- Results from `map`/`imap` are in input order; `imap_unordered`/`as_completed` are completion order. Sort by
  an id when order matters.
- With fork every worker inherits the same `random` / numpy RNG state: identical "random" augmentations.
  Seed per task from a stable key: `random.Random(hash((base_seed, doc_id)))` is not stable across runs
  (string hashing is salted); use `hashlib` or `numpy.random.SeedSequence(base).spawn(n)`.
- Per-task seeds (derived from the item) give the same output regardless of worker count or scheduling;
  per-worker seeds do not.
- Floating-point reductions in a different order differ in the last bits: reduce in a fixed order.

## AI-Engineering Patterns

| Job | Shape |
|-----|-------|
| RAG ingestion (PDF/HTML parse + chunk) | `imap_unordered` over paths, chunksize 1-4 for slow docs, per-task timeout via a watchdog, write results from the parent |
| Tokenizing a corpus | Shard by file/offset, worker reads its own shard, returns token counts or writes `.npy`; fast tokenizers already use threads (set `TOKENIZERS_PARALLELISM=false` before forking) |
| CPU embedding / reranking | Model loaded in the initializer, `torch.set_num_threads(1)`, batches of texts per task |
| Image preprocessing | Pass paths, write outputs to disk or shared memory, return metadata only |
| Eval scoring (BLEU, ROUGE, code execution) | Pool for CPU metrics; code-execution evals: one process per task with a hard kill timeout |
| Minhash dedup | Workers compute signatures for shards; LSH banding/merging in the parent |
| GPU work | `spawn` only, one process per device, never fork after `torch.cuda` init |

Worked, runnable versions: [ai-engineering-multiprocessing.md](references/ai-engineering-multiprocessing.md).

## Version Notes

| Version | Change |
|---------|--------|
| 3.8 | `shared_memory`, `SharedMemoryManager`; macOS default start method becomes spawn |
| 3.9 | `ProcessPoolExecutor.shutdown(cancel_futures=True)` |
| 3.11 | `ProcessPoolExecutor(max_tasks_per_child=...)` (defaults to spawn when given, rejects fork) |
| 3.12 | `DeprecationWarning` when forking a multi-threaded process |
| 3.13 | `os.process_cpu_count()` (executors and `Pool` default to it); `SharedMemory(track=False)`; free-threaded build (experimental, `python3.13t`) |
| 3.14 | forkserver default on Linux; `InterpreterPoolExecutor`; `Executor.map(buffersize=)`; `ProcessPoolExecutor.terminate_workers()`/`kill_workers()`; `Process.interrupt()`; free-threaded build officially supported |

## Output Format

When designing or reviewing process-parallel code, answer with:
1. **Verdict** - is a process pool the right tool (with the measured or estimated per-item cost), or should it
   be threads, asyncio, vectorization, free-threading or a cluster framework.
2. **Plan** - workers, chunksize, start method, expected speedup and memory (paste `pool_tool.py plan` output
   when numbers are known), and what to measure if they are not.
3. **Findings** - numbered, with location, MP rule id when the linter flagged it, the failure it causes
   (crash, hang, silent wrong answer, slowness) and severity.
4. **Code** - complete, runnable before/after: module-level task functions, initializer, guard, error
   handling, shutdown, logging.
5. **Verification** - benchmark vs serial, identical results check, memory ceiling, Ctrl-C and crash tests
   (see [testing-multiprocessing.md](references/testing-multiprocessing.md)).

## Scripts

```bash
# Lint (AST only; never imports or runs the analysed code)
python scripts/pool_tool.py check src/ingest/                        # files or directories
python scripts/pool_tool.py check worker.py --json                   # machine-readable
cat job.py | python scripts/pool_tool.py check -                     # stdin
python scripts/pool_tool.py check src/ --strict                      # exit 1 on any finding (CI gate)
python scripts/pool_tool.py check src/ --select MP001,MP002 --ignore missing-chunksize
python scripts/pool_tool.py check src/ --min-severity medium
python scripts/pool_tool.py check --list-rules                       # why + fix snippet per rule
```
Rules: MP001 pool-without-main-guard, MP002 unpicklable-callable, MP003 pool-not-closed, MP004
async-result-after-with, MP005 missing-chunksize, MP006 lost-async-exception, MP007 set-start-method-misuse,
MP008 fork-with-gpu-framework, MP009 global-mutation-in-worker, MP010 large-per-task-arg, MP011
manager-proxy-in-loop, MP012 join-before-drain, MP013 model-worker-no-recycle, MP014 mp-queue-passed-to-pool,
MP015 os-fork, MP016 keyboardinterrupt-unhandled, MP017 threads-before-fork, MP018 nested-pool-in-worker,
MP019 serialized-submit, MP020 pool-in-loop, MP021 thread-oversubscription. Silence a line with
`# noqa: MP005`. Exit codes: 0 clean (or not strict), 1 findings with `--strict`, 2 usage/read/syntax error
(directory walks warn and skip unparsable files).

```bash
# Capacity planner (deterministic; reads CPU count / cgroup limits only when not given)
python scripts/pool_tool.py plan --items 200000 --item-ms 4 --payload-kb 8 --result-kb 2 --cores 8
python scripts/pool_tool.py plan --items 5000 --item-ms 120 --init-s 6 --mem-per-worker-mb 1800 \
    --mem-limit-mb 8192 --parent-mem-mb 500 --start-method spawn --json
python scripts/pool_tool.py plan --items 1000000 --item-ms 0.02 --min-speedup 2   # exit 1 if not worth it
```
Prints recommended workers, chunksize, estimated wall time vs serial, speedup and efficiency, start-up cost,
IPC/pickling share, memory, a scaling table and warnings (task too small, parent bottleneck, init dominates,
memory caps workers, payload too large). Flags: `--items`, `--item-ms`, `--payload-kb`, `--result-kb`,
`--init-s`, `--cores`, `--mem-per-worker-mb`, `--mem-limit-mb`, `--parent-mem-mb`,
`--start-method {fork,spawn,forkserver}`, `--min-speedup`, `--json`.

## Additional Resources

| File | Content |
|------|---------|
| [pool-api-reference.md](references/pool-api-reference.md) | Pool, ProcessPoolExecutor, InterpreterPoolExecutor, Process, Queue/Pipe: every method, defaults, ordering, version tags |
| [start-methods-and-pickling.md](references/start-methods-and-pickling.md) | fork/spawn/forkserver, platform defaults, fork safety, main guard, what pickles and how to fix what does not |
| [sizing-chunksize-and-memory.md](references/sizing-chunksize-and-memory.md) | Core detection, cgroups, hyperthreads, memory per worker, chunksize math, the planner's formulas and constants |
| [sharing-data-between-processes.md](references/sharing-data-between-processes.md) | shared_memory + numpy, SharedMemoryManager, copy-on-write and gc.freeze, memmap, Arrow, Manager, Queue/Pipe |
| [ai-engineering-multiprocessing.md](references/ai-engineering-multiprocessing.md) | RAG ingestion, tokenization, CPU embedding, images, eval scoring, minhash dedup, CUDA and torch threads, joblib/Ray/Dask/DataLoader |
| [debugging-and-failure-modes.md](references/debugging-and-failure-modes.md) | Every MP rule with before/after, tracebacks, BrokenProcessPool, timeouts, Ctrl-C, logging, leaks, slow pools |
| [testing-multiprocessing.md](references/testing-multiprocessing.md) | Testing workers in-process, spawn in tests, timeouts, crash and Ctrl-C tests, determinism, benchmarks, CI |
