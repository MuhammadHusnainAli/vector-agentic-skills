# Migration Strategy: Typing an Existing Codebase

How to take an untyped or partially typed Python codebase (an LLM service, a
RAG repo, a research training package) to strict type checking without a
big-bang rewrite, and how to modernise old typing syntax safely.

## Contents

- [Principles](#principles)
- [Phase 0: baseline](#phase-0-baseline)
- [Phase 1: checker on, low strictness](#phase-1-checker-on-low-strictness)
- [Phase 2: type the core data](#phase-2-type-the-core-data)
- [Phase 3: annotate outward from the leaves](#phase-3-annotate-outward-from-the-leaves)
- [Phase 4: strict per package](#phase-4-strict-per-package)
- [Phase 5: ship types](#phase-5-ship-types)
- [Ordering heuristics](#ordering-heuristics)
- [Third-party libraries without types](#third-party-libraries-without-types)
- [Modernising legacy syntax](#modernising-legacy-syntax)
- [Raising the minimum Python version](#raising-the-minimum-python-version)
- [Automated annotation tools](#automated-annotation-tools)
- [Annotating a function: worked example](#annotating-a-function-worked-example)
- [Team conventions](#team-conventions)
- [Anti-patterns](#anti-patterns)

## Principles

1. **Ratchet, never big bang.** Coverage and strictness only go up; CI blocks regressions, not legacy.
2. **Types follow data.** Typing the central data structures (messages, chunks, configs, requests) gives more value than annotating 200 helpers with `dict[str, Any]`.
3. **Boundaries first, then inward.** Validate untyped input once (pydantic, `isinstance`), then everything behind the boundary can be precise.
4. **Every error is either a bug or a missing type.** Fix bugs; model the missing type. Suppress only with an error code and a reason.
5. **The checker is part of the test suite.** It runs on every PR with a pinned version.

## Phase 0: baseline

```bash
# coverage snapshot and the list of untyped functions
python annotation_audit.py src --target-version 3.10 --json > typing-baseline.json
python annotation_audit.py src --target-version 3.10 | tail -3

# how many checker errors at each level?
mypy src --ignore-missing-imports | tail -1
mypy src --strict --ignore-missing-imports | tail -1
pyright src --outputjson | python -c "import json,sys; print(json.load(sys.stdin)['summary'])"
```

Record: overall coverage %, number of errors in default mode, number in strict
mode, the most common error codes (`mypy ... | grep -o '\[[a-z-]*\]' | sort | uniq -c | sort -rn`).
This tells you whether you have a "missing annotations" problem or a "real bugs"
problem.

## Phase 1: checker on, low strictness

Goal: CI runs a checker and is green, catching new bugs in existing code without
demanding annotations.

```toml
[tool.mypy]
python_version = "3.10"
files = ["src"]
check_untyped_defs = true          # checks bodies of untyped functions too
warn_unused_ignores = true
warn_redundant_casts = true
no_implicit_optional = true         # default since mypy 0.990
ignore_missing_imports = false

[[tool.mypy.overrides]]
module = ["faiss.*", "some_untyped_sdk.*"]
ignore_missing_imports = true
```

Fix the errors that appear. In AI codebases, typical real bugs found here:
missing `await` on client calls, `None` returned from a retrieval helper on
empty results and then indexed, wrong argument order in embedding calls, string
vs list confusion (`stop="\n"` vs `stop=["\n"]`), and dicts with typo'd keys.

If the error count is too large to fix at once: pyright/basedpyright baselines
or mypy's per-module `ignore_errors = true` for the worst modules, each with a
ticket to remove it. mypy has no built-in baseline; tools such as
`mypy-baseline` can store and diff a baseline.

## Phase 2: type the core data

Find the dicts that flow everywhere and give them names:

| Untyped today | Becomes |
|---------------|---------|
| `messages: list[dict]` | `list[ChatMessage]` (TypedDict with `Literal` roles) |
| `doc = {"id":..., "text":..., "meta":...}` | `@dataclass(frozen=True, slots=True) class Document` |
| `config = yaml.safe_load(...)` passed around | pydantic `Settings` / `ModelConfig` validated once at startup |
| `results: list[tuple]` from search | `list[Hit]` dataclass or `NamedTuple` |
| `tool = {"name":..., "parameters":...}` | `ToolSpec` TypedDict, or a pydantic model producing the schema |
| `response.json()` everywhere | a pydantic response model per endpoint |

Do this in a `types.py` / `schemas.py` module with no heavy imports so every
module can import it without cycles.

## Phase 3: annotate outward from the leaves

Order of work inside a package:

1. Pure utilities (text cleaning, chunking, scoring, token counting): easy, high reuse.
2. Adapters around external services (LLM client, vector DB, object storage): define a `Protocol` for each and annotate the adapter; this is where `Any` from SDKs is contained.
3. Core domain services (retriever, agent loop, evaluator) that depend on 1 and 2.
4. Entry points (FastAPI routes, CLI commands, jobs).

For each module:

```bash
python annotation_audit.py src/app/chunking.py --target-version 3.10   # what is missing + suggestions
# annotate, then:
mypy src/app/chunking.py --strict
python annotation_audit.py src/app/chunking.py --min-coverage 100
```

Then add the module to the strict list (Phase 4) immediately, so it cannot
regress.

## Phase 4: strict per package

`strict = true` is a global-only option in mypy configs: per-module overrides
must list the individual flags. A practical per-module strict set for modules
that are done:

```toml
[[tool.mypy.overrides]]
module = ["app.schemas", "app.chunking", "app.retrieval.*", "app.clients.*"]
disallow_untyped_defs = true
disallow_incomplete_defs = true
disallow_untyped_calls = true
disallow_untyped_decorators = true
disallow_any_generics = true
warn_return_any = true
```

Or invert it once most code is typed: global `strict = true`, plus an override
that relaxes the remaining legacy modules. pyright: `strict = ["src/app/schemas.py", "src/app/retrieval"]`.

CI gate that only ratchets up:

```bash
python annotation_audit.py src --min-coverage "$(cat .typing-coverage)"
# after improving coverage, bump the number in .typing-coverage in the same PR
```

## Phase 5: ship types

For libraries (internal SDKs, shared RAG components):

1. `pyright --verifytypes yourpkg --ignoreexternal` until the public API is complete.
2. Add an empty `src/yourpkg/py.typed` and make sure the build includes it.
3. Export public names explicitly (`__all__` or `from .x import Name as Name`) so `no_implicit_reexport` users can import them.
4. Run `python -m mypy.stubtest` if you also ship `.pyi` stubs.
5. Note in the changelog that type changes are API changes: narrowing a parameter type or widening a return type breaks downstream type checks.

## Ordering heuristics

| Prefer annotating first | Because |
|-------------------------|---------|
| Functions with many callers | each annotation checks every call site |
| Public API and module boundaries | documents contracts, catches misuse |
| Functions returning `None` sometimes | the source of most runtime `AttributeError`s |
| Code that handles external data (HTTP, LLM output, files) | where wrong assumptions live |
| Async code | missing `await` is invisible without types |
| Recently changed / buggy modules | highest return on effort |

Leave for last: one-off scripts, notebooks, tests (annotate fixtures and
helpers; test functions can stay `-> None` only).

## Third-party libraries without types

| Step | Action |
|------|--------|
| 1 | Check for inline types (newer version may have `py.typed`) or `types-<pkg>` on PyPI |
| 2 | Check typeshed's list of stubs and community stubs (`pandas-stubs`, `types-tensorflow`, `boto3-stubs`) |
| 3 | Wrap the library in a small typed adapter module; only that module imports it |
| 4 | Write a minimal `.pyi` stub for the handful of functions you use (`stubs/<pkg>/__init__.pyi`) |
| 5 | Last resort: per-module `ignore_missing_imports = true`; values from it are `Any`, so annotate at the adapter |

## Modernising legacy syntax

Do syntax modernisation as its own mechanical PR, separate from annotation work
and behaviour changes, so review is trivial.

```bash
# report the rewrites for your minimum version
python annotation_audit.py src --target-version 3.10 --ignore missing-param,missing-return

# autofix with ruff (set target-version = "py310" in [tool.ruff])
ruff check src --select UP006,UP007,UP035,UP037,UP045 --fix
# 3.12+: PEP 695 generics and the type statement (some are unsafe fixes)
ruff check src --select UP040,UP046,UP047 --fix --unsafe-fixes
```

| Rule | Rewrite |
|------|---------|
| UP006 | `List[int]` → `list[int]` |
| UP007 / UP045 | `Union[A, B]` → `A \| B`, `Optional[X]` → `X \| None` |
| UP035 | deprecated `typing` imports → `collections.abc` etc. |
| UP037 | remove quotes from annotations when safe (with deferred annotations) |
| UP040 | `X: TypeAlias = ...` → `type X = ...` |
| UP046 / UP047 | `Generic[T]` classes / functions with TypeVars → PEP 695 |

Safety rules for each rewrite:

| Rewrite | Safe when | Watch out for |
|---------|-----------|---------------|
| `List` → `list` | target ≥ 3.9, or inside annotations with the future import | runtime aliases and `cast()` on 3.8 |
| `Optional[X]` → `X \| None` | target ≥ 3.10, or only inside annotations with the future import / 3.14 | pydantic models, FastAPI params, dataclass fields read by `get_type_hints`, `TypeVar(bound=...)`, aliases: all evaluated at runtime |
| `"Foo" \| None` (forward ref) | annotations deferred | at runtime `str \| None` raises `TypeError`; quote the whole thing: `"Foo \| None"` |
| `typing.Callable` → `collections.abc.Callable` | 3.10+ (3.9.0/3.9.1 had bugs with `Callable[..., T]` and `ParamSpec` at runtime) | |
| `TypeAlias` → `type` | target ≥ 3.12 | a `type` alias is not a class: `isinstance(x, Alias)` and calling it break; pydantic supports `type` aliases in v2.x but check your version |
| `TypeVar` → PEP 695 | target ≥ 3.12 | module-level TypeVars shared across many functions become per-function parameters; that is intended |
| `typing_extensions.X` → `typing.X` | target ≥ the version in the cheatsheet | `typing_extensions.TypedDict`/`TypeVar` also carry newer features (closed TypedDicts, defaults) |

After the rewrite: run the full test suite (runtime annotation consumers fail
at import time, not in the checker), then the checker.

## Raising the minimum Python version

Typing improvements are a good reason to raise the floor. When moving from 3.9:

| New floor | Unlocks |
|-----------|---------|
| 3.10 | `X \| None` everywhere including pydantic/FastAPI, `ParamSpec`, `TypeAlias`, `match` for narrowing, `slots=True` dataclasses |
| 3.11 | `Self`, `Never`, `assert_never`, `Required`/`NotRequired`, `StrEnum`, `TaskGroup`, `ExceptionGroup` |
| 3.12 | `type` statement, PEP 695 generics, `@override`, `Unpack[TypedDict]` for `**kwargs` |
| 3.13 | `TypeIs`, `ReadOnly`, type parameter defaults, `warnings.deprecated` |

Update together: `requires-python` in `pyproject.toml`, `[tool.mypy] python_version`,
`[tool.pyright] pythonVersion`, `[tool.ruff] target-version`, the CI matrix,
and then run the modernisation pass.

## Automated annotation tools

| Tool | What it does | Caveat |
|------|--------------|--------|
| `annotation_audit.py` (this skill) | coverage, missing annotations, safe literal-based suggestions, legacy syntax rewrites | suggestions only; never edits |
| MonkeyType | records runtime types while tests run, then applies annotations | types are as narrow as what tests exercised; review every one |
| pyannotate | similar runtime collection (older, less maintained) | |
| `pyright --createstub`, `stubgen` | stubs for third-party packages | generated stubs are mostly `Any`/`Incomplete`; refine by hand |
| `autotyping` | adds trivially inferable annotations (`-> None`, `-> bool` for literals) | limited scope, very safe |
| ruff `ANN` rules | require annotations | only enforcement |
| ruff `UP` rules | modernise syntax | needs a correct `target-version` |
| LLM assistance | drafts annotations for a module | verify with the checker; LLMs over-use `Any` and `dict` |

## Annotating a function: worked example

Before:

```python
def retrieve(query, store, embedder, k=5, filters=None, min_score=0.0):
    vec = embedder.embed([query])[0]
    hits = store.search(vec, k=k * 2, where=filters)
    good = [h for h in hits if h.score >= min_score]
    if not good:
        return None
    return good[:k]
```

Audit output (abridged):

```
L1    retrieve  [missing: query, store, embedder, k, filters, min_score, return]
         k              -> k: int = 5
         filters        -> filters: <T> | None = None
         min_score      -> min_score: float = 0.0
         return            (return value(s) not inferable from literals)
```

After, reasoning one parameter at a time:

```python
from collections.abc import Mapping

def retrieve(
    query: str,
    store: VectorStore[Chunk],                       # Protocol: any backend works, fakes in tests
    embedder: Embedder,
    k: int = 5,
    filters: Mapping[str, str | int | float | bool] | None = None,   # read-only: Mapping
    min_score: float = 0.0,
) -> list[Hit[Chunk]]:                               # concrete return
    vec = embedder.embed([query])[0]
    hits = store.search(vec, k=k * 2, where=filters)
    return [h for h in hits if h.score >= min_score][:k]
```

The annotation exposed a design smell: returning `None` for "no results" forced
every caller to handle `None`; an empty list is the natural empty value, so the
return type became `list[Hit[Chunk]]` and the `None` branch disappeared.

## Team conventions

Write these down in CONTRIBUTING or the repo's AGENTS/CLAUDE file:

- Minimum Python version and therefore the allowed syntax (`X | None`, `list[...]`, `type` statement or not).
- `from __future__ import annotations`: everywhere, nowhere, or only in non-pydantic modules. Pick one.
- Where shared types live (`app/types.py`), naming (`ChatMessage`, `ToolSpec`, `*Config`).
- When to use TypedDict vs dataclass vs pydantic (see [ai-ml-typing.md](ai-ml-typing.md#pydantic-vs-typeddict-vs-dataclass)).
- `Any` policy: allowed only in adapters around untyped libraries, with a comment.
- Suppression policy: `# type: ignore[code]  # reason`, no bare ignores, `warn_unused_ignores` on.
- New code must be fully annotated; touched functions get annotated in the same PR.

## Anti-patterns

| Anti-pattern | Why it hurts | Instead |
|--------------|--------------|---------|
| `dict[str, Any]` everywhere | no key or value checking, false sense of safety | TypedDict / dataclass / pydantic |
| Annotating to match the bug | e.g. `-> str \| None` because a helper sometimes forgot to return | fix the function |
| `cast()` to silence errors | lies to the checker | narrow, or fix the type upstream |
| Global `ignore_errors = true` | checker runs, checks nothing | per-module, with a ticket |
| `Optional` on every parameter "to be safe" | forces `None` handling everywhere | only where `None` is meaningful |
| `list[T]` parameters | invariance errors for callers, implies mutation | `Sequence[T]` / `Iterable[T]` |
| Returning `Iterable` | callers can't `len()` or index | return `list[T]` |
| Unpinned checker in CI | random red builds | pin and upgrade deliberately |
| Typing tests exhaustively first | low value | type the code under test first |
| `TYPE_CHECKING` imports for pydantic field types | `NameError` / `PydanticUndefinedAnnotation` at runtime | real imports for runtime-evaluated annotations |
