"""Fixture: an asyncio lock-order deadlock between two tasks. THIS PROGRAM HANGS FOREVER.

An agent keeps a vector-index lock and a conversation-memory lock. `index_then_memory` takes
index -> memory, `memory_then_index` takes memory -> index; both yield in between, so each task
ends up holding one lock and awaiting the other. Run it only under a watchdog:

    python hang_watchdog.py --dump-after 1 --kill-after 3 dead_async_lock_order.py
"""

import asyncio

index_lock = asyncio.Lock()
memory_lock = asyncio.Lock()


async def index_then_memory():
    async with index_lock:
        await asyncio.sleep(0.05)  # e.g. awaiting an embedding call
        async with memory_lock:
            print("upserted and remembered")


async def memory_then_index():
    async with memory_lock:
        await asyncio.sleep(0.05)  # e.g. awaiting a summarisation call
        async with index_lock:
            print("summarised and indexed")


async def main():
    print("agent started", flush=True)
    await asyncio.gather(
        asyncio.create_task(index_then_memory(), name="upsert-task"),
        asyncio.create_task(memory_then_index(), name="summarise-task"),
    )


if __name__ == "__main__":
    asyncio.run(main())
