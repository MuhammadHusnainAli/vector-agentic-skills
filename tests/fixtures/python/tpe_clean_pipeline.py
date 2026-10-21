"""Fixture for executor_tool.py check: correct thread-pool patterns, zero findings.

Runnable offline (stdlib only, ~1 s): python3 tests/fixtures/python/tpe_clean_pipeline.py
A toy RAG ingestion job: "fetch" pages, "embed" chunks under an RPM limit with a
sliding window, upsert in batches, with per-thread clients, context propagation,
lock-protected stats, a joined writer thread and a heartbeat daemon.
"""
import atexit
import contextvars
import itertools
import logging
import os
import queue
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait

log = logging.getLogger("ingest")
request_id = contextvars.ContextVar("request_id", default="-")
_local = threading.local()
_stats_lock = threading.Lock()
STATS = {"embedded": 0, "failed": 0}
WORKERS = min(32, (os.cpu_count() or 1) + 4)
IO_POOL = ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix="io")
atexit.register(IO_POOL.shutdown, wait=True, cancel_futures=True)


class FakeClient:
    """Stands in for a per-thread HTTP session."""

    def __init__(self):
        self.calls = 0

    def get(self, url):
        self.calls += 1
        time.sleep(0.002)
        return f"<html>{url}</html>"


def client():
    if not hasattr(_local, "client"):
        _local.client = FakeClient()
    return _local.client


def fetch(url):
    return client().get(url)


def embed(chunk):
    time.sleep(0.001)
    with _stats_lock:
        STATS["embedded"] += 1
    return [float(len(chunk)), float(len(request_id.get()))]


def iter_chunks(n):
    for i in range(n):
        yield f"chunk {i} " * (1 + i % 3)


def embed_window(chunks, ex, max_in_flight=16):
    """Sliding window: never more than max_in_flight futures over a lazy source."""
    out, inflight = [], {}
    source = enumerate(chunks)
    for i, chunk in itertools.islice(source, max_in_flight):
        inflight[ex.submit(contextvars.copy_context().run, embed, chunk)] = i
    while inflight:
        done, _ = wait(inflight, timeout=30, return_when=FIRST_COMPLETED)
        for fut in done:
            i = inflight.pop(fut)
            try:
                out.append((i, fut.result()))
            except Exception as exc:
                log.warning("chunk %d failed", i, exc_info=exc)
                with _stats_lock:
                    STATS["failed"] += 1
        for i, chunk in itertools.islice(source, len(done)):
            inflight[ex.submit(contextvars.copy_context().run, embed, chunk)] = i
    return sorted(out)


def writer(q, sink):
    while True:
        item = q.get()
        if item is None:
            break
        sink.append(item)


def heartbeat(stop):
    while not stop.wait(0.05):
        log.debug("alive")


def on_done(fut):
    exc = fut.exception()
    if exc is not None:
        log.error("upsert failed", exc_info=exc)


def handle_query(pool, urls):
    futures = [pool.submit(fetch, u) for u in urls]
    deadline = time.monotonic() + 10
    return [f.result(timeout=max(0.0, deadline - time.monotonic())) for f in futures]


def main():
    stop = threading.Event()
    beat = threading.Thread(target=heartbeat, args=(stop,), daemon=True, name="heartbeat")
    beat.start()
    q, sink = queue.Queue(maxsize=100), []
    w = threading.Thread(target=writer, args=(q, sink), name="writer")
    w.start()
    urls = [f"https://docs.example/{i}" for i in range(40)]
    token = request_id.set("job-7")
    try:
        with ThreadPoolExecutor(max_workers=8, thread_name_prefix="fetch") as ex:
            pages = {ex.submit(fetch, u): u for u in urls}
            for fut in as_completed(pages, timeout=60):
                try:
                    q.put((pages[fut], len(fut.result())))
                except Exception as exc:
                    log.warning("fetch %s failed: %r", pages[fut], exc)
            vectors = embed_window(iter_chunks(200), ex)
            lengths = list(ex.map(len, urls))
            upsert = ex.submit(len, vectors)
            upsert.add_done_callback(on_done)
        answers = handle_query(IO_POOL, urls[:5])
    except KeyboardInterrupt:
        stop.set()
        IO_POOL.shutdown(wait=False, cancel_futures=True)
        raise
    finally:
        request_id.reset(token)
        q.put(None)
        w.join()
        stop.set()
        beat.join(timeout=1)
    if sys.version_info >= (3, 14):
        with ThreadPoolExecutor(max_workers=4) as ex:
            total = sum(ex.map(len, iter_chunks(50), buffersize=8))
    else:
        total = sum(len(c) for c in iter_chunks(50))
    print(f"pages={len(sink)} vectors={len(vectors)} lengths={sum(lengths)} answers={len(answers)} "
          f"upsert={upsert.result()} stats={STATS} total={total} context={vectors[0][1][1] == len('job-7')}")


if __name__ == "__main__":
    main()
