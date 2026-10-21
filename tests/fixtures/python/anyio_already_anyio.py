"""LLM fan-out already written with AnyIO: runs on asyncio or trio.

Fixture for migrate_async.py: no asyncio usage, so `--check` passes (exit 0).
"""
import functools
import random

import anyio
from anyio.streams.memory import MemoryObjectSendStream


async def fake_llm(prompt: str, *, temperature: float = 0.0) -> str:
    await anyio.sleep(random.uniform(0.001, 0.01))
    return f"answer({prompt}, t={temperature})"


def count_tokens(text: str) -> int:
    return len(text.split())


async def run_one(limiter: anyio.CapacityLimiter, index: int, prompt: str,
                  results: list, send: MemoryObjectSendStream) -> None:
    async with limiter, send:
        try:
            with anyio.fail_after(2):
                text = await fake_llm(prompt, temperature=0.2)
        except TimeoutError as exc:
            results[index] = exc
            return
        except anyio.get_cancelled_exc_class():
            with anyio.CancelScope(shield=True), anyio.move_on_after(1):
                await anyio.sleep(0)  # e.g. release a pooled connection
            raise
        results[index] = text
        await send.send((index, await anyio.to_thread.run_sync(count_tokens, text)))


async def main(prompts: list) -> list:
    limiter = anyio.CapacityLimiter(4)
    results: list = [None] * len(prompts)
    send, receive = anyio.create_memory_object_stream[tuple](max_buffer_size=8)
    async with anyio.create_task_group() as tg:
        async with send:
            for i, prompt in enumerate(prompts):
                tg.start_soon(run_one, limiter, i, prompt, results, send.clone(), name=f"llm-{i}")
        async with receive:
            tokens = sum([n async for _, n in receive])
    print("tokens:", tokens)
    return results


if __name__ == "__main__":
    out = anyio.run(functools.partial(main, [f"q{i}" for i in range(10)]), backend="asyncio")
    print(len(out), out[0])
