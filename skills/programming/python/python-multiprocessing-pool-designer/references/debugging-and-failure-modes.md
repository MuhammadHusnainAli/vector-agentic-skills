# Debugging and Failure Modes

What goes wrong with process pools, how to recognise it from the symptom, and the fix. Section 1 is a
symptom index; section 2 walks through every `pool_tool.py check` rule with before/after code; the rest
covers tracebacks, crashes, timeouts, shutdown, logging, leaks and slow pools. For hangs and deadlocks that
need live stack dumps (py-spy, faulthandler, gdb), use the
[python-async-deadlock-debugger](../../python-async-deadlock-debugger/SKILL.md) skill.

## Contents

- [1. Symptom index](#1-symptom-index)
- [2. Rule catalogue with fixes](#2-rule-catalogue-with-fixes)
- [3. Tracebacks from workers](#3-tracebacks-from-workers)
- [4. Worker crashes and BrokenProcessPool](#4-worker-crashes-and-brokenprocesspool)
- [5. Timeouts](#5-timeouts)
- [6. Ctrl-C and graceful shutdown](#6-ctrl-c-and-graceful-shutdown)
- [7. Logging from workers](#7-logging-from-workers)
- [8. Memory leaks and maxtasksperchild](#8-memory-leaks-and-maxtasksperchild)
- [9. "The pool is slower than serial"](#9-the-pool-is-slower-than-serial)
- [10. Inspecting live workers](#10-inspecting-live-workers)

## 1. Symptom index

| Symptom / message | Cause | Section / rule |
|-------------------|-------|----------------|
| `PicklingError: Can't pickle <function <lambda>>` / `Can't pickle local object` | Lambda or nested function sent to workers | MP002 |
| `An attempt has been made to start a new process before ... bootstrapping phase` | No `__main__` guard under spawn/forkserver | MP001 |
| Program prints the bootstrapping error in a loop forever | Same, with `multiprocessing.Pool` respawning workers | MP001 |
| `RuntimeError: context has already been set` | `set_start_method` called twice or at import time | MP007 |
| `Cannot re-initialize CUDA in forked subprocess` | fork after CUDA init | MP008 |
| `RuntimeError: Queue objects should only be shared between processes through inheritance` | `multiprocessing.Queue` as a task argument | MP014 |
| `AssertionError: daemonic processes are not allowed to have children` | Pool inside a Pool worker | MP018 |
| `NotImplementedError: pool objects cannot be passed between processes or pickled` | Bound method of an object holding the pool | MP002 |
| `TypeError: cannot pickle '_io.TextIOWrapper' object` (or `_thread.lock`, `SSLContext`) | Open handle/client/lock in args or on `self` | MP002, start-methods reference |
| `BrokenProcessPool: A process in the process pool was terminated abruptly` | Worker killed (OOM, segfault, `os._exit`) or an exception that cannot be unpickled | Section 4 |
| `Pool.map` never returns, CPU idle | Killed worker (Pool loses its task), unpicklable exception, or results read after `with` exited | Sections 4, MP004 |
| Exit hangs after work is done | Undrained queue, unjoined processes, non-daemon threads | MP012, deadlock skill |
| Parent's list/dict empty after the pool ran | Workers mutated their own copy of a global | MP009 |
| Failures vanish, job "succeeds" | `apply_async` without `get()`/`error_callback`, `submit` without `result()` | MP006 |
| 16 workers slower than 1 | Tiny tasks, chunksize 1, huge payloads, thread oversubscription | Section 9, MP005, MP010, MP021 |
| RSS grows until OOM-kill after hours | Leaks/fragmentation in long-lived workers | Section 8, MP013 |
| Ctrl-C prints N tracebacks, workers survive | SIGINT delivered to every process | Section 6, MP016 |
| Works on Linux, fails on macOS/Windows/3.14 | Code relied on fork | Start-methods reference |
| Worker logs missing or garbled | Handlers not configured in children / several writers on one file | Section 7 |
| `OSError: [Errno 24] Too many open files` | Pools created per request or in a loop and never closed | MP003, MP020 |
| `OSError: [Errno 28] No space left on device` creating SharedMemory | Docker `/dev/shm` 64 MB default | Sharing reference |

## 2. Rule catalogue with fixes

Each rule below is detected by `python scripts/pool_tool.py check`. Run `check --list-rules` for the one-line
fix of each; here is the reasoning and a fuller fix.

### MP001 pool-without-main-guard (high)

```text
# BEFORE                                  # AFTER
from multiprocessing import Pool          from multiprocessing import Pool
pool = Pool(8)                            def main():
out = pool.map(parse, paths)                  with Pool(8) as pool:
                                                  return pool.map(parse, paths)
                                          if __name__ == "__main__":
                                              main()
```
Also flagged: a module-level call `main()` (without the guard) when `main` starts processes.

### MP002 unpicklable-callable (high)

Lambdas, nested functions, `self.method` and `partial(lambda)` passed to `map`/`submit`/`apply_async`, as an
`initializer`, or as a `Process` target under spawn/forkserver. Move to module level; parametrize with
`functools.partial`; keep per-instance heavy state in worker globals set by the initializer.

### MP003 pool-not-closed (medium)

`pool = Pool(...)` with no `close()`+`join()` or `terminate()`, or `ex = ProcessPoolExecutor()` never shut
down. Use `with`, or a `try/finally`:

```text
pool = Pool(8)
try:
    results = pool.map(parse, paths)
    pool.close()
except BaseException:
    pool.terminate()
    raise
finally:
    pool.join()
```

Not flagged when the pool is returned, passed to another function, stored and closed elsewhere
(`self.pool.close()` in another method) or used in `with` later.

### MP004 async-result-after-with (high)

`AsyncResult`, `imap` iterators or lists of them created inside `with Pool()` and read after the block.
`Pool.__exit__` is `terminate()`: the work is gone and `get()` times out or hangs (`get(timeout=3)` raised
`TimeoutError` in testing on 3.11 and 3.14). Collect inside the block.

### MP005 missing-chunksize (medium)

`imap`/`imap_unordered` (default chunksize 1) or `ProcessPoolExecutor.map` (default 1) over a non-literal
iterable. Pass `chunksize` (planner) or batch items. `Pool.map`/`starmap` compute a chunksize and are not
flagged, nor are iterables whose name says they are already batched (`batches`, `batched(...)`, `shards`,
`partitions`).

### MP006 lost-async-exception (high)

`pool.apply_async(...)` / `map_async` / `starmap_async` whose result is discarded or stored and never read,
without `error_callback`; `executor.submit(...)` whose future is dropped. Keep the handles and call
`get()`/`result()`, or add `error_callback` (Pool) / `add_done_callback` that logs `fut.exception()`.

### MP007 set-start-method-misuse (medium)

`set_start_method()` at module level (outside the guard) or called a second time without `force=True`.
Use `get_context()`; call the global setter once, in the guard.

### MP008 fork-with-gpu-framework (high)

`set_start_method("fork")`, `get_context("fork")` or `os.fork()` in a module that imports torch,
tensorflow, jax, cupy, keras, vllm, pycuda, transformers or sentence_transformers. Use spawn.

### MP009 global-mutation-in-worker (high)

A task function mutates a module-level list/dict/set/Counter (append, `[k] =`, update, `global x; x = ...`)
that code outside the workers reads. Each process changes its own copy; the parent sees nothing. Return
values and merge in the parent. Lazy per-worker caches (`if _model is None: _model = load()`) and globals
used only by workers are not flagged.

### MP010 large-per-task-arg (medium)

A name bound to a file read (`.read()`, `read_text`, `json.load`, `np.load`, `pd.read_*`,
`load_dataset`, `from_pretrained`) or a huge literal is bound into `partial(f, big)`, repeated in a
`starmap` comprehension, wrapped in `itertools.repeat(big)`, or passed to `submit`/`apply_async` inside a
loop. Load it once per worker in the initializer, pass a path, or use shared memory.

### MP011 manager-proxy-in-loop (low)

A `Manager().dict()`/`list()`/`Namespace` proxy read or written inside a loop, either in the same function
or in a worker function that received the proxy as an argument. Each access is an IPC round trip. Use a
local dict and merge.

### MP012 join-before-drain (high)

`p.join()` on a process that feeds a `multiprocessing.Queue` before the first `queue.get()` in the same
function. Drain first, then join. The deadlock skill covers the mechanism (feeder thread, pipe buffer).

### MP013 model-worker-no-recycle (low)

The pool's initializer or task function loads a model (`from_pretrained`, `SentenceTransformer`,
`torch.load`, `joblib.load`, `spacy.load`, `InferenceSession`, ...) and the pool sets no
`maxtasksperchild` / `max_tasks_per_child`. Decide consciously: a generous limit (thousands of tasks) caps
memory growth at the cost of periodic reloads. `max_tasks_per_child` needs a non-fork context.

### MP014 mp-queue-passed-to-pool (high)

A `multiprocessing.Queue` passed in task arguments. Pass it once via `initializer`/`initargs` (inherited at
worker creation) or use `Manager().Queue()`.

### MP015 os-fork (medium)

Direct `os.fork()`/`os.forkpty()`. Use a multiprocessing context or `subprocess`. Libraries that must
support fork should register `os.register_at_fork` hooks.

### MP016 keyboardinterrupt-unhandled (low)

A pool `map`-family call inside a function named `main`, in a module that never mentions `KeyboardInterrupt`
or `SIGINT`. Note that `with ProcessPoolExecutor()` makes Ctrl-C wait for all queued work, because
`__exit__` is `shutdown(wait=True)`. See section 6.

### MP017 threads-before-fork (high)

A `threading.Thread` was started (or a `ThreadPoolExecutor` received work outside a `with` block) before a
process pool, `Process.start()` or `os.fork()` that uses fork - explicitly, or by default when the module
never chooses a start method (fork is the Linux default before 3.14). Create processes first, or use
spawn/forkserver. A thread that was `join()`ed before the fork is not flagged.

### MP018 nested-pool-in-worker (high)

A function run by `multiprocessing.Pool` (or by a `daemon=True` `Process`) creates a pool, executor or
process. Flatten the work into one pool. (`ProcessPoolExecutor` workers are not daemonic and may create
children, but nesting still oversubscribes cores.)

### MP019 serialized-submit (medium)

`pool.apply_async(...).get()`, `ex.submit(...).result()` or `pool.apply(...)` inside a loop: one task at a
time. Submit all, then collect.

### MP020 pool-in-loop (medium)

A pool or executor constructed inside a `for`/`while` body. Create it once outside the loop.

### MP021 thread-oversubscription (low)

The module imports torch, starts process workers, and nowhere calls `set_num_threads` or sets
`OMP_NUM_THREADS`. Set threads per worker in the initializer.

## 3. Tracebacks from workers

Traceback objects cannot be pickled. Both stdlib pools work around this: the worker formats its traceback
as text and the parent re-raises the original exception type with the text attached as `__cause__`
(`multiprocessing.pool.RemoteTraceback` / `concurrent.futures.process._RemoteTraceback`). Printing the
exception with its chain shows both stacks:

```python
import concurrent.futures as cf
import multiprocessing as mp
import traceback


def chunk(doc: str) -> list:
    return [doc[i] for i in range(len(doc) + 1)]      # IndexError on the last index


if __name__ == "__main__":
    with cf.ProcessPoolExecutor(1, mp_context=mp.get_context("spawn")) as ex:
        fut = ex.submit(chunk, "abc")
        try:
            fut.result()
        except IndexError as exc:
            text = "".join(traceback.format_exception(exc))
            print("worker frame visible:", "in chunk" in text)   # worker frame visible: True
```

(`traceback.format_exception(exc)` with a single argument needs 3.10+; on 3.9 pass
`(type(exc), exc, exc.__traceback__)`.)

Where tracebacks still get lost:
- `logger.error(str(exc))` or `print(exc)`: logs only the message. Use `logger.exception(...)` or
  `exc_info=exc`, which includes the chained cause.
- `error_callback=lambda e: errors.append(e)` then `str(e)`: keep the exception object and format it.
- Exceptions that cannot be unpickled (custom `__init__`): the pool breaks instead (section 4).
- Wrapping in the worker: if you must return errors as data, include `traceback.format_exc()` in the record.

```python
import multiprocessing as mp
import traceback


def safe_parse(path: str) -> dict:
    try:
        if path.endswith(".bad"):
            raise ValueError("corrupt xref table")
        return {"path": path, "ok": True}
    except Exception as exc:                              # error as data: never breaks the pool
        return {"path": path, "ok": False, "error": repr(exc), "trace": traceback.format_exc()}


if __name__ == "__main__":
    with mp.get_context("spawn").Pool(2) as pool:
        out = pool.map(safe_parse, ["a.pdf", "b.bad"])
    print([r["ok"] for r in out], "corrupt xref" in out[1]["trace"])   # [True, False] True
```

## 4. Worker crashes and BrokenProcessPool

| Event | ProcessPoolExecutor | multiprocessing.Pool |
|-------|--------------------|----------------------|
| Worker SIGKILLed (OOM killer), segfault in C extension, `os._exit()` | Every pending and running future fails with `BrokenProcessPool`; the executor is unusable | Worker replaced silently; its task never completes; `map()` blocks forever |
| Task exception whose class cannot be unpickled | `BrokenProcessPool` (observed on 3.11 and 3.14) | Result-handler thread dies with `TypeError`; `get()` never returns |
| `initializer` raises | `BrokenProcessPool` for all futures | Worker exits; Pool keeps respawning workers that keep failing |
| Result cannot be pickled in the worker | That future raises the pickling error | That task raises `MaybeEncodingError` |

Find the cause:
- `dmesg -T | grep -i -E "killed process|out of memory"` or `journalctl -k`: the OOM killer; container
  runtimes report `OOMKilled`.
- `p.exitcode` / executor worker exit codes: `-9` SIGKILL, `-11` SIGSEGV, `-6` SIGABRT.
- `faulthandler.enable()` in the initializer prints the Python stack of a worker that segfaults.
- Reproduce with one worker and the failing item: `fn(item)` in the parent.

Recovering in a batch job: collect the items whose futures failed with `BrokenProcessPool` (the crashing
item and every innocent item that was in flight or still pending), then re-run each suspect alone in a
fresh single-worker executor. Items that break their private pool are the culprits: quarantine them.

```python
import concurrent.futures as cf
import multiprocessing as mp
import os
from concurrent.futures.process import BrokenProcessPool


def parse(x: int) -> int:
    if x == 3:
        os._exit(1)                        # stand-in for a segfaulting parser / OOM kill
    return x * 2


def run_resilient(items: list, workers: int = 2) -> tuple:
    ctx = mp.get_context("spawn")
    results, suspects, quarantined = {}, [], []
    with cf.ProcessPoolExecutor(workers, mp_context=ctx) as ex:
        futs = {ex.submit(parse, x): x for x in items}
        for fut in cf.as_completed(futs):
            try:
                results[futs[fut]] = fut.result()
            except BrokenProcessPool:
                suspects.append(futs[fut])
    for x in sorted(suspects):                         # isolate: one fresh worker per suspect
        with cf.ProcessPoolExecutor(1, mp_context=ctx) as ex:     # noqa: MP020 (isolation on purpose)
            try:
                results[x] = ex.submit(parse, x).result(timeout=600)    # noqa: MP019
            except BrokenProcessPool:
                quarantined.append(x)
    return results, quarantined


if __name__ == "__main__":
    res, bad = run_resilient(list(range(6)))
    print(sorted(res), bad)   # [0, 1, 2, 4, 5] [3]
```

Isolation costs one pool start per suspect. With thousands of pending items, re-submit suspects to a new
multi-worker pool first and isolate only the ones that are in flight when it breaks again (bisection).

## 5. Timeouts

| Need | Mechanism | Stops the work? |
|------|-----------|-----------------|
| Deadline for the whole job | `as_completed(fs, timeout=T)`, `map(..., timeout=T)` (executor), `AsyncResult.get(timeout=T)` | No: raises in the parent; then shut down / terminate |
| Deadline per result | `fut.result(timeout=t)` | No |
| Kill a stuck task | Run it in its own `Process`, `join(t)`, then `kill()` | Yes |
| Kill all workers | `pool.terminate()`; 3.14 `ex.terminate_workers()` / `ex.kill_workers()` | Yes |
| Soft in-task deadline | `signal.alarm` in the worker (POSIX), cooperative checks in loops | If Python code runs |

Process-per-task with a hard timeout (for untrusted parsers or generated code):

```python
import multiprocessing as mp
import time


def risky(n: float, out) -> None:
    time.sleep(n)                               # stand-in for a parser that may never return
    out.put(f"done after {n}s")


def run_with_timeout(n: float, timeout: float) -> str:
    ctx = mp.get_context("spawn")
    out = ctx.SimpleQueue()
    p = ctx.Process(target=risky, args=(n, out), daemon=True)
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.kill()                                # SIGKILL: cannot be ignored
        p.join()                                # noqa: MP012 (killed; the result is tiny)
        return "timeout"
    return out.get() if p.exitcode == 0 else f"crashed ({p.exitcode})"


if __name__ == "__main__":
    print(run_with_timeout(0.1, 2.0), "|", run_with_timeout(10, 1.0))   # done after 0.1s | timeout
```

Reading `SimpleQueue` after `join` is safe here because the payload is tiny; for large outputs drain first
(MP012) or write the result to a file.

## 6. Ctrl-C and graceful shutdown

What happens on Ctrl-C: the terminal sends SIGINT to the whole foreground process group, so the parent
and every worker get `KeyboardInterrupt`. Workers print tracebacks; the parent may be blocked in `map()`
waiting for results that will never come.

Pattern: workers ignore SIGINT; the parent catches `KeyboardInterrupt`, terminates, and re-raises.

```python
import multiprocessing as mp
import signal
import time


def init_worker() -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)       # only the parent handles Ctrl-C


def work(x: int) -> int:
    time.sleep(0.01)
    return x


def main() -> int:
    pool = mp.get_context("spawn").Pool(2, initializer=init_worker)
    try:
        total = sum(pool.imap_unordered(work, range(50), chunksize=5))
        pool.close()
        return total
    except KeyboardInterrupt:
        pool.terminate()                                # stop now, discard pending work
        raise
    finally:
        pool.join()


if __name__ == "__main__":
    print(main())   # 1225
```

`ProcessPoolExecutor`: in `except KeyboardInterrupt:` call `ex.shutdown(wait=False, cancel_futures=True)`
(3.9) and re-raise; running tasks still finish unless you kill workers (3.14 `terminate_workers()`).
SIGTERM (Kubernetes, systemd): install a handler in the parent that sets a stop flag or raises, so the
same cleanup path runs; Kubernetes sends SIGKILL after `terminationGracePeriodSeconds`.

## 7. Logging from workers

Each process has its own logging configuration. Under spawn, workers start unconfigured (WARNING to
stderr, your handlers missing); under fork they inherit handlers, and several processes writing the same
file interleave or corrupt lines (and a handler lock held at fork time deadlocks the child).

Fix: workers send records through a queue; one listener in the parent owns the real handlers.

```python
import logging
import logging.handlers
import multiprocessing as mp


def init_logging(queue) -> None:
    root = logging.getLogger()
    root.handlers[:] = [logging.handlers.QueueHandler(queue)]
    root.setLevel(logging.INFO)


def work(x: int) -> int:
    logging.getLogger("worker").info("processing %d", x)
    return x


if __name__ == "__main__":
    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    records = []

    class Collect(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    listener = logging.handlers.QueueListener(queue, Collect())
    listener.start()
    try:
        with ctx.Pool(2, initializer=init_logging, initargs=(queue,)) as pool:
            pool.map(work, range(4))
    finally:
        listener.stop()                                 # flushes remaining records
    print(sorted(records))   # ['processing 0', 'processing 1', 'processing 2', 'processing 3']
```

Add `%(processName)s %(process)d` to the formatter so lines identify the worker. Structured logging
libraries (structlog, loguru with `enqueue=True`) offer the same queue-based design.

## 8. Memory leaks and maxtasksperchild

Long-lived workers grow because of genuine leaks (caches keyed by input, C extensions), allocator
fragmentation (glibc malloc arenas rarely return memory), and lazily loaded resources. Detection:
- Log `resource.getrusage(resource.RUSAGE_SELF).ru_maxrss` from workers every N tasks.
- `tracemalloc` snapshots in a single-worker run to find Python-level growth.
- Compare RSS after 1k vs 10k tasks with the same input distribution.

Mitigations: `Pool(maxtasksperchild=N)`, `ProcessPoolExecutor(max_tasks_per_child=N)` (3.11, non-fork
context), clearing caches explicitly, `MALLOC_ARENA_MAX=2` for glibc fragmentation, or jemalloc via
`LD_PRELOAD`. Pick N so that reload cost (init time) is < 1-2% of the work done between reloads:
`N >= 50 x init_s / item_s`.

## 9. "The pool is slower than serial"

Work through these in order (the planner quantifies most of them):

1. **Task too small.** `--item-ms` under ~1 ms with chunksize 1. Batch items or raise chunksize.
2. **Payload or result too big.** The parent pickles everything; `--payload-kb` in the hundreds makes the
   parent the bottleneck. Send paths/ids; write outputs in workers.
3. **Oversubscription.** Each worker's BLAS/torch uses all cores (MP021). Limit threads per worker.
4. **The work releases the GIL already.** numpy/torch/regex in C: threads were enough; processes added
   copies and pickling.
5. **Start-up and init repeated.** A pool per batch/request (MP020), or the model loaded per task. Create
   once, load in the initializer.
6. **Memory pressure.** Too many workers for RAM: swapping or page-cache eviction. Fewer workers.
7. **Serialized submission.** `submit().result()` in a loop (MP019).
8. **CPU quota.** Container limited to 2 CPUs while the pool started 64 workers. Size from cgroup quota.
9. **Disk-bound.** All workers reading from one slow disk/network share: the pool cannot help; profile I/O.

Quick experiment: run with 1, 2, 4, ... workers on 2% of the data and plot wall time; compare with
`pool_tool.py plan` predictions. Flat curves point at the parent (2), I/O (9) or oversubscription (3).

## 10. Inspecting live workers

- `ps -o pid,ppid,stat,rss,etime,cmd --ppid <parent_pid>`: list workers, state (`R` running, `S` sleeping,
  `D` disk wait, `Z` zombie) and memory. spawn workers show `-c from multiprocessing.spawn import
  spawn_main`; forkserver workers descend from the server process.
- `py-spy dump --pid <worker_pid>` (and `--native` for C frames): what each worker is doing.
- `py-spy top --pid <pid> --subprocesses`: sampling profile across the whole tree.
- `python -m pdb -p <pid>` and `sys.remote_exec()` (3.14) attach to a running interpreter.
- `cat /proc/<pid>/status | grep -E "VmRSS|Threads"`: thread count per worker reveals oversubscription.

Hang analysis (which lock, which queue) is covered step by step in the deadlock skill linked at the top.
