# contextlib Reference

Every public tool in `contextlib`, with exact behaviour, version tags and
AI-engineering examples.

## Contents

- [Overview table](#overview-table)
- [@contextmanager](#contextmanager)
- [@asynccontextmanager](#asynccontextmanager)
- [ExitStack](#exitstack)
- [AsyncExitStack](#asyncexitstack)
- [closing and aclosing](#closing-and-aclosing)
- [suppress](#suppress)
- [redirect_stdout and redirect_stderr](#redirect_stdout-and-redirect_stderr)
- [nullcontext](#nullcontext)
- [chdir (3.11)](#chdir-311)
- [AbstractContextManager and AbstractAsyncContextManager](#abstractcontextmanager-and-abstractasynccontextmanager)
- [ContextDecorator and AsyncContextDecorator](#contextdecorator-and-asynccontextdecorator)

## Overview table

| Tool | Since | Use for |
|------|-------|---------|
| `contextmanager` | 2.5 | Turn a one-`yield` generator into a context manager |
| `asynccontextmanager` | 3.7 | Same for `async def` generators (`async with`) |
| `ExitStack` | 3.3 | Dynamic number of managers/callbacks; ownership transfer with `pop_all()` |
| `AsyncExitStack` | 3.7 | Async version; mixes sync and async managers |
| `closing(obj)` | 2.5 | Call `obj.close()` on exit for objects that are not managers |
| `aclosing(obj)` | 3.10 | `await obj.aclose()` on exit (async generators, async clients) |
| `suppress(*excs)` | 3.4 | Ignore specific exceptions (3.12: also inside exception groups) |
| `redirect_stdout(f)` / `redirect_stderr(f)` | 3.4 / 3.5 | Capture prints from chatty libraries |
| `nullcontext(value=None)` | 3.7 (async 3.10) | "No-op manager" for conditional `with` |
| `chdir(path)` | 3.11 | Temporarily change cwd |
| `AbstractContextManager` | 3.6 | ABC with default `__enter__` returning self |
| `AbstractAsyncContextManager` | 3.7 | Async ABC |
| `ContextDecorator` | 3.2 | Let a class manager also work as a decorator |
| `AsyncContextDecorator` | 3.10 | Async version |

## @contextmanager

```python
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def openai_timeout(client, seconds: float) -> Iterator[None]:
    """Temporarily change a client's timeout."""
    old = client.timeout
    client.timeout = seconds        # setup: before try, so a failed setup is not "undone"
    try:
        yield                       # the with-body runs here
    finally:
        client.timeout = old        # teardown: always
```

How it works:

1. Calling `openai_timeout(...)` creates a `_GeneratorContextManager`; nothing runs yet.
2. `__enter__` calls `next(gen)`; the value yielded is bound to `as`.
3. Normal exit: `__exit__` calls `next(gen)` again and expects `StopIteration`.
   A second `yield` → `RuntimeError("generator didn't stop")`.
4. Exception in body: `__exit__` calls `gen.throw(exc)`; the exception is raised
   **at the `yield`**. If the generator:
   - lets it propagate → it propagates out of the `with` (normal).
   - catches it and returns → the exception is **suppressed**.
   - catches it and yields again → `RuntimeError("generator didn't stop after throw()")`.
   - raises a different exception → that one propagates (chained).

### The four shapes

```python
@contextmanager
def always_cleanup() -> Iterator[Resource]:
    r = acquire()
    try:
        yield r
    finally:
        release(r)                  # runs on success and on error


@contextmanager
def commit_or_rollback(conn) -> Iterator[Connection]:
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise                       # MUST re-raise or the error is swallowed
    else:
        conn.commit()               # only on success


@contextmanager
def log_errors(step: str) -> Iterator[None]:
    try:
        yield
    except Exception as exc:
        log.error("step %s failed: %s", step, exc)
        raise


@contextmanager
def ignore(*excs: type) -> Iterator[None]:   # deliberate suppression (= contextlib.suppress)
    try:
        yield
    except excs:
        pass
```

### Rules

| Rule | Why |
|------|-----|
| Exactly one `yield` executed per call | Zero → `RuntimeError("generator didn't yield")`; two → `RuntimeError`. Different branches of an `if` are fine. |
| `yield` inside `try/finally` (or `try/except ... raise`, or a `with`) whenever code follows it | Otherwise the cleanup is skipped when the body raises. |
| Setup before `try` | If setup raises, there is nothing to clean up, and the finally would touch undefined names. |
| Re-raise in every `except` around `yield` unless suppression is the point | Returning normally after catching = suppression. |
| Never `yield` inside a loop | Second iteration = second yield. |
| Each call returns a new single-use object | `cm = f(); with cm: ...; with cm: ...` fails on the second `with`. |

### Used as a decorator

Objects from `@contextmanager` are `ContextDecorator`s, so they decorate
functions; each call re-creates the generator:

```python
@contextmanager
def traced(name: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        metrics.observe(name, time.perf_counter() - start)


@traced("rerank")
def rerank(query: str, docs: list) -> list:
    ...
```

The decorator form cannot give the function access to the yielded value.

## @asynccontextmanager

```python
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx


@asynccontextmanager
async def llm_http(base_url: str) -> AsyncIterator[httpx.AsyncClient]:
    client = httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(60, connect=5))
    try:
        yield client
    finally:
        await client.aclose()


async def main() -> None:
    async with llm_http("https://api.example.com") as http:
        r = await http.post("/v1/chat/completions", json=payload)
```

Same rules as `@contextmanager`. Extra: on cancellation, `CancelledError` is
thrown in at the `yield`; `finally` runs, but any `await` inside `finally` can be
cancelled again if the task is cancelled twice; keep cleanup short or shield it
(see [async-context-managers.md](async-context-managers.md)).
3.10+: usable as a decorator on `async def` functions.

## ExitStack

`ExitStack` is a context manager that holds a LIFO stack of exit callbacks.

| Method | Effect |
|--------|--------|
| `enter_context(cm)` | Enters `cm`, pushes its `__exit__`, returns `__enter__`'s result. 3.11+: `TypeError` if `cm` is not a context manager. |
| `push(exit_or_cm)` | Pushes an `__exit__`-style callable `(exc_type, exc, tb)` or a manager's exit **without entering** |
| `callback(fn, *args, **kwargs)` | Pushes a plain cleanup callable; returns `fn` (usable as decorator) |
| `pop_all()` | Moves all callbacks to a new `ExitStack` and returns it; the original becomes empty |
| `close()` | Unwinds immediately (same as leaving the `with`) |

### Variable number of resources

```python
from contextlib import ExitStack
from pathlib import Path


def merge_shards(shard_paths: list[Path], out_path: Path) -> int:
    with ExitStack() as stack:
        shards = [stack.enter_context(p.open(encoding="utf-8")) for p in shard_paths]
        out = stack.enter_context(out_path.open("w", encoding="utf-8"))
        n = 0
        for f in shards:
            for line in f:
                out.write(line)
                n += 1
        return n
    # every file closed here, in reverse order, even if one open() failed midway
```

### Conditional managers

```python
def generate(model, batch, *, use_amp: bool, profile: bool):
    with ExitStack() as stack:
        stack.enter_context(torch.inference_mode())
        if use_amp:
            stack.enter_context(torch.autocast("cuda", dtype=torch.bfloat16))
        if profile:
            prof = stack.enter_context(torch.profiler.profile())
        return model.generate(**batch)
```

### Callbacks and undo logs

```python
with ExitStack() as stack:
    old_level = logger.level
    logger.setLevel(logging.DEBUG)
    stack.callback(logger.setLevel, old_level)

    tmp = Path(tempfile.mkdtemp())
    stack.callback(shutil.rmtree, tmp, ignore_errors=True)

    run_agent(workdir=tmp)
```

### Ownership transfer with pop_all

Acquire several resources; if any step fails, release the ones already
acquired; on success hand them to a longer-lived owner:

```python
class EmbeddingService:
    def __init__(self, model_path: str, index_path: str) -> None:
        with ExitStack() as stack:
            self.model_file = stack.enter_context(open(model_path, "rb"))
            self.index = stack.enter_context(closing(load_index(index_path)))
            self._resources = stack.pop_all()     # nothing is closed on success

    def close(self) -> None:
        self._resources.close()

    def __enter__(self) -> "EmbeddingService":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
```

### Exception behaviour

- Callbacks run LIFO; **all** of them run even if some raise.
- If a callback raises, later callbacks see that exception; the final exception
  propagates with correct `__context__` chaining.
- A pushed `__exit__` returning `True` suppresses the exception for the
  remaining (outer) callbacks too.

## AsyncExitStack

Async version. Holds both kinds:

| Method | For |
|--------|-----|
| `await enter_async_context(acm)` | async managers |
| `enter_context(cm)` | sync managers |
| `push_async_exit(aexit_or_acm)` | async `__aexit__`-style callables |
| `push_async_callback(coro_fn, *args)` | async cleanup callables |
| `callback(fn, *args)` | sync cleanup callables |
| `pop_all()`, `await aclose()` | transfer / unwind |

```python
from contextlib import AsyncExitStack


async def run_agent_with_tools(tool_configs: list[dict]) -> str:
    async with AsyncExitStack() as stack:
        http = await stack.enter_async_context(httpx.AsyncClient(timeout=30))
        sessions = [
            await stack.enter_async_context(connect_mcp_server(cfg))   # each tool server
            for cfg in tool_configs
        ]
        stack.push_async_callback(flush_traces)
        return await agent_loop(http, sessions)
```

## closing and aclosing

`closing(thing)` calls `thing.close()` on exit and returns `thing` from `__enter__`.
Use it for objects with `close()` but no context-manager support (or when you
want the guarantee explicit).

```python
from contextlib import closing
import sqlite3

with closing(sqlite3.connect("evals.db")) as conn:
    with conn:                                 # sqlite3 connection's own CM = transaction, NOT close
        conn.execute("INSERT INTO runs VALUES (?, ?)", (run_id, score))
```

`aclosing(agen)` (3.10) awaits `agen.aclose()`. Essential for async generators
that hold resources (streaming LLM responses), because an un-exhausted async
generator is only finalized whenever the event loop gets to it:

```python
from contextlib import aclosing


async def stream_tokens(client, prompt):
    async with client.stream("POST", "/v1/completions", json={"prompt": prompt, "stream": True}) as r:
        async for line in r.aiter_lines():
            if line.startswith("data: "):
                yield line[6:]


async def first_sentence(client, prompt) -> str:
    out = []
    async with aclosing(stream_tokens(client, prompt)) as tokens:
        async for tok in tokens:
            out.append(tok)
            if tok.endswith("."):
                break                 # aclose() runs now: the HTTP stream is closed immediately
    return "".join(out)
```

Pre-3.10 equivalent:

```python
@asynccontextmanager
async def aclosing_compat(agen):
    try:
        yield agen
    finally:
        await agen.aclose()
```

## suppress

```python
from contextlib import suppress

with suppress(FileNotFoundError):
    os.remove(cache_path)

with suppress(KeyError, IndexError):
    usage = response["usage"]["completion_tokens"]
```

| Fact | Detail |
|------|--------|
| Exits the block at the first matching exception | Statements after the failing line in the block do **not** run |
| Re-entrant | Can be nested and reused |
| 3.12+ | Strips matching exceptions out of a `BaseExceptionGroup` and re-raises the rest |
| Do not use for broad types | `suppress(Exception)` hides bugs; log instead |

## redirect_stdout and redirect_stderr

Temporarily rebind `sys.stdout`/`sys.stderr`. Useful for capturing output of
libraries that `print` (tokenizer downloads, progress bars that print, tools an
agent runs in-process).

```python
import io
from contextlib import redirect_stdout, redirect_stderr

buf = io.StringIO()
with redirect_stdout(buf), redirect_stderr(buf):
    result = run_python_tool(code)        # in-process tool call
tool_output = buf.getvalue()[-4000:]      # truncate before sending back to the LLM
```

Limits:

- Process-global: other threads printing during the block are captured too.
  Not safe for concurrent agents in threads.
- Does not affect output written directly to file descriptor 1/2 (C extensions,
  subprocesses). For those use `subprocess.run(capture_output=True)` or
  `os.dup2`-based redirection.
- Re-entrant.

## nullcontext

```python
from contextlib import nullcontext

def embed(texts, model, *, no_grad: bool = True):
    guard = torch.no_grad() if no_grad else nullcontext()
    with guard:
        return model(texts)


def write_results(rows, out=None):
    # caller-owned stream vs file we open and must close
    cm = open("results.jsonl", "w") if out is None else nullcontext(out)
    with cm as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
```

`nullcontext(enter_result)` returns `enter_result` from `__enter__`. 3.10+:
supports `async with`.

## chdir (3.11)

```python
from contextlib import chdir

with chdir(sandbox_dir):
    subprocess.run(["pytest", "-q"], check=True)
```

Not thread-safe or asyncio-safe (cwd is process-wide). Reusable but not
re-entrant in a meaningful sense (it records the cwd at each entry).
Backport for 3.9/3.10 is the `cwd` recipe in [recipes.md](recipes.md).
Prefer `subprocess.run(..., cwd=dir)` when you only need it for a child process.

## AbstractContextManager and AbstractAsyncContextManager

```python
from contextlib import AbstractContextManager


class TokenBudget(AbstractContextManager):
    """__enter__ defaults to returning self; only __exit__ is abstract."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.used = 0

    def charge(self, n: int) -> None:
        self.used += n
        if self.used > self.limit:
            raise BudgetExceeded(self.used, self.limit)

    def __exit__(self, exc_type, exc, tb) -> None:
        metrics.gauge("tokens.used", self.used)
```

- Subclassing gives `__enter__` returning `self` and a `__subclasshook__`, so
  `isinstance(x, AbstractContextManager)` is true for any object with both
  methods.
- Subscriptable for typing since 3.9: `AbstractContextManager[Connection]`.
- Recent typeshed stubs model a second type parameter for the `__exit__` return
  type (whether the manager may suppress); at runtime pass just one.

## ContextDecorator and AsyncContextDecorator

```python
from contextlib import ContextDecorator


class log_latency(ContextDecorator):
    def __init__(self, name: str) -> None:
        self.name = name

    def __enter__(self) -> "log_latency":
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        log.info("%s %.1fms", self.name, (time.perf_counter() - self.t0) * 1000)


@log_latency("retrieve")
def retrieve(query: str): ...

with log_latency("rerank"):
    ...
```

Caveats:

- The same instance is reused for every call of the decorated function; state
  set in `__enter__` (like `self.t0`) is shared, so concurrent calls from
  threads race. Override the private hook `_recreate_cm(self)` to return a fresh copy, or use a
  `@contextmanager` function (which recreates its generator each call).
- `AsyncContextDecorator` (3.10) does the same for `async def` functions with
  `__aenter__`/`__aexit__`.
