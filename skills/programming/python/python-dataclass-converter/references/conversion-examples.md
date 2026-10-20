# Conversion Examples

Worked before/after conversions. Each lists what `scripts/to_dataclass.py` reports (rule ids) and the behaviour changes to tell the user about. The last sections cover classes the script deliberately skips and how to convert them by hand.

## Contents

1. [Plain record with redundant dunders](#1-plain-record-with-redundant-dunders)
2. [Mutable default argument bug](#2-mutable-default-argument-bug)
3. [Validation and derived fields](#3-validation-and-derived-fields)
4. [Construction-only parameter (InitVar)](#4-construction-only-parameter-initvar)
5. [Hashable value object](#5-hashable-value-object)
6. [Sortable records](#6-sortable-records)
7. [Embedding-carrying object](#7-embedding-carrying-object)
8. [__slots__ class](#8-__slots__-class)
9. [Keyword-only parameters](#9-keyword-only-parameters)
10. [dict-based code to dataclass](#10-dict-based-code-to-dataclass)
11. [Tuple to NamedTuple to dataclass](#11-tuple-to-namedtuple-to-dataclass)
12. [JSON payload to classes](#12-json-payload-to-classes)
13. [Skipped: inheritance with super().__init__](#13-skipped-inheritance-with-super__init__)
14. [Skipped: renamed attributes](#14-skipped-renamed-attributes)
15. [Skipped: *args / **kwargs](#15-skipped-args--kwargs)
16. [Skipped: exceptions](#16-skipped-exceptions)
17. [Dataclass to pydantic at a boundary](#17-dataclass-to-pydantic-at-a-boundary)
18. [Verification checklist](#18-verification-checklist)

## 1. Plain record with redundant dunders

Before:

```python
from typing import Any, Dict, List, Optional

class ChatMessage:
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
```

After (`DC002`, `DC003`, `DC004`):

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class ChatMessage:
    role: str
    content: str
    name: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
```

Behaviour changes to report:

- `ChatMessage("user", "hi", tool_calls=None)` used to store `[]`; now stores `None`. If callers pass `None` explicitly, keep it `Optional` and normalise in `__post_init__`: `if self.tool_calls is None: self.tool_calls = []`.
- `__eq__` no longer accepts subclass instances (`isinstance` vs exact class).
- Instances were already unhashable (custom `__eq__` without `__hash__` sets `__hash__ = None`), so no hashing change.

## 2. Mutable default argument bug

Before:

```python
class PromptBuilder:
    def __init__(self, system: str, examples=[]):
        self.system = system
        self.examples = examples

    def add_example(self, q: str, a: str) -> None:
        self.examples.append((q, a))      # mutates the shared default list
```

```python
a = PromptBuilder("You are terse.")
b = PromptBuilder("You are verbose.")
a.add_example("2+2?", "4")
print(len(b.examples))   # 1: the bug
```

After (`DC001`, `DC007`, `DC016`):

```python
from dataclasses import dataclass, field

@dataclass
class PromptBuilder:
    system: str
    examples: list = field(default_factory=list)

    def add_example(self, q: str, a: str) -> None:
        self.examples.append((q, a))
```

Improve the inferred annotation by hand: `examples: list[tuple[str, str]]`. `DC016` warns that `PromptBuilder` objects were hashable by identity before; if any code keys a dict by builder, use `@dataclass(eq=False)`.

## 3. Validation and derived fields

Before:

```python
class GenerationConfig:
    def __init__(self, model: str, temperature: float = 0.7, max_tokens: int = 1024):
        if not 0.0 <= temperature <= 2.0:
            raise ValueError(f"temperature must be in [0, 2], got {temperature}")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.is_greedy = temperature == 0.0
```

After (`DC008`):

```python
from dataclasses import dataclass, field

@dataclass
class GenerationConfig:
    model: str
    temperature: float = 0.7
    max_tokens: int = 1024
    is_greedy: bool = field(init=False)

    def __post_init__(self) -> None:
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError(f"temperature must be in [0, 2], got {self.temperature}")
        self.is_greedy = self.temperature == 0.0
```

Better still: make `is_greedy` a `@property` so it can never go stale after `cfg.temperature = 0`. Derived **stored** fields are right only for frozen classes or expensive computations.

With `--frozen` the tool writes the assignment through `object.__setattr__`:

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class GenerationConfigFrozen:
    model: str
    temperature: float = 0.7
    is_greedy: bool = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "is_greedy", self.temperature == 0.0)
```

## 4. Construction-only parameter (InitVar)

Before:

```python
import os

class LLMClient:
    def __init__(self, model: str, api_key_env: str = "OPENAI_API_KEY", timeout: float = 30.0):
        self.model = model
        self.timeout = timeout
        self.api_key = os.environ.get(api_key_env, "")
        self._session = None

    def __repr__(self):
        return f"LLMClient(model={self.model!r}, timeout={self.timeout})"
```

After (`DC013`, `DC014`, `DC003`, `DC016`):

```python
import os
from dataclasses import InitVar, dataclass, field
from typing import Any, Optional

@dataclass(eq=False)                       # a client has identity; value-equality makes no sense
class LLMClient:
    model: str
    api_key_env: InitVar[str] = "OPENAI_API_KEY"
    timeout: float = 30.0
    _session: Optional[Any] = field(default=None, init=False, repr=False)
    api_key: str = field(init=False, repr=False)       # the old __repr__ hid it; keep it hidden

    def __post_init__(self, api_key_env: str) -> None:
        self.api_key = os.environ.get(api_key_env, "")
```

The script marks fields the old `__repr__` omitted as `repr=False`, which is what keeps the API key out of logs. `eq=False` is a judgement call the script leaves to you (it emits `DC016`).

## 5. Hashable value object

Before:

```python
class CacheKey:
    def __init__(self, model: str, prompt_hash: str, temperature: float):
        self.model = model
        self.prompt_hash = prompt_hash
        self.temperature = temperature

    def __eq__(self, other):
        return (self.model, self.prompt_hash, self.temperature) == (other.model, other.prompt_hash, other.temperature)

    def __hash__(self):
        return hash((self.model, self.prompt_hash, self.temperature))
```

After with `--frozen` (`DC004`, `DC005`):

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class CacheKey:
    model: str
    prompt_hash: str
    temperature: float
```

Without `--frozen` the tool emits `@dataclass(unsafe_hash=True)` to preserve behaviour exactly; recommend frozen, because a mutable key changed after insertion is lost in the dict.

If `__hash__` used only some of the compared fields, those others get `field(hash=False)` (still compared, not hashed), which is legal: equal objects still have equal hashes.

## 6. Sortable records

Before:

```python
from functools import total_ordering

@total_ordering
class EvalResult:
    def __init__(self, example_id: str, metric: str, score: float):
        self.example_id = example_id
        self.metric = metric
        self.score = score

    def __eq__(self, other):
        return (self.example_id, self.metric, self.score) == (other.example_id, other.metric, other.score)

    def __lt__(self, other):
        return (self.example_id, self.metric, self.score) < (other.example_id, other.metric, other.score)
```

After (`DC004`, `DC006`):

```python
from dataclasses import dataclass

@dataclass(order=True)
class EvalResult:
    example_id: str
    metric: str
    score: float
```

The tool only uses `order=True` when the comparison tuple equals the compared fields **in declaration order**. A `__lt__` that compares only `score` is kept as a method (and `order` is not set): `order=True` would raise `TypeError: Cannot overwrite attribute __lt__`. Often the cleanest fix is no ordering at all: `sorted(results, key=lambda r: r.score, reverse=True)`.

## 7. Embedding-carrying object

Before:

```python
import numpy as np

class RetrievedChunk:
    def __init__(self, chunk_id: str, text: str, embedding: np.ndarray, score: float = 0.0, metadata=None):
        if metadata is None:
            metadata = {}
        self.chunk_id = chunk_id
        self.text = text
        self.embedding = embedding
        self.score = score
        self.metadata = metadata
```

After (`DC002`, `DC016`, `DC017`):

```python
from dataclasses import dataclass, field

import numpy as np

@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    embedding: np.ndarray = field(compare=False, repr=False)
    score: float = 0.0
    metadata: dict = field(default_factory=dict)
```

`repr=False` on the embedding is a manual improvement (a 1536-float repr in a log line is useless). Consider `score` with `compare=False` too: two retrievals of the same chunk with different scores are usually "the same chunk".

## 8. __slots__ class

Before:

```python
class Token:
    __slots__ = ("id", "text", "logprob")

    def __init__(self, id: int, text: str, logprob: float = 0.0):
        self.id = id
        self.text = text
        self.logprob = logprob
```

After (`DC009`, 3.10+):

```python
from dataclasses import dataclass

@dataclass(slots=True)
class Token:
    id: int
    text: str
    logprob: float = 0.0
```

A manual `__slots__` plus a class-level default (`logprob: float = 0.0`) raises `ValueError: 'logprob' in __slots__ conflicts with class variable`, which is why the tool removes `__slots__`. On 3.9, keep the hand-written class or drop the defaults.

## 9. Keyword-only parameters

Before:

```python
class RetryPolicy:
    def __init__(self, max_attempts: int = 5, *, base_delay: float = 0.5, jitter: bool = True):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.jitter = jitter
```

After (`DC011`, 3.10+):

```python
from dataclasses import KW_ONLY, dataclass

@dataclass
class RetryPolicy:
    max_attempts: int = 5
    _: KW_ONLY
    base_delay: float = 0.5
    jitter: bool = True
```

On 3.9 there is no `KW_ONLY`; the fields become positional-or-keyword (less strict, still compatible with keyword callers).

## 10. dict-based code to dataclass

Before:

```python
def rerank(hits: list) -> list:
    out = []
    for h in hits:
        if h["score"] > 0.3 and h["metadata"].get("lang") == "en":
            out.append({"id": h["id"], "score": h["score"] * 1.1, "text": h["text"]})
    return sorted(out, key=lambda x: x["score"], reverse=True)
```

After:

```python
from dataclasses import dataclass, field, replace
from typing import Any

@dataclass(frozen=True)
class Hit:
    id: str
    score: float
    text: str = field(repr=False)
    metadata: dict = field(default_factory=dict, compare=False, hash=False)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Hit":
        return cls(id=d["id"], score=float(d["score"]), text=d.get("text", ""), metadata=d.get("metadata") or {})

def rerank(hits: list) -> list:
    kept = [replace(h, score=h.score * 1.1) for h in hits
            if h.score > 0.3 and h.metadata.get("lang") == "en"]
    return sorted(kept, key=lambda h: h.score, reverse=True)

hits = [Hit.from_dict(d) for d in [{"id": "a", "score": 0.5, "text": "...", "metadata": {"lang": "en"}}]]
```

Convert at the **entry point** (where the vector DB response arrives) and use attribute access everywhere after. Typos like `h["scroe"]` become type-checker errors.

Note the frozen class with a `dict` field: it works because `metadata` has `hash=False` (otherwise `hash(hit)` would raise). The dict itself stays mutable.

## 11. Tuple to NamedTuple to dataclass

Before:

```python
def search(q: str) -> list:
    return [(0.92, 17, "doc-3"), (0.88, 4, "doc-1")]

for score, idx, doc in search("q"):
    print(doc, score)
```

Step 1, NamedTuple (no caller changes):

```python
from typing import NamedTuple

class SearchHit(NamedTuple):
    score: float
    index: int
    doc_id: str

def search(q: str) -> list:
    return [SearchHit(0.92, 17, "doc-3"), SearchHit(0.88, 4, "doc-1")]
```

Step 2, dataclass, once you need methods/defaults/mutability and no caller unpacks or indexes it:

```python
from dataclasses import astuple, dataclass

@dataclass(frozen=True)
class SearchHitDC:
    score: float
    index: int
    doc_id: str

score, idx, doc = astuple(SearchHitDC(0.9, 1, "d"))   # explicit when unpacking is still needed
```

Watch for code that relies on tuple behaviour: `hit[0]`, `len(hit)`, `hit == (0.9, 1, "d")`, `sorted()` on mixed tuples, `json.dumps(hit)` (NamedTuple serializes as a list, dataclass fails).

## 12. JSON payload to classes

```bash
python scripts/to_dataclass.py json tests/fixtures/python/dc_llm_response.json --name ChatCompletion
```

Excerpt of the output:

```python
from dataclasses import dataclass, field
from typing import Any, Optional

@dataclass
class Message:
    role: str
    content: Optional[str] = None
    refusal: Any = None
    tool_calls: Optional[list] = None      # generator emits list of ToolCall; shortened here

@dataclass
class Gateway:
    x_request_id: str = field(metadata={"json_key": "x-request-id"})
    latency_ms: float = field(metadata={"json_key": "latencyMs"})
    received_at: str = field(metadata={"json_key": "receivedAt"})  # ISO-8601 string
    class_: str = field(metadata={"json_key": "class"})
```

What the generator decided:

- `content` was a string in one choice and `null` in another -> `Optional[str]`.
- `tool_calls` was missing from one message -> `Optional[...] = None`.
- `refusal` was only ever `null` -> `Any`: replace with the real type from the API docs.
- `x-request-id`, `latencyMs`, `class` became valid identifiers; the wire key is kept in `metadata` and used by the generated `from_dict()`.
- Optional fields were moved after required ones (default-ordering rule).

After generating: delete classes you do not need, replace `Any`s, convert `created` epoch ints to `datetime` if useful, and decide whether the boundary should be pydantic instead (`--style pydantic`).

## 13. Skipped: inheritance with super().__init__

```python
class BaseClient:
    def __init__(self, model: str, timeout: float = 30.0):
        self.model = model
        self.timeout = timeout

class AnthropicClient(BaseClient):
    def __init__(self, model: str, max_retries: int = 3):
        super().__init__(model, timeout=60.0)
        self.max_retries = max_retries
```

The tool reports `S04` for the subclass. Convert the base first, then express the overridden default as a field redefinition:

```python
from dataclasses import dataclass

@dataclass
class BaseClient:
    model: str
    timeout: float = 30.0

@dataclass
class AnthropicClient(BaseClient):
    timeout: float = 60.0         # redefined: keeps its position, new default
    max_retries: int = 3
```

Check the new signature: `AnthropicClient(model, timeout=60.0, max_retries=3)` now accepts `timeout`, which the old one did not. If that matters, use `timeout: float = field(default=60.0, init=False)`.

## 14. Skipped: renamed attributes

```python
class VectorStoreAdapter:
    def __init__(self, client):
        self._client = client
```

`S05`: a dataclass field `_client` would make the constructor argument `_client`, breaking `VectorStoreAdapter(client=...)`. Options: keep the hand-written `__init__`; or use a public field name; or

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass(eq=False)
class VectorStoreAdapter:
    client: Any = field(repr=False)

    @property
    def _client(self) -> Any:          # keep old internal name working during migration
        return self.client
```

## 15. Skipped: *args / **kwargs

```python
class StreamingHandler:
    def __init__(self, *callbacks):
        self.callbacks = list(callbacks)
```

`S03`. Either keep it, or change the API to an explicit list and add a convenience constructor:

```python
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class StreamingHandler:
    callbacks: list = field(default_factory=list)

    @classmethod
    def of(cls, *callbacks: Callable) -> "StreamingHandler":
        return cls(list(callbacks))
```

`**kwargs` constructors that `self.__dict__.update(kwargs)` should become explicit fields plus an `extra: dict` field if open-ended keys are really needed.

## 16. Skipped: exceptions

```python
class RateLimitError(Exception):
    def __init__(self, retry_after: float):
        super().__init__(f"rate limited, retry after {retry_after}s")
        self.retry_after = retry_after
```

`S07`. A dataclass `__init__` would not call `Exception.__init__`, so `e.args` is empty and `str(e)` is `""`; frozen dataclass exceptions also fail wherever library code assigns `__traceback__` (contextlib does), and `eq=True` makes them unhashable. Keep exceptions hand-written. If you insist, use `eq=False`, no `frozen`, and call `super().__init__(...)` in `__post_init__`:

```python
from dataclasses import dataclass

@dataclass(eq=False)
class RateLimitErrorDC(Exception):
    retry_after: float

    def __post_init__(self) -> None:
        super().__init__(f"rate limited, retry after {self.retry_after}s")
```

## 17. Dataclass to pydantic at a boundary

Before (dataclass parsed from a request body by hand):

```python
from dataclasses import dataclass, field

@dataclass
class IngestRequest:
    doc_id: str
    text: str
    chunk_size: int = 800
    tags: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("text must not be empty")
        if not 100 <= self.chunk_size <= 4000:
            raise ValueError("chunk_size out of range")
```

After (pydantic v2):

```python
from pydantic import BaseModel, ConfigDict, Field

class IngestRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    text: str = Field(min_length=1)
    chunk_size: int = Field(default=800, ge=100, le=4000)
    tags: list[str] = Field(default_factory=list)
```

Mapping table:

| dataclass | pydantic v2 |
|-----------|-------------|
| `field(default_factory=list)` | `Field(default_factory=list)` (or plain `[]`: pydantic copies defaults) |
| `field(repr=False)` | `Field(repr=False)` |
| `field(compare=False)` | no direct equivalent; override `__eq__` or exclude via a custom key |
| `field(init=False)` + `__post_init__` | `@computed_field` property or `PrivateAttr` + `model_post_init` |
| `__post_init__` validation | `Field` constraints, `@field_validator`, `@model_validator(mode="after")` |
| `frozen=True` | `ConfigDict(frozen=True)` |
| `replace(obj, x=1)` | `obj.model_copy(update={"x": 1})` (no validation) or `Model.model_validate({**obj.model_dump(), "x": 1})` |
| `asdict(obj)` | `obj.model_dump()` |
| positional construction | keyword only |

## 18. Verification checklist

Run these against every converted class (pytest-style):

```python
import copy
import dataclasses
import pickle

def check_converted(cls, *args, **kwargs):
    a = cls(*args, **kwargs)
    b = cls(*args, **kwargs)
    assert a == b, "value equality"                       # unless eq=False on purpose
    repr(a)                                               # no AttributeError from unset init=False fields
    c = dataclasses.replace(a)                            # __post_init__ re-runs without error
    assert c == a
    pickle.loads(pickle.dumps(a))                         # needed for multiprocessing / caching
    copy.deepcopy(a)
    params = cls.__dataclass_params__
    if params.frozen or params.unsafe_hash:
        hash(a)
    return a
```

Also: run the test suite, grep for positional constructor calls if you used `kw_only`, grep for `hash(`, `set(`, dict-key usage when `eq=True` was introduced, and run mypy/pyright to catch `Any`s left by inference.
