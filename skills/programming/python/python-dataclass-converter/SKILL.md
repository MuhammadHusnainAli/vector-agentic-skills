---
name: python-dataclass-converter
description: "Convert boilerplate Python classes, dicts, tuples and JSON payloads into dataclasses, or into pydantic v2 BaseModel, TypedDict, NamedTuple, attrs or msgspec when that fits better. Covers every @dataclass option (frozen, slots, kw_only, order, unsafe_hash, match_args, weakref_slot), field() (default_factory, init=False, repr, compare, hash, metadata), __post_init__, InitVar, KW_ONLY, inheritance and default ordering, replace(), asdict deep-copy pitfalls, hashing/equality, serialization and validation. AI focus: LLM request/response and chat Message types, RAG chunks with embeddings (numpy eq gotcha), eval records, configs, typed OpenAI/Anthropic JSON. Use when the user asks to convert a class or dict to a dataclass, remove __init__/__repr__/__eq__ boilerplate, model a JSON/API response with types, pick dataclass vs pydantic vs TypedDict, or fix dataclass errors (mutable default, non-default argument follows default argument, FrozenInstanceError, unhashable type)."
metadata:
  category: programming
  subcategory: python
  version: "1.0.0"
---

# Python Dataclass Converter

Turn hand-written data-holding classes, loose `dict`s, positional tuples and raw JSON payloads into precise, typed data containers. The default target is `@dataclass` for internal objects; pydantic v2 is chosen at trust boundaries that need validation, `TypedDict` when the data must stay a plain dict, `NamedTuple` for small immutable records that are unpacked, attrs or msgspec when converters or decode speed matter. Every conversion must preserve behaviour (constructor signature, equality, hashing, repr secrecy) or state exactly what changed.

## Trigger Conditions

Activate this skill when the user:
- Asks to "convert this class to a dataclass", "remove the __init__ boilerplate", "make this a dataclass / pydantic model / TypedDict"
- Pastes a JSON sample or API response (OpenAI, Anthropic, a vector DB, a webhook) and wants typed classes for it
- Passes `dict`s or tuples around (`msg["role"]`, `row[2]`) and wants named, typed fields
- Hits `ValueError: mutable default <class 'list'> for field ... is not allowed`, `TypeError: non-default argument 'x' follows default argument`, `FrozenInstanceError`, `TypeError: unhashable type`, or `The truth value of an array with more than one element is ambiguous` from a dataclass `__eq__`
- Asks about `field()`, `__post_init__`, `InitVar`, `KW_ONLY`, `slots=True`, `frozen=True`, `replace()`, `asdict()`
- Designs config objects, LLM request/response types, chat messages, RAG chunks, eval records

## Workflow

```
1. INVENTORY  -> list the classes/dicts/JSON to convert; run scripts/to_dataclass.py class|json
2. CLASSIFY   -> pick the container per object (decision table below): boundary vs internal
3. CONVERT    -> fields + defaults + options; move logic to __post_init__; drop redundant dunders
4. PRESERVE   -> check constructor signature, eq/hash identity semantics, repr secrets, ordering
5. SERIALIZE  -> decide to/from JSON path (asdict, from_dict, pydantic, msgspec)
6. VERIFY     -> construct, compare, hash, round-trip JSON; run tests and type checker
```

## Choosing the Container

| Situation | Use | Why |
|-----------|-----|-----|
| Internal domain object, trusted inputs (Chunk, EvalResult, RunState) | `@dataclass` | stdlib, zero deps, fast, explicit |
| Immutable config / cache key / dict key | `@dataclass(frozen=True)` (+ `slots=True` 3.10+) | hashable, safe to share across threads |
| Untrusted input: HTTP body, LLM JSON output, env, YAML files | pydantic v2 `BaseModel` | validation, coercion, error messages, JSON schema |
| Tool/function-calling schema for an LLM | pydantic `BaseModel` + `model_json_schema()` | schema generation |
| Must remain a `dict` (passed to `json.dumps`, SDK `messages=[...]`) | `TypedDict` | static typing only, zero runtime cost |
| Tiny immutable record you unpack (`score, idx = hit`) | `typing.NamedTuple` | tuple semantics, positional |
| Converters/validators without pydantic | attrs `@define` | `field(converter=...)`, validators |
| Hot decode path (millions of JSON lines, streaming events) | `msgspec.Struct` | very fast decode + validation |

Rule of thumb: **validate at the edge (pydantic), compute in the core (dataclasses)**. Convert once at the boundary, then pass dataclasses around. Full matrix: [choosing-a-data-container.md](references/choosing-a-data-container.md).

## Conversion Rules

### 1. Fields come from `__init__` parameters, in order

```python
# Before
class RetrievedChunk:
    def __init__(self, chunk_id: str, text: str, score: float = 0.0, metadata: dict | None = None):
        self.chunk_id = chunk_id
        self.text = text
        self.score = score
        self.metadata = metadata if metadata is not None else {}

# After
from dataclasses import dataclass, field

@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    score: float = 0.0
    metadata: dict = field(default_factory=dict)
```

- Keep parameter order: positional call sites (`RetrievedChunk("c1", "text")`) must keep working.
- Keep annotations; infer from defaults when missing; use `Any` and flag it rather than guess.
- `x: T = None` without `Optional` -> write `Optional[T]` / `T | None` (3.10+).
- The `None` sentinel + `or []` idiom becomes `default_factory`. Behaviour change to mention: passing `None` explicitly now stores `None`.

### 2. Mutable defaults always use `default_factory`

| Original default | Dataclass |
|------------------|-----------|
| `tags=[]` (shared-list bug) | `tags: list[str] = field(default_factory=list)` |
| `meta={}` | `field(default_factory=dict)` |
| `stop=["\n\n"]` | `field(default_factory=lambda: ["\n\n"])` |
| `self._cache = {}` in `__init__` | `_cache: dict = field(default_factory=dict, init=False, repr=False, compare=False)` |
| `self._lock = threading.Lock()` | `_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False, compare=False)` |

The decorator rejects unhashable defaults (`list`, `dict`, `set`, and since 3.11 any instance whose class sets `__hash__ = None`) with `ValueError`. Defaults that are other mutable objects (a `Tokenizer()` instance) are silently shared: use a factory.

### 3. Logic goes into `__post_init__`; construction-only params become `InitVar`

```python
import os
from dataclasses import InitVar, dataclass, field

@dataclass
class LLMClient:
    model: str
    api_key_env: InitVar[str] = "OPENAI_API_KEY"
    timeout: float = 30.0
    api_key: str = field(init=False, repr=False)       # never printed in logs

    def __post_init__(self, api_key_env: str) -> None:
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        self.api_key = os.environ.get(api_key_env, "")
```

- Validation (`if ...: raise`), normalisation (`self.model = self.model.strip()`) and derived attributes all move to `__post_init__`; parameter names become `self.<name>`.
- A parameter that is used but never stored becomes `InitVar[T]`; it is passed to `__post_init__` in field order and is excluded from `fields()`, `asdict()` and `repr`.
- Derived attributes are `field(init=False)`; give them a default if they are only set conditionally, otherwise `repr()` raises `AttributeError`.
- Subclasses must call `super().__post_init__(...)` themselves.

### 4. Frozen classes write through `object.__setattr__`

```python
@dataclass(frozen=True, slots=True)
class PromptTemplate:
    template: str
    variables: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.variables:
            import string
            names = tuple(n for _, n, _, _ in string.Formatter().parse(self.template) if n)
            object.__setattr__(self, "variables", names)
```

Methods that mutated `self` must return a new instance: `dataclasses.replace(cfg, temperature=0.0)` (or `copy.replace` 3.13+). Store tuples / `frozenset` / `MappingProxyType` in frozen classes; a frozen class holding a `list` is only shallowly immutable and unhashable.

### 5. Drop dunders the decorator generates, but keep semantics

| Hand-written | Replace with | Watch out |
|--------------|-------------|-----------|
| `__init__` that only stores params | fields | rename `self._x = x` breaks keyword callers: keep a manual `__init__` or a property |
| `__repr__` listing fields | `repr=True` (default) | fields it hid (API keys, embeddings) -> `field(repr=False)` |
| `__eq__` comparing a tuple of fields | `eq=True` (default) | fields it ignored -> `field(compare=False)`; dataclass requires the same class, not `isinstance` |
| `__hash__` over fields | `frozen=True` (preferred) or `unsafe_hash=True` | fields not hashed -> `field(hash=False)` |
| `__lt__` + `total_ordering` on a field tuple in field order | `order=True` | ordering is by field order; otherwise keep the method |
| `__slots__ = (...)` | `slots=True` (3.10+) | manual `__slots__` conflicts with defaults |
| no `__eq__` at all | `eq=False` if identity semantics are needed | `eq=True` sets `__hash__ = None`: objects stop working as dict keys / set members |

### 6. Arrays and tensors never take part in `eq`/`hash`

```python
import numpy as np
from dataclasses import dataclass, field

@dataclass
class Embedded:
    doc_id: str
    vector: np.ndarray = field(compare=False, repr=False)

    def same_vector(self, other: "Embedded", atol: float = 1e-6) -> bool:
        return self.vector.shape == other.vector.shape and bool(np.allclose(self.vector, other.vector, atol=atol))
```

Generated `__eq__` compares field values like tuples; `array == array` returns an array and `bool(array)` raises `ValueError: The truth value of an array ... is ambiguous` (it "works" only when both sides are the same object). The same applies to `torch.Tensor`, pandas objects and anything whose `==` is element-wise.

### 7. Inheritance and default ordering

```python
@dataclass
class BaseRequest:
    model: str
    temperature: float = 0.7

@dataclass(kw_only=True)            # 3.10+: avoids "non-default argument follows default argument"
class ChatRequest(BaseRequest):
    messages: list["Message"]
    stream: bool = False
```

Fields are collected base-first. A subclass field without a default after a base field with a default raises `TypeError` unless it is keyword-only (`kw_only=True`, `field(kw_only=True)` or after `_: KW_ONLY`). On 3.9, give the subclass field a default or use composition. Frozen and non-frozen dataclasses cannot inherit from each other.

## Option Cheat-Sheet

| Option | Default | Effect | Version |
|--------|---------|--------|---------|
| `init` | True | generate `__init__` | 3.7 |
| `repr` | True | generate `__repr__` | 3.7 |
| `eq` | True | generate `__eq__` (same class, field-wise) | 3.7 |
| `order` | False | `__lt__`/`__le__`/`__gt__`/`__ge__` by field tuple | 3.7 |
| `unsafe_hash` | False | force `__hash__` even if mutable | 3.7 |
| `frozen` | False | assignment raises `FrozenInstanceError` | 3.7 |
| `match_args` | True | `__match_args__` for `match` positional patterns | 3.10 |
| `kw_only` | False | all fields keyword-only | 3.10 |
| `slots` | False | create `__slots__`, no `__dict__` | 3.10 |
| `weakref_slot` | False | add `__weakref__` slot (needs `slots=True`) | 3.11 |

`field()` parameters: `default`, `default_factory`, `init`, `repr`, `hash`, `compare`, `metadata`, `kw_only` (3.10), `doc` (3.14). Full semantics, hash table and error catalogue: [dataclass-reference.md](references/dataclass-reference.md).

## asdict / astuple / replace Pitfalls

- `asdict()` recurses into dataclasses, lists, tuples and dicts and **`copy.deepcopy`s everything else**: a field holding a 100 MB `np.ndarray` is copied; a field holding a client, lock or open file raises `TypeError: cannot pickle ...`. Use `fields()` + `getattr` for a shallow dict, or mark the field and skip it.
- `asdict()` keeps `Enum`, `datetime`, `Path`, `Decimal` objects as-is: `json.dumps` then fails. Pass `default=` or write a `to_json_dict()`.
- `replace()` calls `__init__` again: `__post_init__` re-runs, `init=False` fields are recomputed (not copied), `InitVar`s without defaults must be passed.
- `fields()` excludes `ClassVar` and `InitVar` pseudo-fields.

Serialization patterns (json, nested, enums, datetimes, numpy) and validation strategies: [serialization-and-validation.md](references/serialization-and-validation.md).

## AI-Engineering Patterns (summary)

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Optional

class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: str          # raw JSON string from the model; parse+validate at the edge

@dataclass(slots=True)
class Message:
    role: Role
    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: Optional[str] = None

    def to_api(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role.value, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = [{"id": t.id, "type": "function",
                                "function": {"name": t.name, "arguments": t.arguments}} for t in self.tool_calls]
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d

@dataclass(frozen=True)
class GenerationConfig:
    model: str
    temperature: float = 0.0
    max_tokens: int = 1024
    stop: tuple[str, ...] = ()
    response_format: Literal["text", "json_object"] = "text"
```

- Configs: frozen dataclass, built once from YAML/env (validated with pydantic or a `from_env` classmethod), hashed into cache keys and run names.
- Requests/responses: dataclass with `to_api()` / `from_api()`; pydantic when parsing model output that may be malformed.
- Chunks/documents: `embedding` field with `compare=False, repr=False`; identity by `chunk_id`.
- Eval records: `order=True` or `sorted(key=...)`; `asdict()` straight into a DataFrame / JSONL.

Full patterns (training/inference configs, streaming deltas, Anthropic content blocks, vector store records, eval harness rows): [ai-engineering-models.md](references/ai-engineering-models.md).

## Anti-Patterns to Fix

| Smell | Fix |
|-------|-----|
| `def __init__(self, tags=[])` | `field(default_factory=list)` |
| `@dataclass` on a class that is used in a `set` / as dict key, without `frozen` | `frozen=True`, or `eq=False` to keep identity |
| `@dataclass` with `np.ndarray` field and default `eq` | `field(compare=False)` |
| `api_key: str` printed by `repr` into logs | `field(repr=False)` |
| `asdict(obj)` on objects holding clients/locks | custom `to_dict()` over `fields()` |
| `dict[str, Any]` passed through 5 layers | dataclass at the boundary, typed access inside |
| pydantic model for every internal struct in a hot loop | dataclass internally, pydantic only at the edge |
| `self.__dict__.update(kwargs)` constructors | explicit fields; reject unknown keys |
| Field type `Optional[list]` with default `None` and `or []` everywhere | non-optional `list` + `default_factory` |
| Subclass field breaks default ordering | `kw_only=True` (3.10+) or composition |

## Output Format

When converting, provide:

1. **Container choice** per object with one-line reason (boundary vs internal, mutability, hashing).
2. **Converted code**: imports, decorator options, fields, `__post_init__`, kept methods.
3. **Behaviour changes**: constructor signature, equality/hash semantics, repr output, explicit-`None` handling, version requirements (3.10 for `kw_only`/`slots`/`KW_ONLY`).
4. **Serialization path** if the object crosses a JSON/API boundary (`from_dict`, `model_validate`, `asdict`).
5. **Verification snippet**: construct, compare, hash, `replace`, JSON round-trip.

## Scripts

`scripts/to_dataclass.py` is static analysis only (it parses, never imports or runs the code):

```bash
# Convert boilerplate classes in a module; prints imports, notes with rule ids and @dataclass code
python scripts/to_dataclass.py class models.py
python scripts/to_dataclass.py class models.py --frozen --slots --kw-only
python scripts/to_dataclass.py class models.py --json --strict    # exit 1 if anything is convertible
cat models.py | python scripts/to_dataclass.py class -

# Generate nested typed classes from a JSON sample (object or list of objects)
python scripts/to_dataclass.py json response.json --name ChatCompletion                  # dataclasses + from_dict()
python scripts/to_dataclass.py json response.json --name ChatCompletion --style pydantic # BaseModel + Field(alias=)
python scripts/to_dataclass.py json events.json --name Event --style typeddict --json
```

Class mode findings: `DC001` mutable default, `DC002` None-sentinel default, `DC003`/`DC004` redundant `__repr__`/`__eq__`, `DC005` `__hash__` -> frozen/unsafe_hash, `DC006` ordering -> `order=True`, `DC007` inferred/missing annotation, `DC008` logic moved to `__post_init__`, `DC009` slots, `DC010` ClassVar, `DC011` keyword-only, `DC012` positional-only, `DC013` InitVar, `DC014` internal state field, `DC015` mutation under frozen, `DC016` identity-eq/hash change, `DC017` array field excluded from eq, `DC018` shared call default, `DC019` implicit Optional. Skips: `S01` already declarative, `S02` no `__init__`, `S03` `*args/**kwargs`, `S04` `super().__init__`, `S05` attribute renamed, `S06` parameter reassigned after storing, `S07` special base (Exception, Enum, BaseModel...), `S08` metaclass/`__new__`, `S09` return/yield in `__init__`, `S10` nothing stored. JSON mode merges types across list items, marks missing/null keys `Optional`, snake_cases keys (aliases kept in `metadata["json_key"]` or `Field(alias=)`) and flags ISO-8601 strings. Exit codes: 0 ok, 1 with `--strict` when convertible classes exist, 2 on read/parse/usage errors. Always review the output: it cannot see call sites.

## Additional Resources

| File | Content |
|------|---------|
| [dataclass-reference.md](references/dataclass-reference.md) | Every decorator option and `field()` parameter, `__post_init__`, `InitVar`, `KW_ONLY`, inheritance, hash/eq table, slots, `replace`/`asdict`/`fields`, error catalogue, performance |
| [choosing-a-data-container.md](references/choosing-a-data-container.md) | dataclass vs pydantic v2 vs TypedDict vs NamedTuple vs attrs vs msgspec vs plain class, with side-by-side code |
| [serialization-and-validation.md](references/serialization-and-validation.md) | JSON in/out, nested objects, enums, datetimes, numpy, aliases, YAML/env config loading, validation strategies |
| [ai-engineering-models.md](references/ai-engineering-models.md) | Configs, LLM requests/responses, chat messages, tool calls, streaming, RAG chunks with embeddings, eval records, OpenAI/Anthropic JSON to typed objects |
| [conversion-examples.md](references/conversion-examples.md) | Worked before/after conversions, including the tricky ones the script skips |
