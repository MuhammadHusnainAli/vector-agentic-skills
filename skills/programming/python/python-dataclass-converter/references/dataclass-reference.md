# Dataclass Reference

Complete reference for `dataclasses` (Python 3.9 baseline, newer features tagged). Examples use AI-engineering objects but every rule is general.

## Contents

1. [What the decorator does](#what-the-decorator-does)
2. [Decorator options](#decorator-options)
3. [field() parameters](#field-parameters)
4. [Default values and default_factory](#default-values-and-default_factory)
5. [__post_init__ and InitVar](#__post_init__-and-initvar)
6. [Keyword-only fields and KW_ONLY](#keyword-only-fields-and-kw_only)
7. [Inheritance and field ordering](#inheritance-and-field-ordering)
8. [Equality, ordering and hashing](#equality-ordering-and-hashing)
9. [frozen=True](#frozentrue)
10. [slots=True and weakref_slot](#slotstrue-and-weakref_slot)
11. [Module functions](#module-functions)
12. [ClassVar, descriptors and properties](#classvar-descriptors-and-properties)
13. [Pattern matching](#pattern-matching)
14. [Generics](#generics)
15. [Performance and memory](#performance-and-memory)
16. [Error catalogue](#error-catalogue)

## What the decorator does

`@dataclass` inspects the class `__annotations__` at class-creation time. Every annotated name that is not a `ClassVar` (and not an `InitVar`, which is a pseudo-field) becomes a field, in definition order. It then **adds** methods to the class: `__init__`, `__repr__`, `__eq__`, and optionally ordering methods, `__hash__`, `__setattr__`/`__delattr__` (frozen), `__match_args__`, `__slots__`. It does **not** add runtime type checking: annotations are documentation for type checkers.

```python
from dataclasses import dataclass

@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int = 0

u = TokenUsage(12, 30)
print(u)                         # TokenUsage(prompt_tokens=12, completion_tokens=30)
print(u == TokenUsage(12, 30))   # True
TokenUsage("12")                 # accepted at runtime: no validation
```

Rules for whether a generated method replaces one you wrote:

| Method | If you define it in the class body |
|--------|------------------------------------|
| `__init__`, `__repr__`, `__eq__` | yours is kept (decorator skips it) |
| `__lt__`/`__le__`/`__gt__`/`__ge__` with `order=True` | `TypeError` |
| `__setattr__`/`__delattr__` with `frozen=True` | `TypeError` |
| `__hash__` | see [hash table](#equality-ordering-and-hashing) |

Introspection attributes: `cls.__dataclass_fields__` (dict name -> `Field`), `cls.__dataclass_params__`, `cls.__match_args__` (3.10+).

## Decorator options

```text
@dataclass(init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False,
           match_args=True, kw_only=False, slots=False, weakref_slot=False)
```

| Option | Default | Generates / changes | Since |
|--------|---------|---------------------|-------|
| `init` | `True` | `__init__(self, <init fields>)`; calls `__post_init__` if defined | 3.7 |
| `repr` | `True` | `__repr__` as `Cls(a=1, b='x')` over `repr=True` fields; recursion-safe | 3.7 |
| `eq` | `True` | `__eq__` comparing compare-fields in order; `NotImplemented` for a different class | 3.7 |
| `order` | `False` | `__lt__`, `__le__`, `__gt__`, `__ge__` comparing field tuples; requires `eq=True` | 3.7 |
| `unsafe_hash` | `False` | force a field-based `__hash__` even when mutable | 3.7 |
| `frozen` | `False` | assignment/deletion raise `FrozenInstanceError` | 3.7 |
| `match_args` | `True` | `__match_args__` = names of positional init fields | 3.10 |
| `kw_only` | `False` | every field keyword-only in `__init__` | 3.10 |
| `slots` | `False` | returns a **new class** with `__slots__` | 3.10 |
| `weakref_slot` | `False` | add `__weakref__` slot; requires `slots=True` | 3.11 |

The decorator can be used bare (`@dataclass`) or called (`@dataclass(frozen=True)`).

### Choosing options quickly

| Need | Options |
|------|---------|
| Plain mutable record | `@dataclass` |
| Config / cache key / dict key | `@dataclass(frozen=True)` |
| Many instances (chunks, tokens, events) | `@dataclass(slots=True)` 3.10+ |
| Immutable and compact | `@dataclass(frozen=True, slots=True)` |
| Sortable results | `@dataclass(order=True)` with sort key first, or `field(compare=False)` on the rest |
| Identity semantics (objects with resources, graph nodes) | `@dataclass(eq=False)` |
| Long constructor, avoid positional mistakes | `@dataclass(kw_only=True)` 3.10+ |

## field() parameters

```text
dataclasses.field(*, default=MISSING, default_factory=MISSING, init=True, repr=True,
                  hash=None, compare=True, metadata=None, kw_only=MISSING, doc=None)
```

| Parameter | Meaning | Typical use |
|-----------|---------|-------------|
| `default` | default value (immutable!) | `field(default=0, repr=False)` when combining with other options |
| `default_factory` | zero-arg callable invoked per instance | `list`, `dict`, `lambda: ["\n"]`, `uuid.uuid4`, `time.time` |
| `init` | include in `__init__` | `False` for derived/internal state |
| `repr` | include in `__repr__` | `False` for secrets, embeddings, big blobs |
| `hash` | include in `__hash__`; `None` = follow `compare` | `False` for a field compared but not hashed |
| `compare` | include in `__eq__`/ordering | `False` for arrays, timestamps, caches |
| `metadata` | read-only mapping, ignored by dataclasses | JSON aliases, units, CLI help |
| `kw_only` | this field keyword-only | 3.10+ |
| `doc` | docstring for the field (shown by `help()`) | 3.14+ |

`default` and `default_factory` are mutually exclusive (`ValueError`). `field(init=False)` without a default leaves the attribute unset until `__post_init__` assigns it; `repr()` before that raises `AttributeError`.

```python
import time
import uuid
from dataclasses import dataclass, field, fields

@dataclass
class TraceSpan:
    name: str
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    started_at: float = field(default_factory=time.time, compare=False)
    attributes: dict = field(default_factory=dict)
    cost_usd: float = field(default=0.0, metadata={"unit": "USD"})

print([(f.name, f.metadata.get("unit")) for f in fields(TraceSpan)])
```

## Default values and default_factory

Defaults are evaluated **once** at class creation and stored as class attributes. That is why mutable defaults are rejected:

```python
from dataclasses import dataclass, field

@dataclass
class Bad:
    tags: list = []           # ValueError: mutable default <class 'list'> for field tags is not allowed: use default_factory

@dataclass
class Good:
    tags: list = field(default_factory=list)
```

- Before 3.11 the check rejected only `list`, `dict`, `set`. Since 3.11 it rejects any default whose class is unhashable (`__hash__ is None`), e.g. an instance of a non-frozen dataclass with `eq=True`.
- Hashable but mutable objects (a `Tokenizer()` instance, a `requests.Session()`) pass the check and are **shared** by all instances. Use `default_factory=Tokenizer`.
- A factory with arguments: `field(default_factory=lambda: defaultdict(list))` or `functools.partial(...)`.
- `default_factory` is not called if a value is passed to `__init__`.
- Fields with `init=False` and a `default_factory` still get the factory value in `__init__`.

Immutable alternatives that work as plain defaults: `()`, `frozenset()`, `""`, `0`, `None`, enum members, instances of frozen dataclasses. A read-only mapping (`MappingProxyType`) is unhashable, so give it a factory.

## __post_init__ and InitVar

The generated `__init__` assigns fields and then calls `self.__post_init__(*initvars)` if the method exists.

```python
from dataclasses import InitVar, dataclass, field
from typing import Optional

@dataclass
class Chunk:
    text: str
    doc_id: str
    tokenizer: InitVar[Optional[object]] = None
    n_tokens: int = field(init=False)
    normalized: str = field(init=False, repr=False)

    def __post_init__(self, tokenizer: Optional[object]) -> None:
        if not self.text:
            raise ValueError("empty chunk")
        self.normalized = " ".join(self.text.split())
        self.n_tokens = len(tokenizer.encode(self.text)) if tokenizer else len(self.text) // 4
```

Rules:

- `InitVar[T]` fields appear in `__init__` (respecting default rules) and are passed positionally to `__post_init__` in declaration order. They are not stored, not in `fields()`, `asdict()`, `repr`, `eq`.
- If a class-level default is given to an `InitVar`, that value is also set as a class attribute (a quirk: `Chunk.tokenizer` is `None`).
- `replace()` requires every `InitVar` without a default to be passed explicitly (`ValueError` on older versions, `TypeError` on recent ones).
- `__post_init__` is not called when `init=False` is passed to the decorator.
- Inheritance: the generated `__init__` calls `self.__post_init__`, which resolves to the most-derived one. Call `super().__post_init__(...)` explicitly when a base also has one.
- Do expensive work lazily (a property or `functools.cached_property`, not available with `slots=True`) rather than in `__post_init__` when objects are created in bulk.

```python
@dataclass
class BaseRecord:
    id: str
    def __post_init__(self) -> None:
        self.id = self.id.strip()

@dataclass
class EvalRecord(BaseRecord):
    score: float = 0.0
    def __post_init__(self) -> None:
        super().__post_init__()
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("score must be in [0, 1]")
```

## Keyword-only fields and KW_ONLY

Three ways (all 3.10+):

```python
from dataclasses import KW_ONLY, dataclass, field

@dataclass(kw_only=True)
class A:
    model: str
    temperature: float = 0.7

@dataclass
class B:
    model: str
    _: KW_ONLY                   # everything after the sentinel is keyword-only
    temperature: float = 0.7
    seed: int                    # no default after a default: allowed because keyword-only

@dataclass
class C:
    model: str
    seed: int = field(kw_only=True, default=0)
```

Keyword-only fields are moved **after** all positional fields in the generated `__init__`, regardless of declaration order, and are excluded from `__match_args__`. On 3.9 there is no keyword-only support: order fields so defaults come last, or write `__init__` by hand.

## Inheritance and field ordering

Fields are gathered in MRO order (base first). A field redefined in a subclass keeps its original position but takes the new type/default.

```python
from dataclasses import dataclass, field

@dataclass
class BaseRequest:
    model: str
    temperature: float = 0.7

@dataclass
class ChatRequest(BaseRequest):
    messages: list = field(default_factory=list)   # has a default: OK

@dataclass
class Broken(BaseRequest):
    messages: list                                  # TypeError: non-default argument 'messages' follows default argument
```

Fixes for `Broken`: give `messages` a default; make the subclass `kw_only=True` (3.10+); use `field(kw_only=True)`; or prefer composition (`request: BaseRequest`).

Other inheritance rules:

| Situation | Result |
|-----------|--------|
| frozen subclass of non-frozen dataclass (or vice versa) | `TypeError: cannot inherit frozen dataclass from a non-frozen one` |
| dataclass subclass of a plain class with its own `__init__` | base `__init__` is **not** called by the generated one; call it from `__post_init__` or convert the base |
| plain subclass of a dataclass | inherits fields and methods; annotations in the subclass are not fields unless decorated |
| `slots=True` base and subclass | each must be decorated with `slots=True` for full slot coverage |
| multiple inheritance | fields merged in reverse MRO; keep it shallow |

## Equality, ordering and hashing

`__eq__` returns `NotImplemented` unless `other.__class__ is self.__class__`, then compares compare-fields in order as if they were tuples. Subclass instances are therefore never equal to base instances.

`order=True` compares `(f1, f2, ...)` tuples of compare-fields: put the sort key first or use `sorted(key=...)` instead.

```python
from dataclasses import dataclass, field

@dataclass(order=True)
class RankedHit:
    neg_score: float                         # sort key first: best score first when ascending
    chunk_id: str = field(compare=True)
    text: str = field(compare=False)

hits = sorted([RankedHit(-0.8, "b", "..."), RankedHit(-0.9, "a", "...")])
```

### Hash generation table

`__hash__` is decided from `unsafe_hash`, `eq`, `frozen` and whether the class body defines `__hash__` explicitly:

| unsafe_hash | eq | frozen | explicit `__hash__` in class | Result |
|-------------|----|--------|------------------------------|--------|
| False | True | False | no | `__hash__ = None` (unhashable) |
| False | True | True | no | generated from hash-fields |
| False | False | any | no | inherited (`object.__hash__`, identity) |
| False | any | any | yes | yours is kept |
| True | any | any | no | generated from hash-fields |
| True | any | any | yes | `TypeError` |

Hash-fields are fields with `hash=True`, or `hash=None` and `compare=True`. Consequences:

- Converting a plain class to `@dataclass` makes instances **unhashable**: `set()` of them, `lru_cache` arguments and dict keys break. Use `frozen=True`, or `eq=False` to keep identity.
- `unsafe_hash=True` on a mutable object: mutating a hashed field while the object sits in a `set` corrupts the set.
- A frozen dataclass containing a `list` or `np.ndarray` field raises `TypeError: unhashable type` only when `hash()` is called: use tuples or `hash=False`.

## frozen=True

```python
from dataclasses import FrozenInstanceError, dataclass, replace

@dataclass(frozen=True)
class SamplingParams:
    temperature: float = 0.7
    top_p: float = 1.0

p = SamplingParams()
try:
    p.temperature = 0.0
except FrozenInstanceError as e:        # subclass of AttributeError
    print(e)                            # cannot assign to field 'temperature'
greedy = replace(p, temperature=0.0)
```

- In `__post_init__` (or any method) use `object.__setattr__(self, "name", value)`.
- Frozen is shallow: `frozen.items.append(x)` still works if `items` is a list.
- Cost: frozen `__init__` uses `object.__setattr__` for every field, measurably slower for millions of objects.
- `copy.replace(obj, **changes)` works on dataclasses from 3.13 (`__replace__`).

## slots=True and weakref_slot

`slots=True` (3.10+) makes the decorator build a **new class** with `__slots__` derived from the fields.

Benefits: lower memory per instance, faster attribute access, typos like `obj.scroe = 1` raise `AttributeError`.

Caveats:

| Caveat | Detail |
|--------|--------|
| New class object | decorators applied before `@dataclass` see the old class; references captured at class creation point to the old one |
| Zero-arg `super()` | broken in methods of `slots=True` dataclasses on 3.10-3.13 (`TypeError`), fixed in 3.14; use `super(Cls, self)` when supporting older versions |
| `functools.cached_property` | needs `__dict__`; fails with `slots=True` |
| `__weakref__` | not available unless `weakref_slot=True` (3.11+) - needed for `weakref.ref`, `WeakValueDictionary` caches |
| Manual `__slots__` | do not combine with `slots=True`; a manual `__slots__` plus field defaults raises `ValueError: 'x' in __slots__ conflicts with class variable` |
| Pickling | supported; frozen + slots classes get generated `__getstate__`/`__setstate__` |
| Adding attributes dynamically | impossible (no `__dict__`) |

On 3.9, emulate with a hand-written `__slots__` only when fields have no defaults, or upgrade.

## Module functions

| Function | Purpose | Notes |
|----------|---------|-------|
| `fields(obj_or_cls)` | tuple of `Field` | excludes `ClassVar` and `InitVar` |
| `asdict(obj, *, dict_factory=dict)` | recursive dict | deep-copies non-dataclass values |
| `astuple(obj, *, tuple_factory=tuple)` | recursive tuple | same deep-copy behaviour |
| `replace(obj, /, **changes)` | new instance via `__init__` | re-runs `__post_init__`; `init=False` fields cannot be passed |
| `is_dataclass(obj)` | True for dataclass classes and instances | `isinstance(obj, type)` to tell them apart |
| `make_dataclass(name, fields, ...)` | build a class dynamically | fields as `name`, `(name, type)` or `(name, type, field(...))` |
| `MISSING` | sentinel for "no default" | compare with `is` |
| `FrozenInstanceError` | raised by frozen assignment | subclass of `AttributeError` |
| `KW_ONLY` | sentinel type (3.10) | `_: KW_ONLY` |
| `InitVar` | init-only pseudo-field | `InitVar[int]` |

### asdict deep-copy pitfalls

```python
import threading
from dataclasses import asdict, dataclass, field, fields

@dataclass
class Retriever:
    index_name: str
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

r = Retriever("docs")
try:
    asdict(r)
except TypeError as e:
    print(e)          # cannot pickle '_thread.lock' object

def shallow_dict(obj) -> dict:
    """Top-level fields only, no copying, skips private fields."""
    return {f.name: getattr(obj, f.name) for f in fields(obj) if not f.name.startswith("_")}
```

- `asdict` handles `namedtuple` specially (rebuilds it), lists/tuples/dicts recursively, and calls `copy.deepcopy` on everything else.
- A 1536-dim `float32` embedding per chunk times 10 000 chunks gets copied on every `asdict` call.
- `dict_factory` receives a list of `(key, value)` pairs, useful to drop `None`s:

```python
from dataclasses import asdict

def drop_none(pairs):
    return {k: v for k, v in pairs if v is not None}

payload = asdict(request, dict_factory=drop_none)  # applied at every nesting level
```

### replace() semantics

```python
from dataclasses import dataclass, field, replace

@dataclass(frozen=True)
class Prompt:
    template: str
    n_chars: int = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "n_chars", len(self.template))

p2 = replace(Prompt("Hi {name}"), template="Hello {name}")
print(p2.n_chars)   # 12: recomputed by __post_init__
# replace(p2, n_chars=3) -> error: field n_chars is declared with init=False, it cannot be specified with replace()
```

### make_dataclass

```python
from dataclasses import field, make_dataclass

Row = make_dataclass(
    "EvalRow",
    [("example_id", str), ("score", float), ("tags", list, field(default_factory=list))],
    frozen=False,
)
print(Row("ex1", 0.9))
```

Useful when the schema comes from a config (column list of an eval CSV). Prefer static classes when the shape is known, so type checkers see it.

## ClassVar, descriptors and properties

```python
from dataclasses import dataclass
from typing import ClassVar

@dataclass
class EmbeddingModel:
    name: str
    dim: int
    registry: ClassVar[dict] = {}           # class-level, not a field, mutable allowed
    DEFAULT_BATCH: ClassVar[int] = 64

    @property
    def is_large(self) -> bool:
        return self.dim >= 1024
```

- Unannotated class attributes are not fields either (`MAX = 3`).
- Properties with the same name as a field interfere with defaults; use a private field plus a property with a different name.
- Descriptor-typed fields: the descriptor's `__get__(None, cls)` result is used as the default; `__set__` is called by `__init__`.

## Pattern matching

`__match_args__` (3.10+) enables positional class patterns:

```python
from dataclasses import dataclass

@dataclass
class TextDelta:
    text: str

@dataclass
class ToolUseDelta:
    tool_name: str
    partial_json: str

def render(event) -> str:
    match event:
        case TextDelta(text):
            return text
        case ToolUseDelta(name, _):
            return f"[calling {name}]"
        case _:
            return ""
```

Keyword-only fields are not in `__match_args__`; match them with keyword patterns: `case Cfg(model="gpt-4o")`.

## Generics

```python
from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")

@dataclass
class Page(Generic[T]):
    items: list = field(default_factory=list)
    next_cursor: str = ""

pages: "Page[str]" = Page(items=["a", "b"])
```

3.12+ syntax: `class Page[T]:` with `items: list[T]` (PEP 695). Subscripting a dataclass generic does not validate anything at runtime.

## Performance and memory

Order-of-magnitude guidance (CPython 3.12, measure your own workload):

| Container | Create 1M small objects | Memory per instance | Attribute access |
|-----------|-------------------------|---------------------|------------------|
| plain class / `@dataclass` | baseline | `__dict__` (~100+ bytes) | baseline |
| `@dataclass(slots=True)` | similar or faster | roughly half or less | slightly faster |
| `@dataclass(frozen=True)` | slower (`object.__setattr__` per field) | as above | same |
| `NamedTuple` | fast | small (tuple) | index-based, fast |
| `dict` | fast | larger than slots | key lookup |
| pydantic v2 `BaseModel` | several times slower (validation) | larger | same-ish |
| `msgspec.Struct` | fastest | smallest | fast |

Tips:

- Class creation runs `exec` once per decorated class: negligible at import, noticeable only for `make_dataclass` in loops.
- For millions of records, columnar storage (numpy arrays, Arrow, DataFrame) beats any per-object container.
- `slots=True` is the cheapest memory win for chunks/tokens/events created in bulk.
- Avoid `asdict()` in hot loops; write a field-by-field `to_dict()`.

## Error catalogue

| Error | Cause | Fix |
|-------|-------|-----|
| `ValueError: mutable default <class 'list'> for field x is not allowed: use default_factory` | list/dict/set (3.11+: any unhashable) default | `field(default_factory=list)` |
| `TypeError: non-default argument 'x' follows default argument` (newer versions append the field name) | field order (often via inheritance) | reorder, defaults, `kw_only` |
| `FrozenInstanceError: cannot assign to field 'x'` | assignment on frozen instance | `replace()`, or `object.__setattr__` in `__post_init__` |
| `TypeError: unhashable type: 'Cfg'` | `eq=True`, not frozen | `frozen=True`, `unsafe_hash=True` or `eq=False` |
| `TypeError: unhashable type: 'list'` from frozen `hash()` | list field in frozen class | tuple, or `hash=False` |
| `ValueError: The truth value of an array with more than one element is ambiguous` | numpy/tensor field in `__eq__` | `field(compare=False)` |
| `TypeError: cannot inherit frozen dataclass from a non-frozen one` | mixed frozen inheritance | make both frozen or neither |
| `field x is declared with init=False, it cannot be specified with replace()` (`ValueError`, `TypeError` on recent versions) | `replace` on init=False field | recompute in `__post_init__` |
| `InitVar 'x' must be specified with replace()` (`ValueError`/`TypeError` as above) | `InitVar` without default | pass it or give it a default |
| `TypeError: __init__() missing 1 required positional argument` | field without default | default or pass the value |
| `AttributeError: 'X' object has no attribute 'y'` in `repr` | `init=False` field never assigned | assign in `__post_init__` or give a default |
| `TypeError: cannot pickle '_thread.lock' object` from `asdict` | deep copy of non-copyable value | shallow `to_dict()` |
| `ValueError: 'x' in __slots__ conflicts with class variable` | manual `__slots__` with defaults | `slots=True` |
| `TypeError: Cannot overwrite attribute __lt__ in class X` | `order=True` with hand-written ordering | remove one of them |
| `TypeError: super(type, obj): obj must be an instance or subtype of type` | zero-arg `super()` in `slots=True` class (3.10-3.13; fixed in 3.14) | `super(Cls, self)` |
