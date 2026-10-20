# Exercises with Hints and Solutions

Graded exercises from first steps to a tiny RAG. Each has: the task, an example of expected behaviour, **Hint 1** (a nudge), **Hint 2** (the tool or a skeleton), the **Solution** with a short explanation, and usually a **Stretch** goal. When tutoring, give the task and the example only; reveal hints one at a time; reveal the solution only after an attempt or an explicit request (see the hint ladder in [teaching-playbook.md](teaching-playbook.md)). All solutions are standard-library Python 3.9+ unless marked.

## Contents

Levels: L1 beginner, L2 elementary, L3 intermediate, L4 advanced.

- 1. [Prompt formatter](#1-prompt-formatter) (L1) · 2. [Token cost estimator](#2-token-cost-estimator) (L1) · 3. [Word counter](#3-word-counter) (L1) · 4. [Keep only user messages](#4-keep-only-user-messages) (L1)
- 5. [Dedupe while keeping order](#5-dedupe-while-keeping-order) (L2) · 6. [Batches](#6-batches) (L2) · 7. [Text chunker with overlap](#7-text-chunker-with-overlap) (L2) · 8. [Prompt template with validation](#8-prompt-template-with-validation) (L2)
- 9. [Cosine similarity in pure Python](#9-cosine-similarity-in-pure-python) (L2) · 10. [Top-k retrieval](#10-top-k-retrieval) (L3) · 11. [Parse a model's JSON reply](#11-parse-a-models-json-reply) (L3) · 12. [Conversation class](#12-conversation-class) (L3)
- 13. [Streaming generator](#13-streaming-generator) (L3) · 14. [Retry decorator](#14-retry-decorator) (L4) · 15. [Async fan-out](#15-async-fan-out) (L4) · 16. [Tiny RAG](#16-tiny-rag) (L4)
- [Predict-the-output drills](#predict-the-output-drills) (L1-3)

## 1. Prompt formatter

**Task**: Ask the user for a role, a task and a tone, then print a prompt.

```text
Role: data analyst
Task: summarise sales trends
Tone: friendly
You are a data analyst. Summarise sales trends. Use a friendly tone.
```

**Hint 1**: `input("Role: ")` gives you a string. How do you put variables inside text?

**Hint 2**: `f"You are a {role}. ..."`. To capitalise only the first letter of the task: `task[0].upper() + task[1:]` or `task.capitalize()` (which lowercases the rest).

**Solution**

```python
role = input("Role: ").strip()
task = input("Task: ").strip()
tone = input("Tone: ").strip()

prompt = f"You are a {role}. {task[:1].upper() + task[1:]}. Use a {tone} tone."
print("---")
print(prompt)
```

`.strip()` removes accidental spaces. `task[:1]` (not `task[0]`) avoids an IndexError when the task is empty.

## 2. Token cost estimator

**Task**: Given input tokens, output tokens and prices per 1,000 tokens, print the cost with 4 decimals and the cost for 10,000 such calls with thousands separators.

```text
cost_per_call(1200, 300, in_price=0.0005, out_price=0.0015) -> 0.00105
one call: $0.0010
10,000 calls: $10.50
```

**Hint 1**: price per token = price per 1,000 / 1000.

**Hint 2**: `f"{value:.4f}"` and `f"{value:,.2f}"`.

**Solution**

```python
def cost_per_call(tokens_in, tokens_out, in_price, out_price):
    return tokens_in / 1000 * in_price + tokens_out / 1000 * out_price


one = cost_per_call(1200, 300, in_price=0.0005, out_price=0.0015)
print(f"one call: ${one:.4f}")                 # $0.0010 (0.00105 rounded for display)
print(f"10,000 calls: ${one * 10_000:,.2f}")   # $10.50
```

`10_000` is the same as `10000`; underscores make big numbers readable. Rounding only happens in the display.

## 3. Word counter

**Task**: `word_counts(text)` returns a dict of lowercased word -> count, ignoring punctuation. Then print the 3 most common words.

```python
word_counts("The cat sat. The cat ran!")   # {'the': 2, 'cat': 2, 'sat': 1, 'ran': 1}
```

**Hint 1**: Clean the text first, then split it into words, then count. What should happen the first time you see a word?

**Hint 2**: `counts[word] = counts.get(word, ___) + 1`. To remove punctuation: `re.findall(r"[a-z']+", text.lower())`.

**Solution**

```python
import re


def word_counts(text):
    counts = {}
    for word in re.findall(r"[a-z']+", text.lower()):
        counts[word] = counts.get(word, 0) + 1
    return counts


counts = word_counts("The cat sat. The cat ran!")
print(counts)
top3 = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:3]
print(top3)                                   # [('the', 2), ('cat', 2), ('sat', 1)]

```

Write the loop version first: it teaches the dict pattern. Then show the shortcut `collections.Counter(words).most_common(3)`.

**Stretch**: Ignore stop words from a set; count bigrams (pairs of neighbouring words) with `zip(words, words[1:])`.

## 4. Keep only user messages

**Task**: From a chat history (list of dicts), return the contents of user messages, numbered.

```python
history = [
    {"role": "system", "content": "Be brief."},
    {"role": "user", "content": "What is RAG?"},
    {"role": "assistant", "content": "Retrieval-augmented generation."},
    {"role": "user", "content": "Give an example."},
]
# 1. What is RAG?
# 2. Give an example.
```

**Hint 1**: Loop over the list; each item is a dict. How do you read its role?

**Hint 2**: `enumerate(..., start=1)` numbers things. Filter first, then number.

**Solution**

```python
history = [
    {"role": "system", "content": "Be brief."},
    {"role": "user", "content": "What is RAG?"},
    {"role": "assistant", "content": "Retrieval-augmented generation."},
    {"role": "user", "content": "Give an example."},
]

user_texts = [m["content"] for m in history if m["role"] == "user"]
for i, text in enumerate(user_texts, start=1):
    print(f"{i}. {text}")
```

Common mistake: numbering inside the original loop with `enumerate(history)` gives 2 and 4.

**Stretch**: Count messages per role in a dict.

## 5. Dedupe while keeping order

**Task**: Remove duplicate retrieved chunks but keep the first occurrence order.

```python
dedupe(["a", "b", "a", "c", "b"])   # ['a', 'b', 'c']
```

**Hint 1**: You need to remember what you've already seen. Which collection answers "have I seen this?" fastest?

**Hint 2**: A `set()` for seen items plus a list for output.

**Solution**

```python
def dedupe(items):
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


print(dedupe(["a", "b", "a", "c", "b"]))     # ['a', 'b', 'c']
print(list(dict.fromkeys(["a", "b", "a"])))  # one-liner: dicts keep insertion order (3.7+)
```

`list(set(items))` also removes duplicates but loses the order.

**Stretch**: Dedupe dicts by their `"id"` key.

## 6. Batches

**Task**: Split a list into batches of size n (the last one may be shorter), as you would before sending texts to an embedding API.

```python
batches(list(range(7)), 3)   # [[0, 1, 2], [3, 4, 5], [6]]
```

**Hint 1**: Where does each batch start? 0, 3, 6, ... What does `range` do with a third argument?

**Hint 2**: `items[start:start + n]` and `range(0, len(items), n)`.

**Solution**

```python
def batches(items, n):
    if n < 1:
        raise ValueError("n must be at least 1")
    return [items[start:start + n] for start in range(0, len(items), n)]


print(batches(list(range(7)), 3))   # [[0, 1, 2], [3, 4, 5], [6]]
print(batches([], 3))               # []
```

Slices past the end are safe (`[6:9]` gives `[6]`), so the last batch needs no special case. 3.12+ has `itertools.batched(items, n)` (yields tuples).

**Stretch**: Make it a generator that works on any iterable, not just lists.

## 7. Text chunker with overlap

**Task**: Split text into chunks of `size` words where each chunk repeats the last `overlap` words of the previous one (so a sentence cut at a boundary still appears whole somewhere). No empty or fully duplicated chunk at the end.

```python
chunk("w0 w1 w2 w3 w4 w5 w6 w7", size=4, overlap=1)
# ['w0 w1 w2 w3', 'w3 w4 w5 w6', 'w6 w7']
```

**Hint 1**: How far does each chunk's start move from the previous one? (Not `size`.)

**Hint 2**: `step = size - overlap`; stop once a chunk reaches the end of the words. Test with lengths that divide exactly and that don't.

**Solution**

```python
def chunk(text, size=200, overlap=20):
    if not 0 <= overlap < size:
        raise ValueError("need 0 <= overlap < size")
    words = text.split()
    step = size - overlap
    chunks = []
    for start in range(0, len(words), step):
        chunks.append(" ".join(words[start:start + size]))
        if start + size >= len(words):      # this chunk reached the end: stop
            break
    return chunks


print(chunk("w0 w1 w2 w3 w4 w5 w6 w7", size=4, overlap=1))  # ['w0 w1 w2 w3', 'w3 w4 w5 w6', 'w6 w7']
print(chunk("w0 w1 w2 w3", size=4, overlap=1))              # ['w0 w1 w2 w3']  (no trailing 'w3' chunk)
print(chunk("", size=4, overlap=1))                         # []
```

Without the `break`, the second test would give a useless final chunk `'w3'` that only repeats the overlap. If `overlap >= size`, `step` would be 0 or negative and `range` would fail or loop nowhere, hence the check.

**Stretch**: Chunk by sentences (`re.split(r"(?<=[.!?])\s+", text)`) and pack sentences until a word budget is reached.

## 8. Prompt template with validation

**Task**: `render(template, **values)` fills `{placeholders}`. If a placeholder is missing, raise a clear `ValueError` listing what is missing. Extra values are fine.

```python
render("Answer {question} using {context}", question="Q?")
# ValueError: missing values for: context
```

**Hint 1**: Try `template.format(**values)` with a missing value. Which error do you get, and can you catch it?

**Hint 2**: `string.Formatter().parse(template)` yields `(literal, field_name, spec, conversion)`; collect field names.

**Solution**

```python
import string


def placeholders(template):
    return {field for _, field, _, _ in string.Formatter().parse(template) if field}


def render(template, **values):
    missing = sorted(placeholders(template) - values.keys())
    if missing:
        raise ValueError(f"missing values for: {', '.join(missing)}")
    return template.format(**values)


print(render("Answer {question} using {context}", question="What is RAG?", context="notes", extra=1))
try:
    render("Answer {question} using {context}", question="Q?")
except ValueError as e:
    print(e)                                    # missing values for: context
```

`values.keys()` behaves like a set, so `set - keys` works. Literal braces in templates must be doubled: `{{` and `}}`, a classic bug when templates contain JSON examples.

**Stretch**: Warn (do not fail) about unused values.

## 9. Cosine similarity in pure Python

**Task**: `cosine(a, b)` for two equal-length lists of floats. Return 0.0 if either vector is all zeros; raise `ValueError` on different lengths.

```python
cosine([1, 0], [1, 0])     # 1.0
cosine([1, 0], [0, 1])     # 0.0
cosine([1, 2], [2, 4])     # 1.0 (same direction)
```

**Hint 1**: cosine = dot(a, b) / (|a| * |b|). How do you multiply matching positions of two lists?

**Hint 2**: `sum(x * y for x, y in zip(a, b))` and `math.sqrt(sum(x * x for x in a))`.

**Solution**

```python
import math


def cosine(a, b):
    if len(a) != len(b):
        raise ValueError(f"length mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


print(cosine([1, 0], [1, 0]), cosine([1, 0], [0, 1]), round(cosine([1, 2], [2, 4]), 6))
print(math.isclose(cosine([0.1, 0.2, 0.3], [0.1, 0.2, 0.3]), 1.0))   # compare floats with isclose
```

On 3.12+ you can write `math.sumprod(a, b)` for the dot product. With numpy: `a @ b / (np.linalg.norm(a) * np.linalg.norm(b))`.

**Stretch**: Normalise every vector once (divide by its norm); then cosine is just the dot product. Why is that faster for search?

## 10. Top-k retrieval

**Task**: Given a query vector and a dict `{doc_id: vector}`, return the `k` best `(doc_id, score)` pairs, highest first.

**Hint 1**: Compute a score per document first (reuse `cosine`), then sort.

**Hint 2**: `sorted(pairs, key=lambda p: p[1], reverse=True)[:k]`; for big collections `heapq.nlargest(k, pairs, key=...)`.

**Solution**

```python
import heapq
import math


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def top_k(query, docs, k=2):
    scored = [(doc_id, cosine(query, vec)) for doc_id, vec in docs.items()]
    return heapq.nlargest(k, scored, key=lambda pair: pair[1])


docs = {"cats": [0.9, 0.1, 0.0], "dogs": [0.8, 0.3, 0.1], "stocks": [0.0, 0.1, 0.9]}
for doc_id, score in top_k([1.0, 0.2, 0.0], docs):
    print(f"{doc_id}: {score:.3f}")
```

**Stretch**: Add a `min_score` threshold and return fewer than k results if needed.

## 11. Parse a model's JSON reply

**Task**: Models often answer with extra text, Markdown fences or broken JSON. Write `parse_reply(raw)` that returns a dict with keys `sentiment` (one of positive/negative/neutral) and `confidence` (float 0-1), or raises `ValueError` with a helpful message.

```python
fence = "`" * 3      # a Markdown code fence, as models often add
parse_reply(f'Sure! {fence}json\n{{"sentiment": "positive", "confidence": 0.92}}\n{fence}')
# {'sentiment': 'positive', 'confidence': 0.92}
parse_reply('{"sentiment": "great", "confidence": 2}')
# ValueError: sentiment must be one of ['negative', 'neutral', 'positive'], got 'great'
```

**Hint 1**: Three steps: find the JSON text, parse it, validate it. Which step can raise which error?

**Hint 2**: `raw.find("{")` and `raw.rfind("}")`; `json.loads` raises `json.JSONDecodeError` (a subclass of `ValueError`); check types with `isinstance`.

**Solution**

```python
import json

ALLOWED = {"positive", "negative", "neutral"}


def parse_reply(raw):
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end < start:
        raise ValueError(f"no JSON object found in: {raw[:60]!r}")
    try:
        data = json.loads(raw[start:end + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON ({e.msg} at char {e.pos})") from e
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    sentiment = data.get("sentiment")
    if sentiment not in ALLOWED:
        raise ValueError(f"sentiment must be one of {sorted(ALLOWED)}, got {sentiment!r}")
    confidence = data.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError(f"confidence must be a number between 0 and 1, got {confidence!r}")
    return {"sentiment": sentiment, "confidence": float(confidence)}


fence = "`" * 3
print(parse_reply(f'Sure! {fence}json\n{{"sentiment": "positive", "confidence": 0.92}}\n{fence}'))
for bad in ['{"sentiment": "great", "confidence": 2}', "I cannot answer that.", '{"sentiment": "positive",}']:
    try:
        parse_reply(bad)
    except ValueError as e:
        print("rejected:", e)
```

`isinstance(True, int)` is True in Python, hence the explicit `bool` check. In real projects use pydantic models or the provider's structured-output feature, but this teaches what they do.

**Stretch**: On failure, build a "repair" prompt that includes the error message for a retry.

## 12. Conversation class

**Task**: A `Conversation` that stores a system prompt and messages, can `add(role, content)` (rejecting unknown roles), `last(n)` messages, and `to_payload()` returns the list of dicts an LLM API expects, with the system message first.

**Hint 1**: What data does each conversation need to remember? Those become attributes set in `__init__`.

**Hint 2**: Use `@dataclass` with `field(default_factory=list)` so each conversation gets its own list.

**Solution**

```python
from dataclasses import dataclass, field

ROLES = {"user", "assistant", "tool"}


@dataclass
class Conversation:
    system: str
    messages: list = field(default_factory=list)

    def add(self, role, content):
        if role not in ROLES:
            raise ValueError(f"unknown role {role!r}; expected one of {sorted(ROLES)}")
        self.messages.append({"role": role, "content": content})

    def last(self, n):
        return self.messages[-n:] if n > 0 else []

    def to_payload(self):
        return [{"role": "system", "content": self.system}, *self.messages]


chat = Conversation("You are concise.")
chat.add("user", "Hi")
chat.add("assistant", "Hello!")
other = Conversation("Different bot")
print(len(chat.messages), len(other.messages))     # 2 0  (separate lists)
print(chat.to_payload())
```

Why `n > 0` in `last`: `messages[-0:]` is `messages[0:]`, the WHOLE list, a classic slicing surprise.

**Stretch**: `trim(max_words)` that drops the oldest messages until the total word count fits.

## 13. Streaming generator

**Task**: Simulate a streaming LLM: `stream(text)` yields the text a few characters at a time; the caller prints pieces as they arrive and also collects the full reply.

**Hint 1**: A function with `yield` produces values one by one. How do you step through text in pieces of 4 characters?

**Hint 2**: `for i in range(0, len(text), 4): yield text[i:i + 4]`; print with `end=""` and `flush=True`.

**Solution**

```python
import time


def stream(text, piece=4, delay=0.02):
    for i in range(0, len(text), piece):
        time.sleep(delay)              # pretend network latency
        yield text[i:i + piece]


parts = []
for delta in stream("Embeddings turn text into vectors."):
    print(delta, end="", flush=True)
    parts.append(delta)
print()
full = "".join(parts)
print(len(full))
```

`"".join(parts)` is the efficient way to assemble strings; `+=` in a loop is fine for small text but quadratic for huge text.

**Stretch**: Stop early when a stop word like `"vectors"` appears in the collected text.

## 14. Retry decorator

**Task**: Write `@retry(times=3, exceptions=(TimeoutError,))` that re-calls the function when one of the given exceptions is raised, waits `0.1 * 2**attempt` seconds between tries, and re-raises after the last failure.

**Hint 1**: A decorator with arguments is three nested functions: settings -> decorator(fn) -> wrapper(*args, **kwargs).

**Hint 2**: Inside the wrapper, a `for attempt in range(times):` with `try: return fn(...)` and `except exceptions:`; on the last attempt, `raise`.

**Solution**

```python
import functools
import time


def retry(times=3, exceptions=(Exception,), base_delay=0.1):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(times):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    if attempt == times - 1:
                        raise
                    wait = base_delay * 2 ** attempt
                    print(f"{fn.__name__} failed ({e}); retry {attempt + 1} in {wait:.2f}s")
                    time.sleep(wait)
        return wrapper
    return decorator


calls = {"n": 0}


@retry(times=3, exceptions=(TimeoutError,), base_delay=0.01)
def flaky():
    calls["n"] += 1
    if calls["n"] < 3:
        raise TimeoutError("model timed out")
    return "ok"


print(flaky(), calls["n"])        # ok 3
```

Bare `raise` re-raises the current exception with its original traceback. `functools.wraps` keeps `flaky.__name__` as `"flaky"`.

**Stretch**: Add random jitter, and only retry on HTTP 429/5xx status codes.

## 15. Async fan-out

**Task**: Call a fake async model for 10 prompts with at most 3 calls in flight, keep results in the same order as the prompts, and print the total time.

**Hint 1**: `asyncio.gather` runs coroutines concurrently and returns results in the order you passed them.

**Hint 2**: `asyncio.Semaphore(3)` with `async with sem:` around the call.

**Solution**

```python
import asyncio
import random
import time


async def fake_model(prompt):
    await asyncio.sleep(random.uniform(0.1, 0.3))
    return prompt[::-1]


async def run_all(prompts, limit=3):
    sem = asyncio.Semaphore(limit)

    async def one(p):
        async with sem:
            return await fake_model(p)

    return await asyncio.gather(*(one(p) for p in prompts))


start = time.perf_counter()
results = asyncio.run(run_all([f"prompt {i}" for i in range(10)]))
print(results[:2], f"{time.perf_counter() - start:.2f}s")
```

Sequential would take ~2 s; with 3 at a time it takes about a third of that.

**Stretch**: Use `return_exceptions=True` so one failing call does not cancel the batch, then report failures separately. On 3.11+ try `asyncio.TaskGroup`.

## 16. Tiny RAG

**Task**: Combine exercises 3, 7, 9 and 10: load a few notes, chunk them, "embed" each chunk with a bag-of-words vector over a shared vocabulary, retrieve the top 2 chunks for a question, and build the final prompt.

**Hint 1**: Build the vocabulary (sorted set of all words) first so every vector has the same length and order.

**Hint 2**: `vector = [counts.get(word, 0) for word in vocab]`.

**Solution**

```python
import math
import re
from collections import Counter

notes = {
    "python.md": "Lists are ordered and mutable. Tuples are ordered and immutable.",
    "rag.md": "RAG retrieves relevant chunks and adds them to the prompt so the model can cite them.",
    "venv.md": "A virtual environment keeps each project's packages separate.",
}


def tokenize(text):
    return re.findall(r"[a-z]+", text.lower())


def chunk(text, size=8, overlap=2):
    words, step, out = text.split(), size - overlap, []
    for start in range(0, len(words), step):
        out.append(" ".join(words[start:start + size]))
        if start + size >= len(words):
            break
    return out


chunks = [(name, c) for name, text in notes.items() for c in chunk(text)]
vocab = sorted({w for _, c in chunks for w in tokenize(c)})


def embed(text):
    counts = Counter(tokenize(text))
    return [counts.get(w, 0) for w in vocab]


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


index = [(name, c, embed(c)) for name, c in chunks]
question = "How does RAG add chunks to the prompt?"
q = embed(question)
best = sorted(index, key=lambda item: cosine(q, item[2]), reverse=True)[:2]
context = "\n".join(f"[{name}] {c}" for name, c, _ in best)
prompt = f"Answer using only the context. Cite the file.\n\nContext:\n{context}\n\nQuestion: {question}"
print(prompt)
```

Next steps: swap `embed` for a real embedding model, store vectors in a numpy matrix, and send `prompt` to an LLM API (stage 13 and 14 in [curriculum-to-ai-engineer.md](curriculum-to-ai-engineer.md)).


## Predict-the-output drills

Ask the learner to predict, then run (or trace with `scripts/explain_concepts.py trace`). Answers below each.

```python
a = [1, 2, 3]
b = a
b.append(4)
print(a)
```
Answer: `[1, 2, 3, 4]`: `b` is another name for the same list.

```python
def add(item, bucket=[]):
    bucket.append(item)
    return bucket

print(add(1), add(2))
```
Answer: `[1, 2] [1, 2]`: one default list shared by both calls, and both results are that same list.

```python
nums = [10, 20, 30, 40]
print(nums[1:3], nums[-1], nums[:-1], len(nums[1:]))
```
Answer: `[20, 30] 40 [10, 20, 30] 3`.

```python
print(7 / 2, 7 // 2, -7 // 2, 7 % 3, 0.1 + 0.2 == 0.3)
```
Answer: `3.5 3 -4 1 False`.

```python
count = 0
def bump():
    count = count + 1
bump()
```
Answer: `UnboundLocalError`: the assignment makes `count` local to `bump`.

```python
items = ["a", "b", "c", "d"]
for x in items:
    if x in ("b", "c"):
        items.remove(x)
print(items)
```
Answer: `['a', 'c', 'd']`: removing `b` shifts `c` into the slot the loop already visited, so `c` is skipped.

```python
gen = (n * n for n in range(3))
print(list(gen), list(gen))
```
Answer: `[0, 1, 4] []`: a generator is used up after one pass.
