# Type Checker Setup

Configuring mypy and pyright, running them in CI, and fixing the errors they
report. Short notes on pyrefly and ty at the end.

## Contents

- [Which checker](#which-checker)
- [mypy configuration](#mypy-configuration)
- [pyright configuration](#pyright-configuration)
- [Strictness flags explained](#strictness-flags-explained)
- [Running in CI and pre-commit](#running-in-ci-and-pre-commit)
- [Suppressing errors correctly](#suppressing-errors-correctly)
- [Debugging types](#debugging-types)
- [Error catalogue with fixes](#error-catalogue-with-fixes)
- [pyrefly and ty](#pyrefly-and-ty)

## Which checker

| | mypy | pyright (and Pylance in VS Code) |
|-|------|-------------------------------|
| Implementation | Python, plugin system | TypeScript/Node, very fast, incremental |
| Default on unannotated functions | skips the body (unless `check_untyped_defs`) | checks everything, infers return types |
| Plugins | yes (pydantic, SQLAlchemy 1.x, django-stubs) | no plugins; relies on `dataclass_transform` and stubs |
| Inference | conservative, explicit | aggressive narrowing and literal inference |
| Editor | via LSP plugins | built into Pylance / basedpyright |
| Best for | CI gate for typed libraries, plugin-dependent frameworks | editor feedback, large codebases, strictest checking |

Many teams run pyright (or Pylance) in the editor and mypy (or pyright) in CI.
Pick one checker as the CI source of truth; running both doubles the
suppression work because they disagree on edge cases.

## mypy configuration

`pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.11"
files = ["src", "tests"]
strict = true                       # see the flag list below
warn_unreachable = true
enable_error_code = ["ignore-without-code", "redundant-expr", "truthy-bool", "possibly-undefined"]
plugins = ["pydantic.mypy"]
mypy_path = "stubs"
exclude = ["^build/", "^notebooks/"]

[tool.pydantic-mypy]
init_forbid_extra = true
init_typed = true
warn_required_dynamic_aliases = true

# untyped third-party libraries
[[tool.mypy.overrides]]
module = ["faiss.*", "sentence_transformers.*", "legacy_rerank.*"]
ignore_missing_imports = true

# legacy code being migrated: checked, but not strict yet
[[tool.mypy.overrides]]
module = ["app.legacy.*"]
disallow_untyped_defs = false
disallow_incomplete_defs = false
check_untyped_defs = true

# tests: allow unannotated test functions
[[tool.mypy.overrides]]
module = ["tests.*"]
disallow_untyped_defs = false
```

Run: `mypy` (uses `files`), `mypy src/app/llm.py`, `mypy -p app`.
Useful CLI flags: `--strict`, `--python-version 3.10`, `--show-error-codes`
(default on), `--pretty`, `--install-types --non-interactive` (fetch missing
`types-*` stubs), `--cache-dir`, `--html-report out/` / `--txt-report`
(needs `lxml` for HTML) for coverage of typed lines.

## pyright configuration

`pyproject.toml` (or `pyrightconfig.json` with the same keys):

```toml
[tool.pyright]
include = ["src", "tests"]
exclude = ["**/__pycache__", "build", "notebooks"]
pythonVersion = "3.11"
typeCheckingMode = "strict"          # "off" | "basic" | "standard" (default) | "strict"
stubPath = "stubs"
venvPath = "."
venv = ".venv"
reportMissingTypeStubs = false       # noisy for libraries without stubs
reportUnknownMemberType = false      # relax individual strict rules while migrating
reportUnnecessaryTypeIgnoreComment = "warning"
reportImplicitOverride = "warning"   # require @override (opt-in)
strict = ["src/app/core"]            # strict for these paths even if the default mode is lower
```

Per-file: `# pyright: strict` or `# pyright: basic` at the top of a file;
per-rule: `# pyright: reportUnknownMemberType=false`.

Run: `pyright` / `npx pyright` / `pip install pyright` (wraps the Node package),
`pyright --verifytypes mypkg` (reports the completeness of a library's public
API types; great before adding `py.typed`), `pyright --outputjson`.
`basedpyright` is a community fork with extra rules and a baseline file feature.

## Strictness flags explained

mypy `strict = true` enables:

| Flag | Effect |
|------|--------|
| `disallow_untyped_defs` | every function needs full annotations |
| `disallow_incomplete_defs` | partially annotated functions are errors |
| `check_untyped_defs` | type-check bodies of unannotated functions |
| `disallow_untyped_calls` | no calls from typed into untyped functions |
| `disallow_untyped_decorators` | decorators must be typed (else they erase the signature) |
| `disallow_any_generics` | `list` → must be `list[str]` |
| `disallow_subclassing_any` | no subclassing classes from untyped modules |
| `warn_return_any` | returning `Any` from a typed function |
| `warn_unused_ignores` | stale `# type: ignore` |
| `warn_redundant_casts` | `cast(str, x)` where `x` is already `str` |
| `no_implicit_reexport` | `from mod import X` in `mod2` does not re-export `X` unless `__all__` or `import X as X` |
| `strict_equality` | `==` between unrelated types |
| `extra_checks` | stricter TypedDict / `**kwargs` / overload rules |

Not in `strict`, worth enabling: `warn_unreachable`, `disallow_any_unimported`,
`disallow_any_explicit` (very strict), `enable_error_code = ["ignore-without-code", "explicit-override", "possibly-undefined", "truthy-bool"]`.

pyright modes:

| Mode | Adds |
|------|------|
| basic | core errors: unknown attributes, wrong arguments, missing imports |
| standard (default) | + override compatibility, protocol/TypedDict checks, possibly-unbound variables |
| strict | + `reportUnknown*` (any value inferred as Unknown), missing parameter types, unused imports/variables, private usage, unnecessary isinstance/casts |

## Running in CI and pre-commit

GitHub Actions:

```yaml
name: types
on: [push, pull_request]
jobs:
  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -e ".[dev]"             # includes mypy/pyright, stubs, plugins
      - run: mypy
      - run: python tools/annotation_audit.py src --min-coverage 85   # vendored copy of this skill's script
```

pre-commit (mypy runs in an isolated env, so list the stubs and typed deps it needs):

```yaml
repos:
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, types-requests, types-PyYAML, numpy]
        args: [--config-file=pyproject.toml]
  - repo: https://github.com/RobertCraigie/pyright-python
    rev: v1.1.389
    hooks:
      - id: pyright
```

Pin the checker version (`mypy==1.x.y`, `pyright==1.1.xyz`); new releases add
checks and will break CI unannounced otherwise. Use ruff's `UP` (pyupgrade)
rules (`UP006`, `UP007`, `UP035`, `UP040`, `UP045`, `UP046`, `UP047`) to
autofix legacy typing syntax, and `ANN` rules to require annotations, and set
ruff's `target-version` to the same minimum Python.

## Suppressing errors correctly

```python
result = legacy.score(q)  # type: ignore[no-untyped-call]  # vendored lib, no stubs (TICKET-123)
value = data["k"]         # pyright: ignore[reportTypedDictNotRequiredAccess]
```

| Do | Don't |
|----|-------|
| `# type: ignore[error-code]` with a reason | bare `# type: ignore` |
| Fix the root type once (adapter, stub, TypedDict) | sprinkle ignores at every call site |
| `cast(T, x)` only after a check the checker cannot see | `cast` to silence a real mismatch |
| `typing.TYPE_CHECKING` for annotation-only imports | `Any` to avoid an import cycle |
| enable `warn_unused_ignores` / `reportUnnecessaryTypeIgnoreComment` | let stale ignores pile up |

`assert isinstance(x, T)` also narrows, and documents an invariant (but is
stripped with `python -O`; raise explicitly for real validation).

## Debugging types

```python
from typing import reveal_type, assert_type        # 3.11 (typing_extensions before)

reveal_type(store.search(q))                        # checker prints the inferred type
assert_type(first(["a"]), str)                      # checker error if the type differs
```

`reveal_type` without an import also works in mypy and pyright (they treat it
as a builtin), but at runtime it is a `NameError` before 3.11 unless imported.
`reveal_locals()` (mypy only) prints all local types. In VS Code, hover shows
pyright's inferred type.

## Error catalogue with fixes

### None-related

| Message | Fix |
|---------|-----|
| mypy: `Item "None" of "Client \| None" has no attribute "complete"  [union-attr]`; pyright: `"complete" is not a known attribute of "None" (reportOptionalMemberAccess)` | narrow: `if self.client is None: raise RuntimeError("not connected")`; copy attributes to a local before narrowing |
| mypy: `Incompatible default for argument "stop" (default has type "None", argument has type "list[str]")  [assignment]`; pyright: `Expression of type "None" cannot be assigned to parameter of type "list[str]"` | `stop: list[str] \| None = None` |
| mypy: `Argument 1 to "f" has incompatible type "str \| None"; expected "str"  [arg-type]`; pyright: `reportArgumentType` | handle None before the call, or `os.environ["KEY"]` instead of `.get` for required settings |
| mypy: `Incompatible return value type (got "str \| None", expected "str")  [return-value]`; pyright: `reportReturnType` | return a default, raise, or widen the return type |
| pyright: `Object of type "None" is not subscriptable (reportOptionalSubscript)` | same narrowing |

### Annotations missing or incomplete

| Message | Fix |
|---------|-----|
| `Function is missing a type annotation  [no-untyped-def]` | annotate all params and the return |
| `Function is missing a return type annotation  [no-untyped-def]` (often `__init__`) | `-> None` |
| `Call to untyped function "load" in typed context  [no-untyped-call]` | annotate `load`, or stub the library |
| `Need type annotation for "cache" (hint: "cache: dict[<type>, <type>] = ...")  [var-annotated]` | `cache: dict[str, list[float]] = {}` |
| `Missing type parameters for generic type "dict"  [type-arg]` | `dict[str, object]` |
| pyright strict: `Type of parameter "x" is unknown (reportUnknownParameterType)`, `Type of "y" is partially unknown (reportUnknownVariableType)` | annotate; the Unknown usually comes from an untyped library: wrap it |
| `Untyped decorator makes function "handler" untyped  [misc]` | type the decorator with `ParamSpec` |

### Container variance and generics

| Message | Fix |
|---------|-----|
| `Argument 1 to "mean" has incompatible type "list[int]"; expected "list[float]"` + note `"List" is invariant` | accept `Sequence[float]` |
| `Argument 1 has incompatible type "dict[str, int]"; expected "dict[str, float \| int]"` | accept `Mapping[str, float]` |
| `Value of type variable "T" of "f" cannot be "X"  [type-var]` | the argument violates the bound; widen the bound or fix the call |
| `A function returning TypeVar should receive at least one argument containing the same TypeVar  [type-var]` | the type parameter appears only in the return: use a concrete type or `object` |
| pyright: `TypeVar "T" appears only once in generic function signature` | replace it with the bound (or `object`) |

### Classes and inheritance

| Message | Fix |
|---------|-----|
| `Signature of "retrieve" incompatible with supertype "Retriever"  [override]` / `reportIncompatibleMethodOverride` | parameters may only be widened and returns only narrowed; keep parameter names (callers may use keywords) |
| `Cannot instantiate abstract class "Base" with abstract attribute "run"  [abstract]` | implement the method in the subclass |
| `"Settings" has no attribute "api_key"  [attr-defined]` | declare it in the class body: `api_key: str` |
| `Cannot assign to final name "MAX_TOKENS"  [misc]` | it is `Final`; use a new name or drop `Final` |
| `Incompatible types in assignment (expression has type "int", base class "Base" defined the type as "str")` | same type in subclass, or make the base generic |
| `Only concrete class can be given where "type[Base]" is expected  [type-abstract]` | pass a concrete subclass or accept `Callable[[], Base]` |

### Calls

| Message | Fix |
|---------|-----|
| `Unexpected keyword argument "temprature" for "complete"  [call-arg]` / `reportCallIssue` | real typo: fix the call |
| `Missing positional argument "model" in call to "Client"  [call-arg]` | pass it, or give it a default |
| `Too many arguments for "f"  [call-arg]` | check the signature (and decorators that may have erased it) |
| `No overload variant of "complete" matches argument types "str", "bool"  [call-overload]` | add a catch-all `bool` overload |
| `"Coroutine[Any, Any, str]" has no attribute "upper"` / `reportAttributeAccessIssue` | missing `await` |
| `Value of type "Coroutine[Any, Any, None]" must be used  [unused-coroutine]` | missing `await` (or `asyncio.create_task(...)`) |

### Imports and modules

| Message | Fix |
|---------|-----|
| `Library stubs not installed for "requests"  [import-untyped]` | `pip install types-requests` |
| `Skipping analyzing "faiss": module is installed, but missing library stubs or py.typed marker  [import-untyped]` | override `ignore_missing_imports = true` for that module, wrap it in an adapter |
| `Cannot find implementation or library stub for module named "app.x"  [import-not-found]` / `reportMissingImports` | run the checker from the project root / set `mypy_path`, `packages`, or pyright `extraPaths`; ensure the venv is the one being checked |
| `Module "app.models" does not explicitly export attribute "Message"  [attr-defined]` | import from the defining module, or re-export with `__all__` / `from .x import Message as Message` |
| `Name "torch" is not defined` at runtime after moving imports under `TYPE_CHECKING` | add `from __future__ import annotations` or quote the annotation |

### TypedDict, Literal, Protocol

| Message | Fix |
|---------|-----|
| `TypedDict "Message" has no key "tool_calls"  [typeddict-unknown-key]` | add the key (as `NotRequired`) or use a different TypedDict |
| `Missing key "content" for TypedDict "Message"  [typeddict-item]` | supply it, or mark it `NotRequired` |
| `Argument 1 has incompatible type "str"; expected "Literal['user', 'assistant']"` | the variable was widened to `str`: annotate it with the Literal type or use `Final` |
| `Argument 1 has incompatible type "OpenAIEmbedder"; expected "Embedder"` + `Following member(s) ... have conflicts` | the method signature differs from the protocol (often a parameter name or `list` vs `Sequence`); align it |
| `Only @runtime_checkable protocols can be used with instance and class checks` | add `@runtime_checkable` or check differently |

### Any leaks

| Message | Fix |
|---------|-----|
| `Returning Any from function declared to return "dict[str, str]"  [no-any-return]` | validate (`TypeAdapter(...).validate_python(data)`), or annotate an intermediate variable after an `isinstance` check |
| `Expression has type "Any"  [misc]` (with `disallow_any_expr`) | type the boundary that produced it |
| `Class cannot subclass "Module" (has type "Any")  [misc]` | install the library's types or stub the base class |

## pyrefly and ty

Two newer checkers written in Rust focus on speed (whole-repo checks in
seconds) and IDE integration:

| | pyrefly (Meta) | ty (Astral, makers of ruff and uv) |
|-|----------------|-------------------------------------|
| Run | `pip install pyrefly`, `pyrefly init`, `pyrefly check` | `uvx ty check` |
| Config | `pyrefly.toml` or `[tool.pyrefly]` | `ty.toml` or `[tool.ty]` |
| Migration | `pyrefly init` can translate an existing mypy/pyright config | |
| Status (2025–2026) | young, evolving quickly | young, evolving quickly |

Both aim at compatibility with the typing spec, but their error codes and
inference differ from mypy and pyright. Treat them as fast extra feedback (or
evaluate them for the editor) and keep a mature checker as the CI gate until
your codebase is clean under the new tool. Annotations written per the typing
spec work unchanged in all four checkers.
