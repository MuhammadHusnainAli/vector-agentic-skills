# Serialization and Validation

How to get dataclasses in and out of JSON, YAML, environment variables and databases, and how to validate them. Stdlib-first, with pydantic / msgspec alternatives where they are clearly better.

## Contents

1. [To JSON: asdict and a custom encoder](#to-json-asdict-and-a-custom-encoder)
2. [From JSON: a typed from_dict](#from-json-a-typed-from_dict)
3. [A generic recursive decoder](#a-generic-recursive-decoder)
4. [Enums](#enums)
5. [Datetimes, UUIDs, Paths, Decimals](#datetimes-uuids-paths-decimals)
6. [numpy arrays and tensors](#numpy-arrays-and-tensors)
7. [Key aliases (camelCase, reserved words)](#key-aliases-camelcase-reserved-words)
8. [Unknown and missing keys](#unknown-and-missing-keys)
9. [Config from YAML and environment](#config-from-yaml-and-environment)
10. [JSONL, CSV and DataFrames](#jsonl-csv-and-dataframes)
11. [Pickle and copy](#pickle-and-copy)
12. [Validation strategies](#validation-strategies)
13. [Round-trip tests](#round-trip-tests)

## To JSON: asdict and a custom encoder

```python
import dataclasses
import datetime as dt
import enum
import json
import uuid
from pathlib import Path
from typing import Any

def to_jsonable(obj: Any) -> Any:
    """`default=` hook for json.dumps: handles what asdict leaves behind."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: getattr(obj, f.name) for f in dataclasses.fields(obj)}   # shallow, json recurses
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, (dt.datetime, dt.date, dt.time)):
        return obj.isoformat()
    if isinstance(obj, (uuid.UUID, Path)):
        return str(obj)
    if isinstance(obj, (set, frozenset)):
        return sorted(obj)
    if hasattr(obj, "tolist"):          # numpy arrays / scalars, torch tensors (cpu)
        return obj.tolist()
    raise TypeError(f"{type(obj).__name__} is not JSON serializable")

def dumps(obj: Any, **kw: Any) -> str:
    return json.dumps(obj, default=to_jsonable, ensure_ascii=False, **kw)
```

Why not `json.dumps(asdict(obj))`?

- `asdict` deep-copies every non-container value (slow for embeddings, crashes on locks/clients).
- It leaves `Enum`, `datetime`, `UUID`, `Path`, numpy values untouched, so `json.dumps` raises `TypeError` anyway.

Passing the dataclass directly to `json.dumps(obj, default=to_jsonable)` avoids the deep copy: the encoder calls `default` once per dataclass and recurses into the returned dict.

Selective output (drop `None`, drop private fields, respect `repr=False` as "do not export"):

```python
import dataclasses
from typing import Any

def export(obj: Any, *, drop_none: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in dataclasses.fields(obj):
        if f.name.startswith("_") or f.metadata.get("export") is False:
            continue
        v = getattr(obj, f.name)
        if drop_none and v is None:
            continue
        if dataclasses.is_dataclass(v) and not isinstance(v, type):
            v = export(v, drop_none=drop_none)
        elif isinstance(v, list):
            v = [export(x, drop_none=drop_none) if dataclasses.is_dataclass(x) else x for x in v]
        out[f.metadata.get("json_key", f.name)] = v
    return out
```

## From JSON: a typed from_dict

Explicit is best for API payloads you own the schema of. `scripts/to_dataclass.py json sample.json` generates this shape:

```python
from dataclasses import dataclass, field
from typing import Any, Optional

@dataclass
class Usage:
    prompt_tokens: int
    completion_tokens: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Usage":
        return cls(prompt_tokens=d["prompt_tokens"], completion_tokens=d["completion_tokens"])

@dataclass
class Completion:
    id: str
    text: str
    usage: Optional[Usage] = None
    stop_reason: Optional[str] = field(default=None, metadata={"json_key": "stopReason"})

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Completion":
        return cls(
            id=d["id"],
            text=d["text"],
            usage=Usage.from_dict(d["usage"]) if d.get("usage") is not None else None,
            stop_reason=d.get("stopReason"),
        )
```

Error handling: `KeyError` for a missing required key is a decent error for internal data; at a trust boundary prefer pydantic, which reports every problem with a path (`choices.0.message.content`).

## A generic recursive decoder

When you have many dataclasses and trusted data, a small reflective decoder avoids writing `from_dict` by hand. It uses `typing.get_type_hints` so string annotations and `from __future__ import annotations` work.

```python
import dataclasses
import enum
import sys
import typing
from typing import Any, Optional, Type, TypeVar, Union

T = TypeVar("T")
_UNION_TYPES: tuple = (Union,)
if sys.version_info >= (3, 10):
    import types
    _UNION_TYPES = (Union, types.UnionType)

def from_data(tp: Any, data: Any) -> Any:
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if tp is Any or data is None:
        return data
    if origin in _UNION_TYPES:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return from_data(non_none[0], data)
        for a in non_none:                       # first type that decodes without error
            try:
                return from_data(a, data)
            except (TypeError, ValueError, KeyError):
                continue
        raise TypeError(f"{data!r} matches none of {tp}")
    if origin in (list, tuple, set, frozenset):
        if origin is tuple and len(args) == 2 and args[1] is Ellipsis:
            return tuple(from_data(args[0], x) for x in data)
        if origin is tuple and args:
            return tuple(from_data(a, x) for a, x in zip(args, data))
        inner = args[0] if args else Any
        return origin(from_data(inner, x) for x in data)
    if origin is dict:
        kt, vt = args if args else (Any, Any)
        return {from_data(kt, k): from_data(vt, v) for k, v in data.items()}
    if isinstance(tp, type) and dataclasses.is_dataclass(tp):
        return decode(tp, data)
    if isinstance(tp, type) and issubclass(tp, enum.Enum):
        return tp(data)
    if tp is float and isinstance(data, int):
        return float(data)
    return data

def decode(cls: Type[T], data: dict) -> T:
    hints = typing.get_type_hints(cls)
    kwargs = {}
    for f in dataclasses.fields(cls):
        if not f.init:
            continue
        key = f.metadata.get("json_key", f.name)
        if key in data:
            kwargs[f.name] = from_data(hints[f.name], data[key])
    unknown = set(data) - {f.metadata.get("json_key", f.name) for f in dataclasses.fields(cls)}
    if unknown and getattr(cls, "__strict_keys__", False):
        raise ValueError(f"{cls.__name__}: unknown keys {sorted(unknown)}")
    return cls(**kwargs)
```

Limits: no coercion beyond int to float, no datetime parsing (add a branch for `dt.datetime` using `fromisoformat`), no error aggregation. If you are growing this further, switch to pydantic `TypeAdapter(Cls)`, `cattrs` or `msgspec.convert(data, type=Cls)`, which all decode straight into stdlib dataclasses.

## Enums

```python
import enum
import json
from dataclasses import asdict, dataclass

class Role(str, enum.Enum):            # 3.11+: enum.StrEnum
    USER = "user"
    ASSISTANT = "assistant"

@dataclass
class Turn:
    role: Role
    content: str

t = Turn(Role.USER, "hi")
print(json.dumps(asdict(t)))           # {"role": "user", "content": "hi"}: str mixin serializes as its value
print(Turn(Role("assistant"), "ok"))   # decode by value
```

- A `str`/`int` mixin enum (or `StrEnum`/`IntEnum`) serializes with plain `json.dumps`. A pure `enum.Enum` does not: use `default=`.
- Decode with `Role(value)`; by name with `Role[name]`.
- `Literal["user", "assistant"]` is a lighter alternative when you do not need enum members at runtime.

## Datetimes, UUIDs, Paths, Decimals

```python
import datetime as dt
from dataclasses import dataclass, field

def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)

@dataclass
class RunRecord:
    run_id: str
    started_at: dt.datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict:
        return {"run_id": self.run_id, "started_at": self.started_at.isoformat()}

    @classmethod
    def from_dict(cls, d: dict) -> "RunRecord":
        ts = d["started_at"].replace("Z", "+00:00")     # fromisoformat accepts "Z" only on 3.11+
        return cls(run_id=d["run_id"], started_at=dt.datetime.fromisoformat(ts))
```

| Type | Encode | Decode |
|------|--------|--------|
| `datetime` | `.isoformat()` | `datetime.fromisoformat()` ("Z" suffix 3.11+) |
| epoch seconds (OpenAI `created`) | int | `datetime.fromtimestamp(x, tz=timezone.utc)` |
| `UUID` | `str(u)` | `uuid.UUID(s)` |
| `Path` | `str(p)` / `p.as_posix()` | `Path(s)` |
| `Decimal` (costs) | `str(d)` (keep precision) | `Decimal(s)` |
| `bytes` | `base64.b64encode(b).decode()` | `base64.b64decode(s)` |
| `timedelta` | `.total_seconds()` | `timedelta(seconds=x)` |

Always store timezone-aware UTC datetimes; naive datetimes in eval logs cause silent off-by-hours bugs.

## numpy arrays and tensors

```python
import base64
from dataclasses import dataclass, field

import numpy as np

@dataclass
class EmbeddedChunk:
    chunk_id: str
    text: str
    embedding: np.ndarray = field(repr=False, compare=False)

    def to_dict(self, *, compact: bool = True) -> dict:
        vec = np.asarray(self.embedding, dtype=np.float32)
        emb = base64.b64encode(vec.tobytes()).decode() if compact else vec.tolist()
        return {"chunk_id": self.chunk_id, "text": self.text, "embedding": emb, "dim": int(vec.shape[0])}

    @classmethod
    def from_dict(cls, d: dict) -> "EmbeddedChunk":
        e = d["embedding"]
        vec = (np.frombuffer(base64.b64decode(e), dtype=np.float32) if isinstance(e, str)
               else np.asarray(e, dtype=np.float32))
        return cls(d["chunk_id"], d["text"], vec)
```

- `tolist()` of a 1536-dim float32 vector is ~30 KB of JSON; base64 of raw bytes is ~8 KB. For bulk storage use `.npy`/Parquet/the vector DB, not JSON.
- numpy scalars (`np.float32(0.8)`) are not JSON serializable: convert with `float(x)` or `.item()`.
- Torch: `t.detach().cpu().numpy()` before encoding; never keep CUDA tensors in objects you serialize.

## Key aliases (camelCase, reserved words)

Keep Python names snake_case and valid; store the wire name in `metadata`.

```python
from dataclasses import dataclass, field, fields

@dataclass
class GatewayMeta:
    request_id: str = field(metadata={"json_key": "x-request-id"})
    latency_ms: float = field(metadata={"json_key": "latencyMs"})
    class_: str = field(default="standard", metadata={"json_key": "class"})

def wire_to_kwargs(cls, d: dict) -> dict:
    return {f.name: d[f.metadata.get("json_key", f.name)]
            for f in fields(cls) if f.init and f.metadata.get("json_key", f.name) in d}

meta = GatewayMeta(**wire_to_kwargs(GatewayMeta, {"x-request-id": "r1", "latencyMs": 12.5, "class": "batch"}))
```

Naming rules for generated fields: snake_case camelCase keys, replace invalid characters with `_`, prefix a leading digit (`"1d"` -> `field_1d`), append `_` to keywords (`class_`, `from_`, `import_`), de-duplicate collisions (`userId` and `user_id`) with a suffix.

pydantic equivalent: `Field(alias="latencyMs")`, or `model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)` with `from pydantic.alias_generators import to_camel`; dump with `model_dump(by_alias=True)`.

## Unknown and missing keys

| Policy | Dataclass | pydantic | msgspec |
|--------|-----------|----------|---------|
| Ignore unknown keys | filter by `fields()` | `extra="ignore"` (default) | default |
| Reject unknown keys | compare key sets, raise | `extra="forbid"` | `forbid_unknown_fields=True` |
| Keep unknown keys | `extra: dict = field(default_factory=dict)` | `extra="allow"` (`model_extra`) | not supported |
| Missing optional key | `Optional[T] = None` | `Optional[T] = None` | `Optional[T] = None` |

LLM providers add fields without notice (`refusal`, `annotations`, `service_tier`), so **ignore unknown keys** on responses you consume, and **forbid unknown keys** on tool arguments the model produces (it catches hallucinated parameters).

## Config from YAML and environment

```python
import os
from dataclasses import dataclass, field, fields
from typing import Any

@dataclass(frozen=True)
class TrainConfig:
    model_name: str
    lr: float = 3e-4
    batch_size: int = 32
    epochs: int = 3
    warmup_ratio: float = 0.03
    tags: tuple = ()

    def __post_init__(self) -> None:
        if self.lr <= 0 or self.batch_size <= 0:
            raise ValueError("lr and batch_size must be positive")

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "TrainConfig":
        names = {f.name for f in fields(cls)}
        unknown = set(raw) - names
        if unknown:
            raise ValueError(f"unknown config keys: {sorted(unknown)}")   # catches typos like 'learning_rate'
        conv: dict[str, Any] = {}
        for f in fields(cls):
            if f.name in raw:
                v = raw[f.name]
                conv[f.name] = tuple(v) if f.type in (tuple, "tuple") else v
        return cls(**conv)

    @classmethod
    def from_env(cls, prefix: str = "TRAIN_") -> "TrainConfig":
        casts = {int: int, float: float, str: str, "int": int, "float": float, "str": str}
        raw = {}
        for f in fields(cls):
            env = os.environ.get(prefix + f.name.upper())
            if env is not None:
                raw[f.name] = casts.get(f.type, str)(env) if f.type not in (tuple, "tuple") else tuple(env.split(","))
        return cls.from_mapping(raw)

# YAML (PyYAML): always safe_load
# import yaml
# cfg = TrainConfig.from_mapping(yaml.safe_load(open("train.yaml")))
```

- `f.type` is the annotation object, or a **string** under `from __future__ import annotations`; use `typing.get_type_hints(cls)` for robust code.
- Layering: defaults (class) < YAML file < environment < CLI flags. Merge dicts in that order, then construct once.
- For anything non-trivial (nested sections, secrets, `.env` files), `pydantic-settings` `BaseSettings` is less code and gives validation errors with paths.

## JSONL, CSV and DataFrames

```python
import csv
import json
from dataclasses import asdict, dataclass, fields

@dataclass
class EvalRow:
    example_id: str
    model: str
    score: float
    latency_ms: float

rows = [EvalRow("ex1", "gpt-4o-mini", 0.8, 420.0), EvalRow("ex2", "gpt-4o-mini", 0.6, 380.0)]

with open("eval.jsonl", "w", encoding="utf-8") as fh:
    for r in rows:
        fh.write(json.dumps(asdict(r)) + "\n")

with open("eval.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=[f.name for f in fields(EvalRow)])
    w.writeheader()
    w.writerows(asdict(r) for r in rows)

# import pandas as pd; df = pd.DataFrame([asdict(r) for r in rows])   # pandas also accepts dataclass lists directly
```

Reading back: `EvalRow(**json.loads(line))` for flat rows; CSV values are strings, so cast (`float(row["score"])`) or use a decoder.

## Pickle and copy

- Dataclasses pickle like normal classes (module-level classes only). `slots=True` dataclasses pickle too.
- `copy.copy(obj)` is shallow and does not call `__init__`/`__post_init__`; `replace()` does.
- Multiprocessing / Ray / torch DataLoader workers pickle your objects: keep clients and locks out of data objects (or implement `__getstate__`).

## Validation strategies

| Strategy | Where | Cost | Use for |
|----------|-------|------|---------|
| Type hints + mypy/pyright | static | none at runtime | all internal code |
| `__post_init__` checks | dataclass | tiny | invariants (`0 <= temperature <= 2`), cross-field rules |
| Validate-at-boundary (pydantic) then convert | edge | moderate, once | HTTP bodies, LLM output, config files |
| `TypeAdapter(Dataclass)` | edge | moderate | keep stdlib dataclasses, still validate input |
| `msgspec.convert` / `decode(type=...)` | edge | very low | high-volume JSON |
| `typeguard` / `beartype` decorators | tests / dev | high / low | catching type drift during development |

`__post_init__` validation pattern with error aggregation:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class SamplingConfig:
    temperature: float = 0.7
    top_p: float = 1.0
    max_tokens: int = 512
    n: int = 1

    def __post_init__(self) -> None:
        errors = []
        if not 0.0 <= self.temperature <= 2.0:
            errors.append(f"temperature={self.temperature} not in [0, 2]")
        if not 0.0 < self.top_p <= 1.0:
            errors.append(f"top_p={self.top_p} not in (0, 1]")
        if self.max_tokens < 1:
            errors.append("max_tokens must be >= 1")
        if self.n > 1 and self.temperature == 0.0:
            errors.append("n > 1 with temperature 0 returns identical samples")
        if errors:
            raise ValueError("invalid SamplingConfig: " + "; ".join(errors))
```

Type-check fields at runtime only when the cost is justified (e.g. config objects built from untrusted dicts):

```python
import dataclasses
import typing

def check_simple_types(obj) -> None:
    """Shallow isinstance check for non-generic annotations (int, str, float, bool, classes)."""
    hints = typing.get_type_hints(type(obj))
    for f in dataclasses.fields(obj):
        tp = hints[f.name]
        if isinstance(tp, type) and not isinstance(getattr(obj, f.name), tp):
            if tp is float and isinstance(getattr(obj, f.name), int):
                continue
            raise TypeError(f"{type(obj).__name__}.{f.name}: expected {tp.__name__}, "
                            f"got {type(getattr(obj, f.name)).__name__}")
```

## Round-trip tests

```python
import json
from dataclasses import asdict

def test_completion_round_trip():
    raw = {"id": "c1", "text": "hi", "usage": {"prompt_tokens": 3, "completion_tokens": 1}, "stopReason": "end"}
    c = Completion.from_dict(raw)
    assert c.usage is not None and c.usage.prompt_tokens == 3
    again = Completion.from_dict(json.loads(json.dumps(export(c))))
    assert again == c
    assert asdict(c)["stop_reason"] == "end"     # asdict uses Python names, not wire names
```

Test with **real captured payloads** from the provider (redact secrets), including: a tool-call response, a refusal, a truncated response (`finish_reason="length"`), a streaming final chunk, and an error body.
