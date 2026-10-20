# Modern Python by Version

Features from Python 3.8 to 3.13 that change what "idiomatic" means. Before suggesting a rewrite, check the project's minimum version (`requires-python` in `pyproject.toml`, `python_requires` in `setup.cfg`, the Docker base image, or CI matrix). A suggestion that does not run on the floor version is a bug, not an improvement.

## Contents

1. [Version gate quick table](#version-gate-quick-table)
2. [3.8](#python-38)
3. [3.9](#python-39)
4. [3.10](#python-310)
5. [3.11](#python-311)
6. [3.12](#python-312)
7. [3.13](#python-313)
8. [Deprecations and removals to flag](#deprecations-and-removals-to-flag)
9. [Upgrade playbook](#upgrade-playbook)

---

## Version gate quick table

| Feature | Min version | Replaces |
|---------|-------------|----------|
| Walrus `:=` | 3.8 | assign-then-test |
| Positional-only params `/` | 3.8 | `*args` hacks |
| `f"{x=}"` debug specifier | 3.8 | `f"x={x}"` |
| `functools.cached_property` | 3.8 | hand-rolled lazy attributes |
| `typing.Protocol`, `Literal`, `TypedDict`, `Final` | 3.8 | `typing_extensions` |
| Builtin generics `list[int]` | 3.9 | `typing.List[int]` |
| Dict union `a \| b`, `a \|= b` | 3.9 | `{**a, **b}`, `a.update(b)` |
| `str.removeprefix/removesuffix` | 3.9 | slicing by `len(prefix)` |
| `functools.cache` | 3.9 | `lru_cache(maxsize=None)` |
| `zoneinfo` | 3.9 | `pytz` |
| `match` statement | 3.10 | if/elif chains on structure |
| `X \| Y` unions at runtime, `isinstance(x, int \| str)` | 3.10 | `Union[X, Y]`, tuples |
| Parenthesised context managers | 3.10 | backslashes / nested `with` |
| `zip(strict=True)` | 3.10 | manual length checks |
| `itertools.pairwise` | 3.10 | `zip(xs, xs[1:])` |
| `dataclass(slots=True, kw_only=True)` | 3.10 | manual `__slots__` |
| `asyncio.TaskGroup`, `asyncio.timeout` | 3.11 | `gather` + manual cancel, `wait_for` |
| `ExceptionGroup`, `except*` | 3.11 | ad-hoc error aggregation |
| `tomllib` | 3.11 | `toml` package (read-only) |
| `enum.StrEnum` | 3.11 | `class E(str, Enum)` |
| `typing.Self`, `LiteralString`, `Required/NotRequired` | 3.11 | TypeVar bound to class |
| `datetime.UTC` | 3.11 | `timezone.utc` |
| Exception notes `err.add_note()` | 3.11 | re-raising with longer messages |
| `type` statement, `def f[T](x: T)` generics | 3.12 | `TypeVar` declarations |
| `itertools.batched` | 3.12 | slicing helpers |
| f-string grammar relaxed (nested same quotes) | 3.12 | quote juggling |
| `@typing.override` | 3.12 | comments |
| `pathlib.Path.walk` | 3.12 | `os.walk` |
| `copy.replace`, free-threaded build (experimental), `warnings.deprecated` | 3.13 | `dataclasses.replace` for more types, custom decorators |

## Python 3.8

**Walrus operator**

```python
while (batch := queue.get_batch(64)):
    process(batch)

if (n := len(tokens)) > MAX_TOKENS:
    raise ValueError(f"prompt has {n} tokens (max {MAX_TOKENS})")

clean = [y for x in raw if (y := normalize(x))]
```

**Positional-only parameters**

```python
def cosine_similarity(a, b, /, *, eps: float = 1e-8) -> float: ...
```

**Self-documenting f-strings**

```python
logger.debug(f"{batch_size=} {lr=:.1e}")      # "batch_size=32 lr=3.0e-04"
```

(Use this for quick debugging only; for log calls prefer `%`-style arguments.)

**`functools.cached_property`**

```python
from functools import cached_property

class Corpus:
    def __init__(self, docs: list[str]):
        self.docs = docs

    @cached_property
    def vocabulary(self) -> set[str]:
        return {tok for doc in self.docs for tok in doc.split()}
```

## Python 3.9

**Builtin and collections generics in annotations**

```python
from collections.abc import Iterable, Iterator, Mapping, Sequence

def batch(items: Sequence[str], size: int) -> Iterator[list[str]]: ...
def merge(a: Mapping[str, float], b: Mapping[str, float]) -> dict[str, float]: ...
```

Import abstract types from `collections.abc`, not `typing` (the `typing` aliases are deprecated).

**Dict union**

```python
params = DEFAULT_GEN_PARAMS | {"temperature": 0.2}
```

**`removeprefix` / `removesuffix`**

```python
deployment = name.removeprefix("azure/")
stem = filename.removesuffix(".jsonl")
```

**`functools.cache`** — unbounded memoisation, simpler than `lru_cache(maxsize=None)`.

**`zoneinfo`**

```python
from zoneinfo import ZoneInfo
from datetime import datetime
local = datetime.now(ZoneInfo("Europe/Berlin"))
```

**`X | None` in annotations on 3.9** works only with `from __future__ import annotations` (annotations become strings). It fails at runtime anywhere annotations are evaluated (pydantic v1 on 3.9, `typing.get_type_hints`). Use `Optional[X]` if pydantic or FastAPI must evaluate them on 3.9.

## Python 3.10

**Structural pattern matching**

```python
def handle(event: dict) -> None:
    match event:
        case {"type": "content_block_delta", "delta": {"text": str(text)}}:
            sink.write(text)
        case {"type": "message_stop"}:
            sink.close()
        case {"type": "error", "error": {"message": msg}}:
            raise ProviderError(msg)
        case _:
            pass
```

Class patterns with dataclasses:

```python
from dataclasses import dataclass

@dataclass
class ToolCall:
    name: str
    args: dict

match call:
    case ToolCall(name="search", args={"query": str(q)}):
        return search(q)
    case ToolCall(name="calculator", args={"expr": str(e)}):
        return calculate(e)
    case ToolCall(name=other):
        raise UnknownTool(other)
```

When **not** to use `match`: plain value → function maps (use a dict), range checks (use if/elif), or code that must run on 3.9.

**Union types at runtime**

```python
def to_list(x: str | list[str]) -> list[str]:
    return [x] if isinstance(x, str) else x
isinstance(value, int | float)
```

**Parenthesised context managers**

```python
with (
    open("prompts.jsonl", encoding="utf-8") as src,
    open("completions.jsonl", "w", encoding="utf-8") as dst,
):
    ...
```

**`zip(strict=True)`** — raises `ValueError` when lengths differ; use it whenever ids and vectors, or predictions and labels, must line up.

**`itertools.pairwise`**

```python
from itertools import pairwise
deltas = [b - a for a, b in pairwise(timestamps)]
```

**Dataclass slots and kw_only**

```python
@dataclass(slots=True, kw_only=True, frozen=True)
class SamplingParams:
    temperature: float = 0.0
    top_p: float = 1.0
    max_tokens: int = 512
```

**Better error messages** — no code change, but suggests reviewers can trust tracebacks more.

**`encoding="locale"`** and `EncodingWarning` (`python -X warn_default_encoding`) help find missing `encoding=` arguments.

## Python 3.11

**TaskGroup (structured concurrency)**

```python
async def retrieve_all(queries: list[str]) -> list[list[Doc]]:
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(retrieve(q)) for q in queries]
    return [t.result() for t in tasks]
```

If any task fails, the others are cancelled and an `ExceptionGroup` is raised.

**asyncio.timeout**

```python
async with asyncio.timeout(15):
    reply = await llm.chat.completions.create(model=model, messages=messages)
```

**ExceptionGroup and except\***

```python
try:
    results = await retrieve_all(queries)
except* TimeoutError as eg:
    logger.warning("%d retrievals timed out", len(eg.exceptions))
    raise
except* ValueError as eg:
    for err in eg.exceptions:
        logger.error("bad query: %s", err)
    raise
```

**Exception notes**

```python
try:
    record = Example.model_validate(row)
except ValidationError as err:
    err.add_note(f"row {i} in {path}")
    raise
```

**tomllib**

```python
import tomllib
with open("pyproject.toml", "rb") as f:     # binary mode is required
    config = tomllib.load(f)
```

**StrEnum**

```python
from enum import StrEnum

class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

{"role": Role.USER, "content": "hi"}   # serialises as "user"
```

**typing.Self**

```python
from typing import Self

class PromptBuilder:
    def __init__(self) -> None:
        self.parts: list[str] = []

    def add(self, text: str) -> Self:
        self.parts.append(text)
        return self
```

**datetime.UTC** — `datetime.now(UTC)` (alias of `timezone.utc`).

**Performance** — 3.11 is 10–60% faster for pure-Python code; an upgrade can beat micro-optimisation.

## Python 3.12

**Type parameter syntax and type aliases**

```python
def first[T](items: list[T]) -> T:
    return items[0]

class Cache[K, V]:
    def __init__(self) -> None:
        self._data: dict[K, V] = {}

type Embedding = list[float]
type Retriever = Callable[[str, int], list[Doc]]
```

Only on 3.12+; on older versions keep `TypeVar` and `TypeAlias`.

**itertools.batched**

```python
from itertools import batched
for batch in batched(ids, 100):            # tuples of up to 100
    index.upsert(list(batch))
```

**Relaxed f-strings (PEP 701)**

```python
f"{', '.join(f'{k}={v}' for k, v in params.items())}"
f"{payload["model"]}"                      # same quotes inside: 3.12+ only
```

Avoid same-quote nesting if the code must run on 3.11 or older.

**typing.override**

```python
from typing import override

class OpenAIEmbedder(BaseEmbedder):
    @override
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

**Path.walk**

```python
for dirpath, dirnames, filenames in Path("corpus").walk():
    dirnames[:] = [d for d in dirnames if not d.startswith(".")]
```

**Deprecated:** `datetime.utcnow()` and `utcfromtimestamp()` (PY027), `asyncio.get_event_loop()` without a running loop warns.

## Python 3.13

- **`copy.replace()`** works on dataclasses, namedtuples and other types implementing `__replace__`: `cfg2 = copy.replace(cfg, temperature=0.7)`.
- **`warnings.deprecated`** decorator (PEP 702) for API deprecations recognised by type checkers.
- **Free-threaded build** (`python3.13t`, experimental): the GIL can be disabled. Thread-safety of shared state matters more; do not rely on the GIL for atomicity.
- **Experimental JIT** — no idiom change.
- **Improved REPL** with multi-line editing and colour.
- **Removed modules** (PEP 594): `cgi`, `cgitb`, `crypt`, `imghdr`, `mailcap`, `nntplib`, `pipes`, `sndhdr`, `telnetlib`, `uu`, `xdrlib`, `audioop`, `chunk`, `msilib`, `nis`, `ossaudiodev`, `spwd`, `sunau`, and `lib2to3`. Flag imports of them.
- `typing.TypeIs` for precise narrowing functions; `ReadOnly` for TypedDict items.

## Deprecations and removals to flag

| Pattern | Status | Replacement |
|---------|--------|-------------|
| `typing.List`, `Dict`, `Tuple`, `Set` | Deprecated aliases since 3.9 | `list`, `dict`, `tuple`, `set` |
| `typing.Iterable` etc. | Deprecated aliases | `collections.abc.Iterable` |
| `datetime.utcnow()` | Deprecated 3.12 | `datetime.now(timezone.utc)` |
| `asyncio.get_event_loop()` outside a loop | Deprecated 3.10–3.12 | `asyncio.run(main())`, `asyncio.get_running_loop()` |
| `@asyncio.coroutine`, `yield from` coroutines | Removed 3.11 | `async def` / `await` |
| `distutils` | Removed 3.12 | `setuptools`, `sysconfig`, `shutil` |
| `imp` | Removed 3.12 | `importlib` |
| `asynchat`, `asyncore`, `smtpd` | Removed 3.12 | `asyncio`, `aiosmtpd` |
| `pkg_resources` | Deprecated (setuptools) | `importlib.metadata`, `importlib.resources` |
| `ast.Num`, `ast.Str`, `ast.Bytes` | Removed 3.14 | `ast.Constant` |
| `locale.getdefaultlocale()` | Deprecated 3.11 | `locale.getlocale()` |
| `unittest.makeSuite`, `findTestCases` | Removed 3.13 | `unittest.TestLoader` |

## Upgrade playbook

1. Raise the floor in `pyproject.toml` (`requires-python = ">=3.11"`) and CI.
2. Run `pyupgrade --py311-plus` (or `ruff check --select UP --fix`) for mechanical rewrites: typing aliases, f-strings, `super()`, set literals.
3. Run `python scripts/review_idioms.py src/` and handle what remains: `match` candidates (PY029), `utcnow` (PY027), typing generics (PY031).
4. Adopt structural features deliberately, one PR each: `TaskGroup` for fan-out, `asyncio.timeout` for deadlines, `StrEnum` for roles/states, `batched` for batching helpers.
5. Re-run tests under `-W error::DeprecationWarning` to surface remaining deprecated calls.
