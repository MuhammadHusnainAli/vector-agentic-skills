# AI-Engineering Data Models

Ready-to-adapt dataclass (and pydantic, where it belongs) designs for LLM apps, RAG pipelines, agents, evals and training code. Each section states the container choice and the gotchas specific to that object.

## Contents

1. [Configs: training, inference, retrieval](#configs-training-inference-retrieval)
2. [Chat messages and content blocks](#chat-messages-and-content-blocks)
3. [Tool definitions and tool calls](#tool-definitions-and-tool-calls)
4. [LLM request and response objects](#llm-request-and-response-objects)
5. [Converting OpenAI-style JSON to typed objects](#converting-openai-style-json-to-typed-objects)
6. [Converting Anthropic-style JSON to typed objects](#converting-anthropic-style-json-to-typed-objects)
7. [Streaming deltas and accumulation](#streaming-deltas-and-accumulation)
8. [RAG: documents, chunks, embeddings, hits](#rag-documents-chunks-embeddings-hits)
9. [Eval records and results](#eval-records-and-results)
10. [Agent state and traces](#agent-state-and-traces)
11. [Batching and async fan-out results](#batching-and-async-fan-out-results)
12. [pydantic vs dataclasses in an LLM service](#pydantic-vs-dataclasses-in-an-llm-service)

## Configs: training, inference, retrieval

Configs are values: frozen, hashable, comparable, easy to diff and to hash into a run id or cache key.

```python
import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from typing import Literal, Optional

@dataclass(frozen=True)
class OptimizerConfig:
    name: Literal["adamw", "sgd"] = "adamw"
    lr: float = 2e-5
    weight_decay: float = 0.01
    betas: tuple[float, float] = (0.9, 0.999)

@dataclass(frozen=True)
class TrainingConfig:
    base_model: str
    dataset: str
    epochs: int = 3
    batch_size: int = 16
    grad_accum_steps: int = 1
    max_seq_len: int = 2048
    seed: int = 42
    optimizer: OptimizerConfig = field(default_factory=OptimizerConfig)
    lora_rank: Optional[int] = None
    output_dir: str = field(default="runs", compare=False)   # where to write does not change the experiment

    def __post_init__(self) -> None:
        if self.batch_size * self.grad_accum_steps > 4096:
            raise ValueError("effective batch size is suspiciously large")

    @property
    def effective_batch_size(self) -> int:
        return self.batch_size * self.grad_accum_steps

    def run_id(self) -> str:
        payload = {k: v for k, v in asdict(self).items() if k != "output_dir"}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]

base = TrainingConfig("meta-llama/Llama-3.1-8B", "support-tickets-v3")
sweep = [replace(base, optimizer=replace(base.optimizer, lr=lr)) for lr in (1e-5, 2e-5, 5e-5)]
print({c.run_id() for c in sweep})   # three distinct ids, deterministic across processes
```

- Nested config: `field(default_factory=OptimizerConfig)` (a frozen instance default would also be accepted, but a factory avoids sharing).
- `hash()` of a frozen dataclass is **not** stable across processes for `str` fields (hash randomisation): use a content hash like `run_id()` for filenames and caches.
- Inference config:

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)          # 3.10+
class InferenceConfig:
    model: str
    temperature: float = 0.0
    top_p: float = 1.0
    max_tokens: int = 1024
    stop: tuple[str, ...] = ()
    seed: int | None = None                  # 3.10+ union syntax
    timeout_s: float = 60.0
    max_retries: int = 5

    def to_request_kwargs(self) -> dict:
        kw = {"model": self.model, "temperature": self.temperature, "top_p": self.top_p,
              "max_tokens": self.max_tokens}
        if self.stop:
            kw["stop"] = list(self.stop)
        if self.seed is not None:
            kw["seed"] = self.seed
        return kw
```

- Retrieval config: `top_k`, `score_threshold`, `mmr_lambda`, `filters: tuple[tuple[str, str], ...]` (a tuple of pairs keeps it hashable; a dict field would make the frozen class unhashable).

## Chat messages and content blocks

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Union

class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

@dataclass(frozen=True)
class TextPart:
    text: str
    type: str = field(default="text", init=False)

@dataclass(frozen=True)
class ImagePart:
    url: str
    detail: str = "auto"
    type: str = field(default="image_url", init=False)

ContentPart = Union[TextPart, ImagePart]

@dataclass
class Message:
    role: Role
    content: Union[str, list[ContentPart], None] = None
    name: Optional[str] = None
    tool_calls: list["ToolCall"] = field(default_factory=list)
    tool_call_id: Optional[str] = None

    @classmethod
    def system(cls, text: str) -> "Message":
        return cls(Role.SYSTEM, text)

    @classmethod
    def user(cls, text: str) -> "Message":
        return cls(Role.USER, text)

    def to_openai(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role.value}
        if isinstance(self.content, list):
            d["content"] = [
                {"type": "text", "text": p.text} if isinstance(p, TextPart)
                else {"type": "image_url", "image_url": {"url": p.url, "detail": p.detail}}
                for p in self.content
            ]
        else:
            d["content"] = self.content
        if self.name:
            d["name"] = self.name
        if self.tool_calls:
            d["tool_calls"] = [tc.to_openai() for tc in self.tool_calls]
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d
```

Notes:

- Messages are mutable during assembly, then appended to a history list; do not use them as dict keys (they are unhashable with `eq=True`, which is fine).
- `type` discriminator fields with `init=False` keep constructors short and make `asdict()` output wire-compatible.
- Keep `content` raw (`str` or parts); do not normalise away provider-specific structure you need to send back.
- A conversation is `list[Message]`; a `Conversation` dataclass is worth it only when it carries behaviour (token budgeting, truncation).

```python
from dataclasses import dataclass, field

@dataclass
class Conversation:
    messages: list = field(default_factory=list)
    max_context_tokens: int = 128_000

    def append(self, msg: "Message") -> None:
        self.messages.append(msg)

    def truncated(self, count_tokens) -> list:
        """Keep the system prompt and as many recent turns as fit."""
        system = [m for m in self.messages if m.role == Role.SYSTEM][:1]
        rest = [m for m in self.messages if m.role != Role.SYSTEM]
        budget = self.max_context_tokens - sum(count_tokens(m) for m in system)
        kept = []
        for m in reversed(rest):
            budget -= count_tokens(m)
            if budget < 0:
                break
            kept.append(m)
        return system + kept[::-1]
```

## Tool definitions and tool calls

Tool **schemas** are generated from pydantic models (JSON Schema); tool **calls** coming back are parsed into dataclasses, and their arguments validated by the same pydantic model.

```python
import json
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError

class GetWeatherArgs(BaseModel):
    city: str = Field(description="City name, e.g. 'Paris'")
    unit: str = Field(default="celsius", pattern="^(celsius|fahrenheit)$")

@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args_model: type

    def to_openai(self) -> dict[str, Any]:
        return {"type": "function", "function": {
            "name": self.name, "description": self.description,
            "parameters": self.args_model.model_json_schema()}}

@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str          # raw JSON text exactly as the model produced it

    def to_openai(self) -> dict[str, Any]:
        return {"id": self.id, "type": "function", "function": {"name": self.name, "arguments": self.arguments}}

@dataclass(frozen=True)
class ToolResult:
    call_id: str
    content: str
    is_error: bool = False

def run_tool(call: ToolCall, specs: dict, impls: dict) -> ToolResult:
    spec = specs.get(call.name)
    if spec is None:
        return ToolResult(call.id, f"unknown tool {call.name!r}", is_error=True)
    try:
        args = spec.args_model.model_validate_json(call.arguments)
    except ValidationError as e:
        return ToolResult(call.id, f"invalid arguments: {e.errors(include_url=False)}", is_error=True)
    fn: Callable[..., Any] = impls[call.name]
    return ToolResult(call.id, json.dumps(fn(**args.model_dump())))
```

- Keep `arguments` as the raw string: models emit invalid JSON sometimes, and you want to report the exact text back.
- `is_error=True` results are sent back to the model so it can self-correct instead of crashing the loop.

## LLM request and response objects

```python
import time
from dataclasses import dataclass, field
from typing import Any, Optional

@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(self.input_tokens + other.input_tokens, self.output_tokens + other.output_tokens,
                     self.cached_tokens + other.cached_tokens)

    def cost_usd(self, in_per_mtok: float, out_per_mtok: float) -> float:
        return (self.input_tokens * in_per_mtok + self.output_tokens * out_per_mtok) / 1_000_000

@dataclass
class LLMRequest:
    model: str
    messages: list
    temperature: float = 0.0
    max_tokens: int = 1024
    tools: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict, compare=False)

@dataclass
class LLMResponse:
    id: str
    model: str
    text: Optional[str]
    tool_calls: list = field(default_factory=list)
    finish_reason: Optional[str] = None
    usage: Usage = field(default_factory=Usage)
    latency_s: float = field(default=0.0, compare=False)
    raw: Any = field(default=None, repr=False, compare=False)   # original payload for debugging

    @property
    def truncated(self) -> bool:
        return self.finish_reason in ("length", "max_tokens")

total = sum((r.usage for r in []), Usage())     # Usage.__add__ makes token accounting trivial
```

- Provider-neutral response objects isolate the rest of the code from SDK changes. Build them in exactly one adapter per provider.
- `raw` with `repr=False, compare=False` keeps the payload for debugging without polluting logs or equality.
- `latency_s` is metadata: exclude from comparison so cached and live responses compare equal.

## Converting OpenAI-style JSON to typed objects

Generate the skeleton from a captured payload, then trim it:

```bash
python scripts/to_dataclass.py json chat_completion.json --name ChatCompletion
```

A hand-tuned adapter (ignores unknown fields, tolerant of `null`s):

```python
from typing import Any

def openai_to_response(d: dict[str, Any], latency_s: float = 0.0) -> LLMResponse:
    choice = d["choices"][0]
    msg = choice.get("message") or {}
    calls = [ToolCall(tc["id"], tc["function"]["name"], tc["function"].get("arguments") or "{}")
             for tc in (msg.get("tool_calls") or [])]
    u = d.get("usage") or {}
    details = u.get("prompt_tokens_details") or {}
    return LLMResponse(
        id=d["id"], model=d.get("model", ""), text=msg.get("content"), tool_calls=calls,
        finish_reason=choice.get("finish_reason"),
        usage=Usage(u.get("prompt_tokens", 0), u.get("completion_tokens", 0), details.get("cached_tokens", 0)),
        latency_s=latency_s, raw=d,
    )
```

SDK objects (`openai` v1 returns pydantic models): use `resp.model_dump()` to get the dict, then the same adapter. Do not pass SDK objects deep into your code.

## Converting Anthropic-style JSON to typed objects

Anthropic Messages responses carry a list of typed **content blocks** (`text`, `tool_use`, `thinking`, ...). Model them as a discriminated union.

```python
from dataclasses import dataclass, field
from typing import Any, Union

@dataclass(frozen=True)
class TextBlock:
    text: str

@dataclass(frozen=True)
class ToolUseBlock:
    id: str
    name: str
    input: dict = field(hash=False)          # already-parsed JSON object, unlike OpenAI's string

@dataclass(frozen=True)
class UnknownBlock:
    type: str
    data: dict = field(hash=False, repr=False)

Block = Union[TextBlock, ToolUseBlock, UnknownBlock]

def parse_block(b: dict[str, Any]) -> Block:
    t = b.get("type")
    if t == "text":
        return TextBlock(b["text"])
    if t == "tool_use":
        return ToolUseBlock(b["id"], b["name"], b.get("input") or {})
    return UnknownBlock(str(t), b)                # forward compatible: new block types do not crash

def anthropic_to_response(d: dict[str, Any]) -> LLMResponse:
    blocks = [parse_block(b) for b in d.get("content", [])]
    text = "".join(b.text for b in blocks if isinstance(b, TextBlock)) or None
    import json
    calls = [ToolCall(b.id, b.name, json.dumps(b.input)) for b in blocks if isinstance(b, ToolUseBlock)]
    u = d.get("usage") or {}
    return LLMResponse(id=d["id"], model=d.get("model", ""), text=text, tool_calls=calls,
                       finish_reason=d.get("stop_reason"),
                       usage=Usage(u.get("input_tokens", 0), u.get("output_tokens", 0),
                                   u.get("cache_read_input_tokens", 0)),
                       raw=d)
```

`UnknownBlock` is the important design choice: providers add block types; an exhaustive parser that raises on unknown types breaks production the day a new feature ships.

## Streaming deltas and accumulation

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass(slots=True)        # many tiny objects per response (3.10+)
class Delta:
    index: int
    text: str = ""
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    args_fragment: str = ""
    finish_reason: Optional[str] = None

@dataclass
class StreamAccumulator:
    text_parts: list = field(default_factory=list)
    calls: dict = field(default_factory=dict)          # index -> {"id", "name", "args"}
    finish_reason: Optional[str] = None

    def add(self, d: Delta) -> None:
        if d.text:
            self.text_parts.append(d.text)
        if d.tool_call_id or d.tool_name or d.args_fragment:
            slot = self.calls.setdefault(d.index, {"id": "", "name": "", "args": []})
            slot["id"] = d.tool_call_id or slot["id"]
            slot["name"] = d.tool_name or slot["name"]
            slot["args"].append(d.args_fragment)
        if d.finish_reason:
            self.finish_reason = d.finish_reason

    @property
    def text(self) -> str:
        return "".join(self.text_parts)        # join once: O(n), not repeated +=

    def tool_calls(self) -> list:
        return [ToolCall(c["id"], c["name"], "".join(c["args"])) for _, c in sorted(self.calls.items())]
```

## RAG: documents, chunks, embeddings, hits

```python
import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

@dataclass(frozen=True)
class Document:
    doc_id: str
    source: str                                        # URL / path
    text: str = field(repr=False)
    metadata: tuple = ()                               # tuple of (key, value) pairs keeps it hashable

@dataclass(slots=True)                                 # 3.10+; created by the hundred thousand
class Chunk:
    doc_id: str
    ordinal: int
    text: str = field(repr=False)
    start_char: int = 0
    end_char: int = 0
    embedding: Optional[np.ndarray] = field(default=None, repr=False, compare=False)
    metadata: dict = field(default_factory=dict, compare=False)

    @property
    def chunk_id(self) -> str:
        return f"{self.doc_id}:{self.ordinal}"

    @property
    def content_hash(self) -> str:                     # dedupe / skip re-embedding unchanged text
        return hashlib.sha1(self.text.encode()).hexdigest()

@dataclass(frozen=True, order=True)
class Hit:
    sort_key: float = field(init=False, repr=False)    # -score so ascending sort = best first
    score: float
    chunk_id: str
    text: str = field(compare=False, repr=False)
    metadata: Any = field(default=None, compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "sort_key", -self.score)

def chunk_document(doc: Document, size: int = 800, overlap: int = 100) -> list:
    chunks, start, i = [], 0, 0
    while start < len(doc.text):
        end = min(len(doc.text), start + size)
        chunks.append(Chunk(doc.doc_id, i, doc.text[start:end], start, end))
        if end == len(doc.text):
            break
        start, i = end - overlap, i + 1
    return chunks
```

The numpy equality gotcha, demonstrated:

```python
import numpy as np
from dataclasses import dataclass

@dataclass
class BadChunk:
    text: str
    embedding: np.ndarray

a = BadChunk("x", np.ones(3))
b = BadChunk("x", np.ones(3))
print(a == a)        # True: tuple comparison short-circuits on identity
try:
    print(a == b)    # ValueError: The truth value of an array with more than one element is ambiguous
except ValueError as e:
    print(e)
```

Rules for embedding-carrying objects:

- `compare=False` (and `repr=False`) on every array/tensor field; compare by id or content hash.
- Never `frozen=True` + default hash with an array field (`TypeError: unhashable type: 'numpy.ndarray'` on `hash()`).
- Do not `asdict()` chunks with embeddings in a loop (deep copy). Store embeddings column-wise: `np.stack([c.embedding for c in chunks])` and keep chunk objects for metadata.
- Normalise once (`v / np.linalg.norm(v)`) at creation and document it, so cosine = dot product.

Vector store record (what you upsert):

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class VectorRecord:
    id: str
    values: tuple = field(repr=False, hash=False)      # list(float) converted to tuple
    metadata: tuple = field(default=(), hash=False)

    def to_upsert(self) -> dict:
        return {"id": self.id, "values": list(self.values), "metadata": dict(self.metadata)}
```

## Eval records and results

```python
import statistics
from dataclasses import asdict, dataclass, field
from typing import Optional

@dataclass(frozen=True)
class EvalExample:
    example_id: str
    question: str
    reference: str
    tags: tuple = ()

@dataclass
class EvalResult:
    example_id: str
    model: str
    prediction: str = field(repr=False)
    score: float = 0.0
    passed: bool = False
    latency_ms: float = field(default=0.0, compare=False)
    cost_usd: float = field(default=0.0, compare=False)
    error: Optional[str] = None
    judge_rationale: str = field(default="", repr=False, compare=False)

@dataclass(frozen=True)
class EvalSummary:
    model: str
    n: int
    mean_score: float
    pass_rate: float
    p95_latency_ms: float
    total_cost_usd: float

    @classmethod
    def from_results(cls, model: str, results: list) -> "EvalSummary":
        ok = [r for r in results if r.error is None]
        lat = sorted(r.latency_ms for r in ok) or [0.0]
        return cls(model=model, n=len(results),
                   mean_score=statistics.fmean(r.score for r in ok) if ok else 0.0,
                   pass_rate=sum(r.passed for r in ok) / len(results) if results else 0.0,
                   p95_latency_ms=lat[min(len(lat) - 1, int(0.95 * len(lat)))],
                   total_cost_usd=sum(r.cost_usd for r in results))

# rows -> JSONL / DataFrame: [asdict(r) for r in results] (flat, cheap)
```

- Keep `error` as data, not an exception: one failing example must not kill a 2 000-example run.
- Judge rationales and predictions are long: `repr=False` so printing a summary list stays readable.
- `statistics.fmean` is 3.8+.

## Agent state and traces

```python
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

@dataclass
class Step:
    kind: Literal["llm", "tool", "retrieval"]
    name: str
    input: Any = field(repr=False)
    output: Any = field(default=None, repr=False)
    error: Optional[str] = None
    started_at: float = field(default_factory=time.time, compare=False)
    ended_at: Optional[float] = field(default=None, compare=False)

    @property
    def duration_s(self) -> Optional[float]:
        return None if self.ended_at is None else self.ended_at - self.started_at

@dataclass
class AgentState:
    task: str
    messages: list = field(default_factory=list)
    steps: list = field(default_factory=list)
    scratchpad: dict = field(default_factory=dict)
    iteration: int = 0
    max_iterations: int = 10
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex, compare=False)

    @property
    def exhausted(self) -> bool:
        return self.iteration >= self.max_iterations
```

Agent state is mutable by design (`eq=True` is fine, no hashing). If you need snapshots (for replay or branching), deep-copy explicitly (`copy.deepcopy(state)`), or make steps frozen and build new state with `replace()`.

## Batching and async fan-out results

```python
import asyncio
from dataclasses import dataclass, field
from typing import Any, Generic, Optional, TypeVar

T = TypeVar("T")

@dataclass(frozen=True)
class Outcome(Generic[T]):
    index: int
    value: Optional[T] = None
    error: Optional[str] = None
    attempts: int = 1

    @property
    def ok(self) -> bool:
        return self.error is None

async def gather_outcomes(coros: list, limit: int = 8) -> list:
    sem = asyncio.Semaphore(limit)

    async def run(i: int, c: Any) -> Outcome:
        async with sem:
            try:
                return Outcome(i, value=await c)
            except Exception as e:           # keep going; report per item
                return Outcome(i, error=f"{type(e).__name__}: {e}")

    return list(await asyncio.gather(*(run(i, c) for i, c in enumerate(coros))))
```

`Outcome` keeps input order (`index`), separates success/failure without exceptions crossing `gather`, and is cheap to log with `asdict`.

## pydantic vs dataclasses in an LLM service

| Object | Container | Reason |
|--------|-----------|--------|
| FastAPI request/response body | pydantic | validation, OpenAPI schema |
| Tool argument schema | pydantic | `model_json_schema()` for the LLM, validate model output |
| Structured output (`response_format` JSON schema) | pydantic | parse + validate + retry on `ValidationError` |
| Provider response after adapter | dataclass | trusted, internal, provider-neutral |
| Chat `Message`, `ToolCall`, `Usage` | dataclass | internal, hot path, simple |
| Chunk / Hit / VectorRecord | dataclass (`slots=True`) | volume, memory |
| Training / inference config | frozen dataclass (load with pydantic if from YAML) | hashing, run ids |
| Settings from env / `.env` | pydantic-settings | parsing, secrets, errors |
| Eval rows | dataclass | flat, `asdict` to JSONL |
| SSE stream events at very high volume | msgspec | decode speed |

Structured-output retry loop combining both:

```python
from pydantic import BaseModel, ValidationError

class Extraction(BaseModel):
    company: str
    amount_usd: float
    date: str

def extract(llm_call, text: str, max_attempts: int = 3) -> Extraction:
    prompt = f"Extract company, amount_usd, date as JSON from:\n{text}"
    for _ in range(max_attempts):
        raw = llm_call(prompt)
        try:
            return Extraction.model_validate_json(raw)
        except ValidationError as e:
            prompt += f"\n\nYour previous answer was invalid: {e.errors(include_url=False)}. Return only valid JSON."
    raise RuntimeError("model never produced valid JSON")
```
