"""Well-behaved asyncio RAG service: bounded fan-out, owned tasks, timeouts, clean shutdown. Zero AIO findings."""

import asyncio
import logging
import random
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TypeVar

import httpx
from fastapi import FastAPI, Request

T = TypeVar("T")
logger = logging.getLogger(__name__)
MAX_CONCURRENCY = 16


class TokenBucket:
    """Async token bucket: `rate` tokens per second, bursts up to `capacity`."""

    def __init__(self, rate: float, capacity: float) -> None:
        self.rate, self.capacity = rate, capacity
        self.tokens = capacity
        self.updated = 0.0
        self.lock = asyncio.Lock()

    async def acquire(self, cost: float = 1.0) -> None:
        loop = asyncio.get_running_loop()
        async with self.lock:
            while True:
                now = loop.time()
                self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
                self.updated = now
                if self.tokens >= cost:
                    self.tokens -= cost
                    return
                await asyncio.sleep((cost - self.tokens) / self.rate)


async def with_retry(call: Callable[[], Awaitable[T]], attempts: int = 5, base: float = 0.5) -> T:
    for attempt in range(attempts):
        try:
            return await call()
        except (httpx.TimeoutException, httpx.ConnectError):
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(random.uniform(0, base * 2 ** attempt))
    raise AssertionError("unreachable")


async def embed_one(http: httpx.AsyncClient, sem: asyncio.Semaphore, bucket: TokenBucket, text: str) -> list[float]:
    async with sem:
        await bucket.acquire()
        async with asyncio.timeout(30):
            resp = await with_retry(lambda: http.post("/embed", json={"text": text}))
        resp.raise_for_status()
        return resp.json()["vector"]


async def embed_all(http: httpx.AsyncClient, texts: list[str]) -> list[list[float]]:
    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    bucket = TokenBucket(rate=50, capacity=50)
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(embed_one(http, sem, bucket, t)) for t in texts]
    return [t.result() for t in tasks]


async def read_corpus(paths: list[Path]) -> list[str]:
    return await asyncio.gather(*(asyncio.to_thread(p.read_text, encoding="utf-8") for p in paths[:8]))


async def pipeline(paths: list[str], http: httpx.AsyncClient, n_workers: int = 4) -> int:
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=2 * n_workers)
    done = 0

    async def worker() -> None:
        nonlocal done
        while True:
            path = await queue.get()
            try:
                text = await asyncio.to_thread(Path(path).read_text, encoding="utf-8")
                await embed_all(http, [text])
                done += 1
            except Exception:
                logger.exception("failed to ingest %s", path)
            finally:
                queue.task_done()

    async with asyncio.TaskGroup() as tg:
        workers = [tg.create_task(worker()) for _ in range(n_workers)]
        for path in paths:
            await queue.put(path)
        await queue.join()
        for w in workers:
            w.cancel()
    return done


async def score_batch(http: httpx.AsyncClient, prompts: list[str]) -> list[str]:
    results = await asyncio.gather(*(complete(http, p) for p in prompts[:4]), return_exceptions=True)
    answers = []
    for prompt, result in zip(prompts, results):
        if isinstance(result, BaseException):
            logger.error("prompt failed: %s", prompt[:40], exc_info=result)
            continue
        answers.append(result)
    return answers


async def complete(http: httpx.AsyncClient, prompt: str) -> str:
    resp = await http.post("/complete", json={"prompt": prompt})
    return resp.json()["text"]


async def stream_tokens(http: httpx.AsyncClient, prompt: str) -> AsyncIterator[str]:
    try:
        async with http.stream("POST", "/stream", json={"prompt": prompt}) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    yield line[6:]
    except asyncio.CancelledError:
        logger.info("client disconnected mid-stream")
        raise


background_tasks: set[asyncio.Task[None]] = set()


async def log_usage(event: dict) -> None:
    await asyncio.sleep(0)
    logger.info("usage %s", event)


def record_usage(event: dict) -> None:
    task = asyncio.create_task(log_usage(event))
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.http = httpx.AsyncClient(base_url="http://llm", timeout=30)
    try:
        yield
    finally:
        await app.state.http.aclose()


app = FastAPI(lifespan=lifespan)


@app.post("/answer")
async def answer(request: Request, question: str) -> dict:
    text = await complete(request.app.state.http, question)
    record_usage({"chars": len(text)})
    return {"answer": text}


async def main() -> None:
    async with httpx.AsyncClient(base_url="http://embedder") as http:
        vectors = await embed_all(http, ["hello", "world"])
        logger.info("embedded %d", len(vectors))


if __name__ == "__main__":
    asyncio.run(main())
