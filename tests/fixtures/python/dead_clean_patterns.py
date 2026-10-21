"""Fixture for hang_scan.py and hang_watchdog.py: the deadlock-free versions of dead_bad_patterns.py.

hang_scan.py must report zero findings here. Running it finishes in well under a second and
prints "clean pipeline finished", so hang_watchdog.py exits 0 on it.
"""

import asyncio
import logging
import multiprocessing
import queue
import signal
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Lock hierarchy: index_lock (level 1) is always taken before cache_lock (level 2).
index_lock = threading.Lock()
cache_lock = threading.Lock()
stop_event = threading.Event()


def upsert_vectors(batch):
    with index_lock:
        with cache_lock:
            batch.clear()


def evict_cache(keys):
    with index_lock:  # same order as upsert_vectors
        with cache_lock:
            keys.clear()


class EmbeddingCache:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.limiter = asyncio.Semaphore(8)
        self.items = {}

    async def get_or_embed(self, text):
        async with self.lock:
            if text not in self.items:
                self._refresh_locked(text)  # caller holds self.lock
            return self.items[text]

    def _refresh_locked(self, text):
        self.items[text] = [float(len(text))] * 4

    async def call_llm(self, prompt):
        async with self.limiter:  # released on 429s, timeouts and cancellation too
            return await asyncio.wait_for(fake_llm(prompt), timeout=5)


async def fake_llm(prompt):
    await asyncio.sleep(0.01)
    return prompt.upper()


async def consume(q: asyncio.Queue, out):
    while True:
        item = await q.get()
        try:
            out.append(await fake_llm(item))
        finally:
            q.task_done()


async def stream_tokens(tokens):
    buffer = asyncio.Queue(maxsize=4)
    out = []
    consumer = asyncio.create_task(consume(buffer, out))
    for tok in tokens:
        await buffer.put(tok)
    await asyncio.wait_for(buffer.join(), timeout=5)
    consumer.cancel()
    await asyncio.gather(consumer, return_exceptions=True)
    return out


async def wait_for_tool_result(loop):
    tool_done = loop.create_future()
    loop.call_later(0.01, tool_done.set_result, "tool ok")
    return await asyncio.wait_for(tool_done, timeout=5)


def ingest_worker(jobs, results):
    while not stop_event.is_set():
        try:
            doc = jobs.get(timeout=0.05)
        except queue.Empty:
            continue
        results.append(len(doc))


def run_threads(docs):
    jobs = queue.Queue()
    results = []
    workers = [threading.Thread(target=ingest_worker, args=(jobs, results), name=f"ingest-{i}")
               for i in range(2)]
    for w in workers:
        w.start()
    for d in docs:
        jobs.put(d)
    while len(results) < len(docs):
        stop_event.wait(0.01)
    stop_event.set()
    for w in workers:
        w.join(timeout=5)
    return sorted(results)


class ResultBoard:
    def __init__(self):
        self.cond = threading.Condition()
        self.results = []

    def publish(self, item):
        with self.cond:
            self.results.append(item)
            self.cond.notify_all()

    def wait_for_result(self):
        with self.cond:
            if self.cond.wait_for(lambda: self.results, timeout=5):
                return self.results.pop()
            raise TimeoutError("no result within 5s")


def embed_part(part):
    return len(part)


def chunk_and_embed(docs, pool):
    futures = [pool.submit(embed_part, part) for doc in docs for part in doc.split()]
    return [f.result(timeout=30) for f in futures]


def gpu_embed(batch, out):
    out.put([len(x) for x in batch])


def run_gpu_workers(batches):
    ctx = multiprocessing.get_context("spawn")
    out = ctx.Queue()
    procs = [ctx.Process(target=gpu_embed, args=(b, out)) for b in batches]
    for p in procs:
        p.start()
    results = [out.get(timeout=60) for _ in procs]  # drain first
    for p in procs:
        p.join(timeout=10)
    return results


def on_sigterm(signum, frame):
    stop_event.set()  # only set a flag


async def amain():
    cache = EmbeddingCache()
    vec = await cache.get_or_embed("hello")
    replies = await asyncio.gather(*(cache.call_llm(p) for p in ["a", "b", "c"]))
    tokens = await stream_tokens(["x", "y", "z", "w", "v"])
    tool = await wait_for_tool_result(asyncio.get_running_loop())
    return vec, replies, tokens, tool


def main():
    signal.signal(signal.SIGTERM, on_sigterm)
    upsert_vectors([1])
    evict_cache([2])
    print(asyncio.run(amain()))
    print(run_threads(["alpha beta", "gamma", "delta epsilon zeta"]))
    with ThreadPoolExecutor(max_workers=2) as pool:
        print(chunk_and_embed(["a bb", "ccc"], pool))
    board = ResultBoard()
    board.publish("done")
    print(board.wait_for_result())
    print("clean pipeline finished")


if __name__ == "__main__":
    main()
