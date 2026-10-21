# Hang Triage Playbook

From "it is stuck" to a named cause in minutes: classify with cheap signals, capture stacks, build the
wait-for graph, match a known shape, fix, and prove the fix with a test that fails by timeout.

## Contents

- [The five questions](#the-five-questions)
- [Decision tree](#decision-tree)
- [Hang classes and their fingerprints](#hang-classes-and-their-fingerprints)
- [Capturing evidence in the right order](#capturing-evidence-in-the-right-order)
- [Reading a thread dump](#reading-a-thread-dump)
- [Reading an asyncio task dump](#reading-an-asyncio-task-dump)
- [Building the wait-for graph](#building-the-wait-for-graph)
- [Symptom -> evidence -> cause -> fix](#symptom---evidence---cause---fix)
- [Worked example 1: two agent tasks, two asyncio locks](#worked-example-1-two-agent-tasks-two-asyncio-locks)
- [Worked example 2: GPU worker threads](#worked-example-2-gpu-worker-threads)
- [Worked example 3: event loop blocked by a sync SDK](#worked-example-3-event-loop-blocked-by-a-sync-sdk)
- [Worked example 4: the job that never exits](#worked-example-4-the-job-that-never-exits)
- [When the dump is not enough](#when-the-dump-is-not-enough)
- [Closing the loop](#closing-the-loop)

## The five questions

Ask these before reading any code. Each one takes seconds.

1. **Is the CPU busy?** `top -p PID` / `ps -o pid,pcpu,stat,nlwp -p PID`. 100% of one core means Python is
   executing (spin, livelock, catastrophic regex, huge pure-Python loop). Near 0% means everyone is waiting.
2. **Did output stop or just slow down?** Throughput dropping gradually to zero is starvation (leaked
   permits, connections, full queues). A sudden stop is a deadlock or a single blocked call.
3. **Is it asyncio?** If yes: does the loop still run callbacks? A heartbeat task that logs every second
   answers this. Heartbeats continuing means tasks are suspended (async deadlock / lost wakeup / slow IO);
   heartbeats stopping means sync code blocks the loop thread.
4. **Does it reproduce?** If yes, re-run under `hang_watchdog.py`. If not, attach to the live process
   (py-spy, gdb, `python -m asyncio ps`) and arrange for automatic dumps next time (`install()`,
   faulthandler).
5. **What changed?** A new lock, a new `await` inside a locked region, a bounded queue, a library upgrade
   that went sync, a switch to `fork`, a new signal handler, a different Python (3.14 forkserver default,
   free-threaded build).

## Decision tree

```
process alive, no progress
├── CPU ~100% on one core
│   ├── same Python frame in two dumps 5 s apart ............ spin / livelock / regex backtracking
│   └── frames move ......................................... slow, not hung: profile (py-spy top)
├── CPU ~0%
│   ├── asyncio?
│   │   ├── loop BLOCKED (no callbacks run) ................. sync call on the loop thread
│   │   └── loop responsive, tasks waiting
│   │       ├── tasks wait on locks held by each other ...... async lock-order deadlock
│   │       ├── task waits on a lock it holds ............... non-reentrant asyncio.Lock
│   │       ├── task waits on Event/Condition/Future ........ lost wakeup / unresolved future
│   │       ├── task waits on queue.join()/get()/put() ...... task_done missing / consumer died
│   │       └── task waits on a socket/stream ............... IO without timeout
│   └── threads
│       ├── threads in `with lock` forming a cycle .......... lock-order deadlock
│       ├── all pool workers waiting on .result() ........... executor self-wait / pool exhaustion
│       ├── parent in join(), child in queue feeder ......... multiprocessing Queue not drained
│       ├── child stuck right after fork .................... lock inherited from fork
│       └── one thread in C code, others idle ............... GIL held / blocking C call
└── work finished but process does not exit .................. non-daemon thread, executor, atexit
```

## Hang classes and their fingerprints

| Class | CPU | Thread dump | Task dump (asyncio) | Typical root cause |
|-------|-----|-------------|---------------------|--------------------|
| Deadlock (lock cycle) | 0% | 2+ threads in `with lock_x:` lines | 2+ tasks awaiting `Lock.acquire` | inconsistent lock order |
| Self-deadlock | 0% | 1 thread in `acquire` of a lock it holds | task awaiting a lock acquired earlier in its own chain | non-reentrant lock + helper that locks |
| Lost wakeup | 0% | thread in `Condition.wait`/`Event.wait` | task awaiting `Event.wait`/`Future` | notify before wait, no predicate loop, setter crashed |
| Unresolved future | 0% | loop idle in `select` | task awaiting a bare `Future` | resolver crashed or forgot error path |
| Loop blocked | 0-100% | loop thread inside a sync call | loop BLOCKED; one task RUNNING | `time.sleep`, `requests`, `.result()`, CPU work |
| IO without timeout | 0% | thread in `recv`/`read`/`connect` | task awaiting a stream/socket read | server never answers, no read timeout |
| Livelock | 100% | frames move between retry/backoff code | tasks cycle between sleep and retry | retry loop without progress/jitter |
| Starvation | low | many threads in `acquire` of a semaphore/pool | many tasks awaiting `Semaphore.acquire` | permits leaked on errors |
| Pool exhaustion | 0% | every worker in `.result()` | tasks awaiting `run_in_executor` | nested submits to the same executor |
| Shutdown hang | 0% | `threading._shutdown` in main, worker in `get()` | n/a | non-daemon thread with no stop signal |
| Fork deadlock | 0% | child stuck in `acquire` in logging/allocator code | n/a | fork in a multi-threaded process |
| GIL held | 100% or 0% | Python dumper does not answer; faulthandler shows a C call | n/a | extension that never releases the GIL |

## Capturing evidence in the right order

Capture before you kill: the stack of a hung process is the only reliable evidence.

1. **Two dumps, 5-10 s apart.** Identical stacks mean a hang; moving stacks mean slowness.
2. **Threads and tasks.** Threads alone are not enough for asyncio (suspended tasks have no thread stack);
   tasks alone are not enough when the loop is blocked.
3. **Process facts.** `ps -o pid,ppid,pgid,stat,pcpu,nlwp,etime -p PID`, open files and sockets
   (`ls -l /proc/PID/fd`, `ss -tp | grep PID`), child processes (`pstree -p PID`).
4. **Logs around the stop time.** The last line before silence often names the item being processed.

| You have | Do this |
|----------|---------|
| A reproducible command | `python scripts/hang_watchdog.py --dump-after 30 --kill-after 120 cmd.py args` |
| A long job that stalls sometimes | `--idle 120` plus `heartbeat()` in the main loop, `--dump-file hang.txt` |
| A live process you cannot restart | `py-spy dump --pid PID` (add `--native` if threads sit in C code) |
| A live 3.14 asyncio process | `python -m asyncio pstree PID` |
| Nothing installed, Linux | `gdb -p PID -batch -ex "thread apply all py-bt"` (needs CPython gdb helpers) |
| Your own code, before the next incident | `from hang_watchdog import install; install()`, or `faulthandler.register(SIGUSR1)` |

## Reading a thread dump

A `hang_watchdog.py` summary for two GPU worker threads (real output, trimmed):

```
--- summary ---
thread 'MainThread' main: dead_thread_deadlock.py:38 in main: t.join()  (inside threading.py:1133 in join: ...)   [join]
thread 'cache-refresher': dead_thread_deadlock.py:27 in cache_refresher: with model_lock:   [lock acquire]
thread 'gpu-batch-worker': dead_thread_deadlock.py:20 in gpu_batch_worker: with tokenizer_lock:   [lock acquire]
```

How to read it:
- The summary shows the innermost **user** frame of each thread and, in parentheses, the innermost frame
  overall (often stdlib). The bracket is a guess at what the line blocks on.
- A `with x:` line at the top of a stack means the thread is **waiting to acquire** `x`. Every enclosing
  `with` further down the same stack is a lock it **holds**. Here `gpu-batch-worker` holds `model_lock`
  (line 18 in its full stack) and waits for `tokenizer_lock`; `cache-refresher` holds `tokenizer_lock` and
  waits for `model_lock`. That is the cycle.
- `MainThread` in `join()` is a victim, not a cause. Ctrl+C will not help either: the main thread waits in
  `join()` with no timeout.

faulthandler output reads in the opposite direction ("most recent call first") and shows thread ids instead
of names (on 3.14 it also prints the OS-level thread name in brackets, truncated to 15 characters). py-spy prints thread names and the innermost frame
first.

## Reading an asyncio task dump

```
event loop _UnixSelectorEventLoop in thread 'MainThread': responsive (every task is suspended: ...); 3 task(s)
task 'Task-1' [waiting]: dead_async_lock_order.py:32 in main: await asyncio.gather(
    awaiting gather of 'upsert-task' (pending), 'summarise-task' (pending)
task 'summarise-task' [waiting]: dead_async_lock_order.py:26 in memory_then_index: async with index_lock:
    awaiting `index_lock` <asyncio.locks.Lock object at 0x7a72ff3f5160 [locked, waiters:1]>
task 'upsert-task' [waiting]: dead_async_lock_order.py:19 in index_then_memory: async with memory_lock:
    awaiting `memory_lock` <asyncio.locks.Lock object at 0x7a72ff0d91d0 [locked, waiters:1]>
```

- **responsive** means a callback scheduled with `call_soon_threadsafe` ran within 0.5 s: the loop is fine,
  the tasks are stuck. **BLOCKED** means synchronous code is running in the loop thread; read that thread's
  stack and the task marked `RUNNING and blocking the loop`.
- Each task line shows its deepest user frame: the exact `await`/`async with` it is suspended on.
- `awaiting` names the primitive (and its variable name when it can be found) or the awaited task/gather.
  `[locked, waiters:1]` tells you somebody holds it and one task waits.
- `Task-1` waiting on a gather is a victim. The two lock waiters are the cycle: `upsert-task` holds
  `index_lock` (its outer `async with` on line 17) and waits for `memory_lock`; `summarise-task` holds
  `memory_lock` and waits for `index_lock`.
- Name your tasks (`asyncio.create_task(coro, name="upsert-task")`, TaskGroup `create_task(..., name=)`);
  `Task-17` tells you nothing at 3 a.m.

## Building the wait-for graph

Write one line per stuck thread/task: `NAME holds {A, B} waits-for C (owner: ?)`. Then fill in owners:

| Waiting on | Who can wake it |
|------------|-----------------|
| Lock / RLock | the current holder (find the stack with an enclosing `with` on it) |
| Semaphore | any holder releasing; if no task holds a permit, permits leaked |
| Event | whoever calls `set()`; if nothing references the event, nobody |
| Condition | a `notify()` after the predicate changed, under the same lock |
| Queue `get()` | a producer `put()`; if producers finished, you need a sentinel or `shutdown()` |
| Queue `put()` (bounded) | a consumer `get()`; if consumers died, nobody |
| Queue `join()` | `task_done()` for every item ever `put()` |
| Future | `set_result`/`set_exception`/`cancel` by whoever holds a reference |
| Task / gather | completion of that task (recurse into it) |
| `thread.join()` / `p.join()` | the thread/process returning (recurse into its stack) |
| socket / stream read | the remote side, or your timeout |

A **cycle** in this graph is a deadlock. A node whose waker is "nobody" is a lost wakeup or leak. A chain
ending in an external system (socket) is an IO hang: add a timeout.

## Symptom -> evidence -> cause -> fix

| Symptom | Evidence to collect | Cause | Fix |
|---------|---------------------|-------|-----|
| asyncio service stops answering, CPU idle | task dump: tasks in `async with lock` on each other's locks | async lock-order cycle | single order or single lock; never hold a lock across an await of another lock-taking call |
| One request hangs forever, others fine | its task awaits a lock acquired earlier in its own await chain | `asyncio.Lock` re-entry | `_locked` helper pattern |
| All requests slow by N seconds, then fine | debug-mode log `Executing <Task ...> took N seconds` | sync call on the loop | `to_thread`, async client |
| All requests stop, one core busy | loop BLOCKED; RUNNING task in a CPU loop | CPU work on the loop | `ProcessPoolExecutor`/`InterpreterPoolExecutor` (3.14) via `run_in_executor` |
| Batch job stops at item k | main in `queue.join()`, workers idle in `get()` | `task_done()` skipped on exceptions | `try/finally: task_done()` |
| Pipeline stops after the consumer raised | producer in `await q.put()` on a full queue | consumer died, producer not told | TaskGroup cancels producer; `shutdown()` |
| Agent step never returns | task awaits a bare Future | tool runner never resolved it | resolve in `finally`, timeout per step |
| Throughput decays to zero after errors | tasks in `Semaphore.acquire`, nobody holds permits | permits leaked on exceptions | `async with sem:` |
| Thread pool job never finishes | every worker in `.result()` of a nested submit | pool exhaustion | separate pools or flatten |
| Multiprocessing job hangs at the end | parent in `p.join()`, child in feeder flush | Queue not drained before join | drain, then join |
| Workers hang at start (Linux, fork) | child in `acquire` inside logging/allocator | fork with threads | spawn/forkserver |
| Ctrl+C ignored | main in `join()`/`get()` without timeout | uninterruptible wait | waits with timeouts in a loop; daemon helpers |
| Script prints "done" but never exits | `threading._shutdown` waiting on a non-daemon thread | shutdown hang | stop event + join; daemon; executor `shutdown(cancel_futures=True)` |
| Jupyter cell hangs / errors with "already running" | nested `run_until_complete` | loop already running | top-level `await` |
| Hang only on the free-threaded build | lock-order cycles the GIL used to serialize | real races now visible | lock hierarchy, `hang_scan.py` |

## Worked example 1: two agent tasks, two asyncio locks

**Symptom:** a research agent stops after "agent started"; CPU 0%.
**Evidence:** watchdog dump above: two tasks waiting on each other's locks, loop responsive.
**Cause:** `index_then_memory` takes index -> memory; `memory_then_index` takes memory -> index, and both
`await` an LLM call while holding the first lock.
**Fix:** one order (index before memory) in both, and keep LLM calls outside locks:

```python
import asyncio

index_lock = asyncio.Lock()
memory_lock = asyncio.Lock()


async def summarise(text: str) -> str:
    await asyncio.sleep(0.01)  # stands in for an LLM call
    return text[:10]


async def memory_then_index(note: str) -> str:
    summary = await summarise(note)          # slow work outside any lock
    async with index_lock, memory_lock:      # canonical order everywhere
        return summary


print(asyncio.run(memory_then_index("a long note about vectors")))  # a long not
```

**Verify:** `python scripts/hang_scan.py agent.py --select DLK001` is clean; a test runs both tasks
concurrently 100 times under `asyncio.timeout(5)`.

## Worked example 2: GPU worker threads

**Symptom:** embedding service stalls under load, never at low load.
**Evidence:** thread dump: `gpu-batch-worker` in `with tokenizer_lock` holding `model_lock`;
`cache-refresher` in `with model_lock` holding `tokenizer_lock`.
**Cause:** lock-order cycle that only bites when both run concurrently.
**Fix:** a lock hierarchy (model=1, tokenizer=2) enforced at runtime in tests with an ordered-lock wrapper
(see [prevention-and-testing.md](prevention-and-testing.md#lock-hierarchy-enforced-at-runtime)), or merge the two
locks: they always protect one logical resource.

## Worked example 3: event loop blocked by a sync SDK

**Symptom:** FastAPI p99 jumps from 300 ms to 30 s; CPU low; all endpoints slow at once.
**Evidence:** `PYTHONASYNCIODEBUG=1` logs `Executing <Task pending name='Task-12' coro=<chat() ...>> took
4.812 seconds`; a dump shows the loop BLOCKED in `requests/adapters.py ... recv_into`.
**Cause:** an `async def` route calls a synchronous HTTP client.
**Fix:** use the async client, or keep the sync client in a `def` route (runs in the thread pool), or wrap
the call: `await asyncio.to_thread(client.complete, prompt)`. See
[ai-engineering-hangs.md](ai-engineering-hangs.md#fastapi-endpoints-calling-sync-clients).

## Worked example 4: the job that never exits

**Symptom:** ingestion prints "done" and sits there; Ctrl+C prints a `KeyboardInterrupt` traceback in
`threading._shutdown` and keeps hanging.
**Evidence:** at exit the main thread is in `threading._shutdown` -> `lock.acquire`; a non-daemon
`metrics-flusher` thread is in `queue.get()` with no timeout.
**Cause:** interpreter shutdown joins every non-daemon thread; the flusher waits for an item that never comes.
**Fix:** give the thread a stop signal and join it with a timeout before returning from `main()`:

```python
import queue
import threading

stop = threading.Event()
metrics: queue.Queue = queue.Queue()


def flusher() -> None:
    while not stop.is_set():
        try:
            item = metrics.get(timeout=0.1)
        except queue.Empty:
            continue
        print("flush", item)


t = threading.Thread(target=flusher, name="metrics-flusher")
t.start()
metrics.put({"docs": 3})
stop.set()
t.join(timeout=5)
print("alive after join:", t.is_alive())
# flush {'docs': 3}
# alive after join: False
```

## When the dump is not enough

- **Python dumper does not answer** (`[in-process dumper did not answer ...]`): the GIL is held by C code or
  the interpreter is wedged. Read the faulthandler C-level dump the watchdog falls back to, then
  `py-spy dump --native --pid PID` or `gdb -p PID -ex "thread apply all bt"` for C frames.
- **The stack is inside a third-party client** (`httpx`, `grpc`, `psycopg`): check its timeout defaults
  (many default to none), connection pool limits (a pool of 10 with 10 leaked connections hangs forever),
  and whether it is safe across `fork`.
- **Different every time**: you may be looking at a livelock or slowness. Take 5 dumps and count frames,
  or run `py-spy top`/`py-spy record`.
- **Only in production**: install `install()` or `faulthandler.register(SIGUSR1)` at startup and add a
  heartbeat watchdog thread that dumps when progress stops ([prevention-and-testing.md](prevention-and-testing.md#watchdogs-and-heartbeats)).

## Closing the loop

Every hang fix ships with three things:
1. **The cause removed** (order, ownership, wakeup guarantee), not just a longer timeout.
2. **A bounded wait** at the place it hung, so a regression becomes an exception with a stack trace
   instead of a silent stall.
3. **A test** that reproduces the interleaving deterministically (events/barriers forcing the bad
   order) and fails within seconds, plus `hang_scan.py --strict` in CI.
