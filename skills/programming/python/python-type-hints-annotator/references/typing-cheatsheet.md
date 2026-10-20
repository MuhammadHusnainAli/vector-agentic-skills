# Typing Cheatsheet by Python Version

Every construct you are likely to write, the version that introduced it, and the
fallback for older targets. Rule of thumb: write the newest syntax your
**minimum supported** Python runs, and take anything newer from
`typing_extensions` (it re-exports `typing` names when they exist, so the
import keeps working after you upgrade).

## Contents

- [Version matrix](#version-matrix)
- [Basics](#basics)
- [Containers and abstract collections](#containers-and-abstract-collections)
- [Optional and unions](#optional-and-unions)
- [Callables](#callables)
- [Literal, Final, ClassVar, enums](#literal-final-classvar-enums)
- [Type aliases](#type-aliases)
- [Generics: TypeVar and PEP 695](#generics-typevar-and-pep-695)
- [TypedDict, NamedTuple, dataclasses](#typeddict-namedtuple-dataclasses)
- [Async types](#async-types)
- [Special return types](#special-return-types)
- [Annotations at runtime: future import, TYPE_CHECKING, 3.14](#annotations-at-runtime)
- [Old to new rewrite table](#old-to-new-rewrite-table)

## Version matrix

| Python | Added to typing / syntax | PEP |
|--------|--------------------------|-----|
| 3.5–3.8 | `typing` module, variable annotations (3.6), `Literal`, `Final`, `Protocol`, `TypedDict` (3.8) | 484, 526, 586, 591, 544, 589 |
| 3.9 | builtin generics `list[int]`, `collections.abc.X[...]` subscriptable, `Annotated` | 585, 593 |
| 3.10 | `X \| Y` at runtime, `ParamSpec`, `Concatenate`, `TypeAlias`, `TypeGuard`, `is_typeddict` | 604, 612, 613, 647 |
| 3.11 | `Self`, `Never`, `LiteralString`, `Required`/`NotRequired`, `TypeVarTuple`, `Unpack`, `assert_never`, `assert_type`, `reveal_type`, `dataclass_transform`, generic `TypedDict`/`NamedTuple` | 673, 655, 675, 646, 681 |
| 3.12 | `type X = ...`, `def f[T]()`, `class C[T]:`, `@override`, `**kwargs: Unpack[TD]`, `TypeAliasType` | 695, 698, 692 |
| 3.13 | `TypeIs`, `ReadOnly`, type parameter defaults, `warnings.deprecated`, `NoDefault` | 742, 705, 696, 702 |
| 3.14 | annotations evaluated lazily by default, `annotationlib` | 649, 749 |

Python 3.9 reached end of life in October 2025; new projects should target 3.10
or later, libraries often still support 3.9.

## Basics

```python
def greet(name: str, excited: bool = False) -> str:
    return f"Hello {name}{'!' if excited else '.'}"

count: int = 0                    # variable annotation (rarely needed: inference works)
hits: list[str] = []              # needed: empty container has no element type
model_name: str | None = None     # needed: None alone would infer as None

class Settings:
    api_key: str                  # declared, assigned in __init__
    timeout_s: float = 30.0
```

| Type | Meaning |
|------|---------|
| `int`, `float`, `complex` | numeric tower: `int` is accepted where `float` is expected, `float`/`int` where `complex` is |
| `bool` | subtype of `int` |
| `str`, `bytes` | text vs binary; `bytes` also accepts `bytearray`/`memoryview` unless you enable mypy `strict_bytes` / pyright `disableBytesTypePromotions` (PEP 688) |
| `None` | in annotations means `type(None)` |
| `object` | any value, but only `object` methods may be used |
| `Any` | any value, every operation allowed: turns checking off |
| `type[C]` | the class `C` or a subclass, not an instance |

## Containers and abstract collections

```python
from collections.abc import Iterable, Iterator, Mapping, MutableMapping, Sequence

def total_tokens(counts: Iterable[int]) -> int:           # any iterable, single pass
    return sum(counts)

def window(xs: Sequence[float], size: int) -> list[list[float]]:   # needs len + indexing
    return [list(xs[i:i + size]) for i in range(0, len(xs), size)]

def merge(base: Mapping[str, object], extra: Mapping[str, object]) -> dict[str, object]:
    return {**base, **extra}

def bump(stats: MutableMapping[str, int], key: str) -> None:       # mutates the argument
    stats[key] = stats.get(key, 0) + 1
```

| Concrete | Abstract (read) | Abstract (mutate) | Import (3.9+) |
|----------|-----------------|-------------------|---------------|
| `list[T]` | `Sequence[T]`, `Iterable[T]`, `Collection[T]` | `MutableSequence[T]` | `collections.abc` |
| `tuple[int, str]` (fixed) / `tuple[int, ...]` (variable) | `Sequence[T]` | | builtin |
| `dict[K, V]` | `Mapping[K, V]` | `MutableMapping[K, V]` | `collections.abc` |
| `set[T]`, `frozenset[T]` | `AbstractSet[T]` (`from collections.abc import Set as AbstractSet`) | `MutableSet[T]` | `collections.abc` |
| `collections.deque[T]`, `defaultdict[K, V]`, `OrderedDict[K, V]`, `Counter[T]`, `ChainMap[K, V]` | | | `collections` |
| generator object | `Iterator[T]`, `Generator[Y, S, R]` | | `collections.abc` |
| `re.Pattern[str]`, `re.Match[str]` | | | `re` |
| context manager | `contextlib.AbstractContextManager[T]` | | `contextlib` |

Notes:
- `tuple[()]` is the empty tuple; `tuple[int, ...]` is "any length of ints".
- `list` and `dict` are **invariant**: `list[bool]` is not a `list[int]`. Read-only `Sequence` and `Mapping` (values) are covariant, so accept those.
- `str` is a `Sequence[str]`: a function taking `Sequence[str]` will happily accept a single string. If that is a bug risk, accept `list[str] | tuple[str, ...]`.
- `Mapping` keys are invariant; `Mapping[str, float]` does not accept `dict[str | int, float]`.

## Optional and unions

```python
# 3.10+
def lookup(doc_id: str, cache: dict[str, str] | None = None) -> str | None: ...

# 3.9 with deferred annotations (annotations only, not runtime expressions)
from __future__ import annotations
def lookup(doc_id: str, cache: dict[str, str] | None = None) -> str | None: ...

# 3.9 without the future import
from typing import Optional, Union
def lookup(doc_id: str, cache: Optional[dict[str, str]] = None) -> Optional[str]: ...
Number = Union[int, float]          # runtime alias: must use Union on 3.9
```

- `Optional[X]` means "X or None", not "optional argument". An argument with a default is optional regardless of its type.
- `X | None` works in `isinstance(x, int | str)` from 3.10.
- Order in a union does not matter to checkers; put `None` last for readability.

## Callables

```python
from collections.abc import Awaitable, Callable

OnToken = Callable[[str], None]                       # one str arg, returns None
Scorer = Callable[[str, str], float]
AnyArgs = Callable[..., str]                          # any arguments
AsyncHandler = Callable[[dict[str, object]], Awaitable[str]]
Factory = Callable[[], "Embedder"]                    # zero args (forward ref in a runtime alias)
```

`Callable` cannot express keyword-only parameters, defaults or overloads. Use a
callback protocol:

```python
from typing import Protocol

class Completion(Protocol):
    def __call__(self, prompt: str, *, max_tokens: int = 256, temperature: float = 0.0) -> str: ...
```

`ParamSpec` and `Concatenate` (decorators): see [advanced-typing.md](advanced-typing.md#paramspec-and-concatenate).

## Literal, Final, ClassVar, enums

```python
from enum import StrEnum                 # 3.11
from typing import ClassVar, Final, Literal

Provider = Literal["openai", "anthropic", "local"]
MAX_CONTEXT: Final = 128_000             # inferred Final[int]; reassignment is an error

class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"

class Model:
    registry: ClassVar[dict[str, type["Model"]]] = {}     # class-level, not per instance
    name: str                                              # instance attribute

def set_mode(mode: Literal["chat", "completion"]) -> None: ...
set_mode("chat")          # ok
m = "chat"
set_mode(m)               # pyright: ok (narrowed to Literal["chat"]); mypy: error (m is inferred as str)
M: Final = "chat"
set_mode(M)               # ok in both: Final keeps the literal type
```

Checkers differ on literal inference for plain variables, so annotate
constants that feed `Literal` parameters with `Final` or an explicit
`Literal[...]` type.

- `Literal` accepts `int`, `str`, `bytes`, `bool`, enum members and `None`; not floats or expressions.
- `LiteralString` (3.11) accepts any string built only from literals: use it for SQL/prompt templates to block injection of user input into the template itself.
- `Final` in a dataclass field means a frozen per-instance value; at class level without dataclass, it is a constant.

## Type aliases

```python
# 3.12+: lazy, supports forward references and type parameters
type JSON = dict[str, JSON] | list[JSON] | str | int | float | bool | None
type Pair[T] = tuple[T, T]

# 3.10–3.11: explicit alias
from typing import TypeAlias
JSON: TypeAlias = "dict[str, JSON] | list[JSON] | str | int | float | bool | None"

# 3.9: implicit alias (any module-level assignment of a type)
from typing import Dict, List, Union
JSON = Union[Dict[str, "JSON"], List["JSON"], str, int, float, bool, None]
```

- A `type` alias is a `TypeAliasType` object at runtime: you cannot call it or use it in `isinstance`. Use `JSON.__value__` to get the value.
- `NewType` creates a distinct nominal type with zero runtime cost: `DocId = NewType("DocId", str)`; `DocId("a1")` is required to make one, so ids cannot be mixed up with other strings.

## Generics: TypeVar and PEP 695

```python
# 3.12+
def first[T](items: Sequence[T]) -> T:
    return items[0]

def longest[S: (str, bytes)](a: S, b: S) -> S:          # constrained: S is exactly str or bytes
    return a if len(a) >= len(b) else b

def top_k[N: float](scores: Sequence[N], k: int) -> list[N]:   # bounded: any subtype of float
    return sorted(scores, reverse=True)[:k]

class Cache[K, V]:
    def __init__(self) -> None:
        self._data: dict[K, V] = {}
    def get(self, key: K) -> V | None:
        return self._data.get(key)

# 3.13+: defaults
class Response[T = str]:
    def __init__(self, body: T) -> None:
        self.body = body

# 3.9–3.11
from typing import Generic, TypeVar
T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")
N = TypeVar("N", bound=float)
S = TypeVar("S", str, bytes)

class Cache(Generic[K, V]): ...
```

PEP 695 parameters infer variance automatically; with old-style `TypeVar` you
declare `covariant=True` / `contravariant=True` yourself (needed for protocols).

## TypedDict, NamedTuple, dataclasses

```python
from dataclasses import dataclass, field
from typing import NamedTuple, NotRequired, ReadOnly, Required, TypedDict

class Usage(TypedDict):
    prompt_tokens: int
    completion_tokens: int

class Message(TypedDict, total=False):      # every key optional...
    role: Required[str]                     # ...except these (3.11)
    content: str

class ToolCall(TypedDict):
    id: ReadOnly[str]                       # 3.13: cannot be assigned through this type
    name: str
    arguments: str
    index: NotRequired[int]                 # 3.11

class Hit(NamedTuple):
    doc_id: str
    score: float

@dataclass(frozen=True, slots=True)         # slots=: 3.10
class Chunk:
    text: str
    source: str
    tags: list[str] = field(default_factory=list)
```

| Use | When |
|-----|------|
| `TypedDict` | data is and stays a `dict` (JSON from/to an API, SDK kwargs); zero runtime cost, no validation |
| `NamedTuple` | small immutable records that should unpack like tuples |
| `dataclass` | internal objects with behaviour, defaults, equality |
| pydantic `BaseModel` | untrusted input that must be validated / coerced; JSON Schema generation |

## Async types

```python
from collections.abc import AsyncGenerator, AsyncIterable, AsyncIterator, Awaitable, Coroutine

async def complete(prompt: str) -> str: ...                     # annotate the awaited result
# complete is Callable[[str], Coroutine[Any, Any, str]]; calling it gives an awaitable

async def stream(prompt: str) -> AsyncIterator[str]:            # async generator
    for token in prompt.split():
        yield token

async def consume(tokens: AsyncIterable[str]) -> str:
    return "".join([t async for t in tokens])

def schedule(job: Awaitable[str]) -> None: ...                  # accepts coroutines, tasks, futures
```

| Annotation | Use for |
|------------|---------|
| `Awaitable[T]` | parameters that will be awaited (coroutine, Task, Future) |
| `Coroutine[Any, Any, T]` | when you need `.send` / `.close`, or `asyncio.create_task` arguments (typeshed requires a coroutine there) |
| `AsyncIterator[T]` | return of an `async def` with `yield` (simplest) |
| `AsyncGenerator[Y, S]` | if callers use `asend` / `aclose` (2 params; current typeshed gives `S` a default of `None`, so `AsyncGenerator[str]` works in up-to-date checkers) |
| `AsyncIterable[T]` | parameters consumed with `async for` |
| `asyncio.Task[T]`, `asyncio.Future[T]` | stored tasks |
| `contextlib.AbstractAsyncContextManager[T]` | objects used with `async with` |

## Special return types

| Annotation | Meaning |
|------------|---------|
| `-> None` | returns nothing (always write it, including `__init__`) |
| `-> NoReturn` / `-> Never` | never returns normally (always raises, `sys.exit`, infinite loop). `Never` is 3.11 and also usable as a parameter type ("cannot be called") |
| `-> Self` | instance of the class the method was called on (builders, fluent APIs, `classmethod` constructors) |
| `-> Iterator[T]` | generator |
| `-> TypeGuard[T]` / `-> TypeIs[T]` | user-defined narrowing predicate |

## Annotations at runtime

| Mode | When annotations are evaluated | Effect |
|------|-------------------------------|--------|
| Default 3.9–3.13 | at `def`/class creation | `list[int] \| None` fails on 3.9; forward refs need quotes |
| `from __future__ import annotations` | never (stored as strings) | new syntax OK in annotations on 3.9; no forward-ref quotes; `get_type_hints()` evaluates later |
| 3.14 default (PEP 649) | lazily, on first access of `__annotations__` | forward refs work without quotes; `annotationlib.get_annotations(obj, format=Format.FORWARDREF)` for partial evaluation |

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from numpy.typing import NDArray          # import only for the checker
    import numpy as np

def normalize(v: NDArray[np.float32]) -> NDArray[np.float32]: ...
```

Runtime consumers of annotations (pydantic, FastAPI, typer, attrs, SQLAlchemy,
`typing.get_type_hints`) must be able to resolve every name, so keep those
imports real and don't hide them under `TYPE_CHECKING`.

## Old to new rewrite table

| Old | New | Minimum |
|-----|-----|---------|
| `List[int]`, `Dict[str, int]`, `Set[str]`, `FrozenSet[str]`, `Tuple[int, ...]`, `Type[C]` | `list[int]`, `dict[str, int]`, `set[str]`, `frozenset[str]`, `tuple[int, ...]`, `type[C]` | 3.9 |
| `typing.Deque`, `DefaultDict`, `OrderedDict`, `Counter`, `ChainMap` | `collections.deque`, `defaultdict`, ... | 3.9 |
| `typing.Callable`, `Iterable`, `Iterator`, `Generator`, `Sequence`, `Mapping`, `Awaitable`, `AsyncIterator`, ... | `collections.abc.*` | 3.9 |
| `typing.ContextManager`, `AsyncContextManager` | `contextlib.AbstractContextManager`, `AbstractAsyncContextManager` | 3.9 |
| `typing.Pattern`, `typing.Match` | `re.Pattern`, `re.Match` | 3.9 |
| `typing.Text` | `str` | any |
| `Optional[X]` | `X \| None` | 3.10 |
| `Union[A, B]` | `A \| B` | 3.10 |
| `X: TypeAlias = ...` | `type X = ...` | 3.12 |
| `T = TypeVar("T")` + `Generic[T]` | `class C[T]:` / `def f[T]()` | 3.12 |
| `P = ParamSpec("P")` | `def deco[**P, R](fn: Callable[P, R])` | 3.12 |
| `Ts = TypeVarTuple("Ts")` | `class Array[*Ts]:` | 3.12 |
| `TypeVar("T", bound=X)` | `[T: X]` | 3.12 |
| `TypeVar("T", A, B)` | `[T: (A, B)]` | 3.12 |
| `typing_extensions.Self` etc. | `typing.Self` | see matrix |
| `T = TypeVar("T", default=str)` (typing_extensions) | `[T = str]` | 3.13 |
| `typing_extensions.deprecated` | `warnings.deprecated` | 3.13 |
| `**kwargs: Any` with a known key set | `**kwargs: Unpack[Options]` (TypedDict) | 3.12 (3.11 via typing_extensions) |

`scripts/annotation_audit.py --target-version X.Y` reports each of these rewrites
with the exact replacement text and the import lines to change.
