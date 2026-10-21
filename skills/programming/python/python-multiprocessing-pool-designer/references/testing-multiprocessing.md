# Testing Multiprocessing Code

Process-parallel code is hard to test because failures are non-deterministic, child processes outlive
failed tests, and fork-only bugs hide on Linux. The strategy: keep task functions pure and test them
in-process, test the orchestration under spawn with tiny inputs and hard timeouts, and add a few targeted
tests for crashes, Ctrl-C and determinism.

## Contents

- [1. Test pyramid for process pools](#1-test-pyramid-for-process-pools)
- [2. Make workers testable in-process](#2-make-workers-testable-in-process)
- [3. Picklability tests](#3-picklability-tests)
- [4. Orchestration tests under spawn](#4-orchestration-tests-under-spawn)
- [5. Timeouts so tests never hang](#5-timeouts-so-tests-never-hang)
- [6. Testing error paths](#6-testing-error-paths)
- [7. Testing worker crashes](#7-testing-worker-crashes)
- [8. Testing Ctrl-C and shutdown](#8-testing-ctrl-c-and-shutdown)
- [9. Determinism tests](#9-determinism-tests)
- [10. Leak checks: processes, shared memory, file descriptors](#10-leak-checks-processes-shared-memory-file-descriptors)
- [11. Performance tests](#11-performance-tests)
- [12. CI configuration](#12-ci-configuration)

## 1. Test pyramid for process pools

| Layer | What | How | Speed |
|-------|------|-----|-------|
| Unit | Task functions, initializer logic, result merging | Call directly, no processes | ms |
| Contract | Every task callable, argument and result pickles; exceptions round-trip | `pickle.dumps/loads` | ms |
| Orchestration | Pool wiring, ordering, error handling, cleanup | Real pool, spawn, 2 workers, tiny input, timeout | 0.2-2 s |
| Failure | Crash, timeout, Ctrl-C, broken pool recovery | Real processes, injected faults | 1-5 s |
| Static | MP rules | `pool_tool.py check --strict` | ms |
| Performance | Speedup and memory budget | Separate, opt-in benchmark job | minutes |

Design for it: a `run(items, workers=..., executor_factory=...)` function that accepts an executor lets
unit tests pass a `ThreadPoolExecutor` or a synchronous fake, and orchestration tests pass a real spawn
pool.

## 2. Make workers testable in-process

```python
import concurrent.futures as cf
from typing import Callable, Iterable


def chunk_doc(doc: str, size: int = 4) -> list:
    words = doc.split()
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size)]


def ingest(docs: Iterable[str], make_executor: Callable[[], cf.Executor]) -> list:
    with make_executor() as ex:
        return [c for chunks in ex.map(chunk_doc, docs) for c in chunks]


class InlineExecutor(cf.Executor):
    """Runs tasks synchronously in the caller: deterministic, debuggable, no pickling."""

    def submit(self, fn, /, *args, **kwargs):
        fut = cf.Future()
        try:
            fut.set_result(fn(*args, **kwargs))
        except BaseException as exc:
            fut.set_exception(exc)
        return fut


def test_ingest_inline():
    assert ingest(["a b c d e"], InlineExecutor) == ["a b c d", "e"]


test_ingest_inline()
print("ok")   # ok
```

`Executor.map` is implemented on top of `submit`, so the inline executor supports both. In production pass
`lambda: cf.ProcessPoolExecutor(8, mp_context=mp.get_context("spawn"))` (the factory lambda runs in the
parent; only `chunk_doc` crosses the process boundary).

Initializer-based globals: expose a function that sets them so tests can call it directly:
`init_worker(...)` then `encode("text")` in the same process.

## 3. Picklability tests

Catch MP002-style errors and unpicklable exceptions without starting processes:

```python
import functools
import pickle


class ParseError(Exception):
    def __init__(self, doc_id: str, reason: str) -> None:
        super().__init__(doc_id, reason)
        self.doc_id, self.reason = doc_id, reason


def normalize(doc: str, *, lower: bool) -> str:
    return doc.lower() if lower else doc


def roundtrip(obj):
    return pickle.loads(pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL))


def test_task_callable_pickles():
    fn = roundtrip(functools.partial(normalize, lower=True))
    assert fn("ABC") == "abc"


def test_exceptions_pickle():
    err = roundtrip(ParseError("doc-1", "encrypted"))
    assert (err.doc_id, err.reason) == ("doc-1", "encrypted")


def test_payload_is_small():
    args = ("s3://bucket/doc-1.pdf", 1)
    assert len(pickle.dumps(args)) < 1024          # paths, not contents


for t in (test_task_callable_pickles, test_exceptions_pickle, test_payload_is_small):
    t()
print("ok")   # ok
```

Add one parametrized test that round-trips every exception class your workers can raise; a failure here
is a `BrokenProcessPool` in production.

## 4. Orchestration tests under spawn

Run real pools in tests with the spawn context, regardless of platform, so fork-only assumptions fail in CI
on Linux too. Task functions must live in an importable module (not in the test function); pytest test
modules are importable, so module-level helpers in the test file work.

```python
# test_pool_orchestration.py
import concurrent.futures as cf
import multiprocessing as mp

SPAWN = mp.get_context("spawn")


def square(x: int) -> int:
    return x * x


def test_map_preserves_order():
    with cf.ProcessPoolExecutor(2, mp_context=SPAWN) as ex:
        assert list(ex.map(square, range(10), chunksize=3)) == [x * x for x in range(10)]


def test_imap_unordered_returns_everything():
    with SPAWN.Pool(2) as pool:
        assert sorted(pool.imap_unordered(square, range(10), chunksize=2)) == [x * x for x in range(10)]


if __name__ == "__main__":
    test_map_preserves_order()
    test_imap_unordered_returns_everything()
    print("ok")   # ok
```

Keep worker counts at 2: enough to exercise concurrency, cheap on CI runners. Share one pool across tests
with a module-scoped fixture when start-up dominates:

```python
import multiprocessing as mp

import pytest


@pytest.fixture(scope="module")
def pool():
    with mp.get_context("spawn").Pool(2) as p:
        yield p
```

## 5. Timeouts so tests never hang

A deadlocked pool hangs the whole test session. Bound every wait and the test itself:
- Every `get()`, `result()`, `join()`, `Queue.get()` in code under test takes a timeout.
- `pytest-timeout`: `@pytest.mark.timeout(30)` or `timeout = 60` in config, with `timeout_method =
  "thread"` (prints all stacks) - it is a third-party plugin.
- Run the suite under `timeout 600 pytest ...` in CI as the last line of defence.
- `faulthandler.dump_traceback_later(60, exit=True)` in `conftest.py` dumps stacks of a hung session (stdlib).

```python
import faulthandler
import sys

faulthandler.dump_traceback_later(600, exit=True, file=sys.stderr)   # conftest.py: hard ceiling
faulthandler.cancel_dump_traceback_later()                            # (cancelled here so the example exits)
print("armed")   # armed
```

## 6. Testing error paths

```python
import concurrent.futures as cf
import multiprocessing as mp

SPAWN = mp.get_context("spawn")


def parse(doc: str) -> str:
    if doc == "bad":
        raise ValueError("corrupt document: bad")
    return doc.upper()


def test_task_error_propagates_with_worker_traceback():
    with cf.ProcessPoolExecutor(1, mp_context=SPAWN) as ex:
        fut = ex.submit(parse, "bad")
        try:
            fut.result(timeout=30)
        except ValueError as exc:
            assert "corrupt document" in str(exc)
            assert "in parse" in str(exc.__cause__)        # remote traceback text
        else:
            raise AssertionError("expected ValueError")


def test_error_callback_called():
    errors = []
    with SPAWN.Pool(1) as pool:
        r = pool.apply_async(parse, ("bad",), error_callback=errors.append)
        r.wait(timeout=30)
    assert len(errors) == 1 and isinstance(errors[0], ValueError)


if __name__ == "__main__":
    test_task_error_propagates_with_worker_traceback()
    test_error_callback_called()
    print("ok")   # ok
```

With pytest use `pytest.raises(ValueError, match="corrupt document")` instead of the try/else.

## 7. Testing worker crashes

Inject a hard crash (`os._exit`, `os.kill(os.getpid(), signal.SIGKILL)`) and assert the code recovers or
fails loudly, never hangs:

```python
import concurrent.futures as cf
import multiprocessing as mp
import os
from concurrent.futures.process import BrokenProcessPool


def crash_on(x: int) -> int:
    if x == 2:
        os._exit(13)                                   # simulates an OOM kill / segfault
    return x


def test_crash_surfaces_as_broken_pool():
    with cf.ProcessPoolExecutor(2, mp_context=mp.get_context("spawn")) as ex:
        futs = [ex.submit(crash_on, i) for i in range(4)]
        outcomes = []
        for f in futs:
            try:
                outcomes.append(f.result(timeout=30))
            except BrokenProcessPool:
                outcomes.append("broken")
    assert "broken" in outcomes


if __name__ == "__main__":
    test_crash_surfaces_as_broken_pool()
    print("ok")   # ok
```

For `multiprocessing.Pool` code the test asserts the opposite risk: that your wrapper uses
`map_async(...).get(timeout=...)` and raises `multiprocessing.TimeoutError` instead of hanging.

## 8. Testing Ctrl-C and shutdown

Run the program as a subprocess, send SIGINT, and assert it exits promptly with no surviving children.
POSIX only.

```python
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time

PROGRAM = textwrap.dedent("""
    import multiprocessing as mp, signal, sys, time

    def init():
        signal.signal(signal.SIGINT, signal.SIG_IGN)

    def work(x):
        time.sleep(0.2)
        return x

    if __name__ == "__main__":
        pool = mp.get_context("spawn").Pool(2, initializer=init)
        try:
            print("started", flush=True)
            pool.map(work, range(1000))
        except KeyboardInterrupt:
            pool.terminate()
            pool.join()
            sys.exit(130)
""")

if sys.platform != "win32":
    path = os.path.join(tempfile.mkdtemp(), "prog.py")
    with open(path, "w") as fh:
        fh.write(PROGRAM)
    proc = subprocess.Popen([sys.executable, path], stdout=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == "started"
    time.sleep(1.0)                                     # let workers start
    t0 = time.monotonic()
    proc.send_signal(signal.SIGINT)
    code = proc.wait(timeout=30)
    print(code, time.monotonic() - t0 < 10)   # 130 True
```

Also assert no orphans: on Linux, list `/proc/*/stat` entries whose parent pid was the program, or record
worker pids to a file from the initializer and check `os.kill(pid, 0)` raises `ProcessLookupError`.

## 9. Determinism tests

Results must not depend on worker count, chunksize or scheduling:

```python
import hashlib
import multiprocessing as mp
import random


def augment(item: str) -> float:
    seed = int.from_bytes(hashlib.blake2b(item.encode(), digest_size=8).digest(), "little")
    return random.Random(seed).random()


def run(workers: int, chunksize: int) -> list:
    with mp.get_context("spawn").Pool(workers) as pool:
        return pool.map(augment, [f"doc{i}" for i in range(50)], chunksize=chunksize)


if __name__ == "__main__":
    baseline = [augment(f"doc{i}") for i in range(50)]
    assert run(1, 50) == run(2, 1) == run(3, 7) == baseline
    print("deterministic")   # deterministic
```

For unordered APIs (`imap_unordered`, `as_completed`) compare sorted results or dicts keyed by id. Float
sums: compare with a tolerance or reduce in a fixed order.

## 10. Leak checks: processes, shared memory, file descriptors

```python
import multiprocessing as mp
import os


def square(x: int) -> int:
    return x * x


def test_no_leaked_children():
    with mp.get_context("spawn").Pool(2) as pool:
        pool.map(square, range(4))
    assert mp.active_children() == []


def open_fds() -> int:
    return len(os.listdir("/proc/self/fd")) if os.path.isdir("/proc/self/fd") else -1


if __name__ == "__main__":
    before = open_fds()
    for _ in range(3):
        test_no_leaked_children()
    print(mp.active_children(), open_fds() - before <= 2)   # [] True
```

- `multiprocessing.active_children()` also joins finished children, so call it once after cleanup.
- Shared memory: on Linux, compare `os.listdir("/dev/shm")` before and after; every created block must be
  unlinked.
- Run tests with `-W error::ResourceWarning` (unclosed pools emit `ResourceWarning` on 3.8+) and
  `-W error::DeprecationWarning` (fork with threads, 3.12+).

## 11. Performance tests

Keep them out of the unit suite (noisy, slow). An opt-in job:
1. Fixed dataset sample (1-5% of production), warm-up run, then 3 timed runs; report the median.
2. Assert speedup over serial within a band of the planner's prediction
   (`pool_tool.py plan ... --json` gives `estimate.speedup`), e.g. at least 60% of predicted.
3. Record peak RSS of the process tree (`resource.getrusage(RUSAGE_CHILDREN).ru_maxrss` after the pool
   exits gives the largest child, on Linux in KB).
4. Gate releases with `pool_tool.py plan --min-speedup 2` for configurations that must stay worth it.

## 12. CI configuration

- Run the suite once with the default start method and once forcing spawn, e.g. an env var read by your
  factory: `MP_START_METHOD=spawn pytest`.
- Test on 3.9 (baseline), the current production version, and 3.14 (forkserver default on Linux).
- Static gate: `python scripts/pool_tool.py check src/ --strict` (exit 1 on findings, 2 on unparsable
  explicitly named files).
- Bound everything: `timeout 900 pytest -p no:cacheprovider -x`, plus per-test timeouts.
- Containers in CI: raise `/dev/shm` (`--shm-size`) for shared-memory tests and set
  `PYTHON_CPU_COUNT` (3.13+) or pass explicit worker counts so tests do not start 64 workers on a big runner.
