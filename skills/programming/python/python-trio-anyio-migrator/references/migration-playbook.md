# Migration Playbook

A step-by-step, incremental path from asyncio to anyio (and optionally on to trio) that keeps the code
shippable after every commit. Each manual rule reported by `scripts/migrate_async.py` has a recipe below;
the self-contained ones run as-is on anyio 4.x and print the output shown.

## Contents

- [Phase 0: decide and inventory](#phase-0-decide-and-inventory)
- [Phase 1: tests first](#phase-1-tests-first)
- [Phase 2: mechanical rewrites](#phase-2-mechanical-rewrites)
- [Phase 3: manual items, in this order](#phase-3-manual-items-in-this-order)
- [Phase 4: cancellation review](#phase-4-cancellation-review)
- [Phase 5: second backend and CI gate](#phase-5-second-backend-and-ci-gate)
- [Mixed codebases](#mixed-codebases)
- [Recipes for every manual rule](#recipes-for-every-manual-rule)

## Phase 0: decide and inventory

1. Write down the reason for migrating: correct cancellation, no orphaned tasks, a library that must run
   under trio as well, or FastAPI code that is already on anyio. "It's nicer" is not enough on its own: on 3.11+
   `asyncio.TaskGroup` + `asyncio.timeout` give most of the structure.
2. List dependencies by backend (see the compatibility table in the SKILL.md). asyncio-only dependencies
   (asyncpg, aiohttp, aioboto3, redis.asyncio, motor) mean "anyio on the asyncio backend" is the realistic
   target for those modules.
3. Inventory:

```bash
python scripts/migrate_async.py src/ --json > migration.json
python scripts/migrate_async.py src/ | tail -1          # "N item(s) ...: X mechanical, Y manual"
python scripts/migrate_async.py src/ --select MIG014,MIG020,MIG021,MIG030   # the structural ones
```

Files whose items are all mechanical are cheap. Free tasks (MIG014), futures (MIG020), callbacks (MIG021)
and external cancellation (MIG030) are where the time goes, because they need a new ownership structure.

## Phase 1: tests first

Switch the test runner before touching production code, so every later step is checked:

```toml
# pyproject.toml
[tool.pytest.ini_options]
anyio_mode = "auto"        # recent anyio 4.x: every async test runs under the anyio plugin
# asyncio_mode = "auto"    # remove pytest-asyncio's auto mode: the two plugins must not both claim tests
```

Pin the backend to asyncio first (`anyio_backend` fixture returning `"asyncio"`). Tests that use
pytest-asyncio fixtures need `@pytest.mark.anyio` and their async fixtures will then run under anyio.
Details: [testing-with-anyio-and-trio.md](testing-with-anyio-and-trio.md). The suite must stay green on the
asyncio backend before you change anything else.

## Phase 2: mechanical rewrites

```bash
python scripts/migrate_async.py src/pkg/module.py --diff | less     # review
python scripts/migrate_async.py src/pkg/module.py --write           # needs zero manual items
python scripts/migrate_async.py src/pkg/ --write --force            # or: partial, keeps import asyncio
pytest -q                                                           # still green on asyncio
```

What the rewriter guarantees: each rewrite is behaviour-preserving at that call site (it refuses otherwise
and reports the reason), the output parses, and `import asyncio` disappears only when nothing uses it. What
it cannot guarantee: semantics outside the call site, which is why Phase 4 exists. Notable fine print:

| Rewrite | Behaviour change to know about |
|---------|-------------------------------|
| `asyncio.to_thread` -> `anyio.to_thread.run_sync` | cancellation waits for the thread (asyncio abandons it); threads come from anyio's limiter (40), not the loop executor |
| `asyncio.timeout` -> `anyio.fail_after` | identical on the asyncio backend; on trio `trio.fail_after` raises `TooSlowError` |
| `asyncio.Lock` -> `anyio.Lock` | releasing from another task raises `RuntimeError` (the tool refuses when `.release()` is called) |
| `asyncio.TimeoutError` -> `TimeoutError` | identical on 3.11+; on 3.9/3.10 correct only once the raiser is anyio too |
| `except asyncio.CancelledError` -> `get_cancelled_exc_class()` | identical class on asyncio; a handler that does not re-raise is flagged MIG031 |

Commit each file separately; review is easier and a bisect stays useful.

## Phase 3: manual items, in this order

1. **MIG014 / MIG030 / MIG021: give every task an owner.** Find the scope that should outlive the task
   (the request, the job, the app lifespan) and open a task group there.
2. **MIG011 / MIG012 / MIG022 / MIG023: fan-out shapes.** gather, wait and as_completed become task groups
   writing into lists or memory streams.
3. **MIG015 / MIG016: queues -> memory object streams.**
4. **MIG013 / MIG024 / MIG032: timeouts and shielding -> cancel scopes.**
5. **MIG017 / MIG028 / MIG019 / MIG018: threads and loop access -> to_thread / from_thread / portals.**
6. **MIG025 / MIG026 / MIG027: subprocess, sockets, signals.**
7. **MIG020 / MIG029 / MIG033 / MIG099: futures, introspection, odds and ends.**

## Phase 4: cancellation review

For every file, check:

- [ ] every `except get_cancelled_exc_class()` ends with `raise` (MIG031 finds the obvious ones);
- [ ] no `except BaseException:` or bare `except:` without re-raise around awaits;
- [ ] every `await` inside `finally` / `except` that must run during cancellation is inside
      `with anyio.CancelScope(shield=True):` and bounded by `move_on_after`;
- [ ] timeouts wrap the smallest unit that can hang (one model call, one tool call), and an outer budget
      wraps the whole request;
- [ ] long CPU loops have a checkpoint or run in a thread/process;
- [ ] `to_thread.run_sync` calls that must stop promptly use `abandon_on_cancel=True` and are idempotent.

Deep dive: [cancellation-and-exception-groups.md](cancellation-and-exception-groups.md).

## Phase 5: second backend and CI gate

```yaml
# .github/workflows/ci.yml (excerpt)
- run: python skills/.../scripts/migrate_async.py src/ --check     # exit 1 while asyncio remains
- run: pytest -q                                                    # anyio_backend over asyncio + trio
```

Keep intentional asyncio code (an asyncpg adapter, a uvloop tweak) behind `# noqa: MIG018`-style comments
with a reason, so `--check` stays meaningful. Add trio to the backend matrix only for packages free of
asyncio-only dependencies; for applications it is fine to stay on the asyncio backend forever.

## Mixed codebases

anyio on the asyncio backend *is* asyncio, so the two styles coexist:

```python
import asyncio

import anyio


async def legacy_fetch(n: int) -> int:          # untouched asyncio code (or an asyncpg call)
    await asyncio.sleep(0.01)
    return n * 2


async def main() -> None:
    results = {}

    async def run_one(n: int) -> None:
        with anyio.fail_after(1):               # anyio scope around native asyncio awaits
            results[n] = await legacy_fetch(n)

    async with anyio.create_task_group() as tg:
        for n in range(3):
            tg.start_soon(run_one, n)
    print(sorted(results.items()))


anyio.run(main)                                 # backend="asyncio" (default)
# Output: [(0, 0), (1, 2), (2, 4)]
```

Rules for mixed code:

- anyio code may call asyncio code; under `backend="trio"` that call fails, so mark those modules
  asyncio-only (and keep them out of the trio test matrix).
- asyncio code may call anyio functions as long as it is running on an asyncio loop (anyio detects it).
  `asyncio.run(main())` where `main` uses anyio task groups works.
- Tasks created by asyncio libraries are not owned by your task groups; wrap the library call so the task
  group sees a single awaited call.
- Do not mix `asyncio.Lock` and `anyio.Lock` for the same resource; pick one per resource.

Bridging trio and asyncio-only libraries (trio-asyncio):

```python
# pip install trio trio-asyncio   (not run here: trio is not installed in this environment)
import trio
import trio_asyncio


async def main():
    async with trio_asyncio.open_loop():
        rows = await trio_asyncio.aio_as_trio(fetch_rows_with_asyncpg)()   # asyncio coroutine fn
        print(len(rows))

trio.run(main)
```

Treat this as a transitional measure: check trio-asyncio's support for your Python version, and plan to
replace the asyncio-only dependency.

## Recipes for every manual rule

### MIG011 gather (fail-fast, ordered results)

```python
import anyio


async def call_llm(prompt: str) -> str:
    await anyio.sleep(0.01 * len(prompt))
    return prompt.upper()


async def fan_out(prompts: list) -> list:
    results: list = [None] * len(prompts)

    async def run_one(i: int, prompt: str) -> None:
        results[i] = await call_llm(prompt)

    async with anyio.create_task_group() as tg:
        for i, prompt in enumerate(prompts):
            tg.start_soon(run_one, i, prompt)
    return results


print(anyio.run(fan_out, ["ccc", "a", "bb"]))
# Output: ['CCC', 'A', 'BB']
```

Difference from `gather`: when one call fails, the others are cancelled and an `ExceptionGroup` is raised.
`gather` (without `return_exceptions`) raises the first error and lets the rest keep running unobserved.

### MIG012 gather(return_exceptions=True) (partial success)

```python
import anyio


async def score(sample: str) -> float:
    await anyio.sleep(0)
    if sample == "bad":
        raise ValueError("unparseable judge output")
    return len(sample) / 10


async def eval_all(samples: list) -> list:
    results: list = [None] * len(samples)

    async def run_one(i: int, sample: str) -> None:
        try:
            results[i] = await score(sample)
        except Exception as exc:              # Exception only: cancellation still propagates
            results[i] = exc

    async with anyio.create_task_group() as tg:
        for i, sample in enumerate(samples):
            tg.start_soon(run_one, i, sample)
    return results


print(anyio.run(eval_all, ["good", "bad", "great"]))
# Output: [0.4, ValueError('unparseable judge output'), 0.5]
```

### MIG013 wait_for / MIG032 advanced timeouts

```python
import anyio


async def slow_model() -> str:
    await anyio.sleep(1)
    return "late"


async def main() -> None:
    try:
        with anyio.fail_after(0.05):          # was: await asyncio.wait_for(slow_model(), 0.05)
            reply = await slow_model()
    except TimeoutError:
        reply = "fallback"
    print(reply)

    with anyio.move_on_after(0.05) as scope:  # give up quietly
        await slow_model()
    print("gave up:", scope.cancelled_caught)

    with anyio.fail_after(0.05) as scope:     # was: cm.reschedule(...)
        scope.deadline = anyio.current_time() + 2
        print(await slow_model())


anyio.run(main)
# Output:
# fallback
# gave up: True
# late
```

### MIG014 create_task: free tasks get an owner

```python
import anyio


async def refresh_index(stop_after: int) -> None:
    for i in range(stop_after):
        await anyio.sleep(0.01)
    print("index refreshed", stop_after, "times")


async def handle_requests(tg) -> None:
    tg.start_soon(refresh_index, 3)           # was: asyncio.create_task(refresh_index(3))
    print("request handled")


async def main() -> None:
    async with anyio.create_task_group() as tg:   # the owner: app/job lifetime
        await handle_requests(tg)


anyio.run(main)
# Output:
# request handled
# index refreshed 3 times
```

When a result is needed, the child writes it somewhere (`results[key] = ...`) or sends it into a memory
stream. On anyio 4.14+ `tg.create_task(coro)` returns a `TaskHandle` you can await; use it only if you do
not need trio or older anyio.

### MIG015 / MIG016 Queue, join and task_done

```python
import anyio
from anyio.streams.memory import MemoryObjectReceiveStream


async def embed_worker(name: str, docs: MemoryObjectReceiveStream, out: list) -> None:
    async with docs:
        async for doc in docs:                 # ends when every send clone is closed
            await anyio.sleep(0.001)
            out.append((doc, name))


async def main() -> None:
    out: list = []
    send, receive = anyio.create_memory_object_stream[str](max_buffer_size=4)
    async with anyio.create_task_group() as tg:
        for n in range(3):
            tg.start_soon(embed_worker, f"w{n}", receive.clone(), out)
        receive.close()                        # only the workers' clones remain
        async with send:                       # closing == "no more work"
            for i in range(10):
                await send.send(f"doc{i}")     # blocks while 4 are buffered: backpressure
    # leaving the task group == queue.join(): every doc has been processed
    print(len(out), sorted({w for _, w in out}) <= ["w0", "w1", "w2"])


anyio.run(main)
# Output: 10 True
```

`PriorityQueue` has no stream equivalent; keep a `heapq` guarded by an `anyio.Condition`, or sort batches
before sending.

### MIG017 run_in_executor

```python
import time

import anyio


def ocr_page(page: int) -> str:
    time.sleep(0.01)                           # blocking SDK / CPU-light C code
    return f"text of page {page}"


async def main() -> None:
    limiter = anyio.CapacityLimiter(4)         # was: ThreadPoolExecutor(max_workers=4)
    pages: dict = {}

    async def run_one(p: int) -> None:
        pages[p] = await anyio.to_thread.run_sync(ocr_page, p, limiter=limiter)

    async with anyio.create_task_group() as tg:
        for p in range(8):
            tg.start_soon(run_one, p)
    print(len(pages), pages[7])


anyio.run(main)
# Output: 8 text of page 7
```

### MIG018 event loop access and MIG028 run_coroutine_threadsafe

```python
import threading

import anyio
from anyio.from_thread import start_blocking_portal


async def embed(text: str) -> int:
    await anyio.sleep(0)
    return len(text)


def sync_callback_from_worker(text: str) -> int:
    # inside a to_thread worker: call back into the event loop
    return anyio.from_thread.run(embed, text)


async def main() -> None:
    print(await anyio.to_thread.run_sync(sync_callback_from_worker, "from worker"))


anyio.run(main)

# From a thread anyio did not start (Celery task, Streamlit callback, CLI):
with start_blocking_portal() as portal:
    print(portal.call(embed, "from portal"), threading.current_thread().name)
# Output:
# 11
# 11 MainThread
```

Never call `portal.call` or `from_thread.run` from inside the event loop thread: they block waiting for
the loop they are blocking.

### MIG019 call_soon / call_later

```python
import anyio


async def later(delay: float, fn, *args) -> None:
    await anyio.sleep(delay)
    fn(*args)


async def main() -> None:
    async with anyio.create_task_group() as tg:
        tg.start_soon(later, 0.02, print, "flush metrics")   # was: loop.call_later(0.02, ...)
        tg.start_soon(later, 10, print, "never printed")
        await anyio.sleep(0.05)
        tg.cancel_scope.cancel()                              # cancel the remaining timer


anyio.run(main)
# Output: flush metrics
```

To cancel one timer without the others, start it through a helper that owns its own scope (see MIG030).

### MIG020 Future and MIG021 add_done_callback

```python
import anyio


class OneShot:
    """Replacement for an asyncio.Future set by one task and awaited by another."""

    def __init__(self) -> None:
        self._event = anyio.Event()
        self._value = None
        self._error = None

    def set_result(self, value) -> None:
        self._value = value
        self._event.set()

    def set_exception(self, error: BaseException) -> None:
        self._error = error
        self._event.set()

    async def wait(self):
        await self._event.wait()
        if self._error is not None:
            raise self._error
        return self._value


async def tool_runner(result: OneShot) -> None:
    try:
        await anyio.sleep(0.01)
        result.set_result({"tool": "search", "hits": 3})
    finally:
        print("tool finished")                 # was: task.add_done_callback(...)


async def main() -> None:
    result = OneShot()
    async with anyio.create_task_group() as tg:
        tg.start_soon(tool_runner, result)
        print(await result.wait())


anyio.run(main)
# Output:
# tool finished
# {'tool': 'search', 'hits': 3}
```

### MIG022 wait(FIRST_COMPLETED) and MIG023 as_completed

```python
import anyio


async def retriever(name: str, delay: float) -> str:
    await anyio.sleep(delay)
    return name


async def first_completed() -> str:
    winner = None

    async with anyio.create_task_group() as tg:
        async def run(name: str, delay: float) -> None:
            nonlocal winner
            result = await retriever(name, delay)
            if winner is None:
                winner = result
                tg.cancel_scope.cancel()       # cancel the losers

        for name, delay in [("dense", 0.03), ("bm25", 0.01), ("hybrid", 0.05)]:
            tg.start_soon(run, name, delay)
    return winner


async def in_completion_order() -> list:
    order = []
    send, receive = anyio.create_memory_object_stream[str](3)
    async with anyio.create_task_group() as tg:
        async def run(name: str, delay: float, out) -> None:
            async with out:
                await out.send(await retriever(name, delay))

        async with send:
            for name, delay in [("dense", 0.03), ("bm25", 0.01), ("hybrid", 0.02)]:
                tg.start_soon(run, name, delay, send.clone())
        async with receive:
            async for name in receive:
                order.append(name)
    return order


async def main() -> None:
    print(await first_completed())
    print(await in_completion_order())


anyio.run(main)
# Output:
# bm25
# ['bm25', 'hybrid', 'dense']
```

### MIG024 shield

```python
import anyio


async def flush(buffer: list) -> None:
    await anyio.sleep(0.01)
    print("flushed", len(buffer))


async def main() -> None:
    buffer = [1, 2, 3]
    with anyio.move_on_after(0.005):
        try:
            await anyio.sleep(1)
        finally:
            with anyio.CancelScope(shield=True), anyio.move_on_after(2):
                await flush(buffer)           # was: await asyncio.shield(flush(buffer))


anyio.run(main)
# Output: flushed 3
```

Unlike `asyncio.shield`, the shielded code is part of the current task: the caller waits for it, and an
error inside it propagates normally.

### MIG025 subprocess

```python
import sys

import anyio


async def main() -> None:
    result = await anyio.run_process([sys.executable, "-c", "print(6 * 7)"])   # check=True default
    print(result.returncode, result.stdout.decode().strip())

    async with await anyio.open_process([sys.executable, "-c", "print('a'); print('b')"]) as proc:
        chunks = [chunk async for chunk in proc.stdout]
    print(b"".join(chunks).decode().split())


anyio.run(main)
# Output:
# 0 42
# ['a', 'b']
```

### MIG026 sockets and streams

```python
import anyio
from anyio.streams.buffered import BufferedByteReceiveStream


async def handler(client) -> None:
    async with client:
        line = await BufferedByteReceiveStream(client).receive_until(b"\n", 1024)
        await client.send(line.upper() + b"\n")


async def main() -> None:
    listener = await anyio.create_tcp_listener(local_host="127.0.0.1", local_port=0)
    port = listener.extra(anyio.abc.SocketAttribute.local_port)
    async with anyio.create_task_group() as tg:
        tg.start_soon(listener.serve, handler)
        async with await anyio.connect_tcp("127.0.0.1", port) as stream:
            await stream.send(b"ping\n")
            print(await BufferedByteReceiveStream(stream).receive_until(b"\n", 1024))
        tg.cancel_scope.cancel()


anyio.run(main)
# Output: b'PING'
```

For TLS: `await anyio.connect_tcp(host, 443, tls=True)` (uses `ssl.create_default_context()` unless you
pass `ssl_context=`).

### MIG027 signals

```python
import os
import signal

import anyio


async def serve_forever() -> None:
    await anyio.sleep_forever()


async def main() -> None:
    async with anyio.create_task_group() as tg:
        tg.start_soon(serve_forever)
        with anyio.open_signal_receiver(signal.SIGTERM, signal.SIGINT) as signals:
            os.kill(os.getpid(), signal.SIGTERM)          # simulate `kill <pid>` (Unix only)
            async for signum in signals:
                print("shutting down on", signal.Signals(signum).name)
                tg.cancel_scope.cancel()
                break


anyio.run(main)
# Output: shutting down on SIGTERM
```

### MIG029 introspection, MIG033 coroutine checks

```python
import inspect

import anyio


async def tool() -> None:
    print("running in", anyio.get_current_task().name)


async def main() -> None:
    print(inspect.iscoroutinefunction(tool))           # was: asyncio.iscoroutinefunction
    async with anyio.create_task_group() as tg:
        tg.start_soon(tool, name="tool:search")


anyio.run(main)
# Output:
# True
# running in tool:search
```

### MIG030 cancel one task from outside

```python
import anyio


async def cancellable(job, *, task_status=anyio.TASK_STATUS_IGNORED) -> None:
    with anyio.CancelScope() as scope:
        task_status.started(scope)             # hand the scope to the parent
        await job()
    if scope.cancelled_caught:
        print("job cancelled")


async def crawl() -> None:
    await anyio.sleep(10)


async def main() -> None:
    async with anyio.create_task_group() as tg:
        scope = await tg.start(cancellable, crawl)
        await anyio.sleep(0.01)
        scope.cancel()                         # was: task.cancel()


anyio.run(main)
# Output: job cancelled
```

### MIG031 swallowed cancellation

```python
import anyio


async def stream_tokens(log: list) -> None:
    try:
        await anyio.sleep(10)
    except anyio.get_cancelled_exc_class():
        log.append("client went away")
        raise                                  # without this the scope cannot finish cleanly


async def main() -> None:
    log: list = []
    with anyio.move_on_after(0.01):
        await stream_tokens(log)
    print(log)


anyio.run(main)
# Output: ['client went away']
```

### MIG099 everything else

`asyncio.Barrier` -> counter + Event:

```python
import anyio


class Barrier:
    def __init__(self, parties: int) -> None:
        self.parties, self.count, self.event = parties, 0, anyio.Event()

    async def wait(self) -> None:
        self.count += 1
        if self.count == self.parties:
            self.event.set()
        await self.event.wait()


async def worker(barrier: Barrier, name: str, out: list) -> None:
    out.append(f"{name} loaded model")
    await barrier.wait()
    out.append(f"{name} serving")


async def main() -> None:
    barrier, out = Barrier(2), []
    async with anyio.create_task_group() as tg:
        tg.start_soon(worker, barrier, "gpu0", out)
        tg.start_soon(worker, barrier, "gpu1", out)
    print(out[:2], len(out))


anyio.run(main)
# Output: ['gpu0 loaded model', 'gpu1 loaded model'] 4
```

This barrier is single-use (anyio Events cannot be reset); create a new one per phase.
