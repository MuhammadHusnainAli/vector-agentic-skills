"""Embedding batch job written for asyncio (Python 3.11+).

Fixture for migrate_async.py: every asyncio usage here has an exact, automatic
anyio/trio rewrite, so `--write` succeeds without --force. Tests must use
--diff (never --write) so this committed file stays unchanged.
"""
import asyncio
import hashlib


class FakeEmbedder:
    def __init__(self, limit: int) -> None:
        self.sem = asyncio.Semaphore(value=limit)
        self.burst = asyncio.BoundedSemaphore(2)
        self.lock: asyncio.Lock = asyncio.Lock()
        self.calls = 0

    async def embed(self, text: str) -> str:
        async with self.sem, self.burst:
            await asyncio.sleep(0.01)
            async with self.lock:
                self.calls += 1
            return hashlib.sha256(text.encode()).hexdigest()[:8]


def chunk(text: str, *, size: int) -> list:
    return [text[i:i + size] for i in range(0, len(text), size)]


async def embed_doc(embedder: FakeEmbedder, doc_id: str, text: str, out: dict, *, size: int = 16) -> None:
    pieces = await asyncio.to_thread(chunk, text, size=size)
    out[doc_id] = [await embedder.embed(piece) for piece in pieces]


async def slow_rerank() -> None:
    try:
        await asyncio.sleep(10)
    except asyncio.CancelledError:
        print("rerank cancelled")
        raise


async def main(docs: dict, limit: int) -> None:
    embedder = FakeEmbedder(limit)
    done = asyncio.Event()
    cond = asyncio.Condition()
    out: dict = {}
    async with asyncio.TaskGroup() as tg:
        for doc_id, text in docs.items():
            tg.create_task(embed_doc(embedder, doc_id, text, out, size=12), name=f"embed-{doc_id}")
        tg.create_task(asyncio.sleep(0))
    done.set()
    try:
        async with asyncio.timeout(0.05):
            await slow_rerank()
    except asyncio.TimeoutError:
        print("rerank timed out")
    async with cond:
        cond.notify_all()
    await done.wait()
    for doc_id in sorted(out):
        print(doc_id, len(out[doc_id]), out[doc_id][0])
    print("embed calls:", embedder.calls)


if __name__ == "__main__":
    asyncio.run(main({"a": "x" * 40, "b": "retrieval augmented generation"}, 4))
