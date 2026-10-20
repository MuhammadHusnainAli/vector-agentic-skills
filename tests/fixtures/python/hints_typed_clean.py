"""Fully annotated modern code (3.12): annotation_audit --strict should pass."""
from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Literal, NotRequired, Protocol, Self, TypedDict

type Role = Literal["system", "user", "assistant", "tool"]


class ChatMessage(TypedDict):
    role: Role
    content: str
    name: NotRequired[str]


class VectorStore[T](Protocol):
    def add(self, ids: Sequence[str], vectors: Sequence[list[float]], payloads: Sequence[T]) -> None: ...
    def search(self, vector: list[float], k: int = 5) -> list[tuple[T, float]]: ...


class PromptBuilder:
    def __init__(self, system: str) -> None:
        self.messages: list[ChatMessage] = [{"role": "system", "content": system}]

    def user(self, content: str) -> Self:
        self.messages.append({"role": "user", "content": content})
        return self


async def stream_completion(prompt: str, chunk_size: int = 16) -> AsyncIterator[str]:
    for i in range(0, len(prompt), chunk_size):
        yield prompt[i:i + chunk_size]


def first[T](items: Sequence[T], default: T | None = None) -> T | None:
    return items[0] if items else default
