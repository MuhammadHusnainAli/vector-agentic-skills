"""Deterministic CPU-heavy RAG preprocessing workload used to generate gil_profile_sample.prof.

Regenerate the committed profile (pstats files are tied to the Python version that wrote them):
    python -m cProfile -o tests/fixtures/python/gil_profile_sample.prof tests/fixtures/python/gil_workload.py
Then classify it:
    python skills/programming/python/python-gil-bottleneck-analyzer/scripts/profile_classify.py \
        tests/fixtures/python/gil_profile_sample.prof
"""

import hashlib
import json
import math
import re
import time

WS = re.compile(r"\s+")
BOILERPLATE = re.compile(r"(cookie policy|subscribe now|all rights reserved)", re.I)


def make_corpus(n_docs):
    words = ["retrieval", "augmented", "generation", "embedding", "vector", "token", "model", "latency"]
    return [
        "  ".join(words[(i * 7 + j) % len(words)] for j in range(400)) + " Subscribe now! All rights reserved."
        for i in range(n_docs)
    ]


def clean(doc):
    return WS.sub(" ", BOILERPLATE.sub("", doc)).strip()


def chunk(text, size=64, overlap=16):
    tokens = text.split(" ")
    out = []
    start = 0
    while start < len(tokens):
        out.append(" ".join(tokens[start:start + size]))
        start += size - overlap
    return out


def embed(text, dim=32):
    # toy hashing "embedding" in pure Python: the kind of loop that holds the GIL
    vec = [0.0] * dim
    for tok in text.split(" "):
        h = 0
        for ch in tok:
            h = (h * 31 + ord(ch)) & 0xFFFFFFFF
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def rerank(query_vec, vecs, k=5):
    scores = [sum(a * b for a, b in zip(query_vec, v)) for v in vecs]
    return sorted(range(len(vecs)), key=scores.__getitem__, reverse=True)[:k]


def parse_model_outputs(n):
    raw = [json.dumps({"id": i, "answer": "ok " * 20, "citations": list(range(10))}) for i in range(n)]
    return [json.loads(r) for r in raw]


def fake_llm_call():
    time.sleep(0.02)  # stands in for network latency


def main():
    docs = [clean(d) for d in make_corpus(60)]
    chunks = [c for d in docs for c in chunk(d)]
    seen = {hashlib.sha256(c.encode()).hexdigest() for c in chunks}
    vecs = [embed(c) for c in chunks]
    top = rerank(embed("vector retrieval latency"), vecs)
    outputs = parse_model_outputs(2000)
    fake_llm_call()
    return len(seen), top, len(outputs)


if __name__ == "__main__":
    print(main())
