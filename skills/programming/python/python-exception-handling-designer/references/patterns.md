# Exception Handling Patterns

Correct, idiomatic patterns for designing, raising, catching, translating and reporting exceptions. Examples
come from LLM clients, RAG pipelines, training loops and FastAPI services, but every pattern is general Python.

## Contents

- [1. Designing a hierarchy](#1-designing-a-hierarchy)
- [2. Raising well](#2-raising-well)
- [3. Where to catch: the three layers](#3-where-to-catch-the-three-layers)
- [4. try / except / else / finally](#4-try--except--else--finally)
- [5. Chaining and context](#5-chaining-and-context)
- [6. Adding context: notes, attributes, wrappers](#6-adding-context-notes-attributes-wrappers)
- [7. Cleanup guarantees](#7-cleanup-guarantees)
- [8. Logging exceptions](#8-logging-exceptions)
- [9. Boundaries: FastAPI, CLI, workers](#9-boundaries-fastapi-cli-workers)
- [10. Validation vs assertions](#10-validation-vs-assertions)
- [11. Warnings](#11-warnings)
- [12. Result types as an alternative](#12-result-types-as-an-alternative)
- [13. Pickling and serialising errors](#13-pickling-and-serialising-errors)

## 1. Designing a hierarchy

Design classes around **decisions the caller makes**: retry? show the user? page on-call? fall back?

```python
from __future__ import annotations

from typing import Any, ClassVar, Dict, Optional


class RagkitError(Exception):
    """Base class for every ragkit error. Catch this at application boundaries."""

    retryable: ClassVar[bool] = False
    code: ClassVar[str] = "ragkit_error"

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.message = message
        self.context = context

    def __str__(self) -> str:
        extra = ", ".join(f"{k}={v!r}" for k, v in self.context.items() if v is not None)
        return f"{self.message} ({extra})" if extra else self.message


class ConfigurationError(RagkitError):
    code = "configuration"


class InputValidationError(RagkitError, ValueError):
    code = "invalid_input"


class ProviderError(RagkitError):
    code = "provider"

    def __init__(self, message: str, *, provider: str, model: Optional[str] = None, **context: Any) -> None:
        super().__init__(message, provider=provider, model=model, **context)
        self.provider = provider
        self.model = model


class RateLimitError(ProviderError):
    retryable = True
    code = "rate_limited"

    def __init__(self, message: str, *, retry_after: Optional[float] = None, **context: Any) -> None:
        super().__init__(message, retry_after=retry_after, **context)
        self.retry_after = retry_after


class ContextLengthError(ProviderError):
    code = "context_length_exceeded"

    def __init__(self, message: str, *, tokens: int, limit: int, **context: Any) -> None:
        super().__init__(message, tokens=tokens, limit=limit, **context)
        self.tokens = tokens
        self.limit = limit


HTTP_STATUS: Dict[type, int] = {RagkitError: 500, InputValidationError: 422, ProviderError: 502,
                                RateLimitError: 429, ContextLengthError: 413}
```

Design checklist:

| Question | Guidance |
|----------|----------|
| How many classes? | As few as there are distinct caller reactions; 5-20 for a typical service |
| Depth? | 2-3 levels; deeper trees are rarely caught at the middle levels |
| Base class? | Exactly one per package, deriving from `Exception` |
| Message vs data? | Human message in `args[0]`; machine data as attributes (never parse messages) |
| Retryability? | Class attribute `retryable`, overridable per instance if needed |
| Builtin mix-ins? | `(RagkitError, ValueError)` / `(RagkitError, LookupError)` / `(RagkitError, TimeoutError)` when generic callers expect the builtin |
| Naming? | `XxxError`; do not shadow builtins (`TimeoutError`) - use `ProviderTimeoutError` |
| Where defined? | `errors.py` (or `exceptions.py`) at the package root, re-exported in `__init__.py` |
| Public? | Yes; exceptions are part of the API. Document which functions raise which errors |

Generate a starting point: `python scripts/scaffold_exceptions.py --package ragkit --preset llm-app --http`.

## 2. Raising well

```python
def build_prompt(template: str, variables: dict) -> str:
    missing = sorted(set(PLACEHOLDER.findall(template)) - variables.keys())
    if missing:
        raise InputValidationError(f"prompt template is missing variables: {', '.join(missing)}",
                                   template_id=variables.get("template_id"))
    return template.format(**variables)
```

| Do | Don't |
|----|-------|
| Lower-case message, no trailing period, include the offending value with `!r` | `raise ValueError("Error!")` |
| Put identifiers in attributes/context | Embed secrets, full prompts or API keys in messages |
| Raise the most specific existing type | `raise Exception(...)` |
| Raise early, at the first invalid input | Return `None`/`-1`/`""` sentinels for errors |
| Raise a class or an instance (`raise ValueError(...)`) | `raise "string"` (TypeError since 2.6) |

Re-raise forms:

```python
except ProviderError:
    metrics.increment("provider_errors")
    raise                       # same exception, original traceback

except ProviderError as err:
    raise err                   # works, but adds this line to the traceback: prefer bare raise
```

## 3. Where to catch: the three layers

| Layer | Example | Handler job |
|-------|---------|-------------|
| **Edge** (wraps a dependency) | `OpenAIClient.chat`, `QdrantStore.search` | Translate SDK errors to domain errors with `from err`; add provider/model context |
| **Policy** (business logic) | `answer_question`, `ingest_document` | Retry transient errors, fall back (other model, keyword search), degrade gracefully |
| **Boundary** (entry point) | FastAPI handler, CLI `main`, Celery task, eval runner | Log once with traceback, convert to HTTP status / exit code / nack, never crash the server |

Everything between those layers lets exceptions propagate untouched. A function that cannot do one of these
jobs should not have a `try` at all.

```python
# edge
class QdrantStore:
    async def search(self, vector: list, top_k: int) -> list:
        try:
            return await self._client.search(self.collection, query_vector=vector, limit=top_k)
        except (httpx.TimeoutException, httpx.ConnectError) as err:
            raise VectorStoreError("qdrant unreachable", store="qdrant", collection=self.collection) from err


# policy
async def retrieve(query: str) -> list:
    vector = await embedder.embed_one(query)
    try:
        return await store.search(vector, top_k=8)
    except VectorStoreError:
        logger.warning("vector search unavailable; falling back to BM25", exc_info=True)
        return bm25.search(query, top_k=8)


# boundary: see section 9
```

## 4. try / except / else / finally

```python
def load_model_config(path: str) -> ModelConfig:
    try:
        fh = open(path, encoding="utf-8")
    except FileNotFoundError:
        raise ConfigurationError(f"model config not found: {path}") from None
    try:
        raw = json.load(fh)
    except json.JSONDecodeError as err:
        raise ConfigurationError(f"{path}:{err.lineno}:{err.colno}: {err.msg}") from err
    else:
        return ModelConfig.model_validate(raw)   # errors here are NOT caught by the JSON handler
    finally:
        fh.close()
```

| Clause | Runs when | Use for |
|--------|-----------|---------|
| `try` | always | only the statements that can raise the handled errors |
| `except E` | `E` raised in `try` | recover, translate, add context |
| `else` | `try` finished without exception | success-path code that must not be protected by the handlers |
| `finally` | always (exception, return, break) | release resources; never `return` here |

Ordering rule: handlers are tested top to bottom; put subclasses first. `except (A, B) as err:` catches either.
Since 3.14 (PEP 758) `except A, B:` without parentheses is allowed when there is no `as`.

Loop pattern (per-item isolation):

```python
results, failures = [], []
for doc in docs:
    try:
        chunks = chunker.split(doc.text)
    except ValueError as err:
        failures.append((doc.id, err))
        logger.warning("skipping doc %s: %s", doc.id, err)
        continue
    results.extend(chunks)
if failures and len(failures) == len(docs):
    raise IngestionError("every document failed to chunk") from failures[0][1]
```

## 5. Chaining and context

```python
try:
    payload = json.loads(text)
except json.JSONDecodeError as err:
    raise StructuredOutputError("model did not return JSON", raw_output=text[:500]) from err
```

| You want | Write |
|----------|-------|
| Translate, keep the cause visible | `raise New(...) from err` |
| Hide an irrelevant internal cause | `raise New(...) from None` |
| Attach a cause outside an `except` block | `raise New(...) from saved_err` |
| Re-raise unchanged | `raise` |
| Re-raise but add text | `err.add_note(...)` then `raise` (3.11+) |

Implicit context (no `from`) prints "During handling of the above exception, another exception occurred",
which reads like a bug in the handler; always choose explicitly.

## 6. Adding context: notes, attributes, wrappers

`add_note` (3.11+) keeps the original type, so callers' handlers still match:

```python
for i, batch in enumerate(batched(texts, 64)):
    try:
        vectors.extend(await embedder.embed(batch))
    except ProviderError as err:
        err.add_note(f"batch {i} ({len(batch)} texts, first id={batch[0].id})")
        raise
```

Backport for 3.9/3.10:

```python
def add_note(err: BaseException, note: str) -> None:
    if hasattr(err, "add_note"):
        err.add_note(note)
    else:
        err.__notes__ = [*getattr(err, "__notes__", []), note]  # shown by the 3.11+ traceback printer only
```

Context manager that annotates any exception passing through:

```python
from contextlib import contextmanager


@contextmanager
def error_context(**fields):
    try:
        yield
    except Exception as err:
        add_note(err, ", ".join(f"{k}={v!r}" for k, v in fields.items()))
        raise


with error_context(step="rerank", model=RERANKER, query_id=qid):
    ranked = reranker.rank(query, candidates)
```

## 7. Cleanup guarantees

Prefer context managers over `finally`; they cannot be forgotten and they compose:

```python
async with httpx.AsyncClient(timeout=30) as http, tracer.start_as_current_span("rag.answer") as span:
    ...
```

`contextlib.ExitStack` for a dynamic number of resources:

```python
from contextlib import ExitStack

with ExitStack() as stack:
    shards = [stack.enter_context(open(p, "rb")) for p in shard_paths]
    index = build_index(shards)   # every opened shard is closed, even if a later open() fails
```

Write a cleanup that does not mask the original error:

```python
def close_all(clients) -> None:
    errors = []
    for c in clients:
        try:
            c.close()
        except Exception as err:      # keep closing the rest
            errors.append(err)
    if errors:
        raise ExceptionGroup("failed to close clients", errors)  # 3.11+
```

`__exit__` returning a truthy value swallows the exception: return `None`/`False` unless suppression is the
explicit purpose (like `contextlib.suppress`).

Do not rely on `__del__` for cleanup; exceptions in `__del__` are printed and ignored, and it may never run.

## 8. Logging exceptions

```python
logger = logging.getLogger(__name__)

try:
    answer = await rag.answer(question)
except ProviderError:
    logger.exception("answer failed", extra={"request_id": rid, "model": settings.model})
    raise
```

| Call | Level | Traceback |
|------|-------|-----------|
| `logger.exception(msg)` | ERROR | yes (only valid inside `except`) |
| `logger.error(msg, exc_info=True)` | ERROR | yes |
| `logger.warning(msg, exc_info=err)` | WARNING | yes, any exception object |
| `logger.error(f"failed: {err}")` | ERROR | **no** - message only, often empty for SDK errors |
| `logger.debug(msg, stack_info=True)` | DEBUG | current stack (not an exception) |

Rules:
- Log **or** raise, not both, except at the boundary (which logs and does not re-raise) or when the log level
  adds something (warning in a fallback path).
- Use lazy `%s` formatting or `extra=`; with structured logging (structlog, JSON formatters) put fields in
  `extra` so they become searchable keys.
- Redact: never log full prompts with user PII, API keys or auth headers. Truncate model outputs.
- `logging.raiseExceptions = False` in production prevents logging errors from printing tracebacks.

## 9. Boundaries: FastAPI, CLI, workers

### FastAPI

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()


@app.exception_handler(RagkitError)
async def handle_ragkit_error(request: Request, exc: RagkitError) -> JSONResponse:
    status = next((HTTP_STATUS[c] for c in type(exc).__mro__ if c in HTTP_STATUS), 500)
    headers = {}
    if getattr(exc, "retry_after", None):
        headers["Retry-After"] = str(math.ceil(exc.retry_after))
    if status >= 500:
        logger.error("request failed", exc_info=exc, extra={"path": request.url.path})
        body = {"error": exc.code, "message": "upstream service error"}
    else:
        body = {"error": exc.code, "message": exc.message, **exc.context}
    return JSONResponse(status_code=status, content=body, headers=headers)


@app.exception_handler(Exception)
async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled error", exc_info=exc, extra={"path": request.url.path})
    return JSONResponse(status_code=500, content={"error": "internal_error"})
```

- Raise `HTTPException` only in the routing layer; keep it out of services so they stay framework-free.
- Pydantic request validation errors become 422 through `RequestValidationError`; customise with
  `@app.exception_handler(RequestValidationError)`.
- For streaming responses (`StreamingResponse`, SSE), headers are already sent when a mid-stream error occurs:
  emit an error event (`event: error`) and close; exception handlers cannot change the status code anymore.

### CLI

```python
def main(argv: Optional[list] = None) -> int:
    args = parse_args(argv)
    try:
        run(args)
    except RagkitError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### Queue worker / batch job

```python
async def consume(queue) -> None:
    async for msg in queue:
        try:
            await handle(msg)
        except Exception as err:              # boundary: one bad message must not stop the worker
            logger.exception("message failed", extra={"msg_id": msg.id, "attempt": msg.attempt})
            if is_retryable(err) and msg.attempt < 5:
                await msg.nack(requeue=True)
            else:
                await msg.dead_letter(reason=type(err).__name__)
        else:
            await msg.ack()
```

Note `except Exception` here is correct: it is a boundary, it logs with traceback, and `CancelledError`
(a `BaseException`) still propagates so the worker can shut down.

## 10. Validation vs assertions

| Tool | Use for | Survives `python -O`? |
|------|---------|-----------------------|
| `if ...: raise ValueError/TypeError` | public function arguments | yes |
| Pydantic models / `TypeAdapter` | request bodies, configs, model outputs | yes |
| `assert` | internal invariants that indicate a bug if false | **no** |
| `typing.assert_never` (3.11) | exhaustiveness in `match`/`if` chains | yes |

```python
from pydantic import BaseModel, Field, ValidationError


class GenerationParams(BaseModel):
    temperature: float = Field(0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(512, gt=0, le=8192)
    top_p: float = Field(1.0, gt=0.0, le=1.0)


try:
    params = GenerationParams.model_validate(user_payload)
except ValidationError as err:
    raise InputValidationError("invalid generation parameters", errors=err.errors()) from err
```

Assert invariants, not inputs:

```python
def merge_scores(dense: np.ndarray, sparse: np.ndarray) -> np.ndarray:
    if dense.shape != sparse.shape:
        raise ValueError(f"shape mismatch: dense {dense.shape} vs sparse {sparse.shape}")
    fused = 0.7 * dense + 0.3 * sparse
    assert fused.shape == dense.shape  # noqa: EXC009 - invariant: never false unless this code is wrong
    return fused
```

## 11. Warnings

```python
import warnings


def chat(prompt: str, *, model: str = "small", engine: Optional[str] = None) -> str:
    if engine is not None:
        warnings.warn("`engine` is deprecated, use `model`", DeprecationWarning, stacklevel=2)
        model = engine
    ...
```

| Need | Code |
|------|------|
| Warn once per call site (default filter) | `warnings.warn(msg, Category, stacklevel=2)` |
| Silence a known noisy warning locally | `with warnings.catch_warnings(): warnings.simplefilter("ignore", FutureWarning)` |
| Turn warnings into errors in CI | `python -W error` or pytest `filterwarnings = ["error"]` |
| Route warnings to logging | `logging.captureWarnings(True)` |
| Deprecation decorator (3.13) | `@warnings.deprecated("use embed_many")` |

`catch_warnings` mutates process-global filter state, so it is not thread-safe or asyncio-safe; 3.14 adds an
opt-in context-aware mode (`-X context_aware_warnings`, default on free-threaded builds). Avoid it in concurrent
code paths.

## 12. Result types as an alternative

Exceptions are the Python default. Use a result value when failure is an **expected, frequent outcome that the
caller must handle per item** - e.g. per-document results in a batch, per-tool results returned to a model.

```python
from dataclasses import dataclass
from typing import Generic, TypeVar, Union

T = TypeVar("T")


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T


@dataclass(frozen=True)
class Err:
    error: Exception


Result = Union[Ok[T], Err]


def embed_each(texts: list) -> list:
    out = []
    for text in texts:
        try:
            out.append(Ok(embedder.embed_one(text)))
        except ProviderError as err:
            out.append(Err(err))
    return out


for text, res in zip(texts, embed_each(texts)):
    if isinstance(res, Ok):
        index.add(text, res.value)
    else:
        logger.warning("embedding failed for %r: %s", text[:40], res.error)
```

With 3.10+ `match`:

```python
match res:
    case Ok(value=vec):
        index.add(text, vec)
    case Err(error=RateLimitError() as err):
        retry_queue.put((text, err.retry_after))
    case Err(error=err):
        dead_letter.append((text, err))
```

| Use exceptions | Use results |
|----------------|-------------|
| failure is rare / exceptional | failure is a normal per-item outcome |
| caller usually cannot handle it locally | caller must decide per item |
| one operation | batch with partial success |
| deep call stacks | values crossing process/LLM boundaries (tool results) |

Keep the original exception inside `Err` so nothing is lost; convert back with `raise res.error`.

## 13. Pickling and serialising errors

Exceptions cross process boundaries in `multiprocessing`, `ProcessPoolExecutor`, Celery and Ray. The default
pickling calls `cls(*self.args)`, which breaks when `__init__` takes required keyword-only arguments:

```python
class ContextLengthError(ProviderError):
    def __init__(self, message: str, *, tokens: int, limit: int, **context):
        super().__init__(message, tokens=tokens, limit=limit, **context)
        self.tokens, self.limit = tokens, limit

    def __reduce__(self):
        return (_rebuild, (type(self), self.message, self.context))


def _rebuild(cls, message, context):
    return cls(message, **context)
```

Verify in a test: `pickle.loads(pickle.dumps(err))` must round-trip type, message and attributes.

For JSON (logs, API bodies, task results) expose `to_dict()` with a stable `code`, the message, `retryable` and
JSON-safe context; never ship tracebacks to clients.
