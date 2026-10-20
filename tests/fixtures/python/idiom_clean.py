"""Fixture: idiomatic modern Python; review_idioms.py should report nothing."""
from __future__ import annotations

import asyncio
import contextlib
import functools
import json
import logging
import os
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)
MAX_RETRIES = 5
PROMPT = """\
Answer using only the context.

Context:
{context}

Question: {question}"""


@dataclass
class Chunk:
    doc_id: str
    text: str
    tags: list[str] = field(default_factory=list)


@functools.cache
def api_key() -> str:
    return os.environ["OPENAI_API_KEY"]


def build_prompt(question: str, chunks: list[Chunk]) -> str:
    context = "\n\n".join(f"[{i}] {c.text}" for i, c in enumerate(chunks, start=1))
    return PROMPT.format(context=context, question=question)


def group_by_doc(chunks: list[Chunk]) -> dict[str, list[Chunk]]:
    groups: dict[str, list[Chunk]] = defaultdict(list)
    for chunk in chunks:
        groups[chunk.doc_id].append(chunk)
    return dict(groups)


def has_stop_token(text: str, stops: tuple[str, ...]) -> bool:
    return any(stop in text for stop in stops)


def load_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def clear_cache(path: Path) -> None:
    with contextlib.suppress(FileNotFoundError):
        path.unlink()


async def post_with_retry(client: httpx.AsyncClient, url: str, payload: dict) -> dict:
    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as err:
            if err.response.status_code != 429:
                raise
            await asyncio.sleep(min(60, 2 ** attempt) + random.random())
    raise RuntimeError(f"gave up after {MAX_RETRIES} attempts")


async def embed_all(client: httpx.AsyncClient, texts: list[str], limit: int = 8) -> list[dict]:
    sem = asyncio.Semaphore(limit)

    async def one(text: str) -> dict:
        async with sem:
            return await post_with_retry(client, "https://api.example.com/embed", {"input": text})

    return await asyncio.gather(*(one(t) for t in texts))


def stamp() -> str:
    now = datetime.now(timezone.utc)
    logger.info("stamped at %s", now)
    return now.isoformat()


def describe(role: str) -> int:
    dispatch = {"system": 0, "user": 1, "assistant": 2, "tool": 3}
    return dispatch.get(role, -1)
