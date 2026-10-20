"""Pre-3.10 typing in a RAG module: annotation_audit should suggest modern rewrites."""
from typing import Any, Callable, Dict, Generic, List, Optional, Tuple, TypeVar, Union

from typing_extensions import Literal, Protocol, TypeAlias

T = TypeVar("T")
Role = Literal["system", "user", "assistant", "tool"]
Message: TypeAlias = Dict[str, Union[str, List[Dict[str, Any]]]]
Embedding = List[float]


class Retriever(Protocol):
    def search(self, query: str, k: int) -> List[Tuple[str, float]]: ...


class Cache(Generic[T]):
    def get(self, key: str) -> Optional[T]:
        return None


def call_llm(
    messages: List[Message],
    tools: Optional[List[Dict[str, Any]]] = None,
    temperature: float = "0.7",
    stop: List[str] = None,
    on_token: Callable[[str], None] = None,
) -> Union[str, Dict[str, Any]]:
    return ""


def rerank(results: List[Tuple[str, float]], top_k: int = 5, seen: set = set()) -> List[str]:
    return [doc for doc, _ in sorted(results, key=lambda r: r[1], reverse=True)[:top_k]]
