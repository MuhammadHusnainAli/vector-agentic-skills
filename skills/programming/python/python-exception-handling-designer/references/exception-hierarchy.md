# Builtin Exception Hierarchy

The complete builtin tree (CPython 3.13/3.14), when each exception is raised, whether you should raise it
yourself, and the stdlib/AI-stack exceptions you meet most often. Version tags mark additions and changes.

## Contents

- [The tree](#the-tree)
- [BaseException branch: never swallow](#baseexception-branch-never-swallow)
- [Exception subclasses: when each is raised](#exception-subclasses-when-each-is-raised)
- [OSError and errno](#oserror-and-errno)
- [Warnings](#warnings)
- [Which builtin should I raise?](#which-builtin-should-i-raise)
- [Common stdlib and third-party exceptions](#common-stdlib-and-third-party-exceptions)
- [Exception object anatomy](#exception-object-anatomy)
- [Version changes that matter](#version-changes-that-matter)

## The tree

```
BaseException
 ├── BaseExceptionGroup                       (3.11)
 ├── GeneratorExit
 ├── KeyboardInterrupt
 ├── SystemExit
 └── Exception
      ├── ArithmeticError
      │    ├── FloatingPointError
      │    ├── OverflowError
      │    └── ZeroDivisionError
      ├── AssertionError
      ├── AttributeError
      ├── BufferError
      ├── EOFError
      ├── ExceptionGroup [BaseExceptionGroup]  (3.11)
      ├── ImportError
      │    └── ModuleNotFoundError
      ├── LookupError
      │    ├── IndexError
      │    └── KeyError
      ├── MemoryError
      ├── NameError
      │    └── UnboundLocalError
      ├── OSError
      │    ├── BlockingIOError
      │    ├── ChildProcessError
      │    ├── ConnectionError
      │    │    ├── BrokenPipeError
      │    │    ├── ConnectionAbortedError
      │    │    ├── ConnectionRefusedError
      │    │    └── ConnectionResetError
      │    ├── FileExistsError
      │    ├── FileNotFoundError
      │    ├── InterruptedError
      │    ├── IsADirectoryError
      │    ├── NotADirectoryError
      │    ├── PermissionError
      │    ├── ProcessLookupError
      │    └── TimeoutError
      ├── ReferenceError
      ├── RuntimeError
      │    ├── NotImplementedError
      │    ├── PythonFinalizationError        (3.13)
      │    └── RecursionError
      ├── StopAsyncIteration
      ├── StopIteration
      ├── SyntaxError
      │    └── IndentationError
      │         └── TabError
      ├── SystemError
      ├── TypeError
      ├── ValueError
      │    └── UnicodeError
      │         ├── UnicodeDecodeError
      │         ├── UnicodeEncodeError
      │         └── UnicodeTranslateError
      └── Warning
           ├── BytesWarning
           ├── DeprecationWarning
           ├── EncodingWarning                (3.10)
           ├── FutureWarning
           ├── ImportWarning
           ├── PendingDeprecationWarning
           ├── ResourceWarning
           ├── RuntimeWarning
           ├── SyntaxWarning
           ├── UnicodeWarning
           └── UserWarning
```

Not builtins but critical: `asyncio.CancelledError` and `concurrent.futures.CancelledError` derive from
`BaseException` since 3.8 (they used to be `Exception`), so `except Exception` no longer catches cancellation.

Aliases: `IOError` and `EnvironmentError` are `OSError`; `socket.error` is `OSError`; `socket.timeout` is
`TimeoutError` (3.10); `asyncio.TimeoutError` and `concurrent.futures.TimeoutError` are `TimeoutError` (3.11).

Print the tree for your interpreter:

```python
def tree(cls: type, indent: int = 0) -> None:
    print(" " * indent + cls.__name__)
    for sub in sorted(cls.__subclasses__(), key=lambda c: c.__name__):
        if sub.__module__ == "builtins":
            tree(sub, indent + 2)


tree(BaseException)
```

## BaseException branch: never swallow

| Exception | Raised by | Correct handling |
|-----------|-----------|------------------|
| `KeyboardInterrupt` | SIGINT (Ctrl+C) in the main thread | Let it propagate; a CLI may convert it to exit code 130 at the very top |
| `SystemExit` | `sys.exit()`, `argparse` errors, `raise SystemExit(code)` | Let it propagate; test it with `pytest.raises(SystemExit)` |
| `GeneratorExit` | `generator.close()`, garbage collection of a suspended generator | Clean up and return/raise; never `yield` after it (RuntimeError) |
| `asyncio.CancelledError` | `task.cancel()`, timeouts, TaskGroup siblings failing, server shutdown | Clean up, then `raise` |
| `BaseExceptionGroup` | TaskGroup/`except*` when a member is a BaseException | Handle with `except*` per member type |

Catch `BaseException` only to run cleanup and re-raise:

```python
def run_training(model, loader, ckpt_path: str) -> None:
    try:
        train(model, loader)
    except BaseException:
        save_checkpoint(model, ckpt_path)  # also on Ctrl+C: resume later
        raise
```

## Exception subclasses: when each is raised

| Exception | Typical trigger | Raise it yourself? |
|-----------|-----------------|--------------------|
| `ArithmeticError` | base of numeric errors | catch only |
| `OverflowError` | `math.exp(1000)`, float -> int of inf | rarely |
| `ZeroDivisionError` | `x / 0`, `x % 0` | no; validate the divisor instead |
| `FloatingPointError` | numpy with `np.seterr(all="raise")` | no |
| `AssertionError` | failing `assert` | only in tests and invariant checks |
| `AttributeError` | missing attribute; also from `__getattr__` | yes, from `__getattr__` |
| `BufferError` | resizing a buffer with exported views | no |
| `EOFError` | `input()` at end of stdin, `asyncio.IncompleteReadError` | rarely |
| `ImportError` / `ModuleNotFoundError` | missing optional dependency | catch to give an install hint |
| `LookupError` | base of Index/KeyError | yes, for custom containers (catch the base) |
| `IndexError` | sequence index out of range | yes, in `__getitem__` |
| `KeyError` | missing mapping key | yes, in mapping types; message is `repr(key)` |
| `MemoryError` | host allocation failure | no; recovery is rarely possible |
| `NameError` / `UnboundLocalError` | undefined variable | never handle; a bug |
| `NotImplementedError` | abstract method placeholders | yes (do not confuse with the `NotImplemented` constant) |
| `RecursionError` | recursion limit exceeded | no |
| `RuntimeError` | generic "cannot happen now" state; also `torch.cuda.OutOfMemoryError` base | prefer a specific subclass |
| `StopIteration` | `next()` on an exhausted iterator | only inside `__next__`; inside a generator it becomes `RuntimeError` (PEP 479) |
| `StopAsyncIteration` | `__anext__` exhaustion | only inside `__anext__` |
| `SyntaxError` | `compile()`, `ast.parse()`, `eval()` | when you parse a DSL; set `filename`/`lineno` |
| `SystemError` | interpreter bug | never |
| `TypeError` | wrong type, wrong arg count, unhashable | yes, for wrong argument types |
| `ValueError` | right type, bad value (`int("x")`, `json.loads("")`) | yes, the default for bad input |
| `UnicodeDecodeError` | `bytes.decode` failure, reading a file with the wrong encoding | catch; decode with `errors="replace"` when lossy is OK |

### KeyError quirk

`str(KeyError("model"))` is `"'model'"` (the repr). Read `err.args[0]` for the key:

```python
try:
    price = PRICES[model_name]
except KeyError:
    raise ConfigurationError(f"no price configured for model {model_name!r}") from None
```

## OSError and errno

`OSError(errno, strerror[, filename])` is auto-mapped to a subclass by `errno`:

| errno | Subclass |
|-------|----------|
| `EAGAIN`, `EWOULDBLOCK`, `EINPROGRESS` | `BlockingIOError` |
| `ECHILD` | `ChildProcessError` |
| `EPIPE`, `ESHUTDOWN` | `BrokenPipeError` |
| `ECONNABORTED` | `ConnectionAbortedError` |
| `ECONNREFUSED` | `ConnectionRefusedError` |
| `ECONNRESET` | `ConnectionResetError` |
| `EEXIST` | `FileExistsError` |
| `ENOENT` | `FileNotFoundError` |
| `EINTR` | `InterruptedError` (auto-retried by the stdlib since 3.5, PEP 475) |
| `EISDIR` / `ENOTDIR` | `IsADirectoryError` / `NotADirectoryError` |
| `EACCES`, `EPERM` | `PermissionError` |
| `ESRCH` | `ProcessLookupError` |
| `ETIMEDOUT` | `TimeoutError` |

```python
import errno
import os

try:
    os.makedirs(cache_dir)
except FileExistsError:
    pass  # fine: the cache already exists (better: os.makedirs(cache_dir, exist_ok=True))
except OSError as err:
    if err.errno == errno.ENOSPC:
        raise ResourceExhaustedError("disk full while writing embedding cache", device=cache_dir) from err
    raise
```

`OSError` attributes: `errno`, `strerror`, `filename`, `filename2`, `winerror` (Windows).

## Warnings

| Category | Shown by default? | Use for |
|----------|-------------------|---------|
| `UserWarning` | yes | default for `warnings.warn` |
| `DeprecationWarning` | only in `__main__` and tests | API being removed (audience: developers) |
| `PendingDeprecationWarning` | no | will be deprecated later |
| `FutureWarning` | yes | behaviour change aimed at end users (pandas style) |
| `RuntimeWarning` | yes | dubious runtime values (numpy overflow) |
| `ResourceWarning` | no (enable with `-X dev`) | unclosed files/sockets/clients |
| `SyntaxWarning` | yes | dubious syntax (`is` with literal, `return` in `finally` in 3.14) |
| `EncodingWarning` | opt-in `-X warn_default_encoding` (3.10) | `open()` without `encoding=` |

```python
import warnings


def retrieve(query: str, top_k: int = 5):
    if top_k > 100:
        warnings.warn(f"top_k={top_k} is slow and rarely improves answers", RuntimeWarning, stacklevel=2)
    ...
```

Python 3.13 adds `warnings.deprecated` (also in `typing_extensions`) as a decorator that warns at call time and
is understood by type checkers.

## Which builtin should I raise?

| Situation | Raise |
|-----------|-------|
| Argument has the wrong type | `TypeError` |
| Argument has the right type but invalid value (`temperature=5`) | `ValueError` |
| Key/ID not found in your registry | `KeyError` / `LookupError` (or a domain `NotFoundError`) |
| Object in wrong state (`client.chat()` before `connect()`) | `RuntimeError` or a domain error |
| Subclass must implement | `NotImplementedError` |
| Operation timed out | `TimeoutError` (or a domain subclass) |
| Feature not available on this platform/config | domain `ConfigurationError` |
| Anything a caller should handle differently | a domain exception |

Never raise `Exception`, `BaseException`, `SystemError`, `NameError`, or `AssertionError` for input validation.

A domain error may also inherit a builtin so callers who only know builtins still catch it:

```python
class InputValidationError(RagkitError, ValueError):
    """Bad caller input; also a ValueError for generic callers."""
```

## Common stdlib and third-party exceptions

| Exception | Base | Notes |
|-----------|------|-------|
| `json.JSONDecodeError` | `ValueError` | `.msg`, `.doc`, `.pos`, `.lineno`, `.colno` - feed back to the model in repair loops |
| `subprocess.CalledProcessError` | `SubprocessError` | `.returncode`, `.stderr` (with `check=True`) |
| `subprocess.TimeoutExpired` | `SubprocessError` | not a `TimeoutError` |
| `asyncio.CancelledError` | `BaseException` (3.8+) | always re-raise |
| `asyncio.TimeoutError` | `TimeoutError` (3.11+), `Exception` before | catch `TimeoutError` on 3.11+ |
| `asyncio.InvalidStateError` | `Exception` | result of an unfinished future |
| `asyncio.IncompleteReadError` | `EOFError` | `.partial` bytes received |
| `concurrent.futures.BrokenExecutor` | `RuntimeError` | worker process died (OOM-killed) |
| `pickle.PicklingError` | `PickleError` | custom exceptions with kw-only `__init__` without `__reduce__` |
| `ssl.SSLError` | `OSError` | TLS failures to model gateways |
| `httpx.TimeoutException` | `httpx.TransportError` -> `RequestError` -> `HTTPError` | Connect/Read/Write/PoolTimeout |
| `httpx.HTTPStatusError` | `HTTPError` | from `response.raise_for_status()`; `.response.status_code` |
| `requests.RequestException` | `OSError` (IOError) | `ConnectionError`, `Timeout`, `HTTPError` subclasses |
| `pydantic.ValidationError` | `ValueError` (v2) | `.errors()` list, `.json()` |
| `openai.APIError` | `OpenAIError` | subclasses `APIConnectionError`, `APITimeoutError(APIConnectionError)`, `APIStatusError` -> `RateLimitError`, `BadRequestError`, `AuthenticationError`, `InternalServerError`... |
| `anthropic.APIStatusError` | `APIError` | `RateLimitError` (429), `InternalServerError` (5xx; 529 overloaded has its own subclass in newer SDK versions), `.status_code`, `.response.headers` |
| `torch.cuda.OutOfMemoryError` | `RuntimeError` | torch >= 1.13; older versions raise plain `RuntimeError("CUDA out of memory")` |

Check an SDK's tree at runtime instead of guessing:

```python
import inspect
import openai

for name, cls in inspect.getmembers(openai, inspect.isclass):
    if issubclass(cls, BaseException):
        print(f"{name:35} {' -> '.join(c.__name__ for c in cls.__mro__[1:-2])}")
```

## Exception object anatomy

| Attribute | Meaning |
|-----------|---------|
| `args` | tuple passed to the constructor; `str(e)` uses it |
| `__traceback__` | traceback object (frames); keep exceptions short-lived to avoid reference cycles |
| `__cause__` | explicit cause from `raise ... from cause` |
| `__context__` | implicit context: the exception being handled when this one was raised |
| `__suppress_context__` | set by `from` (including `from None`): hides `__context__` in the traceback |
| `__notes__` | list of strings added by `add_note()` (3.11) |
| `with_traceback(tb)` | returns self with a replaced traceback |

```python
import traceback


def describe(err: BaseException) -> dict:
    """Serialise an exception chain for an error-tracking payload."""
    chain = []
    cur = err
    while cur is not None:
        chain.append({"type": type(cur).__qualname__, "message": str(cur),
                      "notes": list(getattr(cur, "__notes__", []))})
        cur = cur.__cause__ or (None if cur.__suppress_context__ else cur.__context__)
    return {"chain": chain, "traceback": "".join(traceback.format_exception(err))}
```

`traceback.format_exception(err)` with a single argument works on 3.10+; on 3.9 pass
`(type(err), err, err.__traceback__)`.

The variable bound by `except E as err:` is deleted at the end of the handler (to break the frame cycle). Copy
it to another name if you need it later:

```python
last_error = None
for attempt in range(3):
    try:
        return call()
    except TimeoutError as err:
        last_error = err
raise ProviderTimeoutError("3 attempts timed out") from last_error
```

## Version changes that matter

| Version | Change |
|---------|--------|
| 3.8 | `asyncio.CancelledError` becomes a `BaseException` |
| 3.10 | `socket.timeout` is an alias of `TimeoutError`; `EncodingWarning`; better error messages ("Did you mean ...") |
| 3.11 | `ExceptionGroup`, `BaseExceptionGroup`, `except*`; `add_note`/`__notes__`; `asyncio.TaskGroup`, `asyncio.timeout`; `asyncio.TimeoutError` is `TimeoutError`; fine-grained traceback locations; zero-cost `try` |
| 3.12 | `sys.last_exc`; `sys.exception()` (3.11) preferred over `sys.exc_info()` |
| 3.13 | `PythonFinalizationError`; `warnings.deprecated`; colourised tracebacks |
| 3.14 | `return`/`break`/`continue` in `finally` emit `SyntaxWarning` (PEP 765); `except A, B:` without parentheses allowed when no `as` (PEP 758) |
