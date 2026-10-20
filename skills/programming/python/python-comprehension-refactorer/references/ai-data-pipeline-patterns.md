# AI Data Pipeline Patterns

Comprehensions, generators and itertools applied to the code AI engineers write every day: prompt construction, chat messages, embedding batches, retrieval post-processing, tool calling, token budgeting, dataset streaming, evaluation and training loops. Each pattern names the shape (map, filter, flatten, group, reduce) and when to keep a loop instead.

## Contents

- [Prompt and message construction](#prompt-and-message-construction)
- [Chunking and text preparation](#chunking-and-text-preparation)
- [Embedding batches](#embedding-batches)
- [Vector store records](#vector-store-records)
- [Retrieval post-processing](#retrieval-post-processing)
- [Tool calling](#tool-calling)
- [Token counting and context budgets](#token-counting-and-context-budgets)
- [Streaming responses](#streaming-responses)
- [Lazy dataset streaming](#lazy-dataset-streaming)
- [Evaluation](#evaluation)
- [Training and inference loops](#training-and-inference-loops)
- [Async fan-out](#async-fan-out)
- [Pattern index](#pattern-index)

## Prompt and message construction

```python
SYSTEM = "You are a concise assistant. Cite sources as [n]."

def build_messages(question: str, history: list[tuple[str, str]], hits: list) -> list[dict]:
    context = "\n\n".join(f"[{i}] {h.text}" for i, h in enumerate(hits, start=1))
    return [
        {"role": "system", "content": SYSTEM},
        *({"role": role, "content": text} for role, text in history),
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
    ]
```

Few-shot examples from a dataset, skipping ones that are too long:

```python
shots = [
    f"Q: {ex['question']}\nA: {ex['answer']}"
    for ex in examples
    if len(ex["question"]) + len(ex["answer"]) < 600
][:5]
few_shot_block = "\n\n".join(shots)
```

Prompt list for batch inference:

```python
prompts = [TEMPLATE.format(question=q.strip(), lang=lang) for q in questions if q.strip()]
```

Chat-format conversion between providers (OpenAI-style to a list of role/content pairs):

```python
pairs = [(m["role"], m["content"]) for m in messages if m["role"] in {"user", "assistant"}]
```

Stripping tool messages or `None` contents from history before resending:

```python
history = [m for m in history if m["role"] != "tool" and m.get("content")]
```

## Chunking and text preparation

```python
paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

# fixed-size token windows with overlap
def chunk_tokens(tokens: list[int], size: int = 512, overlap: int = 64) -> list[list[int]]:
    step = size - overlap
    return [tokens[i:i + size] for i in range(0, max(len(tokens) - overlap, 1), step)]

# flatten chunks from many documents, keeping provenance
chunks = [
    {"doc_id": doc.id, "chunk_idx": i, "text": piece}
    for doc in docs
    for i, piece in enumerate(splitter.split_text(doc.text))
]
```

Deduplicate near-identical chunks (keeps first-seen order; a loop because it carries state):

```python
import hashlib

def dedupe(chunks):
    seen = set()
    for c in chunks:
        h = hashlib.sha1(" ".join(c["text"].split()).lower().encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            yield c
```

## Embedding batches

Never embed one text per request, and never send all texts in one request. Batch lazily.

```python
from itertools import batched   # 3.12+; backport in generators-and-itertools.md

def embed_all(texts, client, model="text-embedding-3-small", batch_size=128):
    vectors = []
    for batch in batched(texts, batch_size):
        resp = client.embeddings.create(model=model, input=list(batch))
        vectors.extend(d.embedding for d in sorted(resp.data, key=lambda d: d.index))
    return vectors
```

This is a loop, not a comprehension, because each iteration does I/O and may need retries. The inner `extend` with a generator is idiomatic.

With rate-limit retry (keep it in a loop; retries are control flow):

```python
import random
import time

def embed_with_retry(batch, client, model, attempts=5):
    for attempt in range(attempts):
        try:
            return [d.embedding for d in client.embeddings.create(model=model, input=list(batch)).data]
        except RateLimitError:
            time.sleep(min(2 ** attempt, 30) + random.random())
    raise RuntimeError("embedding failed after retries")

vectors = [v for batch in batched(texts, 128) for v in embed_with_retry(batch, client, MODEL)]
```

Token-budgeted batches (APIs cap tokens per request) need a generator function: see `batch_by_tokens` in [generators-and-itertools.md](generators-and-itertools.md#batching).

## Vector store records

```python
ids = [c["id"] for c in chunks]
texts = [c["text"] for c in chunks]
metadatas = [{k: v for k, v in c.items() if k not in {"text", "embedding"}} for c in chunks]

# id -> embedding lookup
vec_by_id = {c["id"]: c["embedding"] for c in chunks}

# upsert in batches; zip keeps parallel lists aligned (strict=True: 3.10+)
for batch in batched(zip(ids, vectors, metadatas, strict=True), 100):
    index.upsert(vectors=[{"id": i, "values": v, "metadata": m} for i, v, m in batch])
```

Convert to a numpy matrix once for local search:

```python
import numpy as np

order = list(vec_by_id)                                     # stable id order
matrix = np.array([vec_by_id[i] for i in order], dtype=np.float32)
```

## Retrieval post-processing

```python
# keep hits above a threshold, best first
relevant = sorted((h for h in hits if h.score >= 0.75), key=lambda h: h.score, reverse=True)

# first good hit or None
best = next((h for h in hits if h.score >= 0.9), None)

# unique sources, in rank order
sources = list(dict.fromkeys(h.metadata["source"] for h in relevant))

# group hits per document and keep the best chunk of each
from collections import defaultdict

by_doc = defaultdict(list)
for h in relevant:
    by_doc[h.metadata["doc_id"]].append(h)
best_per_doc = [max(group, key=lambda h: h.score) for group in by_doc.values()]
```

Reciprocal rank fusion of several retrievers (dict accumulation with a loop, then a sorted comprehension):

```python
def rrf(result_lists, k=60):
    scores = defaultdict(float)
    for results in result_lists:
        for rank, doc_id in enumerate(results, start=1):
            scores[doc_id] += 1.0 / (k + rank)
    return [doc_id for doc_id, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]
```

Score normalisation:

```python
lo, hi = min(scores), max(scores)
norm = [(s - lo) / (hi - lo) if hi > lo else 0.0 for s in scores]
```

## Tool calling

Tool schemas from Python functions:

```python
import inspect

def tool_schema(fn):
    params = inspect.signature(fn).parameters
    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": inspect.getdoc(fn) or "",
            "parameters": {
                "type": "object",
                "properties": {name: {"type": "string"} for name in params},
                "required": [n for n, p in params.items() if p.default is inspect.Parameter.empty],
            },
        },
    }

TOOLS = [search_docs, get_weather, run_sql]
schemas = [tool_schema(fn) for fn in TOOLS]
registry = {fn.__name__: fn for fn in TOOLS}
```

Flatten tool calls across choices or turns, tolerating `None`:

```python
calls = [call for choice in resp.choices for call in (choice.message.tool_calls or [])]
names = {c.function.name for c in calls}
```

Execute tool calls: a loop, because each one is an action with error handling:

```python
import json

tool_messages = []
for call in calls:
    fn = registry.get(call.function.name)
    try:
        result = fn(**json.loads(call.function.arguments)) if fn else {"error": "unknown tool"}
    except Exception as exc:   # report the failure back to the model
        result = {"error": str(exc)}
    tool_messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
```

Anthropic-style content blocks:

```python
text = "".join(b.text for b in message.content if b.type == "text")
tool_uses = [b for b in message.content if b.type == "tool_use"]
```

## Token counting and context budgets

```python
from collections import Counter

total = sum(len(enc.encode(m["content"])) for m in messages)
per_role = Counter()
for m in messages:
    per_role[m["role"]] += len(enc.encode(m["content"]))
vocab_freq = Counter(tok for doc in corpus for tok in enc.encode(doc))
```

Count once, reuse (walrus):

```python
sized = [(m, n) for m in messages if (n := len(enc.encode(m["content"]))) > 0]
```

Trim history to a budget, keeping the most recent messages (needs early exit, so a loop):

```python
def fit_history(messages, budget, count):
    kept, used = [], 0
    for m in reversed(messages):
        n = count(m["content"])
        if used + n > budget:
            break
        kept.append(m)
        used += n
    return kept[::-1]
```

Cumulative token offsets for chunk citation spans:

```python
from itertools import accumulate, pairwise

lengths = [len(enc.encode(c)) for c in chunks]
spans = list(pairwise(accumulate(lengths, initial=0)))   # [(0, 120), (120, 460), ...]  3.10+
```

## Streaming responses

```python
def stream_text(stream):
    for event in stream:
        delta = event.choices[0].delta.content
        if delta:
            yield delta

answer = "".join(stream_text(stream))
```

Async streaming with an async comprehension (inside `async def`):

```python
parts = [e.choices[0].delta.content async for e in stream if e.choices and e.choices[0].delta.content]
answer = "".join(parts)
```

Group streamed events by message id when a stream interleaves several (already ordered by id runs):

```python
from itertools import groupby
messages = {mid: "".join(e.text for e in evs) for mid, evs in groupby(events, key=lambda e: e.message_id)}
```

## Lazy dataset streaming

Keep memory flat regardless of dataset size by chaining generators:

```python
import json
from itertools import islice

def read_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)

records = read_jsonl("train.jsonl")
valid = (r for r in records if r.get("text") and r.get("label") is not None)
formatted = ({"prompt": PROMPT.format(text=r["text"]), "completion": r["label"]} for r in valid)
preview = list(islice(formatted, 3))   # inspect without reading the whole file
```

Many shards as one stream:

```python
from itertools import chain
from pathlib import Path

shards = sorted(Path("data/").glob("part-*.jsonl"))
all_records = chain.from_iterable(read_jsonl(p) for p in shards)
```

Deterministic train/validation split without loading everything (hash-based):

```python
import zlib

def is_val(record_id: str, pct: int = 5) -> bool:
    return zlib.crc32(record_id.encode()) % 100 < pct

train = (r for r in read_jsonl(path) if not is_val(r["id"]))
val = (r for r in read_jsonl(path) if is_val(r["id"]))
```

Hugging Face `datasets`: prefer `ds.map(fn, batched=True)` and `ds.filter(...)` (Arrow-backed, multiprocess) over Python comprehensions over rows. Use comprehensions only on the small batches inside `fn`:

```python
def tokenize(batch):
    return tokenizer([t.strip() for t in batch["text"]], truncation=True, max_length=512)

ds = ds.map(tokenize, batched=True)
```

## Evaluation

```python
preds = [normalize(p) for p in predictions]
golds = [normalize(g) for g in references]
exact = sum(p == g for p, g in zip(preds, golds, strict=True)) / len(golds)

# per-category accuracy
from collections import defaultdict
buckets = defaultdict(list)
for case, p in zip(cases, preds):
    buckets[case["category"]].append(p == normalize(case["answer"]))
accuracy = {cat: sum(v) / len(v) for cat, v in buckets.items()}

failures = [c["id"] for c, p in zip(cases, preds) if p != normalize(c["answer"])]
all_passed = all(p == g for p, g in zip(preds, golds))
```

Hyper-parameter or prompt-variant grid:

```python
from itertools import product

runs = [
    {"model": m, "temperature": t, "prompt": name}
    for m, t, name in product(["small", "large"], [0.0, 0.7], PROMPTS)
]
```

## Training and inference loops

Training loops are loops: they have side effects (optimizer steps, logging, checkpointing). Comprehensions appear around them.

```python
import torch

param_groups = [
    {"params": [p for n, p in model.named_parameters() if not any(nd in n for nd in ("bias", "norm"))],
     "weight_decay": 0.01},
    {"params": [p for n, p in model.named_parameters() if any(nd in n for nd in ("bias", "norm"))],
     "weight_decay": 0.0},
]
optimizer = torch.optim.AdamW(param_groups, lr=3e-5)

n_trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
frozen = [n for n, p in model.named_parameters() if not p.requires_grad]

batch = {k: v.to(device) for k, v in batch.items()}           # move a batch dict to GPU
metrics = {k: v.item() for k, v in loss_parts.items()}          # one .item() per scalar, not per element
```

Collate function with padding:

```python
def collate(samples, pad_id=0):
    max_len = max(len(s["input_ids"]) for s in samples)
    input_ids = [s["input_ids"] + [pad_id] * (max_len - len(s["input_ids"])) for s in samples]
    attention = [[1] * len(s["input_ids"]) + [0] * (max_len - len(s["input_ids"])) for s in samples]
    return {"input_ids": torch.tensor(input_ids), "attention_mask": torch.tensor(attention)}
```

Batched inference over a generator of inputs:

```python
@torch.inference_mode()
def predict(texts, batch_size=32):
    for batch in batched(texts, batch_size):
        enc = tokenizer(list(batch), padding=True, truncation=True, return_tensors="pt").to(device)
        yield from model(**enc).logits.argmax(dim=-1).tolist()

labels = [id2label[i] for i in predict(texts)]
```

## Async fan-out

A comprehension with `await` runs sequentially. Build coroutines with a generator and gather them, with a semaphore for rate limits:

```python
import asyncio

async def summarize_all(docs, client, limit=10):
    sem = asyncio.Semaphore(limit)

    async def one(doc):
        async with sem:
            resp = await client.messages.create(model=MODEL, max_tokens=300,
                                                messages=[{"role": "user", "content": f"Summarize:\n{doc}"}])
            return resp.content[0].text

    return await asyncio.gather(*(one(d) for d in docs))
```

Python 3.11+ `TaskGroup` (cancels siblings on failure):

```python
async def fetch_all(urls, fetch):
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(fetch(u)) for u in urls]
    return [t.result() for t in tasks]
```

Keep partial results when some calls fail:

```python
results = await asyncio.gather(*(one(d) for d in docs), return_exceptions=True)
ok = [r for r in results if not isinstance(r, BaseException)]
errors = [r for r in results if isinstance(r, BaseException)]
```

## Pattern index

| Task | Shape | Tool |
|---|---|---|
| prompts from questions | map + filter | list comprehension |
| chat messages with history | map + unpack | list with `*(... for ...)` |
| chunk documents | flatten with provenance | two-`for` comprehension with `enumerate` |
| dedupe chunks | stateful filter | generator function with a `seen` set |
| embedding requests | batch + I/O | `batched` in a loop |
| id -> vector | key/value map | dict comprehension |
| filter hits by score | filter | comprehension / generator into `sorted` |
| first good hit | search | `next(gen, None)` |
| unique sources in order | dedupe | `dict.fromkeys` |
| group hits by doc | group | `defaultdict(list)` loop |
| flatten tool calls | flatten | two-`for` comprehension or `chain.from_iterable` |
| execute tool calls | side effects | for loop |
| token totals | reduce | `sum(generator)` |
| token frequencies | count | `Counter(generator)` |
| context budget | early exit | for loop with `break` |
| JSONL dataset | stream | generator functions + `islice` |
| eval accuracy | reduce over zip | `sum(p == g for ...)` |
| optimizer param groups | filter | list comprehension |
| concurrent LLM calls | fan-out | `asyncio.gather(*(coro for ...))` |
