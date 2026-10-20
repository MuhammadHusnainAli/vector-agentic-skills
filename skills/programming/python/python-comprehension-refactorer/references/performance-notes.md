# Performance Notes

What comprehensions, generators, `map`/`filter` and vectorized libraries actually cost, how to measure it, and when each wins. Readability decides most choices; this file is for the cases where speed or memory matters.

## Contents

- [Measured timings](#measured-timings)
- [Why comprehensions beat append loops](#why-comprehensions-beat-append-loops)
- [map and filter](#map-and-filter)
- [Generators: memory, not speed](#generators-memory-not-speed)
- [join, sorted and other materialising consumers](#join-sorted-and-other-materialising-consumers)
- [Vectorization with numpy, pandas and torch](#vectorization-with-numpy-pandas-and-torch)
- [Hoisting work out of the loop](#hoisting-work-out-of-the-loop)
- [Measuring correctly](#measuring-correctly)
- [Memory measurement](#memory-measurement)
- [Decision summary](#decision-summary)

## Measured timings

CPython 3.14, 100,000 items, `python -m timeit` best of 5. Absolute numbers vary by machine and version; the ratios are what matter.

| Code | Time | Relative |
|---|---|---|
| `out = []; for x in xs: out.append(x * 2)` | 1.65 ms | 1.00 |
| `[x * 2 for x in xs]` | 1.52 ms | 0.92 |
| `list(map(lambda x: x * 2, xs))` | 2.63 ms | 1.59 |
| `[x for x in xs if x % 3]` | 1.29 ms | |
| `list(filter(lambda x: x % 3, xs))` | 2.22 ms | 1.72 vs comp |
| `[str(x) for x in xs]` | 3.46 ms | |
| `list(map(str, xs))` | 3.16 ms | 0.91 vs comp |
| `sum([x for x in xs])` | 0.69 ms | |
| `sum(x for x in xs)` | 1.04 ms | 1.51 vs list |
| `sum(xs)` | 0.18 ms | 0.26 vs list |
| `"".join([str(x) for x in xs])` | 3.83 ms | |
| `"".join(str(x) for x in xs)` | 4.39 ms | 1.15 vs list |

numpy 2.x on the same machine, 100,000 floats:

| Code | Time |
|---|---|
| `[s for s in scores if s > 0.5]` (Python list) | 1.48 ms |
| `a[a > 0.5]` (numpy boolean mask) | 0.43 ms |
| `[x * 2.0 for x in scores]` | 1.32 ms |
| `a * 2.0` | 0.024 ms (about 55x) |
| `sum(x * y for x, y in zip(scores, scores))` | 2.12 ms |
| `a @ a` | 0.005 ms (about 400x) |
| `[s for s in a if s > 0.5]` (iterating a numpy array in Python) | 4.2 ms (slowest of all) |

Takeaways:

1. A comprehension is modestly faster than an append loop: about 5 to 10 percent on 3.11+ (the adaptive interpreter specialises `list.append`); the gap is larger on 3.9/3.10. Re-measure on your version before quoting numbers.
2. `map`/`filter` with a `lambda` are the slowest option. With a builtin (`str`, `len`, `str.strip`, `operator.itemgetter`) `map` is as fast as or faster than a comprehension.
3. A generator is *slower* per item than a list for cheap elements. Use it for memory and short-circuiting, not speed.
4. A builtin that does the whole job (`sum(xs)`, `max(xs)`, `set(xs)`) beats any comprehension.
5. Iterating a numpy array element by element in Python is worse than iterating a list: each element is boxed into a numpy scalar.

## Why comprehensions beat append loops

The loop pays, per item, for loading `out`, looking up `.append`, and calling it. A list comprehension uses a dedicated `LIST_APPEND` bytecode. Since 3.12 (PEP 709) list, dict and set comprehensions are inlined into the enclosing function, so there is no extra function object or frame either.

```python
import dis
dis.dis("[x * 2 for x in xs]")      # shows LIST_APPEND, no CALL to append
```

Micro-optimising the loop by caching the method (`append = out.append`) closes most of the gap but costs readability. Prefer the comprehension.

## map and filter

| Form | Verdict |
|---|---|
| `map(str.strip, lines)` | fine, fast, lazy |
| `map(int, fields)` | fine |
| `map(operator.itemgetter("text"), hits)` | fine |
| `map(func, xs, ys)` (several iterables) | fine; a comprehension needs `zip` |
| `map(lambda h: h.text, hits)` | prefer `(h.text for h in hits)` |
| `filter(None, xs)` | fine; drops falsy items |
| `filter(lambda x: x.score > t, xs)` | prefer `(x for x in xs if x.score > t)` |
| `list(map(...))` with side-effect functions | use a for loop |

`map` and `filter` return lazy iterators in Python 3; wrap with `list()` when you need a list.

## Generators: memory, not speed

A list of 100,000 ints costs about 800 KB for the pointers alone (`sys.getsizeof([0] * 100_000)` is 800,056 bytes) plus the objects. A generator object is about 200 bytes regardless of length.

```python
import sys
sys.getsizeof([0] * 100_000)                     # 800056
sys.getsizeof(x for x in range(100_000))         # ~200
```

When this matters in AI code:

- summing token counts over a corpus of millions of documents;
- `any`/`all` over expensive checks (model calls) where short-circuit saves money;
- streaming JSONL training data that does not fit in RAM;
- reading embeddings shard by shard into a vector store.

When it does not: small lists, data you will index or iterate twice, and anything passed to a consumer that materialises it anyway.

## join, sorted and other materialising consumers

`str.join` needs the total length before copying, so it converts any iterable to a list first. Passing a list comprehension avoids the generator overhead and is slightly faster. Same for `sorted`, `tuple`, `np.array`, `torch.tensor`, `pd.DataFrame`.

```python
context = "\n\n".join([chunk.text for chunk in top_chunks])   # fine, marginally faster
context = "\n\n".join(chunk.text for chunk in top_chunks)     # also fine
```

## Vectorization with numpy, pandas and torch

When the data is numeric and already in an array, do not loop in Python at all.

| Python comprehension | Vectorized |
|---|---|
| `[s for s in scores if s > t]` | `scores[scores > t]` |
| `[x / n for x, n in zip(vecs, norms)]` | `vecs / norms[:, None]` |
| `[sum(a * b for a, b in zip(q, d)) for d in docs]` | `doc_matrix @ q` |
| `[math.sqrt(sum(v * v for v in row)) for row in m]` | `np.linalg.norm(m, axis=1)` |
| `sorted(range(n), key=lambda i: -scores[i])[:k]` | `np.argsort(-scores)[:k]` or `np.argpartition` |
| `[1 if t != pad else 0 for t in ids]` | `(ids != pad).astype(np.int64)` / `(ids != pad).long()` |
| `[label_map[x] for x in df["label"]]` | `df["label"].map(label_map)` |
| `[len(t) for t in df["text"]]` | `df["text"].str.len()` |
| `[r.a + r.b for r in df.itertuples()]` | `df["a"] + df["b"]` |

Top-k retrieval over embeddings:

```python
import numpy as np

def top_k(query: np.ndarray, doc_matrix: np.ndarray, k: int = 5) -> np.ndarray:
    """Indices of the k most similar rows (cosine), best first."""
    q = query / np.linalg.norm(query)
    d = doc_matrix / np.linalg.norm(doc_matrix, axis=1, keepdims=True)
    sims = d @ q
    idx = np.argpartition(-sims, kth=min(k, len(sims) - 1))[:k]
    return idx[np.argsort(-sims[idx])]
```

Comprehensions still have a place around vectorized code: building the input arrays from Python objects, and mapping indices back to objects.

```python
doc_matrix = np.array([c.embedding for c in chunks], dtype=np.float32)
best = [chunks[i] for i in top_k(q_vec, doc_matrix, k=5)]
```

pandas: `df.apply(f, axis=1)` is a Python loop in disguise; a list comprehension over `zip(df["a"], df["b"])` is often faster than `apply`, and a vectorized column expression is faster than both.

torch: avoid `[t.item() for t in tensor]` (one device sync per element); use `tensor.tolist()` once.

## Hoisting work out of the loop

The biggest wins are rarely loop-vs-comprehension; they are work done per item that could be done once.

```python
# slow: regex compiled per item (cached, but still a lookup), set rebuilt per item
cleaned = [re.sub(r"\s+", " ", t) for t in texts if t.split()[0] not in set(STOPWORDS)]

# fast
WS = re.compile(r"\s+")
stop = frozenset(STOPWORDS)
cleaned = [WS.sub(" ", t) for t in texts if t.split()[0] not in stop]
```

| Per-item cost | Hoist to |
|---|---|
| `x in some_list` | build a `set`/`frozenset` once |
| `re.sub(pattern, ...)` | `re.compile` once |
| `tokenizer = load_tokenizer()` | load once at module or init |
| one API call per item | batch the call (`client.embed(list_of_texts)`) |
| `len(tokenizer.encode(t))` twice | walrus or store the result |

## Measuring correctly

```bash
python -m timeit -s "xs = list(range(100_000))" "[x * 2 for x in xs]"
python -m timeit -s "from mymod import load; data = load()" "process(data)"
```

```python
import timeit

setup = "texts = ['hello world'] * 10_000"
print(min(timeit.repeat("[t.upper() for t in texts]", setup, number=100, repeat=5)))
print(min(timeit.repeat("list(map(str.upper, texts))", setup, number=100, repeat=5)))
```

Rules: measure on realistic sizes, take the minimum of repeats, compare in the same Python version, and profile the whole program (`python -m cProfile -s cumtime app.py` or `py-spy`) before micro-optimising a comprehension that is not the bottleneck. In LLM apps the network call usually dominates by 1000x.

## Memory measurement

```python
import tracemalloc

tracemalloc.start()
texts = [str(i) * 10 for i in range(100_000)]
current, peak = tracemalloc.get_traced_memory()
print(f"peak {peak / 1024:.0f} KiB")      # about 9.5 MiB on 64-bit CPython
tracemalloc.stop()
```

Compare peak memory of the list version and the generator version of a pipeline stage; for streaming code the generator version's peak should not grow with input size.

## Decision summary

| Situation | Fastest readable choice |
|---|---|
| transform a list into a list | list comprehension |
| apply a builtin/C function to each item | `map(func, xs)` |
| transform with a lambda | comprehension |
| reduce (`sum`, `max`, `any`) | builtin on the iterable directly, else generator expression |
| `join` / `sorted` | list comprehension or generator, either |
| numeric array math | numpy/torch vectorization |
| dataframe column math | pandas vectorized expressions |
| huge or unbounded input | generator expression / generator function |
| per-item network or model call | batch the call; comprehension choice is irrelevant |
