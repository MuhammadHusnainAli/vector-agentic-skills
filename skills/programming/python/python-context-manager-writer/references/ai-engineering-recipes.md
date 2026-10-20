# AI-Engineering Context Manager Recipes

Production patterns for LLM apps, RAG, agents, training and inference. Every
recipe restores state on error and never swallows exceptions unless stated.
`ctx_tool.py scaffold --recipe NAME` prints the full, verified version of the
recipes marked *(scaffold)*.

## Contents

- [PyTorch: no_grad, inference_mode, autocast](#pytorch-no_grad-inference_mode-autocast)
- [Temporary eval()/train() switch](#temporary-evaltrain-switch)
- [GPU memory cleanup and peak tracking](#gpu-memory-cleanup-and-peak-tracking)
- [Timing and token-usage meters](#timing-and-token-usage-meters)
- [Tracing spans](#tracing-spans)
- [Temporary env vars and API keys](#temporary-env-vars-and-api-keys)
- [Rate-limit semaphores](#rate-limit-semaphores)
- [FastAPI lifespan: load models and clients once](#fastapi-lifespan-load-models-and-clients-once)
- [Per-request dependencies with yield](#per-request-dependencies-with-yield)
- [Database and vector-store transactions](#database-and-vector-store-transactions)
- [Atomic checkpoint writes](#atomic-checkpoint-writes)
- [Deterministic seeds](#deterministic-seeds)
- [Agent sandboxes: temp dirs and cwd](#agent-sandboxes-temp-dirs-and-cwd)
- [Freezing parameters temporarily](#freezing-parameters-temporarily)
- [Prompt/model config overrides](#promptmodel-config-overrides)

## PyTorch: no_grad, inference_mode, autocast

| Manager | Effect | Use |
|---------|--------|-----|
| `torch.no_grad()` | Disables graph recording; tensors can later be used in autograd | Validation loops, EMA updates, weight surgery |
| `torch.inference_mode()` (1.9+) | Stronger: no version counters/view tracking; faster; tensors created inside can never enter autograd | Pure inference / serving |
| `torch.enable_grad()` | Re-enable inside a no_grad region | Gradient-based attribution inside eval code |
| `torch.set_grad_enabled(flag)` | Conditional; works as function call **and** manager | `with torch.set_grad_enabled(is_train):` |
| `torch.autocast(device_type, dtype=...)` | Mixed precision for eligible ops | `bfloat16` on Ampere+/TPU, `float16` + GradScaler for training |

All are thread-local and also usable as decorators (`@torch.inference_mode()`).

```python
import torch


@torch.inference_mode()
def embed_batch(model: torch.nn.Module, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    with torch.autocast(device_type=input_ids.device.type, dtype=torch.bfloat16):
        out = model(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
    mask = attention_mask.unsqueeze(-1).to(out.dtype)
    return (out * mask).sum(1) / mask.sum(1).clamp(min=1)       # mean pooling
```

Bugs to avoid:

```python
torch.no_grad()                  # BUG: creates the object, enters nothing (ctx_tool CTX012)
logits = model(x)

with torch.no_grad:              # BUG: the class, not an instance -> TypeError;
    ...                          #      always write torch.no_grad()

with torch.inference_mode():
    feats = backbone(x)
loss = head(feats).sum()
loss.backward()                  # RuntimeError: inference tensors cannot be saved for backward
                                 # -> use no_grad() when outputs feed training later
```

Training-loop autocast + GradScaler (the scaler is not a context manager; only
autocast is):

```python
scaler = torch.amp.GradScaler("cuda")
for batch in loader:
    optimizer.zero_grad(set_to_none=True)
    with torch.autocast(device_type="cuda", dtype=torch.float16):
        loss = model(**batch).loss
    scaler.scale(loss).backward()          # backward OUTSIDE autocast
    scaler.step(optimizer)
    scaler.update()
```

## Temporary eval()/train() switch

`model.eval()` inside a training loop that is never undone silently disables
dropout and freezes BatchNorm statistics for the rest of training.

```python
from contextlib import contextmanager
from typing import Iterator

import torch


@contextmanager
def evaluating(model: torch.nn.Module) -> Iterator[torch.nn.Module]:
    """eval() + no_grad() for the block, restoring each submodule's original mode."""
    modes = {m: m.training for m in model.modules()}   # submodules may differ (frozen BN)
    model.eval()
    try:
        with torch.no_grad():
            yield model
    finally:
        for m, was_training in modes.items():
            m.train(was_training)


for step, batch in enumerate(train_loader):
    train_step(model, batch)
    if step % 500 == 0:
        with evaluating(model) as m:
            val_loss = sum(m(**b).loss.item() for b in val_loader) / len(val_loader)
```

`ctx_tool.py scaffold --recipe gpu-inference` combines eval switch,
`inference_mode`, optional autocast and cache clearing through an `ExitStack`.

## GPU memory cleanup and peak tracking

```python
import gc
from contextlib import contextmanager
from typing import Dict, Iterator

import torch


@contextmanager
def cuda_memory(label: str, device: int = 0) -> Iterator[Dict[str, float]]:
    """Report peak memory of the block; free cached blocks afterwards."""
    stats: Dict[str, float] = {}
    if not torch.cuda.is_available():
        yield stats
        return
    torch.cuda.synchronize(device)
    torch.cuda.reset_peak_memory_stats(device)
    start = torch.cuda.memory_allocated(device)
    try:
        yield stats
    finally:
        torch.cuda.synchronize(device)
        stats["peak_mib"] = (torch.cuda.max_memory_allocated(device) - start) / 2**20
        gc.collect()
        torch.cuda.empty_cache()
        print(f"[{label}] peak +{stats['peak_mib']:.0f} MiB")


with cuda_memory("generate bs=32") as mem:
    out = model.generate(**batch, max_new_tokens=256)
```

Facts:

- `empty_cache()` only returns *cached, unused* blocks to the driver. Tensors
  still referenced (including by an exception's traceback frames!) stay
  allocated. After an OOM inside `try`, drop references (`del out`, let the
  `except` block end) before clearing.
- Calling `empty_cache()` every step slows training; do it between phases
  (after eval, before loading another model).
- Unloading a model: `del model; gc.collect(); torch.cuda.empty_cache()`
  inside a `finally`.

OOM back-off loop:

```python
def generate_with_backoff(model, prompts, batch_size: int = 64):
    while batch_size >= 1:
        try:
            with torch.inference_mode():
                return [model.generate(**tok(prompts[i:i + batch_size])) for i in range(0, len(prompts), batch_size)]
        except torch.cuda.OutOfMemoryError:
            batch_size //= 2
            gc.collect()
            torch.cuda.empty_cache()     # the traceback has been released at this point
    raise RuntimeError("cannot fit even batch_size=1")
```

## Timing and token-usage meters

```python
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, Iterator


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0
    seconds: float = 0.0
    cost_usd: float = 0.0

    def add(self, resp, price_in: float, price_out: float) -> None:
        u = resp.usage
        self.prompt_tokens += u.prompt_tokens
        self.completion_tokens += u.completion_tokens
        self.calls += 1
        self.cost_usd += u.prompt_tokens * price_in + u.completion_tokens * price_out


@contextmanager
def metered(budget_usd: float = float("inf")) -> Iterator[Usage]:
    """Collect token usage/cost for a block; raise if the budget was exceeded."""
    usage = Usage()
    t0 = time.perf_counter()
    try:
        yield usage
    finally:
        usage.seconds = time.perf_counter() - t0
    if usage.cost_usd > budget_usd:                     # only on success: don't mask errors
        raise RuntimeError(f"budget exceeded: ${usage.cost_usd:.4f} > ${budget_usd}")


with metered(budget_usd=0.50) as usage:
    for q in eval_questions:
        resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": q}])
        usage.add(resp, price_in=0.15e-6, price_out=0.60e-6)
print(f"{usage.calls} calls, {usage.prompt_tokens}+{usage.completion_tokens} tokens, "
      f"${usage.cost_usd:.4f}, {usage.seconds:.1f}s")
```

Use `time.perf_counter()` for durations (monotonic, high resolution), never
`time.time()`. For GPU work call `torch.cuda.synchronize()` before reading the
clock, because kernels run asynchronously.

## Tracing spans

`ctx_tool.py scaffold --recipe span` prints a dependency-free span with parent
tracking via `contextvars` (correct across threads and asyncio tasks).

With OpenTelemetry:

```python
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer("rag-service")


def answer(question: str) -> str:
    with tracer.start_as_current_span("rag.answer") as span:      # records exceptions by default
        span.set_attribute("question.length", len(question))
        with tracer.start_as_current_span("retrieve") as s:
            docs = retriever.search(question, k=8)
            s.set_attribute("retrieve.k", 8)
        with tracer.start_as_current_span("llm.generate") as s:
            resp = llm.complete(build_prompt(question, docs))
            s.set_attribute("gen_ai.usage.input_tokens", resp.usage.prompt_tokens)
            s.set_attribute("gen_ai.usage.output_tokens", resp.usage.completion_tokens)
        return resp.text
```

`start_as_current_span` sets the span status to ERROR and records the exception
when the block raises (`record_exception=True`, `set_status_on_exception=True`
are the defaults), then re-raises.

Why `contextvars` and not a global/thread-local stack: asyncio tasks share a
thread; each task gets a copy of the context at creation, so concurrent tasks
do not corrupt each other's parent span. Always `reset(token)` in `finally`.

## Temporary env vars and API keys

*(scaffold: `temp-env`)* Used for tests and for SDKs that only read config from
the environment.

Caveats:

- `os.environ` is process-wide: two threads or tasks overriding the same key
  race. Prefer passing keys explicitly (`OpenAI(api_key=...)`).
- SDK clients often read env vars **at construction**; create the client inside
  the block.
- In pytest use `monkeypatch.setenv` / `monkeypatch.delenv` instead (auto-undone).
- `unittest.mock.patch.dict(os.environ, {...}, clear=False)` is the stdlib
  equivalent and works as decorator too.

```python
from unittest import mock

with mock.patch.dict("os.environ", {"OPENAI_BASE_URL": "http://localhost:8000/v1"}):
    client = OpenAI()        # picks up the local vLLM server
```

## Rate-limit semaphores

*(scaffold: `semaphore`)* Concurrency cap + minimum spacing between request
starts. Combine with retry/backoff on 429:

```python
import asyncio
import random


async def call_with_retry(limiter, fn, *, attempts: int = 5):
    for attempt in range(attempts):
        async with limiter:                         # slot released before sleeping
            try:
                return await fn()
            except RateLimitError as exc:
                if attempt == attempts - 1:
                    raise
                delay = getattr(exc, "retry_after", None) or min(60, 2 ** attempt + random.random())
        await asyncio.sleep(delay)                  # back off OUTSIDE the semaphore
```

Sleeping while holding the slot would block other healthy requests.

Thread version (sync SDKs with a `ThreadPoolExecutor`):

```python
import threading

LLM_SLOTS = threading.BoundedSemaphore(8)

def classify(text: str) -> str:
    with LLM_SLOTS:
        return llm.complete(f"Classify: {text}")
```

## FastAPI lifespan: load models and clients once

`lifespan` is an async context manager: code before `yield` runs at startup,
after `yield` at shutdown. Replaces deprecated `@app.on_event`.

```python
from contextlib import asynccontextmanager
from typing import AsyncIterator

import gc

import httpx
import torch
from fastapi import FastAPI, Request
from sentence_transformers import SentenceTransformer
from starlette.concurrency import run_in_threadpool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.embedder = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cuda")
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(60, connect=5))
    try:
        yield
    finally:
        await app.state.http.aclose()
        del app.state.embedder
        gc.collect()
        torch.cuda.empty_cache()


app = FastAPI(lifespan=lifespan)


@app.post("/embed")
async def embed(req: Request, texts: list[str]) -> list[list[float]]:
    model = req.app.state.embedder
    # encode() is blocking CPU/GPU work: run it off the event loop
    vectors = await run_in_threadpool(model.encode, texts, normalize_embeddings=True)
    return vectors.tolist()
```

Alternatively yield a
state dict: `yield {"embedder": model}` and read `request.state.embedder`.

Testing: `with TestClient(app) as client:` runs the lifespan; a bare
`TestClient(app)` without `with` does **not**.

## Per-request dependencies with yield

FastAPI dependencies with `yield` are context managers per request:

```python
from typing import AsyncIterator

from fastapi import Depends


async def get_db() -> AsyncIterator["AsyncSession"]:
    async with SessionLocal() as session:          # SQLAlchemy AsyncSession
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


@app.post("/documents")
async def add_document(doc: DocIn, db=Depends(get_db)):
    db.add(Document(**doc.model_dump()))
```

Do not hand the session to `BackgroundTasks`: the dependency's exit code
(commit/close) may already have run when the background task starts. Open a
fresh session inside the task instead.

## Database and vector-store transactions

```python
import sqlite3
from contextlib import closing, contextmanager
from typing import Iterator


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute("BEGIN")
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    else:
        conn.commit()


with closing(sqlite3.connect("rag.db", isolation_level=None)) as conn:   # autocommit; we manage BEGIN
    with transaction(conn):
        conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
        conn.executemany("INSERT INTO chunks(doc_id, ord, text) VALUES (?, ?, ?)", rows)
```

Facts that bite:

| Library | `with conn:` means |
|---------|-------------------|
| `sqlite3` | Transaction (commit/rollback) — does **not** close |
| `psycopg2` | Transaction — does **not** close |
| `psycopg` (3) | Closes the connection (and commits/rolls back) |
| SQLAlchemy `Session` | `with Session() as s:` closes; `with s.begin():` is the transaction |
| `asyncpg` | `async with conn.transaction():` |

Vector stores without transactions (most HTTP-based ones): emulate atomic
re-indexing with a compensation step:

```python
@contextmanager
def staged_upsert(store, collection: str) -> Iterator[str]:
    """Write into a temp collection; swap alias on success, drop it on failure."""
    staging = f"{collection}__staging"
    store.create_collection(staging)
    try:
        yield staging
    except BaseException:
        store.delete_collection(staging)
        raise
    store.swap_alias(alias=collection, target=staging)
```

## Atomic checkpoint writes

*(scaffold: `atomic-write`)* Write to a temp file **in the same directory**,
flush + `fsync`, then `os.replace` (atomic on POSIX and Windows when on the same
filesystem). A crash mid-save leaves the old checkpoint intact.

```python
with atomic_write("checkpoints/step_1200.pt", mode="wb") as f:
    torch.save({"model": model.state_dict(), "optim": optimizer.state_dict(), "step": 1200}, f)

with atomic_write("index/manifest.json") as f:
    json.dump({"embedding_model": "bge-small-en-v1.5", "dim": 384, "count": n}, f)
```

For full durability also `fsync` the directory after `os.replace` on Linux.

## Deterministic seeds

*(scaffold: `seed`)* Seeds `random`, NumPy's legacy global RNG and torch, and
restores their states. Prefer explicit generators where possible:

```python
rng = np.random.default_rng(1234)                 # no global state to restore
g = torch.Generator().manual_seed(1234)
loader = DataLoader(ds, shuffle=True, generator=g)
```

LLM sampling cannot be made deterministic by local seeds; set `temperature=0`
and, where the API supports it, a `seed` parameter, and still expect
occasional variation.

## Agent sandboxes: temp dirs and cwd

```python
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def sandbox(files: dict[str, str], keep_on_error: bool = False) -> Iterator[Path]:
    """Materialise agent-written files in a fresh dir; delete afterwards."""
    root = Path(tempfile.mkdtemp(prefix="agent-"))
    ok = False
    try:
        for rel, content in files.items():
            p = (root / rel).resolve()
            if root.resolve() not in p.parents:            # block ../../ path traversal
                raise ValueError(f"path escapes sandbox: {rel}")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        yield root
        ok = True
    finally:
        if ok or not keep_on_error:
            shutil.rmtree(root, ignore_errors=True)


with sandbox({"main.py": code, "test_main.py": tests}) as root:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"], cwd=root,
        capture_output=True, text=True, timeout=60,
    )
```

Pass `cwd=` to the subprocess instead of `os.chdir` — `chdir` is process-wide
and breaks concurrent agents. `tempfile.TemporaryDirectory(ignore_cleanup_errors=True)`
(3.10+) is the simpler choice when you never need to keep the directory;
`delete=False` was added in 3.12.

## Freezing parameters temporarily

```python
@contextmanager
def frozen(module: torch.nn.Module) -> Iterator[torch.nn.Module]:
    flags = [p.requires_grad for p in module.parameters()]
    for p in module.parameters():
        p.requires_grad_(False)
    try:
        yield module
    finally:
        for p, flag in zip(module.parameters(), flags):
            p.requires_grad_(flag)


with frozen(model.encoder):
    train_head_for_one_epoch(model)
```

## Prompt/model config overrides

Temporarily override fields of a shared config object (e.g. lower temperature
for a single evaluation pass):

```python
from contextlib import contextmanager
from dataclasses import replace
from typing import Any, Iterator


@contextmanager
def overridden(obj: Any, **changes: Any) -> Iterator[Any]:
    """Set attributes for the block and restore the originals (also for missing ones)."""
    missing = object()
    saved = {k: getattr(obj, k, missing) for k in changes}
    try:
        for k, v in changes.items():
            setattr(obj, k, v)
        yield obj
    finally:
        for k, v in saved.items():
            if v is missing:
                delattr(obj, k)
            else:
                setattr(obj, k, v)


with overridden(gen_config, temperature=0.0, max_new_tokens=64):
    score = run_eval(model, gen_config)
```

If the config is a frozen dataclass or Pydantic model, prefer creating a copy
(`dataclasses.replace(cfg, temperature=0.0)` / `cfg.model_copy(update={...})`)
over mutation — no context manager needed and no shared-state races.
