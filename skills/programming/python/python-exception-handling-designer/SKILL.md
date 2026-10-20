---
name: python-exception-handling-designer
description: "Design and review Python exception handling: custom exception hierarchies with retryable flags, what to catch where, EAFP vs LBYL, chaining with raise ... from, else/finally, logger.exception, add_note, ExceptionGroup and except* with asyncio.TaskGroup, warnings, asserts vs validation, FastAPI error translation, retries with backoff and jitter, timeouts, cancellation, pytest.raises, plus LLM-app failures: 429 rate limits with retry-after, 5xx overloaded, context-length exceeded, content filters, broken streams, malformed JSON repair loops, tool-call errors fed back to the model, partial embedding batch failures, CUDA OOM batch halving, vector DB outages, circuit breakers and model fallbacks. Use when the user writes or reviews try/except code, designs an errors.py, asks how to retry or handle LLM/API errors, sees swallowed or lost tracebacks, maps exceptions to HTTP status codes, or tests exceptions in .py files."
metadata:
  category: programming
  subcategory: python
  version: "1.0.0"
---

# Python Exception Handling Designer

Design exception handling that makes failures loud, specific and recoverable: a small domain hierarchy with a
`retryable` flag, narrow handlers placed only where something can actually be done, chained causes, one
boundary that turns exceptions into logs and HTTP responses, and retry/fallback logic that distinguishes a
transient 429 from a permanent 400. Every review produces concrete before/after code, and the audit script
catches the mechanical mistakes (bare except, swallowed errors, lost causes, swallowed cancellation).

## Trigger Conditions

Activate this skill when the user:
- Writes, reviews or refactors `try`/`except`/`finally` code, or asks "is this error handling OK?"
- Designs an `errors.py` / exception hierarchy for a library, SDK wrapper, RAG pipeline or FastAPI service
- Asks how to retry LLM/embedding/vector-DB calls, handle 429/5xx/timeouts, or add fallbacks between models
- Sees lost tracebacks, "During handling of the above exception, another exception occurred", silent failures,
  tasks that will not cancel, or `Ctrl+C` that does nothing
- Uses `asyncio.gather`/`TaskGroup` and needs to handle several failures (`ExceptionGroup`, `except*`)
- Parses model output (JSON, tool arguments) and needs a validate-and-repair loop
- Needs to map exceptions to HTTP status codes or test that code raises the right error

## Workflow

```
1. MAP        -> List failure sources: I/O, provider SDK, parsing, validation, cancellation, bugs
2. CLASSIFY   -> For each: expected or bug? transient (retry) or permanent? caller-fixable (4xx)?
3. HIERARCHY  -> One base error per package + subclasses by how callers react, retryable flag
                 (scaffold with scripts/scaffold_exceptions.py)
4. PLACE      -> Translate at the dependency edge (raise Domain(...) from err),
                 recover where you have a fallback, log+respond once at the boundary
5. HARDEN     -> Narrow handlers, else/finally, re-raise CancelledError, timeouts, bounded retries
6. AUDIT      -> python scripts/audit_exceptions.py <path> --strict
7. TEST       -> pytest.raises(match=...), ExceptionGroup checks, retry/fallback paths with fakes
```

## Core Rules

1. **Catch what you can handle, where you can handle it.** A handler must retry, fall back, translate, add
   context, or clean up. Anything else lets the exception propagate.
2. **Never swallow silently.** `except Exception: pass` hides `KeyError`/`TypeError` bugs. If a fallback is
   intentional, log with `logger.exception` (or `warning(..., exc_info=True)`) and make the fallback explicit.
3. **Bare `except:` and `except BaseException` must re-raise.** They catch `KeyboardInterrupt`, `SystemExit`
   and `asyncio.CancelledError` (a `BaseException` since 3.8).
4. **Chain on translation.** `raise ProviderError(...) from err` keeps the cause; `from None` deliberately hides
   internals (e.g. `KeyError` from a lookup table). Never `raise X(str(err))`.
5. **Keep `try` bodies tiny.** Only the call that can raise goes in `try`; success-path code goes in `else:`;
   cleanup goes in `finally:` or a context manager.
6. **Specific before general.** Handlers run first-match, so `except RateLimitError` must precede
   `except ProviderError`.
7. **No `return`/`break`/`continue` in `finally`.** It discards the in-flight exception (SyntaxWarning in 3.14,
   PEP 765).
8. **Log once, at the boundary.** Inner layers add context (`add_note`, attributes, chaining) and re-raise; the
   request/job boundary logs with traceback and converts to a response/exit code. Log-and-raise at every layer
   produces duplicate tracebacks.
9. **`assert` is for invariants, not input.** Asserts vanish under `python -O`; validate arguments with `if` +
   `ValueError`/`TypeError` or Pydantic.
10. **Retry only transient errors, with a budget.** Exponential backoff + full jitter, honour `Retry-After`,
    cap attempts and total time, never retry 400/401/403/422 or context-length errors.
11. **Cancellation must propagate.** Catch `CancelledError` only to clean up, then `raise`.
12. **Raise specific types.** Never `raise Exception("...")`; use builtins (`ValueError`, `TypeError`,
    `LookupError`, `TimeoutError`) or your domain hierarchy.

## Designing a Hierarchy

Group classes by **how the caller reacts**, not by where the error came from.

| Class | Caller reaction | retryable | HTTP |
|-------|-----------------|-----------|------|
| `RagkitError` (base) | catch-all at the boundary | no | 500 |
| `ConfigurationError` | fail fast at startup | no | 500 |
| `InputValidationError` | tell the user what to fix | no | 422 |
| `ProviderError` | translate SDK errors here | depends | 502 |
| `RateLimitError(ProviderError)` | wait `retry_after`, retry | yes | 429 |
| `ProviderOverloadedError(ProviderError)` | backoff, then fallback model | yes | 503 |
| `ContextLengthError(ProviderError)` | truncate/summarise, larger model | no | 413 |
| `StructuredOutputError` | repair loop with validation errors | yes | 502 |
| `ToolExecutionError` | feed error back to the model | no | 500 |
| `VectorStoreError` | retry, then degrade to keyword search | yes | 503 |

```python
class RagkitError(Exception):
    """Base for every error raised by ragkit."""
    retryable: ClassVar[bool] = False

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.message = message
        self.context = context


class ProviderError(RagkitError):
    def __init__(self, message: str, *, provider: str, model: str, **context: Any) -> None:
        super().__init__(message, provider=provider, model=model, **context)
        self.provider, self.model = provider, model


class RateLimitError(ProviderError):
    retryable = True

    def __init__(self, message: str, *, retry_after: Optional[float] = None, **kw: Any) -> None:
        super().__init__(message, retry_after=retry_after, **kw)
        self.retry_after = retry_after
```

Rules: one base per package; inherit from `Exception` (never `BaseException`); names end in `Error`; do not
shadow builtins (`TimeoutError`, `ConnectionError`); you may multiply-inherit a builtin when it helps callers
(`class InputValidationError(RagkitError, ValueError)`); keyword-only context attributes instead of parsing
messages; implement `__reduce__` when `__init__` has keyword-only args so errors survive pickling across
processes. `scripts/scaffold_exceptions.py --preset llm-app --http` generates all of this.

## Translate at the Edge

Wrap third-party exceptions once, inside the client wrapper, so the rest of the codebase never imports
`openai`/`httpx` exception types.

Before:
```python
async def complete(prompt: str) -> str:
    try:
        resp = await client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": prompt}])
        text = resp.choices[0].message.content
        data = json.loads(text)
        return data["answer"]
    except Exception as e:
        logger.error(f"LLM failed: {e}")
        return ""
```

After:
```python
async def complete(prompt: str) -> str:
    try:
        resp = await client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": prompt}])
    except openai.RateLimitError as err:
        raise RateLimitError("rate limited", provider="openai", model=MODEL,
                             retry_after=parse_retry_after(err.response.headers)) from err
    except openai.APITimeoutError as err:
        raise ProviderTimeoutError("timed out", provider="openai", model=MODEL) from err
    except openai.APIStatusError as err:
        if err.status_code >= 500:
            raise ProviderOverloadedError("upstream 5xx", provider="openai", model=MODEL,
                                          status_code=err.status_code) from err
        raise ProviderError(f"upstream {err.status_code}", provider="openai", model=MODEL) from err
    else:
        return parse_answer(resp.choices[0].message.content or "")  # raises StructuredOutputError
```

## EAFP vs LBYL

| Prefer | When | Example |
|--------|------|---------|
| EAFP (`try`) | race-prone checks, the common path succeeds | `try: cfg = cache[key] except KeyError: ...` |
| EAFP | file/network existence checks (TOCTOU) | open the file and catch `FileNotFoundError` |
| LBYL (`if`) | validating caller input with a clear message | `if not 0 < temperature <= 2: raise ValueError(...)` |
| LBYL | the failure is common, or the try would be large | `if chunk.strip():` before embedding |
| Neither | a method exists that expresses intent | `d.get(k, default)`, `next(iter(xs), None)` |

## Context, Chaining and Notes

```python
try:
    chunks = chunker.split(doc.text)
except ValueError as err:
    err.add_note(f"doc_id={doc.id} source={doc.source}")  # 3.11+: shown under the traceback
    raise
```

| Form | `__cause__` | `__suppress_context__` | Traceback shows |
|------|-------------|------------------------|-----------------|
| `raise New()` inside except | None | False | "During handling ... another exception occurred" (looks like a bug in the handler) |
| `raise New() from err` | err | True | "The above exception was the direct cause of ..." |
| `raise New() from None` | None | True | only the new exception |
| `raise` | unchanged | unchanged | original traceback, continued |

Use bare `raise` to re-raise (not `raise err`, which adds a frame and is easy to confuse with a new raise).

## Logging

```python
except VectorStoreError:
    logger.exception("retrieval failed", extra={"collection": coll, "query_id": qid})  # ERROR + traceback
    raise
```
- `logger.exception` only inside an `except` block; elsewhere pass `exc_info=err`.
- Never `logger.error(e)` / `logger.error(f"{e}")`: it drops type and traceback, and many SDK messages are empty.
- Put identifiers in `extra=` (structured logging), never prompts with PII or API keys.

## Async, Timeouts and Groups

```python
async def stream_answer(prompt: str) -> AsyncIterator[str]:
    try:
        async with asyncio.timeout(60):              # 3.11+; use asyncio.wait_for on 3.9/3.10
            async for delta in provider.stream(prompt):
                yield delta
    except asyncio.CancelledError:
        await provider.aclose()                      # cleanup only
        raise                                        # never swallow cancellation
    except TimeoutError as err:                      # asyncio.TimeoutError is TimeoutError since 3.11
        raise ProviderTimeoutError("stream timed out", provider="x", model="y") from err
```

```python
try:
    async with asyncio.TaskGroup() as tg:             # 3.11+
        tasks = [tg.create_task(embed(batch)) for batch in batches]
except* RateLimitError as eg:
    logger.warning("rate limited on %d batches", len(eg.exceptions))
    raise
except* VectorStoreError as eg:
    raise RetrievalError("index unavailable") from eg
```
`except*` handlers each receive a sub-group; unmatched exceptions re-raise automatically. Use
`asyncio.gather(..., return_exceptions=True)` when partial success is acceptable. Details in
[async-and-groups.md](references/async-and-groups.md).

## Retries, Fallbacks and Circuit Breakers

```python
async def with_retry(call, *, attempts=5, base=0.5, cap=30.0, deadline=120.0):
    start = time.monotonic()
    for attempt in range(attempts):
        try:
            return await call()
        except RagkitError as err:
            if not err.retryable or attempt == attempts - 1:
                raise
            delay = getattr(err, "retry_after", None) or random.uniform(0, min(cap, base * 2 ** attempt))
            if time.monotonic() - start + delay > deadline:
                raise
            err.add_note(f"retry attempt {attempt + 1}/{attempts}")  # 3.11+
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")
```

| Error | Retry? | Then |
|-------|--------|------|
| 429 rate limit | yes, honour `Retry-After` | fallback model / queue |
| 500/502/503/529 overloaded | yes, backoff + jitter | fallback model, open circuit |
| connect/read timeout | yes (idempotent calls only) | fallback |
| 400 bad request, 422 | no | fix the request |
| 401/403 auth | no | page someone |
| context length exceeded | no (same input) | truncate history / larger-context model |
| content filtered | no | return a safe refusal |
| malformed JSON output | yes, as a **repair** call with errors | after N tries raise `StructuredOutputError` |
| CUDA OOM | not as-is | halve batch size, `torch.cuda.empty_cache()` |

Full patterns (repair loops, tool errors, embedding partial failures, OOM halving, breakers) are in
[ai-error-handling.md](references/ai-error-handling.md).

## Boundaries: FastAPI, CLIs, Workers

```python
@app.exception_handler(RagkitError)
async def ragkit_error_handler(request: Request, exc: RagkitError) -> JSONResponse:
    status = http_status_for(exc)
    if status >= 500:
        logger.error("request failed", exc_info=exc, extra={"path": request.url.path})
    headers = {"Retry-After": str(math.ceil(exc.retry_after))} if getattr(exc, "retry_after", None) else {}
    return JSONResponse(status_code=status, content=exc.to_dict(), headers=headers)
```

CLI: `main()` catches the package base error, prints one line to stderr and returns exit code 1; lets
`KeyboardInterrupt` become exit code 130. Workers (Celery, queue consumers): catch per message, log with
traceback, ack/nack based on `is_retryable(exc)`, never let one poisoned message kill the loop.

## Warnings vs Exceptions

Use `warnings.warn("top_k > 100 is slow", RuntimeWarning, stacklevel=2)` for "works, but probably not what you
want" and deprecations (`DeprecationWarning`, `stacklevel=2` points at the caller). Escalate in tests with
`-W error` or `filterwarnings = ["error"]` in pytest config.

## Output Format

When reviewing or designing, answer with:
1. **Findings** - numbered, each with location, rule id (EXC0xx when the script flagged it), why it is wrong
   (what failure becomes invisible or mis-handled), and severity.
2. **Fixed code** - complete before/after for every changed handler; keep behaviour on the happy path.
3. **Hierarchy** (when designing) - tree with `retryable` and HTTP status per class, plus where each is raised
   and where it is caught.
4. **Retry/fallback policy** - table of error -> retry? -> backoff -> fallback, with budgets.
5. **Tests** - `pytest.raises(..., match=...)` cases for every new raise path and for retry exhaustion.

## Scripts

```bash
# Audit files or whole directories (AST only; never imports or runs the code)
python scripts/audit_exceptions.py src/ragkit/
python scripts/audit_exceptions.py app/llm_client.py --json
cat handler.py | python scripts/audit_exceptions.py -
python scripts/audit_exceptions.py src/ --strict                       # exit 1 on any finding (CI gate)
python scripts/audit_exceptions.py src/ --select EXC001,EXC003,EXC008  # ids, id prefixes or names
python scripts/audit_exceptions.py src/ --ignore try-too-large --max-try-body 6
```
Rules: EXC001 bare-except, EXC002 base-exception-swallow, EXC003 broad-except-swallow (also
`suppress(Exception)`), EXC004 raise-without-from, EXC005 generic-raise, EXC006 unreachable-handler, EXC007
finally-control-flow, EXC008 cancellation-swallowed, EXC009 assert-validation, EXC010 log-error-not-exception,
EXC011 try-too-large, EXC012 useless-reraise, EXC013 stringified-exception, EXC014 redundant-except-type.
Silence one line with `# noqa: EXC003`. Exit codes: 0 clean (or not strict), 1 findings with `--strict`,
2 usage/read/syntax error.

```bash
# Generate errors.py: base class, retryable flags, attributes, __str__, to_dict, pickling, is_retryable()
python scripts/scaffold_exceptions.py --package ragkit --errors "ProviderError:retryable,provider=str" \
    "RateLimitError(ProviderError):retryable,retry_after=float" "ContextLengthError(ProviderError):tokens=int"
python scripts/scaffold_exceptions.py --package ragkit --preset llm-app --http -o src/ragkit/errors.py
python scripts/scaffold_exceptions.py --spec errors.json --json        # JSON spec file (or - for stdin)
python scripts/scaffold_exceptions.py --package ragkit --preset llm-app --http --check src/ragkit/errors.py
```
Spec grammar: `Name[(Parent)][:retryable,http=429,code=slug,attr=type,...]`. `--http` adds `HTTP_STATUS`,
`http_status_for(exc)` and `register_exception_handlers(app)` for FastAPI. Output is verified with
`ast.parse`/`compile` (exit 2 if invalid); `--check` exits 1 when the file has drifted.

## Additional Resources

| File | Content |
|------|---------|
| [exception-hierarchy.md](references/exception-hierarchy.md) | Full builtin tree, when each builtin is raised, which to raise yourself, version changes |
| [patterns.md](references/patterns.md) | Hierarchy design, translation, chaining, notes, else/finally, cleanup, logging, boundaries, warnings, result types |
| [anti-patterns.md](references/anti-patterns.md) | Every EXC rule with before/after fixes, plus smells the script cannot see |
| [async-and-groups.md](references/async-and-groups.md) | Cancellation, timeouts, TaskGroup, ExceptionGroup and `except*`, gather, generators, threads |
| [ai-error-handling.md](references/ai-error-handling.md) | Provider errors, retries, streaming, JSON repair, tool errors, embeddings, CUDA OOM, vector DBs, breakers, fallbacks |
| [testing-exceptions.md](references/testing-exceptions.md) | pytest.raises, match, ExceptionGroup, warnings, logging assertions, fault injection for retries |
