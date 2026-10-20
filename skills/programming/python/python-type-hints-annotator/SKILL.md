---
name: python-type-hints-annotator
description: "Add accurate, modern type hints to Python and fix mypy / pyright (pyrefly, ty) errors: builtin generics, X | None, TypeAlias and the 3.12 type statement, TypeVar and PEP 695 generics, Protocol, Callable / ParamSpec / Concatenate, TypedDict (Required, NotRequired, ReadOnly), Literal, Final, ClassVar, overload, Annotated, TypeGuard / TypeIs, Self, Never, TypeVarTuple, async types, Iterable vs Sequence vs Mapping, TYPE_CHECKING, stubs, py.typed, gradual strictness. AI-engineering focus: typed LLM message dicts and tool schemas, pydantic vs TypedDict, numpy NDArray, torch / jaxtyping shapes, streaming generators, async clients, callbacks, generic VectorStore protocols, typed config. Ships an AST audit: coverage gate, legacy-typing rewrites, inferred types. Use when the user asks to add type hints, annotate or type a module, fix a mypy or pyright error, modernise typing imports (List, Optional, Union), set up strict type checking or a coverage gate in CI, or type LLM, RAG, agent, FastAPI or ML code."
metadata:
  category: programming
  subcategory: python
  version: "1.0.0"
---

# Python Type Hints Annotator

Annotate Python so a type checker can prove things about it: precise parameter and return types, modern syntax for the project's minimum Python version, abstract inputs and concrete outputs, no silent `Any`, and zero new checker errors. Then fix whatever mypy or pyright reports with the smallest correct change, never with a blanket `# type: ignore`. `scripts/annotation_audit.py` measures coverage, finds unannotated functions, infers easy types and rewrites legacy `typing` syntax; you supply the types that need understanding of the code: protocols, generics, TypedDicts for LLM payloads, overloads and array shapes.

## Trigger Conditions

Activate this skill when the user:
- Says "add type hints", "annotate this", "type this module", "make mypy/pyright happy", "get to strict"
- Pastes a mypy or pyright error (`Incompatible types in assignment`, `Item "None" of "X | None" has no attribute`, `reportOptionalMemberAccess`, `Missing type parameters for generic type`, `Function is missing a return type annotation`)
- Wants to modernise typing: `List`/`Dict`/`Optional`/`Union` to `list`/`dict`/`X | None`, `TypeVar` to PEP 695, `TypeAlias` to `type`
- Types LLM / RAG / agent code: chat message dicts, tool schemas, streaming responses, async clients, retry decorators, callbacks, embeddings, vector stores, model configs
- Types numeric code: numpy arrays and dtypes, torch tensors, shape annotations with jaxtyping
- Sets up `mypy`/`pyright` config, a CI gate, `py.typed`, stubs, or plans incremental adoption on a large untyped codebase

## Workflow

```
1. SCOPE     -> minimum Python version? checker (mypy / pyright / both)? library (public API) or app?
2. AUDIT     -> python scripts/annotation_audit.py <file|dir> --target-version 3.X
3. MODERNISE -> apply legacy-* rewrites and fix the import lines it prints
4. ANNOTATE  -> public API first: params abstract (Iterable, Mapping), returns concrete (list, dict)
5. MODEL     -> TypedDict / dataclass / pydantic for structured data, Protocol for collaborators,
                generics where a type flows from input to output, overload where it depends on a value
6. CHECK     -> run mypy / pyright; fix errors by narrowing, not by casting or ignoring
7. GATE      -> --min-coverage N in CI; tighten checker strictness module by module
```

## Core Rules

1. **Annotate every public function fully** (all params and the return), including `-> None`. An unannotated `def` is skipped by mypy's default mode: its body is not checked at all.
2. **Use the syntax the minimum supported Python allows** (see table below). Libraries supporting 3.9 can still write `X | None` inside annotations with `from __future__ import annotations`, but never in runtime expressions (aliases, `cast`, `isinstance`, pydantic fields, FastAPI params).
3. **Accept abstract, return concrete.** Parameters take `Iterable[str]`, `Sequence[float]`, `Mapping[str, object]`; returns give `list[str]`, `dict[str, float]`. Callers get maximum freedom in, maximum information out.
4. **No implicit Optional.** `def f(stop: list[str] = None)` is an error in mypy and pyright. Write `stop: list[str] | None = None` and never use a mutable default.
5. **`Any` is an escape hatch, not a type.** Prefer `object` (accept anything, use nothing), a `TypeVar` (pass through), a `TypedDict`/`Protocol` (known shape), or a recursive JSON alias. Each remaining `Any` gets a comment saying why.
6. **Narrow instead of cast.** `if x is None: raise`, `isinstance`, `match`, `TypeIs` functions and `assert_never` keep the checker honest; `cast()` and `# type: ignore[code]` are last resorts and always carry the error code.
7. **Model data, don't annotate `dict[str, Any]`.** LLM messages, tool calls, configs and API payloads get a `TypedDict` (static shape for dicts you pass to SDKs), a `dataclass` (internal objects) or a pydantic model (validation at a trust boundary).
8. **Generics when types flow through.** If the output type depends on the input type (`first(items)`, `Cache[T]`, `retry(fn)`), use a type parameter; `ParamSpec` for decorators so wrapped signatures survive.
9. **Don't over-annotate locals.** Annotate variables only where inference fails: empty containers (`hits: list[Doc] = []`), `None` initialisers, and class attributes.
10. **Typing must not change runtime behaviour.** Imports used only in annotations go under `if TYPE_CHECKING:`; never import torch just to annotate a helper module that otherwise doesn't need it.

## Syntax by Python Version

| Feature | Minimum | Instead of | Notes |
|---------|---------|------------|-------|
| `list[int]`, `dict[str, X]`, `tuple[int, ...]`, `type[C]` | 3.9 | `List`, `Dict`, `Tuple`, `Type` | PEP 585; `collections.abc.Callable[...]` too |
| `Annotated[T, meta]` | 3.9 | `typing_extensions` | pydantic `Field`, FastAPI `Query`, jaxtyping |
| `X \| None`, `A \| B` | 3.10 | `Optional[X]`, `Union[A, B]` | runtime-valid from 3.10; works in `isinstance` too |
| `ParamSpec`, `Concatenate`, `TypeGuard`, `TypeAlias` | 3.10 | | decorators keep signatures |
| `Self`, `Never`, `LiteralString`, `Required`/`NotRequired`, `TypeVarTuple`, `Unpack`, `assert_never`, `reveal_type` | 3.11 | `typing_extensions` | |
| `type Alias = ...`, `def f[T](x: T)`, `class C[T]:`, `@override`, `Unpack[TypedDict]` for `**kwargs` | 3.12 | `TypeVar`, `TypeAlias`, `Generic[T]` | PEP 695 / 698 / 692 |
| `TypeIs`, `ReadOnly`, TypeVar defaults `[T = str]`, `warnings.deprecated` | 3.13 | | PEP 742 / 705 / 696 / 702 |
| Deferred evaluation of annotations by default | 3.14 | `from __future__ import annotations` | PEP 649/749; `annotationlib` |

Anything newer than the target comes from `typing_extensions` (a tiny, ubiquitous dependency). Full per-version detail: [typing-cheatsheet.md](references/typing-cheatsheet.md).

## Before and After

```python
# Before: untyped, mutable default, Optional implicit, any-shaped dicts
def call_llm(messages, tools=None, temperature=0.2, stop=[]):
    ...

# After (3.10+)
from collections.abc import Sequence
from typing import Literal, NotRequired, TypedDict

class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: NotRequired[str]

class ToolSpec(TypedDict):
    name: str
    description: str
    parameters: dict[str, object]           # JSON Schema

def call_llm(
    messages: Sequence[ChatMessage],
    tools: Sequence[ToolSpec] | None = None,
    temperature: float = 0.2,
    stop: Sequence[str] | None = None,
) -> str:
    ...
```

## Choosing the Right Type

| Situation | Annotation |
|-----------|------------|
| Read-only iteration, any iterable | `Iterable[T]` (consumed once; generators OK) |
| Needs `len()` / indexing / multiple passes | `Sequence[T]` (list, tuple, str) |
| Read-only key lookup | `Mapping[K, V]` (accepts dict, `MappingProxyType`, custom) |
| Will mutate the argument | `list[T]` / `dict[K, V]` / `MutableMapping[K, V]` |
| Function returns a fresh container | concrete `list[T]` / `dict[K, V]` |
| Generator function | `Iterator[T]` (or `Generator[Y, S, R]` if it uses send/return) |
| `async def` generator (streaming tokens) | `AsyncIterator[str]` |
| `async def f() -> T` | annotate `T`, not `Coroutine[...]`; callers see `Coroutine[Any, Any, T]` |
| Callback / hook argument | `Callable[[str], None]`, or a `Protocol` with `__call__` for keyword args |
| Async callback | `Callable[[str], Awaitable[None]]` |
| Fixed set of string values | `Literal["openai", "anthropic", "local"]` |
| Constant never reassigned | `Final[int]` / `MAX_TOKENS: Final = 4096` |
| Class-level shared attribute | `ClassVar[dict[str, type[Model]]]` |
| Method returning its own instance (builders) | `Self` |
| Never returns (always raises / exits) | `NoReturn` (return position) / `Never` (bottom type, 3.11) |
| Return type depends on an argument's value | `@overload` with `Literal` parameters |
| Same type in and out | type parameter: `def first[T](xs: Sequence[T]) -> T` |
| Anything, but used opaquely | `object` |
| Constrained to a few unrelated types | `def f[S: (str, bytes)](x: S) -> S` (constrained TypeVar) |
| Function decorator preserving signature | `ParamSpec` (`**P`) plus return `TypeVar` |

## Fixing Checker Errors (most common)

| Error (mypy / pyright) | Cause | Fix |
|------------------------|-------|-----|
| `Item "None" of "X \| None" has no attribute "y"` / `reportOptionalMemberAccess` | value may be None | narrow: `if x is None: raise ValueError(...)`; early return; or make it non-optional upstream |
| `Incompatible default for argument` / `Expression of type "None" cannot be assigned` | implicit Optional | `param: T \| None = None` |
| `Function is missing a type annotation` `[no-untyped-def]` | strict mode | annotate it; for `__init__` add `-> None` |
| `Need type annotation for "x"` `[var-annotated]` | empty container | `x: list[Chunk] = []` |
| `Argument 1 has incompatible type "list[int]"; expected "list[float]"` `[arg-type]` | `list` is invariant | accept `Sequence[float]` (covariant) |
| `Returning Any from function declared to return "str"` `[no-any-return]` | untyped library / `json.loads` | validate or `str(...)`; type the boundary once |
| `Missing type parameters for generic type "dict"` `[type-arg]` | bare `dict` | `dict[str, object]` |
| `Skipping analyzing "x": module is installed, but missing library stubs or py.typed marker` `[import-untyped]` | no types shipped | `pip install types-x`, else per-module `ignore_missing_imports` |
| `Signature of "m" incompatible with supertype` `[override]` / `reportIncompatibleMethodOverride` | narrowed param or widened return | params may only widen, returns only narrow (LSP) |
| `"TypedDict" has no key "x"` / `reportTypedDictNotRequiredAccess` | `NotRequired` key read directly | `msg.get("x")` or `if "x" in msg:` |
| `Unused "type: ignore" comment` `[unused-ignore]` | stale suppression | delete it (enable `warn_unused_ignores`) |

A longer catalogue with pyright rule names and fixes is in [type-checker-setup.md](references/type-checker-setup.md).

## Narrowing Patterns

```python
from typing import Literal, assert_never        # assert_never: 3.11+, else typing_extensions

def require(value: str | None, name: str) -> str:
    if value is None:
        raise ValueError(f"{name} is required")
    return value                                 # narrowed to str

def cost_per_token(provider: Literal["openai", "anthropic", "local"]) -> float:
    match provider:
        case "openai":
            return 2.5e-6
        case "anthropic":
            return 3e-6
        case "local":
            return 0.0
        case _:
            assert_never(provider)               # checker errors if a new provider is unhandled
```

User-defined narrowing: `TypeGuard[T]` (3.10) narrows only the positive branch to exactly `T`; `TypeIs[T]` (3.13) narrows both branches and intersects with the input type. Prefer `TypeIs` for "is this X?" predicates. See [advanced-typing.md](references/advanced-typing.md).

## Protocols over Base Classes

```python
from collections.abc import Sequence
from typing import Protocol

class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...

class VectorStore[T](                            # 3.12 syntax; Protocol[T] before
    Protocol
):
    def upsert(self, ids: Sequence[str], vectors: Sequence[list[float]], payloads: Sequence[T]) -> None: ...
    def query(self, vector: list[float], k: int = 5) -> list[tuple[T, float]]: ...

def index(docs: Sequence[str], embedder: Embedder, store: VectorStore[str]) -> None:
    store.upsert([str(i) for i in range(len(docs))], embedder.embed(docs), docs)
```

Any class with matching methods satisfies the protocol: no inheritance, so OpenAI, local and fake test embedders all fit. Add `@runtime_checkable` only if you need `isinstance` (it checks method names, not signatures).

## Decorators that Keep Signatures

```python
import asyncio
import functools
from collections.abc import Awaitable, Callable

def retry[**P, R](attempts: int = 3) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    def deco(fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            for i in range(attempts - 1):
                try:
                    return await fn(*args, **kwargs)
                except TimeoutError:
                    await asyncio.sleep(2 ** i)
            return await fn(*args, **kwargs)
        return wrapper
    return deco
```

Before 3.12: `P = ParamSpec("P")`, `R = TypeVar("R")` at module level, same body.

## AI-Engineering Typing Quick Reference

| Thing | Type it as |
|-------|-----------|
| Chat message passed to an SDK | `TypedDict` with `role: Literal[...]`, `NotRequired` optional keys |
| Validated config / request body / LLM structured output | pydantic `BaseModel` (validation + JSON Schema) |
| Internal value objects (Chunk, Hit, Usage) | `@dataclass(frozen=True, slots=True)` |
| Tool registry | `dict[str, Callable[..., Awaitable[str]]]` or a `Protocol` per tool |
| Streaming tokens | `AsyncIterator[str]` / `Iterator[str]` |
| Embedding matrix | `NDArray[np.float32]`; with shape: `Float[np.ndarray, "n d"]` (jaxtyping) |
| Torch batch | `torch.Tensor`; with shape: `Float[Tensor, "batch seq dim"]` (jaxtyping + beartype at runtime) |
| JSON payload of unknown shape | `JSON` recursive alias, not `Any` |
| Provider/model names | `Literal[...]` or `StrEnum` (3.11) |
| Callbacks / hooks | `Callable[[TokenEvent], None]` or a `Protocol` |

Full worked examples (OpenAI/Anthropic-style messages, tool schemas, pydantic vs TypedDict trade-offs, generic repositories, typed settings, training loops): [ai-ml-typing.md](references/ai-ml-typing.md).

## Imports, Cycles and Heavy Dependencies

```python
from __future__ import annotations              # annotations become strings: no runtime cost, no cycles

from typing import TYPE_CHECKING

if TYPE_CHECKING:                                # never executed; checkers still see it
    import torch
    from .store import VectorStore

def to_device(batch: torch.Tensor, store: VectorStore[str]) -> torch.Tensor: ...
```

Caveat: libraries that evaluate annotations at runtime (pydantic, FastAPI, typer, `dataclasses` with `get_type_hints`, SQLAlchemy `Mapped[...]`) need the names importable at runtime; keep their imports real, and on 3.9 keep `Optional[X]` in those classes even with the future import.

## Gradual Adoption

1. Run the audit to get a baseline: `annotation_audit.py src/ --json > typing-baseline.json`.
2. Turn on the checker in non-strict mode with `check_untyped_defs = true`; fix real bugs first.
3. Make new and touched modules strict via per-module overrides; annotate leaf utilities, then core domain types (messages, configs), then services.
4. Gate CI on coverage that only goes up (`--min-coverage`), and on `mypy --strict` for opted-in packages.
5. Ship `py.typed` once the public API is annotated.

Step-by-step plan, config snippets and how to handle untyped third-party libraries: [migration-strategy.md](references/migration-strategy.md).

## Output Format

When annotating or fixing types, return:

1. **Summary**: target Python version, checker, coverage before → after (from the audit script).
2. **Annotated code**: the full rewritten functions or module, with any new TypedDict / Protocol / alias definitions placed above their first use and imports fixed.
3. **Decisions**: one line each for non-obvious choices (why `Sequence` not `list`, why an overload, where `Any` remains and why).
4. **Checker errors fixed**: the original message, the cause, the fix.
5. **Follow-ups**: config changes (strictness flags, overrides), stubs to install, `py.typed`.

Never leave a bare `# type: ignore`; if one is unavoidable, use `# type: ignore[code]  # reason`.

## Scripts

Audit coverage, missing annotations and legacy syntax (stdlib only, never imports the analysed code):

```bash
python scripts/annotation_audit.py src/llm_client.py                       # report for one file
python scripts/annotation_audit.py src/ --target-version 3.12              # 3.12 rewrites: type, PEP 695
python scripts/annotation_audit.py src/ --min-coverage 85                  # CI gate: exit 1 if overall < 85%
python scripts/annotation_audit.py app.py --strict --json                  # exit 1 on any finding, JSON output
python scripts/annotation_audit.py app.py --ignore any-usage,missing-return
cat module.py | python scripts/annotation_audit.py -
```

It reports per-function missing parameter and return annotations with suggested types (from literal defaults; from `return` of literals, f-strings, comparisons, annotated parameters, `self` → `Self`, `cls()` → `Self`; generators → `Iterator[...]`; always-raising → `NoReturn`), coverage for params, returns and overall (`self`/`cls` excluded), and rule-tagged issues with the exact rewrite: `legacy-generic`, `legacy-optional`, `legacy-union`, `legacy-abc`, `legacy-import` (the replacement import lines), `legacy-backport` (`typing_extensions` names already in `typing`), `legacy-alias` and `legacy-typevar` (3.12+), `any-usage`, `mutable-default`, `implicit-optional`, `default-mismatch`. It knows that `from __future__ import annotations` (or target 3.14) makes `X | None` safe in annotations but not in runtime expressions or pydantic fields, and quotes forward references when needed. Exit codes: 0 ok, 1 with `--strict` findings or a failed `--min-coverage` gate, 2 for usage or syntax errors. Inferred types are suggestions: confirm them against the code, then run the real checker.

## Additional Resources

| File | Content |
|------|---------|
| [typing-cheatsheet.md](references/typing-cheatsheet.md) | Every typing construct with syntax per Python version (3.9 to 3.14), imports, old vs new forms |
| [advanced-typing.md](references/advanced-typing.md) | Generics and variance, PEP 695, Protocol, ParamSpec/Concatenate, overload, TypedDict details, TypeGuard vs TypeIs, TypeVarTuple, Self, dataclass_transform, Annotated |
| [ai-ml-typing.md](references/ai-ml-typing.md) | Typing LLM messages, tool schemas, streaming, async clients, callbacks, pydantic vs TypedDict, numpy/torch/jaxtyping, generic VectorStore/Repository, typed config |
| [type-checker-setup.md](references/type-checker-setup.md) | mypy and pyright configs, strictness flags, CI, pre-commit, error messages with fixes, pyrefly / ty |
| [migration-strategy.md](references/migration-strategy.md) | Gradual typing plan for large codebases, stubs, py.typed, untyped dependencies, modernising syntax safely |
