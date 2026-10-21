"""RAG ingestion + serving code with asyncio mistakes. Every AIO rule fires here (default --target-version 3.11)."""

import asyncio
import queue
import socket
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

import aiohttp
import httpx
import requests
from fastapi import FastAPI
from openai import OpenAI

app = FastAPI()
sync_llm = OpenAI()
cache_lock = threading.Lock()
work_queue = asyncio.Queue()  # AIO021: no maxsize, producers never block


async def embed(text: str) -> list[float]:
    async with httpx.AsyncClient() as http:
        resp = await http.post("http://embedder/embed", json={"text": text})
        return resp.json()["vector"]


async def call_llm(prompt: str) -> str:
    time.sleep(0.5)  # AIO001: crude rate limit
    resp = requests.post("http://llm/v1/complete", json={"prompt": prompt})  # AIO002
    return resp.json()["text"]


async def summarize_with_sync_sdk(text: str) -> str:
    out = sync_llm.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": text}])  # AIO002
    return out.choices[0].message.content


async def convert_pdf(path: str) -> str:
    subprocess.run(["pdftotext", path, "out.txt"], check=True)  # AIO003
    return Path("out.txt").read_text()  # AIO004


async def load_prompt_template() -> str:
    with open("prompts/system.txt") as fh:  # AIO004
        return fh.read()


async def lookup_doc(doc_id: str):
    conn = sqlite3.connect("docs.db")  # AIO005
    row = conn.execute("SELECT body FROM docs WHERE id = ?", (doc_id,)).fetchone()  # AIO005
    return row


async def read_feed(host: str) -> bytes:
    sock = socket.create_connection((host, 9000))  # AIO006
    return sock.recv(4096)  # AIO006


async def ask_operator() -> str:
    return input("approve? ")  # AIO006


async def ingest(docs: list[str]) -> None:
    embed(docs[0])  # AIO007: coroutine never awaited
    asyncio.sleep(1)  # AIO007
    asyncio.create_task(embed(docs[1]))  # AIO008: fire-and-forget, no reference
    warmup = asyncio.create_task(embed("warmup"))  # AIO020: never awaited or stored
    vectors = await asyncio.gather(*[embed(d) for d in docs])  # AIO012: unbounded fan-out
    print(len(vectors))


def helper_called_from_async() -> None:
    loop = asyncio.get_event_loop()  # AIO010
    loop.run_forever()


async def run_eval(prompts: list[str]) -> list[str]:
    answers = asyncio.run(call_llm(prompts[0]))  # AIO009
    loop = asyncio.get_running_loop()
    more = loop.run_until_complete(call_llm(prompts[1]))  # AIO011
    return [answers, more]


async def score_all(prompts: list[str]) -> list[str]:
    results = []
    for p in prompts:
        answer = await call_llm(p)  # AIO013: sequential over independent prompts
        results.append(answer)
    return results


async def stream_tokens(prompt: str):
    try:
        async with httpx.AsyncClient() as http:
            async with http.stream("POST", "http://llm/stream", json={"prompt": prompt}) as resp:
                async for line in resp.aiter_lines():
                    yield line
    except BaseException:  # AIO014: swallows CancelledError
        yield "[stream aborted]"


async def bounded_call(prompt: str) -> str:
    return await asyncio.wait_for(call_llm(prompt), timeout=30)  # AIO015 (3.11+ target)


async def update_cache(key: str, value: str) -> None:
    with cache_lock:  # AIO016: threading.Lock held across await
        await asyncio.sleep(0.01)
    lock = threading.Lock()  # AIO016: thread lock created in async code
    results: queue.Queue = queue.Queue()
    first = results.get()  # AIO016: blocks the loop until a thread puts something
    print(lock, first)


async def build_prompt(question: str, context: str) -> str:  # AIO017: never awaits
    return f"Context:\n{context}\n\nQuestion: {question}"


async def wait_for_index(state: dict) -> None:
    while not state.get("ready"):
        await asyncio.sleep(0)  # AIO018: busy wait


async def fetch_page(url: str) -> str:
    session = aiohttp.ClientSession()  # AIO019: never closed
    async with session.get(url) as resp:
        return await resp.text()


async def scrape(urls: list[str]) -> list[str]:
    pages = await asyncio.gather(*(fetch_page(u) for u in urls[:10]), return_exceptions=True)  # AIO022
    return [p.upper() for p in pages]


async def producer(paths: list[str]) -> None:
    for path in paths:
        await work_queue.put(path)


@app.post("/summarize")
def summarize_route(text: str) -> dict:
    summary = asyncio.run(call_llm(text))  # AIO023
    return {"summary": summary}


async def main() -> None:
    loop = asyncio.get_running_loop()
    loop.set_task_factory(asyncio.eager_task_factory)  # AIO024: 3.12+, target is 3.11
    await ingest(["a", "b"])
