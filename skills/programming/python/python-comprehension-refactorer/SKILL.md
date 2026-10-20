---
name: python-comprehension-refactorer
description: "Refactor Python loops into list, dict and set comprehensions and generator expressions, and unroll comprehensions that are too clever: filtering, mapping, nested-loop flattening, conditional expressions, walrus in comprehensions, dict inversion, grouping with defaultdict/Counter, lazy generators for sum/any/all/max, streaming large files, itertools (chain, islice, groupby, batched, pairwise, accumulate, product), scoping rules, side-effect anti-patterns and performance (when map/filter or numpy/pandas vectorization win). AI-engineering focus: building prompt lists, batching texts for embeddings, filtering retrieved chunks by score, id->embedding dicts, flattening tool-call results, lazy dataset streaming and token counting. Use when the user asks to make a loop more Pythonic, convert a for loop to a comprehension, simplify or explain a nested comprehension, reduce memory with generators, batch or chunk an iterable, or review .py code for comprehension anti-patterns."
metadata:
  category: programming
  subcategory: python
  version: "1.0.0"
---

# Python Comprehension Refactorer

Turn accumulate-in-a-loop code into comprehensions and generator expressions when that makes it clearer and faster, and turn comprehensions back into loops (or named generator functions) when they have grown past what a reader can hold in their head. The skill covers the whole family: list/set/dict comprehensions, generator expressions, `itertools`, scoping and leakage rules, side-effect anti-patterns and performance. Its examples come from AI-engineering code: prompt construction, embedding batches, retrieval filtering, tool-call flattening, token counting and dataset streaming.

## Trigger Conditions

Activate this skill when the user:
- Asks to make a loop "more Pythonic", "a one-liner", or "a list/dict comprehension"
- Pastes a comprehension and asks what it does, or says it is unreadable
- Builds lists/dicts in loops in RAG, agent, eval or training code and wants it cleaner
- Hits memory problems from materialising large lists (`sum([...])`, reading whole files, embedding all texts at once)
- Needs batching/chunking (`batched`, `islice`), flattening (`chain.from_iterable`), grouping (`groupby`, `defaultdict`) or sliding windows (`pairwise`)
- Asks whether `map`/`filter`, a comprehension or numpy/pandas vectorization is faster
- Wants a review pass over `.py` files for comprehension anti-patterns

## Workflow

```
1. SCAN       -> run scripts/find_comprehension_candidates.py on the file(s)
2. CLASSIFY   -> map, filter, flatten, group, count, reduce, or side effect?
3. CHOOSE     -> list/set/dict comp, generator expr, itertools, Counter/defaultdict, or keep the loop
4. REWRITE    -> apply the suggested code; keep names meaningful; wrap long comps one clause per line
5. CHECK      -> leaked loop variables, class-body scope, exceptions, evaluation order, laziness
6. VERIFY     -> run tests or compare old vs new output on sample data; re-run the script
```

## Decision Table

| The loop body... | Use | Example |
|---|---|---|
| appends a transformed item | list comprehension | `[p.strip() for p in prompts]` |
| appends only when a condition holds | comprehension with `if` | `[c for c in chunks if c.score >= 0.75]` |
| appends one of two values | conditional expression in the element | `["pos" if s > 0 else "neg" for s in scores]` |
| assigns `d[k] = v` | dict comprehension | `{r.id: r.vector for r in rows}` |
| adds to a set | set comprehension | `{c.metadata["source"] for c in chunks}` |
| `extend`s with an inner iterable | two `for` clauses or `chain.from_iterable` | `[t for r in responses for t in r.tool_calls]` |
| computes a temp then filters on it | walrus in the `if` (3.8+) | `[v for x in xs if (v := parse(x)) is not None]` |
| counts keys | `collections.Counter` | `Counter(tokens)` |
| groups values by key | `defaultdict(list)` loop | `groups[c.doc_id].append(c)` |
| feeds `sum/any/all/max/min/join` | generator expression | `sum(len(t) for t in texts)` |
| result is consumed once, maybe huge | generator expression / function | `(json.loads(l) for l in fh)` |
| does I/O, logging, mutation, `try/except`, `break` | keep the `for` loop | writes, retries, early exit |
| numeric work on arrays | numpy/torch vectorization | `scores[scores > 0.75]` |

## Core Rules

1. **A comprehension builds a value. A loop performs actions.** Never use a comprehension for side effects (`[print(x) for x in xs]`, `[db.add(r) for r in rows]`): it allocates a throwaway list of `None` and hides intent.
2. **Two `for` clauses and two `if` clauses are the readability limit.** Past that, or past one level of nesting (a comprehension inside a comprehension inside a comprehension), unroll into a loop or a named generator function.
3. **Clause order equals loop order.** `[x for row in matrix for x in row]` is `for row in matrix: for x in row:`. The element goes first, everything else reads top-down.
4. **Filter `if` goes at the end, choice `if/else` goes in front.** `[x for x in xs if ok(x)]` drops items; `[a if ok(x) else b for x in xs]` keeps every item.
5. **Use a generator expression when the result is consumed once.** `sum(x for x in xs)` needs no extra parentheses when it is the sole argument; `any`/`all` then short-circuit.
6. **Do not compute the same expression twice.** `[f(x) for x in xs if f(x)]` calls `f` twice; use `[y for x in xs if (y := f(x))]` (3.8+) or a nested generator `[y for y in map(f, xs) if y]`.
7. **Comprehension variables do not leak (Python 3).** If code after the loop reads the loop variable, the rewrite changes behaviour. Walrus targets *do* bind in the enclosing scope.
8. **Class bodies are special.** Inside a class body only the outermost iterable can see class-level names; the walrus operator in a comprehension is a `SyntaxError` there.
9. **Grouping is not a comprehension.** `{k: [v for v in vs if key(v) == k] for k in keys}` is O(n*k). Use `defaultdict(list)` in one pass, or `itertools.groupby` on already-sorted data.
10. **Readability beats cleverness.** If a comprehension needs a comment to explain it, give it a name instead: a helper function, a generator function, or an intermediate variable.

## Before / After

**Prompt list with filtering**
```python
# before
prompts = []
for q in questions:
    if q.strip():
        prompts.append(TEMPLATE.format(question=q.strip()))

# after
prompts = [TEMPLATE.format(question=q.strip()) for q in questions if q.strip()]
```

**Retrieved chunks above a score threshold, keeping order**
```python
relevant = [hit.text for hit in hits if hit.score >= min_score]
top_k = sorted(hits, key=lambda h: h.score, reverse=True)[:k]   # not a comprehension job
```

**id -> embedding dict, and inversion**
```python
vectors = {rec["id"]: rec["embedding"] for rec in records}
label_to_id = {label: idx for idx, label in enumerate(labels)}
id_to_label = {idx: label for label, idx in label_to_id.items()}   # values must be unique
```

**Flatten tool calls from several model responses**
```python
calls = [call for resp in responses for call in (resp.tool_calls or [])]
# or, lazily
from itertools import chain
calls = chain.from_iterable(resp.tool_calls or [] for resp in responses)
```

**Parse-and-keep with the walrus operator (3.8+)**
```python
answers = [parsed for raw in outputs if (parsed := try_parse_json(raw)) is not None]
```

**Token counting**
```python
from collections import Counter
counts = Counter(tok for doc in docs for tok in tokenizer.tokenize(doc))
total_tokens = sum(len(tokenizer.encode(t)) for t in texts)      # generator: no temp list
```

**Batching for an embeddings API**
```python
from itertools import batched          # 3.12+; see references for a 3.9 fallback
for batch in batched(texts, 64):
    vectors.extend(client.embed(list(batch)))
```

**Too complex: unroll it**
```python
# before: four for clauses and three ifs on one line
toks = [t.lower() for c in corpora for d in c for s in d.sents for t in s if t.is_alpha if not t.is_stop if len(t) > 2]

# after: a named generator function the reader can follow and test
def content_tokens(corpora):
    for corpus in corpora:
        for doc in corpus:
            for sent in doc.sents:
                for tok in sent:
                    if tok.is_alpha and not tok.is_stop and len(tok) > 2:
                        yield tok.lower()

toks = list(content_tokens(corpora))
```

**Side effects belong in a loop**
```python
# before
[logger.info("upserting %s", c.id) for c in chunks]
# after
for c in chunks:
    logger.info("upserting %s", c.id)
```

## Generators and itertools in One Table

| Need | Tool | Version |
|---|---|---|
| lazily transform/filter | `(f(x) for x in xs if p(x))` | all |
| first match or default | `next((c for c in chunks if c.score > t), None)` | all |
| first N of a stream | `itertools.islice(stream, n)` | all |
| fixed-size batches | `itertools.batched(it, n)` (`strict=True` in 3.13) | 3.12+ |
| flatten one level | `itertools.chain.from_iterable(lists)` | all |
| consecutive pairs | `itertools.pairwise(xs)` | 3.10+ |
| running totals | `itertools.accumulate(token_counts)` | all |
| grid search configs | `itertools.product(lrs, batch_sizes)` | all |
| group sorted runs | `itertools.groupby(sorted_rows, key=...)` | all |
| stop at condition | `itertools.takewhile(pred, it)` | all |
| split stream into N readers | `itertools.tee(it, n)` (buffers!) | all |

Full coverage, including recipes and pitfalls, is in [generators-and-itertools.md](references/generators-and-itertools.md).

## Scoping and Laziness Gotchas

| Gotcha | Example | Fix |
|---|---|---|
| loop variable no longer leaks | code after the loop reads `item` | `last = items[-1] if items else None` |
| class body cannot see class names | `[f"{PREFIX}{n}" for n in NAMES]` in a class raises `NameError` | module constant, `__init__`, or classmethod |
| late-binding lambdas | `[lambda: run(t) for t in tools]` all call the last `t` | `lambda t=t: run(t)` or `functools.partial` |
| generator consumed twice | `g = (h for h in hits); len(list(g)); list(g)` is `[]` | materialise once, or re-create |
| generator outlives a file | `return (l for l in fh)` inside `with open` | `yield` inside the `with` block |
| free variable read late | `norm` reassigned before the generator is iterated | bind first, or build a list |
| `max()`/`min()` on empty input | `max(h.score for h in [])` raises `ValueError` | `default=0.0` |
| `[...][0]` on no match | `IndexError` | `next((... ), None)` |
| `groupby` without sorting | splits equal keys into several groups | sort by the same key, or `defaultdict` |

```python
# leaked variable: before
for chunk in chunks:
    ids.append(chunk.id)
log.info("last chunk %s", chunk.id)

# after: the dependency is explicit
ids = [c.id for c in chunks]
if chunks:
    log.info("last chunk %s", chunks[-1].id)
```

Details and the full list are in [when-not-to-use.md](references/when-not-to-use.md).

## Correctness Checklist

```
- [ ] Same output order and same duplicates (a set/dict comprehension dedupes)
- [ ] Dict comprehension: duplicate keys keep the LAST value, same as the loop
- [ ] No loop variable read after the loop (comprehension vars do not leak)
- [ ] No break/continue/return/try/except/yield needed inside the body
- [ ] Expensive calls not duplicated between element and condition
- [ ] Generators consumed only once (a second pass yields nothing)
- [ ] Laziness does not outlive a resource (file closed, session ended) before iteration
- [ ] Late binding: lambdas created in a comprehension capture the variable, not the value
- [ ] Not inside a class body when the comprehension reads class attributes or uses walrus
```

## Performance Facts

- A list comprehension is faster than the equivalent `append` loop (measured about 8 percent on 3.14, more on 3.9/3.10): it uses a dedicated `LIST_APPEND` bytecode instead of a method lookup and call per item. PEP 709 (3.12) also inlines list/dict/set comprehensions, removing the hidden function call.
- A generator expression is *slower* per item than a list for cheap elements (`sum(x for x in xs)` took 1.5x `sum([x for x in xs])`); choose it for memory and short-circuiting, not raw speed.
- `map(str.strip, lines)` with a builtin or C function is as fast as or faster than a comprehension; `map(lambda ...)` is slower than a comprehension.
- `"".join([...])` with a list is slightly faster than with a generator (join materialises it anyway); this is the one reducer where a list is fine.
- For numeric arrays, numpy/torch vectorization is 10 to 100 times faster than any comprehension: `scores[scores > t]`, `embeddings @ query`, `np.linalg.norm(vecs, axis=1)`.
- Generators trade a little per-item speed for O(1) memory. Use them for streams, files and large corpora, not for 10-element lists you index into.

Numbers, benchmarks and the timing method are in [performance-notes.md](references/performance-notes.md).

## Output Format

When refactoring, respond with:

1. **Findings**: each loop or comprehension, its line range and the category (map, filter, flatten, group, count, reduce, side effect, too complex).
2. **Rewrite**: before and after code for each change, with the target Python version noted when it matters (`batched` 3.12+, `pairwise` 3.10+, walrus 3.8+).
3. **Behaviour notes**: anything that changes (leaked variables, laziness, evaluation count, empty-input errors, ordering, duplicate keys).
4. **Left as a loop**: what you deliberately did not convert, and why.
5. **Verification**: how to confirm equivalence (a test, an assert on sample data, or re-running the script).

## Scripts

Find candidates and get exact replacement code:

```bash
python scripts/find_comprehension_candidates.py rag/pipeline.py
python scripts/find_comprehension_candidates.py src/**/*.py --json          # machine-readable findings
cat agent.py | python scripts/find_comprehension_candidates.py - --strict    # exit 1 if anything is found (CI)
python scripts/find_comprehension_candidates.py ingest.py --max-for 3 --max-ifs 3 --max-line 120
```

`scripts/find_comprehension_candidates.py` parses the code with `ast` (never executes it) and reports:

| Rule | Severity | What it catches |
|---|---|---|
| `loop-to-list/set/dict-comprehension` | medium | `x = []`/`set()`/`{}` followed by a loop that only appends/adds/assigns; handles `if` filters, `continue` guards, nested loops, `if/else`, `extend`, walrus temps, `async for` |
| `loop-to-counter` / `loop-to-defaultdict` | medium / low | counting and grouping loops |
| `side-effect-comprehension` | high | comprehension used as a statement |
| `complex-comprehension` | medium | more than `--max-for` fors or `--max-ifs` ifs, nesting > 2 levels, long lines, side-effect calls inside; prints the unrolled loop or a generator function |
| `materialised-reducer-arg` | medium | `sum([...])`, `any([...])`, `max(list(...))` |
| `len-of-comprehension`, `first-of-comprehension` | low | `len([... if c])`, `[... if c][0]` |
| `identity-comprehension`, `redundant-constructor`, `map-filter-lambda` | low | `[x for x in y]`, `list([...])`, `list(map(lambda ...))` |

Each finding includes line numbers, the suggested code (via `ast.unparse`), behaviour notes (leaked loop variables, class-body scope, NaN-safe negation) and the reference file to read. Exit codes: 0 ran, 1 findings with `--strict`, 2 usage, unreadable file or syntax error.

## Additional Resources

| File | Content |
|------|---------|
| [comprehension-patterns.md](references/comprehension-patterns.md) | Every comprehension form with loop equivalents: filter, map, nested, flatten, conditional, walrus, dict/set, inversion, grouping, Counter |
| [generators-and-itertools.md](references/generators-and-itertools.md) | Generator expressions and functions, laziness, `yield from`, every useful `itertools` function and recipes |
| [when-not-to-use.md](references/when-not-to-use.md) | Scoping and leakage, class-body rules, late binding, side effects, complexity limits, unrolling recipes |
| [performance-notes.md](references/performance-notes.md) | Timings, memory, PEP 709, map/filter vs comprehension, join, numpy/pandas/torch vectorization |
| [ai-data-pipeline-patterns.md](references/ai-data-pipeline-patterns.md) | Prompt lists, embedding batches, retrieval filtering, tool-call flattening, token counting, JSONL streaming, async fan-out |
