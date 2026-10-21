"""Fixture for hang_scan.py: an LLM/RAG service full of deadlock and hang risks.

Every DLK rule fires at least once. Static analysis only: do not run this file.
"""

import asyncio
import logging
import multiprocessing as mp
import os
import queue
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

index_lock = threading.Lock()
cache_lock = threading.Lock()
work_queue = queue.Queue()
ready = threading.Event()
results_cv = threading.Condition()
POOL = ThreadPoolExecutor(max_workers=4)


# DLK001: upsert takes index -> cache, evict takes cache -> index
def upsert_vectors(batch):
    with index_lock:
        with cache_lock:
            batch.clear()


def evict_cache(keys):
    with cache_lock:
        with index_lock:
            keys.clear()


class EmbeddingCache:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.limiter = asyncio.Semaphore(8)
        self.items = {}

    # DLK002: get_or_embed holds self.lock and awaits refresh(), which takes it again
    async def get_or_embed(self, text):
        async with self.lock:
            if text not in self.items:
                await self.refresh(text)
            return self.items[text]

    async def refresh(self, text):
        async with self.lock:
            self.items[text] = [0.0] * 8

    # DLK009: a 429 between acquire and release leaks a rate-limit permit forever
    async def call_llm(self, prompt):
        await self.limiter.acquire()
        reply = await fake_llm(prompt)
        self.limiter.release()
        return reply


async def fake_llm(prompt):
    await asyncio.sleep(0)
    return prompt.upper()


# DLK003 + DLK004 + DLK005 + DLK006 + DLK007 in one bad endpoint
async def answer(question, loop):
    with index_lock:
        await asyncio.sleep(0)
    time.sleep(0.5)
    fut = POOL.submit(len, question)
    n = fut.result()
    worker = threading.Thread(target=print, daemon=True)
    worker.start()
    worker.join()
    item = work_queue.get()
    ready.wait()
    reply = asyncio.run_coroutine_threadsafe(fake_llm(question), loop).result()
    loop.run_until_complete(fake_llm(question))
    return n, item, reply


# DLK008: join() on a queue nobody calls task_done() on
async def drain_jobs(jobs: asyncio.Queue):
    await jobs.join()


# DLK010 + DLK011
def wait_for_results(results):
    with results_cv:
        if not results:
            results_cv.wait()
        return results.pop()


def ingest_worker():
    doc = work_queue.get()
    ready.wait()
    return doc


# DLK012: a chunking task waits on embedding tasks in the same pool
def chunk_and_embed(doc):
    futures = [POOL.submit(len, part) for part in doc.split()]
    return [f.result() for f in futures]


def ingest_corpus(docs):
    return list(POOL.map(chunk_and_embed, docs))


# DLK013: non-daemon heartbeat thread, never joined
def start_heartbeat():
    hb = threading.Thread(target=ingest_worker)
    hb.start()


# DLK014: parent joins GPU workers before reading their results
def gpu_embed(batch, out):
    out.put([len(x) for x in batch])


def run_gpu_workers(batches):
    out = mp.Queue()
    procs = [mp.Process(target=gpu_embed, args=(b, out)) for b in batches]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    return [out.get() for _ in procs]


# DLK015: bounded queue filled with no consumer in sight
async def stream_tokens(tokens):
    buffer = asyncio.Queue(maxsize=16)
    for tok in tokens:
        await buffer.put(tok)


# DLK016: tool-call future nobody ever resolves
async def wait_for_tool_result(loop):
    tool_done = loop.create_future()
    await tool_done


# DLK017: fork while a thread pool and heartbeat thread exist
def fork_scraper():
    pid = os.fork()
    return pid


# DLK018: signal handler that logs and takes a lock
def on_sigterm(signum, frame):
    with cache_lock:
        logger.warning("shutting down on %s", signum)


signal.signal(signal.SIGTERM, on_sigterm)
