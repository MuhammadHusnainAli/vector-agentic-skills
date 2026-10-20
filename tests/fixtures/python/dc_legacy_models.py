"""Hand-written data classes from an LLM/RAG codebase, used to test to_dataclass.py.

Nothing here is executed by the tool; it only parses the file.
"""
import os
from dataclasses import dataclass
from functools import total_ordering
from typing import Any, Dict, List, Optional

import numpy as np


class ChatMessage:
    """One turn of a chat transcript."""

    def __init__(self, role: str, content: str, name: Optional[str] = None,
                 tool_calls: Optional[List[Dict[str, Any]]] = None):
        self.role = role
        self.content = content
        self.name = name
        self.tool_calls = tool_calls or []

    def __repr__(self):
        return f"ChatMessage(role={self.role!r}, content={self.content!r}, name={self.name!r}, tool_calls={self.tool_calls!r})"

    def __eq__(self, other):
        if not isinstance(other, ChatMessage):
            return NotImplemented
        return (self.role, self.content, self.name, self.tool_calls) == (
            other.role, other.content, other.name, other.tool_calls)

    def to_openai(self) -> dict:
        msg = {"role": self.role, "content": self.content}
        if self.name:
            msg["name"] = self.name
        return msg


class GenerationConfig:
    def __init__(self, model, temperature=0.7, max_tokens=1024, stop=[], *, seed=None):
        if not 0.0 <= temperature <= 2.0:
            raise ValueError(f"temperature must be in [0, 2], got {temperature}")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.stop = stop
        self.seed = seed

    def __eq__(self, other):
        return (self.model, self.temperature, self.max_tokens, self.stop, self.seed) == (
            other.model, other.temperature, other.max_tokens, other.stop, other.seed)

    def __hash__(self):
        return hash((self.model, self.temperature, self.max_tokens))


class RetrievedChunk:
    def __init__(self, chunk_id: str, text: str, embedding: np.ndarray, score: float = 0.0,
                 metadata: Optional[dict] = None):
        if metadata is None:
            metadata = {}
        self.chunk_id = chunk_id
        self.text = text
        self.embedding = embedding
        self.score = score
        self.metadata = metadata

    def __lt__(self, other):
        return self.score < other.score


class LLMClient:
    __slots__ = ("model", "timeout", "api_key", "_session")

    def __init__(self, model: str, api_key_env: str = "OPENAI_API_KEY", timeout: float = 30.0):
        self.model = model
        self.timeout = timeout
        self.api_key = os.environ.get(api_key_env, "")
        self._session = None

    def __repr__(self):
        return f"LLMClient(model={self.model!r}, timeout={self.timeout})"

    def complete(self, prompt: str) -> str:
        raise NotImplementedError


@total_ordering
class EvalResult:
    max_score: float = 1.0

    def __init__(self, example_id: str, metric: str, score: float):
        self.example_id = example_id
        self.metric = metric
        self.score = score

    def __eq__(self, other):
        return (self.example_id, self.metric, self.score) == (other.example_id, other.metric, other.score)

    def __lt__(self, other):
        return (self.example_id, self.metric, self.score) < (other.example_id, other.metric, other.score)


class StreamingHandler:
    def __init__(self, *callbacks):
        self.callbacks = list(callbacks)


class RateLimitError(Exception):
    def __init__(self, retry_after: float):
        self.retry_after = retry_after


class AnthropicClient(LLMClient):
    def __init__(self, model: str, max_retries: int = 3):
        super().__init__(model, api_key_env="ANTHROPIC_API_KEY")
        self.max_retries = max_retries


@dataclass
class ToolSpec:
    name: str
    description: str


class VectorStoreAdapter:
    def __init__(self, client):
        self._client = client
