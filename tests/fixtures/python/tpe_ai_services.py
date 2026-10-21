"""Fixture for executor_tool.py check: thread-pool bugs in AI-engineering code. Never run this file."""
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from fastapi import FastAPI

app = FastAPI()


def embed_texts(session, texts):
    return session.post("https://api.example/embed", json={"input": texts}, timeout=30).json()


def call_tool(name, args):
    return {"tool": name, "args": args}


def list_s3_keys(bucket):
    for i in range(1_000_000):
        yield f"{bucket}/chunk-{i}.json"


def upload_chunk(key):
    return key


@app.post("/rag/answer")
def answer(question: str):
    pool = ThreadPoolExecutor(max_workers=4)                         # TPE016 per request
    futures = [pool.submit(call_tool, t, question) for t in ("search", "sql")]
    out = [f.result() for f in futures]                              # TPE011 no timeout
    pool.shutdown()
    return out


def embed_corpus(batches):
    session = requests.Session()                                     # TPE008 shared via submit args
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = {ex.submit(embed_texts, session, b): i for i, b in enumerate(batches)}
        return {futs[f]: f.result() for f in as_completed(futs)}


def upload_all(bucket):
    with ThreadPoolExecutor(max_workers=32) as ex:
        futures = [ex.submit(upload_chunk, k) for k in list_s3_keys(bucket)]   # TPE003 comprehension
        return [f.result() for f in futures]


def cache_answers(rows):
    conn = sqlite3.connect("answers.db")                             # TPE008 closure capture

    def save(row):
        conn.execute("INSERT INTO answers VALUES (?)", (row,))

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(save, rows))


def process_doc(ex, doc):
    pages = [ex.submit(call_tool, "ocr", p) for p in doc]           # TPE009 via executor argument
    return [p.result() for p in pages]


def ingest(docs):
    with ThreadPoolExecutor(max_workers=4) as ex:
        return [f.result() for f in [ex.submit(process_doc, ex, d) for d in docs]]


def run_agent_step(calls):
    with ThreadPoolExecutor(max_workers=8) as inner:                 # TPE016 executor inside a task
        return list(inner.map(call_tool, calls, calls))


def agent_loop(steps):
    with ThreadPoolExecutor(max_workers=4) as ex:
        return [f.result() for f in [ex.submit(run_agent_step, s) for s in steps]]


def warm_cache(keys):
    threading.Thread(target=upload_chunk, args=(keys[0],)).start()   # TPE017 never joinable
