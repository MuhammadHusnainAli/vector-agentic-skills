# Structured Concurrency Concepts

What trio introduced, what anyio adds on top of asyncio, and why these ideas change how you write fan-out,
timeouts and shutdown. Read this before migrating: most migration bugs come from carrying asyncio intuitions
(free tasks, edge-triggered cancel, single exceptions) into a structured codebase.

## Contents

- [The problem with free-floating tasks](#the-problem-with-free-floating-tasks)
- [Nurseries and task groups](#nurseries-and-task-groups)
- [Cancel scopes](#cancel-scopes)
- [Level-triggered vs edge-triggered cancellation](#level-triggered-vs-edge-triggered-cancellation)
- [Checkpoints](#checkpoints)
- [Readiness with start and task_status](#readiness-with-start-and-task_status)
- [Errors: ExceptionGroup](#errors-exceptiongroup)
- [AnyIO 4 on the asyncio backend](#anyio-4-on-the-asyncio-backend)
- [Version notes](#version-notes)

## The problem with free-floating tasks

`asyncio.create_task()` returns a task that can outlive the function that created it:

```python
import asyncio


async def handler(request_id: int) -> str:
    asyncio.create_task(log_usage(request_id))   # who waits for this? who sees its error?
    return "ok"


async def log_usage(request_id: int) -> None:
    await asyncio.sleep(0.01)
    raise RuntimeError(f"metrics backend down for {request_id}")
```

Three classic failures follow:

1. **Lost errors.** The `RuntimeError` is reported only as "Task exception was never retrieved" when the task
   is garbage-collected, maybe never.
2. **Lost tasks.** The event loop keeps only weak references to tasks; a task without a strong reference can
   be collected mid-flight (the asyncio docs tell you to keep a set of tasks for this reason).
3. **No cancellation path.** When the request is cancelled, `log_usage` keeps running; at shutdown nobody
   knows it exists.

`asyncio.TaskGroup` (3.11) fixes this *when you use it*; trio made it the only way to start a task, and anyio
brings the same rule to code that runs on either backend.

## Nurseries and task groups

A nursery (trio) / task group (anyio, asyncio 3.11+) is an `async with` block that owns its children:

- children are started with `start_soon(func, *args)` (anyio/trio) or `create_task(coro)` (asyncio);
- the block does not exit until every child has finished;
- if any child (or the block body) raises, the remaining children are cancelled and the errors are raised
  from the `async with` as an `ExceptionGroup`;
- cancelling the group's `cancel_scope` cancels the body and every child.

```python
import anyio


async def embed(doc: str, out: dict) -> None:
    await anyio.sleep(0.01)                  # stands in for an embedding API call
    out[doc] = len(doc)


async def main() -> None:
    out: dict = {}
    async with anyio.create_task_group() as tg:
        for doc in ["intro", "methods", "results"]:
            tg.start_soon(embed, doc, out)
    # every child has finished here, guaranteed
    print(sorted(out.items()))


anyio.run(main)
# Output: [('intro', 5), ('methods', 7), ('results', 7)]
```

The guarantee "when the block exits, the work is done or cancelled" is what makes code easy to reason about:
concurrency has the same shape as the call stack. Errors propagate to the caller, cancellation propagates to
callees.

Rules that follow from it:

| Rule | Consequence |
|------|-------------|
| A task needs a group that outlives it | Background work for a server goes into a group opened in the server's lifespan, not into a request handler |
| `start_soon` takes a function and args | It calls `func(*args)` itself, so the group controls when the coroutine starts; passing `func(args)` is a `TypeError` |
| No task handle (trio; anyio < 4.14) | Results are written into a container or sent into a memory stream; cancellation goes through a scope |
| The group waits | A child that never returns keeps the block open forever: consumers must see their input closed |

## Cancel scopes

A cancel scope is a `with` block that can be cancelled, either explicitly (`scope.cancel()`) or by a
deadline. Every task group has one (`tg.cancel_scope`). Timeouts are cancel scopes with a deadline:

| Construct | On deadline | Raises |
|-----------|-------------|--------|
| `with anyio.fail_after(5):` | cancels the block | `TimeoutError` (builtin) after the block exits |
| `with anyio.move_on_after(5) as scope:` | cancels the block | nothing; `scope.cancelled_caught` is `True` |
| `with anyio.CancelScope(deadline=anyio.current_time() + 5):` | cancels the block | nothing |
| `with anyio.CancelScope(shield=True):` | never; also blocks cancellation from outside | nothing |
| trio: `trio.fail_after`, `trio.move_on_after`, `trio.CancelScope` | same | `trio.TooSlowError` for `fail_after` |

Scopes nest: the effective deadline is the earliest one in force (`anyio.current_effective_deadline()`). A
shielded scope ignores outer cancellation but its own deadline still applies, which is how you bound cleanup:

```python
import anyio


async def main() -> None:
    with anyio.move_on_after(0.05) as outer:
        try:
            await anyio.sleep(10)                    # the "request"
        finally:
            with anyio.CancelScope(shield=True) as cleanup:
                cleanup.deadline = anyio.current_time() + 1   # cleanup gets at most 1 s
                await anyio.sleep(0.01)              # e.g. flush buffered vectors
                print("cleanup finished")
    print("outer cancelled:", outer.cancelled_caught)


anyio.run(main)
# Output:
# cleanup finished
# outer cancelled: True
```

The cancellation is *delivered* as an exception (`asyncio.CancelledError` on the asyncio backend,
`trio.Cancelled` on trio; `anyio.get_cancelled_exc_class()` returns the right one) and *caught* by the scope
that issued it when it reaches the scope's `with` statement. Code in between sees an exception and runs its
`finally` blocks, exactly like any other exception.

## Level-triggered vs edge-triggered cancellation

This is the most important behavioural difference when migrating.

- **asyncio is edge-triggered.** `task.cancel()` delivers *one* `CancelledError` at the next `await`. If the
  coroutine catches it and carries on, the task simply continues. (3.11 added `Task.cancelling()` /
  `uncancel()` so that `asyncio.timeout` and `TaskGroup` can tell their own cancellations apart.)
- **trio and anyio are level-triggered.** While a task is inside a cancelled scope, *every* checkpoint raises
  the cancel exception again until the scope is exited. Swallowing it does not make it go away.

```python
import asyncio

import anyio


async def asyncio_edge() -> None:
    async def child() -> str:
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            print("asyncio: caught once, swallowing")
        await asyncio.sleep(0.01)
        return "asyncio: second sleep completed"

    task = asyncio.create_task(child())
    await asyncio.sleep(0.01)
    task.cancel()
    print(await task)


async def anyio_level() -> None:
    with anyio.move_on_after(0.01):
        try:
            await anyio.sleep(1)
        except anyio.get_cancelled_exc_class():
            print("anyio: caught once, swallowing")
        try:
            await anyio.sleep(1)
        except anyio.get_cancelled_exc_class():
            print("anyio: cancelled again at the next checkpoint")
            raise


async def main() -> None:
    await asyncio_edge()
    await anyio_level()


anyio.run(main)
# Output:
# asyncio: caught once, swallowing
# asyncio: second sleep completed
# anyio: caught once, swallowing
# anyio: cancelled again at the next checkpoint
```

Consequences for migration:

- Code that "handles" cancellation by catching `CancelledError` and continuing (retry loops, best-effort
  cleanup with `await`) behaves differently: under anyio the next `await` raises again.
- Cleanup that must `await` during cancellation needs a shielded scope (see
  [cancellation-and-exception-groups.md](cancellation-and-exception-groups.md)).
- In exchange, cancellation is *reliable*: a timeout cannot be accidentally defeated by a library that
  swallows `CancelledError` once.

## Checkpoints

A checkpoint is a point where the task (a) checks for cancellation and (b) may let other tasks run. In trio
and anyio, every async function of the library is a checkpoint, even if it would not block (e.g.
`await send.send(x)` into a non-full buffer, `await lock.acquire()` on a free lock). In asyncio, an
`await` on something already done may not yield at all.

| Need | anyio | trio |
|------|-------|------|
| Yield and check for cancellation | `await anyio.lowlevel.checkpoint()` (or `await anyio.sleep(0)`) | `await trio.lowlevel.checkpoint()` |
| Check for cancellation without yielding | `await anyio.lowlevel.checkpoint_if_cancelled()` | `await trio.lowlevel.checkpoint_if_cancelled()` |
| Yield without checking cancellation | `await anyio.lowlevel.cancel_shielded_checkpoint()` | `await trio.lowlevel.cancel_shielded_checkpoint()` |

Practical rule: a CPU-heavy loop with no awaits cannot be cancelled and starves other tasks on every backend.
Move it to a thread (`anyio.to_thread.run_sync`) or process, or add a checkpoint per batch:

```python
import anyio


def tokenize(text: str) -> list:
    return text.split()


async def main() -> None:
    corpus = ["structured concurrency in python"] * 3000
    total = 0
    for i, doc in enumerate(corpus):
        total += len(tokenize(doc))
        if i % 500 == 0:
            await anyio.lowlevel.checkpoint()     # cancellable, lets other tasks run
    print(total)


anyio.run(main)
# Output: 12000
```

## Readiness with start and task_status

`tg.start(func)` starts a child and waits until the child calls `task_status.started(value)`; the value is
returned to the parent. This replaces the asyncio "create a task plus an Event" dance for servers, workers
and connection pools:

```python
import anyio


async def vector_db_proxy(*, task_status=anyio.TASK_STATUS_IGNORED) -> None:
    await anyio.sleep(0.01)                  # bind socket, warm caches...
    task_status.started(6333)               # parent resumes here with the port
    await anyio.sleep_forever()              # serve until cancelled


async def main() -> None:
    async with anyio.create_task_group() as tg:
        port = await tg.start(vector_db_proxy)
        print("proxy ready on", port)
        tg.cancel_scope.cancel()            # shut everything down


anyio.run(main)
# Output: proxy ready on 6333
```

If the child raises before calling `started()`, `tg.start()` raises that exception in the parent: startup
failures are not lost. trio has the same API: `await nursery.start(func)` with `task_status=trio.TASK_STATUS_IGNORED`.

## Errors: ExceptionGroup

When several children fail at once, there is no single "the" exception. Task groups therefore raise an
`ExceptionGroup` (PEP 654, builtin on 3.11+, `exceptiongroup` backport on 3.9/3.10):

- anyio 4.x always raises an `ExceptionGroup` from a task group, even for a single error;
- `asyncio.TaskGroup` does the same;
- trio nurseries do the same by default since trio 0.25 (`strict_exception_groups=True`).

Handle with `except*` (3.11+) or `exceptiongroup.catch()` on older Pythons. Full treatment in
[cancellation-and-exception-groups.md](cancellation-and-exception-groups.md).

## AnyIO 4 on the asyncio backend

anyio is a layer, not a new event loop:

| Aspect | Behaviour (verified with anyio 4.14 and 4.15) |
|--------|-----------------------------------------------|
| Event loop | `anyio.run(main)` runs a normal asyncio loop (`backend="asyncio"` is the default); `backend_options={"use_uvloop": True}` selects uvloop when installed |
| Native asyncio code | Works inside anyio code: `asyncio.Queue`, `asyncio.wait_for`, asyncpg, aiohttp |
| Cancel scopes vs native awaits | An anyio scope cancels native asyncio awaits inside it (they see `CancelledError`) |
| Cancel exception | `anyio.get_cancelled_exc_class()` is `asyncio.CancelledError` |
| Level-triggered cancel | Emulated: anyio keeps re-delivering cancellation to tasks inside a cancelled scope |
| Primitives | `anyio.Lock/Event/Semaphore/CapacityLimiter` work on both backends; they can be created outside a running loop (adapters), but are used inside one |
| Threads | `anyio.to_thread.run_sync` uses anyio's own worker threads limited by a default `CapacityLimiter(40)`, not the loop's default executor |
| Native tasks started by libraries | Not part of any anyio task group; they behave as in plain asyncio |

On the trio backend, anything that touches the asyncio loop (asyncpg, aiohttp, `asyncio.*`) fails, which is
why an incremental migration keeps the asyncio backend until the asyncio-only pieces are gone or isolated.

## Version notes

| Version | Change |
|---------|--------|
| Python 3.11 | `asyncio.TaskGroup`, `asyncio.timeout`, `ExceptionGroup`/`except*`, `asyncio.TimeoutError` becomes an alias of builtin `TimeoutError` |
| anyio 4.0 | Task groups always raise `ExceptionGroup`; `create_memory_object_stream[T](...)` subscript form |
| anyio 4.14 / 4.15 metadata | `Requires-Python >=3.10`; on 3.9 pin an older anyio 4.x (check that release's `Requires-Python`) |
| anyio 4.1 | `to_thread.run_sync(..., abandon_on_cancel=True)` (replaces `cancellable=`) |
| anyio 4.14 | `TaskGroup.create_task(coro)` and `start_soon` returning a `TaskHandle`; `tg.cancel()` shortcut |
| anyio 4.15 | `anyio.gather`, `anyio.as_completed`, `anyio.amap`, `anyio.Future`, `fail_at` / `move_on_at` |
| trio 0.23 | `trio.to_thread.run_sync(..., abandon_on_cancel=...)` (replaces `cancellable=`) |
| trio 0.25 | `strict_exception_groups=True` by default: nurseries always raise `ExceptionGroup` |

The 4.14/4.15 additions were read from the docstrings of the installed anyio releases. They are recent, so
code that must support older anyio versions (and trio) should stick to `start_soon` plus result containers,
which is what this skill's rewriter emits.
