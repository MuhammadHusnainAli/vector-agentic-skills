"""An async LLM fan-out with a few advanced features."""
import asyncio
from dataclasses import dataclass


@dataclass
class Message:
    role: str
    content: str


class RateLimitError(Exception):
    pass


def retry(times=3):
    def wrap(fn):
        async def inner(*args, **kwargs):
            for attempt in range(times):
                try:
                    return await fn(*args, **kwargs)
                except RateLimitError as e:
                    last = e
            raise RuntimeError("gave up") from last
        return inner
    return wrap


@retry(times=2)
async def call_model(msg: Message) -> str:
    await asyncio.sleep(0)
    return msg.content.upper()


def chunks(text, size):
    for start in range(0, len(text), size):
        yield text[start:start + size]


async def main():
    msgs = [Message("user", c) for c in chunks("hello world", 4)]
    results = await asyncio.gather(*(call_model(m) for m in msgs))
    if (n := len(results)) > 1:
        match results:
            case [first, *rest]:
                print(first, n, rest)
    return {r: len(r) for r in results}


if __name__ == "__main__":
    print(asyncio.run(main()))
