# When Not to Use a Comprehension

Comprehensions are expressions that build values. This file covers where they stop being the right tool: scoping rules that change behaviour, side effects, control flow they cannot express, complexity limits, and how to unroll a comprehension cleanly.

## Contents

- [Scoping rules](#scoping-rules)
- [Class bodies](#class-bodies)
- [Late binding in closures](#late-binding-in-closures)
- [Side-effect anti-patterns](#side-effect-anti-patterns)
- [Control flow a comprehension cannot express](#control-flow-a-comprehension-cannot-express)
- [Complexity limits](#complexity-limits)
- [Unrolling recipes](#unrolling-recipes)
- [Duplicated work and evaluation order](#duplicated-work-and-evaluation-order)
- [Mutation while iterating](#mutation-while-iterating)
- [Review checklist](#review-checklist)

## Scoping rules

In Python 3 a comprehension has its own scope. Its iteration variables never leak.

```python
x = "outer"
squares = [x * x for x in range(3)]
print(x)            # "outer": the comprehension's x is separate

for x in range(3):
    pass
print(x)            # 2: a for loop rebinds the enclosing x
```

Consequences when converting a loop:

| Loop code relies on | After converting |
|---|---|
| reading the loop variable after the loop (last item) | `NameError` or a stale outer value; keep `last = items[-1]` explicitly |
| loop variable shadowing an outer name intentionally | outer name no longer overwritten |
| walrus target after the comprehension | still works: `:=` binds in the enclosing function scope |

```python
names = []
for item in items:
    names.append(item.name)
log.info("last processed: %s", item.id)   # depends on the leaked `item`

names = [item.name for item in items]
last = items[-1] if items else None        # make the dependency explicit
```

What the comprehension can read:

- the outermost iterable is evaluated in the enclosing scope, once, before the comprehension starts;
- everything else (element, conditions, inner iterables) is evaluated inside the comprehension scope, which sees enclosing function locals through closures and module globals;
- since 3.12 (PEP 709) list, set and dict comprehensions are inlined into the enclosing function for speed, but the visible scoping behaviour is unchanged. Generator expressions are not inlined.

`locals()` inside a comprehension differs by version (before 3.12 it shows only the comprehension's variables); do not rely on it.

## Class bodies

A class body is not an enclosing scope for nested functions, and a comprehension behaves like a nested function. Only the outermost iterable can see class-level names.

```python
class PromptLibrary:
    PREFIX = "You are a helpful assistant."
    NAMES = ["qa", "summarise"]

    ok = [n.upper() for n in NAMES]                  # fine: NAMES is the outermost iterable
    broken = [f"{PREFIX} {n}" for n in NAMES]        # NameError: PREFIX not visible
    broken2 = [(a, b) for a in NAMES for b in NAMES] # NameError: inner NAMES not visible
```

Fixes: compute it at module level, in `__init__`/`__post_init__`, in a `classmethod`/`functools.cached_property`, or pass the name through the outer iterable:

```python
PREFIX = "You are a helpful assistant."

class PromptLibrary:
    NAMES = ["qa", "summarise"]
    TEMPLATES = {n: f"{PREFIX} Task: {n}" for n in NAMES}   # PREFIX is a global now
```

The walrus operator inside a comprehension in a class body is a `SyntaxError`.

## Late binding in closures

Functions created inside a comprehension capture the *variable*, not its value at creation time.

```python
handlers = [lambda: print(name) for name in ["search", "calc"]]
for h in handlers:
    h()          # prints "calc" twice

handlers = [lambda name=name: print(name) for name in ["search", "calc"]]   # bind now
handlers = [functools.partial(print, name) for name in ["search", "calc"]]  # or partial
```

The same applies to tool registries built with comprehensions:

```python
tools = {spec["name"]: (lambda args, spec=spec: call_tool(spec, args)) for spec in tool_specs}
```

## Side-effect anti-patterns

A comprehension used for its side effects builds and discards a list, reads as if a value matters, and hides control flow.

| Anti-pattern | Write instead |
|---|---|
| `[print(x) for x in xs]` | `for x in xs: print(x)` |
| `[db.add(row) for row in rows]` | `for row in rows: db.add(row)` or `db.add_all(rows)` |
| `[out.append(f(x)) for x in xs]` | `out.extend(f(x) for x in xs)` or `out += [f(x) for x in xs]` |
| `[d.update({k: v}) for k, v in pairs]` | `d.update(pairs)` |
| `[fh.write(line) for line in lines]` | `fh.writelines(lines)` |
| `[t.start() for t in threads]` | a for loop |
| `any(cache.pop(k) for k in keys)` | a for loop; `any` may stop early and skip pops |
| `[seen.add(x) or x for x in xs if x not in seen]` | the explicit loop (see dedupe in comprehension-patterns.md) |
| `list(map(client.delete, ids))` | a for loop (also hides that results are discarded) |

Side effects *inside* a value-producing comprehension (logging, metrics, appending to another list) are also a smell: the reader expects a pure transformation. Split the side effect into a loop, or log after building:

```python
# smell
results = [log_and_return(parse(r)) for r in raw]

# clearer
results = [parse(r) for r in raw]
log.debug("parsed %d results", len(results))
```

Exception: calling a function that *returns* the value you want and also has incidental effects you accept (e.g. a cached `embed()` call) is fine.

## Control flow a comprehension cannot express

Keep a loop when the body needs:

| Need | Why a comprehension does not fit |
|---|---|
| `break` / early exit on a condition after processing | no break; `takewhile` or `next()` only cover simple cases |
| `try` / `except` per item | no statements; wrap in a helper function if you must |
| retries, sleeps, rate-limit backoff | stateful control flow |
| several outputs per iteration (two lists, a dict and a counter) | one comprehension builds one value |
| state carried between iterations (previous item, running buffer) | use a loop or a generator function |
| `await` with concurrency | a comprehension of awaits is sequential; use `asyncio.gather`/`TaskGroup` |
| progress reporting, partial checkpointing | side effects |

Per-item error handling via a helper keeps the comprehension readable:

```python
def safe_parse(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None

parsed = [p for raw in outputs if (p := safe_parse(raw)) is not None]
```

But if you also need to count or log failures, use a loop:

```python
parsed, failures = [], 0
for raw in outputs:
    try:
        parsed.append(json.loads(raw))
    except json.JSONDecodeError:
        failures += 1
```

## Complexity limits

Unroll (or split) when any of these hold. These are the defaults of `scripts/find_comprehension_candidates.py`.

| Signal | Limit | Script flag |
|---|---|---|
| `for` clauses | more than 2 | `--max-for N` |
| `if` clauses | more than 2 | `--max-ifs N` |
| nesting | a comprehension inside a comprehension inside a comprehension | fixed |
| line length | the comprehension makes a line longer than 100 characters | `--max-line N` |
| side-effect calls inside | `print`, `.append`, `.write`, logger calls, `.pop`, ... | fixed |
| needs a comment to understand | judgment | |
| conditional expression chain | more than one `elif` | judgment |

The cost of a clever comprehension is paid by every future reader and in every debugger session: you cannot set a breakpoint on one clause or print an intermediate value.

## Unrolling recipes

Three targets, depending on how the comprehension is used.

**1. Assigned to a name: explicit accumulator loop**

```python
# before
rows = [(doc.id, chunk.text, emb) for doc in docs if doc.ok for chunk, emb in zip(doc.chunks, doc.embs) if emb is not None]

# after
rows = []
for doc in docs:
    if not doc.ok:
        continue
    for chunk, emb in zip(doc.chunks, doc.embs):
        if emb is not None:
            rows.append((doc.id, chunk.text, emb))
```

**2. Used inline (argument, return value, larger expression): named generator function**

```python
def valid_rows(docs):
    """(doc_id, text, embedding) for every chunk that has an embedding."""
    for doc in docs:
        if not doc.ok:
            continue
        for chunk, emb in zip(doc.chunks, doc.embs):
            if emb is not None:
                yield doc.id, chunk.text, emb

store.upsert(list(valid_rows(docs)))
```

A generator function has a name, a docstring, can be unit-tested, and stays lazy.

**3. Split into named intermediate steps**

```python
ok_docs = [d for d in docs if d.ok]
pairs = [(d, c, e) for d in ok_docs for c, e in zip(d.chunks, d.embs)]
rows = [(d.id, c.text, e) for d, c, e in pairs if e is not None]
```

Each step is checkable in a debugger. Costs extra lists; use generators for large inputs.

Nested 3-level comprehension:

```python
# before
batch_ids = [[[vocab[t] for t in sent] for sent in doc] for doc in docs]

# after
def encode_sentence(sent):
    return [vocab[t] for t in sent]

def encode_doc(doc):
    return [encode_sentence(s) for s in doc]

batch_ids = [encode_doc(d) for d in docs]
```

## Duplicated work and evaluation order

```python
# f called twice per kept item
out = [f(x) for x in xs if f(x)]

# once
out = [y for x in xs if (y := f(x))]          # 3.8+
out = [y for y in (f(x) for x in xs) if y]   # any version
out = [y for y in map(f, xs) if y]
```

Order of evaluation for each item: clauses left to right, then the element. Conditions short-circuit, so put the cheap test first:

```python
hits = [h for h in candidates if h.lang == "en" and rerank_score(h) > 0.5]   # rerank only English
```

## Mutation while iterating

Building a new list with a comprehension is the safe way to "remove while iterating":

```python
# bug: skips elements
for msg in history:
    if msg["role"] == "tool":
        history.remove(msg)

# correct: rebuild (slice assignment keeps the same list object for other references)
history[:] = [m for m in history if m["role"] != "tool"]
```

Same for dicts: `RuntimeError: dictionary changed size during iteration` is fixed with `cache = {k: v for k, v in cache.items() if not v.expired}`.

## Review checklist

```
- [ ] Is the result used? If not, it must be a for loop.
- [ ] More than 2 fors / 2 ifs / 1 nesting level / 100 chars? Unroll or split.
- [ ] Any calls with side effects inside? Move them to a loop.
- [ ] Does code after it rely on a leaked loop variable?
- [ ] Inside a class body? Check name visibility and walrus.
- [ ] Lambdas or closures created inside? Bind values with defaults or partial.
- [ ] Same expensive call in element and condition? Use walrus or a nested generator.
- [ ] Does the loop body need try/except, break, retries or multiple outputs? Keep the loop.
```
