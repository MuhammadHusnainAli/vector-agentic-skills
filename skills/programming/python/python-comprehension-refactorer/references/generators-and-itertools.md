# Generators and itertools

Lazy iteration for memory-bounded pipelines: generator expressions, generator functions, and the `itertools` toolbox. Python 3.9+ unless tagged.

## Contents

- [Generator expressions](#generator-expressions)
- [Feeding reducers: sum, any, all, max, min, join](#feeding-reducers-sum-any-all-max-min-join)
- [Generator functions and yield from](#generator-functions-and-yield-from)
- [Laziness pitfalls](#laziness-pitfalls)
- [Streaming large files](#streaming-large-files)
- [itertools reference](#itertools-reference)
- [Batching](#batching)
- [Windows and pairs](#windows-and-pairs)
- [groupby](#groupby)
- [accumulate, product, combinations](#accumulate-product-combinations)
- [Recipes](#recipes)
- [Choosing list vs generator](#choosing-list-vs-generator)

## Generator expressions

Same syntax as a list comprehension with parentheses. Nothing runs until something iterates it; it produces one item at a time and can be consumed once.

```python
squares = (x * x for x in range(10**9))   # instant, O(1) memory
next(squares)                              # 0
next(squares)                              # 1
```

When the generator is the only argument of a call, the call's parentheses are enough:

```python
total = sum(len(t) for t in texts)
total = sum((len(t) for t in texts), start=0)   # extra parentheses needed with a second argument
```

The first iterable is evaluated immediately; everything else is deferred:

```python
gen = (x / norm for x in vectors)   # `vectors` evaluated now
norm = 2.0                          # `norm` looked up lazily: changes the result!
```

## Feeding reducers: sum, any, all, max, min, join

| Call | Prefer | Why |
|---|---|---|
| `sum([f(x) for x in xs])` | `sum(f(x) for x in xs)` | no temporary list |
| `any([p(x) for x in xs])` | `any(p(x) for x in xs)` | stops at first True, skips the rest of `p` calls |
| `all([p(x) for x in xs])` | `all(p(x) for x in xs)` | stops at first False |
| `max([f(x) for x in xs])` | `max(f(x) for x in xs)` or `max(xs, key=f)` | `key=` returns the item, not the score |
| `len([x for x in xs if p(x)])` | `sum(1 for x in xs if p(x))` | count without storing |
| `[x for x in xs if p(x)][0]` | `next((x for x in xs if p(x)), None)` | stops at first match |
| `"".join([...])` | either | `join` builds a list internally; the list form is slightly faster |
| `sorted([...])` | either | `sorted` materialises anyway |

Short-circuiting matters when each check is expensive, for example calling a moderation model:

```python
def is_safe(text: str) -> bool:
    return moderation_client.classify(text).safe   # network call

ok = all(is_safe(t) for t in outputs)       # stops at the first unsafe text
ok = all([is_safe(t) for t in outputs])     # classifies everything first
```

Empty inputs: `max()`/`min()` of an empty iterable raise `ValueError`; pass `default=`:

```python
best = max((h.score for h in hits), default=0.0)
top_hit = max(hits, key=lambda h: h.score, default=None)
```

`sum` of floats accumulates rounding error; `math.fsum` is exact (and in 3.12 `sum` itself uses compensated summation for floats).

## Generator functions and yield from

A function containing `yield` returns a generator. Use one when the logic needs statements (try/except, several steps, state).

```python
from typing import Iterator, Iterable

def clean_lines(lines: Iterable[str]) -> Iterator[str]:
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        yield line
```

`yield from` delegates to another iterable (and forwards `send`/`throw` to sub-generators):

```python
def walk_messages(conversations):
    for conv in conversations:
        yield from conv["messages"]

def flatten(obj):
    """Recursively flatten nested lists/tuples (arbitrary depth)."""
    if isinstance(obj, (list, tuple)):
        for item in obj:
            yield from flatten(item)
    else:
        yield obj

list(flatten([1, [2, [3, [4]]], (5,)]))   # [1, 2, 3, 4, 5]
```

Generator pipelines compose like Unix pipes; each stage holds one item:

```python
lines = read_lines("corpus.txt")
cleaned = clean_lines(lines)
chunks = (c for line in cleaned for c in split_into_chunks(line, 512))
for chunk in chunks:
    index.add(chunk)
```

Type hints: `Iterator[T]` for simple generators; `Generator[Yield, Send, Return]` when you use `send` or `return` values. In 3.13 the last two parameters of `Generator` default to `None`, so `Generator[str]` is valid.

## Laziness pitfalls

| Pitfall | Example | Fix |
|---|---|---|
| consumed once | `g = (x for x in xs); list(g); list(g)` gives `[]` the second time | make a list, or a function returning a new generator |
| truthiness | `if g:` is always True | `first = next(g, None)` or materialise |
| no `len()` / indexing | `len(g)`, `g[0]` raise `TypeError` | `sum(1 for _ in g)`, `next(islice(g, i, None))` |
| closed resource | returning `(l for l in fh)` from inside `with open(...)` | `yield` inside the `with`, or read eagerly |
| late lookup of free variables | `norm` changed before iteration (see above) | bind as default arg or materialise |
| exceptions raised at consumption time | errors appear far from the definition | validate inputs eagerly before returning the generator |
| `StopIteration` inside a generator | becomes `RuntimeError` (PEP 479, 3.7+) | use `next(it, default)` or `return` |

Closed file example:

```python
def bad(path):
    with open(path) as fh:
        return (line.strip() for line in fh)   # file closes on return

def good(path):
    with open(path) as fh:
        for line in fh:
            yield line.strip()                  # file stays open while iterating
```

Consuming a generator partially and abandoning it keeps the file open until the generator is garbage-collected. Use `contextlib.closing(gen)` or exhaust it if you need deterministic cleanup.

## Streaming large files

Never `fh.read().splitlines()` or `json.load` a multi-GB file. Iterate.

```python
import json

def read_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    raise ValueError(f"{path}:{lineno}: {e}") from e

n_long = sum(1 for rec in read_jsonl("train.jsonl") if len(rec["text"]) > 4000)
```

Fixed-size binary chunks with the two-argument `iter`:

```python
from functools import partial

def file_chunks(path, size=1 << 20):
    with open(path, "rb") as fh:
        yield from iter(partial(fh.read, size), b"")
```

CSV rows lazily: `csv.DictReader(fh)` is already an iterator. Gzip: `gzip.open(path, "rt")` iterates lines the same way.

## itertools reference

| Function | What it yields | Typical use |
|---|---|---|
| `count(start, step)` | infinite counter | ids, with `zip` |
| `cycle(it)` | repeats forever (stores a copy) | round-robin API keys |
| `repeat(x, n)` | `x` n times | padding, `map(pow, xs, repeat(2))` |
| `accumulate(it, func, initial=)` | running reduction | cumulative tokens, offsets |
| `batched(it, n)` 3.12+ | tuples of size n (last may be short) | embedding / API batches |
| `batched(it, n, strict=True)` 3.13+ | raises if last batch is short | fixed-shape tensors |
| `chain(*its)` / `chain.from_iterable(its)` | concatenation / flatten one level | merge result lists |
| `compress(data, selectors)` | items where selector is truthy | apply a boolean mask |
| `dropwhile(pred, it)` | skip while pred true, then everything | skip a header |
| `takewhile(pred, it)` | yield while pred true, then stop | stop at a sentinel |
| `filterfalse(pred, it)` | items where pred is false | complement of filter |
| `groupby(it, key)` | (key, group iterator) per consecutive run | sorted grouping |
| `islice(it, start, stop, step)` | slice of any iterator | first N, skip N, sample every k |
| `pairwise(it)` 3.10+ | overlapping pairs | deltas, bigrams |
| `starmap(func, it)` | `func(*args)` per tuple | apply to zipped args |
| `tee(it, n)` | n independent iterators (buffers) | two passes over a stream |
| `zip_longest(*its, fillvalue=)` | zip to the longest | align ragged lists |
| `product(*its, repeat=)` | cartesian product | hyper-parameter grids |
| `permutations(it, r)` | ordered arrangements | tests |
| `combinations(it, r)` | unordered subsets | pairwise similarity |
| `combinations_with_replacement(it, r)` | subsets with repeats | rarely |

## Batching

```python
from itertools import islice

def batched(iterable, n):
    """Backport of itertools.batched (3.12+) for Python 3.9-3.11."""
    if n < 1:
        raise ValueError("n must be at least one")
    it = iter(iterable)
    while batch := tuple(islice(it, n)):
        yield batch

list(batched("ABCDEFG", 3))   # [('A', 'B', 'C'), ('D', 'E', 'F'), ('G',)]
```

Use it for embedding requests, bulk vector-store upserts and DB writes:

```python
for batch in batched(chunks, 100):
    vector_store.upsert(
        ids=[c.id for c in batch],
        vectors=embed([c.text for c in batch]),
        metadata=[c.metadata for c in batch],
    )
```

Batch by token budget instead of count (variable-size batches) needs state, so it is a generator function:

```python
def batch_by_tokens(texts, count_tokens, max_tokens=8000, max_items=256):
    batch, used = [], 0
    for text in texts:
        n = count_tokens(text)
        if batch and (used + n > max_tokens or len(batch) == max_items):
            yield batch
            batch, used = [], 0
        batch.append(text)
        used += n
    if batch:
        yield batch
```

Slicing a list into batches when you already have a list is also fine:

```python
batches = [items[i:i + size] for i in range(0, len(items), size)]
```

## Windows and pairs

```python
from itertools import pairwise, islice
from collections import deque

deltas = [b - a for a, b in pairwise(timestamps)]          # 3.10+
bigrams = list(pairwise(tokens))

def sliding_window(iterable, n):
    """Overlapping windows of size n: ABCDE, 3 -> ABC BCD CDE."""
    it = iter(iterable)
    window = deque(islice(it, n - 1), maxlen=n)
    for x in it:
        window.append(x)
        yield tuple(window)
```

Overlapping text chunks (chunk size and overlap in tokens):

```python
def overlapping_chunks(tokens, size=512, overlap=64):
    step = size - overlap
    return [tokens[i:i + size] for i in range(0, max(len(tokens) - overlap, 1), step)]
```

Pre-3.10 `pairwise`: `zip(xs, xs[1:])` for sequences, or `a, b = tee(it); next(b, None); zip(a, b)` for iterators.

## groupby

`groupby` groups *consecutive* equal keys. Sort by the same key first, unless the data is already ordered (log lines per request, streaming tokens per message).

```python
from itertools import groupby
from operator import itemgetter

rows = sorted(results, key=itemgetter("model"))
for model, group in groupby(rows, key=itemgetter("model")):
    scores = [r["score"] for r in group]       # consume before the next iteration
    print(model, sum(scores) / len(scores))
```

The group iterator is invalidated when `groupby` advances; materialise it if you need it later. If you cannot or do not want to sort, use `defaultdict(list)` (one pass, O(n)).

Run-length encoding:

```python
rle = [(k, sum(1 for _ in g)) for k, g in groupby("aaabccdd")]   # [('a', 3), ('b', 1), ('c', 2), ('d', 2)]
```

## accumulate, product, combinations

```python
from itertools import accumulate, product, combinations
import operator

token_counts = [120, 340, 90, 410]
offsets = list(accumulate(token_counts, initial=0))      # [0, 120, 460, 550, 960]
running_max = list(accumulate(losses, min))               # best loss so far

# keep messages until the context budget is exhausted
from itertools import takewhile
kept = [m for m, total in takewhile(lambda p: p[1] <= budget,
                                    zip(messages, accumulate(len_tokens(m) for m in messages)))]

# hyper-parameter grid
grid = [
    {"lr": lr, "batch_size": bs, "warmup": w}
    for lr, bs, w in product([1e-5, 3e-5], [16, 32], [0, 500])
]

# all unordered pairs for a similarity matrix (n*(n-1)/2 pairs)
pairs = [(a.id, b.id, cosine(a.vec, b.vec)) for a, b in combinations(docs, 2)]
```

`product` evaluates its inputs eagerly into tuples, so infinite iterators do not work with it.

## Recipes

```python
from itertools import chain, islice, zip_longest, tee, filterfalse
from collections import deque

def take(n, iterable):
    return list(islice(iterable, n))

def first(iterable, default=None):
    return next(iter(iterable), default)

def consume(iterator):
    deque(iterator, maxlen=0)

def partition(pred, iterable):
    """Split into (false_items, true_items) iterators."""
    t1, t2 = tee(iterable)
    return filterfalse(pred, t1), filter(pred, t2)

def unique_everseen(iterable, key=None):
    seen = set()
    for item in iterable:
        k = item if key is None else key(item)
        if k not in seen:
            seen.add(k)
            yield item

def roundrobin(*iterables):
    sentinel = object()
    for group in zip_longest(*iterables, fillvalue=sentinel):
        yield from (x for x in group if x is not sentinel)
```

`partition` with `tee` buffers items consumed by one side and not the other; when you need both lists, a single loop with two `append`s is simpler and uses one pass:

```python
passed, failed = [], []
for case in eval_cases:
    (passed if case.score >= 0.8 else failed).append(case)
```

## Choosing list vs generator

| Situation | Choose |
|---|---|
| iterate once, large or unbounded input | generator |
| need `len`, indexing, slicing, multiple passes | list |
| result returned from a public API | list (or document that it is lazy) |
| passing to `sum`/`any`/`all`/`min`/`max` | generator |
| passing to `"".join`, `sorted`, `np.array` | list is fine (they materialise anyway) |
| inside a `with` block that closes a resource | list, or yield inside the block |
| debugging | list (you can print it) |
| feeding an async pipeline / streaming response | async generator (`async def ... yield`) |
