# Debugging and Troubleshooting Asyncio

How to find blocking calls, hangs, deadlocks, lost exceptions and leaks in async code, plus the observability
that makes them visible in production before users notice.

## Contents

- [Triage table](#triage-table)
- [Error messages decoded](#error-messages-decoded)
- [Debug mode](#debug-mode)
- [Finding blocking calls](#finding-blocking-calls)
- [Event-loop lag monitor](#event-loop-lag-monitor)
- [Debugging hangs](#debugging-hangs)
- [Deadlock patterns](#deadlock-patterns)
- [Lost exceptions and never-awaited coroutines](#lost-exceptions-and-never-awaited-coroutines)
- [Resource leaks](#resource-leaks)
- [Observability in production](#observability-in-production)
- [Profiling](#profiling)

## Triage table

| Symptom | First check | Likely cause | Fix |
|---------|-------------|--------------|-----|
| All requests slow at once, CPU low | loop lag monitor, debug-mode slow callbacks | blocking call on the loop (sync HTTP, `time.sleep`, big file read) | async client / `to_thread` |
| All requests slow at once, CPU 100% on one core | `py-spy dump` | CPU-bound work on the loop (JSON of 50 MB, tokenizing, regex) | process pool |
| Throughput flat as concurrency rises | Semaphore size, client pool size, provider 429s | pool smaller than semaphore; rate limit; global lock | match pool to semaphore, rate limiter |
| Process never exits | `asyncio.all_tasks()` dump | non-daemon thread, executor job stuck, task awaiting forever | timeouts, cancel leftovers, daemon threads |
| Hang at `queue.join()` | count `get` vs `task_done` | missing `task_done()` on error path, or dead worker | `task_done` in `finally`, catch per item |
| Hang on shutdown / Ctrl+C ignored | grep `except BaseException`, `except CancelledError` | cancellation swallowed | re-raise (lint AIO014) |
| Memory grows steadily | queue sizes, task count over time | unbounded queue, tasks per item, retained results | bounded queue, sliding window |
| `Too many open files` | open sockets per process | client per request, unclosed responses | one client, `async with` |
| Random `RuntimeError: ... different loop` | where primitives/clients are created | object created under one loop, used under another | create inside `asyncio.run` / lifespan |
| Results silently wrong / missing | `return_exceptions=True` handling | exceptions treated as results | `isinstance(r, BaseException)` |
| Works locally, 429 storm in prod | concurrency x replicas | unbounded fan-out, retries in lockstep | rate limiter, jittered backoff |

Run `python scripts/async_lint.py <path>` first: it finds most of these causes statically.

## Error messages decoded

| Message | Meaning | Fix |
|---------|---------|-----|
| `RuntimeWarning: coroutine 'x' was never awaited` | a coroutine object was created and garbage-collected without running | add `await`, or schedule it as an owned task |
| `Task exception was never retrieved` | a task failed and nobody awaited it or called `.exception()` | TaskGroup, or await/gather it, or a done callback that logs |
| `Task was destroyed but it is pending!` | the loop closed (or the task was GC'd) while the task was still running | keep references; cancel and await tasks before the loop closes |
| `RuntimeError: asyncio.run() cannot be called from a running event loop` | nested `asyncio.run` (common in Jupyter, or sync wrapper called from async code) | `await` the coroutine; in Jupyter use top-level `await` |
| `RuntimeError: This event loop is already running` | `loop.run_until_complete` inside a coroutine | `await` |
| `RuntimeError: no running event loop` | `get_running_loop()`/`create_task()` called from sync code with no loop | call from inside a coroutine, or start a loop with `asyncio.run` |
| `RuntimeError: Event loop is closed` | something used the loop after `asyncio.run` returned (often a client's `__del__`) | close clients explicitly before the loop ends |
| `... got Future <...> attached to a different loop` | an asyncio object created under loop A awaited under loop B | create clients/primitives inside the loop that uses them |
| `RuntimeError: cannot reuse already awaited coroutine` | the same coroutine object awaited twice (e.g. in a retry loop) | pass a factory: `lambda: client.call(x)` |
| `TypeError: object X can't be used in 'await' expression` | awaiting a sync function's result | the client is sync: use the async client or `to_thread` |
| `RuntimeWarning: Enable tracemalloc to get the object allocation traceback` | accompanies the never-awaited warning | run with `-X tracemalloc=20` or debug mode |
| `Executing <Task ...> took 1.234 seconds` | debug mode: one step held the loop longer than `slow_callback_duration` | find the blocking call in that task |
| `Unclosed client session` / `Unclosed connector` (aiohttp) | `ClientSession` never closed | `async with aiohttp.ClientSession()` |
| `ResourceWarning: unclosed transport` | stream/transport not closed | `writer.close(); await writer.wait_closed()` |
| `ExceptionGroup: unhandled errors in a TaskGroup (2 sub-exceptions)` | two children failed | inspect `eg.exceptions`, handle with `except*` |
| `asyncio.InvalidStateError: Result is not set.` | `task.result()` called before the task finished | await it first (or read after the TaskGroup block) |

## Debug mode

Enable any of:
- `PYTHONASYNCIODEBUG=1 python app.py`
- `python -X dev app.py` (dev mode: asyncio debug + more warnings)
- `asyncio.run(main(), debug=True)` or `loop.set_debug(True)`

What it adds:
- Logs every callback/task step slower than `loop.slow_callback_duration` (default 0.1 s) on the `asyncio`
  logger: `Executing <Task ...> took 0.512 seconds`.
- Never-awaited coroutine warnings include where the coroutine was created.
- Raises `RuntimeError` when non-threadsafe loop methods are called from another thread.
- Logs unclosed transports and slow DNS/IO selector calls; tasks keep their creation traceback.

It costs performance; use it in development, CI and when reproducing a production issue.

```python
import asyncio
import logging
import time


class Collect(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


async def blocking_handler() -> None:
    time.sleep(0.2)               # the bug: blocks the loop for 200 ms
    await asyncio.sleep(0)


async def main() -> None:
    loop = asyncio.get_running_loop()
    loop.slow_callback_duration = 0.05
    await asyncio.create_task(blocking_handler(), name="handle-request-42")


handler = Collect()
logging.getLogger("asyncio").addHandler(handler)
logging.getLogger("asyncio").setLevel(logging.WARNING)
asyncio.run(main(), debug=True)
slow = [m for m in handler.messages if m.startswith("Executing")]
print("slow step logged:", bool(slow), "| names the task:", "handle-request-42" in slow[0])
# Output: slow step logged: True | names the task: True
```

Naming tasks (`create_task(..., name=...)`, `tg.create_task(..., name=...)`) makes these logs and task dumps
far easier to read.

## Finding blocking calls

1. Static: `python scripts/async_lint.py src/ --select AIO001,AIO002,AIO003,AIO004,AIO005,AIO006,AIO016`.
2. Debug mode slow-callback logs (above) name the task; the culprit runs between two of its awaits.
3. `py-spy dump --pid <PID>` while the service stalls shows the Python stack of the loop thread; a frame inside
   `requests`, `socket.recv`, `time.sleep` or a C extension is the blocker. `py-spy top` for CPU hot spots.
4. Third-party wrappers sometimes hide sync calls inside `async def` (an "async" SDK method that calls a sync
   client internally). The lag monitor below catches those in production.

## Event-loop lag monitor

A heartbeat task that measures how late it wakes up. Lag above ~50-100 ms means something is blocking the
loop. Export it as a metric (gauge or histogram).

```python
import asyncio
import time


async def monitor_loop_lag(samples: list[float], interval: float = 0.02) -> None:
    loop = asyncio.get_running_loop()
    while True:
        start = loop.time()
        await asyncio.sleep(interval)
        samples.append(loop.time() - start - interval)     # how late we woke up


async def main() -> None:
    samples: list[float] = []
    monitor = asyncio.create_task(monitor_loop_lag(samples), name="loop-lag-monitor")
    await asyncio.sleep(0.1)
    time.sleep(0.15)                 # simulate a blocking call somewhere in a handler
    await asyncio.sleep(0.1)
    monitor.cancel()
    try:
        await monitor
    except asyncio.CancelledError:
        pass
    print("max lag over 100 ms:", max(samples) > 0.1)


asyncio.run(main())
# Output: max lag over 100 ms: True
```

## Debugging hangs

Dump every task's stack: where each one is waiting tells you who is waiting on whom. Dump before cancelling:
a timeout that cancels the stuck task also removes it from `asyncio.all_tasks()`.

```python
import asyncio
import io


async def waits_forever(event: asyncio.Event) -> None:
    await event.wait()                       # nobody ever calls event.set()


def dump_tasks() -> str:
    out = io.StringIO()
    for task in asyncio.all_tasks():
        out.write(f"--- {task.get_name()} done={task.done()}\n")
        task.print_stack(limit=5, file=out)
    return out.getvalue()


async def main() -> None:
    event = asyncio.Event()
    stuck = asyncio.create_task(waits_forever(event), name="index-builder")
    done, _ = await asyncio.wait({stuck}, timeout=0.05)   # wait() does not cancel on timeout
    if not done:
        report = dump_tasks()                            # dump while the task is still stuck
        print("index-builder" in report, "waits_forever" in report)
        stuck.cancel()


asyncio.run(main())
# Output: True True
```

Tools for live processes:
- **3.14:** `python -m asyncio ps <PID>` lists all tasks of a running Python process with their names and
  coroutine stacks; `python -m asyncio pstree <PID>` shows the await tree (which task awaits which). Both use
  the remote-debugging support added in 3.14 and may need ptrace permissions (root or
  `/proc/sys/kernel/yama/ptrace_scope` = 0).
- **3.14:** `asyncio.capture_call_graph(task)` / `asyncio.print_call_graph(task)` print the await chain from
  inside the process (useful in a debug endpoint).
- Any version: install a signal handler that logs `dump_tasks()` (`loop.add_signal_handler(signal.SIGUSR1,
  ...)` on Unix), or expose it on an admin-only debug endpoint.
- `faulthandler.dump_traceback_later(timeout, repeat=True)` prints all **thread** stacks periodically;
  it shows a loop thread stuck in a blocking call even when no asyncio code can run.
- `py-spy dump --pid` (all threads, native frames with `--native`).
- `aiomonitor` (third party) gives a telnet console with task listing and cancellation for running apps.

## Deadlock patterns

| Pattern | Why it deadlocks | Fix |
|---------|------------------|-----|
| `await queue.join()` but a worker skipped `task_done()` on error | unfinished count never reaches 0 | `task_done()` in `finally` |
| All workers dead (exception escaped), producer blocked on `put()` to a full queue | nobody consumes | catch per item; supervise workers (TaskGroup) |
| `threading.Lock` held across `await`, second task acquires it | the loop thread blocks on a lock its own task holds | `asyncio.Lock` (lint AIO016) |
| Task A awaits B's result while B waits on an Event A sets later | circular wait | restructure; add timeouts to surface it |
| `asyncio.Lock` re-acquired by the same task | not reentrant | split the function; pass "already locked" state |
| Waiting on a future from `run_coroutine_threadsafe(...).result()` **on the loop thread** | blocks the loop that must run it | only call `.result()` from other threads; on the loop use `await asyncio.wrap_future(fut)` |
| Sync callback calls `asyncio.run` in a thread whose loop is busy | nested loops | use the existing loop via `run_coroutine_threadsafe` |
| Bounded `Semaphore` acquired twice in a nested call path | inner acquire waits for outer release | acquire at one level only |

Every network await with a timeout turns a silent deadlock into a `TimeoutError` with a stack trace, which is
a large part of why rule 4 ("every network await has a deadline") matters.

## Lost exceptions and never-awaited coroutines

```python
import asyncio
import gc
import warnings


async def save_usage(n: int) -> None:
    await asyncio.sleep(0)


async def main() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        save_usage(1)                        # bug: missing await
        gc.collect()
    print([str(w.message) for w in caught])


asyncio.run(main())
# Output: ["coroutine 'save_usage' was never awaited"]
```

- Make warnings visible in tests: `-W error::RuntimeWarning` or pytest `filterwarnings = ["error"]` turns
  never-awaited coroutines into test failures.
- `Task exception was never retrieved` is logged only when the task object is garbage-collected, which may be
  much later or at shutdown. Do not rely on it; own tasks and log in a done callback.
- Route the loop's exception handler to your logging (`loop.set_exception_handler`, see the cancellation
  reference) and make sure the `asyncio` logger is not filtered out.

## Resource leaks

- Enable `-X dev` or `-W default::ResourceWarning` to see unclosed sockets, transports, files and sessions.
- aiohttp logs `Unclosed client session` with the creation point in debug mode.
- Count open file descriptors over time (`len(os.listdir("/proc/self/fd"))` on Linux) as a metric for
  long-running workers.
- Async generators that are not exhausted keep their resources until finalized; use `contextlib.aclosing`.

## Observability in production

| Signal | How | Alert when |
|--------|-----|------------|
| Event-loop lag | heartbeat task above | p99 > 100 ms |
| In-flight requests per provider | gauge inc/dec around the call | pinned at the semaphore limit for minutes |
| Queue depth per pipeline stage | `queue.qsize()` sampled | grows steadily (consumer too slow) |
| 429 / 5xx / timeout counts | counters by provider and model | 429 rate > 1% |
| Retry count and give-ups | counters | rising give-ups |
| Task count | `len(asyncio.all_tasks())` sampled | grows without bound (leak) |
| Latency per stage | histograms (retrieve, rerank, generate, first token) | p95 regression |
| Tokens and cost | from `usage` | budget burn rate |

Logging: put the request id in a `contextvars.ContextVar` and add it with a logging filter; it propagates into
tasks and `to_thread` automatically. Tracing: OpenTelemetry's context also uses contextvars, so spans follow
`create_task`/`gather` without extra work; create one span per external call.

```python
import contextvars
import logging

request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id.get()
        return True


handler = logging.StreamHandler()
handler.addFilter(RequestIdFilter())
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"))
logging.getLogger().addHandler(handler)
```

## Profiling

- `py-spy record -o profile.svg --pid <PID>` samples without code changes; async frames appear as the
  coroutine functions being resumed.
- `yappi` with `set_clock_type("wall")` and coroutine-aware stats attributes wall time correctly across awaits.
- `cProfile` attributes time to the event loop's `select` call while waiting; useful for CPU hot spots, not
  for "where is time spent waiting".
- To measure where a request waits, time each await (stage histograms) rather than profiling.
