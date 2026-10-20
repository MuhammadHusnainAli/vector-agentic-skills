"""Fixture: an LLM/RAG pipeline full of resource-handling bugs (for ctx_tool.py leaks)."""

import json
import sqlite3
import subprocess
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, asynccontextmanager
from pathlib import Path

import aiohttp
import httpx
import requests
import torch

_cache_lock = threading.Lock()
http = requests.Session()  # module-level client, never closed


def load_prompts(path):
    return json.load(open(path))  # file passed along, closed only by GC


def read_config(config_path):
    return config_path.open().read()  # Path.open() chained


def save_embeddings(rows):
    conn = sqlite3.connect("vectors.db")  # never closed
    conn.executemany("INSERT INTO emb VALUES (?, ?)", rows)
    conn.commit()


def write_manifest(path, data):
    f = open(path, "w")
    f.write(json.dumps(data))
    f.close()  # not in finally: leaks if json.dumps raises


def embed_all(texts, embed):
    pool = ThreadPoolExecutor(max_workers=8)
    return list(pool.map(embed, texts))  # pool never shut down


def scratch_dir():
    d = tempfile.mkdtemp()  # never removed
    Path(d, "notes.txt").write_text("hi")


def start_tool_server():
    subprocess.Popen(["python", "-m", "tool_server"])  # fire and forget


def update_cache(cache, key, value):
    _cache_lock.acquire()
    cache[key] = value  # KeyError/MemoryError here deadlocks every later caller
    _cache_lock.release()


def bump_counter(counts, key):
    with threading.Lock():  # new lock every call: no mutual exclusion
        counts[key] = counts.get(key, 0) + 1


@contextmanager
def vector_transaction(db):
    conn = db.connect()
    conn.begin()
    yield conn
    conn.commit()  # skipped if the body raises
    conn.close()


@contextmanager
def ignore_rate_limits(client):
    try:
        yield client
    except Exception:  # does not re-raise: suppresses every error in the block
        print("rate limited")


@contextmanager
def retrying_session():
    for attempt in range(3):
        yield attempt  # yields more than once


@contextmanager
def maybe_trace(enabled):
    try:
        yield "span"
    except ValueError:
        yield "fallback"  # second yield after throw()
        raise


@contextmanager
async def llm_session():  # async def under @contextmanager
    async with httpx.AsyncClient() as client:
        yield client


@asynccontextmanager
async def fetch_session():
    with aiohttp.ClientSession() as session:  # async-only resource with plain with
        yield session


class GPUSession:
    def __init__(self, model):
        self.model = model
        self.client = httpx.Client(timeout=30)  # class owns it, nothing closes it

    def __enter__(self):
        self.model.eval()  # returns None

    def __exit__(self, exc_type, exc, tb):
        self.model.train()
        return True  # swallows every exception


class Meter:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc):  # wrong signature
        return None


class AsyncPool:
    async def __enter__(self):  # async def for the sync protocol
        return self

    def __aexit__(self, exc_type, exc, tb):  # must be async def
        return False


def predict(model, batch):
    torch.no_grad()  # created, never entered: gradients still tracked
    with GPUSession(model) as s:
        return s.model(batch)
