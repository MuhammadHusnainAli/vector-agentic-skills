"""Fixture for pool_tool.py check: correct process-pool patterns, zero findings.

Runnable (stdlib only, ~1 s): python3 tests/fixtures/python/mp_clean_pipeline.py
A toy RAG ingestion job: chunk documents, hash shingles for dedup, score with a
per-worker "model", and sum a shared numpy-free array via shared_memory.
"""
import concurrent.futures
import functools
import hashlib
import logging
import logging.handlers
import multiprocessing
import os
import random
import signal
import struct
import sys
from multiprocessing import shared_memory

log = logging.getLogger("ingest")
_vocab = None          # per-worker state, set by the initializer
_seed_base = 0


def init_worker(vocab_words, seed_base, log_queue):
    """Runs once per worker: ignore Ctrl-C, route logs to the parent, load heavy state."""
    global _vocab, _seed_base
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    root = logging.getLogger()
    root.handlers[:] = [logging.handlers.QueueHandler(log_queue)]
    root.setLevel(logging.INFO)
    _vocab = {w: i for i, w in enumerate(vocab_words)}
    _seed_base = seed_base


def chunk_doc(doc, *, size):
    words = doc.split()
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size)]


def encode(chunk):
    rng = random.Random(_seed_base + int(hashlib.blake2b(chunk.encode(), digest_size=4).hexdigest(), 16))
    ids = [_vocab.get(w, 0) for w in chunk.split()]
    return ids, rng.random()


def shingle_hashes(chunk, k=3):
    words = chunk.split()
    grams = {" ".join(words[i:i + k]) for i in range(max(1, len(words) - k + 1))}
    return min(int(hashlib.blake2b(g.encode(), digest_size=8).hexdigest(), 16) for g in grams)


def sum_slice(shm_name, start, stop):
    shm = shared_memory.SharedMemory(name=shm_name)
    try:
        values = struct.unpack_from(f"{stop - start}d", shm.buf, start * 8)
        return sum(values)
    finally:
        shm.close()


def on_error(exc):
    log.error("task failed: %r", exc)


def make_docs(n):
    rng = random.Random(0)
    words = [f"w{i}" for i in range(200)]
    return [" ".join(rng.choice(words) for _ in range(120)) for _ in range(n)]


def run(n_docs, workers):
    ctx = multiprocessing.get_context("spawn")
    docs = make_docs(n_docs)
    vocab = [f"w{i}" for i in range(200)]
    log_queue = ctx.Queue()
    listener = logging.handlers.QueueListener(log_queue, logging.StreamHandler(sys.stderr))
    listener.start()
    try:
        with ctx.Pool(workers, initializer=init_worker, initargs=(vocab, 1234, log_queue),
                      maxtasksperchild=1000) as pool:
            chunker = functools.partial(chunk_doc, size=40)
            chunks = [c for part in pool.imap(chunker, docs, chunksize=8) for c in part]
            pending = pool.map_async(encode, chunks, chunksize=16, error_callback=on_error)
            encoded = pending.get(timeout=120)
            signatures = pool.map(shingle_hashes, chunks)
            pool.close()
            pool.join()
    except KeyboardInterrupt:
        log.warning("interrupted; pool terminated")
        raise
    finally:
        listener.stop()

    data = [float(i) for i in range(10_000)]
    shm = shared_memory.SharedMemory(create=True, size=len(data) * 8)
    try:
        struct.pack_into(f"{len(data)}d", shm.buf, 0, *data)
        bounds = [(i, min(i + 2500, len(data))) for i in range(0, len(data), 2500)]
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as ex:
            futures = [ex.submit(sum_slice, shm.name, a, b) for a, b in bounds]
            total = 0.0
            for fut in concurrent.futures.as_completed(futures, timeout=120):
                total += fut.result()
    finally:
        shm.close()
        shm.unlink()
    unique = len(set(signatures))
    return len(chunks), len(encoded), unique, total


def main():
    workers = min(4, os.cpu_count() or 1)
    n_chunks, n_encoded, unique, total = run(n_docs=40, workers=workers)
    print(f"chunks={n_chunks} encoded={n_encoded} unique={unique} total={total:.0f}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
