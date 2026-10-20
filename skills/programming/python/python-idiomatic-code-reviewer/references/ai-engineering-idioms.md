# AI-Engineering Idioms

Idiomatic, production-safe Python for LLM apps, RAG pipelines, agents, eval harnesses, model-serving APIs and training code. Each section lists the smell, why it bites in production, and the rewrite. Rule ids map to `scripts/review_idioms.py`.

## Contents

1. [Secrets and configuration](#secrets-and-configuration)
2. [Client lifecycle](#client-lifecycle)
3. [Timeouts](#timeouts)
4. [Retries and backoff](#retries-and-backoff)
5. [Async correctness](#async-correctness)
6. [Concurrency and fan-out](#concurrency-and-fan-out)
7. [Prompt construction](#prompt-construction)
8. [Parsing model output](#parsing-model-output)
9. [Streaming](#streaming)
10. [Batching and chunking](#batching-and-chunking)
11. [Logging and observability](#logging-and-observability)
12. [Caching](#caching)
13. [Numerics: numpy and torch](#numerics-numpy-and-torch)
14. [Training and inference loops](#training-and-inference-loops)
15. [Review quick table](#review-quick-table)

---

## Secrets and configuration

**Smell (PY036):** literal keys in code, notebooks or default arguments.

```python
# Before
client = OpenAI(api_key="sk-proj-...")
HEADERS = {"Authorization": "Bearer hf_abc..."}
```

A key in git history is leaked even after the commit is reverted. Rotate it, then:

```python
import os
api_key = os.environ["OPENAI_API_KEY"]          # KeyError at startup is a feature: fail fast
```

Typed settings with validation (pydantic-settings v2):

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_")
    openai_api_key: SecretStr
    model: str = "gpt-4o-mini"
    request_timeout_s: float = 30.0
    max_concurrency: int = 8

settings = Settings()                            # reads APP_OPENAI_API_KEY, APP_MODEL, ...
key = settings.openai_api_key.get_secret_value() # SecretStr hides the value in repr/logs
```

Rules:

- `.env` in `.gitignore`; commit `.env.example` with placeholder values.
- Never log full headers, request bodies with keys, or `repr(settings)` of a non-Secret type.
- Model names, temperatures and limits are configuration, not literals scattered across modules.

## Client lifecycle

**Smell (PY041):** heavy objects created at import time.

```python
# Before: runs on import (tests, CLI --help, every forked worker)
client = OpenAI()
embedder = SentenceTransformer("all-MiniLM-L6-v2")    # downloads weights, allocates GPU
```

Problems: slow imports, network access in unit tests, settings cannot be overridden, GPU memory allocated in processes that never use it, and fork-unsafe objects copied into workers.

**Lazy, cached factory (scripts, libraries):**

```python
from functools import cache

@cache
def get_embedder() -> "SentenceTransformer":
    from sentence_transformers import SentenceTransformer   # defer heavy import too
    return SentenceTransformer(settings.embed_model, device=settings.device)
```

**FastAPI lifespan + dependency injection (services):**

```python
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request
from openai import AsyncOpenAI

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.llm = AsyncOpenAI(timeout=30.0, max_retries=2)
    yield
    await app.state.llm.close()

app = FastAPI(lifespan=lifespan)

def get_llm(request: Request) -> AsyncOpenAI:
    return request.app.state.llm

@app.post("/answer")
async def answer(q: Question, llm: AsyncOpenAI = Depends(get_llm)):
    ...
```

Reuse one client (one connection pool) per process; do not construct a client per request.

## Timeouts

**Smells (PY039, PY042):** `requests` without `timeout=`; SDK clients on default timeouts.

| Library | Default | Idiomatic |
|---------|---------|-----------|
| `requests` | none: waits forever | `requests.post(url, json=b, timeout=(5, 60))` (connect, read) |
| `httpx` | 5 s for each phase | `httpx.Client(timeout=httpx.Timeout(30.0, connect=5.0))` |
| `urllib.request.urlopen` | socket default (none) | `urlopen(req, timeout=30)` |
| `openai` SDK | 600 s, 2 retries | `OpenAI(timeout=30.0, max_retries=3)`; per call `client.with_options(timeout=5)` |
| `anthropic` SDK | 600 s, 2 retries | `Anthropic(timeout=30.0, max_retries=3)` |
| `asyncio` code | none | `async with asyncio.timeout(10):` (3.11+) or `await asyncio.wait_for(coro, 10)` |

```python
import asyncio
async def answer_with_deadline(question: str) -> str:
    async with asyncio.timeout(20):             # 3.11+: cancels everything inside on expiry
        ctx = await retrieve(question)
        return await generate(question, ctx)
```

Set an overall deadline per user request and smaller per-call timeouts beneath it.

## Retries and backoff

**Smell (PY040):** `while True` retry loops.

```python
# Before: 401 Unauthorized or a 400 bad request retries forever
while True:
    try:
        return client.chat.completions.create(**kw)
    except Exception:
        time.sleep(1)
```

Rules for retries:

1. Bound the number of attempts (and ideally total elapsed time).
2. Retry only retryable failures: 408, 409, 429, 5xx, connection errors, timeouts. Never 400/401/403/404/422.
3. Exponential backoff with jitter; honour `Retry-After` when present.
4. Make the operation idempotent (or pass an idempotency key) before retrying writes.
5. Know what the SDK already does: OpenAI/Anthropic SDKs retry twice by default, so wrapping them in another 5-attempt loop gives up to 15 calls.

```python
import random
import time

RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}

def post_json(session, url: str, payload: dict, *, attempts: int = 5, timeout=(5, 60)) -> dict:
    for attempt in range(attempts):
        resp = session.post(url, json=payload, timeout=timeout)
        if resp.status_code not in RETRYABLE_STATUS:
            resp.raise_for_status()
            return resp.json()
        if attempt == attempts - 1:
            resp.raise_for_status()
        retry_after = resp.headers.get("Retry-After")
        delay = float(retry_after) if retry_after and retry_after.isdigit() else min(30.0, 2 ** attempt)
        time.sleep(delay + random.uniform(0, 1))
    raise AssertionError("unreachable")
```

With tenacity (declarative, async-aware):

```python
from openai import APIConnectionError, APITimeoutError, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

@retry(
    retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError)),
    wait=wait_random_exponential(min=1, max=30),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def complete(llm, messages):
    return await llm.chat.completions.create(model=settings.model, messages=messages)
```

## Async correctness

**Smells (PY037, PY038):** blocking calls inside `async def`.

One blocking call inside a coroutine freezes the whole event loop: every in-flight request in a FastAPI worker waits.

| Blocking | Async replacement |
|----------|-------------------|
| `time.sleep(s)` | `await asyncio.sleep(s)` |
| `requests.get(...)` | `await client.get(...)` with `httpx.AsyncClient` / `aiohttp` |
| `OpenAI().chat.completions.create` | `await AsyncOpenAI().chat.completions.create` |
| `subprocess.run([...])` | `await asyncio.create_subprocess_exec(...)` |
| File I/O on large files | `await asyncio.to_thread(path.read_text, encoding="utf-8")` or `aiofiles` |
| CPU-bound (tokenising, embedding on CPU, numpy) | `await asyncio.to_thread(fn, ...)` (releases GIL in C code) or a process pool |

```python
async def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedder()
    return await asyncio.to_thread(model.encode, texts, batch_size=64)
```

Other async rules:

- Never call `asyncio.run()` inside a running loop (notebooks, FastAPI handlers); `await` instead.
- Every coroutine must be awaited or scheduled; a bare `fetch(url)` call does nothing (and warns).
- Keep references to tasks created with `asyncio.create_task`, or they can be garbage collected mid-flight; prefer `TaskGroup` (3.11+).
- In FastAPI, a plain `def` endpoint runs in a threadpool and may block safely; an `async def` endpoint must not block.

## Concurrency and fan-out

**Smell (PY044):** sequential awaits.

```python
# Before: 100 documents = 100 round-trips, one after another
results = []
for doc in docs:
    results.append(await summarize(doc))
```

```python
# After: bounded concurrency
async def summarize_all(docs, limit: int = 8):
    sem = asyncio.Semaphore(limit)

    async def one(doc):
        async with sem:
            return await summarize(doc)

    return await asyncio.gather(*(one(d) for d in docs))
```

Structured concurrency (3.11+): failures cancel siblings and surface as an `ExceptionGroup`.

```python
async def summarize_all(docs, limit: int = 8):
    sem = asyncio.Semaphore(limit)
    results: list[str | None] = [None] * len(docs)

    async def one(i, doc):
        async with sem:
            results[i] = await summarize(doc)

    async with asyncio.TaskGroup() as tg:
        for i, doc in enumerate(docs):
            tg.create_task(one(i, doc))
    return results
```

Partial failure tolerated: `await asyncio.gather(*coros, return_exceptions=True)` then split results with `isinstance(r, BaseException)`.

Choose the limit from the provider's rate limits (requests/min and tokens/min), not from CPU count. Threads (`concurrent.futures.ThreadPoolExecutor`) are the sync equivalent for I/O-bound SDK calls.

## Prompt construction

**Smell (PY043):** prompts glued together with `+` across a function.

```python
# Before
prompt = "You are a helpful assistant.\n" + "Context: " + context + "\n" + "Q: " + q
```

```python
# After: one template constant with named fields
RAG_TEMPLATE = """\
You are a support assistant. Answer only from the context.
If the answer is not in the context, say "I don't know".

<context>
{context}
</context>

Question: {question}"""

def render_rag_prompt(question: str, chunks: list[Chunk]) -> str:
    context = "\n\n".join(f"[{i}] {c.text}" for i, c in enumerate(chunks, start=1))
    return RAG_TEMPLATE.format(context=context, question=question)
```

- Keep templates as module constants or files (versionable, testable, diffable).
- `str.format` treats `{` and `}` specially: double them (`{{` `}}`) when the template contains JSON examples, or use `string.Template` (`$context`) for JSON-heavy prompts.
- Build chat messages as data, not as one string:

```python
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    *history,
    {"role": "user", "content": render_rag_prompt(question, chunks)},
]
```

- Delimit untrusted content (retrieved documents, user input) with clear tags; never concatenate user input into the system prompt.
- Count tokens with the model's tokenizer, not `len(text)`, when trimming context.

## Parsing model output

**Smell (PY004):** `eval()` / `exec()` on model output.

```python
# Before
args = eval(reply)                         # prompt injection -> code execution
```

```python
# After: JSON + schema validation
from pydantic import BaseModel, ValidationError

class SearchArgs(BaseModel):
    query: str
    top_k: int = 5

try:
    args = SearchArgs.model_validate_json(reply)
except ValidationError as err:
    raise InvalidToolArgs(reply[:500]) from err
```

- Prefer provider structured outputs / tool calling with JSON schema over regex-scraping prose.
- Extract fenced JSON with a regex and the walrus operator, then validate:

```python
import re
FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)

def extract_json(reply: str) -> dict:
    if m := FENCE.search(reply):
        return json.loads(m.group(1))
    return json.loads(reply)
```

- `ast.literal_eval` only for Python literals you trust the shape of; it is safe from code execution but can still exhaust memory on huge inputs.

## Streaming

```python
from openai import AsyncOpenAI

async def stream_answer(llm: AsyncOpenAI, messages: list[dict]):
    stream = await llm.chat.completions.create(model=settings.model, messages=messages, stream=True)
    async for event in stream:
        if delta := event.choices[0].delta.content:
            yield delta
```

FastAPI server-sent events:

```python
from fastapi.responses import StreamingResponse

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest, llm: AsyncOpenAI = Depends(get_llm)):
    async def events():
        async for piece in stream_answer(llm, req.messages):
            yield f"data: {json.dumps({'delta': piece})}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(events(), media_type="text/event-stream")
```

Accumulate streamed text with a list and `"".join(parts)` at the end, not `text += delta` (PY018).

## Batching and chunking

```python
from itertools import batched           # 3.12+

def embed_corpus(texts: list[str], batch_size: int = 128) -> list[list[float]]:
    vectors: list[list[float]] = []
    for batch in batched(texts, batch_size):
        resp = client.embeddings.create(model=EMBED_MODEL, input=list(batch))
        vectors.extend(d.embedding for d in resp.data)
    return vectors
```

Chunker with overlap, written with ranges instead of manual index arithmetic:

```python
def chunk_tokens(tokens: list[int], size: int = 512, overlap: int = 64) -> list[list[int]]:
    if not 0 <= overlap < size:
        raise ValueError("overlap must be in [0, size)")
    step = size - overlap
    return [tokens[i:i + size] for i in range(0, max(len(tokens) - overlap, 1), step)]
```

Deduplicate before embedding (`dict.fromkeys(texts)`), and keep ids aligned with vectors by zipping, never by parallel index counters.

## Logging and observability

**Smells (PY034, PY035):** `print` in pipelines; f-strings in log calls.

```python
import logging
logger = logging.getLogger(__name__)

logger.info("retrieved %d chunks in %.0f ms", len(chunks), elapsed_ms)
logger.debug("prompt tokens=%d model=%s", n_tokens, model)
try:
    reply = await complete(llm, messages)
except Exception:
    logger.exception("completion failed request_id=%s", request_id)
    raise
```

- Configure once in the entry point: `logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))`.
- Attach request ids / trace ids with `logging.LoggerAdapter` or `contextvars`, or use structlog.
- Never log raw prompts or completions at INFO in production: they contain user data; log sizes, ids, token counts and latencies instead.
- Record token usage from responses (`resp.usage`) for cost tracking.

## Caching

```python
from functools import lru_cache

@lru_cache(maxsize=10_000)
def embed_query(text: str) -> tuple[float, ...]:
    vec = client.embeddings.create(model=EMBED_MODEL, input=text).data[0].embedding
    return tuple(vec)            # immutable: callers cannot corrupt the cached value
```

- `lru_cache` keys must be hashable; convert lists to tuples.
- It does not work on `async def` (it caches the coroutine object). Use a dict keyed by input plus an `asyncio.Lock`, or a library such as `aiocache`.
- On methods, `lru_cache` keeps `self` alive; prefer module functions or `functools.cached_property` for per-instance values.

## Numerics: numpy and torch

| Smell | Idiom |
|-------|-------|
| `if embedding:` | `if embedding is not None and len(embedding):` / `arr.size` |
| `mask == True` | `mask` (already boolean) |
| Python loop over vectors for cosine | `normed = X / np.linalg.norm(X, axis=1, keepdims=True); sims = normed @ q` |
| `sorted(range(len(s)), key=lambda i: -s[i])[:k]` | `np.argpartition(-s, k)[:k]` then sort those k |
| `x == np.nan` | `np.isnan(x)` |
| `torch.tensor(existing_tensor)` | `existing.clone().detach()` |
| `.cpu().numpy()` inside the hot loop | Accumulate on device, convert once |

```python
import numpy as np

def top_k_cosine(query: np.ndarray, matrix: np.ndarray, k: int = 5) -> list[tuple[int, float]]:
    q = query / np.linalg.norm(query)
    m = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    sims = m @ q
    idx = np.argpartition(-sims, min(k, len(sims) - 1))[:k]
    idx = idx[np.argsort(-sims[idx])]
    return [(int(i), float(sims[i])) for i in idx]
```

## Training and inference loops

```python
import torch

def evaluate(model, loader, device) -> float:
    model.eval()
    correct = total = 0
    with torch.inference_mode():                    # no autograd bookkeeping
        for inputs, labels in loader:               # unpack, don't index batch[0], batch[1]
            inputs, labels = inputs.to(device), labels.to(device)
            preds = model(inputs).argmax(dim=-1)
            correct += (preds == labels).sum().item()
            total += labels.numel()
    return correct / max(total, 1)
```

- `model.train()` / `model.eval()` explicitly at the start of each phase.
- `torch.inference_mode()` (or `no_grad`) for eval and serving.
- `optimizer.zero_grad(set_to_none=True)`.
- Seed once from config (`random`, `numpy`, `torch`), not scattered.
- Checkpoint with `pathlib` paths and atomic writes; save `state_dict()`, not the module object.
- Use `tqdm` / logging for progress, not `print` every step.
- Hyperparameters in a frozen dataclass or pydantic model, not module globals mutated with `global`.

## Review quick table

| Rule | Look for | Severity |
|------|----------|----------|
| PY036 | `sk-`, `hf_`, `AKIA`, `ghp_` literals; `api_key="..."` | high |
| PY037 | `time.sleep` in `async def` | high |
| PY038 | `requests`, `subprocess`, sync SDKs in `async def` | high |
| PY040 | `while True` + `except` + `sleep` | high |
| PY004 | `eval` / `exec` | high |
| PY039 | HTTP without `timeout=` | medium |
| PY041 | Clients/models at module level | medium |
| PY042 | SDK client without `timeout=` | low |
| PY043 | `prompt = ... + ...` | low |
| PY044 | `await` inside `for` | low |
| PY034 | `print` in library functions | low |
| PY035 | `logger.info(f"...")` | low |
| — | Sync SDK method called in `async def` (not detectable by name) | high, manual |
| — | Unbounded `asyncio.gather` over thousands of items | medium, manual |
| — | Raw prompts/PII logged at INFO | medium, manual |
