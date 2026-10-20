# Advanced Typing

Generics, variance, protocols, decorators, overloads, narrowing and the rest of
the toolbox you need once simple annotations are in place. Examples use 3.12
syntax with the pre-3.12 equivalent where it differs.

## Contents

- [Generics and variance](#generics-and-variance)
- [PEP 695 type parameters](#pep-695-type-parameters)
- [Protocols](#protocols)
- [ParamSpec and Concatenate](#paramspec-and-concatenate)
- [Overloads](#overloads)
- [TypedDict in depth](#typeddict-in-depth)
- [Narrowing: isinstance, match, TypeGuard, TypeIs](#narrowing)
- [Self, classmethods and fluent APIs](#self-classmethods-and-fluent-apis)
- [Never, NoReturn and exhaustiveness](#never-noreturn-and-exhaustiveness)
- [TypeVarTuple and Unpack](#typevartuple-and-unpack)
- [Annotated metadata](#annotated-metadata)
- [dataclass_transform, override, deprecated, Final methods](#decorators-for-type-checkers)
- [Recursive types and JSON](#recursive-types-and-json)
- [Stubs and py.typed](#stubs-and-pytyped)

## Generics and variance

A type parameter links types across a signature: whatever goes in, comes out.

```python
from collections.abc import Callable, Iterable, Sequence

def batched[T](items: Sequence[T], size: int) -> list[Sequence[T]]:
    return [items[i:i + size] for i in range(0, len(items), size)]

def map_concurrently[T, R](fn: Callable[[T], R], items: Iterable[T]) -> list[R]:
    return [fn(x) for x in items]

chunks = batched(["a", "b", "c"], 2)        # list[Sequence[str]]
lengths = map_concurrently(len, ["ab", "c"])  # list[int]
```

Variance answers "if `Dog` is a subtype of `Animal`, is `Box[Dog]` a subtype of `Box[Animal]`?"

| Variance | Rule | Examples | Why |
|----------|------|----------|-----|
| covariant | yes | `Sequence[T]`, `Iterator[T]`, `tuple[T, ...]`, `frozenset[T]`, `Mapping[K, V]` (in `V`), return types | read-only: you only get Ts out |
| contravariant | reversed | `Callable[[T], R]` (in `T`), parameter types, a `Sink[T]` with only `send(T)` | write-only: you only put Ts in |
| invariant | no | `list[T]`, `dict[K, V]`, `set[T]`, mutable attributes | read and write |

The classic error:

```python
def mean(xs: list[float]) -> float: ...
scores: list[int] = [1, 2, 3]
mean(scores)          # error: list[int] is not list[float] (invariant)

def mean(xs: Sequence[float]) -> float: ...   # fix: read-only and covariant
```

Old-style variance must be declared, and protocol checkers enforce it:

```python
from typing import Protocol, TypeVar

T_co = TypeVar("T_co", covariant=True)

class Source(Protocol[T_co]):
    def read(self) -> T_co: ...
```

With PEP 695 type parameters on a `Protocol` subclass, the checker infers variance from usage.

Bounds and constraints:

| Form | Meaning | Use |
|------|---------|-----|
| `[T]` | anything | containers, pass-through |
| `[T: Hashable]` (`bound=`) | `T` is a subtype of the bound and stays that precise type | `def dedupe[T: Hashable](xs: Iterable[T]) -> list[T]` |
| `[S: (str, bytes)]` (constraints) | exactly one of the listed types, never a mix | `str`/`bytes` utilities |

## PEP 695 type parameters

```python
# Functions
def first[T](xs: Sequence[T]) -> T: ...

# Classes (Generic base is implicit)
class Registry[K, V]:
    def __init__(self) -> None:
        self._items: dict[K, V] = {}
    def register(self, key: K, value: V) -> None:
        self._items[key] = value

# Aliases with parameters
type Scored[T] = list[tuple[T, float]]
type Handler[**P] = Callable[P, Awaitable[None]]
type Shape[*Ts] = tuple[*Ts]

# Defaults (3.13)
class Page[T = dict[str, object]]:
    items: list[T]
```

Rules:
- Type parameters are scoped to their function/class/alias; no module-level `TypeVar` objects.
- Do not mix PEP 695 parameters with `Generic[T]` on the same class.
- A class's type parameters exist only inside the class body and its methods; they are not visible at module level.
- `TypeAliasType` (`typing_extensions`) gives you `type`-statement semantics on 3.9–3.11:
  `JSON = TypeAliasType("JSON", "dict[str, JSON] | list[JSON] | str | int | float | bool | None")`.

## Protocols

Structural subtyping: a class matches if it has the right members, no inheritance.

```python
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

class SupportsLen(Protocol):
    def __len__(self) -> int: ...

class Tokenizer(Protocol):
    @property
    def vocab_size(self) -> int: ...                       # read-only attribute
    def encode(self, text: str) -> list[int]: ...
    def decode(self, ids: Sequence[int]) -> str: ...

@runtime_checkable
class Closeable(Protocol):
    def close(self) -> None: ...

def count_tokens(tok: Tokenizer, texts: Sequence[str]) -> int:
    return sum(len(tok.encode(t)) for t in texts)
```

| Detail | Rule |
|--------|------|
| Attributes | `name: str` in a protocol means read-write; implementations with a read-only `@property` don't match. Use `@property` in the protocol for read-only |
| `@runtime_checkable` | `isinstance` checks member names only, not signatures; slow-ish; avoid in hot paths |
| Generic protocol | PEP 695 parameters on a class whose base is `Protocol`, or `Protocol[T_co]` before 3.12 |
| Explicit opt-in | an implementation may subclass the protocol to get errors at the class definition; then it is nominal too |
| Callback protocol | define `__call__` to express kwargs, defaults, overloads |
| Module as protocol | a module object satisfies a protocol if it has the functions (PEP 544) |

Protocol vs ABC: ABCs give runtime enforcement and shared implementation;
protocols give decoupling (no import of the base class needed, third-party
classes match). Prefer protocols for collaborator interfaces (embedders, stores,
LLM clients) and ABCs when you ship a base implementation.

## ParamSpec and Concatenate

`ParamSpec` captures a whole parameter list so decorators preserve it.

```python
import functools
import time
from collections.abc import Callable

def timed[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            print(f"{fn.__name__}: {time.perf_counter() - start:.3f}s")
    return wrapper

@timed
def embed(texts: list[str], model: str = "small") -> list[list[float]]: ...

embed(["a"], model="large")     # checked against the real signature
embed(["a"], modle="large")     # error: unexpected keyword argument
```

`Concatenate` adds or removes leading positional parameters:

```python
from typing import Concatenate

class Client:
    ...

def with_client[**P, R](fn: Callable[Concatenate[Client, P], R]) -> Callable[P, R]:
    """Inject a client as the first argument; callers no longer pass it."""
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return fn(Client(), *args, **kwargs)
    return wrapper

@with_client
def ask(client: Client, prompt: str, *, temperature: float = 0.0) -> str: ...

ask("hi", temperature=0.3)      # Client parameter removed from the signature
```

Pre-3.12:

```python
from typing import ParamSpec, TypeVar
P = ParamSpec("P")
R = TypeVar("R")
def timed(fn: Callable[P, R]) -> Callable[P, R]: ...
```

Decorator factories (decorators with arguments) return a decorator:
`def retry(attempts: int) -> Callable[[Callable[P, R]], Callable[P, R]]`.
Both mypy and pyright solve `P` and `R` when the returned decorator is applied.

Rules: `P.args` and `P.kwargs` must be used together as `*args`/`**kwargs`;
you cannot add keyword-only parameters with `Concatenate` (only positional ones).

## Overloads

Use when the return type depends on argument values or types.

```python
from typing import Literal, overload

class Stream: ...

@overload
def complete(prompt: str, *, stream: Literal[False] = False) -> str: ...
@overload
def complete(prompt: str, *, stream: Literal[True]) -> Stream: ...
@overload
def complete(prompt: str, *, stream: bool) -> str | Stream: ...
def complete(prompt: str, *, stream: bool = False) -> str | Stream:
    return Stream() if stream else "done"

text = complete("hi")                  # str
s = complete("hi", stream=True)        # Stream
```

Rules:
- At least two `@overload` signatures, followed by one undecorated implementation (except in stubs and protocols).
- The implementation signature must accept every overload's arguments, and return a supertype of each.
- Order matters: checkers pick the first match, so put narrower signatures first.
- Add the `bool` catch-all overload so callers passing a non-literal `bool` still type-check.
- Don't overload when a type parameter suffices (`def first[T](xs: Sequence[T]) -> T`).

## TypedDict in depth

```python
from typing import Literal, NotRequired, ReadOnly, Required, TypedDict, Unpack

class Message(TypedDict):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: NotRequired[str]

class GenerationOptions(TypedDict, total=False):
    temperature: float
    max_tokens: int
    stop: list[str]
    model: Required[str]

def generate(prompt: str, **opts: Unpack[GenerationOptions]) -> str:   # PEP 692, 3.12
    return opts["model"]

generate("hi", model="small", temperature=0.2)     # keys and types checked
generate("hi", temprature=0.2)                     # error: unexpected keyword
```

| Feature | Version | Notes |
|---------|---------|-------|
| `total=False` | 3.8 | all keys optional |
| `Required` / `NotRequired` | 3.11 | per-key override |
| Generic TypedDict (`class Page[T]` with base `TypedDict`) | 3.11 (3.12 syntax for `[T]`) | |
| `ReadOnly` | 3.13 | key cannot be assigned through this type; allows covariant-style assignment |
| `Unpack[TD]` for `**kwargs` | 3.12 | |
| Inheritance | 3.8 | `class ToolMessage(Message): tool_call_id: str` |
| Alternative syntax | 3.8 | `TypedDict("Msg", {"from": str})` for keys that are keywords or invalid identifiers |
| Closed / extra items | `typing_extensions` (PEP 728) | `closed=True`, `extra_items=` |

Behaviour to remember:
- TypedDicts are plain `dict`s at runtime: no validation, `isinstance(x, Message)` is a `TypeError`.
- A `dict[str, str]` is not assignable to a TypedDict, and a TypedDict is not assignable to `dict[str, object]` (it is to `Mapping[str, object]`).
- Reading a `NotRequired` key directly is reported by pyright (`reportTypedDictNotRequiredAccess`); use `.get` or check `in`.
- Structural: two TypedDicts with the same keys are compatible.

## Narrowing

Checkers narrow on: `is None` / `is not None`, `isinstance`, `issubclass`,
`callable`, `==` against literals and enum members, `in` against literal
collections, truthiness, `len(t) == n` for tuples, `match` patterns, and
discriminated unions on a `Literal` field.

```python
from typing import Literal, TypedDict

class TextBlock(TypedDict):
    type: Literal["text"]
    text: str

class ToolUseBlock(TypedDict):
    type: Literal["tool_use"]
    name: str
    input: dict[str, object]

type Block = TextBlock | ToolUseBlock

def render(block: Block) -> str:
    if block["type"] == "text":
        return block["text"]            # narrowed to TextBlock
    return f"<tool {block['name']}>"    # narrowed to ToolUseBlock
```

User-defined predicates:

```python
from typing import TypeGuard, TypeIs

def is_str_list(xs: list[object]) -> TypeGuard[list[str]]:   # 3.10: narrows the True branch only
    return all(isinstance(x, str) for x in xs)

def is_text_block(b: Block) -> TypeIs[TextBlock]:            # 3.13: narrows both branches
    return b["type"] == "text"

def handle(b: Block) -> None:
    if is_text_block(b):
        print(b["text"])          # TextBlock
    else:
        print(b["name"])          # ToolUseBlock (TypeGuard would leave Block here)
```

| | `TypeGuard[T]` | `TypeIs[T]` |
|-|----------------|-------------|
| True branch | exactly `T` | input type intersected with `T` |
| False branch | unchanged | input minus `T` |
| `T` must be a subtype of the input | no (can convert `list[object]` to `list[str]`) | yes |
| Use | changing the "view" of a value | "is this one of the union members?" |

Narrowing is lost when the value could change: attributes (`self.client`) after
any call, or captured variables in nested functions. Copy to a local first:
`client = self.client; if client is None: ...`.

## Self, classmethods and fluent APIs

```python
from typing import Self

class Pipeline:
    def __init__(self) -> None:
        self.steps: list[str] = []

    def add(self, step: str) -> Self:          # subclasses keep their own type
        self.steps.append(step)
        return self

    @classmethod
    def from_config(cls, steps: list[str]) -> Self:
        p = cls()
        for s in steps:
            p.add(s)
        return p

class RagPipeline(Pipeline):
    def rerank(self) -> Self:
        return self.add("rerank")

RagPipeline().add("retrieve").rerank()          # ok: add returns RagPipeline
```

Before 3.11: `from typing_extensions import Self`, or a bound TypeVar:
`TPipeline = TypeVar("TPipeline", bound="Pipeline")` and `def add(self: TPipeline, ...) -> TPipeline`.
`Self` is not allowed in static methods or module-level functions.

## Never, NoReturn and exhaustiveness

```python
from enum import Enum
from typing import NoReturn, assert_never

def fail(msg: str) -> NoReturn:
    raise RuntimeError(msg)

class Finish(Enum):
    STOP = "stop"
    LENGTH = "length"
    TOOL = "tool_calls"

def describe(reason: Finish) -> str:
    if reason is Finish.STOP:
        return "complete"
    elif reason is Finish.LENGTH:
        return "truncated"
    elif reason is Finish.TOOL:
        return "needs tool"
    else:
        assert_never(reason)      # error here if a member is added and not handled
```

`Never` and `NoReturn` are the same type; convention: `NoReturn` for return
annotations, `Never` elsewhere. Code after a call to a `NoReturn` function is
treated as unreachable.

## TypeVarTuple and Unpack

Variadic generics: a variable number of types, mostly for array shapes and
`*args` forwarding.

```python
from collections.abc import Callable

def call_later[*Ts](fn: Callable[[*Ts], None], *args: *Ts) -> None:
    fn(*args)

def log(level: int, msg: str) -> None: ...

call_later(log, 10, "hi")       # ok
call_later(log, "hi", 10)       # error: argument types do not match

class Array[*Shape]:
    def __init__(self, *shape: *Shape) -> None:
        self.shape = shape
```

Pre-3.11 spelling: `Ts = TypeVarTuple("Ts")`, `Unpack[Ts]` instead of `*Ts`.
Array libraries have not standardised on TypeVarTuple shapes yet; for tensors
use jaxtyping (see [ai-ml-typing.md](ai-ml-typing.md#arrays-and-tensors)).

## Annotated metadata

`Annotated[T, x, y]` is just `T` to the checker; tools read the extra metadata.

```python
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field

class SearchRequest(BaseModel):
    query: Annotated[str, Field(min_length=1, max_length=2000)]
    k: Annotated[int, Field(ge=1, le=100)] = 10

def search(q: Annotated[str, Query(max_length=200)], k: Annotated[int, Query(ge=1)] = 5) -> list[str]: ...

type Temperature = Annotated[float, Field(ge=0.0, le=2.0)]   # reusable constrained type
```

## Decorators for type checkers

```python
from typing import final, override          # override: 3.12
from warnings import deprecated             # 3.13 (typing_extensions before)

class BaseRetriever:
    def retrieve(self, query: str) -> list[str]:
        return []

    @final
    def close(self) -> None: ...              # subclasses may not override

class BM25Retriever(BaseRetriever):
    @override
    def retrieve(self, query: str) -> list[str]:   # error if the base method is renamed
        return [query]

@deprecated("use embed_batch()")
def embed_one(text: str) -> list[float]: ...      # callers get a checker warning
```

`@dataclass_transform()` (3.11) marks your own decorator, base class or
metaclass as creating dataclass-like `__init__`s (pydantic, SQLModel and attrs
use it), so checkers synthesise constructors for model classes you define.

## Recursive types and JSON

```python
type JSON = dict[str, JSON] | list[JSON] | str | int | float | bool | None   # 3.12

import json

def load_json(text: str) -> JSON:
    return json.loads(text)        # json.loads returns Any; the annotation documents the boundary

def get_path(doc: JSON, *keys: str) -> JSON:
    for k in keys:
        if not isinstance(doc, dict):
            raise KeyError(k)
        doc = doc[k]
    return doc
```

Recursive aliases are supported by mypy and pyright. Prefer
`Mapping[str, object]` for "some JSON object I only pass along" and parse into
TypedDict/pydantic as soon as you depend on the structure.

## Stubs and py.typed

| Need | Do |
|------|----|
| Your package is typed | add an empty `py.typed` file to the package and include it in the wheel (`[tool.setuptools.package-data] mypkg = ["py.typed"]`, hatch/poetry include it automatically) |
| Third-party package without types | `pip install types-<name>` (typeshed: `types-requests`, `types-PyYAML`, `types-redis` for old redis, ...) |
| No stubs exist | write `stubs/<pkg>/__init__.pyi` with only the functions you use; set `mypy_path = "stubs"` / pyright `stubPath = "stubs"` |
| Generate a starting stub | `stubgen -p <pkg> -o stubs` (mypy) or `pyright --createstub <pkg>` |
| Partial package | `py.typed` containing `partial\n` |
| Verify stubs match runtime | `python -m mypy.stubtest <pkg>` |

A `.pyi` stub contains signatures only:

```python
# stubs/legacy_vectordb/__init__.pyi
from collections.abc import Sequence

class Collection:
    def add(self, ids: Sequence[str], embeddings: Sequence[Sequence[float]]) -> None: ...
    def query(self, embedding: Sequence[float], n_results: int = ...) -> dict[str, list[list[str]]]: ...

def connect(url: str, *, timeout: float = ...) -> Collection: ...
```
