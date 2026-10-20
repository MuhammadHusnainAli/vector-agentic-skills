# Error Handling for AI Applications

Failure modes specific to LLM apps, RAG pipelines, agents and model inference/training, with production
patterns: classify provider errors, retry with backoff and jitter, honour `Retry-After`, handle broken
streams, repair malformed structured output, feed tool errors back to the model, survive partial embedding
failures, recover from CUDA OOM, degrade around vector DB outages, and fall back between models behind a
circuit breaker.

## Contents

- [1. Failure taxonomy](#1-failure-taxonomy)
- [2. Translating provider SDK errors](#2-translating-provider-sdk-errors)
- [3. Retry with backoff, jitter and Retry-After](#3-retry-with-backoff-jitter-and-retry-after)
- [4. Context length exceeded](#4-context-length-exceeded)
- [5. Content filtering and refusals](#5-content-filtering-and-refusals)
- [6. Streaming failures mid-response](#6-streaming-failures-mid-response)
- [7. Structured output: validate and repair](#7-structured-output-validate-and-repair)
- [8. Tool-call errors fed back to the model](#8-tool-call-errors-fed-back-to-the-model)
- [9. Embedding batches with partial failure](#9-embedding-batches-with-partial-failure)
- [10. GPU out-of-memory: halve the batch](#10-gpu-out-of-memory-halve-the-batch)
- [11. Vector database errors](#11-vector-database-errors)
- [12. Circuit breaker](#12-circuit-breaker)
- [13. Model fallback chains](#13-model-fallback-chains)
- [14. Budgets, idempotency and observability](#14-budgets-idempotency-and-observability)
- [15. Training loops and evals](#15-training-loops-and-evals)

## 1. Failure taxonomy

| Failure | Typical signal | Retryable | Strategy |
|---------|----------------|-----------|----------|
| Rate limit | HTTP 429, `RateLimitError`, `retry-after` / `x-ratelimit-reset-*` headers | yes | wait `retry_after` (else backoff + jitter), lower concurrency |
| Overloaded / server error | 500, 502, 503, 504, 529 | yes | backoff + jitter, then fallback model |
| Network | connect reset, DNS, TLS, `httpx.ConnectError` | yes | backoff; idempotent requests only |
| Timeout | `APITimeoutError`, `httpx.ReadTimeout`, own deadline | yes (bounded) | shorter prompt / max_tokens, fallback |
| Bad request | 400, 404 model not found, 422 | no | bug or config: raise |
| Auth | 401, 403 | no | config error: alert |
| Context length | 400 with `context_length_exceeded` code / "prompt is too long" | no (same input) | truncate, summarise, larger-context model |
| Content filter | 400 policy error, `finish_reason == "content_filter"`, refusal | no | safe message; do not retry blindly |
| Truncated output | `finish_reason == "length"` / `stop_reason == "max_tokens"` | yes with more tokens | raise max_tokens or continue generation |
| Malformed JSON / schema mismatch | `json.JSONDecodeError`, `pydantic.ValidationError` | yes, as a repair call | repair loop with the error message |
| Tool execution error | your tool raises | no (transport) | return the error to the model as a tool result |
| Embedding partial failure | some inputs fail / batch rejected | partially | retry failed indices, split oversize inputs |
| CUDA OOM | `torch.cuda.OutOfMemoryError` | not as-is | free memory, halve batch, retry |
| Vector DB down | connection errors, 5xx, timeouts | yes | retry, then degrade (keyword search / cache) |

Encode the decision in the exception class (`retryable`) rather than in scattered `if status == ...` checks.

## 2. Translating provider SDK errors

Translate once in the client wrapper; the rest of the app sees only domain errors (see `patterns.md`).
SDK class names below are from the official `openai` Python SDK v1; the `anthropic` SDK has the same shape
(`APIConnectionError`, `APITimeoutError`, `APIStatusError` with `RateLimitError`, `BadRequestError`,
`AuthenticationError`, `InternalServerError`).

```python
import email.utils
import time
from typing import Mapping, Optional

import openai


def parse_retry_after(headers: Mapping[str, str]) -> Optional[float]:
    """Seconds to wait from Retry-After (seconds or HTTP date) or retry-after-ms."""
    ms = headers.get("retry-after-ms")
    if ms:
        try:
            return float(ms) / 1000
        except ValueError:
            pass
    value = headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        parsed = email.utils.parsedate_to_datetime(value)   # HTTP-date form
    except (TypeError, ValueError):
        return None
    return max(0.0, parsed.timestamp() - time.time())


CONTEXT_MARKERS = ("context_length_exceeded", "maximum context length", "prompt is too long")


async def chat(messages: list, *, model: str, **kw) -> "openai.types.chat.ChatCompletion":
    ctx = {"provider": "openai", "model": model}
    try:
        return await client.chat.completions.create(model=model, messages=messages, **kw)
    except openai.RateLimitError as err:
        raise RateLimitError("rate limited", retry_after=parse_retry_after(err.response.headers), **ctx) from err
    except openai.APITimeoutError as err:          # subclass of APIConnectionError: must come first
        raise ProviderTimeoutError("request timed out", **ctx) from err
    except openai.APIConnectionError as err:
        raise ProviderOverloadedError("connection failed", **ctx) from err
    except openai.BadRequestError as err:
        body = str(getattr(err, "body", "") or err).lower()
        if getattr(err, "code", None) == "context_length_exceeded" or any(m in body for m in CONTEXT_MARKERS):
            raise ContextLengthError("prompt exceeds the context window", **ctx) from err
        if getattr(err, "code", None) == "content_filter":
            raise ContentFilterError("request blocked by content policy", **ctx) from err
        raise ProviderError(f"bad request: {err.message}", **ctx) from err
    except openai.AuthenticationError as err:
        raise ProviderAuthError("invalid API key", **ctx) from err
    except openai.APIStatusError as err:
        if err.status_code >= 500:
            raise ProviderOverloadedError(f"upstream {err.status_code}", status_code=err.status_code, **ctx) from err
        raise ProviderError(f"upstream {err.status_code}", **ctx) from err
```

Notes:
- SDKs retry internally (`max_retries=2` by default in openai/anthropic). Either set `max_retries=0` and own
  the policy, or keep the SDK retries and do not stack another 5 attempts on top (that is 15 calls).
- Read status and codes from attributes (`err.status_code`, `err.code`, `err.response.headers`), not messages,
  except where providers only signal via message text (context length) - keep those markers in one place.
- Successful responses can still be failures: check `finish_reason` / `stop_reason`.

```python
choice = resp.choices[0]
if choice.finish_reason == "length":
    raise TruncatedOutputError("hit max_tokens", provider="openai", model=model)
if choice.finish_reason == "content_filter":
    raise ContentFilterError("output filtered", provider="openai", model=model)
```

## 3. Retry with backoff, jitter and Retry-After

```python
import asyncio
import random
import time
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


async def retry_async(
    call: Callable[[], Awaitable[T]],
    *,
    attempts: int = 5,
    base: float = 0.5,
    cap: float = 30.0,
    deadline: float = 90.0,
    is_retryable: Callable[[BaseException], bool] = is_retryable,
) -> T:
    """Full-jitter exponential backoff; honours retry_after; bounded by attempts and wall time."""
    start = time.monotonic()
    for attempt in range(1, attempts + 1):
        try:
            return await call()
        except Exception as err:
            if not is_retryable(err) or attempt == attempts:
                raise
            hinted = getattr(err, "retry_after", None)
            delay = hinted if hinted is not None else random.uniform(0, min(cap, base * 2 ** (attempt - 1)))
            remaining = deadline - (time.monotonic() - start)
            if delay >= remaining:
                err.add_note(f"gave up after {attempt} attempts: retry delay {delay:.1f}s exceeds deadline")
                raise
            logger.warning("retrying after %s (attempt %d/%d, sleep %.2fs)", type(err).__name__,
                           attempt, attempts, delay)
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")
```

Key properties:
- `except Exception` is fine here because non-retryable errors are re-raised immediately and
  `CancelledError` (BaseException) passes through `asyncio.sleep` untouched.
- **Full jitter** (`uniform(0, backoff)`) spreads clients apart after a shared 429; plain exponential backoff
  synchronises them.
- Bound by attempts **and** wall-clock deadline; the user is waiting.
- Re-raise the last real exception (not a generic `RetryError`) so handlers and HTTP mapping still work.
- Only retry idempotent operations, or use idempotency keys.

With tenacity:

```python
from tenacity import (AsyncRetrying, retry_if_exception, stop_after_attempt, stop_after_delay,
                      wait_random_exponential)


def wait_retry_after_or_jitter(retry_state) -> float:
    err = retry_state.outcome.exception()
    hinted = getattr(err, "retry_after", None)
    return hinted if hinted is not None else wait_random_exponential(multiplier=0.5, max=30)(retry_state)


async def chat_with_retry(messages: list, model: str):
    async for attempt in AsyncRetrying(
        retry=retry_if_exception(is_retryable),
        wait=wait_retry_after_or_jitter,
        stop=stop_after_attempt(5) | stop_after_delay(90),
        reraise=True,                                 # raise the original error, not RetryError
    ):
        with attempt:
            return await chat(messages, model=model)
```

Client-side rate limiting prevents most 429s: a token bucket or `asyncio.Semaphore` sized to your TPM/RPM
quota, and lowering concurrency when 429s appear (AIMD).

## 4. Context length exceeded

Not retryable with the same input. Recover by shrinking the prompt, then optionally switching models.

```python
async def answer_with_budget(question: str, history: list, chunks: list, model: str) -> str:
    for attempt in range(3):
        messages = build_messages(question, history, chunks)
        try:
            resp = await chat(messages, model=model, max_tokens=800)
        except ContextLengthError as err:
            err.add_note(f"attempt {attempt}: {len(history)} turns, {len(chunks)} chunks")
            if chunks:
                chunks = chunks[: len(chunks) // 2]           # drop lowest-ranked retrieved chunks
            elif len(history) > 2:
                history = [await summarise_history(history)]  # compress the conversation
            else:
                raise
            continue
        return resp.choices[0].message.content
    raise ContextLengthError("prompt still too long after trimming", provider="openai", model=model)
```

Prevent rather than recover: count tokens before the call (`tiktoken`, provider token-count endpoints) and
budget `prompt_tokens + max_tokens <= context_window`.

## 5. Content filtering and refusals

- Treat as a terminal, user-facing outcome: return a safe message, log the category, do not retry the same
  input in a loop.
- Distinguish **input** blocked (400 from the provider) from **output** filtered (`finish_reason`).
- Model refusals inside a normal 200 response are not exceptions; detect them in the parsing layer if your
  product needs to (structured-output APIs may expose a `refusal` field).

```python
try:
    reply = await assistant.reply(conversation)
except ContentFilterError as err:
    logger.info("content filtered", extra={"category": err.context.get("category"), "user": user_id})
    reply = "I can't help with that request."
```

## 6. Streaming failures mid-response

A stream can fail after tokens were delivered. Decide per product:

| Strategy | When |
|----------|------|
| Surface error, keep partial text | chat UIs: show partial answer + "response interrupted, retry?" |
| Restart from scratch | short outputs, structured outputs (partial JSON is useless) |
| Continue generation | long-form text: send the partial output as an assistant prefix and ask to continue |

```python
async def stream_reply(messages: list, model: str):
    received = []
    try:
        stream = await client.chat.completions.create(model=model, messages=messages, stream=True)
        async for event in stream:
            delta = event.choices[0].delta.content if event.choices else None
            if delta:
                received.append(delta)
                yield delta
    except (openai.APIConnectionError, openai.APIStatusError, httpx.RemoteProtocolError) as err:
        raise StreamInterruptedError("stream broke mid-response", provider="openai", model=model,
                                     received_chars=sum(map(len, received))) from err
```

Rules: never retry a stream transparently after yielding tokens (the consumer would see duplicated text);
add an idle timeout between chunks (see `async-and-groups.md`); let `CancelledError` (client disconnected)
propagate and close the upstream stream so you stop paying for tokens.

## 7. Structured output: validate and repair

Models return almost-JSON: code fences, trailing commas, missing fields, wrong types. Validate with Pydantic
and, on failure, send the validation errors back for a bounded number of repair attempts.

```python
import json
import re

from pydantic import BaseModel, Field, ValidationError


class Extraction(BaseModel):
    company: str
    amount: float = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")


FENCE = re.compile(r"^`{3}(?:json)?\s*|\s*`{3}$", re.MULTILINE)  # strip markdown code fences


def parse_extraction(text: str) -> Extraction:
    cleaned = FENCE.sub("", text.strip())
    try:
        return Extraction.model_validate_json(cleaned)
    except ValidationError as err:
        raise StructuredOutputError("output failed schema validation", raw_output=text[:2000],
                                    errors=[f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in err.errors()]
                                    ) from err


async def extract(document: str, model: str, max_repairs: int = 2) -> Extraction:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": document}]
    for attempt in range(max_repairs + 1):
        resp = await chat(messages, model=model, response_format={"type": "json_object"})
        text = resp.choices[0].message.content or ""
        try:
            return parse_extraction(text)
        except StructuredOutputError as err:
            if attempt == max_repairs:
                err.add_note(f"gave up after {max_repairs} repair attempts")
                raise
            messages += [
                {"role": "assistant", "content": text},
                {"role": "user", "content": "Your JSON was invalid:\n- " + "\n- ".join(err.errors)
                 + "\nReturn only corrected JSON matching the schema."},
            ]
    raise AssertionError("unreachable")
```

Notes:
- `model_validate_json` raises `ValidationError` for both invalid JSON and schema violations (Pydantic v2).
- Prefer provider-native structured output (JSON schema / tool-forced output) to reduce failures; keep the
  repair loop anyway.
- Cap repairs (1-2); log raw outputs truncated; count repairs as a quality metric.

## 8. Tool-call errors fed back to the model

In an agent loop, an exception inside a tool is information for the model, not a crash. Return it as the
tool result; reserve raising for errors the model cannot fix (auth, budget, cancellation, bugs in your loop).

```python
class ToolInputError(RagkitError):
    """The model passed bad arguments; tell it what to fix."""


async def run_tool_call(call) -> dict:
    tool = TOOLS.get(call.function.name)
    if tool is None:
        return tool_result(call.id, f"error: unknown tool {call.function.name!r}; available: {sorted(TOOLS)}")
    try:
        args = json.loads(call.function.arguments or "{}")
        params = tool.schema.model_validate(args)
    except (json.JSONDecodeError, ValidationError) as err:
        return tool_result(call.id, f"error: invalid arguments: {err}")
    try:
        async with asyncio.timeout(20):
            output = await tool.run(params)
    except TimeoutError:
        return tool_result(call.id, "error: tool timed out after 20s; try a narrower query")
    except (ToolInputError, LookupError, ValueError) as err:
        return tool_result(call.id, f"error: {err}")
    except ProviderAuthError:
        raise                                      # the model cannot fix this
    except Exception as err:
        logger.exception("tool %s crashed", call.function.name)
        return tool_result(call.id, f"error: tool failed with {type(err).__name__}")  # no internals
    return tool_result(call.id, truncate(json.dumps(output, default=str), 8000))


def tool_result(call_id: str, content: str) -> dict:
    return {"role": "tool", "tool_call_id": call_id, "content": content}
```

Guardrails: cap consecutive tool errors (e.g. 3) and the total number of agent steps, then raise
`ToolExecutionError`/`AgentLoopError`; never send tracebacks, secrets or SQL to the model.

## 9. Embedding batches with partial failure

```python
async def embed_texts(texts: list, batch_size: int = 128, max_rounds: int = 3) -> list:
    vectors: list = [None] * len(texts)
    pending = list(range(len(texts)))
    for round_no in range(max_rounds):
        failed = []
        for start in range(0, len(pending), batch_size):
            idx = pending[start:start + batch_size]
            try:
                out = await retry_async(lambda idx=idx: embedder.embed([texts[i] for i in idx]))
            except ContextLengthError:
                if len(idx) == 1:
                    texts[idx[0]] = truncate_tokens(texts[idx[0]], 8000)  # oversize single input
                failed.extend(idx)
                continue
            except ProviderError as err:
                logger.warning("embedding batch failed (round %d): %s", round_no, err)
                failed.extend(idx)
                continue
            for i, vec in zip(idx, out):
                vectors[i] = vec
        if not failed:
            return vectors
        pending, batch_size = failed, max(1, batch_size // 4)   # smaller batches isolate bad inputs
    raise EmbeddingError(f"{len(pending)} of {len(texts)} texts could not be embedded", provider="openai",
                         failed_indices=pending)
```

Also validate before sending: drop empty strings (many APIs reject them), strip NULs, cap token length, and
check output dimensionality (`len(vec) == EXPECTED_DIM`) to fail fast on a misconfigured model.

## 10. GPU out-of-memory: halve the batch

`torch.cuda.OutOfMemoryError` (torch >= 1.13, subclass of `RuntimeError`) is recoverable if you release the
references and retry with a smaller batch.

```python
import gc

import torch


def _is_oom(err: BaseException) -> bool:
    oom_cls = getattr(torch.cuda, "OutOfMemoryError", None)
    return (oom_cls is not None and isinstance(err, oom_cls)) or "out of memory" in str(err).lower()


@torch.inference_mode()
def encode_adaptive(model, texts: list, batch_size: int = 256, min_batch: int = 1) -> torch.Tensor:
    outputs, i = [], 0
    while i < len(texts):
        batch = texts[i:i + batch_size]
        oom = False
        try:
            outputs.append(model.encode(batch, convert_to_tensor=True).cpu())
        except RuntimeError as err:
            if not _is_oom(err) or batch_size <= min_batch:
                raise
            oom = True                                   # recover after the handler has exited
        if oom:
            gc.collect()                                 # the traceback (and its tensors) is gone now
            torch.cuda.empty_cache()
            batch_size = max(min_batch, batch_size // 2)
            logger.warning("CUDA OOM; retrying with batch_size=%d", batch_size)
            continue
        i += len(batch)
    return torch.cat(outputs)
```

Details:
- Do the recovery **outside** the `except` block: the active exception's traceback references frames that
  hold tensors, so `empty_cache()` inside the handler cannot free them. The `oom` flag above defers cleanup
  until the handler has exited and `err` has been deleted.
- In training, also zero gradients (`optimizer.zero_grad(set_to_none=True)`) before retrying, and consider
  gradient accumulation to keep the effective batch size.
- Do not catch OOM inside distributed training steps unless every rank does the same; otherwise collectives
  deadlock.
- Host-RAM OOM usually kills the process (no exception); `MemoryError` is rare.

## 11. Vector database errors

```python
async def search_with_degradation(query: str, top_k: int = 8) -> list:
    vector = await embedder.embed_one(query)
    try:
        return await retry_async(lambda: store.search(vector, top_k=top_k), attempts=3, deadline=5.0)
    except VectorStoreError as err:
        logger.warning("vector store unavailable; using BM25 fallback", exc_info=err)
        metrics.increment("retrieval.fallback.bm25")
        return keyword_index.search(query, top_k=top_k)
```

| Error | Handling |
|-------|----------|
| connection refused/reset, timeout, 5xx | retryable `VectorStoreError`, then degrade |
| collection/index not found | `ConfigurationError` - do not retry |
| dimension mismatch on upsert/search | `ConfigurationError` (embedding model changed) |
| payload too large / batch limit | split the batch, not retryable as-is |
| partial upsert failure | upsert is usually idempotent by id: retry the failed ids |

Use deterministic ids (hash of source + chunk index) so retries of upserts are idempotent.

## 12. Circuit breaker

Stop hammering a failing dependency; fail fast with a retryable error while it recovers.

```python
import time


class CircuitBreaker:
    """closed -> open after `threshold` consecutive failures; half-open after `reset_after` seconds."""

    def __init__(self, name: str, threshold: int = 5, reset_after: float = 30.0) -> None:
        self.name, self.threshold, self.reset_after = name, threshold, reset_after
        self.failures = 0
        self.opened_at = None

    def _check(self) -> None:
        if self.opened_at is None:
            return
        remaining = self.reset_after - (time.monotonic() - self.opened_at)
        if remaining > 0:
            raise CircuitOpenError(f"circuit {self.name!r} is open", retry_after=remaining)
        # half-open: allow one trial call through

    async def call(self, fn, *args, **kwargs):
        self._check()
        try:
            result = await fn(*args, **kwargs)
        except Exception as err:
            if is_retryable(err):                    # only infrastructure failures trip the breaker
                self.failures += 1
                if self.failures >= self.threshold or self.opened_at is not None:
                    self.opened_at = time.monotonic()
            raise
        self.failures, self.opened_at = 0, None
        return result


openai_breaker = CircuitBreaker("openai")
```

Do not count client errors (400, context length, validation) as breaker failures; they say nothing about the
dependency's health. In multi-process deployments, keep breaker state per process or in Redis.

## 13. Model fallback chains

```python
FALLBACKS = [("openai", "gpt-4o"), ("anthropic", "claude-sonnet"), ("local", "llama-3-8b")]


async def complete_with_fallback(messages: list) -> str:
    errors = []
    for provider, model in FALLBACKS:
        try:
            return await BREAKERS[provider].call(
                retry_async, lambda: CLIENTS[provider].complete(messages, model=model), attempts=2)
        except (ProviderOverloadedError, RateLimitError, ProviderTimeoutError, CircuitOpenError) as err:
            err.add_note(f"fallback: {provider}/{model} failed")
            errors.append(err)
            continue
        except ContextLengthError as err:
            errors.append(err)                      # a larger-context model later in the chain may fit
            continue
    raise ExceptionGroup("all models failed", errors)
```

Rules: fall back only on availability errors (and context length if a later model is larger), never on
400/auth/content-filter; prompts may need per-model adaptation; record which model answered for evals.
On 3.9/3.10, raise `ProviderError("all models failed") from errors[-1]` instead of `ExceptionGroup`.

## 14. Budgets, idempotency and observability

- Budgets: track tokens/cost per request and tenant; raise `BudgetExceededError` before calling the model.
- Idempotency: pass idempotency keys where APIs support them; make writes (DB, vector upserts, emails)
  idempotent before enabling retries around them.
- Observability: one structured log at the boundary with `error_code`, `provider`, `model`, `attempts`,
  `latency_ms`, `retryable`; metrics for retries, fallbacks, repairs, breaker state; trace spans with
  `span.record_exception(err)` and `span.set_status(StatusCode.ERROR)` (OpenTelemetry).
- Error budgets in evals: count provider errors separately from wrong answers; a run with 10% 429s is not a
  quality regression.

## 15. Training loops and evals

```python
def train(model, loader, optimizer, ckpt_dir: str, max_bad_batches: int = 10) -> None:
    bad = 0
    step = 0
    try:
        for step, batch in enumerate(loader):
            loss = model(**batch).loss
            if not torch.isfinite(loss):
                bad += 1
                logger.warning("non-finite loss at step %d (%d/%d)", step, bad, max_bad_batches)
                if bad > max_bad_batches:
                    raise FloatingPointError(f"loss diverged: {bad} non-finite losses by step {step}")
                optimizer.zero_grad(set_to_none=True)
                continue
            loss.backward()
            optimizer.step()
            optimizer.zero_grad(set_to_none=True)
    except BaseException:
        save_checkpoint(model, optimizer, f"{ckpt_dir}/interrupted-{step}.pt")  # also on Ctrl+C / preemption
        raise
```

Eval harnesses: run each sample in isolation, record per-sample errors (result type), and fail the run only on
systemic errors (auth, config) or when the error rate exceeds a threshold.

```python
async def run_eval(samples: list, threshold: float = 0.05) -> dict:
    results = await asyncio.gather(*(score(s) for s in samples), return_exceptions=True)
    errors = [r for r in results if isinstance(r, Exception)]
    if any(isinstance(e, (ProviderAuthError, ConfigurationError)) for e in errors):
        raise next(e for e in errors if isinstance(e, (ProviderAuthError, ConfigurationError)))
    if len(errors) / max(1, len(samples)) > threshold:
        raise ExceptionGroup(f"{len(errors)} eval samples errored", errors)
    scores = [r for r in results if not isinstance(r, BaseException)]
    return {"mean": sum(scores) / max(1, len(scores)), "errors": len(errors)}
```
