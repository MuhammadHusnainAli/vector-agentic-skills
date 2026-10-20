---
name: python-context-manager-writer
description: "Write correct Python context managers and find resource-handling bugs — __enter__/__exit__ semantics and exception suppression, contextlib (contextmanager, asynccontextmanager, ExitStack, AsyncExitStack, closing, aclosing, suppress, redirect_stdout, nullcontext, chdir), async with, re-entrancy, leaked files/connections/clients/pools/locks, and AI-engineering recipes: torch.no_grad/inference_mode/autocast, eval()/train() switches, GPU cache cleanup, token and latency meters, tracing spans, temp env vars, rate-limit semaphores, httpx/aiohttp client lifecycle, FastAPI lifespan, DB/vector-store transactions, atomic checkpoint writes, seeds and agent sandboxes. Use when writing or reviewing a with statement or context manager, when files/sockets/clients/sessions/locks are opened without with, when an error is silently swallowed by __exit__ or a @contextmanager, on ResourceWarning, Too many open files, deadlocks, or generator didn't stop errors, or when wiring setup/teardown for models, clients and transactions."
metadata:
  category: programming
  subcategory: python
  version: "1.0.0"
---

# Python Context Manager Writer

Design, write and review context managers so that every resource an LLM app,
RAG pipeline, agent or training loop acquires — files, DB and vector-store
connections, HTTP clients, GPU memory, locks, semaphores, temp directories,
global state like env vars or `model.training` — is released on every exit
path, exceptions are never swallowed by accident, and async code uses the
async protocol. Includes a static leak finder and a generator for typed,
documented managers and AI-engineering recipes.

## Trigger Conditions

Activate this skill when the user:
- Asks to write a context manager, a `with`-able class, or a `@contextmanager` / `@asynccontextmanager` function
- Has code that opens files, `sqlite3`/`psycopg` connections, sockets, `httpx`/`aiohttp`/`requests` clients, `ThreadPoolExecutor`, `subprocess.Popen` or temp dirs without `with`
- Sees `ResourceWarning`, `Too many open files`, "database is locked", deadlocks, `generator didn't stop`, `generator didn't yield`, `'NoneType' object has no attribute` on an `as` variable, or `__exit__() takes N positional arguments`
- Reports exceptions that "disappear" inside a `with` block
- Needs setup/teardown for models (eval mode, `inference_mode`, autocast, GPU cleanup), API clients, FastAPI `lifespan`, DB transactions, checkpoints, seeds, env vars, tracing, rate limits or agent sandboxes
- Wants to manage a variable number of resources (`ExitStack`) or cancel background tasks on exit

## Workflow

```
1. INVENTORY -> list every resource/state change: what acquires it, who owns it, how it is released
2. SCAN      -> python scripts/ctx_tool.py leaks <file|dir> (static; never runs code)
3. CHOOSE    -> with-statement / @contextmanager / class / ExitStack / lifespan (table below)
4. WRITE     -> setup before try, one yield inside try/finally, falsy __exit__, typed
                (scripts/ctx_tool.py scaffold ... gives a verified skeleton)
5. EDGE      -> partial setup failure, body raises, early return, cancellation, reuse, threads
6. TEST      -> teardown on success + on exception + exception still propagates
7. RE-SCAN   -> ctx_tool.py leaks --strict exits 0
```

## Choosing the Tool

| Situation | Use |
|-----------|-----|
| Resource already supports `with` (files, `httpx.Client`, pools, `Popen`, locks, `TemporaryDirectory`) | Plain `with` — do not wrap it |
| Object has `close()` but no `__exit__` | `contextlib.closing(obj)` / `aclosing(obj)` (3.10) |
| One-off setup/teardown around a block | `@contextmanager` generator |
| Async setup/teardown (`await` in either half) | `@asynccontextmanager` or `__aenter__`/`__aexit__` |
| Object with methods that owns resources (client wrapper, session, index) | Class with `__enter__` returning `self` + `close()` |
| N resources decided at runtime, conditional managers | `ExitStack` / `AsyncExitStack` |
| Acquire several, keep them on success, release on partial failure | `ExitStack` + `pop_all()` |
| App-lifetime resources (models, clients, pools) in a web service | FastAPI `lifespan` |
| Optional manager | `cm if flag else nullcontext()` |
| Ignore one specific exception | `contextlib.suppress(FileNotFoundError)` |
| Reusable or re-entrant behaviour, or suppression logic | Class (with depth counter / `RLock` for re-entrancy) |

## Protocol Rules (non-negotiable)

| Rule | Detail |
|------|--------|
| `__enter__` returns the thing bound by `as` | Usually `self`; forgetting it binds `None` |
| `__exit__(self, exc_type, exc, tb)` | Exactly four params (or `*exc_info`) |
| `__exit__` returns falsy | Truthy suppresses the exception — only for specific, handled types: `return exc_type is not None and issubclass(exc_type, X)` |
| If `__enter__` raises, `__exit__` does not run | Undo partial setup inside `__enter__` (or build it with `ExitStack` + `pop_all()`) |
| `__exit__` runs on `return`/`break`/`continue` and on `BaseException` | Including `KeyboardInterrupt` and `asyncio.CancelledError` |
| An exception in `__exit__` replaces the body's exception | Log secondary cleanup failures when `exc is not None` |
| Multiple items enter left-to-right, exit right-to-left | Parenthesized form is 3.10+ |
| Async protocol is separate | `async def __aenter__/__aexit__`; `async with` only |

## @contextmanager Rules

```python
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def leased_gpu(pool: "DevicePool") -> Iterator[int]:
    device = pool.take()            # 1. setup BEFORE try (nothing to undo if it fails)
    try:
        yield device                # 2. exactly one yield, inside try
    finally:
        pool.give_back(device)      # 3. teardown in finally (runs on error too)
```

| Do | Don't |
|----|-------|
| `try/finally` around `yield` whenever code follows it | Cleanup after a bare `yield` (skipped on error) |
| `except ...: rollback(); raise` | `except Exception: log(...)` without `raise` (suppresses) |
| `else:` for success-only work (commit) | Commit in `finally` (commits failed work) |
| One `yield` per path (`if/else` branches OK) | `yield` in a loop or in an `except` after the main yield |
| Call the function for each `with` | Reuse the returned object (single use) |

## Before / After

### Leaked resources in a RAG ingest job

```python
# BEFORE
def ingest(paths, db_path):
    conn = sqlite3.connect(db_path)                 # never closed
    pool = ThreadPoolExecutor(8)                    # never shut down
    for p in paths:
        text = open(p).read()                       # closed only by GC
        chunks = list(pool.map(embed, split(text)))
        conn.executemany("INSERT INTO chunks VALUES (?, ?)", chunks)
    conn.commit()
```

```python
# AFTER
from contextlib import closing
from pathlib import Path


def ingest(paths: list[Path], db_path: str) -> None:
    with closing(sqlite3.connect(db_path)) as conn, ThreadPoolExecutor(8) as pool:
        with conn:                                  # sqlite3: transaction, not close
            for p in paths:
                text = p.read_text(encoding="utf-8")
                chunks = list(pool.map(embed, split(text)))
                conn.executemany("INSERT INTO chunks VALUES (?, ?)", chunks)
```

### __exit__ that swallows everything

```text
# BEFORE                                  # AFTER
class EvalMode:                           class EvalMode:
    def __enter__(self):                      def __enter__(self) -> "EvalMode":
        self.m.eval()                             self.was_training = self.m.training
                                                  self.m.eval()
                                                  return self
    def __exit__(self, *a):                   def __exit__(self, exc_type, exc, tb) -> None:
        self.m.train()                            self.m.train(self.was_training)
        return True   # hides every bug           # falsy: exceptions propagate
```

### Lock without finally

```text
# BEFORE                                  # AFTER
lock.acquire()                            with lock:
cache[key] = compute()  # raises ->           cache[key] = compute()
lock.release()          # deadlock
```

### Async client per request → shared client in lifespan

```python
# BEFORE: new pool + TLS handshake per call, never closed
async def complete(prompt):
    client = httpx.AsyncClient()
    r = await client.post(URL, json={"prompt": prompt})
    return r.json()
```

```python
# AFTER
from contextlib import asynccontextmanager
from typing import AsyncIterator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(60, connect=5))
    try:
        yield
    finally:
        await app.state.http.aclose()

app = FastAPI(lifespan=lifespan)
```

## AI-Engineering Patterns (summary)

| Need | Pattern |
|------|---------|
| Inference without autograd | `with torch.inference_mode():` (`no_grad()` if outputs feed training) |
| Mixed precision | `with torch.autocast(device_type="cuda", dtype=torch.bfloat16):`; `backward()` outside |
| Validation inside a training loop | Save `model.training` (per submodule), `eval()`, restore in `finally` |
| Free GPU memory between phases | `del` refs → `gc.collect()` → `torch.cuda.empty_cache()` in `finally` |
| Latency / token / cost accounting | Meter yielded from `@contextmanager`, duration in `finally`, `perf_counter()` |
| Tracing | OpenTelemetry `start_as_current_span`, or `contextvars`-based span; reset token in `finally` |
| Temporary API key / base URL | Save & restore `os.environ` (not thread-safe; prefer explicit client args) |
| Concurrency/rate limits | One shared `asyncio.Semaphore`; back off **outside** the slot |
| Model + client loading once | FastAPI `lifespan`; `with TestClient(app)` in tests |
| Per-request DB session | Dependency with `yield` (commit / rollback / close) |
| Checkpoints, indexes, manifests | Atomic write: temp in same dir → `fsync` → `os.replace` |
| Reproducible evals | Seed and restore `random`/NumPy/torch RNG state |
| Agent code execution | Temp dir sandbox + `subprocess.run(cwd=..., timeout=...)`, never `os.chdir` |
| Background heartbeat for a block | `create_task` on enter; `cancel()` + await in `finally` |

Full code: [references/ai-engineering-recipes.md](references/ai-engineering-recipes.md).

## Async Rules

- `httpx.AsyncClient`, `aiohttp.ClientSession`, `asyncio.Lock/Semaphore`, `TaskGroup`, `asyncio.timeout` (3.11) need `async with`.
- Never swallow `asyncio.CancelledError` in `__aexit__` or around `yield`.
- Cleanup that must finish during cancellation: `await asyncio.shield(release())`, kept short.
- Close async generators that hold connections with `contextlib.aclosing` (3.10).
- No blocking I/O in `__aexit__`; use `await asyncio.to_thread(fn)`.
- Create shared semaphores/locks once; `async with asyncio.Semaphore(8):` in a worker limits nothing.

Details: [references/async-context-managers.md](references/async-context-managers.md).

## ExitStack Essentials

```python
from contextlib import ExitStack


def open_shards(paths):
    with ExitStack() as stack:
        files = [stack.enter_context(open(p, encoding="utf-8")) for p in paths]
        stack.callback(log.info, "closed %d shards", len(files))
        return merge(files)


class Index:
    def __init__(self, vec_path, meta_path):
        with ExitStack() as stack:                       # releases on partial failure
            self.vec = stack.enter_context(open(vec_path, "rb"))
            self.meta = stack.enter_context(closing(sqlite3.connect(meta_path)))
            self._stack = stack.pop_all()                # success: keep them open

    def close(self) -> None:
        self._stack.close()
```

## Review Checklist

- [ ] Every acquire has a release on **every** path (success, exception, early return, cancellation)
- [ ] No `open(...).read()`, `json.load(open(...))`, unclosed `Session`/`Client`/pool/`Popen`
- [ ] `close()` calls that are not in `finally` replaced by `with`
- [ ] `@contextmanager`: setup before `try`, single `yield` in `try`, cleanup in `finally`, every `except` re-raises
- [ ] `__enter__` returns a value; `__exit__` has 4 params and returns falsy unless suppression is intended and narrow
- [ ] Partial setup in `__enter__` undone on failure
- [ ] Sync vs async protocol matches the call site
- [ ] Locks/semaphores created once and shared
- [ ] Global state (env, cwd, stdout, logging level, `model.training`, RNG) restored in `finally`
- [ ] Lazy iterators do not escape the `with` that owns their source
- [ ] Tests cover teardown on exception and that the exception still propagates

## Output Format

When writing or fixing context managers, answer with:

1. **Findings** (review tasks): table of `line | rule | problem | fix`, ordered by severity
   (paste `ctx_tool.py leaks` output where useful).
2. **Code**: the complete manager or the rewritten function — typed, with a docstring
   stating what is acquired, what is released, whether exceptions are suppressed,
   and whether it is reusable/re-entrant/thread-safe.
3. **Usage**: a short `with`/`async with` example in the user's domain.
4. **Tests**: at least "cleanup on success", "cleanup on exception + exception propagates",
   and (async) "cleanup on cancellation".
5. **Notes**: version requirements (3.10 parenthesized `with`/`aclosing`, 3.11 `chdir`/`TaskGroup`),
   thread/async-safety caveats.

## Scripts

`scripts/ctx_tool.py` — standard library only, Python 3.9+, never imports or runs the analysed code.

```bash
# Static leak and protocol-bug scan (files, directories, or - for stdin)
python scripts/ctx_tool.py leaks app/ingest.py
python scripts/ctx_tool.py leaks src/ --json
cat agent.py | python scripts/ctx_tool.py leaks - --strict             # exit 1 on medium/high findings
python scripts/ctx_tool.py leaks src/ --strict --fail-on high          # CI gate on high only
python scripts/ctx_tool.py leaks src/ --min-severity medium            # hide low-severity notes
python scripts/ctx_tool.py rules                                       # CTX001..CTX012

# Scaffold a typed, documented manager (verified with ast.parse; exit 2 if it does not parse)
python scripts/ctx_tool.py scaffold vector_tx --kind generator \
    --setup "conn = pool.getconn()" --teardown "pool.putconn(conn)" --yields conn
python scripts/ctx_tool.py scaffold ModelSession --kind async-class \
    --setup "self.client = httpx.AsyncClient()" --teardown "await self.client.aclose()" --import "import httpx"
python scripts/ctx_tool.py scaffold lease --kind async-generator \
    --setup "conn = await pool.acquire()" --teardown "await pool.release(conn)" --yields conn
python scripts/ctx_tool.py scaffold --list-recipes
python scripts/ctx_tool.py scaffold --recipe gpu-inference              # timer|temp-env|cwd|gpu-inference|
python scripts/ctx_tool.py scaffold eval_seed --recipe seed --json      # atomic-write|semaphore|span|seed
```

| Rule | Severity | Catches |
|------|----------|---------|
| CTX001 | high/medium/low | Resource opened outside `with`: never closed (high), closed outside `finally` / inline `.read()` / passed along (medium), module-level or handed to another owner (low) |
| CTX002 | high/low | `.acquire()` without `try/finally` release; acquire inside the `try` (low) |
| CTX003 | high | `@contextmanager` cleanup after `yield` not protected by `finally` |
| CTX004 | high | No yield, yield in a loop, or two yields on one path |
| CTX005 | high | `__exit__`/`__aexit__` unconditionally returns a truthy value |
| CTX006 | low/medium | `__enter__` returns None (medium when the file binds it with `as`) |
| CTX007 | medium | `except` around `yield` that does not re-raise |
| CTX008 | high | Wrong `__exit__` arity |
| CTX009 | high | Sync/async protocol mix-up |
| CTX010 | high | Plain `with` on `httpx.AsyncClient` / `aiohttp.ClientSession` |
| CTX011 | high | `with threading.Lock():` / `asyncio.Semaphore()` created in the `with` |
| CTX012 | medium | `torch.no_grad()`, `suppress(...)` etc. as a bare statement |

Exit codes: 0 = clean (or findings without `--strict`), 1 = `--strict` and a finding at or above
`--fail-on` (default medium), 2 = usage error, unreadable file, syntax error, or scaffold failed to parse.
Heuristics are intraprocedural: confirm "handed to another owner" (low) findings by reading the callee.

## Additional Resources

| File | Content |
|------|---------|
| [protocol-reference.md](references/protocol-reference.md) | `with` semantics, `__enter__`/`__exit__` return values, exceptions in `__exit__`, multi-item `with`, reusable vs re-entrant, typing, version notes |
| [contextlib-reference.md](references/contextlib-reference.md) | Every contextlib tool: contextmanager, asynccontextmanager, ExitStack, AsyncExitStack, closing, aclosing, suppress, redirect_*, nullcontext, chdir, ABCs, ContextDecorator |
| [async-context-managers.md](references/async-context-managers.md) | Async protocol, cancellation, semaphores, background tasks, TaskGroup/timeout, httpx/aiohttp lifecycle, aclosing, dual sync/async managers |
| [ai-engineering-recipes.md](references/ai-engineering-recipes.md) | torch no_grad/inference_mode/autocast, eval switch, GPU memory, meters, spans, env vars, rate limits, FastAPI lifespan, transactions, atomic checkpoints, seeds, sandboxes |
| [recipes.md](references/recipes.md) | General recipes: files, temp files, cwd, locks, pools, subprocesses, sockets, patching, logging, warnings, signals, timing, object pools |
| [pitfalls-and-testing.md](references/pitfalls-and-testing.md) | 20 pitfalls with fixes and rule ids, generator pitfalls, lazy iterators, thread safety, pytest patterns, runtime leak detection |
