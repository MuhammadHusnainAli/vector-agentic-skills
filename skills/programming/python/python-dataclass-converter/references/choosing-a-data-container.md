# Choosing a Data Container

Python has at least eight ways to hold structured data. This reference compares them on the axes that matter when converting code: validation, mutability, hashing, serialization, performance, dependencies and how the object is consumed.

## Contents

1. [Decision flow](#decision-flow)
2. [Comparison matrix](#comparison-matrix)
3. [The same object in every style](#the-same-object-in-every-style)
4. [dataclass](#dataclass)
5. [pydantic v2 BaseModel](#pydantic-v2-basemodel)
6. [pydantic dataclasses and TypeAdapter](#pydantic-dataclasses-and-typeadapter)
7. [TypedDict](#typeddict)
8. [NamedTuple](#namedtuple)
9. [attrs](#attrs)
10. [msgspec.Struct](#msgspecstruct)
11. [Plain dict and plain class](#plain-dict-and-plain-class)
12. [Boundary vs core architecture](#boundary-vs-core-architecture)
13. [Migration recipes between containers](#migration-recipes-between-containers)

## Decision flow

```
Is the data coming from outside the process (HTTP, LLM output, file, env, queue)?
 ├─ yes -> does it need coercion/validation/error messages or a JSON Schema?
 │         ├─ yes -> pydantic BaseModel (or msgspec.Struct if decode speed dominates)
 │         └─ no, trusted and you only want types -> TypedDict (keeps it a dict)
 └─ no (internal object)
      ├─ is it a tiny immutable record mainly unpacked / indexed? -> NamedTuple
      ├─ do you need converters/validators but no pydantic? -> attrs
      ├─ millions of instances, memory-bound? -> dataclass(slots=True) or columnar arrays
      └─ otherwise -> dataclass (frozen=True when it is a value / key / config)
```

## Comparison matrix

| | `@dataclass` | pydantic `BaseModel` | `TypedDict` | `NamedTuple` | attrs `@define` | `msgspec.Struct` | plain `dict` |
|---|---|---|---|---|---|---|---|
| Dependency | stdlib | `pydantic` | stdlib | stdlib | `attrs` | `msgspec` | - |
| Runtime validation | no (manual `__post_init__`) | yes, with coercion | no | no | opt-in validators | yes on decode | no |
| Runtime type is | your class | your class | `dict` | `tuple` | your class | your class | `dict` |
| Mutable | yes / `frozen=True` | yes / `frozen=True` | yes | no | yes / `@frozen` | yes / `frozen=True` | yes |
| Hashable by default | no (eq=True) | no (`frozen=True` to hash) | no | yes | no (`@frozen` yes) | no (`frozen=True` yes) | no |
| Positional construction | yes | no (keyword only) | no | yes | yes | yes (kw_only option) | - |
| Iterable / unpackable | no | yes (iterates pairs) | keys | yes | no | no | keys |
| JSON in | manual / helper | `model_validate_json` | `json.loads` | manual | cattrs | `msgspec.json.decode` | `json.loads` |
| JSON out | `asdict` + `json.dumps` | `model_dump_json` | `json.dumps` | `_asdict` | `attrs.asdict` | `msgspec.json.encode` | `json.dumps` |
| JSON Schema | no | `model_json_schema()` | via pydantic `TypeAdapter` | via TypeAdapter | no | `msgspec.json.schema` | no |
| Aliases (camelCase) | `metadata` + helper | `Field(alias=)`, `alias_generator` | not possible (keys are the names) | no | `alias=` (init only) | `rename=` | - |
| Memory per instance | medium (`slots` small) | larger | dict | small | small (slots default) | smallest | dict |
| Creation speed | fast | slower (validation) | fastest | fast | fast | fast | fastest |
| Static typing | full | full (plugin helps) | full | full | full | full | none |

## The same object in every style

An LLM tool call, as the OpenAI API returns it.

```python
# dataclass
from dataclasses import dataclass

@dataclass(frozen=True)
class ToolCallDC:
    id: str
    name: str
    arguments: str
```

```python
# pydantic v2
from pydantic import BaseModel, ConfigDict

class ToolCallPM(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    name: str
    arguments: str

ToolCallPM.model_validate({"id": "call_1", "name": "search", "arguments": "{}"})
```

```python
# TypedDict
from typing import TypedDict

class ToolCallTD(TypedDict):
    id: str
    name: str
    arguments: str

call: ToolCallTD = {"id": "call_1", "name": "search", "arguments": "{}"}   # still a dict
```

```python
# NamedTuple
from typing import NamedTuple

class ToolCallNT(NamedTuple):
    id: str
    name: str
    arguments: str

call_id, name, args = ToolCallNT("call_1", "search", "{}")
```

```python
# attrs
import attrs

@attrs.frozen
class ToolCallAT:
    id: str
    name: str
    arguments: str = attrs.field(validator=attrs.validators.instance_of(str))
```

```python
# msgspec
import msgspec

class ToolCallMS(msgspec.Struct, frozen=True):
    id: str
    name: str
    arguments: str

call = msgspec.json.decode(b'{"id":"call_1","name":"search","arguments":"{}"}', type=ToolCallMS)
```

## dataclass

Use for internal objects created by your own code: retrieved chunks after parsing, eval rows, pipeline state, configs after validation.

Strengths: stdlib, explicit, fast enough, supports `slots`, `frozen`, `kw_only`, `order`, works with `match`, type checkers understand it natively (PEP 681 `dataclass_transform` lets other libraries mimic it).

Weaknesses: no validation or coercion (`TokenUsage("12")` is accepted), no aliasing, `asdict` deep-copies, no built-in JSON.

Validation inside a dataclass is your job:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 5
    base_delay_s: float = 0.5
    max_delay_s: float = 30.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if not 0 < self.base_delay_s <= self.max_delay_s:
            raise ValueError("need 0 < base_delay_s <= max_delay_s")
```

## pydantic v2 BaseModel

Use at trust boundaries: FastAPI request/response bodies, parsing LLM "JSON mode" output, tool-call arguments, config files, environment (`pydantic-settings`), message queues.

```python
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

class SearchArgs(BaseModel):
    """Arguments the model passes to the search tool."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=512)
    top_k: int = Field(default=5, ge=1, le=50)
    filters: dict[str, str] = Field(default_factory=dict)
    mode: Literal["dense", "hybrid"] = "hybrid"
    since: Optional[str] = None

    @field_validator("query")
    @classmethod
    def no_wildcards(cls, v: str) -> str:
        if v == "*":
            raise ValueError("wildcard queries are not allowed")
        return v

raw = '{"query": " paris hotels ", "top_k": "10"}'
try:
    args = SearchArgs.model_validate_json(raw)     # "10" coerced to 10 in lax mode
except ValidationError as e:
    print(e.errors())                              # feed back to the LLM for a retry
print(SearchArgs.model_json_schema()["properties"]["top_k"])   # tool schema for function calling
```

Key v2 API:

| Need | API |
|------|-----|
| Parse dict / JSON | `Model.model_validate(d)`, `Model.model_validate_json(s)` |
| Dump | `m.model_dump(mode="json", by_alias=True, exclude_none=True)`, `m.model_dump_json()` |
| Copy with changes | `m.model_copy(update={...})` (no re-validation) |
| Schema | `Model.model_json_schema()` |
| Strictness | `ConfigDict(strict=True)` or `Field(strict=True)` |
| Unknown keys | `ConfigDict(extra="forbid" or "ignore" or "allow")` |
| Aliases | `Field(alias="finishReason")`, `ConfigDict(alias_generator=to_camel, populate_by_name=True)` (2.11+: `validate_by_name=True`) |
| Immutability | `ConfigDict(frozen=True)` (then hashable) |
| Cross-field checks | `@model_validator(mode="after")` |
| Arbitrary types (numpy) | `ConfigDict(arbitrary_types_allowed=True)` |

Costs: every construction validates (`model_construct()` skips it for trusted data), extra dependency, objects are heavier. Do not use `BaseModel` for millions of internal chunks in a hot loop.

## pydantic dataclasses and TypeAdapter

You can keep stdlib dataclasses and still validate at the boundary:

```python
from dataclasses import dataclass
from pydantic import TypeAdapter

@dataclass
class Chunk:
    chunk_id: str
    text: str
    score: float = 0.0

chunks = TypeAdapter(list[Chunk]).validate_json('[{"chunk_id": "a", "text": "x", "score": "0.5"}]')
print(type(chunks[0]), chunks[0].score)   # <class '__main__.Chunk'> 0.5
```

`TypeAdapter` validates into the real stdlib dataclass (and works for `TypedDict`, `NamedTuple`, `list[...]`). `pydantic.dataclasses.dataclass` is a drop-in decorator that validates on every `__init__`; it mixes the two worlds and is best avoided in core code.

## TypedDict

Use when the value must remain a `dict`: SDK call parameters (`messages=[{"role": "user", "content": "..."}]`), JSON you forward unchanged, `**kwargs` typing (3.12 `Unpack`).

```python
from typing import Literal, TypedDict

try:
    from typing import NotRequired          # 3.11+
except ImportError:                          # 3.9 / 3.10
    from typing_extensions import NotRequired

class ChatMessageTD(TypedDict):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: NotRequired[str]
    tool_call_id: NotRequired[str]

def user(content: str) -> ChatMessageTD:
    return {"role": "user", "content": content}
```

- `total=False` makes all keys optional; `Required[...]` / `NotRequired[...]` (3.11) per key; `ReadOnly[...]` (3.13).
- Non-identifier keys need the functional form: `Gateway = TypedDict("Gateway", {"x-request-id": str})`.
- No runtime checks: `isinstance(x, ChatMessageTD)` raises `TypeError`. Validate with pydantic `TypeAdapter(ChatMessageTD)` when needed.

## NamedTuple

Use for small immutable records that are naturally positional or unpacked: `(score, index)` search hits, `(start, end)` spans, rows from `csv`.

```python
from typing import NamedTuple

class Hit(NamedTuple):
    score: float
    index: int
    doc_id: str = ""

hits = sorted([Hit(0.4, 3), Hit(0.9, 1)], reverse=True)
best_score, best_idx, _ = hits[0]
print(hits[0]._replace(doc_id="d1"), hits[0]._asdict())
```

Gotchas: it **is** a tuple, so `Hit(0.4, 3) == (0.4, 3, "")` is `True`, `len()` works, and two different NamedTuple classes with equal values compare equal. No mutable defaults problem only because defaults are shared (do not use a list default). No `__post_init__`.

## attrs

The project dataclasses was modelled on. Use when you want converters and validators on plain classes without pydantic, or slots by default.

```python
import attrs

def _to_tuple(v) -> tuple:
    return tuple(v)

@attrs.define(frozen=True)            # slots=True by default with define
class Prompt:
    template: str = attrs.field(validator=attrs.validators.min_len(1))
    stop: tuple = attrs.field(factory=tuple, converter=_to_tuple)
    temperature: float = attrs.field(default=0.7, validator=[attrs.validators.ge(0), attrs.validators.le(2)])

p = Prompt("Answer: {q}", stop=["\n"])   # list converted to tuple
```

`cattrs` adds structured (de)serialization with aliases and unions. Note: `attrs.define` makes `eq=True` and hashing follows the same rules as dataclasses (unhashable unless frozen).

## msgspec.Struct

Use for hot decode/encode paths: streaming server-sent events, large JSONL eval logs, high-throughput inference gateways.

```python
from typing import Optional

import msgspec

class Usage(msgspec.Struct):
    prompt_tokens: int
    completion_tokens: int

class Completion(msgspec.Struct, rename="camel"):   # Python snake_case, JSON camelCase
    request_id: str
    finish_reason: Optional[str] = None
    usage: Optional[Usage] = None

decoder = msgspec.json.Decoder(Completion)          # reuse the decoder
c = decoder.decode(b'{"requestId": "r1", "finishReason": "stop", "usage": {"prompt_tokens": 3, "completion_tokens": 5}}')
print(msgspec.json.encode(c))
```

Validation is type-based (strict by default), structs are slotted and small, `frozen=True`, `kw_only=True`, `array_like=True`, `omit_defaults=True` are class options. Less flexible than pydantic for custom validators.

## Plain dict and plain class

Keep a plain `dict` for genuinely dynamic data (arbitrary metadata from a vector store, model kwargs passed through). Keep a hand-written class when the object owns resources and behaviour (an HTTP client, a model wrapper with a session) and has identity semantics; a dataclass adds little and `eq=True` would be wrong. If you still want the generated `__init__`/`repr`, use `@dataclass(eq=False)`.

## Boundary vs core architecture

```
HTTP / LLM output / files / env
        │  pydantic BaseModel (validate, coerce, clear errors)  or msgspec for speed
        ▼
  convert once: Model -> dataclass   (or validate straight into dataclasses with TypeAdapter)
        ▼
  core logic: frozen dataclasses for values/configs, slots dataclasses for bulk records
        ▼
  serialize at the edge: asdict / custom to_dict / model_dump
```

```python
from dataclasses import dataclass

from pydantic import BaseModel, Field

class IngestRequest(BaseModel):               # edge
    doc_id: str
    text: str = Field(min_length=1)
    chunk_size: int = Field(default=800, ge=100, le=4000)

@dataclass(frozen=True, slots=True)           # core (3.10+ for slots)
class IngestJob:
    doc_id: str
    text: str
    chunk_size: int

def to_job(req: IngestRequest) -> IngestJob:
    return IngestJob(**req.model_dump())
```

## Migration recipes between containers

| From | To | Recipe |
|------|----|--------|
| `dict` access everywhere | dataclass | add `from_dict` classmethod at the entry point; replace `d["x"]` with `obj.x` |
| tuple `(score, idx)` | NamedTuple | same positional order; existing unpacking keeps working |
| NamedTuple | dataclass | add `@dataclass(frozen=True)`; fix callers that unpack / index / compare to tuples; `astuple()` if needed |
| dataclass | pydantic | `class X(BaseModel)`; `field(default_factory=...)` -> `Field(default_factory=...)`; `__post_init__` -> `model_validator(mode="after")`; `replace()` -> `model_copy(update=)`; positional calls -> keywords |
| pydantic | dataclass | drop validators into `__post_init__` or keep pydantic at the edge; `model_dump()` -> `asdict()` |
| dataclass | TypedDict | only when it must be a dict; methods become functions |
| dataclass | msgspec.Struct | `class X(msgspec.Struct)`; `field(default_factory=list)` -> `msgspec.field(default_factory=list)`; no `__post_init__` before msgspec 0.18 |
| dataclass | attrs | `@attrs.define`; `field(default_factory=x)` -> `attrs.field(factory=x)`; validators/converters available |
