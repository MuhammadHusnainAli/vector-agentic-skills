# The Context Manager Protocol

Exact semantics of `with`, `__enter__`/`__exit__`, return values, exception
suppression, re-entrancy and reusability. Everything here applies to Python 3.9+
unless tagged.

## Contents

- [What `with` actually does](#what-with-actually-does)
- [`__enter__`](#__enter__)
- [`__exit__` arguments and return value](#__exit__-arguments-and-return-value)
- [Exceptions raised inside `__exit__`](#exceptions-raised-inside-__exit__)
- [Multiple items and parenthesized `with` (3.10)](#multiple-items-and-parenthesized-with-310)
- [Single-use, reusable and re-entrant managers](#single-use-reusable-and-re-entrant-managers)
- [Typing context managers](#typing-context-managers)
- [Class vs generator: choosing](#class-vs-generator-choosing)
- [Version notes](#version-notes)

## What `with` actually does

`with EXPR as TARGET: BODY` is (PEP 343, simplified but faithful):

```python
manager = EXPR
enter = type(manager).__enter__      # looked up on the TYPE, not the instance
exit_ = type(manager).__exit__
value = enter(manager)
hit_except = False
try:
    TARGET = value                   # assignment happens inside the try
    BODY
except BaseException as exc:
    hit_except = True
    if not exit_(manager, type(exc), exc, exc.__traceback__):
        raise                        # re-raise unless __exit__ returned truthy
finally:
    if not hit_except:
        exit_(manager, None, None, None)
```

Consequences you must know:

| Fact | Consequence |
|------|-------------|
| `__enter__`/`__exit__` are looked up on the type | Assigning `obj.__exit__ = f` on an instance does nothing; missing methods raise `TypeError` (3.11+: "object does not support the context manager protocol"; older: `AttributeError: __enter__`). |
| `__exit__` is looked up **before** `__enter__` runs | A class without `__exit__` fails before any setup happens. |
| If `__enter__` raises, `__exit__` is **not** called | Setup must clean up its own partial work (or use `ExitStack`, see below). |
| `TARGET = value` is inside the try | If unpacking `as (a, b)` fails, `__exit__` still runs. |
| `__exit__` runs for `return`, `break`, `continue` | Leaving the block by any route triggers cleanup with `(None, None, None)`. |
| `BaseException` is caught | `KeyboardInterrupt`, `SystemExit`, `asyncio.CancelledError` (a `BaseException` since 3.8) and `GeneratorExit` all go through `__exit__`. |

### Partial setup inside `__enter__`

```python
class RagSession:
    """Opens a vector-store connection and an LLM HTTP client together."""

    def __init__(self, dsn: str, base_url: str) -> None:
        self.dsn = dsn
        self.base_url = base_url

    def __enter__(self) -> "RagSession":
        self.db = connect_vector_store(self.dsn)
        try:
            self.http = httpx.Client(base_url=self.base_url, timeout=30)
        except BaseException:
            self.db.close()          # __exit__ will NOT run if __enter__ raises
            raise
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self.http.close()
        finally:
            self.db.close()          # close both even if the first close fails
```

The same thing with `ExitStack`, which scales to N resources:

```python
from contextlib import ExitStack


class RagSession:
    def __init__(self, dsn: str, base_url: str) -> None:
        self.dsn, self.base_url = dsn, base_url
        self._stack = ExitStack()

    def __enter__(self) -> "RagSession":
        with ExitStack() as stack:                       # unwinds if anything below fails
            self.db = stack.enter_context(closing(connect_vector_store(self.dsn)))
            self.http = stack.enter_context(httpx.Client(base_url=self.base_url))
            self._stack = stack.pop_all()                # success: transfer ownership
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._stack.close()
```

## `__enter__`

- Its return value is bound to the `as` target. Returning nothing binds `None`:
  the classic bug `with Session() as s: s.query(...)` → `AttributeError: 'NoneType'`.
- Return `self` for resource objects (files, clients, sessions).
- Return something else when the manager is a *guard* around another object:
  `decimal.localcontext()` returns the new context, a DB transaction manager can
  return the connection, `torch.no_grad()` returns `None` (nothing to bind).
- Keep `__enter__` cheap and idempotent-safe; do expensive work in `__init__`
  only if the object is meant to be constructed once and entered later.

```python
class PromptCache:
    def __enter__(self) -> "PromptCache":     # annotate with the class (string or `Self`)
        self._conn = sqlite3.connect(self.path)
        return self
```

## `__exit__` arguments and return value

Signature: `__exit__(self, exc_type, exc_value, traceback)`.

| Situation | Arguments |
|-----------|-----------|
| Body finished normally / `return` / `break` | `(None, None, None)` |
| Body raised `E` | `(type(E), E, E.__traceback__)` |

Return value:

| `__exit__` returns | Effect |
|--------------------|--------|
| `None`, `False`, any falsy value | Exception (if any) propagates. **Default; almost always what you want.** |
| `True` or any truthy value | Exception is **suppressed**; execution continues after the `with`. |

Rules:

1. Never `raise exc` yourself to propagate — return falsy and let the interpreter
   re-raise with the original traceback.
2. Only return `True` for *specific* exception types you have fully handled.
3. A `return self` or `return 1` by accident suppresses everything (`ctx_tool.py`
   rule CTX005 catches this).
4. Annotate as `-> None` when you never suppress (type checkers then know code
   after the `with` is reachable only on success), `-> bool` when you may.

```python
from types import TracebackType
from typing import Optional, Type


class SkipOnRateLimit:
    """Swallow RateLimitError only; count how many calls were skipped."""

    def __init__(self) -> None:
        self.skipped = 0

    def __enter__(self) -> "SkipOnRateLimit":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> bool:
        if exc_type is not None and issubclass(exc_type, RateLimitError):
            self.skipped += 1
            return True          # handled: suppress
        return False             # everything else propagates


skipper = SkipOnRateLimit()
for doc in docs:
    with skipper:
        summaries.append(llm.summarize(doc))
print(f"skipped {skipper.skipped} docs due to rate limits")
```

Use `issubclass(exc_type, X)`, not `exc_type is X`, so subclasses match.

### Inspecting and enriching the exception

`__exit__` may annotate the exception before letting it propagate:

```python
class StepContext:
    def __init__(self, step: str) -> None:
        self.step = step

    def __enter__(self) -> "StepContext":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc is not None:
            exc.add_note(f"while running pipeline step {self.step!r}")   # 3.11+
        # returning None: the (now annotated) exception propagates
```

On 3.9/3.10 use `raise PipelineError(self.step) from exc` instead of `add_note`
(that *replaces* the exception — see next section).

## Exceptions raised inside `__exit__`

If `__exit__` itself raises, the new exception replaces the original one; the
original is preserved as `__context__` ("During handling of the above
exception, another exception occurred").

```python
class Upload:
    def __exit__(self, exc_type, exc, tb) -> None:
        self.conn.close()              # if this raises, the body's error is now only __context__
```

Guidelines:

| Goal | Pattern |
|------|---------|
| Several cleanup steps must all run | Nest `try/finally`, or register them on an `ExitStack` (it runs every callback and chains exceptions). |
| A cleanup failure should not mask the real error | Catch and log inside `__exit__` when `exc is not None`. |
| Translate to a domain error | `raise ToolError("upload failed") from exc` inside `__exit__` (the original becomes `__cause__`). |

```python
import logging

log = logging.getLogger(__name__)


class Checkpointer:
    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self.flush()
        except Exception:
            if exc is None:
                raise                      # nothing else went wrong: surface the flush error
            log.exception("flush failed while handling %r", exc)   # keep the original error primary
        finally:
            self.file.close()
```

## Multiple items and parenthesized `with` (3.10)

```python
with open(src) as fin, open(dst, "w") as fout:       # any version
    fout.write(fin.read())

with (                                                # 3.10+ official (3.9 parser accepts it unofficially)
    open("prompts.jsonl") as prompts,
    open("completions.jsonl", "w") as out,
    torch.inference_mode(),
):
    ...
```

Semantics are exactly nested `with` statements: entered left-to-right, exited
right-to-left; if the second `__enter__` fails, the first is still exited.

| Need | Use |
|------|-----|
| Fixed, small number of managers | Comma list / parenthesized `with` |
| Variable number (list of files, N model shards) | `contextlib.ExitStack` |
| Conditional manager | `cm if cond else contextlib.nullcontext()` |

Pre-3.10, a backslash continuation works: `with open(a) as f, \` newline
`open(b) as g:`.

## Single-use, reusable and re-entrant managers

| Kind | Meaning | Examples |
|------|---------|----------|
| Single-use | Can be entered once; a second `with` fails or misbehaves | Files, `@contextmanager` objects (`RuntimeError: generator didn't yield` on reuse), `httpx.Client` after close |
| Reusable | Can be used in many sequential `with`s, not nested | `threading.Lock`, `ExitStack` instances, a timer class that resets in `__enter__` |
| Re-entrant | Can be nested inside itself | `threading.RLock`, `contextlib.suppress`, `redirect_stdout`, `nullcontext`; a `@contextmanager` *function* (each call makes a fresh object) |

```python
lock = threading.Lock()
with lock:
    with lock:        # deadlock: Lock is reusable but NOT re-entrant
        ...

rlock = threading.RLock()
with rlock:
    with rlock:       # fine
        ...
```

Making a class re-entrant: keep a depth counter and only set up/tear down at the
outermost level.

```python
import threading


class ModelLease:
    """Nested `with lease:` blocks share one GPU load; unload when the outermost exits."""

    def __init__(self, loader) -> None:
        self._loader = loader
        self._depth = 0
        self._lock = threading.RLock()
        self.model = None

    def __enter__(self):
        with self._lock:
            if self._depth == 0:
                self.model = self._loader()
            self._depth += 1
            return self.model

    def __exit__(self, exc_type, exc, tb) -> None:
        with self._lock:
            self._depth -= 1
            if self._depth == 0:
                self.model = None          # drop the reference so GPU memory can be freed
```

Guard against accidental reuse of single-use managers by raising early:

```python
class OneShot:
    def __init__(self) -> None:
        self._used = False

    def __enter__(self) -> "OneShot":
        if self._used:
            raise RuntimeError("OneShot can only be entered once; create a new instance")
        self._used = True
        return self

    def __exit__(self, *exc_info) -> None:
        ...
```

## Typing context managers

| Thing | Annotation |
|-------|------------|
| `@contextmanager` function yielding `T` | `-> Iterator[T]` (or `Generator[T, None, None]`) |
| `@asynccontextmanager` yielding `T` | `-> AsyncIterator[T]` |
| Parameter that accepts any manager | `contextlib.AbstractContextManager[T]` (subscriptable 3.9+) or `typing.ContextManager[T]` (deprecated alias) |
| Async parameter | `contextlib.AbstractAsyncContextManager[T]` |
| `__enter__` returning the instance | `-> "ClassName"`, or `-> Self` (3.11+, `typing_extensions` before) |
| `__exit__` | `(self, exc_type: Optional[Type[BaseException]], exc: Optional[BaseException], tb: Optional[TracebackType]) -> Optional[bool]` |

```python
from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager
from typing import Iterator


@contextmanager
def batch_writer(path: str, batch_size: int = 512) -> Iterator[BatchWriter]:
    writer = BatchWriter(path, batch_size)
    try:
        yield writer
    finally:
        writer.flush_and_close()


def run_eval(guard: AbstractContextManager[object]) -> None:
    with guard:
        ...
```

`typing.Protocol`-style structural checks: any class with `__enter__` and
`__exit__` satisfies `AbstractContextManager` in `isinstance` checks via its
`__subclasshook__`.

## Class vs generator: choosing

| Choose a class when | Choose `@contextmanager` when |
|---------------------|-------------------------------|
| The object is a resource with methods (`client.complete()`, `writer.add()`) | You wrap setup/teardown around a value that already exists |
| It must be reusable or re-entrant | Single use per call is fine (each call creates a new generator) |
| You need to suppress specific exceptions with clear logic | No suppression, or a simple `try/except ...: pass` |
| Performance matters in a hot loop (generator CMs cost a few extra µs) | Readability matters more |
| Users may also call `close()` without `with` | Cleanup only makes sense in a block |

A class can also expose a generator-based helper:

```python
class VectorStore:
    @contextmanager
    def transaction(self) -> Iterator["VectorStore"]:
        self._conn.execute("BEGIN")
        try:
            yield self
        except BaseException:
            self._conn.rollback()
            raise
        else:
            self._conn.commit()
```

## Version notes

| Version | Change |
|---------|--------|
| 3.7 | `contextlib.nullcontext`, `AbstractAsyncContextManager`, `asynccontextmanager`, `AsyncExitStack` |
| 3.9 | Generic `AbstractContextManager[T]`; the new PEG parser happens to accept parenthesized `with` |
| 3.10 | Parenthesized multi-item `with` officially supported; `contextlib.aclosing`; `nullcontext` usable with `async with`; `asynccontextmanager` objects usable as decorators |
| 3.11 | `contextlib.chdir`; `typing.Self`; `BaseException.add_note`; clearer `TypeError` when an object is not a context manager |
| 3.12 | `suppress` also suppresses matching exceptions inside `BaseExceptionGroup` |
| 3.13 | No protocol changes; free-threaded builds make lock-protected managers matter more |
