---
name: python-trio-anyio-migrator
description: "Migrate asyncio code to AnyIO (runs on asyncio or trio) or to trio, and decide whether to migrate at all: structured concurrency (nurseries, task groups, cancel scopes, level-triggered cancellation, checkpoints), a complete asyncio -> anyio -> trio API map (run, sleep, gather/TaskGroup -> create_task_group/start_soon, tg.start and task_status, wait_for/timeout -> fail_after/move_on_after, shield, Event/Lock/Semaphore/CapacityLimiter, Queue -> memory object streams, to_thread, from_thread and blocking portals, run_process, signals), ExceptionGroup and except*, pytest anyio plugin, trio MockClock, httpx/Starlette/FastAPI vs asyncpg/aiohttp compatibility. Ships an AST rewriter with diff/write/check modes. Use when someone asks to port asyncio to anyio or trio, make a library backend-agnostic, replace gather/create_task/Queue/wait_for, or hits ExceptionGroup surprises, swallowed get_cancelled_exc_class, hangs on await in finally, or pytest-asyncio to anyio test migration."
metadata:
  category: programming
  subcategory: python
  version: "1.0.0"
---

# Python Trio / AnyIO Migrator

Move asyncio code to structured concurrency without changing behaviour by accident. Start by deciding whether
to move at all: asyncio with `TaskGroup` on 3.11+ may be enough. If the answer is yes, migrate in an order
that keeps the code running at every step. The rewriter handles the mechanical renames exactly. The skill
covers the parts that need judgement: `gather`, free-floating tasks, queues, futures, callbacks and
cancellation. Every migrated module should end up passing the same tests on the asyncio and trio backends,
plus a CI gate that stops asyncio from creeping back in.

## Trigger Conditions

Activate this skill when the user:
- Asks to port, convert or migrate asyncio code to AnyIO or trio, or asks "should we use anyio/trio?"
- Writes a library or SDK wrapper that must work under asyncio *and* trio (backend-agnostic)
- Needs replacements for `gather`, `create_task`, `wait_for`, `asyncio.Queue`, `Future`, `call_later`,
  `add_done_callback`, `run_in_executor` or `run_coroutine_threadsafe`
- Hits `ExceptionGroup` where a plain exception used to come out, a task group that will not finish, an
  `await` in `finally` that raises immediately, or `get_cancelled_exc_class()` swallowed in an `except`
- Mixes FastAPI/Starlette/httpx (anyio-based) with asyncpg/aiohttp (asyncio-only)
- Moves tests from pytest-asyncio to `@pytest.mark.anyio`, or wants deterministic time with trio's `MockClock`

## Workflow

```
1. DECIDE    -> Migrate, or stay on asyncio + TaskGroup? (decision table below)
2. INVENTORY -> python scripts/migrate_async.py src/ --json      (mechanical vs manual per file)
3. TESTS     -> switch the suite to the anyio pytest plugin first; keep it green on asyncio
4. MECHANICAL-> python scripts/migrate_async.py src/ --diff, review, then --write per file
5. MANUAL    -> gather -> task group + results list, Queue -> memory streams, create_task -> owned
                groups, wait_for -> fail_after, futures/callbacks -> events/streams
6. CANCEL    -> re-raise get_cancelled_exc_class(), shield awaits in finally, review timeouts
7. VERIFY    -> tests on asyncio AND trio backends; migrate_async.py src/ --check as a CI gate
```

## Why Structured Concurrency

| Idea | asyncio (default) | anyio / trio |
|------|-------------------|--------------|
| Task lifetime | `create_task` tasks can outlive their creator; a lost reference can let one be garbage-collected | every task lives inside a task group / nursery block that waits for it |
| Errors | an exception in an un-awaited task is only logged ("Task exception was never retrieved") | first failure cancels the siblings; the block raises an `ExceptionGroup` |
| Cancellation | edge-triggered: `task.cancel()` delivers one `CancelledError`; swallow it and the task keeps running | level-triggered: every checkpoint inside a cancelled scope raises until the scope exits |
| Timeouts | `wait_for` / `asyncio.timeout` (3.11+) | cancel scopes: `fail_after`, `move_on_after`, nestable, shieldable, deadline is readable |
| Checkpoints | any `await` may or may not yield | every anyio/trio async API is a checkpoint (it checks for cancellation and can yield) |

Under the asyncio backend, anyio builds this model on top of the asyncio loop. Native asyncio libraries still
work there, and anyio's cancel scopes also cancel the native asyncio awaits inside them (verified on anyio
4.14/4.15). Details: [structured-concurrency-concepts.md](references/structured-concurrency-concepts.md).

## Should You Migrate? Situation -> Right Tool

| Situation | Recommendation |
|-----------|----------------|
| App on 3.11+, asyncio-only deps (asyncpg, aiohttp), team knows asyncio | Stay on asyncio; adopt `TaskGroup` + `asyncio.timeout` ([asyncio advisor](../python-asyncio-pattern-advisor/SKILL.md)) |
| Library/SDK others call from FastAPI, Starlette, trio or Jupyter | **anyio**: one codebase works under both backends; never pick the loop for your users |
| FastAPI/Starlette app with background work, streaming, thread offload | **anyio** (already a dependency): task groups in lifespan, `to_thread`, memory streams |
| Need cancel scopes, `move_on_after`, shielding or `tg.start` readiness before 3.11 | **anyio** (4.14/4.15 need Python 3.10+, so pin an older 4.x on 3.9; pulls in the `exceptiongroup` backport below 3.11) |
| Greenfield service where correctness under cancellation matters most and deps are trio-compatible | **trio** directly (or anyio with `backend="trio"`, which keeps an escape hatch) |
| Large app with heavy asyncpg/aiohttp/uvloop use | anyio on the asyncio backend only, or stay; trio would need trio-asyncio |
| Must keep running asyncio-only code inside trio | trio-asyncio bridge, as a temporary measure; plan to replace the dependency |

App authors may pin a backend. Library authors should depend on anyio and test on both backends. If the user
cannot name a concrete benefit (correct cancellation, no lost tasks, or backend independence), recommend
staying on asyncio.

## Ecosystem Compatibility

| Library | Runs on | Notes |
|---------|---------|-------|
| httpx, httpcore | anyio (asyncio or trio) | `httpx.AsyncClient` works under both; most httpx-based LLM SDKs follow, but check the SDK's own docs before assuming trio support |
| Starlette, FastAPI | anyio | `def` routes run in anyio's thread pool (default 40 tokens); background work uses anyio |
| asyncpg, aiohttp, aioredis-style clients, uvloop | asyncio only | Fine under anyio's asyncio backend; fail under trio |
| redis-py asyncio, motor, most `aio*` packages | asyncio only | Same; keep them behind an adapter if you want trio later |
| trio-asyncio | bridge | Runs an asyncio loop inside trio (`trio_asyncio.open_loop()`); maintenance is low-activity, so check it supports your Python |
| pytest-asyncio | asyncio only | Replace with the anyio pytest plugin (ships with anyio) |

## Mapping Cheat Sheet (full table: [api-mapping-asyncio-anyio-trio.md](references/api-mapping-asyncio-anyio-trio.md))

| asyncio | anyio | trio |
|---------|-------|------|
| `asyncio.run(main(a))` | `anyio.run(main, a)` | `trio.run(main, a)` |
| `await asyncio.sleep(s)` | `await anyio.sleep(s)` | `await trio.sleep(s)` |
| `async with asyncio.TaskGroup() as tg: tg.create_task(f(a))` | `async with anyio.create_task_group() as tg: tg.start_soon(f, a)` | `async with trio.open_nursery() as n: n.start_soon(f, a)` |
| server ready signal (Event dance) | `value = await tg.start(f)` + `task_status.started(value)` | `value = await nursery.start(f)` |
| `async with asyncio.timeout(s):` | `with anyio.fail_after(s):` (TimeoutError) | `with trio.fail_after(s):` (TooSlowError) |
| `wait_for(x, s)` that may give up | `with anyio.move_on_after(s) as scope:` | `with trio.move_on_after(s) as scope:` |
| `asyncio.shield(aw)` | `with anyio.CancelScope(shield=True):` | `with trio.CancelScope(shield=True):` |
| `Event / Lock / Semaphore(n)` | `anyio.Event / Lock / Semaphore(n)`, `CapacityLimiter(n)` | `trio.Event / Lock / Semaphore(n)`, `CapacityLimiter(n)` |
| `asyncio.Queue(maxsize=n)` | `send, recv = anyio.create_memory_object_stream[T](n)` | `send, recv = trio.open_memory_channel(n)` |
| `await asyncio.to_thread(f, *a)` | `await anyio.to_thread.run_sync(f, *a, limiter=lim)` | `await trio.to_thread.run_sync(f, *a)` |
| `run_coroutine_threadsafe(c, loop)` | `anyio.from_thread.run(fn, *a)` / blocking portal | `trio.from_thread.run(fn, *a)` |
| `create_subprocess_exec` | `await anyio.run_process([...])` / `open_process` | `await trio.run_process([...])` |
| `except asyncio.CancelledError:` | `except anyio.get_cancelled_exc_class():` | `except trio.Cancelled:` |

## Migrating the Hard Parts

**gather -> task group + results list.** `gather` without `return_exceptions` does not cancel the other
awaitables when one fails. A task group does, and it raises an `ExceptionGroup` instead of the first error.
```python
async def fan_out(prompts: list[str], limiter: anyio.CapacityLimiter) -> list[str]:
    results: list = [None] * len(prompts)

    async def run_one(i: int, prompt: str) -> None:
        async with limiter:                       # replaces gather + Semaphore
            results[i] = await call_llm(prompt)

    async with anyio.create_task_group() as tg:
        for i, prompt in enumerate(prompts):
            tg.start_soon(run_one, i, prompt)
    return results
```
For `return_exceptions=True`, catch `Exception` inside `run_one` and store it. Never catch the cancellation
class there. anyio 4.15 adds `anyio.gather`, but it is new and trio has nothing like it, so the pattern
above is the portable choice.

**create_task -> an owner.** Every fire-and-forget task needs a task group that outlives it, for example one
opened in the FastAPI lifespan. Before anyio 4.14, and always in trio, `start_soon` returns `None`: results
go into a dict, list or memory stream, and cancelling one task means cancelling its own `CancelScope`.

**Queue -> memory object stream.** The stream has a send end and a receive end. `max_buffer_size` gives
backpressure; 0 means rendezvous. Each producer gets its own `clone()`. Closing every send clone ends the
consumers' `async for`, which makes `join()`/`task_done()` and sentinel values unnecessary.
```python
send, receive = anyio.create_memory_object_stream[str](max_buffer_size=32)
async with anyio.create_task_group() as tg:
    for _ in range(4):
        tg.start_soon(embed_worker, receive.clone())   # worker: `async with recv: async for doc in recv`
    receive.close()                                    # workers hold the clones
    async with send:
        for doc in docs:
            await send.send(doc)                       # blocks when 32 are waiting: backpressure
```

**wait_for -> scopes.** `with anyio.fail_after(10): reply = await llm(p)`. Use `move_on_after` and check
`scope.cancelled_caught` when giving up is not an error. **Future/callbacks** become an `Event` plus a value
slot, or a 1-item stream. **call_later** becomes a child task that sleeps and then acts. **asyncio.wait
FIRST_COMPLETED** becomes children that store a result and call `tg.cancel_scope.cancel()`. Full recipes:
[migration-playbook.md](references/migration-playbook.md).

## Cancellation and Exception Groups (the Gotchas)

| Gotcha | What happens | Fix |
|--------|--------------|-----|
| Swallowing `get_cancelled_exc_class()` | Level-triggered: the next checkpoint raises again; code that "continues" never does | Catch only to clean up, then `raise` |
| `await` in `finally`/`except` during cancellation | Raises the cancel exception at once: cleanup is skipped | `with anyio.CancelScope(shield=True):` around cleanup, plus `move_on_after` so cleanup cannot hang |
| Task group raised `ExceptionGroup` for one error | anyio 4 (and trio by default since 0.25) always groups | `except* RateLimitError:` (3.11+) or `exceptiongroup.catch` on 3.9/3.10 |
| One failing child cancels all the others | Structured semantics, same as `asyncio.TaskGroup` | Catch per child when partial success is acceptable |
| `start_soon` result is not a task | No `.result()` or `.cancel()` (a `TaskHandle` exists only from anyio 4.14) | Write results into containers; cancel via a scope |
| `except Exception` around an `await` | Fine: the cancel class is not an `Exception` subclass (asyncio `CancelledError` and trio `Cancelled` are `BaseException`) | Never use bare `except:` / `except BaseException:` without re-raise |
| Blocking portal used from inside the loop thread | Deadlock: the portal waits for the loop it is blocking | Portals are only for foreign threads; inside async code just `await` |
| `to_thread.run_sync` ignores cancellation | Default waits for the thread to finish | `abandon_on_cancel=True` (anyio 4.1+; trio 0.23+) and make the work idempotent |
| `move_on_after` / `fail_after` timer starts when *called* | Matters only if you build the scope early | Create it in the `with` statement |

Deep dive: [cancellation-and-exception-groups.md](references/cancellation-and-exception-groups.md).

## Mixed Codebases and Interop

- Under `anyio.run(main)` (asyncio backend), asyncpg/aiohttp calls and even `asyncio.wait_for` keep working.
  Migrate module by module. Run the tests on both backends only for modules that are free of asyncio-only
  dependencies.
- Blocking SDKs: `await anyio.to_thread.run_sync(fn, *args, limiter=limiter)`. From inside that worker
  thread, call back into the loop with `anyio.from_thread.run(async_fn, *args)`.
- Sync code that needs async (a CLI, Celery task or Streamlit callback): use
  `with anyio.from_thread.start_blocking_portal() as portal: portal.call(async_fn, arg)`.
- An asyncio-only library inside trio: wrap it with trio-asyncio, or keep the service on anyio's asyncio
  backend.

Thread sizing and executor details: [threadpool builder](../python-threadpool-executor-builder/SKILL.md).
CPU-bound work: [GIL analyzer](../python-gil-bottleneck-analyzer/SKILL.md) and
[multiprocessing designer](../python-multiprocessing-pool-designer/SKILL.md) (`anyio.to_process.run_sync`
exists, but a tuned process pool is usually better).

## AI-Engineering Cases

| Case | Pattern |
|------|---------|
| LLM fan-out (gather + Semaphore) | task group + `CapacityLimiter(n)` + results list; per-call `fail_after` |
| Streaming tokens to a client | producer sends deltas into `create_memory_object_stream[str](64)`, the SSE consumer iterates; a slow client applies backpressure to the model stream |
| Agent tool calls | each tool in its own `fail_after(tool.timeout)`; run independent tools in a task group; the agent's overall budget is an outer `move_on_after` |
| FastAPI background work | a task group opened in `lifespan` and stored on `app.state`; endpoints `start_soon` into it; shutdown cancels and drains |
| SDK wrapper library | depend on anyio + httpx only, no `asyncio` imports, `anyio.Lock` for token refresh, tests on both backends |

Runnable versions: [ai-engineering-anyio.md](references/ai-engineering-anyio.md).

## Testing

```python
import importlib.util

import anyio
import pytest

HAS_TRIO = importlib.util.find_spec("trio") is not None


@pytest.fixture(params=["asyncio", pytest.param("trio", marks=pytest.mark.skipif(not HAS_TRIO,
                                                                                reason="trio not installed"))])
def anyio_backend(request):
    return request.param


@pytest.mark.anyio
async def test_fan_out_keeps_order_and_limit():
    assert await fan_out(["a", "b", "c"], anyio.CapacityLimiter(2)) == ["A", "B", "C"]
```
- Replace `@pytest.mark.asyncio` with `@pytest.mark.anyio`. Async fixtures work when the test requests
  `anyio_backend`; `anyio_mode = "auto"` in recent anyio 4.x marks every async test.
- In recent anyio 4.x the built-in `anyio_backend` fixture runs every *installed* backend. Older releases ran
  asyncio only. Override it explicitly (as above) so the result does not depend on the version.
- Trio gives deterministic time: `trio.testing.MockClock(autojump_threshold=0)` via
  `anyio_backend = ("trio", {"clock": MockClock(autojump_threshold=0)})`. A 30-second timeout test then
  takes milliseconds.

More: [testing-with-anyio-and-trio.md](references/testing-with-anyio-and-trio.md).

## Symptom -> Cause -> Fix

| Symptom | Cause | Fix |
|---------|-------|-----|
| `TypeError: 'coroutine' object is not callable` from `start_soon` / `anyio.run`, plus "never awaited" warning | Passed `f(a)` instead of `f, a` | `tg.start_soon(f, a)`; kwargs via `functools.partial` |
| `ExceptionGroup` escapes where `ValueError` was caught before | Task groups always group errors | `except* ValueError` or catch inside the child |
| Task group never exits | A child loops forever (consumer whose send side is never closed, `sleep_forever`) | Close every send clone; `tg.cancel_scope.cancel()` on shutdown |
| Cleanup in `finally` silently skipped | Unshielded `await` during cancellation | Shielded scope + timeout |
| Code after `except get_cancelled_exc_class()` keeps getting cancelled | Level-triggered cancellation | Re-raise; do not try to continue |
| `RuntimeError` releasing a Lock | anyio/trio locks are owned by the acquiring task | `async with lock:` in one task |
| `AttributeError: 'Event' object has no attribute 'clear'` | anyio/trio Events are one-shot | Replace the Event object |
| `NoEventLoopError: Not currently running on any asynchronous event loop` (older anyio: sniffio `AsyncLibraryNotFoundError`) | anyio API called outside `anyio.run` or from a foreign thread | Run inside the loop, or use `from_thread` / a portal |
| asyncpg/aiohttp fails under `backend="trio"` | asyncio-only library | Stay on the asyncio backend or bridge with trio-asyncio |
| Timeout handler not triggered on trio | `trio.fail_after` raises `trio.TooSlowError`, not `TimeoutError` | Catch `trio.TooSlowError` or use anyio |

More symptoms and step-by-step diagnosis: [troubleshooting-migration.md](references/troubleshooting-migration.md).
For hangs, see the [deadlock debugger](../python-async-deadlock-debugger/SKILL.md).

## Verify

1. `python scripts/migrate_async.py src/ --check` exits 0, or what remains is behind `# noqa: MIG0xx` with a
   reason such as "asyncpg adapter".
2. The test suite passes with `anyio_backend` set to asyncio, and also to trio wherever the dependencies
   allow.
3. Cancellation tests: cancel mid-flight and assert that cleanup ran, that nothing leaked (open streams,
   threads) and that no warnings appeared (`-W error::ResourceWarning`).
4. Load test the fan-out: concurrency stays at or below the limiter's `total_tokens`, and p95 latency has
   not regressed.

## Output Format

When advising or migrating, answer with:
1. **Decision**: migrate or not, to anyio or trio, and why (dependencies, library vs app, Python version).
2. **Inventory**: mechanical vs manual counts per file (script output), plus blockers (asyncio-only deps).
3. **Rewritten code**: complete before/after for every manual item, with semantics differences called out
   (errors grouped, siblings cancelled, cancellation waits for threads, and so on).
4. **Cancellation review**: every `except` that catches the cancel class re-raises, every await in `finally` is
   shielded with a timeout, and every timeout is placed where it belongs.
5. **Tests and gate**: anyio plugin setup, both-backend fixture, the `--check` CI step.

## Scripts

```bash
# Inventory: every asyncio usage with rule id, mechanical/manual, and the replacement
python scripts/migrate_async.py src/rag_service/
python scripts/migrate_async.py app/agent.py --target trio --json
cat worker.py | python scripts/migrate_async.py - --diff               # stdin: report or --diff only
python scripts/migrate_async.py app/agent.py --diff                    # unified diff of the exact rewrites
python scripts/migrate_async.py app/agent.py --write                   # in place, keeps app/agent.py.bak
python scripts/migrate_async.py app/agent.py --write --force           # write although manual items remain
python scripts/migrate_async.py src/ --check                           # CI gate: exit 1 while asyncio remains
python scripts/migrate_async.py src/ --strict                          # exit 1 if anything needs a human
python scripts/migrate_async.py src/ --select MIG003,MIG004 --ignore gather
python scripts/migrate_async.py --list-rules --target trio             # why + fix snippet for every rule
```
Mechanical rewrites happen only when they are provably equivalent at that call site:
MIG001 imports (`import asyncio` is kept only while still used), MIG002 `asyncio.run(main(a))` ->
`anyio.run(main, a)` (kwargs via `functools.partial`), MIG003 sleep, MIG004 Event/Lock/Semaphore/
BoundedSemaphore/Condition, MIG005 `to_thread` -> `to_thread.run_sync`, MIG006 `async with asyncio.timeout(x)`
-> `with anyio.fail_after(x)`, MIG007/MIG008 `TaskGroup` + `tg.create_task(f(a))` -> `create_task_group` +
`tg.start_soon(f, a)` (only when no task result is used), MIG009 `except CancelledError` ->
`get_cancelled_exc_class()`, and MIG010 `asyncio.TimeoutError`. If a call site is not safe (`Event.clear()`
used, `as cm` on a timeout, a stored task, a builtin `TimeoutError` handler with `--target trio`), the item is
reported as manual with the reason. Manual-only rules: MIG011-MIG033 (gather, wait_for, create_task, Queue,
join/task_done, run_in_executor, loop access, callbacks, futures, done callbacks, wait, as_completed, shield,
subprocess, sockets, signals, run_coroutine_threadsafe, introspection, task.cancel, swallowed cancellation,
advanced timeouts, coroutine checks) and MIG099 for anything else. `# noqa: MIG013` skips one line, including
its rewrite. Every rewrite is checked with `ast.parse`. `--write` refuses a file that has manual items unless
`--force` is given. Exit codes: 0 ok; 1 `--check` found asyncio, `--strict` found manual items, or `--write`
refused a file; 2 usage error, unreadable or unparsable file named on the command line (files found while
walking a directory are skipped with a warning), or a rewrite that fails `ast.parse`.

## Additional Resources

| File | Content |
|------|---------|
| [structured-concurrency-concepts.md](references/structured-concurrency-concepts.md) | Nurseries/task groups, cancel scopes, level vs edge triggering, checkpoints, anyio 4 on asyncio, version notes |
| [api-mapping-asyncio-anyio-trio.md](references/api-mapping-asyncio-anyio-trio.md) | The complete asyncio -> anyio -> trio table, plus APIs with no direct equivalent and what to do |
| [migration-playbook.md](references/migration-playbook.md) | Step-by-step incremental migration, mixed codebases, recipes for every manual rule, CI gate |
| [cancellation-and-exception-groups.md](references/cancellation-and-exception-groups.md) | Cancel semantics on each backend, shielding, timeouts, ExceptionGroup, except*, backport |
| [ai-engineering-anyio.md](references/ai-engineering-anyio.md) | LLM fan-out, token streaming, agent tool calls, FastAPI lifespan groups, backend-agnostic SDKs, eval harness |
| [testing-with-anyio-and-trio.md](references/testing-with-anyio-and-trio.md) | anyio pytest plugin, both-backend fixtures, pytest-asyncio migration, MockClock, cancellation tests |
| [troubleshooting-migration.md](references/troubleshooting-migration.md) | Error messages and symptoms after a migration, with causes and fixes |
