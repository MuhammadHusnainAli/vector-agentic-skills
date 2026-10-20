"""Fixture: idiomatic exception handling for an LLM client wrapper; audits clean."""
import asyncio
import json
import logging
import random

logger = logging.getLogger(__name__)


class AppError(Exception):
    retryable = False


class ProviderError(AppError):
    pass


class RateLimitError(ProviderError):
    retryable = True

    def __init__(self, message, *, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


class StructuredOutputError(AppError):
    pass


async def call_with_retry(call, *, attempts=4, base=0.5, cap=20.0):
    for attempt in range(attempts):
        try:
            return await call()
        except RateLimitError as err:
            if attempt == attempts - 1:
                raise
            delay = err.retry_after or min(cap, base * 2 ** attempt)
            await asyncio.sleep(random.uniform(0, delay))
        except ProviderError:
            logger.exception("provider failed", extra={"attempt": attempt})
            raise
    raise AssertionError("unreachable")


def parse_tool_args(raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError as err:
        raise StructuredOutputError("tool arguments are not valid JSON") from err


async def stream_tokens(client, prompt):
    try:
        async for tok in client.stream(prompt):
            yield tok
    except asyncio.CancelledError:
        await client.aclose()
        raise


def rerank(docs, top_k):
    if top_k <= 0:
        raise ValueError(f"top_k must be positive, got {top_k!r}")
    return docs[:top_k]


def index_chunks(store, chunks):
    failed = []
    for chunk in chunks:
        try:
            store.upsert(chunk)
        except ConnectionError:
            logger.exception("upsert failed", extra={"chunk_id": chunk.id})
            failed.append(chunk.id)
    return failed
