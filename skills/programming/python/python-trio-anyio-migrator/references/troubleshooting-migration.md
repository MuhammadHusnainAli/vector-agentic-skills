# Troubleshooting a Migration

Error messages and symptoms that show up after moving asyncio code to anyio or trio, grouped by cause, each
with symptom -> cause -> fix. The messages quoted here were reproduced with anyio 4.15 and trio 0.34 on
Python 3.13; wording can differ slightly in other versions, so match on the distinctive part. For hangs with
no error at all, also use the [deadlock debugger](../../python-async-deadlock-debugger/SKILL.md).

## Contents

- [First: which backend is running?](#first-which-backend-is-running)
- [asyncio code running under the trio backend](#asyncio-code-running-under-the-trio-backend)
- [No running event loop, wrong thread, nested loops](#no-running-event-loop-wrong-thread-nested-loops)
- [sniffio errors](#sniffio-errors)
- [ExceptionGroup surprises](#exceptiongroup-surprises)
- [Cancel scope errors](#cancel-scope-errors)
- [Cancellation that does not behave](#cancellation-that-does-not-behave)
- [Blocking calls](#blocking-calls)
- [Task groups that never finish](#task-groups-that-never-finish)
- [Synchronisation primitives and streams](#synchronisation-primitives-and-streams)
- [Library incompatibilities](#library-incompatibilities)
- [Test-suite failures after switching plugins](#test-suite-failures-after-switching-plugins)
- [migrate_async.py problems](#migrate_asyncpy-problems)
- [Step-by-step diagnosis](#step-by-step-diagnosis)

## First: which backend is running?

Half of all post-migration errors are "asyncio code ran on trio" or "anyio code ran outside any loop". Check
before reading the traceback in detail:

```python
import anyio
import sniffio


async def where_am_i() -> None:
    print(sniffio.current_async_library(), anyio.get_cancelled_exc_class().__name__)


anyio.run(where_am_i)                     # asyncio CancelledError
anyio.run(where_am_i, backend="trio")     # trio Cancelled
```

- In tests, request the `anyio_backend_name` fixture; the test id also ends in `[asyncio]` or `[trio]`.
- A traceback that runs through `trio/_core/_run.py` and then into `asyncio/...` frames is asyncio code on
  trio: see the next section.
- `LookupError: Backend 'trio' is not available. Install it with: pip install anyio[trio]` means trio is not
  installed in that environment.

## asyncio code running under the trio backend

Anything that needs the asyncio event loop fails under `anyio.run(..., backend="trio")`, under
`trio.run`, and in the trio column of the test matrix. The failure appears where the asyncio call happens,
which can be deep inside a dependency.

| Symptom | Cause | Fix |
|---------|-------|-----|
| `RuntimeError: no running event loop` from `asyncio.sleep`, `asyncio.create_task`, `asyncio.timeout`, `asyncio.get_running_loop()`, `loop.run_in_executor` | leftover `asyncio.*` call in migrated code | `python scripts/migrate_async.py <file>` lists it with the replacement; for a dependency, see [Library incompatibilities](#library-incompatibilities) |
| `AttributeError: 'NoneType' object has no attribute 'create_future'` (Python 3.13) when awaiting an `asyncio.Event`, `asyncio.Queue.get()` or `asyncio.Lock` that has to wait | asyncio primitive with no asyncio loop behind it; it may work while it never has to wait, then fail under load | `anyio.Event` / `create_memory_object_stream` / `anyio.Lock` (MIG004, MIG015) |
| `TypeError: trio.run received unrecognized yield message <Future pending>. Are you trying to use a library written for some other framework like asyncio?` | an asyncio `Future` (from an asyncio-only library, or created on another loop) was awaited on trio | keep that code on the asyncio backend, or bridge with trio-asyncio |
| Works on `[asyncio]`, fails only on `[trio]` | asyncio-only dependency or primitive | pin that module's `anyio_backend` to `"asyncio"` until the dependency is replaced |
| `RuntimeError: must be called from async context` from `trio.sleep` etc. under the **asyncio** backend | the reverse: trio API called on asyncio | use the anyio API (`anyio.sleep`), which works on both |

Module-level primitives deserve a special look. `LOCK = asyncio.Lock()` at import time hides until two
callers contend for it. Grep for `asyncio.` in fakes, test helpers and `conftest.py` too. They run in the
trio column and fail there.

## No running event loop, wrong thread, nested loops

| Symptom | Cause | Fix |
|---------|-------|-----|
| `NoEventLoopError: Not currently running on any asynchronous event loop. Available async backends: asyncio, trio` | an anyio API that needs the loop (`get_cancelled_exc_class()`, `lowlevel.current_token()`, ...) called from sync code or a foreign thread | call it inside `anyio.run` / an async function; from a worker thread use `anyio.from_thread.run` |
| `NoEventLoopError: Not running inside an AnyIO worker thread, and no event loop token was provided` | `anyio.from_thread.run` called from a thread that anyio did not start (or from the loop thread itself) | start the thread with `anyio.to_thread.run_sync`, pass `token=anyio.lowlevel.current_token()` captured inside the loop, or use a blocking portal; in the loop thread just `await` |
| `RuntimeError: Already running asyncio in this thread` (or `trio`) | `anyio.run` called while a loop runs in the same thread: inside an async function, an async test, or a Jupyter notebook | `await` the coroutine function instead; in Jupyter use top-level `await`; from sync code inside a running loop's thread, refactor so that the caller is async |
| `RuntimeError: This event loop is already running` or `asyncio.run() cannot be called from a running event loop` | the same mistake through asyncio APIs | same fix |
| A blocking portal call never returns | `portal.call` issued from the thread that runs the portal's loop | portals are for foreign threads; inside async code use `await` |
| Older anyio: `sniffio.AsyncLibraryNotFoundError` where newer anyio says `NoEventLoopError` | same causes as the first row | same fixes; `NoEventLoopError` is a `RuntimeError` subclass |

`anyio.Event()` and other primitives can be *created* outside a loop. They only need one when you await
them, so the error shows up at the first `await`, not at construction.

## sniffio errors

sniffio tells libraries such as httpx and anyio which async library is running. In recent anyio it is an
optional dependency of anyio itself, but httpx and others still use it.

| Symptom | Cause | Fix |
|---------|-------|-----|
| `sniffio.AsyncLibraryNotFoundError: unknown async library, or not in async context` from httpx/httpcore | async client used from sync code, or from a worker thread (`to_thread.run_sync` workers are not in async context) | do the async call in the loop thread; from the worker thread call back with `anyio.from_thread.run(client.get, url)` |
| The same error under a custom loop, gevent or a hand-rolled coroutine runner | sniffio only recognises asyncio, trio and libraries that set its context variable | run under `anyio.run` / `trio.run` / `asyncio.run` |
| httpx picks the wrong backend inside trio-asyncio code | the asyncio-flavoured context inside trio-asyncio reports a different library than the surrounding trio code | keep httpx on one side of the bridge; do not share one `AsyncClient` across it |

## ExceptionGroup surprises

anyio 4 task groups, `asyncio.TaskGroup` and trio nurseries (trio 0.25+ by default) always raise an
`ExceptionGroup`, even for one failing child. On the anyio asyncio backend the message reads
`unhandled errors in a TaskGroup (1 sub-exception)`; on trio, `Exceptions from Trio nursery (1 sub-exception)`.

| Symptom | Cause | Fix |
|---------|-------|-----|
| `except ValueError:` around a migrated fan-out no longer fires; an `ExceptionGroup` escapes | `gather` raised the bare first error; a task group wraps it | `except* ValueError:` (3.11+) or `exceptiongroup.catch` on 3.10; or unwrap at the public boundary ([how](cancellation-and-exception-groups.md#keeping-a-single-exception-api-for-callers)) |
| An HTTP framework returns 500 with an `ExceptionGroup` in the log instead of mapping the error to a 4xx | exception handlers match on the class of the raised object, which is now the group | translate at the task group: `except* NotFound as eg: raise NotFound(...) from eg` |
| `pytest.raises(ValueError)` fails in tests | same | `pytest.RaisesGroup(ValueError)` or `excinfo.group_contains(ValueError)`; see [testing](testing-with-anyio-and-trio.md#testing-exception-groups) |
| Nested groups: `ExceptionGroup(..., [ExceptionGroup(...)])` | nested task groups each wrap | `except*` matches leaves at any depth; for logging, walk the tree ([example](cancellation-and-exception-groups.md#exceptiongroup-handling)) |
| An error in the `async with` body comes out wrapped | the body counts as a member of the group; its error is grouped with the children's | same handling; or move the work into a child |
| Several errors where you expected one | first failure cancelled the siblings, and some of them raised during cleanup | make cleanup robust (shielded, bounded); only the first is the root cause, usually |
| `TypeError: 'coroutine' object is not callable` inside the group, plus `RuntimeWarning: coroutine ... was never awaited` | `tg.start_soon(f(x))` instead of `tg.start_soon(f, x)` | pass the function and its arguments; kwargs via `functools.partial` |
| `RuntimeError: Child exited without calling task_status.started()` (trio: lowercase `child`) | a function used with `await tg.start(f)` returned or failed before `task_status.started()` | call `started()` once ready, on every path; use `start_soon` if no readiness is needed |
| `RuntimeError: This task group is not active; no new tasks can be started.` | `start_soon` on a group whose `async with` already exited (e.g. stored on an object after shutdown) | keep the group open for as long as producers exist (lifespan); refuse new work after shutdown |

Never handle a group by catching `BaseExceptionGroup` and dropping it: it may contain the cancel exception
and `KeyboardInterrupt`.

## Cancel scope errors

Cancel scopes (including every task group, `fail_after` and `move_on_after`) are a strict stack per task.
They must be exited in reverse order of entry, in the task that entered them.

| Message | Backend | Cause |
|---------|---------|-------|
| `RuntimeError: Attempted to exit a cancel scope that isn't the current tasks's current cancel scope` | anyio on asyncio | scopes exited out of order, or the scope's task moved on to another scope |
| `RuntimeError: Attempted to exit cancel scope in a different task than it was entered in` | anyio on asyncio | the scope is exited by another task: typically an async generator finalised by the loop |
| `RuntimeError: Cancel scope stack corrupted: attempted to exit <trio.CancelScope ...> in <Task ...> that's still within its child <trio.CancelScope ...>` | trio (also anyio on trio) | scopes exited out of order |
| `RuntimeError: Cancel scope stack corrupted: Cancel scope surrounding <Task ...> was closed before the task exited` | trio (also anyio on trio) | a scope exited from another task while the task it surrounds is still running |

Causes, from most to least common:

1. **`yield` inside a task group or cancel scope in an async generator.** The consumer stops iterating, the
   generator is closed later from another task or by the loop's async-generator finaliser, and the scope
   exits there. Fix: a producer task writes into a memory object stream that the caller's task group owns
   ([pattern](cancellation-and-exception-groups.md#async-generators-and-cancel-scopes)). An
   `@asynccontextmanager` with a single `yield` is fine.
2. **Manual `__enter__`/`__exit__` or `AsyncExitStack` misuse.** Scopes pushed onto an exit stack that is
   closed in a different task, or in a different order. Fix: use `with`/`async with` statements; if you need
   an exit stack, open and close it in the same task.
3. **A scope or task group stored on an object and exited from another method called by another task**, for
   example `__aenter__` in a request task and `__aexit__` in a shutdown task. Fix: give the object one owner
   task that runs `async with` around its whole lifetime (`tg.start(service.run)`), and talk to it through
   streams or events.
4. **Mixing asyncio cancellation tools with anyio scopes in one task**, such as `asyncio.timeout()` blocks
   that interleave with `anyio.fail_after` blocks. Fix: finish migrating that function to anyio scopes.

Lifecycle tip: these errors often surface at interpreter or loop shutdown ("an error occurred during closing
of asynchronous generator"), far from the cause. Search for `yield` in async generators that contain
`async with anyio.create_task_group()`, `fail_after`, `move_on_after` or `CancelScope`.

## Cancellation that does not behave

| Symptom | Cause | Fix |
|---------|-------|-----|
| Code after `except anyio.get_cancelled_exc_class():` keeps getting cancelled at every `await` | level-triggered cancellation: the scope stays cancelled | re-raise; use `try/finally` for cleanup |
| A retry loop "finishes" after cancellation and the scope still reports `cancelled_caught` | the handler swallowed the cancel exception at each attempt | re-raise in the handler; `migrate_async.py` flags it as MIG031 |
| Cleanup in `finally` silently skipped, connection or lease left open | the `await` in `finally` is a checkpoint in a cancelled scope and raises immediately | `with anyio.CancelScope(shield=True), anyio.move_on_after(5):` around the cleanup |
| Shutdown hangs forever | a shielded cleanup with no timeout is waiting for something that will never answer | always pair `shield=True` with a `move_on_after` |
| A timeout fires much later than set | blocking code inside the scope; cancellation is only delivered at checkpoints | see [Blocking calls](#blocking-calls) |
| `except TimeoutError:` never runs on trio | `trio.fail_after` raises `trio.TooSlowError` (not a `TimeoutError` subclass) | catch `trio.TooSlowError`, or use `anyio.fail_after`, which raises `TimeoutError` on both backends |
| Inner `fail_after` did not raise although its block was cut short | an outer scope cancelled first; the inner scope passes the outer cancellation through | check the outer scope's `cancelled_caught`; the earliest deadline wins |
| `to_thread.run_sync` call ignores the timeout | anyio waits for the thread by default | `abandon_on_cancel=True` (work continues in the background) or `anyio.from_thread.check_cancelled()` inside the worker |
| `asyncio.CancelledError` handler no longer runs on trio | the class differs per backend | `except anyio.get_cancelled_exc_class():` (MIG009), or `try/finally` |
| A task cancelled with `task.cancel()` ignores the request and keeps running | edge-triggered asyncio cancellation was swallowed once | own the task in a task group and cancel its scope (MIG030) |

Under the asyncio backend, anyio scopes also cancel native asyncio awaits (`asyncio.wait_for`,
`asyncio.sleep`, asyncpg calls) inside them, so mixed code is cancelled correctly while you migrate.

## Blocking calls

A blocking call (`time.sleep`, `requests.get`, a sync DB driver, a CPU-heavy loop, a large `json.loads`)
inside async code freezes every task on the loop, and no timeout can interrupt it, because cancellation is
only delivered at checkpoints.

| Symptom | Cause | Fix |
|---------|-------|-----|
| p95 latency of *all* endpoints rises when one endpoint is busy | a blocking call in an `async def` | `await anyio.to_thread.run_sync(fn, *args, limiter=limiter)`; or make the route `def` in FastAPI (it then runs in the thread pool) |
| `fail_after(0.05)` around `time.sleep(0.2)` does not raise; the block takes the full 0.2 s | no checkpoint inside the scope, so there is nothing to deliver the timeout to | move the blocking call to a thread; add checkpoints in long pure-Python loops (`await anyio.lowlevel.checkpoint()` every N items) |
| The same block raises `TimeoutError` on trio but not on asyncio once a checkpoint follows | trio checks deadlines at the checkpoint; on asyncio the deadline is a loop timer that may not have run yet | do not rely on either: never block inside a timed scope |
| `move_on_after` around a busy loop reports `cancelled_caught == False` | same: the loop never awaited | checkpoints, or a thread/process |
| The thread pool is exhausted; `to_thread` calls queue up | the default limiter has 40 tokens, shared with FastAPI's `def` routes | pass a dedicated `CapacityLimiter` per workload; size it from the [threadpool builder](../../python-threadpool-executor-builder/SKILL.md) |

Finding blocking calls:

- asyncio backend: `anyio.run(main, backend_options={"debug": True})` (or the test param
  `("asyncio", {"debug": True})`) logs `Executing <Task ...> took 0.200 seconds` for every step over
  `loop.slow_callback_duration` (0.1 s by default). trio has no built-in equivalent.
- Grep the migrated modules for `time.sleep`, `requests.`, `urllib`, `open(` and `subprocess.run` inside
  `async def`.
- CPU-bound work does not get faster in a thread because of the GIL: see the
  [GIL analyzer](../../python-gil-bottleneck-analyzer/SKILL.md).

## Task groups that never finish

| Symptom | Cause | Fix |
|---------|-------|-----|
| `async with create_task_group()` hangs after all the "real" work is done | a child that runs forever: a consumer whose send side is still open, a heartbeat loop, `sleep_forever()` | close every send clone (`async with send:` in each producer); cancel background children with `tg.cancel_scope.cancel()` when the body is done |
| Consumers never see the end of the stream | the original `send` (or receive) object was kept open after `clone()` | close the originals after cloning (`receive.close()` in the parent, as in the SKILL.md example) |
| `await tg.start(f)` hangs | `f` never calls `task_status.started()` and keeps running | call `started()` at the readiness point |
| Producer blocks forever on `send` | buffer full and no one is receiving (consumers crashed or exited) | consumers must hold the receive end for their whole life; when the receive side closes, `send` raises `BrokenResourceError` instead of hanging |
| Deadlock between two tasks with locks | lock ordering, unchanged by the migration | the [deadlock debugger](../../python-async-deadlock-debugger/SKILL.md) |
| A blocking portal call from the loop thread never returns | the portal waits for the loop it is blocking | use `await` in async code |

To see what is stuck: `anyio.get_running_tasks()` lists `TaskInfo` objects (`id`, `parent_id`, `name`,
`coro`) from inside the loop. On trio, `trio.lowlevel.current_root_task()` plus a task-tree walk, or an instrument, gives the
same picture.

## Synchronisation primitives and streams

| Symptom | Cause | Fix |
|---------|-------|-----|
| `RuntimeError: The current task is not holding this lock` (anyio on asyncio) / `RuntimeError: can't release a Lock you don't own` (trio) | anyio and trio locks belong to the task that acquired them; asyncio locks did not check | `async with lock:` inside one task; for cross-task signalling use an `Event` or a `Semaphore` (which may be released by another task) |
| `AttributeError: 'Event' object has no attribute 'clear'` | anyio/trio events are one-shot | create a new `Event` for each round; or use a stream for repeated notifications |
| `anyio.WouldBlock` from `send_nowait` / `receive_nowait` | buffer full / empty (`max_buffer_size=0` is always "full" for `send_nowait`) | `await send.send(x)` for backpressure, or catch `WouldBlock` to drop on purpose |
| `anyio.BrokenResourceError` on `send` | every receive clone is closed | consumers stopped; treat as shutdown, or fix the consumer that exited early |
| `anyio.ClosedResourceError` | used this very stream object after closing it (often after `async with send:` ended) | clone before handing out; keep the object open while in use |
| `anyio.EndOfStream` from `receive()` | every send clone is closed and the buffer is empty | normal end; `async for` handles it for you |
| `queue.join()` / `task_done()` have no counterpart | memory streams have no join | close the send side and let the consumer task group exit; that is the "join" |
| `asyncio.Condition` code behaves differently | `anyio.Condition` exists, but most queue-plus-condition code is simpler as a stream | rewrite as a memory object stream |

## Library incompatibilities

| Library or tool | Under anyio asyncio backend | Under trio | What to do |
|-----------------|-----------------------------|------------|-----------|
| asyncpg, aiohttp, redis-py asyncio, motor, aioboto3 | works | fails (`no running event loop`, `unrecognized yield message`, ...) | pin `backend="asyncio"`; isolate behind an adapter; or trio-asyncio as a temporary bridge |
| httpx, httpcore, Starlette, FastAPI | works | works | nothing; make sure custom middleware does not import asyncio |
| uvloop | `anyio.run(main, backend_options={"use_uvloop": True})` | n/a | asyncio backend only |
| pytest-asyncio | conflicts with anyio auto mode (config warning) | n/a | remove it, or keep it in strict mode during the transition |
| `asyncio.run_coroutine_threadsafe`, `loop.call_soon_threadsafe` in callbacks from C extensions or GUI threads | works while the loop is asyncio | fails | `anyio.from_thread.run_sync` with a token captured via `anyio.lowlevel.current_token()` |
| `nest_asyncio` (Jupyter workarounds) | not supported by anyio; re-entrant loops break the one-loop-per-thread model | n/a | remove; use top-level `await` in the notebook |
| SDKs built on httpx (most LLM clients) | works | usually works, but check the SDK's own statements before relying on trio | run the trio test column against a mocked transport |
| trio-asyncio | n/a | runs an asyncio loop inside trio (`async with trio_asyncio.open_loop():`) | short-term bridge; maintenance is low-activity, check Python-version support |

Rule of thumb: a dependency that only says "asyncio" in its docs is asyncio-only until proven otherwise.
Grep its source for `asyncio.get_event_loop`, `asyncio.get_running_loop`, `loop.create_future`, or
`asyncio.Future`.

## Test-suite failures after switching plugins

| Symptom | Cause | Fix |
|---------|-------|-----|
| `async def functions are not natively supported` | the test is not claimed by any plugin: missing `@pytest.mark.anyio` in strict mode | mark it, `pytestmark = pytest.mark.anyio`, or `anyio_mode = "auto"` |
| `ScopeMismatch: You tried to access the function scoped fixture anyio_backend with a module scoped request object` | a module- or session-scoped async fixture, plus a function-scoped `anyio_backend` override | give the override `scope="module"` (or `"session"`) |
| `'test_x' requested an async fixture 'y', with no plugin or hook that handled it` | sync test requesting an async fixture | make the test `async` and marked, or the fixture sync |
| `RuntimeError: Cannot schedule a coroutine in the test runner while another is already running` | `request.getfixturevalue()` on an async fixture inside a running async test | request it as a parameter |
| Every test runs twice / trio column appears unexpectedly | recent anyio's built-in `anyio_backend` runs every installed backend | override the fixture with explicit params |
| Flaky only on `[trio]` | ordering assumption: trio randomises the order of runnable tasks on purpose | events, `wait_all_tasks_blocked()`, indexed results ([ordering](testing-with-anyio-and-trio.md#deterministic-ordering)) |
| Timeout tests are slow | real sleeps | trio param with `MockClock(autojump_threshold=0)` |

## migrate_async.py problems

| Symptom | Cause | Fix |
|---------|-------|-----|
| `--write` exits 1 and leaves the file untouched | the file still has manual items | do the manual items first, or `--write --force` for a partial rewrite that keeps `import asyncio` |
| `--check` fails on an adapter that must stay asyncio | asyncio-only dependency on purpose | `# noqa: MIG0xx` on that line with a reason, e.g. `# noqa: MIG014 asyncpg pool adapter` |
| Exit code 2 | unreadable or unparsable file named on the command line, usage error, or a rewrite that would not parse | fix the syntax error first; report a rewrite that fails `ast.parse` as a bug |
| A rewrite was reported as manual "although it looks mechanical" | the call site is not provably equivalent (`Event.clear()` used, `as cm` on a timeout, a stored task, a result that is used) | follow the reason in the report; `--list-rules` shows the recipe |

## Step-by-step diagnosis

1. **Reproduce on one backend at a time.** `pytest -k asyncio` then `pytest -k trio`. A failure only on trio
   points to asyncio leftovers or ordering assumptions; a failure on both points to semantics (grouping,
   cancellation).
2. **Read the bottom of the traceback for the frame that touches asyncio.** Leftover calls live there.
   `python scripts/migrate_async.py <that file>` shows the rule id and the fix.
3. **Unwrap groups.** Print `eg.exceptions` recursively. The leaf with the earliest timestamp in the logs is
   usually the root cause; the rest are cleanup failures caused by the cancellation it triggered.
4. **Check cancel scopes.** Any `yield` inside a scope in an async generator? Any scope stored on an object?
   Any `__aenter__`/`__aexit__` split across tasks?
5. **Check handlers.** Every `except` that can catch the cancel class re-raises. Every `await` in
   `finally` is shielded and bounded.
6. **Check for blocking.** Run with asyncio `debug=True` and look for `took 0.xxx seconds` warnings.
7. **Check for hangs.** Add a `fail_after` guard around the suspect block, then list tasks with
   `anyio.get_running_tasks()` before it fires.
8. **Fix, then add a regression test** on both backends: cancellation tests assert cleanup ran; group tests
   use `pytest.RaisesGroup`; timing tests use `MockClock`
   (see [testing-with-anyio-and-trio.md](testing-with-anyio-and-trio.md)).
