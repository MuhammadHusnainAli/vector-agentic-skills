# Asyncio Version History (3.7 -> 3.14)

What changed in each Python version that matters for writing asyncio code, and what to use when you must
support an older target. Items marked "verified" were checked against CPython 3.11 and 3.14 interpreters;
the rest follow the official "What's New" documents. When a detail differs between patch releases, the table
says so instead of guessing.

## Contents

- [Quick matrix](#quick-matrix)
- [3.7](#37)
- [3.8](#38)
- [3.9](#39)
- [3.10](#310)
- [3.11](#311)
- [3.12](#312)
- [3.13](#313)
- [3.14](#314)
- [Writing code for a range of versions](#writing-code-for-a-range-of-versions)
- [get_event_loop over time](#get_event_loop-over-time)
- [Free-threading and asyncio](#free-threading-and-asyncio)
- [Ecosystem notes](#ecosystem-notes)

## Quick matrix

| Feature | Minimum | Fallback for older targets |
|---------|---------|----------------------------|
| `asyncio.run`, `create_task`, `get_running_loop` | 3.7 | - |
| `CancelledError` is a `BaseException` | 3.8 | on 3.7 `except Exception` also caught cancellation |
| `python -m asyncio` REPL (top-level await) | 3.8 | IPython |
| Task names (`name=`, `set_name`) | 3.8 | - |
| `asyncio.to_thread` | 3.9 | `loop.run_in_executor(None, functools.partial(fn, ...))` |
| `Task.cancel(msg)` | 3.9 | - |
| `aiter()`, `anext()`, `contextlib.aclosing` | 3.10 | `x.__aiter__()`, `x.__anext__()`, a small aclosing helper |
| `asyncio.TaskGroup` | 3.11 | `anyio.create_task_group()` or gather + cancel-on-error helper |
| `asyncio.timeout` / `timeout_at` | 3.11 | `asyncio.wait_for` (single awaitable), `async_timeout` package |
| `asyncio.Runner` | 3.11 | `asyncio.run` per call |
| `asyncio.Barrier` | 3.11 | Condition + counter |
| `ExceptionGroup`, `except*` | 3.11 | `exceptiongroup` backport (`catch()`) |
| `Task.cancelling()`, `Task.uncancel()` | 3.11 | - |
| `asyncio.TimeoutError is TimeoutError` | 3.11 (verified) | catch `asyncio.TimeoutError` on 3.9/3.10 |
| `eager_task_factory`, `create_eager_task_factory` | 3.12 (verified absent in 3.11) | plain tasks |
| `asyncio.run(..., loop_factory=)` | 3.12 (verified) | `asyncio.Runner(loop_factory=...)` on 3.11, `uvloop.run` |
| `Queue.shutdown()`, `QueueShutDown` | 3.13 (verified absent in 3.11) | sentinel per worker or cancel workers |
| `async for` over `as_completed` (yields the original tasks) | 3.13 (verified on 3.14) | `for fut in as_completed(...): await fut` |
| `asyncio.EventLoop` alias | 3.13 | `asyncio.new_event_loop()` |
| `eager_start=` on `create_task`/`TaskGroup.create_task` | 3.14 (verified) | eager task factory (3.12) |
| `asyncio.capture_call_graph`, `print_call_graph` | 3.14 (verified) | `task.print_stack()` |
| `python -m asyncio ps <pid>` / `pstree <pid>` | 3.14 (verified) | task dumps via signal handler, py-spy |
| `get_event_loop()` raises when no loop is set | 3.14 (verified) | use `get_running_loop` / `asyncio.run` |

## 3.7

- `asyncio.run()`, `asyncio.create_task()`, `asyncio.get_running_loop()`, `asyncio.current_task()`,
  `asyncio.all_tasks()` added; `async`/`await` became reserved keywords.
- Context variables (`contextvars`) integrated: each task runs in a copy of the context.
- `loop.start_tls()`, `loop.sock_sendfile()`, `BufferedProtocol` added.

## 3.8

- `asyncio.CancelledError` now inherits from `BaseException`, so `except Exception:` no longer swallows
  cancellation (bare `except:` and `except BaseException:` still do).
- `python -m asyncio` launches a REPL with top-level `await`.
- Tasks can be named (`create_task(coro, name=...)`, `task.get_name()`).
- `@asyncio.coroutine` generator-based coroutines deprecated (removed in 3.11).
- On Windows `ProactorEventLoop` became the default (subprocesses and pipes work).
- Passing coroutine objects to `asyncio.wait()` deprecated (forbidden from 3.11).

## 3.9

- `asyncio.to_thread()` added (runs a function in the default executor, propagating contextvars).
- `loop.shutdown_default_executor()`; `asyncio.run()` calls it on exit, so pending `to_thread` work is waited
  for.
- `Task.cancel(msg=...)` lets you attach a reason that appears in the `CancelledError`.
- `PidfdChildWatcher` on Linux; child watchers were later deprecated (3.12) and removed (3.14).
- Generic aliases: `asyncio.Queue[int]`, `asyncio.Task[str]` and `list[...]` work in annotations at runtime.

## 3.10

- The `loop` parameter was removed from high-level APIs (`Queue`, `Lock`, `Event`, `Semaphore`, `sleep`,
  `gather`, `wait_for`, ...). Primitives now bind to the running loop lazily on first use, which removed most
  "attached to a different loop" errors for objects created before `asyncio.run`.
- Built-ins `aiter()` and `anext()`; `contextlib.aclosing()`.
- `asyncio.get_event_loop()` deprecation warnings began for calls with no running loop (behaviour adjusted
  in patch releases, see below).

## 3.11

- `asyncio.TaskGroup` (structured concurrency) and `ExceptionGroup`/`except*` (PEP 654).
- `asyncio.timeout()`, `asyncio.timeout_at()` and the `Timeout` class (reschedulable deadlines).
- `asyncio.Runner` for several `run()` calls on one loop; `asyncio.run()` is implemented with it. The runner
  installs a SIGINT handler that cancels the main task, so Ctrl+C runs cleanup code.
- `asyncio.Barrier` and `BrokenBarrierError`.
- `Task.cancelling()` / `Task.uncancel()` to track nested cancellation requests.
- `asyncio.TimeoutError` became an alias of the built-in `TimeoutError`.
- `asyncio.wait()` rejects bare coroutines with `TypeError` (verified: "Passing coroutines is forbidden").
- `@asyncio.coroutine` removed.
- `create_task(..., context=)` and `TaskGroup.create_task(..., context=)` accept an explicit context.
- General interpreter speedups (PEP 659) benefit async code too.

## 3.12

- Eager tasks: `asyncio.eager_task_factory` and `asyncio.create_eager_task_factory()`; a coroutine starts
  running synchronously inside `create_task` until its first suspension.
- `asyncio.run(main, loop_factory=...)` (verified: present in 3.14, absent in 3.11's signature).
- `asyncio.wait_for()` reimplemented on top of `asyncio.timeout()`, fixing races around cancellation at the
  deadline.
- Significant performance work on asyncio (faster socket writes, `current_task` in C).
- Child watcher classes deprecated.

## 3.13

- `asyncio.Queue.shutdown(immediate=False)` and `asyncio.QueueShutDown`: `put()` raises after shutdown,
  `get()` raises once the queue is drained (immediately with `immediate=True`).
- `asyncio.as_completed()` also works as an async iterator and then yields the **original** task/future
  objects, so you can map results back to inputs.
- `asyncio.EventLoop` alias for the default loop class (useful with `Runner(loop_factory=asyncio.EventLoop)`).
- `Server.close_clients()` / `Server.abort_clients()` for shutting down servers.
- TaskGroup: improved handling when the group and an outer scope are cancelled at the same time.
- Experimental free-threaded build (`python3.13t`, PEP 703) and an experimental JIT; asyncio itself is
  unchanged in usage but became the subject of thread-safety work.

## 3.14

- `python -m asyncio ps <PID>` and `python -m asyncio pstree <PID>` inspect the tasks of a running process
  (built on the new remote debugging support).
- `asyncio.capture_call_graph()` / `asyncio.print_call_graph()` show the await chain of a task in-process.
- `create_task()` and `TaskGroup.create_task()` accept `eager_start=` (verified).
- `asyncio.get_event_loop()` raises `RuntimeError` when there is no current event loop instead of creating one
  (verified: "There is no current event loop in thread 'MainThread'").
- The event loop policy system is deprecated (`get_event_loop_policy`, `set_event_loop_policy`, ...; verified
  DeprecationWarning: "slated for removal in Python 3.16"); use `loop_factory` instead of policies.
- `asyncio.iscoroutinefunction()` deprecated in favour of `inspect.iscoroutinefunction()` (verified).
- Child watchers removed (verified `get_child_watcher` absent).
- Free-threaded build officially supported (PEP 779), still optional; asyncio internals were made safe and
  scalable for it (per-thread task bookkeeping).
- `concurrent.interpreters` module (PEP 734) and `concurrent.futures.InterpreterPoolExecutor` (verified
  present) for running Python code in subinterpreters with separate GILs.
- `multiprocessing` default start method on Linux (and other POSIX except macOS) is now `forkserver`
  (verified: `fork` on 3.11, `forkserver` on 3.14). Process pools now need the `if __name__ == "__main__":`
  guard and picklable callables on Linux too.

## Writing code for a range of versions

| Target | Recommended style |
|--------|-------------------|
| 3.9-3.10 | `gather` + Semaphore + cancel-on-error helper (or anyio task groups), `wait_for` for timeouts, catch `asyncio.TimeoutError`, `exceptiongroup` backport if you need groups |
| 3.11+ | `TaskGroup`, `asyncio.timeout`, `except*`, `Runner` |
| 3.12+ | consider eager tasks for cache-heavy code; `asyncio.run(loop_factory=uvloop.new_event_loop)` |
| 3.13+ | `Queue.shutdown()` for worker pools; `async for` over `as_completed` |
| 3.14+ | `python -m asyncio ps/pstree` in runbooks; no policies; forkserver-safe process pools |

Feature-gating in code:

```python
import asyncio
import sys

if sys.version_info >= (3, 11):
    from asyncio import timeout as async_timeout
else:                                           # pip install async-timeout (same API)
    from async_timeout import timeout as async_timeout


async def fetch_with_deadline(coro, seconds: float):
    async with async_timeout(seconds):
        return await coro
```

Static checking: `python scripts/async_lint.py src/ --target-version 3.9` reports uses of `TaskGroup`,
`asyncio.timeout`, `Runner`, `Barrier`, eager task factories, `QueueShutDown`, `asyncio.EventLoop`,
`except*`, `async for` over `as_completed` and `asyncio.run(loop_factory=)` that are newer than the target
(rule AIO024). With `--target-version 3.11` or later it suggests `asyncio.timeout` over `wait_for` (AIO015).

## get_event_loop over time

| Version | `asyncio.get_event_loop()` with no running loop in the main thread |
|---------|--------------------------------------------------------------------|
| 3.7-3.9 | returns the policy's loop, creating one if needed |
| 3.10-3.13 | still returns/creates a loop in most cases; a `DeprecationWarning` was added and its exact conditions changed between patch releases (e.g. 3.10.9 and 3.11.1 narrowed it; local check: 3.11.15 emitted none when creating a loop) |
| 3.14 | raises `RuntimeError` if no current loop has been set |

Inside coroutines and callbacks it has always returned the running loop, but `get_running_loop()` says what
you mean and fails loudly outside a loop. At program entry use `asyncio.run(main())` or `asyncio.Runner`.

## Free-threading and asyncio

The free-threaded build (3.13 experimental, 3.14 officially supported but optional) removes the GIL, which
changes the trade-offs for the **thread** side of async programs, not the event loop itself:

| Question | Answer |
|----------|--------|
| Does one event loop get faster? | No. A loop still runs on one thread; blocking it still stalls every task. |
| Does `asyncio.to_thread` for CPU work become parallel? | Yes, on the free-threaded build, if the C extensions involved support it (check each wheel; unsupported extensions re-enable the GIL at import with a warning). |
| Can I run several event loops in several threads? | Always could; with free-threading their CPU-bound parts no longer serialize. One loop per thread, no sharing of asyncio objects between loops. |
| Are asyncio objects thread-safe now? | No. Use `call_soon_threadsafe` / `run_coroutine_threadsafe` across threads exactly as before. |
| How do I check at runtime? | `sys._is_gil_enabled()` (3.13+) returns False when running without the GIL. |

For CPU-heavy stages in AI pipelines (parsing, chunking, tokenizing) the order of preference on 3.14 is:
library that releases the GIL in threads -> free-threaded build with threads (if all extensions support it)
-> `InterpreterPoolExecutor` for pure-Python code -> `ProcessPoolExecutor` (most compatible, pickling cost).

## Ecosystem notes

Library versions change behaviour that looks like asyncio behaviour. Check these when upgrading:

| Library | Change to know about |
|---------|----------------------|
| pytest-asyncio | 0.24 added `loop_scope`; 1.0 removed the `event_loop` fixture; strict mode is the default (async fixtures need `@pytest_asyncio.fixture`) |
| anyio | ships the `pytest.mark.anyio` plugin; FastAPI/Starlette run sync routes and dependencies in anyio's threadpool (default 40 threads) |
| uvloop | `uvloop.run()` added in 0.18; `uvloop.install()` relies on event-loop policies, deprecated by Python 3.14 |
| httpx | default timeout is 5 s for connect/read/write/pool; LLM calls need explicit longer read timeouts |
| redis-py | `redis.asyncio` replaced the separate `aioredis` package; newer versions prefer `aclose()` over `close()` |
| PyMongo | a native async API (`AsyncMongoClient`) supersedes Motor |
| async-timeout | the 3.9/3.10 backport of `asyncio.timeout`; not needed on 3.11+ |
| nest_asyncio | unmaintained; breaks on newer Python and with uvloop; use top-level `await` in notebooks instead |

Pin these in your lock file and re-run the async test suite (with debug mode on) when bumping them.
