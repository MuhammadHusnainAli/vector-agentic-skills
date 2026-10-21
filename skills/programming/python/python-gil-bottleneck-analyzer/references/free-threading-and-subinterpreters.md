# Free-Threading and Subinterpreters

Two ways CPython itself now runs Python code on several cores inside one process: the free-threaded build
(no GIL, PEP 703) and sub-interpreters with their own GIL (PEP 684 / PEP 734). Both are young; this file is
deliberately precise about what changed in which release. When a decision depends on a detail, confirm it in
the "What's New" page of the exact version you deploy.

## Contents

1. [Status by version](#1-status-by-version)
2. [Getting and detecting a free-threaded interpreter](#2-getting-and-detecting-a-free-threaded-interpreter)
3. [How the GIL comes back: extensions and PYTHON_GIL](#3-how-the-gil-comes-back-extensions-and-python_gil)
4. [Performance: what to expect](#4-performance-what-to-expect)
5. [Thread safety without the GIL](#5-thread-safety-without-the-gil)
6. [Porting checklist for a library or service](#6-porting-checklist-for-a-library-or-service)
7. [Subinterpreters: concurrent.interpreters (3.14)](#7-subinterpreters-concurrentinterpreters-314)
8. [InterpreterPoolExecutor (3.14)](#8-interpreterpoolexecutor-314)
9. [Threads vs interpreters vs processes](#9-threads-vs-interpreters-vs-processes)
10. [When to choose which](#10-when-to-choose-which)

## 1. Status by version

| Version | Free-threaded build | Subinterpreters |
|---------|---------------------|-----------------|
| 3.12 | not available | PEP 684: a per-interpreter GIL, available only through the C API |
| 3.13 (Oct 2024) | PEP 703 **experimental**: separate build (`--disable-gil`), usually installed as `python3.13t`; specializing adaptive interpreter disabled in this build, so single-threaded code is markedly slower | C API only (a private test module existed) |
| 3.14 (Oct 2025) | PEP 779: **officially supported** ("phase II"), still an optional separate build (`python3.14t`), not the default; specializing interpreter enabled; much smaller single-thread penalty | PEP 734: stdlib `concurrent.interpreters` and `concurrent.futures.InterpreterPoolExecutor` |

"Supported" means the core team commits to it (bugs fixed, documented, in CI); it does **not** mean the
ecosystem is ready or that it is the default. The default `python3.14` still has a GIL. Making free-threading
the default is a future decision (PEP 703's phase III) with no fixed release.

## 2. Getting and detecting a free-threaded interpreter

Ways to install (availability differs by platform; check the docs of your installer):

- python.org installers for Windows and macOS offer an optional free-threaded component (`python3.14t`).
- `uv python install 3.14t` then `uv venv --python 3.14t`.
- `pyenv install 3.14t`; conda-forge provides free-threaded builds; some Linux distributions package it
  separately; or build from source with `./configure --disable-gil`.

Detect at runtime; the build flag and the runtime state are different questions:

```python
import sys
import sysconfig

build_ft = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))   # was it compiled without the GIL?
check = getattr(sys, "_is_gil_enabled", None)                  # 3.13+
gil_now = check() if check else True                           # is the GIL active right now?
print(f"free-threaded build={build_ft} gil_enabled={gil_now} version={sys.version.split()[0]}")
```

`python -VV` prints "free-threading build" on such interpreters. Wheels for them carry a `t` ABI tag
(`cp313t`, `cp314t`); the limited/stable ABI (`abi3`) wheels do not load on free-threaded 3.13/3.14, so
packages need dedicated builds.

## 3. How the GIL comes back: extensions and PYTHON_GIL

On a free-threaded build the GIL starts disabled, but importing a C extension that has **not** declared
free-threading support turns it back on for the whole process and emits a warning like:

```text
RuntimeWarning: The global interpreter lock (GIL) has been enabled to load module 'fastthing', which has not
declared that it can run safely without the GIL. To override this behavior and keep the GIL disabled (at your
own risk), run with PYTHON_GIL=0 or -X gil=0.
```

| Control | Effect |
|---------|--------|
| `PYTHON_GIL=0` / `-X gil=0` | keep the GIL disabled even when such modules load (you own any crash or race) |
| `PYTHON_GIL=1` / `-X gil=1` | force the GIL on (useful to compare, or to run unported code safely) |
| no setting | GIL off until an undeclared extension is imported |

Do not export `PYTHON_GIL=0` globally (Dockerfile, CI env) where GIL builds also run: on a default build it
aborts at startup with `Fatal Python error: config_read_gil: Disabling the GIL is not supported by this build`
(verified on 3.14.4). `sys.flags.gil` reflects the `-X gil` / `PYTHON_GIL` setting.

How extension authors declare support:

| Tool | Declaration |
|------|-------------|
| C API, multi-phase init | module slot `{Py_mod_gil, Py_MOD_GIL_NOT_USED}` |
| C API, single-phase init | `PyUnstable_Module_SetGIL(module, Py_MOD_GIL_NOT_USED)` |
| Cython 3.1+ | directive `# cython: freethreading_compatible = True` |
| PyO3 | `#[pymodule(gil_used = false)]` (recent PyO3 versions) |
| pybind11 | `py::mod_gil_not_used()` in `PYBIND11_MODULE` |

Practical rule: import all your dependencies, *then* check `sys._is_gil_enabled()` and fail loudly in the
service's startup if you depend on parallel threads:

```python
import sys
import warnings


def require_free_threading() -> None:
    check = getattr(sys, "_is_gil_enabled", None)
    if check is None or check():
        warnings.warn("GIL is enabled: CPU-bound threads will not run in parallel", RuntimeWarning, stacklevel=2)


require_free_threading()
```

Run tests with `-W error::RuntimeWarning` to turn the re-enable warning into a failure, and keep a list of the
versions of numpy, pydantic-core, orjson, tokenizers and friends that ship `cp314t` wheels for your platform
(community tracking sites list ecosystem status).

## 4. Performance: what to expect

| Effect | 3.13t | 3.14t |
|--------|-------|-------|
| Single-threaded slowdown vs the GIL build | large (specializer disabled; commonly measured in the tens of percent) | small; the 3.14 What's New cites roughly 5-10% depending on platform and compiler |
| Multi-threaded CPU-bound Python | scales with cores (if no hidden contention) | same, better tuned |
| Memory | higher (different allocator, per-object state) | still somewhat higher |

Hidden serialisation on the free-threaded build:

- Contended per-object locks: many threads appending to *one* list or updating *one* dict serialise on that
  object. Give each thread its own accumulator and merge.
- Reference-count contention on shared objects (mitigated by immortal objects and deferred/biased reference
  counting, but still visible in microbenchmarks).
- Extensions holding their own global locks, or re-enabling the GIL.
- Memory bandwidth: once the GIL is gone, numeric code can hit the same limits as processes.

Always measure on your workload: `scripts/gil_probe.py --target mod:fn` reports whether the interpreter is
free-threaded and whether threads scaled.

```python
import sys
import time
from concurrent.futures import ThreadPoolExecutor


def tokenize_count(n):
    total = 0
    for i in range(n):
        total += len(str(i).split("0"))
    return total


def best_of(fn, repeat=3):
    best = float("inf")
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
    return best


N, WORKERS = 300_000, 4
serial = best_of(lambda: [tokenize_count(N) for _ in range(WORKERS)])
with ThreadPoolExecutor(WORKERS) as ex:
    threaded = best_of(lambda: list(ex.map(tokenize_count, [N] * WORKERS)))
gil = getattr(sys, "_is_gil_enabled", lambda: True)()
print(f"GIL enabled: {gil}; thread speedup {serial / threaded:.2f}x")   # ~1x with the GIL, >2x without
```

## 5. Thread safety without the GIL

The free-threaded build keeps the interpreter itself safe (built-in `dict`, `list`, `set` use internal
per-object locks so a single operation will not corrupt them), but **your invariants are your job**:

| Pattern | GIL build | Free-threaded build | Fix |
|---------|-----------|---------------------|-----|
| `counter += 1` from many threads | racy (rarely observed) | racy (often observed) | `threading.Lock`, or per-thread counters |
| `if key not in cache: cache[key] = load()` | racy | racy, more often | lock, or `dict.setdefault` with a cheap value |
| sharing one iterator/generator between threads | unsafe | unsafe (`ValueError: generator already executing`, or skipped items) | a `queue.Queue` of items |
| mutating a list while another thread iterates | unsafe | unsafe | copy, or lock |
| lazily creating a global client | double creation | double creation | lock + double-checked init, or create at startup |
| module-level caches in C extensions | protected by GIL | the extension must lock | upgrade/pin a declared-safe version |

```python
import threading
from concurrent.futures import ThreadPoolExecutor

lock = threading.Lock()
totals = {"tokens": 0}


def count(doc: str) -> None:
    n = len(doc.split())
    with lock:                          # compound update: always lock, GIL or not
        totals["tokens"] += n


with ThreadPoolExecutor(8) as ex:
    list(ex.map(count, ["a b c"] * 10_000))
print(totals["tokens"])                 # 30000 on every build
```

Other 3.14 free-threaded defaults worth knowing: `sys.flags.thread_inherit_context` is on (new threads start
with a copy of the caller's `contextvars` context) and `sys.flags.context_aware_warnings` is on
(`warnings.catch_warnings` becomes thread-local-safe via a context variable). Both are off by default on the
GIL build.

## 6. Porting checklist for a library or service

1. Install `python3.14t` in a separate venv; install dependencies; note which lack `cp314t` wheels.
2. Import everything, then assert `sys._is_gil_enabled() is False`; run tests with
   `-W error::RuntimeWarning`.
3. Grep for shared mutable state: module-level dicts/lists, singletons, caches, counters, global clients.
   Add locks or make them per-thread (`threading.local`) or immutable.
4. Run the test suite many times with threads (`pytest -p xdist` is processes; you need *threaded* stress tests:
   N threads hammering the same API, see [testing-and-benchmarking.md](testing-and-benchmarking.md)).
5. Benchmark single-threaded and multi-threaded paths on both builds; keep the GIL build if the
   multi-threaded gain does not beat the single-thread loss for your traffic.
6. For C extensions: audit global state, use critical sections (`Py_BEGIN_CRITICAL_SECTION`) where objects are
   mutated, declare `Py_MOD_GIL_NOT_USED`, build `cp314t` wheels (cibuildwheel supports them).

## 7. Subinterpreters: concurrent.interpreters (3.14)

Each interpreter has its own modules, globals and (since 3.12) its own GIL, inside one OS process. Code in
different interpreters runs in parallel when called from different threads.

```python
from concurrent import interpreters

interp = interpreters.create()
interp.prepare_main(limit=5)                       # bind names in the interpreter's __main__
interp.exec("import math; result = [math.factorial(i) for i in range(limit)]; print(result)")

queue = interpreters.create_queue()                # cross-interpreter queue
interp.prepare_main(q=queue)
interp.exec("q.put({'doc_id': 7, 'chunks': 3})")   # non-shareable objects are pickled
print(queue.get())

try:
    interp.exec("raise ValueError('bad chunk')")
except interpreters.ExecutionFailed as err:        # the exception does not cross as itself
    print("failed:", err.excinfo.type.__name__)
interp.close()
```

Verified behaviour on 3.14: `Interpreter.call(fn, *args)` runs a callable and returns its result;
`call_in_thread` runs it in a new thread; `create_queue()` passes shareable objects (None, bool, int, float,
str, bytes, tuples of them, queues, memoryviews) efficiently and pickles other values.

Limits:

- **Extension compatibility.** A C extension must use multi-phase init and declare per-interpreter-GIL support.
  Many popular ones do not yet. numpy 2.3, tried while writing this, failed inside a sub-interpreter with a
  misleading `ImportError` ("you should not try to import numpy from its source directory") whose root cause
  was `RuntimeError: CPU dispatcher tracer already initlized`. Test your imports first.
- **No shared objects.** Everything crosses by copy (pickle or a shareable type); there is no shared heap of
  Python objects as with threads.
- **Startup cost.** Creating an interpreter imports modules again; reuse them (pools) rather than one per task.
- **Young API.** Expect refinements in later releases.

## 8. InterpreterPoolExecutor (3.14)

A `concurrent.futures` executor whose workers are threads, each running its own sub-interpreter. The API matches
`ThreadPoolExecutor`/`ProcessPoolExecutor`; callables and arguments are pickled into the worker interpreter
(module-level functions, importable modules), results pickled back.

```python
import time
from concurrent.futures import InterpreterPoolExecutor


def score(n):                          # module-level, stdlib-only: importable inside the sub-interpreter
    acc = 0
    for i in range(n):
        acc += i % 7
    return acc


if __name__ == "__main__":
    t0 = time.perf_counter()
    with InterpreterPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(score, [500_000] * 4))
    print(len(results), f"{time.perf_counter() - t0:.2f}s")
```

`scripts/gil_probe.py --interpreters` measures it next to threads and processes. On the pure-Python builtin
workload on 3.14 it scales like processes, with less start-up cost; with numpy-dependent targets it reports
the import failure instead.

## 9. Threads vs interpreters vs processes

| Property | Threads (GIL build) | Threads (free-threaded) | InterpreterPoolExecutor | ProcessPoolExecutor |
|----------|--------------------|-------------------------|-------------------------|---------------------|
| Python CPU in parallel | no | yes | yes | yes |
| Shared Python objects | yes | yes (with locks) | no (copy) | no (copy) |
| Extension compatibility | all | must declare FT support | must support sub-interpreters | all |
| Start-up per worker | ~nothing | ~nothing | import cost per interpreter | new process + imports |
| Memory per worker | tiny | tiny | one interpreter's modules | full process |
| Isolation of crashes | none | none | none (same process) | yes |
| Available since | always | 3.13 (exp.), 3.14 (supported) | 3.14 | 3.2 |

## 10. When to choose which

- **Processes** remain the safe default for CPU-bound pure-Python work today: every library works, crashes
  are isolated. Pay attention to pickling and memory ([pool skill](../../python-multiprocessing-pool-designer/SKILL.md)).
- **Free-threaded threads** when you need shared in-memory state (big caches, models in Python objects),
  control the interpreter and all dependencies have `t` wheels, and the workload benefits more than the
  single-thread penalty costs.
- **InterpreterPoolExecutor** for stdlib-heavy or pure-Python tasks where process start-up or memory hurts and
  you can live with copying arguments; not (yet) for numpy/torch-heavy code.
- **None of them** when the hot path can be vectorised or moved to native code that releases the GIL: then
  plain threads on the default build are enough ([escape-hatches.md](escape-hatches.md)).
