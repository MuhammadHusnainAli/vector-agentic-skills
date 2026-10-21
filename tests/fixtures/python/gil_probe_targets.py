"""Target functions for gil_probe.py --target tests (AI-preprocessing flavoured, stdlib only)."""

import hashlib
import time

WORDS = ["retrieval", "augmented", "generation", "embedding", "vector", "token", "model", "latency"]


def count_wordpieces(n_docs=40):
    """Pure-Python tokenizer-style loop: holds the GIL, so threads do not help."""
    total = 0
    for i in range(n_docs):
        text = " ".join(WORDS[(i + j) % len(WORDS)] for j in range(2000))
        for word in text.split():
            total += sum(1 for k in range(0, len(word), 3))
    return total


def fingerprint_shards(n_shards=60):
    """sha256 over 1 MiB shards (dedup keys): hashlib releases the GIL, so threads scale."""
    shard = bytes(range(256)) * 4096
    return [hashlib.sha256(shard + bytes([i % 256])).hexdigest() for i in range(n_shards)]


def call_model_api(latency_s=0.1):
    """Stands in for an HTTP call to an LLM endpoint: pure waiting."""
    time.sleep(latency_s)
    return {"text": "ok"}


def stuck_worker():
    """Never returns: used to prove --timeout kills everything."""
    while True:
        time.sleep(1)


def broken_parser(payload="{bad json"):
    """Raises, to test error reporting."""
    import json

    return json.loads(payload)
