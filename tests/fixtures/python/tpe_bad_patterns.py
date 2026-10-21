"""Fixture for executor_tool.py check: every TPE rule fires at least once. Never run this file."""
import concurrent.futures as cf
import contextvars
import json
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

SESSION = requests.Session()                                     # TPE008 shared Session
DB = sqlite3.connect("cache.db")                                 # TPE008 shared sqlite3 connection
EXECUTOR = ThreadPoolExecutor(max_workers=200)                   # TPE002 never shut down, TPE010 > 64
TOKEN_TOTAL = 0
RESULTS = []
CACHE = {}
request_id = contextvars.ContextVar("request_id", default="-")


def fetch_page(url):
    return SESSION.get(url, timeout=10).text


def store_embedding(doc_id, vector):
    DB.execute("INSERT INTO vectors VALUES (?, ?)", (doc_id, json.dumps(vector)))


def count_tokens(text):
    global TOKEN_TOTAL
    TOKEN_TOTAL += len(text.split())                             # TPE006 read-modify-write
    RESULTS.append(text[:20])                                    # TPE007 shared append


def cached_embed(text):
    if text not in CACHE:
        CACHE[text] = [0.0] * 8                                  # TPE006 check-then-set
    return CACHE[text]


def call_llm(prompt):
    return f"answer to {prompt}"


def traced_call(prompt):
    return f"[{request_id.get()}] {prompt}"                      # read by TPE019


def score(n):
    total = 0
    for i in range(n):
        total += i * i % 7
    return total


def summarize_doc(doc):
    chunks = doc.split("\n\n")
    futs = [EXECUTOR.submit(call_llm, c) for c in chunks]
    return [f.result() for f in futs]                            # TPE009 waits on own executor


def write_jsonl(path, rows):
    with open(path, "w") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def crawl(urls):
    for u in urls:
        fetch_page(u)


def fire_and_forget(urls):
    with ThreadPoolExecutor(max_workers=8) as ex:
        for u in urls:
            ex.submit(fetch_page, u)                             # TPE001 future dropped
        last = None
        for u in urls:
            last = ex.submit(fetch_page, u)                      # TPE001 only last future kept
        last.result()
        cb = ex.submit(store_embedding, "d1", [0.1])
        cb.add_done_callback(lambda f: print("done"))            # TPE001 callback never reads it


def leaky(prompts):
    ex = cf.ThreadPoolExecutor(max_workers=1)                    # TPE002 no shutdown, TPE010 serial
    return [f.result() for f in [ex.submit(call_llm, p) for p in prompts]]


def unbounded(path):
    with ThreadPoolExecutor(max_workers=16) as ex:
        futures = []
        for line in open(path):                                  # whole file queued at once
            futures.append(ex.submit(call_llm, line))            # TPE003
        return [f.result() for f in futures]


def eager_map(path):
    with ThreadPoolExecutor(max_workers=16) as ex:
        return list(ex.map(call_llm, (line.strip() for line in open(path))))   # TPE004


def map_dropped(docs):
    with ThreadPoolExecutor(max_workers=16) as ex:
        ex.map(count_tokens, docs)                               # TPE005 never iterated
        ex.map(cached_embed, docs)                               # TPE005
        upserts = ex.map(store_embedding, docs, docs, timeout=30)
    for _ in upserts:                                            # TPE005 timeout after the with block
        pass


def handle_search(queries):
    pending = [EXECUTOR.submit(call_llm, q) for q in queries]
    return [p.result() for p in pending]                         # TPE011 no timeout in handler


def main():
    ex = ThreadPoolExecutor(max_workers=8)
    futs = [ex.submit(crawl, ["https://a"]), EXECUTOR.submit(summarize_doc, "a\n\nb")]
    try:
        while not all(f.done() for f in futs):                   # TPE014 polling
            time.sleep(0.5)
        for f in futs:
            try:
                f.result()
            except Exception:                                    # TPE015 swallowed
                pass
    except KeyboardInterrupt:
        ex.shutdown(wait=False)                                  # TPE012 no cancel_futures


def per_batch(batches):
    out = []
    for batch in batches:
        with ThreadPoolExecutor(max_workers=8) as ex:            # TPE016 executor per loop iteration
            out.extend(ex.map(call_llm, batch))
    return out


def background_jobs(rows):
    writer = threading.Thread(target=write_jsonl, args=("out.jsonl", rows), daemon=True)   # TPE013
    writer.start()
    worker = threading.Thread(target=crawl, args=(["https://b"],))                         # TPE017
    worker.start()


def cpu_in_threads():
    with ThreadPoolExecutor(max_workers=8) as ex:
        return list(ex.map(score, [10_000] * 8))                 # TPE018 GIL-bound


def traced(prompts):
    request_id.set("req-42")
    with ThreadPoolExecutor(max_workers=4) as ex:
        return [f.result() for f in [ex.submit(traced_call, p) for p in prompts]]   # TPE019

