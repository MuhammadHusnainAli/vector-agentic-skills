---
name: python-async-deadlock-debugger
description: "Diagnose and fix hangs, deadlocks, livelocks and starvation in asyncio, threaded and multiprocessing Python: classify CPU spin vs blocked IO vs deadlock vs lost wakeup vs event loop blocked by sync code, collect evidence with faulthandler, py-spy dump, gdb py-bt, asyncio.all_tasks, python -m asyncio ps/pstree, debug mode and sys._current_frames, then fix lock-order cycles, non-reentrant asyncio.Lock re-acquisition, run_coroutine_threadsafe().result() on the loop thread, Queue.join without task_done, Condition lost wakeups, semaphore leaks, futures nobody resolves, nested event loops, thread pool exhaustion, multiprocessing Queue/fork deadlocks and shutdown hangs. Ships a static hang scanner and a watchdog that dumps every thread and asyncio task. Use when a Python program, agent loop, eval harness, embedding job, FastAPI service or GPU worker hangs, freezes, stops making progress, gets stuck at 99%, ignores Ctrl+C, never exits, or a test times out."
metadata:
  category: programming
  subcategory: python
  version: "1.0.0"
---

# Python Async Deadlock Debugger

Turn "it just hangs" into a named cause and a tested fix. First classify the hang from cheap signals (CPU
use, output, whether the event loop still runs callbacks), then capture stacks of every thread and every
asyncio task without guessing, match the stacks against a catalogue of known deadlock shapes, and fix the
cause, not the symptom: one lock order, timeouts on every wait, owned tasks, drained queues, resolved
futures. `scripts/hang_watchdog.py` runs a target and dumps all threads and tasks when it stalls;
`scripts/hang_scan.py` finds the same patterns statically before they ship.

## Trigger Conditions

Activate this skill when the user:
- Says a script, agent, eval run, embedding/ingestion job, training data pipeline or service "hangs",
  "freezes", "is stuck", "stops at 99%", "never finishes", "won't exit" or "ignores Ctrl+C"
- Has a FastAPI/Starlette endpoint whose latency explodes or that stops answering while CPU is idle
- Uses asyncio with `Lock`, `Queue`, `Event`, `Condition`, `Semaphore`, futures, `run_coroutine_threadsafe`,
  `run_in_executor`/`to_thread`, or mixes threads and an event loop
- Uses `threading`, `ThreadPoolExecutor`, `multiprocessing`/`ProcessPoolExecutor`, `os.fork`, signal handlers
- Sees `RuntimeError: This event loop is already running`, `asyncio.run() cannot be called from a running
  event loop`, `Executing <Task ...> took 2.3 seconds`, a pytest timeout, or a CI job killed after N minutes
- Asks how to get stack traces from a live or stuck Python process, or how to test for deadlocks

## Workflow

```
1. CLASSIFY  -> CPU busy or idle? Output stopped or slowed? Does the event loop still run callbacks?
                -> spin / livelock | blocked IO | deadlock | lost wakeup | loop blocked by sync code
2. CAPTURE   -> Re-run under: python scripts/hang_watchdog.py --dump-after 30 --kill-after 120 app.py
                Live process: py-spy dump --pid PID [--native]; kill -USR1 PID with faulthandler or install()
                3.14: python -m asyncio ps PID / pstree PID
3. READ      -> For each thread: what line is it blocked on? For each task: what does it await?
                Build the wait-for graph: who holds what, who waits for what; a cycle = deadlock
4. MATCH     -> Symptom -> cause table below; scan the code: python scripts/hang_scan.py src/
5. FIX       -> Remove the cycle (lock order, unlocked helper), make waits bounded (timeouts),
                guarantee wakeups (task_done/set_result/notify in finally), move blocking calls off the loop
6. VERIFY    -> Reproduce with a deterministic test that fails by timeout, not by hanging CI;
                re-run under the watchdog; python scripts/hang_scan.py src/ --strict
```

## Step 1: Classify the Hang

| Signal | Likely class | Next check |
|--------|--------------|------------|
| One core at 100%, no output | CPU spin / livelock / catastrophic regex / huge sync loop | `py-spy dump` twice: same frame = spin, moving frames = slow work |
| ~0% CPU, no output, process alive | deadlock, lost wakeup, unresolved future, IO without timeout | dump threads + tasks; look for waits on locks, queues, futures, sockets |
| 0% CPU, asyncio app, tasks all "waiting", loop responsive | async deadlock or lost wakeup (nobody will ever wake them) | which object each task awaits and who should set it |
| asyncio app, loop does not run callbacks, heartbeats stop | event loop blocked by sync code (`time.sleep`, `requests`, `.result()`, CPU) | thread stack of the loop thread shows the blocking call |
| Many threads in `acquire`/`join`/`get` and one in a C call | GIL held by a C extension, or pool exhaustion | `py-spy dump --native`, faulthandler C-level dump |
| Throughput decays to zero over hours | starvation: leaked semaphore permits, leaked connections, full bounded queue | count permits/pool size over time, look for acquire without finally |
| Work finishes but the process never exits | non-daemon thread, executor shutdown, atexit, multiprocessing feeder thread | dump at exit: which non-daemon thread is still alive |
| Ctrl+C does nothing | main thread blocked in `join()`/`get()` without timeout, or signal handler deadlock | thread dump; check signal handlers and `except BaseException` |
| Hangs only after `fork` / only in workers | lock inherited in locked state (logging, CUDA, BLAS, gRPC) | start method; `DLK017`; switch to spawn/forkserver |

A **deadlock** is a cycle of waits (A holds X waits Y, B holds Y waits X). A **lost wakeup** is a waiter whose
notifier already fired or will never fire. A **livelock** burns CPU retrying without progress (two agents
backing off in lock-step, a retry loop that re-queues the same failing item). **Starvation** is progress
for some but not all (a leaked semaphore permit per error until zero remain).

## Step 2: Collect Evidence

| Situation | Tool | Command / code |
|-----------|------|----------------|
| You can re-run it | watchdog (dumps threads + asyncio tasks, then kills) | `python scripts/hang_watchdog.py --dump-after 30 --kill-after 120 job.py` |
| Long job, stall at unknown time | watchdog in idle mode + `heartbeat()` | `python scripts/hang_watchdog.py --idle 120 --kill-after 7200 -m pkg.job` |
| Live process, cannot restart | py-spy (no code changes; needs ptrace permission) | `py-spy dump --pid PID --native` |
| Live process, py-spy unavailable | gdb with the CPython extension | `gdb -p PID -batch -ex "thread apply all py-bt"` |
| Live asyncio process on 3.14 | built-in task introspection | `python -m asyncio ps PID`, `python -m asyncio pstree PID` |
| Your own app, prepared in advance | faulthandler / `install()` | `faulthandler.register(signal.SIGUSR1, all_threads=True)` then `kill -USR1 PID` |
| CI job or test that hangs | timed dump before the job is killed | `faulthandler.dump_traceback_later(600, exit=True)`, pytest `faulthandler_timeout = 300` |
| Event loop feels slow / stuck | asyncio debug mode | `PYTHONASYNCIODEBUG=1` or `asyncio.run(main(), debug=True)`; `loop.slow_callback_duration = 0.05` |
| Inside the process, from code | stdlib introspection | `sys._current_frames()`, `threading.enumerate()`, `asyncio.all_tasks()`, `task.print_stack()` |

```python
# Prepare any long-running service for hang forensics (stdlib only, Linux/macOS).
import faulthandler
import signal
import sys

faulthandler.enable()  # segfaults and aborts print a traceback
faulthandler.register(signal.SIGUSR1, file=sys.stderr, all_threads=True)  # kill -USR1 <pid>
faulthandler.dump_traceback_later(3600, repeat=True)  # periodic dump: "where is everyone after an hour?"
faulthandler.cancel_dump_traceback_later()  # cancel when the job finishes normally
```

faulthandler prints threads only. For asyncio you need task stacks too: a task suspended on `await` has no
thread stack, so a thread dump of a deadlocked asyncio app shows only the loop idling in `select()`. Use
`hang_watchdog.py` (or `from hang_watchdog import install`), which walks every task's full await chain and
reports what it awaits, or on 3.14 `python -m asyncio pstree PID`. Details: [tools-for-live-processes.md](references/tools-for-live-processes.md).

## Step 3: Read the Dump

A real `hang_watchdog.py` summary for two agent tasks taking two `asyncio.Lock`s in opposite order:

```
event loop _UnixSelectorEventLoop in thread 'MainThread': responsive (every task is suspended: look at what each one awaits); 3 task(s)
task 'summarise-task' [waiting]: dead_async_lock_order.py:26 in memory_then_index: async with index_lock:
    awaiting `index_lock` <asyncio.locks.Lock object at 0x7a72ff3f5160 [locked, waiters:1]>
task 'upsert-task' [waiting]: dead_async_lock_order.py:19 in index_then_memory: async with memory_lock:
    awaiting `memory_lock` <asyncio.locks.Lock object at 0x7a72ff0d91d0 [locked, waiters:1]>
```

Reading rules:
1. **Loop responsive + every task waiting** -> nothing is running; some wakeup will never come. Find, for each
   awaited object, who is supposed to release/set/put it, and whether that party is itself waiting.
2. **Loop BLOCKED** -> the loop thread is inside synchronous code; its thread stack names the culprit
   (`time.sleep`, `requests.get`, `fut.result()`, `thread.join()`, a CPU loop, a `threading.Lock`).
3. **Threads in `with lock_x:`** -> write down "thread T holds L1 (the outer `with` in its stack) and waits for
   L2"; a cycle across threads is a lock-order deadlock.
4. **Main thread in `join()` / `Queue.join()` / `get()`** -> the waited-for worker is the real suspect: dump
   its stack, check it is alive (`threading.enumerate()`), check it calls `task_done()`.
5. **Same frame in two dumps 10 s apart and high CPU** -> spin or livelock; moving frames -> just slow.

## Step 4: Symptom -> Cause -> Fix

| Evidence in the dump | Cause | Fix |
|----------------------|-------|-----|
| Two threads/tasks each in `with lock_b` / `with lock_a` | lock-order cycle (DLK001) | one global order; acquire both in sorted order; or one coarser lock |
| Task awaits a Lock it already holds higher in its own chain | `asyncio.Lock` is not reentrant (DLK002) | split into public locked method + private `_x_locked()` helper |
| Loop thread inside `threading.Lock.acquire` | thread lock taken on the loop (DLK003) | `asyncio.Lock` for task-shared state; `await asyncio.to_thread(...)` for thread-shared |
| Loop thread in `fut.result()` / `run_coroutine_threadsafe(...).result()` | blocking on work that needs this loop (DLK005/006) | `await asyncio.wrap_future(fut)`; just `await coro` inside the loop |
| `RuntimeError: This event loop is already running` / hang in Jupyter | nested `asyncio.run`/`run_until_complete` (DLK007) | `await` directly; top-level `await` in notebooks; one `asyncio.run` at the entry point |
| Main in `queue.join()`, workers idle in `get()` | `task_done()` missing or skipped on errors (DLK008) | `task_done()` in `finally`, exactly once per `get()` |
| Producer in `put()` on a full bounded queue, consumer gone | consumer crashed or stopped reading | supervise consumers (TaskGroup), `Queue.shutdown()` (3.13+), cancel producers |
| Waiter in `Condition.wait()`, notifier already finished | lost wakeup / no predicate loop (DLK010) | `cond.wait_for(predicate, timeout)`; set state before `notify` under the lock |
| All callers waiting in `sem.acquire()`, nobody holds work | semaphore leak on error path (DLK009) | `async with sem:`; never manual acquire/release across `await` without finally |
| Task awaiting a `Future` nobody references | unresolved future (DLK016) | resolve on every path, fail all pending futures when the resolver dies, `wait_for` |
| `gather` waiting on a task that waits on a cancelled/failed sibling | dependent task never woken | TaskGroup (cancels siblings), propagate failure to dependents explicitly |
| All pool workers in `.result()` on inner submits | executor self-wait / pool exhaustion (DLK012) | separate pools per level, or fan out leaf tasks from the caller |
| Parent in `p.join()`, child in feeder thread `send` | Process joined before its Queue drained (DLK014) | drain results first, then `join(timeout)` |
| `Popen.wait()` with `stdout=PIPE`, child blocked on `write` | OS pipe buffer full | `communicate(timeout=...)` or read the pipes in threads |
| Child process stuck in `acquire` right after start | fork while another thread held a lock (DLK017) | spawn/forkserver start method; never fork a threaded process |
| Main thread in a signal handler inside `logging`/lock code | non-reentrant work in a signal handler (DLK018) | handler sets a flag/Event only; `loop.add_signal_handler` in asyncio |
| Work done, process does not exit, non-daemon thread in `get()` | shutdown hang (DLK013) | stop event + `join(timeout)`; sentinels; `daemon=True` for disposable helpers |
| Everything stopped, one thread in C code, no Python dumper output | GIL held by a C extension | `py-spy dump --native`; release the GIL in the extension, or run it in a process |

Full catalogues with runnable bad/fixed code: [asyncio-deadlocks.md](references/asyncio-deadlocks.md) and
[threading-and-multiprocessing-deadlocks.md](references/threading-and-multiprocessing-deadlocks.md).

## Core Fixes

**Lock hierarchy.** Give every lock a level and only acquire upward; when two locks are needed, take them in
one canonical order everywhere.

```python
import threading

index_lock = threading.Lock()  # level 1
cache_lock = threading.Lock()  # level 2: never taken before index_lock


def upsert(batch: list) -> None:
    with index_lock, cache_lock:
        batch.clear()


def evict(keys: list) -> None:
    with index_lock, cache_lock:  # same order, even though only the cache is evicted
        keys.clear()
```

**asyncio.Lock is not reentrant.** Never call a method that takes the lock from code that already holds it.

```python
import asyncio


class EmbeddingCache:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._items: dict[str, list[float]] = {}

    async def get_or_embed(self, text: str) -> list[float]:
        async with self._lock:
            if text not in self._items:
                self._refresh_locked(text)  # helper assumes the caller holds the lock
            return self._items[text]

    async def refresh(self, text: str) -> None:  # public entry point takes the lock once
        async with self._lock:
            self._refresh_locked(text)

    def _refresh_locked(self, text: str) -> None:
        self._items[text] = [float(len(text))]
```

**Never block the loop thread on work that needs the loop.**

```python
import asyncio
import concurrent.futures


async def call_from_loop(pool: concurrent.futures.ThreadPoolExecutor, text: str) -> int:
    fut = pool.submit(len, text)
    return await asyncio.wrap_future(fut)  # not fut.result(): that freezes every task


def call_from_worker_thread(loop: asyncio.AbstractEventLoop, coro) -> object:
    # Only from a thread that is NOT running `loop`; always bound the wait.
    return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=30)
```

**Every wait is bounded; every wakeup is guaranteed.**

```python
import asyncio


async def worker(queue: asyncio.Queue, out: list) -> None:
    while True:
        doc = await queue.get()
        try:
            out.append(await asyncio.wait_for(embed(doc), timeout=30))
        except TimeoutError:  # asyncio.TimeoutError is TimeoutError since 3.11
            out.append(None)
        finally:
            queue.task_done()  # even on errors, or join() never returns


async def embed(doc: str) -> int:
    await asyncio.sleep(0.01)
    return len(doc)


async def main(docs: list) -> list:
    queue: asyncio.Queue = asyncio.Queue(maxsize=8)
    out: list = []
    workers = [asyncio.create_task(worker(queue, out)) for _ in range(4)]
    for d in docs:
        await queue.put(d)
    await asyncio.wait_for(queue.join(), timeout=300)
    for w in workers:
        w.cancel()
    await asyncio.gather(*workers, return_exceptions=True)
    return out


print(len(asyncio.run(main(["a", "bb", "ccc"]))))  # 3
```

**Permits are released on every path.** `async with limiter:` instead of `acquire()`/`release()`; a 429 or a
cancellation between a manual acquire and release leaks one permit forever, and a rate limiter with 8
permits dies after 8 errors.

## AI-Engineering Hangs

| Situation | Typical cause | Fix |
|-----------|---------------|-----|
| Agent loop stuck after a tool call | tool coroutine/HTTP call without timeout, or a future the tool runner never resolves | `asyncio.timeout()` per tool call, overall step budget, resolve/fail futures in `finally` |
| Streaming LLM consumer stops early, server stalls | producer blocks on full bounded queue / unclosed async generator | `aclose()` the stream, cancel the producer, `Queue.shutdown()` (3.13+) |
| Rate limiter deadlocks after a burst of 429s | semaphore permits leaked on exceptions | `async with sem:`, token bucket with timeouts, alert on available permits |
| GPU worker thread died, requests hang forever | futures for queued requests never failed | supervisor that fails every pending future when the worker exits; health check |
| FastAPI endpoint freezes all others | `async def` route calling sync client (`requests`, sync DB, `time.sleep`) | `def` route (thread pool), async client, or `await asyncio.to_thread(...)` |
| Celery/Ray worker hung | no task time limit; nested `ray.get` inside a single-threaded actor | `soft_time_limit`/`time_limit`; `ray.get(ref, timeout=...)`; `ray stack` |
| Eval harness stuck at 99% | one straggler request without a timeout; `as_completed` waits forever | per-item timeout + retry/record failure, global deadline, report stragglers |

Recipes: [ai-engineering-hangs.md](references/ai-engineering-hangs.md).

## Prevention Checklist

- A timeout on every network call, `queue.get`, `Event.wait`, `Future.result`, `join` and lock acquire that
  can wait on another party; a global deadline per job (`asyncio.timeout`, 3.11+; `wait_for` on 3.9/3.10)
- One documented lock order; no `await`/IO/callbacks while holding a lock; no lock taken in signal handlers
- Structured concurrency: `asyncio.TaskGroup` (3.11+) or an owned task set; no fire-and-forget tasks
- `task_done()`/`release()`/`set_result()` in `finally`; consumers supervised so producers fail fast
- Never fork a threaded process (spawn/forkserver; forkserver is the Linux default since 3.14)
- Watchdog in production: heartbeats + `faulthandler.register(SIGUSR1)` or `install()`; stack dump on stall
- Deadlock regression tests that fail by timeout in seconds, never by hanging CI; hang_scan in CI

Testing patterns and lock-order checkers: [prevention-and-testing.md](references/prevention-and-testing.md).

## Version Notes

| Version | Change relevant to hangs |
|---------|--------------------------|
| 3.9 | `asyncio.to_thread`; `Executor.shutdown(cancel_futures=True)`; asyncio primitives no longer accept `with await lock` |
| 3.10 | asyncio primitives no longer bind to a loop at construction (`loop=` removed) |
| 3.11 | `asyncio.TaskGroup`, `asyncio.timeout()`, `asyncio.Runner`, `asyncio.Barrier`; `asyncio.TimeoutError` is `TimeoutError` |
| 3.12 | eager task factory; `os.fork()` in a multi-threaded process emits `DeprecationWarning` |
| 3.13 | `Queue.shutdown()` for `queue.Queue` and `asyncio.Queue`; experimental free-threaded build (`python3.13t`) |
| 3.14 | `python -m asyncio ps/pstree PID`; `asyncio.capture_call_graph()`/`print_call_graph()`; `python -m pdb -p PID` and `sys.remote_exec()` (PEP 768); free-threading officially supported; forkserver default start method on Linux; `concurrent.interpreters` + `InterpreterPoolExecutor` |

## Output Format

When diagnosing, answer with:
1. **Classification** - spin, blocked IO, deadlock, lost wakeup, loop blocked, starvation or shutdown hang,
   with the evidence (CPU, dump lines) that supports it.
2. **Wait-for graph** - "task/thread A holds X, waits for Y; B holds Y, waits for X" (or "waits for Z,
   which nobody will ever set because ...").
3. **Root cause** - file:line and rule id (DLKxxx when hang_scan flags it).
4. **Fix** - complete before/after code, plus the timeout/guard that would have turned the hang into an error.
5. **Verification** - a deterministic test that fails within seconds on the old code, and the watchdog or
   hang_scan command that now passes.

If evidence is missing, give the exact capture command (watchdog, py-spy, faulthandler) instead of guessing.

## Scripts

```bash
# Static scan (AST only; never imports or runs the code). 18 rules, DLK001-DLK018.
python scripts/hang_scan.py src/                      # files and/or directories
python scripts/hang_scan.py app/agent.py --json       # machine-readable findings with why + fix
cat worker.py | python scripts/hang_scan.py -         # stdin
python scripts/hang_scan.py src/ --strict             # exit 1 on any finding (CI gate)
python scripts/hang_scan.py src/ --select DLK001,DLK002,reentrant-acquire --ignore DLK011,DLK015
python scripts/hang_scan.py --list-rules              # every rule with why and fix
```
Rules: DLK001 lock-order-cycle (with both code paths), DLK002 reentrant-acquire (one call level), DLK003
thread-lock-in-async, DLK004 sleep-in-async, DLK005 blocking-wait-in-async, DLK006 threadsafe-result-in-loop,
DLK007 nested-event-loop, DLK008 join-without-task-done, DLK009 acquire-without-finally, DLK010
condition-wait-no-loop, DLK011 wait-without-timeout (low), DLK012 executor-self-wait, DLK013
thread-never-joined, DLK014 process-join-before-drain, DLK015 bounded-put-no-consumer (low), DLK016
unresolved-future, DLK017 fork-with-threads, DLK018 lock-in-signal-handler. Silence a line with
`# noqa: DLK009`. Exit codes: 0 clean (or not strict), 1 findings with `--strict`, 2 usage error, unreadable
file or syntax error in a named file (directory walks warn and skip unparsable files).

```bash
# Runtime watchdog. THIS EXECUTES THE TARGET in a child process (own process group).
python scripts/hang_watchdog.py --dump-after 30 --kill-after 120 eval_harness.py --shard 3
python scripts/hang_watchdog.py --idle 60 --kill-after 3600 -m myproj.embed_job --batch 512
python scripts/hang_watchdog.py --dump-after 1 --kill-after 3 --json deadlock.py > report.json
python scripts/hang_watchdog.py --kill-after 900 --grace 5 --max-dumps 5 --dump-timeout 3 \
    --dump-file hang.txt --fail-on-dump --python python3.11 -- train.py --epochs 1
```
`--dump-after S` dumps once after S seconds; `--idle S` dumps when there is no output and no `heartbeat()`
for S seconds; `--kill-after S` (default 600) always terminates the whole process group (SIGTERM, then SIGKILL
after `--grace`). Each dump has a summary (every thread's blocking line, every event loop responsive or
BLOCKED, every task with what it awaits) and full stacks; if the in-process dumper does not answer within
`--dump-timeout` a C-level faulthandler dump is used. Leftover grandchildren are killed even after a normal
exit. Exit codes: 0 target exited 0, 1 target exited non-zero, 2 usage error, 3 hung and killed (or dumped,
with `--fail-on-dump`), 130 interrupted. Library use: `from hang_watchdog import install, dump_all, heartbeat`;
`install()` makes `kill -USR1 PID` print threads and asyncio tasks; `install(dump_after=300)` dumps on a timer.

## Additional Resources

| File | Content |
|------|---------|
| [hang-triage-playbook.md](references/hang-triage-playbook.md) | Symptom -> evidence -> cause -> fix walkthroughs, reading dumps, wait-for graphs, decision tree |
| [asyncio-deadlocks.md](references/asyncio-deadlocks.md) | Every asyncio hang pattern with runnable bad/fixed code: locks, queues, events, futures, gather, nested loops, Jupyter |
| [threading-and-multiprocessing-deadlocks.md](references/threading-and-multiprocessing-deadlocks.md) | Thread lock order, Condition, executors, pool exhaustion, multiprocessing queues/pipes, fork, logging, GIL, signals, shutdown |
| [tools-for-live-processes.md](references/tools-for-live-processes.md) | faulthandler, py-spy, gdb py-bt, asyncio ps/pstree, pdb -p, sys.remote_exec, sys._current_frames, debug mode, hang_watchdog |
| [ai-engineering-hangs.md](references/ai-engineering-hangs.md) | Agent tool calls, streaming consumers, rate limiters, GPU worker queues, FastAPI, Ray/Celery, eval harness at 99% |
| [prevention-and-testing.md](references/prevention-and-testing.md) | Timeouts everywhere, lock hierarchies, structured concurrency, watchdogs/heartbeats, deterministic deadlock tests |
