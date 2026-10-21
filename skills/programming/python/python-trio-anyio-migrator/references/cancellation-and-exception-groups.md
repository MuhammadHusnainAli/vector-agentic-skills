# Cancellation and Exception Groups

Most behaviour changes after a migration come from two places: how cancellation is delivered, and how
errors leave a task group. This reference covers both on each backend, with runnable anyio examples. The
asyncio-only side (uncancel, `wait_for` edge cases) is covered in the
[asyncio advisor](../../python-asyncio-pattern-advisor/SKILL.md), and generic exception design in the
[exception handling designer](../../python-exception-handling-designer/SKILL.md).

## Contents

- [The cancel exception on each backend](#the-cancel-exception-on-each-backend)
- [Rule 1: catch only to clean up, then re-raise](#rule-1-catch-only-to-clean-up-then-re-raise)
- [Rule 2: shield awaits in cleanup, and bound them](#rule-2-shield-awaits-in-cleanup-and-bound-them)
- [Timeouts: which scope fired?](#timeouts-which-scope-fired)
- [Task groups: first error cancels the rest](#task-groups-first-error-cancels-the-rest)
- [ExceptionGroup handling](#exceptiongroup-handling)
- [Keeping a single-exception API for callers](#keeping-a-single-exception-api-for-callers)
- [Async generators and cancel scopes](#async-generators-and-cancel-scopes)
- [Threads, processes and cancellation](#threads-processes-and-cancellation)
- [Ctrl-C and shutdown](#ctrl-c-and-shutdown)
- [Checklist](#checklist)

## The cancel exception on each backend

| Backend | Exception | Base class | Get it portably |
|---------|-----------|------------|-----------------|
| asyncio (plain or under anyio) | `asyncio.CancelledError` | `BaseException` (3.8+) | `anyio.get_cancelled_exc_class()` |
| trio (plain or under anyio) | `trio.Cancelled` | `BaseException` | `anyio.get_cancelled_exc_class()` |

Because both derive from `BaseException`, `except Exception:` never catches cancellation, which is
exactly what you want around a model call. Only bare `except:` / `except BaseException:` are dangerous.

`get_cancelled_exc_class()` must be called while the event loop is running (it inspects the current
backend), which is fine inside an `except` clause of async code.

## Rule 1: catch only to clean up, then re-raise

anyio and trio cancellation is level-triggered: a task inside a cancelled scope gets the cancel exception at
every checkpoint until the scope exits (see
[structured-concurrency-concepts.md](structured-concurrency-concepts.md#level-triggered-vs-edge-triggered-cancellation)).
A handler that swallows it does not "survive" the cancellation; it just fails at the next `await`, often far
from the cause.

```python
import anyio


async def stream_answer(log: list) -> None:
    try:
        for token in ["Struct", "ured", " concurrency"]:
            await anyio.sleep(0.02)
            log.append(token)
    except anyio.get_cancelled_exc_class():
        log.append("<client disconnected>")
        raise                                   # always


async def main() -> None:
    log: list = []
    with anyio.move_on_after(0.03):
        await stream_answer(log)
    print(log)


anyio.run(main)
# Output: ['Struct', '<client disconnected>']
```

Prefer `try/finally` (runs for errors *and* cancellation) unless you need to know it was a cancellation.
`scripts/migrate_async.py` reports handlers that catch the cancel class without a `raise` as MIG031.

## Rule 2: shield awaits in cleanup, and bound them

During cancellation, an `await` in `finally` or `except` is itself a checkpoint inside the cancelled scope,
so it raises immediately and the cleanup is skipped:

```python
import anyio


class VectorBuffer:
    def __init__(self) -> None:
        self.pending = [1, 2, 3]

    async def flush(self) -> None:
        await anyio.sleep(0.01)
        print("flushed", len(self.pending))
        self.pending.clear()


async def ingest(buf: VectorBuffer, shielded: bool) -> None:
    try:
        await anyio.sleep(10)
    finally:
        if shielded:
            with anyio.CancelScope(shield=True), anyio.move_on_after(2):
                await buf.flush()
        else:
            await buf.flush()                    # raises the cancel exception right away


async def main() -> None:
    for shielded in (False, True):
        buf = VectorBuffer()
        with anyio.move_on_after(0.01):
            await ingest(buf, shielded)
        print("shielded" if shielded else "unshielded", "pending:", len(buf.pending))


anyio.run(main)
# Output:
# unshielded pending: 3
# flushed 3
# shielded pending: 0
```

Why both `shield=True` and `move_on_after`: a shield blocks outer cancellation completely, so a hung flush
would hang shutdown forever. The inner timeout bounds it. `anyio.fail_after(2, shield=True)` /
`anyio.move_on_after(2, shield=True)` combine both in one scope.

Shield only cleanup that must complete (flush, release a lease, close a connection politely). Never shield
the main work: that silently disables timeouts and Ctrl-C for it.

## Timeouts: which scope fired?

```python
import anyio


async def main() -> None:
    # 1. outer fail_after fires while the inner move_on_after is still pending
    try:
        with anyio.fail_after(0.05):
            with anyio.move_on_after(1) as inner:
                await anyio.sleep(1)
    except TimeoutError:
        print("outer fired; inner.cancelled_caught =", inner.cancelled_caught)

    # 2. an outer move_on_after cancels; the inner fail_after does NOT raise TimeoutError
    with anyio.move_on_after(0.02) as outer:
        try:
            with anyio.fail_after(5):
                await anyio.sleep(1)
        except TimeoutError:
            print("not printed: the inner deadline did not pass")
    print("outer.cancelled_caught =", outer.cancelled_caught)


anyio.run(main)
# Output:
# outer fired; inner.cancelled_caught = False
# outer.cancelled_caught = True
```

Rules:

- A scope catches only the cancellation it caused; anything else propagates through it.
- `fail_after` raises `TimeoutError` only when its *own* deadline passed. An outer cancellation passes
  straight through as the cancel exception.
- Put the per-call timeout on the call (`fail_after(30)` around one LLM request) and the overall budget on
  the request (`move_on_after(120)` around the agent loop). The earliest deadline wins.
- `move_on_after(d)` starts its timer when called (the docstring says this changes in anyio 5.0), so create
  it in the `with` statement.
- trio: `trio.fail_after` raises `trio.TooSlowError`; anyio's `fail_after` on the trio backend raises
  `TimeoutError`.

## Task groups: first error cancels the rest

```python
import anyio


async def call_tool(name: str, fail: bool, log: list) -> None:
    try:
        await anyio.sleep(0.01 if fail else 1)
        if fail:
            raise ConnectionError(f"{name}: upstream reset")
    except anyio.get_cancelled_exc_class():
        log.append(f"{name} cancelled")
        raise


async def main() -> None:
    log: list = []
    try:
        async with anyio.create_task_group() as tg:
            tg.start_soon(call_tool, "web_search", True, log)
            tg.start_soon(call_tool, "sql", False, log)
            tg.start_soon(call_tool, "calculator", False, log)
    except* ConnectionError as eg:
        print("failed:", [str(e) for e in eg.exceptions])
    print(sorted(log))


anyio.run(main)
# Output:
# failed: ['web_search: upstream reset']
# ['calculator cancelled', 'sql cancelled']
```

This is the same as `asyncio.TaskGroup`, but different from `asyncio.gather`. Without `return_exceptions`,
gather raises the first error and leaves the other awaitables running. When partial results are acceptable
(an eval harness, best-effort retrieval), catch `Exception` *inside* each child and record it.

An exception raised in the `async with` body is handled the same way: the children are cancelled and the
body's exception comes out inside the `ExceptionGroup`.

## ExceptionGroup handling

anyio 4 task groups always raise `ExceptionGroup`, even when only one child failed. So do
`asyncio.TaskGroup` and trio nurseries (trio 0.25+ default). Nested groups give nested exception groups:

```python
import anyio


async def bad(msg: str) -> None:
    await anyio.sleep(0)
    raise ValueError(msg)


async def main() -> None:
    try:
        async with anyio.create_task_group() as tg:
            tg.start_soon(bad, "outer child")
            async with anyio.create_task_group() as inner:
                inner.start_soon(bad, "inner child")
    except* ValueError as eg:
        leaves = []

        def walk(group) -> None:
            for exc in group.exceptions:
                walk(exc) if isinstance(exc, BaseExceptionGroup) else leaves.append(str(exc))

        walk(eg)
        print(sorted(leaves))


anyio.run(main)
# Output: ['inner child', 'outer child']
```

Handling patterns (3.11+):

| Need | Code |
|------|------|
| Handle one type, let others propagate | `except* RateLimitError as eg:` (unmatched parts re-raise automatically) |
| Translate to a domain error | `except* VectorStoreError as eg: raise RetrievalError("index down") from eg` |
| Inspect without handling | `except ExceptionGroup as eg: log(eg.exceptions); raise` |
| Pick parts | `matched, rest = eg.split(ValueError)`; `eg.subgroup(lambda e: ...)` |
| Never | `except* anyio.get_cancelled_exc_class()` (cancellation is handled by scopes) |

Python 3.10 (no `except*`): anyio depends on the `exceptiongroup` backport there.

```python
# Python 3.10 (and newer). Not run here: the backport is not installed in this environment.
from exceptiongroup import ExceptionGroup, catch


def on_rate_limit(eg: ExceptionGroup) -> None:
    print("rate limited", len(eg.exceptions), "calls")


with catch({RateLimitError: on_rate_limit}):
    anyio.run(fan_out, prompts)
```

## Keeping a single-exception API for callers

A library that used `gather` may promise callers a plain `ProviderError`. Unwrap a lone exception at the
boundary and keep the group otherwise:

```python
import anyio


def unwrap_single(eg: BaseExceptionGroup) -> BaseException:
    """Return the only leaf exception of a (possibly nested) group, or the group itself."""
    leaves = []
    stack = [eg]
    while stack:
        g = stack.pop()
        for exc in g.exceptions:
            (stack if isinstance(exc, BaseExceptionGroup) else leaves).append(exc)
    return leaves[0] if len(leaves) == 1 else eg


class ProviderError(Exception):
    pass


async def call(prompt: str) -> None:
    await anyio.sleep(0)
    raise ProviderError(f"429 for {prompt!r}")


async def public_api(prompts: list) -> None:
    try:
        async with anyio.create_task_group() as tg:
            for p in prompts:
                tg.start_soon(call, p)
    except BaseExceptionGroup as eg:
        exc = unwrap_single(eg)
        if exc is eg:
            raise
        raise exc from eg                       # keep the group as the cause for debugging


async def main() -> None:
    try:
        await public_api(["only one"])
    except ProviderError as exc:
        print("caller sees:", exc)


anyio.run(main)
# Output: caller sees: 429 for 'only one'
```

Never unwrap a group that contains the cancel exception plus a real error: re-raise the group. The
`unwrap_single` helper above returns the group unchanged whenever there is more than one leaf.

## Async generators and cancel scopes

Do not `yield` from inside a task group or cancel scope in an async generator. The consumer may stop
iterating at any time, and the generator is then finalised later in a different task. anyio reports this
with `RuntimeError: Attempted to exit cancel scope in a different task than it was entered in` (seen when
the loop shuts down async generators); trio has the same rule.

Bad:
```python
async def tokens(prompt):
    async with anyio.create_task_group() as tg:      # scope spans a yield
        tg.start_soon(keepalive)
        async for t in llm.stream(prompt):
            yield t
```

Good: a producer task feeds a memory object stream, owned by the caller's task group:
```python
import anyio
from anyio.streams.memory import MemoryObjectSendStream


async def produce_tokens(prompt: str, send: MemoryObjectSendStream) -> None:
    async with send:
        for token in prompt.split():
            await anyio.sleep(0.001)          # stands in for the model stream
            await send.send(token)


async def main() -> None:
    send, receive = anyio.create_memory_object_stream[str](8)
    async with anyio.create_task_group() as tg:
        tg.start_soon(produce_tokens, "tokens flow through a stream", send)
        async with receive:
            print([t async for t in receive])


anyio.run(main)
# Output: ['tokens', 'flow', 'through', 'a', 'stream']
```

An async *context manager* (`@asynccontextmanager` with one `yield`) may hold a task group open: the
`async with` statement guarantees it is exited in the same task.

## Threads, processes and cancellation

| Call | On cancellation |
|------|-----------------|
| `anyio.to_thread.run_sync(f)` | waits for `f` to finish, then raises the cancel exception |
| `anyio.to_thread.run_sync(f, abandon_on_cancel=True)` | returns immediately; the thread keeps running and its result is discarded |
| inside `f`: `anyio.from_thread.check_cancelled()` | raises the cancel exception in the worker, so long loops can stop cooperatively |
| `anyio.to_process.run_sync(f, cancellable=True)` | kills the worker process |
| `anyio.run_process` / `open_process` | the child process is killed when the awaiting scope is cancelled |
| trio: `trio.to_thread.run_sync(f, abandon_on_cancel=True)` | same as anyio (trio 0.23+) |

```python
import time

import anyio


def chunk_corpus(n: int) -> int:
    done = 0
    for _ in range(n):
        time.sleep(0.01)                          # blocking work
        anyio.from_thread.check_cancelled()       # cooperative cancellation point
        done += 1
    return done


async def main() -> None:
    start = time.monotonic()
    with anyio.move_on_after(0.05) as scope:
        await anyio.to_thread.run_sync(chunk_corpus, 1000)
    print(scope.cancelled_caught, time.monotonic() - start < 0.5)


anyio.run(main)
# Output: True True
```

## Ctrl-C and shutdown

- asyncio backend: on SIGINT, anyio's runner cancels the main task, so `finally` blocks and shielded
  cleanup run, and then `anyio.run` raises `KeyboardInterrupt` (verified with anyio 4.15).
- trio: `KeyboardInterrupt` is raised in the main task. With
  `trio.run(..., restrict_keyboard_interrupt_to_checkpoints=True)` it is raised only at checkpoints.
- Services: catch SIGTERM with `anyio.open_signal_receiver` and cancel the top-level task group's scope.
  Everything below shuts down in order, and each layer's `finally` runs (see the MIG027 recipe in
  [migration-playbook.md](migration-playbook.md#mig027-signals)).

## Checklist

- [ ] No `except get_cancelled_exc_class()` / `except trio.Cancelled` / `except asyncio.CancelledError`
      without `raise`.
- [ ] No bare `except:` or `except BaseException:` around awaits without `raise`.
- [ ] Every cleanup `await` is in `CancelScope(shield=True)` plus a timeout.
- [ ] Timeouts: one per external call, plus an outer budget; `TimeoutError` is handled where a fallback
      exists.
- [ ] Callers of task groups handle `ExceptionGroup` (`except*`), or the boundary unwraps single errors on
      purpose.
- [ ] No `yield` inside a task group or cancel scope in an async generator.
- [ ] Thread work that must stop promptly uses `abandon_on_cancel=True` or `from_thread.check_cancelled()`.
