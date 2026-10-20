# Stdlib Power Tools

Standard-library modules that replace hand-written loops, helper classes and small dependencies. Each entry gives the before/after and when to reach for it. Examples assume Python 3.9+; newer APIs are tagged.

## Contents

1. [collections](#collections)
2. [itertools](#itertools)
3. [functools](#functools)
4. [operator](#operator)
5. [pathlib](#pathlib)
6. [contextlib](#contextlib)
7. [dataclasses](#dataclasses)
8. [enum](#enum)
9. [heapq and bisect](#heapq-and-bisect)
10. [Other quick wins](#other-quick-wins)

---

## collections

| Tool | Use it for | Replaces |
|------|-----------|----------|
| `defaultdict(list)` | Grouping | `if k not in d: d[k] = []` |
| `Counter` | Frequencies, top-k, multiset maths | manual count dicts |
| `deque(maxlen=n)` | Sliding windows, bounded history, queues | `list.pop(0)` (O(n)) |
| `OrderedDict` | LRU via `move_to_end` / `popitem(last=False)` | — (plain dict keeps order otherwise) |
| `ChainMap` | Layered config lookup | merged dict copies |
| `namedtuple` | Lightweight immutable records | tuples indexed by position |

```python
from collections import ChainMap, Counter, OrderedDict, defaultdict, deque, namedtuple

# Group chunks by document
by_doc = defaultdict(list)
for chunk in chunks:
    by_doc[chunk.doc_id].append(chunk)

# Label distribution and top tokens
labels = Counter(ex["label"] for ex in dataset)
top_tokens = Counter(tok for text in corpus for tok in text.split()).most_common(20)
labels.update(["positive", "negative"])           # add counts
imbalance = labels.most_common(1)[0][1] / max(labels.total(), 1)   # .total(): 3.10+

# Bounded chat memory: keeps the last 20 turns automatically
history = deque(maxlen=20)
history.append({"role": "user", "content": "hi"})

# Simple LRU cache
class LRU:
    def __init__(self, capacity: int):
        self.capacity, self.data = capacity, OrderedDict()

    def get(self, key):
        if key not in self.data:
            return None
        self.data.move_to_end(key)
        return self.data[key]

    def put(self, key, value):
        self.data[key] = value
        self.data.move_to_end(key)
        if len(self.data) > self.capacity:
            self.data.popitem(last=False)

# Layered configuration: CLI > env > file > defaults
config = ChainMap(cli_args, env_config, file_config, DEFAULTS)
model = config["model"]

# Record type
Hit = namedtuple("Hit", ["doc_id", "score"])
best = max(hits, key=lambda h: h.score)
```

`typing.NamedTuple` gives the same with type hints:

```python
from typing import NamedTuple

class Hit(NamedTuple):
    doc_id: str
    score: float
```

## itertools

| Function | Example | Use case |
|----------|---------|----------|
| `chain.from_iterable` | flatten chunks of docs | one-level flatten |
| `islice` | first n of a stream | `head` of a generator / JSONL file |
| `batched` (3.12+) | `batched(texts, 64)` | API batch limits |
| `pairwise` (3.10+) | consecutive pairs | deltas, overlaps |
| `groupby` | group **sorted** data | runs by key |
| `accumulate` | running totals | cumulative token counts |
| `product` | hyperparameter grids | grid search |
| `combinations` | pairwise comparisons | duplicate detection |
| `zip_longest` | align uneven sequences | padding |
| `count`, `cycle`, `repeat` | infinite counters / round-robin | id generation, key rotation |
| `takewhile`, `dropwhile` | prefix/suffix by condition | header skipping |
| `starmap` | apply to argument tuples | `starmap(pow, pairs)` |
| `tee` | duplicate an iterator | rarely; prefer a list |

```python
from itertools import accumulate, chain, combinations, cycle, groupby, islice, product

# Peek at the first 5 records of a huge JSONL file without reading it all
with open("train.jsonl", encoding="utf-8") as f:
    sample = [json.loads(line) for line in islice(f, 5)]

# Grid search over generation params
grid = [dict(temperature=t, top_p=p) for t, p in product([0.0, 0.3, 0.7], [0.9, 1.0])]

# Pack chunks into a context window by cumulative token count
lengths = [len(enc.encode(c.text)) for c in ranked_chunks]
fits = [c for c, total in zip(ranked_chunks, accumulate(lengths)) if total <= budget]

# groupby needs input sorted by the same key
rows.sort(key=lambda r: r["doc_id"])
for doc_id, group in groupby(rows, key=lambda r: r["doc_id"]):
    merge(doc_id, list(group))

# Near-duplicate check over all pairs (O(n^2): small n only)
dupes = [(a.id, b.id) for a, b in combinations(docs, 2) if jaccard(a, b) > 0.9]

# Round-robin over API keys / replicas
endpoints = cycle(["https://a.example", "https://b.example"])
next_url = next(endpoints)
```

## functools

| Tool | Use it for |
|------|-----------|
| `cache` (3.9+) / `lru_cache(maxsize=n)` | Memoising pure functions (tokenizer lookups, query embeddings) |
| `cached_property` | Lazy per-instance computed attributes |
| `partial` | Pre-binding arguments for callbacks / `map` |
| `reduce` | Folding (rarely clearer than a loop or `sum`/`math.prod`) |
| `wraps` | Writing decorators that keep `__name__` / `__doc__` |
| `singledispatch` | Type-based function overloading |
| `total_ordering` | Fill in comparison methods from `__eq__` + `__lt__` |

```python
import functools
import time

@functools.cache
def get_tokenizer(name: str):
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(name)

def timed(fn):
    @functools.wraps(fn)                     # keeps fn.__name__, docstring, signature for tooling
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            logger.info("%s took %.1f ms", fn.__name__, (time.perf_counter() - start) * 1000)
    return wrapper

@functools.singledispatch
def to_text(obj) -> str:
    raise TypeError(f"cannot convert {type(obj).__name__}")

@to_text.register
def _(obj: str) -> str:
    return obj

@to_text.register
def _(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False)

embed_small = functools.partial(embed, model="text-embedding-3-small")
vectors = list(map(embed_small, texts))
```

Caching caveats: arguments must be hashable; cached return values are shared, so return immutable objects (tuples, frozen dataclasses); `lru_cache` on methods keeps instances alive; it does not cache coroutines' results.

## operator

```python
from operator import attrgetter, itemgetter, methodcaller

hits.sort(key=attrgetter("score"), reverse=True)        # instead of lambda h: h.score
rows.sort(key=itemgetter("doc_id", "chunk_index"))     # multi-key
ids = list(map(itemgetter("id"), records))
stripped = list(map(methodcaller("strip"), lines))
```

`attrgetter`/`itemgetter` are faster than lambdas and read as data.

## pathlib

| os / glob | pathlib |
|-----------|---------|
| `os.path.join(a, b)` | `Path(a) / b` |
| `os.path.exists(p)` | `p.exists()` |
| `os.path.basename(p)` | `p.name` |
| `os.path.splitext(p)[0]` | `p.stem` (name) / `p.with_suffix("")` (path) |
| `os.path.splitext(p)[1]` | `p.suffix` |
| `os.path.dirname(p)` | `p.parent` |
| `os.path.abspath(p)` | `p.resolve()` |
| `os.makedirs(d, exist_ok=True)` | `d.mkdir(parents=True, exist_ok=True)` |
| `os.listdir(d)` | `d.iterdir()` |
| `glob.glob("**/*.md", recursive=True)` | `Path().glob("**/*.md")` / `rglob("*.md")` |
| `open(p).read()` | `p.read_text(encoding="utf-8")` |
| `os.remove(p)` | `p.unlink(missing_ok=True)` (3.8+) |
| `os.rename(a, b)` | `a.rename(b)` / `a.replace(b)` |
| `os.path.getsize(p)` | `p.stat().st_size` |
| `os.walk(d)` | `d.walk()` (3.12+) |

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

def iter_documents(folder: Path, exts=(".md", ".txt")):
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.suffix.lower() in exts:
            yield path.relative_to(folder).as_posix(), path.read_text(encoding="utf-8")

out = DATA / "embeddings" / f"{run_id}.npy"
out.parent.mkdir(parents=True, exist_ok=True)
```

Libraries accepting paths should take `str | os.PathLike` and call `Path(p)` once at the boundary.

## contextlib

| Tool | Use it for |
|------|-----------|
| `contextmanager` | Turn a generator into a `with` block (setup/teardown) |
| `asynccontextmanager` | Same for async (FastAPI lifespan, pooled clients) |
| `suppress(*excs)` | Intentionally ignore specific exceptions |
| `ExitStack` / `AsyncExitStack` | A dynamic number of resources |
| `closing(obj)` | Objects with `.close()` but no context-manager support |
| `nullcontext(x)` | Optional context managers (`lock if threaded else nullcontext()`) |
| `redirect_stdout` | Capture noisy library prints in tests/tools |
| `chdir` (3.11+) | Temporarily change directory |

```python
import time
from contextlib import ExitStack, contextmanager, nullcontext, suppress

@contextmanager
def timer(name: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        logger.info("%s: %.2fs", name, time.perf_counter() - start)

with timer("embed corpus"):
    vectors = embed_corpus(texts)

with suppress(FileNotFoundError):
    Path("index.lock").unlink()

def write_shards(paths: list[Path], rows):
    with ExitStack() as stack:
        files = [stack.enter_context(p.open("w", encoding="utf-8")) for p in paths]
        for i, row in enumerate(rows):
            files[i % len(files)].write(json.dumps(row) + "\n")

def maybe_locked(lock=None):
    return lock if lock is not None else nullcontext()
```

## dataclasses

```python
from dataclasses import asdict, dataclass, field, replace

@dataclass(frozen=True)
class RetrievalConfig:
    top_k: int = 5
    min_score: float = 0.2
    rerank: bool = True
    filters: dict = field(default_factory=dict)    # never filters: dict = {}

    def __post_init__(self):
        if self.top_k <= 0:
            raise ValueError("top_k must be positive")

base = RetrievalConfig()
strict = replace(base, min_score=0.5)            # copy with changes (immutable update)
payload = asdict(strict)                          # recursive dict for JSON/logging
```

| Option | Version | Effect |
|--------|---------|--------|
| `frozen=True` | 3.7 | Immutable, hashable |
| `order=True` | 3.7 | Generates `<`, `<=`, ... |
| `slots=True` | 3.10 | `__slots__`: less memory, no typo attributes |
| `kw_only=True` | 3.10 | All fields keyword-only |
| `field(repr=False)` | 3.7 | Hide secrets/large arrays from repr |

dataclass vs pydantic: use dataclasses for internal values; pydantic at trust boundaries (API payloads, LLM JSON, config files) where validation and coercion are needed.

## enum

```python
from enum import Enum, Flag, auto

class FinishReason(str, Enum):          # 3.11+: StrEnum
    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    CONTENT_FILTER = "content_filter"

reason = FinishReason(choice.finish_reason)     # raises ValueError on unknown values
if reason is FinishReason.LENGTH:
    logger.warning("truncated output")

class Capability(Flag):
    TEXT = auto()
    VISION = auto()
    TOOLS = auto()

caps = Capability.TEXT | Capability.TOOLS
if Capability.TOOLS in caps: ...
```

Enums give exhaustiveness in `match`, typo safety, and a single list of valid values for validation.

## heapq and bisect

```python
import bisect
import heapq

# Top-k without full sort: O(n log k)
top = heapq.nlargest(10, scored_docs, key=lambda d: d.score)

# Merge already-sorted result lists from several shards
merged = list(heapq.merge(shard_a, shard_b, key=lambda d: -d.score))

# Priority queue of pending jobs
jobs: list[tuple[int, str]] = []
heapq.heappush(jobs, (priority, job_id))
priority, job_id = heapq.heappop(jobs)

# Bucket a score into bands with bisect
BANDS = [0.3, 0.6, 0.85]
LABELS = ["low", "medium", "high", "exact"]
label = LABELS[bisect.bisect_right(BANDS, score)]
```

## Other quick wins

| Module | Quick win |
|--------|-----------|
| `json` | `json.dumps(obj, ensure_ascii=False)` for non-ASCII text; `separators=(",", ":")` for compact JSONL |
| `textwrap` | `dedent` for prompt constants; `shorten(text, 200)` for log previews |
| `string` | `Template("$context")` for JSON-heavy prompts without brace escaping |
| `re` | Compile once at module level; named groups `(?P<name>...)`; `re.VERBOSE` for complex patterns |
| `statistics` | `mean`, `median`, `quantiles(latencies, n=100)` for p95/p99 |
| `math` | `isclose`, `prod`, `fsum` (accurate float sums), `dist` |
| `time` | `perf_counter()` for durations, never `time.time()` differences |
| `uuid` | `uuid.uuid4().hex` for request ids |
| `hashlib` | `hashlib.sha256(text.encode()).hexdigest()` as a stable cache/dedup key (not `hash()`, which is salted per process) |
| `secrets` | `secrets.token_urlsafe(32)` for tokens, never `random` |
| `concurrent.futures` | `ThreadPoolExecutor(max_workers=8).map(fn, items)` for sync I/O fan-out |
| `asyncio` | `Semaphore`, `TaskGroup` (3.11+), `timeout` (3.11+), `to_thread` (3.9+) |
| `logging` | `getLogger(__name__)` per module; `logger.exception` in `except` |
| `tempfile` | `TemporaryDirectory()` for scratch model checkpoints in tests |
| `shutil` | `shutil.which("ffmpeg")`, `copytree`, `rmtree`, `disk_usage` |
| `sqlite3` | Local caches and eval result stores with zero dependencies |
| `argparse` | CLIs with `--help`; `type=Path`, `choices=[...]` |
| `tomllib` (3.11+) | Read `pyproject.toml` / config files |
| `importlib.metadata` | `version("openai")` to log dependency versions |

```python
import statistics
p50, p95 = statistics.median(latencies), statistics.quantiles(latencies, n=100)[94]

import hashlib
def cache_key(model: str, prompt: str) -> str:
    return hashlib.sha256(f"{model}\0{prompt}".encode()).hexdigest()
```
