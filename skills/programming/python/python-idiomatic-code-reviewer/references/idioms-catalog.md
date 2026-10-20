# Idioms Catalog

Before/after pairs for idiomatic Python, numbered for easy citation in reviews ("see idiom 14"). Examples come from LLM, RAG and ML code but every idiom applies to general Python. Baseline is Python 3.9; newer features carry a version tag. Rule ids (PYxxx) map to `scripts/review_idioms.py`.

## Contents

1. [Iteration](#iteration) (1–14)
2. [Unpacking and assignment](#unpacking-and-assignment) (15–21)
3. [Comparisons and truthiness](#comparisons-and-truthiness) (22–29)
4. [Strings](#strings) (30–37)
5. [Dicts and sets](#dicts-and-sets) (38–46)
6. [Functions](#functions) (47–54)
7. [Exceptions](#exceptions) (55–61)
8. [Classes and data](#classes-and-data) (62–67)
9. [Files and resources](#files-and-resources) (68–72)
10. [Module hygiene](#module-hygiene) (73–76)

---

## Iteration

**1. Iterate directly (PY012)**

```python
# Before
for i in range(len(chunks)):
    embed(chunks[i])
# After
for chunk in chunks:
    embed(chunk)
```

**2. Need the index: enumerate (PY012, PY013)**

```python
# Before
i = 0
for doc in docs:
    print(i, doc.title)
    i += 1
# After
for i, doc in enumerate(docs):
    print(i, doc.title)
for rank, hit in enumerate(hits, start=1):   # 1-based ranks
    print(f"{rank}. {hit.doc_id}")
```

**3. Parallel sequences: zip**

```python
# Before
for i in range(len(questions)):
    score(questions[i], answers[i])
# After
for question, answer in zip(questions, answers):
    score(question, answer)
# 3.10+: raise if lengths differ instead of silently truncating
for question, answer in zip(questions, answers, strict=True):
    score(question, answer)
```

**4. Comprehension instead of append loop (PY015)**

```python
# Before
texts = []
for doc in docs:
    if doc.text.strip():
        texts.append(doc.text.strip())
# After
texts = [doc.text.strip() for doc in docs if doc.text.strip()]
# 3.8+: avoid calling strip twice
texts = [t for doc in docs if (t := doc.text.strip())]
```

**5. Dict and set comprehensions**

```python
by_id = {doc.id: doc for doc in docs}
vocab = {tok for text in corpus for tok in text.split()}
inverted = {v: k for k, v in label2id.items()}
```

**6. Generator expressions for aggregates (no intermediate list)**

```python
total_tokens = sum(len(enc.encode(t)) for t in texts)
longest = max(docs, key=lambda d: len(d.text))
```

**7. any / all instead of flag loops (PY016)**

```python
# Before
def has_pii(text):
    for pattern in PII_PATTERNS:
        if pattern.search(text):
            return True
    return False
# After
def has_pii(text):
    return any(p.search(text) for p in PII_PATTERNS)

all_valid = all(0.0 <= s <= 1.0 for s in scores)
```

**8. Dictionary iteration (PY014)**

```python
# Before
for key in config.keys():
    print(key, config[key])
# After
for key, value in config.items():
    print(key, value)
if "temperature" in config: ...      # not: in config.keys()
```

**9. Reverse and sorted iteration**

```python
for msg in reversed(history): ...
for doc in sorted(docs, key=lambda d: d.score, reverse=True): ...
```

**10. Loop with else for "not found"**

```python
for model in candidates:
    if model in available:
        chosen = model
        break
else:
    raise LookupError("no candidate model is available")
```

Use sparingly; `next((m for m in candidates if m in available), None)` is often clearer.

**11. First match: next() with default**

```python
tool = next((t for t in tools if t.name == call.name), None)
if tool is None:
    raise KeyError(call.name)
```

**12. Batching (3.12+ `itertools.batched`)**

```python
from itertools import batched          # 3.12+
for batch in batched(texts, 64):
    vectors.extend(model.encode(list(batch)))

# 3.9–3.11 equivalent
def batched(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]
```

**13. Sliding windows / pairs**

```python
from itertools import pairwise         # 3.10+
gaps = [b.start - a.end for a, b in pairwise(spans)]
# overlapping chunk windows
def windows(tokens, size, stride):
    return [tokens[i:i + size] for i in range(0, max(len(tokens) - size, 0) + 1, stride)]
```

**14. Flatten one level**

```python
from itertools import chain
all_chunks = list(chain.from_iterable(doc.chunks for doc in docs))
# or
all_chunks = [c for doc in docs for c in doc.chunks]
```

## Unpacking and assignment

**15. Tuple unpacking**

```python
# Before
pair = best_match(query)
score = pair[0]
doc = pair[1]
# After
score, doc = best_match(query)
```

**16. Star unpacking**

```python
system, *turns = messages
head, *_, tail = log_lines
```

**17. Swap without temp:** `a, b = b, a`

**18. Ignore values with `_`**

```python
for _ in range(n_retries): ...
name, _, ext = filename.rpartition(".")
```

**19. Unpack in for loops**

```python
for (q, a), score in zip(pairs, scores): ...
for i, (input_ids, labels) in enumerate(loader): ...
```

**20. Walrus for assign-and-test (3.8+, PY046)**

```python
# Before
m = re.search(r"```json\s*(.*?)```", reply, re.S)
if m:
    payload = json.loads(m.group(1))
# After
if m := re.search(r"```json\s*(.*?)```", reply, re.S):
    payload = json.loads(m.group(1))

# Read-loop
while chunk := stream.read(8192):
    sink.write(chunk)
```

Do not use the walrus where it hides an assignment in a long expression; readability wins.

**21. Conditional expression for simple choices**

```python
device = "cuda" if torch.cuda.is_available() else "cpu"
```

## Comparisons and truthiness

**22. `is None` (PY006)**

```python
if response is None: ...
if usage is not None: ...
```

`==` calls `__eq__`, which numpy, pandas and some ORMs override.

**23. Truthiness for containers (PY020)**

```python
if not docs: return []           # not: if len(docs) == 0
if history: ...                   # not: if len(history) > 0
```

Exception: numpy arrays, tensors and DataFrames raise on `bool()`. Use `arr.size == 0`, `t.numel() == 0`, `df.empty`.

**24. Don't compare to True/False (PY007)**

```python
if stream: ...                    # not: if stream == True
if not cached: ...                # not: if cached == False
```

With numpy/pandas masks, `mask == True` is element-wise and legal but redundant: `df[mask]` works.

**25. `not in` / `is not` (PY021)**

```python
if token not in vocab: ...        # not: if not token in vocab
```

**26. isinstance, not type equality (PY008, PY022)**

```python
if isinstance(value, (int, float)): ...
# 3.10+
if isinstance(value, int | float): ...
```

`type(x) is bool` is legitimate when `True` must not count as an `int`.

**27. Chained comparisons**

```python
if 0.0 <= top_p <= 1.0: ...
```

**28. Membership in a set literal**

```python
if finish_reason in {"length", "content_filter"}: ...
```

**29. Float comparison**

```python
import math
math.isclose(similarity, 1.0, rel_tol=1e-6)
# numpy
np.allclose(a, b, atol=1e-6)
```

## Strings

**30. f-strings (PY019)**

```python
# Before
"%s used %d tokens" % (model, n)
"{} used {} tokens".format(model, n)
# After
f"{model} used {n:,} tokens"
```

**31. f-string format specs**

```python
f"{latency_ms:.1f} ms"
f"{ratio:.1%}"                    # 0.873 -> 87.3%
f"{n:>8,}"                        # right-aligned with thousands separator
f"{now:%Y-%m-%d %H:%M}"
f"{name!r}"                       # repr
f"{tokens = }"                    # 3.8+: "tokens = 412" (debugging)
```

**32. join, not += in loops (PY018)**

```python
context = "\n\n".join(f"[{i}] {c.text}" for i, c in enumerate(chunks, 1))
```

**33. Multi-line templates (PY043)**

```python
import textwrap
SYSTEM = textwrap.dedent("""\
    You are a support assistant.
    Answer only from the provided context.
""")
RAG_PROMPT = "Context:\n{context}\n\nQuestion: {question}\nAnswer:"
prompt = RAG_PROMPT.format(context=context, question=question)
```

**34. removeprefix / removesuffix (3.9+)**

```python
model = name.removeprefix("models/")       # not: name[len("models/"):] if name.startswith(...)
```

**35. startswith/endswith with tuples**

```python
if path.endswith((".md", ".mdx", ".txt")): ...
```

**36. str methods over regex for simple jobs**

```python
key, _, value = line.partition("=")
words = text.split()                       # splits on any whitespace, drops empties
```

**37. Raw strings for regex**

```python
CODE_BLOCK = re.compile(r"```(\w+)?\n(.*?)```", re.S)
```

## Dicts and sets

**38. `.get` with default**

```python
temperature = params.get("temperature", 0.7)
```

Caution: `.get(k, d)` returns `None` if the key exists with value `None`.

**39. setdefault / defaultdict (PY017)**

```python
# Before
groups = {}
for chunk in chunks:
    if chunk.doc_id not in groups:
        groups[chunk.doc_id] = []
    groups[chunk.doc_id].append(chunk)
# After
from collections import defaultdict
groups = defaultdict(list)
for chunk in chunks:
    groups[chunk.doc_id].append(chunk)
```

**40. Counter for frequencies**

```python
from collections import Counter
label_counts = Counter(example["label"] for example in dataset)
label_counts.most_common(3)
```

**41. Merge dicts (3.9+)**

```python
params = DEFAULTS | user_params            # new dict, right side wins
params |= {"stream": True}                 # in place
```

**42. Dict unpacking into calls**

```python
client.chat.completions.create(model=model, messages=messages, **gen_kwargs)
```

**43. Invert or filter dicts with comprehensions**

```python
nonnull = {k: v for k, v in payload.items() if v is not None}
```

**44. Ordered dicts are the default (3.7+)**

Plain `dict` preserves insertion order. Use `OrderedDict` only for `move_to_end` / `popitem(last=False)` (e.g. a small LRU).

**45. Set operations**

```python
missing = required_fields - payload.keys()
shared = set(a_tokens) & set(b_tokens)
jaccard = len(shared) / len(set(a_tokens) | set(b_tokens))
```

**46. Deduplicate preserving order**

```python
unique_ids = list(dict.fromkeys(doc_ids))
```

## Functions

**47. No mutable defaults (PY001)**

```python
def retrieve(query: str, filters: dict | None = None) -> list[Doc]:   # | in annotation: 3.10+ or __future__
    filters = {} if filters is None else filters
    ...
```

**48. Keyword-only arguments for options**

```python
def generate(prompt: str, *, temperature: float = 0.0, max_tokens: int = 512) -> str: ...
generate("hi", temperature=0.2)           # generate("hi", 0.2) is a TypeError: intent is explicit
```

**49. Positional-only for stable APIs (3.8+)**

```python
def cosine(a, b, /): ...
```

**50. def, not named lambdas (PY023)**

```python
# Before
score = lambda d: d.similarity * d.boost
# After
def score(d: Doc) -> float:
    return d.similarity * d.boost
```

Lambdas are fine inline: `sorted(docs, key=lambda d: d.score)`.

**51. Return early, avoid deep nesting**

```python
def parse_tool_call(msg):
    if msg.get("type") != "tool_use":
        return None
    if "name" not in msg:
        raise ValueError("tool_use without name")
    return ToolCall(msg["name"], msg.get("input", {}))
```

**52. Consistent return types**

Return `[]` rather than sometimes `None`, sometimes a list. Raise rather than return error strings.

**53. Generators for streams**

```python
def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)
```

**54. `functools.partial` for pre-bound callables**

```python
from functools import partial
embed_query = partial(embed, model="text-embedding-3-small", dimensions=512)
```

## Exceptions

**55. Catch specific exceptions (PY002, PY003)**

```python
try:
    data = json.loads(reply)
except json.JSONDecodeError as err:
    raise InvalidModelOutput(reply[:200]) from err
```

**56. Chain with `from` (PY011)**

```python
try:
    cfg = CONFIGS[name]
except KeyError:
    raise UnknownModel(name) from None     # hide the KeyError deliberately
```

**57. contextlib.suppress for intentional ignores (PY045)**

```python
from contextlib import suppress
with suppress(FileNotFoundError):
    tmp_path.unlink()
# 3.8+: Path.unlink(missing_ok=True) is even shorter
tmp_path.unlink(missing_ok=True)
```

**58. Log with traceback, then decide**

```python
try:
    result = tool.run(args)
except ToolError:
    logger.exception("tool %s failed", tool.name)
    raise
```

**59. try/except/else/finally**

```python
try:
    resp = client.post(url, json=body, timeout=30)
except httpx.TimeoutException:
    metrics.incr("timeout")
    raise
else:
    metrics.incr("ok")          # only when no exception
finally:
    span.end()
```

**60. Keep the try block small**

Only the call that can raise belongs inside `try`; processing of the result goes in `else` or after.

**61. ExceptionGroup and except* (3.11+)**

```python
try:
    async with asyncio.TaskGroup() as tg:
        for url in urls:
            tg.create_task(fetch(url))
except* httpx.TimeoutException as eg:
    logger.warning("%d fetches timed out", len(eg.exceptions))
```

## Classes and data

**62. dataclasses for plain data**

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class GenerationConfig:
    model: str
    temperature: float = 0.0
    stop: tuple[str, ...] = ()
    extra: dict = field(default_factory=dict)
```

**63. `__repr__` that helps debugging**

dataclasses generate one; for hand-written classes return something that identifies the object: `f"{type(self).__name__}(model={self.model!r})"`.

**64. Properties instead of getters**

```python
class Usage:
    def __init__(self, prompt: int, completion: int):
        self.prompt, self.completion = prompt, completion

    @property
    def total(self) -> int:
        return self.prompt + self.completion
```

**65. Enum for fixed choices**

```python
from enum import Enum
class Role(str, Enum):           # 3.11+: class Role(StrEnum)
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
```

**66. match for structure (3.10+, PY029)**

```python
match block:
    case {"type": "text", "text": str(text)}:
        out.append(text)
    case {"type": "tool_use", "name": name, "input": dict(args)}:
        calls.append(ToolCall(name, args))
    case _:
        raise ValueError(f"unknown block {block!r}")
```

**67. Protocols over inheritance for duck typing**

```python
from typing import Protocol
class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

## Files and resources

**68. with for every resource (PY009)**

```python
with open(path, encoding="utf-8") as f:
    config = json.load(f)
```

**69. pathlib (PY025)**

```python
from pathlib import Path
root = Path(__file__).resolve().parent
data = root / "data" / "eval.jsonl"
for md in (root / "docs").rglob("*.md"):
    ingest(md.read_text(encoding="utf-8"))
data.parent.mkdir(parents=True, exist_ok=True)
```

**70. Explicit encoding (PY026)**

`open(p, encoding="utf-8")`, `p.read_text(encoding="utf-8")`. Binary modes take no encoding.

**71. Atomic writes**

```python
import os, tempfile
def write_atomic(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)        # atomic on POSIX and Windows
```

**72. Temporary files and dirs**

```python
with tempfile.TemporaryDirectory() as tmp:
    ckpt = Path(tmp) / "model.pt"
```

## Module hygiene

**73. No star imports (PY010)** — `from prompts import SYSTEM, render` not `from prompts import *`.

**74. Main guard**

```python
def main() -> int:
    ...
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

**75. No `global` (PY028)** — wrap state in a class, pass it in, or cache a factory with `functools.cache`.

**76. Don't shadow builtins (PY024)** — `doc_id`, `kind`, `user_input`, `items` instead of `id`, `type`, `input`, `list`.
