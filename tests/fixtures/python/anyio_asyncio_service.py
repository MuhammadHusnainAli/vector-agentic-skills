"""RAG answer service written for asyncio (Python 3.11+).

Fixture for migrate_async.py: realistic code with both mechanical and manual
migration items; every MIG rule fires at least once. Never executed by tests.
"""
import asyncio
import json
import signal

from asyncio import CancelledError

RETRIEVERS = ("bm25", "dense", "hybrid")


class LLMClient:
    async def complete(self, prompt: str) -> str:
        await asyncio.sleep(0.05)                                     # MIG003 mechanical
        return f"answer to {prompt}"

    async def aclose(self) -> None:
        return None


class AnswerService:
    def __init__(self) -> None:
        self.client = LLMClient()
        self.lock = asyncio.Lock()                                     # MIG004 mechanical
        self.cache_ready = asyncio.Event()                             # MIG004 manual (clear() below)
        self.jobs = asyncio.Queue(maxsize=100)                         # MIG015
        self.refresher = None

    def invalidate(self) -> None:
        self.cache_ready.clear()

    async def answer(self, question: str) -> str:
        loop = asyncio.get_running_loop()                              # MIG018
        tokens = await loop.run_in_executor(None, len, question)       # MIG017
        try:
            reply = await asyncio.wait_for(self.client.complete(question), timeout=30)   # MIG013
        except asyncio.TimeoutError:                                   # MIG010 mechanical
            return "timeout"
        loop.call_later(60, self.invalidate)                           # MIG019
        return f"{reply} ({tokens} chars)"

    async def fan_out(self, prompts: list) -> list:
        return await asyncio.gather(*(self.client.complete(p) for p in prompts))           # MIG011

    async def eval_batch(self, prompts: list) -> list:
        return await asyncio.gather(*(self.client.complete(p) for p in prompts),           # MIG012
                                    return_exceptions=True)

    async def retrieve_all(self, query: str) -> dict:
        found = {}
        async with asyncio.TaskGroup() as tg:                          # MIG007 + MIG008 mechanical
            for name in RETRIEVERS:
                tg.create_task(self.retrieve(name, query, found))
        return found

    async def retrieve(self, name: str, query: str, found: dict) -> None:
        async with asyncio.timeout(2):                                 # MIG006 mechanical
            await asyncio.sleep(0.01)
        async with self.lock:
            found[name] = [f"{name}:{query}"]

    async def first_retriever(self, query: str) -> str:
        tasks = [asyncio.create_task(self.client.complete(f"{n}:{query}")) for n in RETRIEVERS]  # MIG014
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)        # MIG022
        for t in pending:
            t.cancel()
        return done.pop().result()

    async def stream_results(self, prompts: list) -> None:
        for fut in asyncio.as_completed([self.client.complete(p) for p in prompts]):       # MIG023
            print(await fut)

    async def save(self, record: dict) -> None:
        await asyncio.shield(self.persist(record))                     # MIG024

    async def persist(self, record: dict) -> None:
        payload = await asyncio.to_thread(json.dumps, record, sort_keys=True)   # MIG005 mechanical
        proc = await asyncio.create_subprocess_exec(                   # MIG025
            "gzip", "-c", stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
        await proc.communicate(payload.encode())

    async def health(self, host: str) -> bool:
        reader, writer = await asyncio.open_connection(host, 6333)     # MIG026
        writer.close()
        return reader is not None

    async def worker(self) -> None:
        while True:
            job = await self.jobs.get()
            try:
                await self.answer(job)
            finally:
                self.jobs.task_done()                                  # MIG016

    async def drain(self) -> None:
        await self.jobs.join()                                         # MIG016

    async def start_refresher(self) -> None:
        self.refresher = asyncio.create_task(self.refresh_loop())      # MIG014 stored
        self.refresher.add_done_callback(lambda t: print("refresher stopped"))   # MIG021

    async def stop_refresher(self) -> None:
        self.refresher.cancel()                                        # MIG030

    async def refresh_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(300)
        except CancelledError:                                         # MIG009 mechanical
            await self.client.aclose()
            raise

    async def quiet_shutdown(self) -> None:
        try:
            await self.client.aclose()
        except asyncio.CancelledError:                                 # MIG009 + MIG031
            pass

    async def deadline(self) -> None:
        async with asyncio.timeout(10) as cm:                          # MIG032
            cm.reschedule(asyncio.get_running_loop().time() + 20)

    def future_reply(self) -> asyncio.Future:                          # MIG020
        fut = asyncio.get_running_loop().create_future()
        return fut

    def label(self) -> str:
        task = asyncio.current_task()                                  # MIG029
        return task.get_name() if task else "-"


def is_async_tool(fn) -> bool:
    return asyncio.iscoroutinefunction(fn)                             # MIG033


def submit_from_thread(service: AnswerService, loop, question: str) -> str:
    return asyncio.run_coroutine_threadsafe(service.answer(question), loop).result()   # MIG028


async def main() -> None:
    service = AnswerService()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, service.invalidate)       # MIG027
    barrier = asyncio.Barrier(2)                                       # MIG099
    print(await service.answer("what is RAG?"), barrier.parties)


if __name__ == "__main__":
    asyncio.run(main())                                                # MIG002 mechanical
