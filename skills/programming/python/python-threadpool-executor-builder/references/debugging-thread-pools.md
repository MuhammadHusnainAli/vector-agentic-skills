# Debugging Thread Pools

Find out what a thread pool is doing, why it lost data, why it is slow, and why it will not stop. For a full
hang investigation (thread dumps of a stuck production process, lock-order cycles, watchdogs) use
[python-async-deadlock-debugger](../../python-async-deadlock-debugger/SKILL.md); this file covers the
pool-specific failure modes and every linter rule.

## Contents

1. [Triage](#1-triage)
2. [Error messages explained](#2-error-messages-explained)
3. [Every TPE rule, before and after](#3-every-tpe-rule-before-and-after)
4. [Seeing what every thread is doing](#4-seeing-what-every-thread-is-doing)
5. [The process will not exit](#5-the-process-will-not-exit)
6. [The pool is slow](#6-the-pool-is-slow)
7. [Instrumenting an executor](#7-instrumenting-an-executor)

## 1. Triage

| Observation | First check | Likely cause |
|-------------|-------------|--------------|
| Output has fewer rows than input, exit code 0 | `executor_tool.py check` for TPE001/TPE005/TPE015 | Futures never read; `except Exception: pass` |
| RSS grows during "submitting", no progress output | TPE003/TPE004 | Unbounded submission |
| Stuck at N% forever | Thread dump (section 4) | Pool exhaustion (TPE009), a call without timeout, a lock |
| Finishes work but does not exit | `threading.enumerate()` at the end of `main` | Non-daemon thread, executor never shut down, queued work |
| Ctrl-C does nothing for minutes | Main thread in `with` exit / `result()` | No `cancel_futures`, no stop event (TPE012) |
| Throughput far below the rate limit | Limiter wait vs call latency (section 6) | Too few workers, small connection pool, GIL-bound parsing |
| 429s despite a limiter | Is the bucket shared? Do retries take tokens? | One bucket per thread, retries bypassing it, several processes |
| Wrong totals, flaky tests | TPE006 | Unlocked read-modify-write |
| Request ids missing in worker logs | TPE019 | Context not copied |

## 2. Error messages explained

| Message | Meaning | Fix |
|---------|---------|-----|
| `RuntimeError: cannot schedule new futures after shutdown` | `submit` after `shutdown()` / after the `with` block | Submit inside the block; keep app-wide executors alive until app shutdown |
| `RuntimeError: cannot schedule new futures after interpreter shutdown` | `submit` while the interpreter exits: from `atexit`, `__del__`, a daemon thread, or after `main` returned while threads still run | Stop producers and join threads before `main` returns |
| `concurrent.futures.thread.BrokenThreadPool: A thread initializer failed, the thread pool is not usable anymore` | `initializer` raised; traceback logged as `Exception in initializer:` | Fix the initializer; validate config before creating the pool |
| `exception calling callback for <Future ...>` (logged) | A done-callback raised; the exception was swallowed after logging | Make callbacks total (try/except inside) |
| `TimeoutError` from `as_completed` / `map` | The overall deadline passed | The tasks still run: cancel queued ones, decide what to do with the rest |
| `concurrent.futures.CancelledError` from `result()` | The future was cancelled (by you, `shutdown(cancel_futures=True)` or `map` after an error) | Expected during shutdown: count it |
| `Connection pool is full, discarding connection: host` (urllib3 warning) | More threads than `pool_maxsize` for one host | `HTTPAdapter(pool_maxsize=workers)` |
| `httpx.PoolTimeout` | All connections busy longer than the pool timeout | `Limits(max_connections=...)` >= workers, or fewer workers |
| `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread` | Shared connection | Connection per thread / writer thread |
| `RuntimeError: dictionary changed size during iteration` | One thread iterates a dict another mutates | Snapshot under a lock (`with lock: items = list(d.items())`) |
| `RuntimeError: cannot enter context: <Context> is already entered` | One `copy_context()` result shared by concurrent tasks | One copy per task |
| `Exception in thread writer:` + traceback on stderr | A raw `Thread` died; printed by `threading.excepthook` | Catch in the thread and forward the error; or use a pool |

## 3. Every TPE rule, before and after

Run `python scripts/executor_tool.py check --list-rules` for the canonical why/fix text of each rule.

**TPE001 future-never-read** - exceptions vanish.

```python
# before
for doc in docs:
    ex.submit(upsert, doc)
# after
futures = {ex.submit(upsert, doc): doc for doc in docs}
for fut in as_completed(futures):
    try:
        fut.result()
    except Exception as exc:
        failed[futures[fut]] = exc
```

**TPE002 executor-not-shutdown** - leaked threads, no collection point.

```python
# before
def embed_all(batches):
    ex = ThreadPoolExecutor(16)
    return list(ex.map(embed, batches))
# after
def embed_all(batches):
    with ThreadPoolExecutor(16, thread_name_prefix="embed") as ex:
        return list(ex.map(embed, batches))
```

**TPE003 unbounded-submit** and **TPE004 map-over-generator** - memory grows with the input.

```python
# before
futures = [ex.submit(score, line) for line in open("prompts.jsonl")]
results = ex.map(score, (json.loads(l) for l in open("prompts.jsonl")))
# after: sliding window (any version) or buffersize (3.14+)
for i, res in window_map(score, open("prompts.jsonl"), ex, max_in_flight=64):
    write(i, res)
results = ex.map(score, (json.loads(l) for l in open("prompts.jsonl")), buffersize=64)
```

**TPE005 map-results-unconsumed** - exceptions never raised; timeout never enforced.

```python
# before
with ThreadPoolExecutor(8) as ex:
    ex.map(upsert, batches)
    it = ex.map(fetch, urls, timeout=30)
pages = list(it)                       # after the with: everything already finished, timeout meaningless
# after
with ThreadPoolExecutor(8) as ex:
    for _ in ex.map(upsert, batches):
        pass
    pages = list(ex.map(fetch, urls, timeout=30))
```

**TPE006 shared-read-modify-write** and **TPE007 shared-container-mutation**.

```python
# before
def work(doc):
    global TOKENS
    TOKENS += count(doc)
    RESULTS.append(parse(doc))
# after: return values and aggregate in the caller
def work(doc):
    return count(doc), parse(doc)
pairs = list(ex.map(work, docs))
tokens = sum(n for n, _ in pairs)
```

**TPE008 shared-unsafe-client** - one `requests.Session` / `sqlite3` connection used by all workers.

```python
# before
SESSION = requests.Session()
def fetch(url):
    return SESSION.get(url, timeout=10).text
# after
_local = threading.local()
def fetch(url):
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
    return _local.s.get(url, timeout=10).text
```

**TPE009 executor-self-wait** - pool exhaustion deadlock under load.

```python
# before
def summarize_doc(doc):
    parts = [POOL.submit(summarize_chunk, c) for c in chunks(doc)]
    return combine([p.result() for p in parts])        # holds a POOL worker while waiting on POOL
results = [POOL.submit(summarize_doc, d) for d in docs]
# after: flatten (submit leaves from the caller), or a separate pool per level
chunk_futs = {POOL.submit(summarize_chunk, c): d for d in docs for c in chunks(d)}
```

Why it deadlocks and how to prove it from a thread dump: section 6 of
[threading-and-multiprocessing-deadlocks.md](../../python-async-deadlock-debugger/references/threading-and-multiprocessing-deadlocks.md).

**TPE010 pool-size-smell** - `max_workers=200` or `max_workers=1`.

```python
# before
ex = ThreadPoolExecutor(max_workers=200)
# after
ex = ThreadPoolExecutor(max_workers=workers_for(rpm / 60, p95_latency_s), thread_name_prefix="llm")
```

**TPE011 result-without-timeout** (request handlers).

```python
# before
def search(queries):
    futures = [IO_POOL.submit(call_llm, q) for q in queries]
    return [f.result() for f in futures]
# after
def search(queries):
    futures = [IO_POOL.submit(call_llm, q) for q in queries]
    deadline = time.monotonic() + 10
    return [f.result(timeout=max(0.0, deadline - time.monotonic())) for f in futures]
```

**TPE012 shutdown-nowait-at-exit** - queued work keeps running after Ctrl-C.

```python
# before
try:
    run_all(ex)
except KeyboardInterrupt:
    ex.shutdown(wait=False)
# after
try:
    run_all(ex)
except KeyboardInterrupt:
    stop.set()
    ex.shutdown(wait=True, cancel_futures=True)
    raise
```

**TPE013 daemon-thread-side-effects** - writes cut off at exit.

```python
# before
threading.Thread(target=flush_to_s3, args=(q,), daemon=True).start()
# after
t = threading.Thread(target=flush_to_s3, args=(q,), name="s3-flusher")
t.start()
q.put(None)
t.join()
```

**TPE014 polling-future-done** - latency, CPU and lost exceptions.

```python
# before
while not all(f.done() for f in futures):
    time.sleep(1)
# after
for f in as_completed(futures, timeout=3600):
    handle(f.result())
```

**TPE015 swallowed-future-exception**.

```python
# before
try:
    rows.append(fut.result())
except Exception:
    pass
# after
try:
    rows.append(fut.result())
except Exception as exc:
    log.warning("task failed", exc_info=exc)
    errors.append(exc)
```

**TPE016 executor-per-call** - per request / per batch / per task pools.

```python
# before
@app.post("/answer")
def answer(q: str):
    with ThreadPoolExecutor(4) as ex:
        return list(ex.map(call_tool, plan(q)))
# after: one executor for the app, created in the lifespan, shut down on stop
def answer(q: str):
    return [f.result(timeout=20) for f in [IO_POOL.submit(call_tool, t) for t in plan(q)]]
```

**TPE017 thread-not-joined**.

```python
# before
threading.Thread(target=warm_cache).start()
# after
t = threading.Thread(target=warm_cache, name="warm-cache")
t.start()
t.join(timeout=60)
```

**TPE018 cpu-bound-thread-pool** - pure-Python arithmetic gains nothing from threads on a GIL build.

```python
# before
with ThreadPoolExecutor(8) as ex:
    scores = list(ex.map(edit_distance_matrix, pairs))
# after
with ProcessPoolExecutor() as ex:
    scores = list(ex.map(edit_distance_matrix, pairs, chunksize=64))
```

Confirm the diagnosis before switching: [python-gil-bottleneck-analyzer](../../python-gil-bottleneck-analyzer/SKILL.md).

**TPE019 contextvar-not-propagated**.

```python
# before
fut = ex.submit(call_llm, prompt)                  # call_llm logs request_id.get() -> "-"
# after
fut = ex.submit(contextvars.copy_context().run, call_llm, prompt)
```

## 4. Seeing what every thread is doing

Name every pool (`thread_name_prefix`) and long-lived thread (`name=`) first; dumps are useless otherwise.

| Tool | Command | Notes |
|------|---------|-------|
| faulthandler on demand | `faulthandler.register(signal.SIGUSR1, all_threads=True)` then `kill -USR1 <pid>` | stdlib, prints every thread's stack to stderr; Unix |
| faulthandler timer | `faulthandler.dump_traceback_later(600, repeat=True)` | Dumps if the job is still running after N seconds |
| py-spy | `py-spy dump --pid <pid>` (add `--locals` for variables) | No code changes; may need `sudo` / `CAP_SYS_PTRACE` |
| In-process | `sys._current_frames()` + `threading.enumerate()` | Build a `/debug/threads` endpoint |
| Watchdog | `python-async-deadlock-debugger/scripts/hang_watchdog.py` | Runs the target and dumps on stall |

```python
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor


def dump_threads() -> str:
    names = {t.ident: t.name for t in threading.enumerate()}
    out = []
    for ident, frame in sys._current_frames().items():
        top = traceback.extract_stack(frame)[-1]
        out.append(f"{names.get(ident, ident)}: {top.name} line {top.lineno}")
    return "\n".join(sorted(out))


def stuck_call() -> None:
    time.sleep(0.2)                                     # e.g. a request without a timeout


with ThreadPoolExecutor(max_workers=2, thread_name_prefix="llm") as ex:
    ex.submit(stuck_call).add_done_callback(lambda f: f.result())
    ex.submit(stuck_call).add_done_callback(lambda f: f.result())
    time.sleep(0.05)
    print("\n".join(line.split(" line ")[0] for line in dump_threads().splitlines() if line.startswith("llm")))
# llm_0: stuck_call
# llm_1: stuck_call
```

Reading a pool dump:
- All `llm_*` threads in `_worker -> work_queue.get`: workers idle; the bottleneck is upstream (producer,
  limiter, main thread).
- All in a socket `recv`/`ssl.read`: waiting on the network; check timeouts and the provider.
- All in `TokenBucket.acquire` / `Event.wait`: the rate limiter is the bottleneck (expected at the limit).
- All in `Future.result` / `wait` inside your task: TPE009 pool exhaustion.
- In `Lock.acquire` on one lock: contention or a lock held across I/O.

## 5. The process will not exit

At interpreter exit Python joins every non-daemon thread, including pool workers, after their queues drain.

```python
import threading


def report_live_threads() -> list:
    """Call at the end of main(): anything listed here will keep the process alive."""
    return sorted(t.name for t in threading.enumerate()
                  if t is not threading.main_thread() and not t.daemon and t.is_alive())


print(report_live_threads())                            # [] when everything was joined/shut down
```

Typical culprits: a `ThreadPoolExecutor` created at module level with work still queued; a background thread
running `while True` without a stop event; a `queue.get()` with no sentinel; an `asyncio` loop thread never
stopped; a third-party SDK's own background threads (telemetry, batch span processors) that need
`client.close()` / `provider.shutdown()`. Diagnosis of the stuck thread is the same as section 4; the
shutdown-hang catalogue is in section 14 of
[threading-and-multiprocessing-deadlocks.md](../../python-async-deadlock-debugger/references/threading-and-multiprocessing-deadlocks.md).

## 6. The pool is slow

Measure where time goes per task: **queue wait** (submitted -> started), **limiter wait**, **call latency**,
**post-processing**. Then:

| Measurement | Meaning | Action |
|-------------|---------|--------|
| Queue wait high, all workers busy in calls | Too few workers for the latency | Raise workers (Little's law) |
| Limiter wait high | You are at the rate limit | Expected; raise the limit with the provider, or cache/batch |
| Call latency rises with workers | Server or DB saturated | Fewer workers, bigger batches |
| Main thread at 100% CPU, workers idle | Producer/consumer in the main thread is the bottleneck (JSON parsing, writing) | Move parsing into tasks or processes |
| One core busy, many threads, little I/O | GIL-bound work in tasks | Processes; see the GIL skill |
| Many new TLS connections | Connection pool smaller than workers | Raise pool size (see the bounding reference) |

Turn on library debug logs briefly: `logging.getLogger("urllib3").setLevel(logging.DEBUG)` shows connection
creation; `logging.getLogger("httpx").setLevel(logging.DEBUG)` shows requests.

## 7. Instrumenting an executor

A subclass that records queue wait and run time per task, plus in-flight count, gives you the numbers for
section 6 and feeds metrics (Prometheus, OpenTelemetry) or logs.

```python
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Dict, List


class InstrumentedExecutor(ThreadPoolExecutor):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._lock = threading.Lock()
        self.in_flight = 0
        self.queue_wait: List[float] = []
        self.run_time: List[float] = []
        self.errors: Dict[str, int] = {}

    def submit(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Future:
        submitted = time.monotonic()

        def timed() -> Any:
            started = time.monotonic()
            with self._lock:
                self.in_flight += 1
                self.queue_wait.append(started - submitted)
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                with self._lock:
                    self.errors[type(exc).__name__] = self.errors.get(type(exc).__name__, 0) + 1
                raise
            finally:
                with self._lock:
                    self.in_flight -= 1
                    self.run_time.append(time.monotonic() - started)

        return super().submit(timed)


def call(i: int) -> int:
    time.sleep(0.01)
    if i % 10 == 0:
        raise TimeoutError("read timeout")
    return i


with InstrumentedExecutor(max_workers=4, thread_name_prefix="api") as ex:
    futures = [ex.submit(call, i) for i in range(40)]
    outcomes = [f.exception() is None for f in futures]
p95_wait = sorted(ex.queue_wait)[int(0.95 * len(ex.queue_wait))]
print(sum(outcomes), ex.errors, f"p95 queue wait > run time: {p95_wait > 0.01}")
# 36 {'TimeoutError': 4} p95 queue wait > run time: True
```

A p95 queue wait far above the run time with idle rate-limit headroom means: add workers. Export
`in_flight`, latency histograms, error counts by type, retries and limiter wait as metrics in long-running
services; log a summary line at the end of batch jobs.
