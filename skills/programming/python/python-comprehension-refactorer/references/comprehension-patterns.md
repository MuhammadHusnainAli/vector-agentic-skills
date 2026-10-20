# Comprehension Patterns

Every comprehension form, with the loop it replaces. Examples use LLM, RAG and ML code but every pattern is general Python. Python 3.9+ unless a version tag says otherwise.

## Contents

- [Anatomy and grammar](#anatomy-and-grammar)
- [Mapping](#mapping)
- [Filtering](#filtering)
- [Conditional expressions (choose, do not drop)](#conditional-expressions-choose-do-not-drop)
- [Nested loops and flattening](#nested-loops-and-flattening)
- [Nested comprehensions (building 2-D structures)](#nested-comprehensions-building-2-d-structures)
- [The walrus operator in comprehensions](#the-walrus-operator-in-comprehensions)
- [Dict comprehensions](#dict-comprehensions)
- [Set comprehensions](#set-comprehensions)
- [Grouping and counting](#grouping-and-counting)
- [Identity copies and redundant constructors](#identity-copies-and-redundant-constructors)
- [enumerate, zip and unpacking](#enumerate-zip-and-unpacking)
- [Async comprehensions](#async-comprehensions)
- [Formatting long comprehensions](#formatting-long-comprehensions)
- [Loop to comprehension conversion table](#loop-to-comprehension-conversion-table)

## Anatomy and grammar

```
[ ELEMENT  for TARGET in ITERABLE  (for TARGET in ITERABLE | if CONDITION)* ]
{ KEY: VALUE  for ... }          dict comprehension
{ ELEMENT  for ... }             set comprehension
( ELEMENT  for ... )             generator expression (lazy)
```

The clauses after the element are read exactly like nested statements, top to bottom:

```python
result = [f(x, y) for x in xs if p(x) for y in ys if q(x, y)]

# is equivalent to
result = []
for x in xs:
    if p(x):
        for y in ys:
            if q(x, y):
                result.append(f(x, y))
```

| Part | Rules |
|---|---|
| element | any expression; a conditional expression needs no parentheses, a tuple does: `[(i, x) for ...]` |
| target | a name, tuple or starred unpack: `for i, (a, b) in enumerate(pairs)` |
| first iterable | evaluated once, immediately, in the enclosing scope |
| later iterables | evaluated once per outer item, inside the comprehension scope |
| `if` | any number, AND-ed together; each applies to the clauses before it |
| walrus `:=` | allowed in element and conditions (3.8+), not in the iterable expression, never rebinding an iteration variable |
| `await` / `async for` | only inside `async def` (and in asyncio REPL) |

There is no tuple comprehension. `(x for x in xs)` is a generator; use `tuple(x for x in xs)`.

## Mapping

Transform every item, keep all of them.

```python
# loop
cleaned = []
for doc in docs:
    cleaned.append(doc.page_content.strip())

# comprehension
cleaned = [doc.page_content.strip() for doc in docs]
```

More mapping examples:

```python
messages = [{"role": "user", "content": q} for q in questions]
lengths = [len(tokenizer.encode(t)) for t in texts]
names = [tool["function"]["name"] for tool in tool_schemas]
normalized = [v / norm for v, norm in zip(vectors, norms)]
ids = [f"chunk-{doc_id}-{i}" for i, _ in enumerate(chunks)]
```

When the mapping function already exists and takes one argument, `map` is equally fine:

```python
stripped = list(map(str.strip, lines))       # fine, often fastest
stripped = [line.strip() for line in lines]  # also fine
stripped = list(map(lambda s: s.strip(), lines))  # avoid: slower and noisier
```

## Filtering

Keep items that pass a test. The `if` goes after the `for`.

```python
# loop
relevant = []
for hit in hits:
    if hit.score >= 0.75:
        relevant.append(hit)

relevant = [hit for hit in hits if hit.score >= 0.75]
```

Filter plus map:

```python
user_texts = [m["content"] for m in messages if m["role"] == "user"]
non_empty = [line.rstrip("\n") for line in lines if line.strip()]
python_files = [p for p in root.rglob("*.py") if "venv" not in p.parts]
```

Multiple conditions: chained `if`s and `and` are equivalent; prefer `and` once you have two.

```python
good = [c for c in chunks if c.score > 0.5 if c.lang == "en"]
good = [c for c in chunks if c.score > 0.5 and c.lang == "en"]
```

`continue` guards in a loop become negated conditions:

```python
for hit in hits:
    if hit.score < min_score:
        continue
    out.append(hit.text)

out = [hit.text for hit in hits if hit.score >= min_score]
# Note: not (a < b) and (a >= b) differ when a or b is NaN. If scores can be NaN,
# write `if not hit.score < min_score` to keep the loop's exact behaviour.
```

`filter` with `None` drops falsy values:

```python
non_empty = list(filter(None, texts))  # same as [t for t in texts if t]
```

## Conditional expressions (choose, do not drop)

An `if/else` before the `for` chooses a value for every item; it never removes items.

```python
labels = ["relevant" if s >= threshold else "irrelevant" for s in scores]

# an if/elif/else chain becomes a chained conditional expression
tiers = ["high" if s > 0.8 else "mid" if s > 0.5 else "low" for s in scores]
```

Combine both forms: choose, then filter.

```python
clipped = [min(s, 1.0) if s > 0 else 0.0 for s in scores if s is not None]
```

More than one `elif` belongs in a helper function or a lookup:

```python
def tier(score: float) -> str:
    if score > 0.9:
        return "excellent"
    if score > 0.75:
        return "good"
    if score > 0.5:
        return "fair"
    return "poor"

tiers = [tier(s) for s in scores]
```

Common mistakes:

```python
# [x for x in xs if x > 0 else 0]    -> SyntaxError: else not allowed in the filter position
# [x if x > 0 for x in xs]           -> SyntaxError: conditional expression needs else
[x if x > 0 else 0 for x in xs]      # correct: choose
[x for x in xs if x > 0]             # correct: drop
```

## Nested loops and flattening

The `for` clauses appear in the same order as the nested loops.

```python
# flatten a list of lists
flat = [tok for sent in sentences for tok in sent]

# flatten tool calls across responses (None-safe)
calls = [call for resp in responses for call in (resp.tool_calls or [])]

# cartesian product with a filter
pairs = [(q, d) for q in queries for d in docs if d.lang == q.lang]
```

Loops that `extend` become an extra `for` clause:

```python
texts = []
for doc in docs:
    texts.extend(splitter.split_text(doc.page_content))

texts = [t for doc in docs for t in splitter.split_text(doc.page_content)]
```

Flattening alternatives:

| Way | When |
|---|---|
| `[x for xs in nested for x in xs]` | need a list, maybe a filter or transform |
| `list(chain.from_iterable(nested))` | pure flatten, fastest for many short lists |
| `sum(nested, [])` | never: quadratic copying |
| `[*a, *b, *c]` | a fixed, small number of known lists |
| recursive generator | arbitrary depth (see generators-and-itertools.md) |

A common bug is reversing the clause order:

```python
[x for x in row for row in matrix]   # NameError (or uses a stale `row`): row is used before defined
[x for row in matrix for x in row]   # correct
```

## Nested comprehensions (building 2-D structures)

A comprehension *inside the element* builds a nested structure; a second `for` clause flattens. Do not confuse them.

```python
matrix = [[0.0] * dim for _ in range(n)]             # n independent rows
bad = [[0.0] * dim] * n                               # n references to ONE row
transpose = [[row[i] for row in matrix] for i in range(len(matrix[0]))]
transpose = [list(col) for col in zip(*matrix)]       # usually clearer
attention_mask = [[1 if tok != pad_id else 0 for tok in seq] for seq in batch]
```

One level of nesting is fine. Two levels (a comprehension in a comprehension in a comprehension) should be unrolled or split into named steps. See [when-not-to-use.md](when-not-to-use.md).

## The walrus operator in comprehensions

`:=` (3.8+) binds a name inside the comprehension so an expensive value is computed once and reused.

```python
# compute once, filter on it, keep it
answers = [parsed for raw in outputs if (parsed := try_parse_json(raw)) is not None]

# avoid double tokenization
fits = [(t, n) for t in texts if (n := len(tokenizer.encode(t))) <= max_tokens]

# equivalent without walrus: a nested generator
fits = [(t, n) for t, n in ((t, len(tokenizer.encode(t))) for t in texts) if n <= max_tokens]
```

Rules and gotchas:

| Rule | Detail |
|---|---|
| binds in the enclosing scope | after the comprehension `parsed` holds the last value computed (like a loop variable would) |
| cannot rebind an iteration variable | `[x := 1 for x in xs]` is a `SyntaxError` |
| not in the iterable expression | `[y for x in (z := data)]` is a `SyntaxError` |
| not in a class-body comprehension | `SyntaxError: assignment expression within a comprehension cannot be used in a class body` |
| parenthesize | `if (y := f(x))` reads better; required in some positions |

A running state with walrus (works, but `itertools.accumulate` is clearer):

```python
total = 0
running = [total := total + n for n in token_counts]
```

## Dict comprehensions

```python
vectors = {rec["id"]: rec["embedding"] for rec in records}
by_name = {tool.name: tool for tool in tools}
config = {k: v for k, v in raw_config.items() if v is not None}
lowercased = {k.lower(): v for k, v in headers.items()}
token_to_id = {tok: i for i, tok in enumerate(vocab)}
```

Behaviour to know:

- Duplicate keys: the last one wins, exactly like repeated `d[k] = v`. If duplicates are a bug, check `len(result) == len(source)`.
- Key and value are evaluated key first, then value (3.8+).
- Insertion order is preserved (3.7+).

Dict inversion:

```python
id_to_label = {v: k for k, v in label_to_id.items()}   # values must be unique and hashable

# values not unique: invert to lists
from collections import defaultdict
label_to_ids = defaultdict(list)
for doc_id, label in labels.items():
    label_to_ids[label].append(doc_id)
```

Merging and filtering dicts:

```python
merged = {**defaults, **overrides}          # all versions
merged = defaults | overrides               # 3.9+
params = {k: v for k, v in kwargs.items() if k in ALLOWED_PARAMS}
```

Building a dict from two lists: `dict(zip(keys, values))` is clearer than a comprehension. With 3.10+ use `zip(keys, values, strict=True)` to catch length mismatches.

`dict.fromkeys(keys, default)` is fine for immutable defaults; never `dict.fromkeys(keys, [])`, all keys share one list. Use `{k: [] for k in keys}`.

## Set comprehensions

```python
sources = {c.metadata["source"] for c in chunks}
seen_hashes = {hashlib.sha256(t.encode()).hexdigest() for t in texts}
vocab = {tok for doc in corpus for tok in doc.split()}
```

A set comprehension dedupes and loses order. To dedupe while keeping first-seen order:

```python
unique_in_order = list(dict.fromkeys(items))   # items must be hashable
```

To dedupe by a key (e.g. near-duplicate chunks by normalized text):

```python
seen: set[str] = set()
unique = []
for c in chunks:
    key = c.text.strip().lower()
    if key not in seen:
        seen.add(key)
        unique.append(c)
```

That loop mutates `seen` while building `unique`: keep it a loop. The comprehension trick `[c for c in chunks if not (k in seen or seen.add(k))]` works but hides a side effect.

## Grouping and counting

Counting: use `Counter`, not a comprehension.

```python
from collections import Counter

counts = {}
for tok in tokens:
    counts[tok] = counts.get(tok, 0) + 1

counts = Counter(tokens)
top = counts.most_common(20)
by_role = Counter(m["role"] for m in messages)
```

Do not count with `{t: tokens.count(t) for t in set(tokens)}`: that is O(n * unique).

Grouping: one pass with `defaultdict(list)`.

```python
from collections import defaultdict

by_doc = {}
for chunk in chunks:
    by_doc.setdefault(chunk.doc_id, []).append(chunk)

by_doc = defaultdict(list)
for chunk in chunks:
    by_doc[chunk.doc_id].append(chunk)
by_doc = dict(by_doc)   # optional: stop auto-creating keys on lookup
```

Grouping with `itertools.groupby` needs the data sorted by the same key:

```python
from itertools import groupby
from operator import attrgetter

key = attrgetter("doc_id")
by_doc = {doc_id: list(group) for doc_id, group in groupby(sorted(chunks, key=key), key=key)}
```

The comprehension `{k: list(g) for k, g in groupby(...)}` is fine *because* each group is materialised with `list` before `groupby` advances. Storing `g` itself gives empty iterators later.

Aggregating per group in a comprehension after grouping:

```python
mean_score = {doc_id: sum(c.score for c in cs) / len(cs) for doc_id, cs in by_doc.items()}
```

## Identity copies and redundant constructors

| Write | Instead of |
|---|---|
| `list(xs)` / `xs.copy()` / `xs[:]` | `[x for x in xs]` |
| `set(xs)` | `{x for x in xs}` |
| `dict(d)` / `d.copy()` | `{k: v for k, v in d.items()}` |
| `list(pairs)` | `[(a, b) for a, b in pairs]` |
| `[f(x) for x in xs]` | `list([f(x) for x in xs])` |
| `{f(x) for x in xs}` | `set(f(x) for x in xs)` |
| `{k: v for k, v in pairs}` or `dict(pairs)` | `dict([(k, v) for k, v in pairs])` |

All of these copies are shallow: nested lists and dicts are shared. Use `copy.deepcopy` for a deep copy.

## enumerate, zip and unpacking

```python
numbered = [f"{i}. {q}" for i, q in enumerate(questions, start=1)]
pairs = [(q, a) for q, a in zip(questions, answers, strict=True)]   # strict: 3.10+
records = [{"id": i, **meta} for i, meta in enumerate(metadatas)]
heads = [first for first, *_ in rows]
cosine = [sum(a * b for a, b in zip(u, v)) for u, v in pairs]
```

## Async comprehensions

Inside `async def` you can use `async for` and `await` in comprehensions (3.6+).

```python
async def collect(stream):
    return [chunk.delta async for chunk in stream if chunk.delta]

async def embed_all(batches, client):
    return [await client.embed(b) async for b in batches]   # sequential, one await at a time
```

A comprehension of `await` calls runs them one after another. For concurrency, build the coroutines in a comprehension and gather them:

```python
import asyncio

async def embed_concurrently(batches, client, limit=8):
    sem = asyncio.Semaphore(limit)

    async def one(batch):
        async with sem:
            return await client.embed(batch)

    return await asyncio.gather(*(one(b) for b in batches))
```

## Formatting long comprehensions

Up to about 80 characters, one line. Longer: one clause per line, closing bracket on its own line. Black and Ruff format this way.

```python
context_blocks = [
    f"[{i}] {hit.metadata['title']}\n{hit.text}"
    for i, hit in enumerate(hits, start=1)
    if hit.score >= min_score
]
```

If it still does not read well, extract the element into a function:

```python
def render_hit(i: int, hit: Hit) -> str:
    return f"[{i}] {hit.metadata['title']}\n{hit.text}"

context_blocks = [render_hit(i, h) for i, h in enumerate(hits, 1) if h.score >= min_score]
```

## Loop to comprehension conversion table

| Loop shape | Comprehension |
|---|---|
| `out = []` / `for x in xs:` / `out.append(f(x))` | `out = [f(x) for x in xs]` |
| `... if p(x): out.append(x)` | `[x for x in xs if p(x)]` |
| `... if p(x): continue` / `out.append(x)` | `[x for x in xs if not p(x)]` |
| `... out.append(a if c else b)` or `if c: append(a) else: append(b)` | `[a if c else b for x in xs]` |
| `for x in xs: for y in f(x): out.append(y)` | `[y for x in xs for y in f(x)]` |
| `for x in xs: out.extend(f(x))` | `[y for x in xs for y in f(x)]` |
| `y = g(x)` / `if y: out.append(y)` | `[y for x in xs if (y := g(x))]` |
| `d = {}` / `d[k(x)] = v(x)` | `{k(x): v(x) for x in xs}` |
| `s = set()` / `s.add(f(x))` | `{f(x) for x in xs}` |
| `d[k] = d.get(k, 0) + 1` | `Counter(k for ...)` |
| `d.setdefault(k, []).append(v)` | keep the loop with `defaultdict(list)` |
| `total += f(x)` | `sum(f(x) for x in xs)` |
| `found = False` / `if p(x): found = True; break` | `any(p(x) for x in xs)` |
| `for x in xs: if p(x): return x` / `return None` | `next((x for x in xs if p(x)), None)` |
| `best = max(...)` updating in a loop | `max(xs, key=score)` |

The script [find_comprehension_candidates.py](../scripts/find_comprehension_candidates.py) detects the first ten shapes automatically and prints the rewrite.
