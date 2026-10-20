# Exception Handling Anti-Patterns

Every rule reported by `scripts/audit_exceptions.py`, with why it hurts and a before/after fix, followed by
smells the AST audit cannot detect. Rule ids match the script output so findings can be linked here.

## Contents

| Id | Name | Severity |
|----|------|----------|
| [EXC001](#exc001-bare-except) | bare-except | high |
| [EXC002](#exc002-base-exception-swallow) | base-exception-swallow | high |
| [EXC003](#exc003-broad-except-swallow) | broad-except-swallow | high |
| [EXC004](#exc004-raise-without-from) | raise-without-from | medium |
| [EXC005](#exc005-generic-raise) | generic-raise | medium |
| [EXC006](#exc006-unreachable-handler) | unreachable-handler | high |
| [EXC007](#exc007-finally-control-flow) | finally-control-flow | high |
| [EXC008](#exc008-cancellation-swallowed) | cancellation-swallowed | high |
| [EXC009](#exc009-assert-validation) | assert-validation | medium |
| [EXC010](#exc010-log-error-not-exception) | log-error-not-exception | medium |
| [EXC011](#exc011-try-too-large) | try-too-large | low |
| [EXC012](#exc012-useless-reraise) | useless-reraise | low |
| [EXC013](#exc013-stringified-exception) | stringified-exception | medium |
| [EXC014](#exc014-redundant-except-type) | redundant-except-type | low |

Suppress a deliberate case on its line: `except Exception:  # noqa: EXC003 - best-effort telemetry`.

## EXC001 bare-except

`except:` catches `BaseException`: Ctrl+C, `sys.exit()`, `asyncio.CancelledError`, `GeneratorExit`.

Before:
```python
def load_prompt(path):
    try:
        return Path(path).read_text()
    except:
        return DEFAULT_PROMPT
```

After:
```python
def load_prompt(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("prompt %s not found; using default", path)
        return DEFAULT_PROMPT
```

If the intent is cleanup-then-reraise, write `except BaseException: ...; raise` or use `finally`.

## EXC002 base-exception-swallow

Before:
```python
def run_eval(suite):
    try:
        return suite.run()
    except BaseException as err:
        return {"status": "failed", "error": str(err)}   # Ctrl+C now reports "failed" and keeps going
```

After:
```python
def run_eval(suite):
    try:
        return suite.run()
    except Exception as err:
        logger.exception("eval suite %s crashed", suite.name)
        return {"status": "failed", "error": type(err).__name__}
```

## EXC003 broad-except-swallow

`except Exception: pass` (or `continue`, `return None`, or a silent fallback that never logs or uses the
error) turns bugs into wrong answers. Also flagged: `contextlib.suppress(Exception)`.

Before:
```python
def rerank(query, docs):
    try:
        return cross_encoder.rank(query, docs)
    except Exception:
        return docs
```

After (narrow + observable):
```python
def rerank(query: str, docs: list) -> list:
    try:
        return cross_encoder.rank(query, docs)
    except (ProviderError, TimeoutError):
        logger.warning("reranker unavailable; keeping vector order", exc_info=True)
        metrics.increment("rerank.fallback")
        return docs
```

A broad handler is acceptable only at a boundary (request, job, message, plugin call) and must log with
traceback.

## EXC004 raise-without-from

Before:
```python
try:
    resp = await http.post(url, json=payload)
    resp.raise_for_status()
except httpx.HTTPStatusError as err:
    raise ProviderError("embedding request failed")
```
Traceback: *"During handling of the above exception, another exception occurred"* - looks like the handler is
broken.

After:
```python
except httpx.HTTPStatusError as err:
    raise ProviderError(f"embedding request failed with {err.response.status_code}",
                        provider="tei") from err
```

Use `from None` only when the cause is noise (e.g. the `KeyError` from a lookup dict you are translating).

## EXC005 generic-raise

Before:
```python
if len(tokens) > limit:
    raise Exception("too long")
```

After:
```python
if len(tokens) > limit:
    raise ContextLengthError(f"prompt has {len(tokens)} tokens, limit {limit}",
                             provider=provider, tokens=len(tokens), limit=limit)
```

Callers can no longer distinguish your error from `KeyError` without catching everything; a specific class
costs two lines.

## EXC006 unreachable-handler

Handlers match top-down; a subclass after its base is dead code.

Before:
```python
try:
    return await client.chat(messages)
except openai.APIError:
    raise ProviderError("openai failed") from None
except openai.RateLimitError as err:          # never runs: RateLimitError is an APIError
    raise RateLimitError("429") from err
```

After:
```python
try:
    return await client.chat(messages)
except openai.RateLimitError as err:
    raise RateLimitError("rate limited", provider="openai") from err
except openai.APIError as err:
    raise ProviderError("openai failed", provider="openai") from err
```

The script knows the builtin tree, common stdlib/AI-stack exceptions (`json.JSONDecodeError`,
`torch.cuda.OutOfMemoryError`) and classes defined in the same file. Common traps:

| Wrong order | Why |
|-------------|-----|
| `except OSError` before `except FileNotFoundError` / `TimeoutError` / `ConnectionError` | all are `OSError` |
| `except ValueError` before `except json.JSONDecodeError` / `UnicodeDecodeError` | both are `ValueError` |
| `except RuntimeError` before `except torch.cuda.OutOfMemoryError` | OOM is a `RuntimeError` |
| `except LookupError` before `except KeyError` | `KeyError` is a `LookupError` |
| `except Exception` before anything | catches everything except the BaseException branch |

## EXC007 finally-control-flow

`return`, `break` or `continue` in `finally` silently discards the exception being propagated. Python 3.14
emits a `SyntaxWarning` (PEP 765).

Before:
```python
def save_checkpoint(state, path):
    try:
        torch.save(state, path)
    finally:
        return path      # disk-full error disappears; caller thinks the checkpoint exists
```

After:
```python
def save_checkpoint(state: dict, path: str) -> str:
    tmp = path + ".tmp"
    try:
        torch.save(state, tmp)
        os.replace(tmp, path)     # atomic
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return path
```

## EXC008 cancellation-swallowed

`asyncio.CancelledError`, `KeyboardInterrupt`, `SystemExit` and `GeneratorExit` caught without re-raise.
Swallowing `CancelledError` makes `TaskGroup`, `asyncio.timeout()` and server shutdown hang or misbehave.

Before:
```python
async def stream(prompt):
    try:
        async for tok in llm.stream(prompt):
            yield tok
    except asyncio.CancelledError:
        logger.info("client disconnected")
```

After:
```python
async def stream(prompt: str):
    try:
        async for tok in llm.stream(prompt):
            yield tok
    except asyncio.CancelledError:
        logger.info("client disconnected")
        raise
    finally:
        await llm.aclose()
```

Not flagged: a CLI handler that converts `KeyboardInterrupt`/`SystemExit` into a return code, or code that
records the exception object (sandbox runners).

## EXC009 assert-validation

Asserts are stripped by `python -O` / `PYTHONOPTIMIZE`, and `AssertionError` tells the caller nothing.

Before:
```python
def chunk(text: str, size: int, overlap: int) -> list:
    assert size > overlap
```

After:
```python
def chunk(text: str, size: int, overlap: int) -> list:
    if overlap >= size:
        raise ValueError(f"overlap ({overlap}) must be smaller than size ({size})")
```

The script flags asserts that reference a function parameter, outside `test_*.py`, `*_test.py`, `conftest.py`.
A genuine post-condition that happens to mention an argument can be kept with `# noqa: EXC009`.

## EXC010 log-error-not-exception

Before:
```python
except VectorStoreError as e:
    logger.error(e)
    logger.error(f"upsert failed: {e}")
```
Only `str(e)` is logged - no type, no traceback, often an empty string for SDK errors.

After:
```python
except VectorStoreError:
    logger.exception("upsert failed", extra={"collection": coll, "batch": i})
```
or `logger.error("upsert failed", exc_info=True)`.

## EXC011 try-too-large

A big `try` makes the handler guess which statement failed and can catch errors from code you never meant to
protect (a `KeyError` from your own dict lookup handled as "missing config").

Before:
```python
try:
    cfg = load_config()
    client = make_client(cfg)
    docs = load_docs(cfg["corpus"])
    chunks = [c for d in docs for c in chunker.split(d)]
    vectors = embed(chunks)
    store.upsert(vectors)
except KeyError:
    raise ConfigurationError("missing key")
```

After:
```python
cfg = load_config()
try:
    corpus = cfg["corpus"]
except KeyError:
    raise ConfigurationError("config has no 'corpus' entry") from None
client = make_client(cfg)
chunks = [c for d in load_docs(corpus) for c in chunker.split(d)]
store.upsert(embed(chunks))
```

Tune the threshold with `--max-try-body N` (default 10, counted recursively).

## EXC012 useless-reraise

`except X: raise` as the last handler is a no-op. It is **not** a no-op when it precedes a broader handler
(that idiom excludes `X` from the broad handler) - the script does not flag that case.

```python
try:
    return tokenizer.encode(text)
except ValueError:
    raise                                  # delete; or add context:

except ValueError as err:
    err.add_note(f"text starts with {text[:30]!r}")
    raise
```

## EXC013 stringified-exception

Before:
```python
except json.JSONDecodeError as e:
    raise ValueError("bad tool arguments: " + str(e))
```

After:
```python
except json.JSONDecodeError as err:
    raise ToolArgumentsError("tool arguments are not valid JSON", tool_name=name) from err
```

The original type, position (`err.pos`, `err.lineno`) and traceback stay available through `__cause__`.

## EXC014 redundant-except-type

`except (json.JSONDecodeError, ValueError)` - the first member is already a `ValueError`. Harmless at
runtime, but it signals a misunderstanding of the hierarchy; keep only the base or split into two handlers if
they need different treatment.

## Smells the audit cannot detect

| Smell | Why it hurts | Fix |
|-------|--------------|-----|
| Returning `None`/`-1`/`{}` for errors | callers forget to check; failure surfaces far away | raise, or return an explicit result type |
| Log-and-raise at every layer | the same traceback 4 times in the logs | add context, log once at the boundary |
| Catch-and-retry everything | retries 400s and bugs, burns tokens and quota | retry only `is_retryable(err)` |
| Retry without jitter | synchronised thundering herd after a 429 storm | full jitter: `uniform(0, base * 2 ** n)` |
| Retry without budget | requests hang for minutes | cap attempts and total deadline |
| Retrying non-idempotent calls | duplicate charges/messages/writes | idempotency keys or no retry after send |
| Exceptions for control flow in hot loops | slow when the exceptional path is common | LBYL or `dict.get` |
| Parsing exception messages (`"429" in str(e)`) | breaks on SDK upgrades/locales | catch types, read attributes (`err.status_code`) |
| Leaking internals to clients | stack traces, SQL, prompts in 500 bodies | generic 5xx body, details in logs |
| `except Exception as e: raise MyError(e)` | `str(e)` as message, no `from` | `raise MyError("...") from e` |
| Holding exceptions in long-lived lists | traceback keeps frames (tensors, buffers) alive | store `repr(err)` / summary, or `err.__traceback__ = None` |
| `sys.exit()` inside library code | kills the host app/notebook | raise a domain error; exit only in `main()` |
| `os._exit()` on error | skips `finally`, flushing and atexit | `sys.exit` from `main()` |
| Custom exception without calling `super().__init__` | empty `args`, broken `str()` and pickling | always call `super().__init__(message)` |
| Mutable default `errors=[]` in exception `__init__` | shared across instances | `errors: Optional[list] = None` |
| Catching `ImportError` broadly at module top | hides real errors inside the optional module | catch `ModuleNotFoundError` and check `err.name` |
| `except Exception` around `await` without timeout | handler never runs; the call hangs | `asyncio.timeout()` / client timeouts |
| Swallowing errors in `__del__` / atexit / signal handlers | silent data loss | explicit `close()`/context managers |
| Raising in `__exit__` while an exception is active | masks the original | log cleanup failures or chain them |

### Optional dependency import

```python
try:
    import tiktoken
except ModuleNotFoundError as err:
    if err.name != "tiktoken":
        raise                       # a dependency OF tiktoken is missing: a real error
    tiktoken = None


def count_tokens(text: str, encoding: str = "cl100k_base") -> int:
    if tiktoken is None:
        raise ConfigurationError("token counting needs `pip install tiktoken`")
    return len(tiktoken.get_encoding(encoding).encode(text))
```

### Exceptions keeping GPU memory alive

```python
failures = []
for batch in loader:
    try:
        loss = step(model, batch)
    except torch.cuda.OutOfMemoryError as err:
        failures.append(repr(err))     # not `err`: its traceback references frames holding CUDA tensors
        del batch
        torch.cuda.empty_cache()
```
