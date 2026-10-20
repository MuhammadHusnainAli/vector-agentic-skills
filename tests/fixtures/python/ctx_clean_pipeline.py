"""Fixture: correct resource handling in an LLM/RAG pipeline (ctx_tool.py leaks finds nothing)."""

import asyncio
import json
import os
import sqlite3
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, asynccontextmanager, closing, contextmanager

import httpx
import torch

_cache_lock = threading.Lock()


def load_prompts(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_embeddings(rows):
    with closing(sqlite3.connect("vectors.db")) as conn, conn:
        conn.executemany("INSERT INTO emb VALUES (?, ?)", rows)


def embed_all(texts, embed):
    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(embed, texts))


def update_cache(cache, key, value):
    _cache_lock.acquire()
    try:
        cache[key] = value
    finally:
        _cache_lock.release()


def open_many(paths):
    with ExitStack() as stack:
        files = [stack.enter_context(open(p)) for p in paths]
        return [f.readline() for f in files]


def make_client():
    return httpx.Client(timeout=30)  # factory: caller owns it


def read_with_finally(path):
    f = open(path)
    try:
        return f.read()
    finally:
        f.close()


@contextmanager
def vector_transaction(conn):
    conn.execute("BEGIN")
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    else:
        conn.commit()


@contextmanager
def temp_workspace():
    with tempfile.TemporaryDirectory() as d:
        old = os.getcwd()
        os.chdir(d)
        try:
            yield d
        finally:
            os.chdir(old)


@contextmanager
def maybe_mock(enabled):
    if enabled:
        yield "mock"
    else:
        yield "real"


@asynccontextmanager
async def llm_client():
    client = httpx.AsyncClient(timeout=60)
    try:
        yield client
    finally:
        await client.aclose()


class InferenceMode:
    def __init__(self, model):
        self.model = model
        self._was_training = False

    def __enter__(self):
        self._was_training = self.model.training
        self.model.eval()
        return self.model

    def __exit__(self, exc_type, exc, tb):
        self.model.train(self._was_training)
        return exc_type is not None and issubclass(exc_type, StopIteration)


class Client:
    def __init__(self):
        self.http = httpx.Client()

    def close(self):
        self.http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()


async def fan_out(prompts, call):
    sem = asyncio.Semaphore(8)

    async def one(p):
        async with sem:
            return await call(p)

    return await asyncio.gather(*(one(p) for p in prompts))


def predict(model, batch):
    with torch.no_grad():
        return model(batch)
