# Typing AI and ML Code

Patterns for typing LLM applications, RAG pipelines, agents, tool calling,
evals, numeric code and model services. Examples use 3.12 syntax; replace
`type X = ...` with `X: TypeAlias = ...` and `def f[T]` with a module-level
`TypeVar` for older targets.

## Contents

- [Chat messages](#chat-messages)
- [Tool schemas and tool calls](#tool-schemas-and-tool-calls)
- [pydantic vs TypedDict vs dataclass](#pydantic-vs-typeddict-vs-dataclass)
- [LLM client wrappers: sync, async, streaming](#llm-client-wrappers)
- [Callbacks and hooks](#callbacks-and-hooks)
- [Retry and rate-limit decorators](#retry-and-rate-limit-decorators)
- [Embeddings, vector stores and repositories](#embeddings-vector-stores-and-repositories)
- [RAG pipeline types](#rag-pipeline-types)
- [Arrays and tensors](#arrays-and-tensors)
- [Training and inference loops](#training-and-inference-loops)
- [Typed configuration](#typed-configuration)
- [FastAPI services around models](#fastapi-services-around-models)
- [Untyped AI libraries](#untyped-ai-libraries)

## Chat messages

Provider SDKs accept plain dicts; a `TypedDict` documents and checks the shape
at zero runtime cost.

```python
from typing import Literal, NotRequired, TypedDict

type Role = Literal["system", "user", "assistant", "tool"]

class FunctionCall(TypedDict):
    name: str
    arguments: str                       # JSON string, parse before use

class ToolCall(TypedDict):
    id: str
    type: Literal["function"]
    function: FunctionCall

class ChatMessage(TypedDict):
    role: Role
    content: str | None                  # None for assistant messages that only call tools
    name: NotRequired[str]
    tool_calls: NotRequired[list[ToolCall]]
    tool_call_id: NotRequired[str]       # required when role == "tool"

def system(text: str) -> ChatMessage:
    return {"role": "system", "content": text}

def tool_result(call_id: str, output: str) -> ChatMessage:
    return {"role": "tool", "content": output, "tool_call_id": call_id}
```

A stricter discriminated union makes invalid combinations unrepresentable and
narrows on `role`:

```python
class SystemMessage(TypedDict):
    role: Literal["system"]
    content: str

class UserMessage(TypedDict):
    role: Literal["user"]
    content: str

class AssistantMessage(TypedDict):
    role: Literal["assistant"]
    content: str | None
    tool_calls: NotRequired[list[ToolCall]]

class ToolMessage(TypedDict):
    role: Literal["tool"]
    content: str
    tool_call_id: str

type Message = SystemMessage | UserMessage | AssistantMessage | ToolMessage

def last_text(history: list[Message]) -> str:
    for m in reversed(history):
        if m["role"] == "assistant" and m["content"] is not None:
            return m["content"]                     # narrowed to AssistantMessage, then to str
    return ""
```

Content blocks (Anthropic-style multi-part content) are the same idea:

```python
class TextBlock(TypedDict):
    type: Literal["text"]
    text: str

class ImageSource(TypedDict):
    type: Literal["base64"]
    media_type: Literal["image/png", "image/jpeg", "image/webp", "image/gif"]
    data: str

class ImageBlock(TypedDict):
    type: Literal["image"]
    source: ImageSource

type ContentBlock = TextBlock | ImageBlock

class RichMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str | list[ContentBlock]
```

When the SDK ships its own types (the official `openai` and `anthropic`
packages export TypedDicts such as `ChatCompletionMessageParam` and
`MessageParam`), use them for values you pass to the SDK instead of redefining
them, and keep your own internal types separate.

## Tool schemas and tool calls

```python
import json
from collections.abc import Awaitable, Callable, Mapping
from typing import Literal, NotRequired, TypedDict

type JSON = dict[str, JSON] | list[JSON] | str | int | float | bool | None

class JSONSchema(TypedDict, total=False):
    type: Literal["object", "string", "number", "integer", "boolean", "array", "null"]
    description: str
    properties: dict[str, "JSONSchema"]
    required: list[str]
    items: "JSONSchema"
    enum: list[str | int]

class ToolSpec(TypedDict):
    name: str
    description: str
    input_schema: JSONSchema
    strict: NotRequired[bool]

type ToolFn = Callable[..., Awaitable[str]]

class ToolRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._fns: dict[str, ToolFn] = {}

    def register(self, spec: ToolSpec, fn: ToolFn) -> None:
        self._specs[spec["name"]] = spec
        self._fns[spec["name"]] = fn

    def specs(self) -> list[ToolSpec]:
        return list(self._specs.values())

    async def dispatch(self, name: str, arguments: str) -> str:
        args: object = json.loads(arguments)          # untrusted model output
        if not isinstance(args, dict):
            raise ValueError(f"{name}: arguments must be a JSON object")
        fn = self._fns[name]
        return await fn(**args)
```

Better: derive both the schema and validation from a pydantic model so the
types, the JSON Schema and runtime validation cannot drift apart.

```python
from pydantic import BaseModel, Field

class SearchArgs(BaseModel):
    query: str = Field(description="Full-text query")
    k: int = Field(5, ge=1, le=50)

def to_tool_spec(name: str, description: str, model: type[BaseModel]) -> ToolSpec:
    return {"name": name, "description": description,
            "input_schema": model.model_json_schema()}      # returns dict[str, Any]; fine at this boundary

async def search(args: SearchArgs) -> str:
    return f"top {args.k} for {args.query!r}"

async def run_search(arguments: str) -> str:
    return await search(SearchArgs.model_validate_json(arguments))   # validated + typed
```

## pydantic vs TypedDict vs dataclass

| Criterion | `TypedDict` | `@dataclass` | pydantic `BaseModel` |
|-----------|-------------|--------------|----------------------|
| Runtime object | plain `dict` | class instance | class instance |
| Validation / coercion | none | none | yes (on construction) |
| Cost | zero | low (`slots=True` cheaper) | higher (fast in v2, still more than a dataclass) |
| JSON Schema | no (hand-written) | via pydantic `TypeAdapter` | `model_json_schema()` |
| Pass straight to an SDK expecting dicts | yes | `asdict()` | `model_dump()` |
| Best for | SDK payloads, JSON you build, `**kwargs` | internal domain objects (Chunk, Hit, Usage) | trust boundaries: API requests, LLM structured output, config files, tool arguments |

Rules of thumb:
- Validate once at the edge (pydantic), then pass typed objects inward (dataclasses or the models themselves).
- Never annotate LLM structured output as a TypedDict and trust it: the model can return anything. Parse with pydantic (`Model.model_validate_json(text)`) or `TypeAdapter(MyTypedDict).validate_python(data)`.
- pydantic evaluates annotations at runtime: on 3.9 use `Optional[X]` in models even with `from __future__ import annotations`, and do not hide imports used by model fields behind `TYPE_CHECKING`.

## LLM client wrappers

```python
import asyncio
from collections.abc import AsyncIterator, Iterator, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int
    output_tokens: int

@dataclass(frozen=True, slots=True)
class Completion:
    text: str
    finish_reason: Literal["stop", "length", "tool_calls"]
    usage: Usage

class ChatModel(Protocol):
    """What the rest of the app depends on: any provider, or a fake in tests."""
    def complete(self, messages: Sequence[ChatMessage], *, max_tokens: int = 1024) -> Completion: ...
    def stream(self, messages: Sequence[ChatMessage], *, max_tokens: int = 1024) -> Iterator[str]: ...

class AsyncChatModel(Protocol):
    async def complete(self, messages: Sequence[ChatMessage], *, max_tokens: int = 1024) -> Completion: ...
    def stream(self, messages: Sequence[ChatMessage], *, max_tokens: int = 1024) -> AsyncIterator[str]: ...

class FakeModel:
    """Satisfies AsyncChatModel structurally."""
    async def complete(self, messages: Sequence[ChatMessage], *, max_tokens: int = 1024) -> Completion:
        return Completion("ok", "stop", Usage(1, 1))

    async def stream(self, messages: Sequence[ChatMessage], *, max_tokens: int = 1024) -> AsyncIterator[str]:
        for tok in ("o", "k"):
            yield tok

async def fan_out(model: AsyncChatModel, prompts: Sequence[str]) -> list[Completion]:
    async with asyncio.TaskGroup() as tg:                     # 3.11
        tasks = [tg.create_task(model.complete([{"role": "user", "content": p}])) for p in prompts]
    return [t.result() for t in tasks]

async def collect(model: AsyncChatModel, prompt: str) -> str:
    return "".join([tok async for tok in model.stream([{"role": "user", "content": prompt}])])
```

Typing note: in a protocol, declare an async generator method as a plain `def`
returning `AsyncIterator[str]`. An implementation written as `async def` with
`yield` has exactly that type. Declaring it `async def ... -> AsyncIterator[str]`
in the protocol (without `yield`) would mean "coroutine returning an iterator",
which needs `await` before `async for`.

| Function shape | Annotation | Caller sees |
|----------------|------------|-------------|
| `def f() -> str` | `str` | `str` |
| `async def f() -> str` | `str` | `Coroutine[Any, Any, str]` until awaited |
| `def f()` with `yield` | `Iterator[str]` | iterator |
| `async def f()` with `yield` | `AsyncIterator[str]` | async iterator, no `await` |
| method returning a context-managed stream | `AbstractAsyncContextManager[AsyncIterator[str]]` | `async with ... as s: async for ...` |

With `@contextlib.asynccontextmanager`, annotate the generator function as
`-> AsyncIterator[T]`; the decorator turns it into a context manager of `T`.

## Callbacks and hooks

```python
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True, slots=True)
class TokenEvent:
    text: str
    index: int

type OnToken = Callable[[TokenEvent], None]
type AsyncOnToken = Callable[[TokenEvent], Awaitable[None]]

class OnFinish(Protocol):                  # keyword arguments need a callback protocol
    def __call__(self, text: str, *, usage: Usage, latency_s: float) -> None: ...

def stream_to(tokens: Iterator[str], on_token: OnToken | None = None) -> str:
    parts: list[str] = []
    for i, t in enumerate(tokens):
        parts.append(t)
        if on_token is not None:
            on_token(TokenEvent(t, i))
    return "".join(parts)
```

Hook registries: `dict[str, list[Callable[[TokenEvent], None]]]`. If a hook
may be sync or async, accept `Callable[[TokenEvent], Awaitable[None] | None]`
and check with `inspect.isawaitable(result)`.

## Retry and rate-limit decorators

```python
import asyncio
import functools
import random
from collections.abc import Awaitable, Callable

class RateLimitError(Exception):
    retry_after: float | None = None

def retry_async[**P, R](
    *, attempts: int = 5, base_delay: float = 0.5, retry_on: tuple[type[BaseException], ...] = (RateLimitError,)
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    def decorator(fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            for attempt in range(attempts):
                try:
                    return await fn(*args, **kwargs)
                except retry_on:
                    if attempt == attempts - 1:
                        raise
                    await asyncio.sleep(base_delay * 2 ** attempt + random.random() * 0.1)
            raise AssertionError("unreachable")
        return wrapper
    return decorator

@retry_async(attempts=3)
async def embed(texts: list[str], *, model: str = "text-embedding-3-small") -> list[list[float]]: ...

# embed keeps its signature: (texts: list[str], *, model: str = ...) -> Coroutine[..., list[list[float]]]
```

The trailing `raise AssertionError("unreachable")` satisfies the checker, which
cannot prove the loop always returns or raises.

## Embeddings, vector stores and repositories

```python
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

type Vector = NDArray[np.float32]                     # shape (d,)
type Matrix = NDArray[np.float32]                     # shape (n, d)
type Metadata = Mapping[str, str | int | float | bool]

class Embedder(Protocol):
    @property
    def dim(self) -> int: ...
    def embed(self, texts: Sequence[str]) -> Matrix: ...

@dataclass(frozen=True, slots=True)
class Record[T]:
    id: str
    vector: Vector
    payload: T
    metadata: Metadata = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class Hit[T]:
    record: Record[T]
    score: float

class VectorStore[T](
    Protocol
):
    def upsert(self, records: Iterable[Record[T]]) -> int: ...
    def search(self, query: Vector, k: int = 5, where: Metadata | None = None) -> list[Hit[T]]: ...
    def delete(self, ids: Iterable[str]) -> None: ...

class InMemoryStore[T]:
    def __init__(self) -> None:
        self._records: dict[str, Record[T]] = {}

    def upsert(self, records: Iterable[Record[T]]) -> int:
        n = 0
        for r in records:
            self._records[r.id] = r
            n += 1
        return n

    def search(self, query: Vector, k: int = 5, where: Metadata | None = None) -> list[Hit[T]]:
        rows = [r for r in self._records.values()
                if where is None or all(r.metadata.get(key) == v for key, v in where.items())]
        scored = [Hit(r, float(np.dot(r.vector, query))) for r in rows]
        return sorted(scored, key=lambda h: h.score, reverse=True)[:k]

    def delete(self, ids: Iterable[str]) -> None:
        for i in ids:
            self._records.pop(i, None)

store: VectorStore[str] = InMemoryStore[str]()        # checked structurally
```

Generic repository for any persisted entity:

```python
class Repository[K, E](
    Protocol
):
    def get(self, key: K) -> E | None: ...
    def add(self, entity: E) -> K: ...
    def list(self, *, limit: int = 100, offset: int = 0) -> list[E]: ...
```

## RAG pipeline types

```python
from collections.abc import Callable, Sequence
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Chunk:
    doc_id: str
    text: str
    start: int
    end: int

type Chunker = Callable[[str, str], list[Chunk]]        # (doc_id, text) -> chunks
type Reranker = Callable[[str, Sequence[Chunk]], list[tuple[Chunk, float]]]
type PromptBuilder = Callable[[str, Sequence[Chunk]], list[ChatMessage]]

def fixed_size_chunker(size: int = 800, overlap: int = 100) -> Chunker:
    def chunk(doc_id: str, text: str) -> list[Chunk]:
        step = size - overlap
        return [Chunk(doc_id, text[i:i + size], i, min(i + size, len(text)))
                for i in range(0, max(len(text) - overlap, 1), step)]
    return chunk

@dataclass(slots=True)
class RagPipeline:
    embedder: Embedder
    store: VectorStore[Chunk]
    model: AsyncChatModel
    build_prompt: PromptBuilder
    k: int = 5

    async def answer(self, question: str) -> str:
        q = self.embedder.embed([question])[0]
        hits = self.store.search(q, self.k)
        messages = self.build_prompt(question, [h.record.payload for h in hits])
        return (await self.model.complete(messages)).text
```

## Arrays and tensors

### numpy

```python
import numpy as np
import numpy.typing as npt
from numpy.typing import NDArray

def normalize(v: NDArray[np.float32]) -> NDArray[np.float32]:
    norms = np.linalg.norm(v, axis=-1, keepdims=True)
    return (v / np.maximum(norms, 1e-12)).astype(np.float32)

def to_array(x: npt.ArrayLike) -> NDArray[np.float64]:       # accepts lists, tuples, scalars, arrays
    return np.asarray(x, dtype=np.float64)

def cosine_topk(q: NDArray[np.floating], m: NDArray[np.floating], k: int) -> NDArray[np.intp]:
    return np.argsort(-(m @ q))[:k]
```

| Annotation | Meaning |
|------------|---------|
| `NDArray[np.float32]` | `ndarray` of any shape with dtype float32 |
| `NDArray[np.floating]` / `NDArray[np.integer]` | any float / int precision (abstract scalar types) |
| `NDArray[np.generic]` or `np.ndarray` | any dtype |
| `npt.ArrayLike` | anything `np.asarray` accepts (parameters only) |
| `npt.DTypeLike` | anything accepted as `dtype=` |
| `np.ndarray[tuple[int, int], np.dtype[np.float32]]` | 2-D shape in the type (numpy 2.x stubs; shape typing is still limited, most operations return `tuple[int, ...]` / `Any` shapes) |

numpy does not check dtypes at runtime from annotations. Many numpy functions
return `Any` or broad types; add `.astype(...)` or annotate the result where
precision matters.

### torch and jaxtyping (shapes)

`torch.Tensor` carries no dtype or shape in the type. jaxtyping adds both as
annotations that can be checked at runtime with a type checker such as
beartype or typeguard (works with numpy, torch, jax, tensorflow):

```python
import torch
from beartype import beartype
from jaxtyping import Float, Int, jaxtyped
from torch import Tensor

@jaxtyped(typechecker=beartype)
def attention(
    q: Float[Tensor, "batch heads seq d"],
    k: Float[Tensor, "batch heads seq d"],
    v: Float[Tensor, "batch heads seq d"],
    mask: Int[Tensor, "batch seq"] | None = None,
) -> Float[Tensor, "batch heads seq d"]:
    scores = q @ k.transpose(-2, -1) / q.shape[-1] ** 0.5
    if mask is not None:
        scores = scores.masked_fill(mask[:, None, None, :] == 0, float("-inf"))
    return scores.softmax(dim=-1) @ v

def mean_pool(
    hidden: Float[Tensor, "batch seq dim"], attn: Int[Tensor, "batch seq"]
) -> Float[Tensor, "batch dim"]:
    m = attn.unsqueeze(-1).to(hidden.dtype)
    return (hidden * m).sum(1) / m.sum(1).clamp(min=1e-9)
```

| jaxtyping syntax | Meaning |
|------------------|---------|
| `Float[Tensor, "b n d"]` | float dtype, 3 named dims; same name = same size across arguments |
| `Int`, `Bool`, `Shaped`, `Float32`, `BFloat16` | dtype families / exact dtypes; `Shaped` = any dtype |
| `"batch *rest"` | variadic dims |
| `"_ d"` / `"... d"` | unchecked dim / any leading dims |
| `"3 d"` | fixed-size dim |
| `"seq+1"` | expressions over named dims |

Static checkers see `Float[Tensor, "..."]` as `Tensor`; the shape checks happen
at runtime under `@jaxtyped`. Enable them in tests and debug runs; you can also
use `install_import_hook` to instrument a package. Name dims consistently
(`batch`, `seq`, `heads`, `dim`) across a codebase.

Torch module typing:

```python
from torch import Tensor, nn

class ProjectionHead(nn.Module):
    def __init__(self, dim_in: int, dim_out: int, dropout: float = 0.1) -> None:
        super().__init__()
        self.proj = nn.Linear(dim_in, dim_out)
        self.drop = nn.Dropout(dropout)

    def forward(self, x: Tensor) -> Tensor:
        return self.drop(self.proj(x))

# nn.Module.__call__ returns Any in torch's type hints, so `head(x)` is Any.
# Annotate the receiving variable to recover the type: `y: Tensor = head(x)`.
```

## Training and inference loops

```python
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import TypedDict

import torch
from torch import Tensor, nn
from torch.utils.data import DataLoader

class Batch(TypedDict):
    input_ids: Tensor
    attention_mask: Tensor
    labels: Tensor

@dataclass(slots=True)
class StepMetrics:
    step: int
    loss: float
    lr: float

def train_epoch(
    model: nn.Module,
    loader: DataLoader[Batch],
    optimizer: torch.optim.Optimizer,
    scheduler: torch.optim.lr_scheduler.LRScheduler | None = None,
    *,
    device: torch.device | str = "cuda",
    grad_clip: float | None = 1.0,
) -> Iterator[StepMetrics]:
    model.train()
    for step, batch in enumerate(loader):
        moved = {k: v.to(device) for k, v in batch.items()}       # dict[str, Tensor], no longer Batch
        out = model(**moved)
        loss: Tensor = out.loss
        loss.backward()
        if grad_clip is not None:
            nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
        optimizer.step()
        optimizer.zero_grad(set_to_none=True)
        if scheduler is not None:
            scheduler.step()
        yield StepMetrics(step, loss.item(), optimizer.param_groups[0]["lr"])

def batched[T](items: Iterable[T], size: int) -> Iterator[list[T]]:
    batch: list[T] = []
    for x in items:
        batch.append(x)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch
```

Note how the dict comprehension loses the `Batch` TypedDict type: a comprehension
always produces `dict[K, V]`, and assigning it back to `batch` would be a type
error, hence the new name `moved`. Either build the TypedDict explicitly
(`Batch(input_ids=..., attention_mask=..., labels=...)`) or accept that the
model call is loosely typed (torch module calls return `Any`).

## Typed configuration

```python
from typing import Literal

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class ModelConfig(BaseModel):
    provider: Literal["openai", "anthropic", "local"] = "openai"
    name: str = "gpt-4o-mini"
    temperature: float = Field(0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(1024, gt=0)

class RetrievalConfig(BaseModel):
    k: int = Field(5, ge=1, le=100)
    chunk_size: int = 800
    chunk_overlap: int = 100

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_nested_delimiter="__")
    api_key: SecretStr
    model: ModelConfig = ModelConfig()
    retrieval: RetrievalConfig = RetrievalConfig()
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

settings = Settings()                      # APP_API_KEY=..., APP_MODEL__TEMPERATURE=0.0
```

Without pydantic, a frozen dataclass with `Literal`/`Final` fields plus a
`from_env()` classmethod returning `Self` gives the same static guarantees
(no validation). Avoid `dict[str, Any]` configs passed through many layers:
every key access becomes unchecked.

## FastAPI services around models

```python
from typing import Annotated

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field

app = FastAPI()

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    temperature: float = Field(0.2, ge=0, le=2)

class ChatResponse(BaseModel):
    answer: str
    input_tokens: int
    output_tokens: int

def get_model() -> AsyncChatModel:
    return FakeModel()

ModelDep = Annotated[AsyncChatModel, Depends(get_model)]

@app.post("/chat")
async def chat(req: ChatRequest, model: ModelDep) -> ChatResponse:    # return annotation = response_model
    c = await model.complete([{"role": "user", "content": req.message}])
    return ChatResponse(answer=c.text, input_tokens=c.usage.input_tokens, output_tokens=c.usage.output_tokens)
```

FastAPI reads annotations at runtime: keep `Annotated`, models and dependency
types importable (not under `TYPE_CHECKING`), and on 3.9 use `Optional[X]`.

## Untyped AI libraries

| Situation | Fix |
|-----------|-----|
| Library has no `py.typed` (many research repos) | per-module `ignore_missing_imports` (mypy) and wrap it behind a small typed adapter |
| Library returns `Any` (`json.loads`, `requests.Response.json()`, HF `pipeline(...)`) | annotate the adapter's return and validate (pydantic / `isinstance`) |
| `transformers` / `datasets` return loosely typed objects | type your own functions in terms of `torch.Tensor`, `dict[str, Tensor]`, `BatchEncoding` and keep `Any` inside the adapter |
| Stubs exist on PyPI | `types-requests`, `types-PyYAML`, `types-tqdm`, `pandas-stubs`, `types-protobuf` |
| Partially typed SDK raises odd errors | upgrade the SDK; official `openai`, `anthropic`, `httpx`, `pydantic`, `fastapi`, `numpy` ship inline types |

The adapter pattern keeps `Any` contained:

```python
from typing import Any

import legacy_rerank   # untyped

def rerank(query: str, docs: Sequence[str], top_k: int = 5) -> list[tuple[int, float]]:
    raw: Any = legacy_rerank.score(query, list(docs))      # the only Any in the codebase for this library
    pairs = [(int(i), float(s)) for i, s in enumerate(raw)]
    return sorted(pairs, key=lambda p: p[1], reverse=True)[:top_k]
```
