# General-Purpose Context Manager Recipes

Stdlib-only recipes that come up in every Python codebase, written so they are
safe on error and correct under the protocol rules in
[protocol-reference.md](protocol-reference.md). AI-specific recipes are in
[ai-engineering-recipes.md](ai-engineering-recipes.md).

## Contents

- [Files and file-like objects](#files-and-file-like-objects)
- [Temporary files and directories](#temporary-files-and-directories)
- [Working directory (pre-3.11 chdir)](#working-directory-pre-311-chdir)
- [Locks and thread safety](#locks-and-thread-safety)
- [Thread and process pools](#thread-and-process-pools)
- [Subprocesses](#subprocesses)
- [Sockets and HTTP sessions](#sockets-and-http-sessions)
- [Attribute, dict and global-state patching](#attribute-dict-and-global-state-patching)
- [Logging level and capture](#logging-level-and-capture)
- [Warnings, decimal precision, numpy error state](#warnings-decimal-precision-numpy-error-state)
- [Signals and timeouts (sync)](#signals-and-timeouts-sync)
- [Timing](#timing)
- [Resource pools (checkout/checkin)](#resource-pools-checkoutcheckin)
- [Indentation / nesting printer](#indentation--nesting-printer)

## Files and file-like objects

```python
with open("prompts.jsonl", encoding="utf-8") as f:          # always pass encoding for text
    prompts = [json.loads(line) for line in f]

from pathlib import Path
text = Path("system_prompt.txt").read_text(encoding="utf-8")  # opens + closes for you

with open("data.bin", "rb") as src, open("data.bak", "wb") as dst:
    shutil.copyfileobj(src, dst)
```

| Leaky | Safe |
|-------|------|
| `data = open(p).read()` | `data = Path(p).read_text(encoding="utf-8")` |
| `json.load(open(p))` | `with open(p) as f: json.load(f)` |
| `f = open(p); ...; f.close()` | `with open(p) as f: ...` |
| `csv.reader(open(p))` | `with open(p, newline="") as f: rows = list(csv.reader(f))` |
| `yaml.safe_load(open(p))` | `with open(p) as f: yaml.safe_load(f)` |

`open(p).read()` closes promptly on CPython (refcounting) but emits
`ResourceWarning` under `-X dev`, leaks on PyPy, and leaks if an exception
traceback keeps the frame alive. Treat it as a bug in library code.

Compressed and archive formats are all context managers:

```python
import gzip, tarfile, zipfile

with gzip.open("corpus.jsonl.gz", "rt", encoding="utf-8") as f:
    for line in f:
        ...

with zipfile.ZipFile("dataset.zip") as zf, zf.open("train.jsonl") as member:
    first = member.readline()

with tarfile.open("model.tar.gz", "r:gz") as tf:
    tf.extractall("weights/", filter="data")   # filter= on 3.12+ (and backports); blocks path traversal
```

## Temporary files and directories

| API | Context manager? | Deleted when |
|-----|------------------|--------------|
| `tempfile.TemporaryFile()` | Yes | Closed (may never have a visible name) |
| `tempfile.NamedTemporaryFile(delete=True)` | Yes | Closed. On Windows cannot be reopened while open; 3.12+ `delete_on_close=False` keeps it until the `with` exits |
| `tempfile.SpooledTemporaryFile(max_size=...)` | Yes | Closed; in memory until `max_size` |
| `tempfile.TemporaryDirectory()` | Yes (yields the path str) | `with` exits / `.cleanup()` |
| `tempfile.mkstemp()` | **No** — returns `(fd, path)` | Never; you must `os.close(fd)` and `os.remove(path)` |
| `tempfile.mkdtemp()` | **No** — returns path | Never; you must `shutil.rmtree(path)` |

```python
import os
import tempfile

# Hand a real file path to a library that insists on a filename (e.g. an audio
# transcription SDK), cross-platform:
with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "clip.wav")
    with open(path, "wb") as f:
        f.write(audio_bytes)
    text = transcribe(path)

# 3.12+: NamedTemporaryFile that can be reopened by name on Windows too
with tempfile.NamedTemporaryFile("wb", suffix=".wav", delete_on_close=False) as f:
    f.write(audio_bytes)
    f.close()
    text = transcribe(f.name)
```

## Working directory (pre-3.11 chdir)

`ctx_tool.py scaffold --recipe cwd` prints this, typed:

```python
import os
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def working_directory(path: str) -> Iterator[str]:
    previous = os.getcwd()
    os.chdir(path)
    try:
        yield path
    finally:
        os.chdir(previous)
```

On 3.11+ use `contextlib.chdir`. Neither is thread-safe.

## Locks and thread safety

```python
import threading

_index_lock = threading.Lock()          # module-level: shared by every caller


def add_to_index(index, vectors, ids) -> None:
    with _index_lock:                   # acquire; release on any exit
        index.add_with_ids(vectors, ids)
```

| Primitive | Re-entrant | Notes |
|-----------|------------|-------|
| `threading.Lock` | No | Nested acquire in the same thread deadlocks |
| `threading.RLock` | Yes | Same thread may re-acquire; must release as many times |
| `threading.Semaphore(n)` | — | n concurrent holders |
| `threading.BoundedSemaphore(n)` | — | Raises `ValueError` on over-release |
| `threading.Condition(lock)` | per lock | `with cond: cond.wait_for(pred)` |

Timeouts — the `with` form cannot take a timeout, so use explicit acquire with
a correct try/finally:

```python
if not _index_lock.acquire(timeout=5):
    raise TimeoutError("index busy")
try:
    index.add(vectors)
finally:
    _index_lock.release()
```

Or wrap it:

```python
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def acquired(lock: threading.Lock, timeout: float) -> Iterator[None]:
    if not lock.acquire(timeout=timeout):
        raise TimeoutError(f"could not acquire lock within {timeout}s")
    try:
        yield
    finally:
        lock.release()
```

Acquire **before** `try`: if acquire is inside the `try` and raises, `finally`
releases a lock you do not hold (`RuntimeError: release unlocked lock`) — or
worse, one another thread holds.

Is my context manager thread-safe? Checklist:

- State stored on `self` in `__enter__` is shared if the same instance is used
  from several threads (common with `ContextDecorator` instances used as
  decorators). Store per-entry state in a local (generator CMs) or
  `threading.local()` / `contextvars.ContextVar`.
- Process-global effects (`os.environ`, `os.chdir`, `sys.stdout`, `signal`,
  `logging` levels, `warnings` filters, `numpy.seterr`, `decimal` context is
  thread-local) are not thread-safe to override.
- On free-threaded builds (3.13t) races that the GIL used to hide become real;
  guard shared state with a lock.

## Thread and process pools

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=16) as pool:        # exit = shutdown(wait=True)
    futures = {pool.submit(fetch_page, url): url for url in urls}
    for fut in as_completed(futures):
        pages[futures[fut]] = fut.result()
```

- Exiting the `with` waits for all submitted work. To abandon queued work on
  error, call `pool.shutdown(wait=False, cancel_futures=True)` (3.9+) in an
  `except` block before re-raising.
- `multiprocessing.Pool.__exit__` calls `terminate()`, not `close()+join()`:
  results not yet collected are lost. Collect results inside the `with`.

```python
from multiprocessing import Pool

with Pool(8) as pool:
    chunks = pool.map(chunk_document, documents)   # map blocks until done: safe
```

## Subprocesses

```python
import subprocess

result = subprocess.run(["git", "status"], capture_output=True, text=True, timeout=30, check=True)
```

`subprocess.run` manages the process for you. Use `Popen` only for streaming,
and then as a context manager (waits and closes pipes on exit):

```python
with subprocess.Popen(
    ["python", "-u", "train.py"], stdout=subprocess.PIPE, text=True, bufsize=1,
) as proc:
    try:
        for line in proc.stdout:
            log_metric_line(line)
    except BaseException:
        proc.kill()                 # don't wait forever for a child we are abandoning
        raise
if proc.returncode:
    raise subprocess.CalledProcessError(proc.returncode, proc.args)
```

## Sockets and HTTP sessions

```python
import socket

with socket.create_connection(("localhost", 6379), timeout=2) as sock:
    sock.sendall(b"PING\r\n")
    reply = sock.recv(64)

import requests

with requests.Session() as s:                     # reuse TCP/TLS connections
    s.headers["Authorization"] = f"Bearer {token}"
    pages = [s.get(u, timeout=10).json() for u in urls]

with requests.get(url, stream=True, timeout=30) as r:   # streamed body must be released
    r.raise_for_status()
    with open(dest, "wb") as f:
        for block in r.iter_content(1 << 20):
            f.write(block)

from urllib.request import urlopen
with urlopen("https://example.com/model-card.json", timeout=10) as resp:
    card = json.load(resp)
```

## Attribute, dict and global-state patching

```python
from unittest import mock

with mock.patch("app.llm.client.complete", return_value="stubbed answer") as fake:
    assert answer("hi") == "stubbed answer"
    fake.assert_called_once()

with mock.patch.object(settings, "max_tokens", 16):
    ...

with mock.patch.dict(PROMPTS, {"system": "You are terse."}):
    ...
```

Patch where the name is **looked up**, not where it is defined
(`app.service.httpx`, not `httpx`).

## Logging level and capture

```python
import logging
from contextlib import contextmanager
from typing import Iterator, List


@contextmanager
def log_level(logger_name: str, level: int) -> Iterator[logging.Logger]:
    logger = logging.getLogger(logger_name)
    old = logger.level
    logger.setLevel(level)
    try:
        yield logger
    finally:
        logger.setLevel(old)


@contextmanager
def captured_logs(logger_name: str = "", level: int = logging.INFO) -> Iterator[List[logging.LogRecord]]:
    records: List[logging.LogRecord] = []

    class _ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _ListHandler(level)
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    try:
        yield records
    finally:
        logger.removeHandler(handler)


with log_level("httpx", logging.WARNING):          # silence per-request INFO lines
    run_batch()
```

## Warnings, decimal precision, numpy error state

```python
import warnings
with warnings.catch_warnings():                       # restores filters on exit (not thread-safe)
    warnings.simplefilter("ignore", category=FutureWarning)
    tokenizer = load_tokenizer()

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    legacy_call()
assert any(issubclass(w.category, DeprecationWarning) for w in caught)

from decimal import Decimal, localcontext
with localcontext() as ctx:                           # thread-local, safe
    ctx.prec = 6
    cost = Decimal(tokens) * Decimal("0.0000006")

import numpy as np
with np.errstate(divide="ignore", invalid="ignore"):
    cosine = dot / (norm_a * norm_b)                  # zero vectors -> nan, no warning
```

3.11+: `warnings.catch_warnings(action="ignore", category=FutureWarning)` does
both steps.

## Signals and timeouts (sync)

Timeout a blocking call in the main thread (POSIX only; not in threads):

```python
import signal
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def time_limit(seconds: float) -> Iterator[None]:
    def _raise(signum, frame):
        raise TimeoutError(f"timed out after {seconds}s")

    previous = signal.signal(signal.SIGALRM, _raise)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
```

For portable timeouts on untrusted code (agent tool execution) run it in a
subprocess with `timeout=`; signals cannot interrupt C extensions that hold
the GIL.

## Timing

`ctx_tool.py scaffold --recipe timer` prints a class that works as both a
`with` block and a decorator. Minimal generator version:

```python
import time
from contextlib import contextmanager
from typing import Dict, Iterator


@contextmanager
def timed(label: str, sink: Dict[str, float]) -> Iterator[None]:
    t0 = time.perf_counter()
    try:
        yield
    finally:
        sink[label] = sink.get(label, 0.0) + time.perf_counter() - t0


timings: Dict[str, float] = {}
with timed("chunk", timings):
    chunks = chunker.split(doc)
with timed("embed", timings):
    vecs = embedder.encode(chunks)
```

## Resource pools (checkout/checkin)

```python
import queue
from contextlib import contextmanager
from typing import Callable, Generic, Iterator, TypeVar

T = TypeVar("T")


class Pool(Generic[T]):
    """Fixed-size pool of expensive objects (e.g. tokenizers, model replicas)."""

    def __init__(self, factory: Callable[[], T], size: int) -> None:
        self._items: "queue.Queue[T]" = queue.Queue()
        for _ in range(size):
            self._items.put(factory())

    @contextmanager
    def checkout(self, timeout: float = 30.0) -> Iterator[T]:
        item = self._items.get(timeout=timeout)     # raises queue.Empty on timeout
        try:
            yield item
        finally:
            self._items.put(item)                   # always returned, even on error


tokenizers = Pool(lambda: load_tokenizer("bpe.json"), size=4)
with tokenizers.checkout() as tok:
    ids = tok.encode(text)
```

If an error may leave the item in a bad state (a broken DB connection), replace
it instead of returning it: catch in an `except`, `put(factory())`, re-raise.

## Indentation / nesting printer

A small example of state that must be restored on every exit path:

```python
from contextlib import contextmanager
from typing import Iterator


class TreePrinter:
    def __init__(self) -> None:
        self.level = 0

    @contextmanager
    def indented(self) -> Iterator[None]:
        self.level += 1
        try:
            yield
        finally:
            self.level -= 1

    def line(self, text: str) -> None:
        print("  " * self.level + text)


p = TreePrinter()
p.line("agent")
with p.indented():
    p.line("tool: search")
    with p.indented():
        p.line("3 results")
p.line("done")
```
