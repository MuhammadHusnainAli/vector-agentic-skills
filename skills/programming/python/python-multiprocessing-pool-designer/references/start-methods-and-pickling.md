# Start Methods and Pickling

How a worker process comes into existence decides what it inherits, what must be pickled, what is safe and
how long it takes. Get this right and most "works on my Linux box, fails on macOS / in CI / on 3.14" bugs
disappear.

## Contents

- [1. The three start methods](#1-the-three-start-methods)
- [2. Platform defaults by version](#2-platform-defaults-by-version)
- [3. The main guard and why spawn needs it](#3-the-main-guard-and-why-spawn-needs-it)
- [4. set_start_method vs get_context](#4-set_start_method-vs-get_context)
- [5. Fork safety](#5-fork-safety)
- [6. forkserver in practice](#6-forkserver-in-practice)
- [7. What pickles and what does not](#7-what-pickles-and-what-does-not)
- [8. Fixing unpicklable callables](#8-fixing-unpicklable-callables)
- [9. Exceptions must pickle too](#9-exceptions-must-pickle-too)
- [10. cloudpickle via joblib / loky](#10-cloudpickle-via-joblib--loky)
- [11. Notebooks and interactive sessions](#11-notebooks-and-interactive-sessions)
- [12. Checklist](#12-checklist)

## 1. The three start methods

| | fork | spawn | forkserver |
|-|------|-------|------------|
| How | `os.fork()` of the parent | Fresh interpreter runs `-c "from multiprocessing.spawn import spawn_main; ..."` | A single-threaded server process is started once; each worker is forked from it |
| Child inherits | Entire parent memory (copy-on-write), open fds, locks in their current state, only the calling thread | Nothing but the pickled process object; re-imports `__main__` as `__mp_main__` | Memory of the server (modules from `set_forkserver_preload`) |
| Per-worker start | ~1-5 ms | 50-500 ms+ (interpreter + your imports) | ~1-5 ms after server start-up |
| Target function and args | Not pickled for `Process` (inherited) | Pickled | Pickled |
| Safe with threads, CUDA, gRPC, open clients | No | Yes | Yes |
| Platforms | POSIX only | All | POSIX (not on Windows) |

Pool tasks are always pickled, whatever the start method: the task queue is a pipe. Only `Process(target=...,
args=...)` and pool `initargs` benefit from fork's inheritance.

## 2. Platform defaults by version

| Platform | <= 3.7 | 3.8 - 3.13 | 3.14+ |
|----------|--------|------------|-------|
| Linux | fork | fork | **forkserver** |
| Other POSIX (BSD) | fork | fork | forkserver |
| macOS | fork | **spawn** (fork is unsafe with system frameworks) | spawn |
| Windows | spawn | spawn | spawn |

Consequences:
- Code that silently relied on fork (lambdas as `Process` targets, globals set before `Process.start()`,
  module-level pools without a guard) breaks when moved to macOS, Windows or Python 3.14 on Linux.
- `ProcessPoolExecutor(max_tasks_per_child=n)` without `mp_context` uses spawn on every platform (3.11+).
- Check at runtime: `multiprocessing.get_start_method()`; list available ones: `get_all_start_methods()`.

## 3. The main guard and why spawn needs it

spawn and forkserver children import your main module to find the task functions. Everything at module
level runs again in each child. If that includes creating a pool, every child tries to create its own pool
before it has finished bootstrapping:

```text
RuntimeError:
        An attempt has been made to start a new process before the
        current process has finished its bootstrapping phase.
        ...
        if __name__ == '__main__':
            freeze_support()
```

With `multiprocessing.Pool` the parent then keeps replacing the dying workers forever: the program prints
the error in a loop and never finishes (verified on 3.11 and 3.14). If the module also calls
`set_start_method()` at top level, the children fail earlier with `RuntimeError: context has already been
set`.

Correct shape: definitions at module level, work behind the guard.

```python
import multiprocessing as mp

CONFIG = {"chunk_size": 512}          # cheap constants at module level are fine


def chunk(text: str) -> list:
    size = CONFIG["chunk_size"]
    return [text[i:i + size] for i in range(0, len(text), size)]


def main() -> None:
    docs = ["x" * 2000, "y" * 700]
    with mp.get_context("spawn").Pool(2) as pool:
        print([len(c) for c in pool.map(chunk, docs)])   # [4, 2]


if __name__ == "__main__":
    main()
```

Rules:
- No pool, process start, model loading, network calls or heavy file reads at import time. Children
  re-import the module: heavy module-level work is paid once per worker (and can recurse).
- Console entry points (`[project.scripts]`) call `main()` from a wrapper module, which is fine.
- `multiprocessing.freeze_support()` is only needed for frozen Windows executables (PyInstaller); it is a
  no-op elsewhere.
- Under pytest, test modules are imported as normal modules (not `__main__`), so pools inside test functions
  work without a guard.

## 4. set_start_method vs get_context

| | `set_start_method("spawn")` | `get_context("spawn")` |
|-|----------------------------|------------------------|
| Scope | Global default for the whole program | Local object |
| Calls allowed | Once (second call: `RuntimeError: context has already been set`, unless `force=True`) | Any number |
| Libraries | Never | Yes |
| Where | Inside `if __name__ == "__main__":` before any process | Anywhere |

```python
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor


def square(x: int) -> int:
    return x * x


if __name__ == "__main__":
    spawn = mp.get_context("spawn")
    with spawn.Pool(2) as pool:
        a = pool.map(square, range(5))
    with ProcessPoolExecutor(max_workers=2, mp_context=spawn) as ex:
        b = list(ex.map(square, range(5)))
    print(a == b)   # True; the global default start method was never set to spawn
```

`torch.multiprocessing` wraps `multiprocessing` with tensor-sharing reducers; use
`torch.multiprocessing.get_context("spawn")` the same way.

## 5. Fork safety

fork duplicates one thread and all memory. Everything another thread was doing at that instant is frozen
in the child:

| Inherited state | What goes wrong in the child | Mitigation |
|-----------------|------------------------------|-----------|
| A lock held by another thread (logging handler, `queue.Queue`, import lock, malloc arena) | First use deadlocks forever | spawn / forkserver; fork before starting threads |
| CUDA context (`torch.cuda.is_available()` with init, any tensor on GPU) | `RuntimeError: Cannot re-initialize CUDA in forked subprocess` | spawn; do not touch CUDA in the parent before starting workers |
| OpenMP / MKL / OpenBLAS thread pools | Hangs or single-threaded children (GNU OpenMP is not fork-safe after use) | spawn, or fork before first BLAS call; set thread env vars |
| HF `tokenizers` Rust thread pool | Warning "The current process just got forked, after parallelism has already been used. Disabling parallelism" | `TOKENIZERS_PARALLELISM=false`, or spawn |
| gRPC / HTTP/2 clients, DB connections, Kafka producers | Shared sockets, corrupted streams, hangs | Create clients inside the worker (initializer) |
| Open files with buffered writes | Data written twice (both buffers flushed) | Flush before fork, or open in the worker |
| Random state (`random`, numpy global RNG) | All workers produce the same "random" numbers | Seed per task (see the AI reference) |
| `asyncio` event loop | The child has a copy of a running loop it must not use | Never fork from inside a running loop; spawn |

Python 3.12+ emits `DeprecationWarning: This process (pid=...) is multi-threaded, use of fork() may lead to
deadlocks in the child.` Treat it as an error in CI: `python -W error::DeprecationWarning`.

When fork is still the right call (Linux, no threads, no CUDA): sharing a large read-only structure loaded
in the parent without pickling it. See copy-on-write and `gc.freeze()` in
[sharing-data-between-processes.md](sharing-data-between-processes.md).

`os.register_at_fork(before=..., after_in_child=..., after_in_parent=...)` (3.7) lets a library reset its
state in children (reopen clients, reseed). Use it in libraries you own instead of documenting "do not
fork".

## 6. forkserver in practice

- The server starts on first use and imports the modules in `set_forkserver_preload([...])`, then forks a
  worker for each request. Preload heavy pure-Python imports (your package, `numpy`) to make worker start
  cheap; do not preload anything that starts threads or initializes CUDA.
- The main module is still re-imported in the worker (same guard rule as spawn) and task functions and
  `initargs` are pickled.
- Arguments to `Process` are pickled, exactly like spawn: code written for spawn works unchanged.

```python
import multiprocessing as mp


def work(x: int) -> int:
    return x + 1


if __name__ == "__main__":
    if "forkserver" in mp.get_all_start_methods():
        ctx = mp.get_context("forkserver")
        ctx.set_forkserver_preload(["json"])      # modules imported once in the server
    else:
        ctx = mp.get_context("spawn")             # Windows
    with ctx.Pool(2) as pool:
        print(pool.map(work, [1, 2, 3]))          # [2, 3, 4]
```

## 7. What pickles and what does not

Pickle stores functions and classes **by reference** (`module.qualname`) and instances **by value** (class
reference + state). The child must import the same module and find the same name.

| Object | Pickles? | Notes |
|--------|----------|-------|
| Module-level function / class | Yes | By name; the child imports the module |
| `functools.partial(module_func, ...)` | Yes | If its args pickle |
| Built-ins (`len`, `str.upper`), `operator.itemgetter` | Yes | |
| Bound method `obj.method` | Yes (Py3) | Pickles `obj` by value each time |
| `staticmethod` / `classmethod` accessed via class | Yes | By qualified name |
| `lambda` | No | `PicklingError: ... it's not found as __main__.<lambda>` |
| Nested function / closure | No | `Can't pickle local object 'outer.<locals>.inner'` |
| Generator, coroutine | No | |
| Open file, socket, `sqlite3.Connection`, HTTP client | No | `TypeError: cannot pickle '_io.TextIOWrapper' object` |
| `threading.Lock`, `Condition` | No | Use `multiprocessing` / `Manager` primitives |
| `multiprocessing.Queue`, `Lock`, `Value` | Only by inheritance | Pass via `Process(args=)` or pool `initargs`; Manager proxies pickle |
| `Pool`, executor | No | `NotImplementedError: pool objects cannot be passed between processes or pickled` |
| numpy arrays, pandas frames | Yes | Copied; large ones cost pickling time and memory |
| torch tensors | Yes | `torch.multiprocessing` shares CPU tensors via shared memory |
| Dataclasses, Pydantic models | Yes | If defined at module level |
| Objects of a class defined in `__main__` | Yes with spawn | The child re-imports `__main__` as `__mp_main__` |

Check before you ship: `pickle.dumps(obj)` in a unit test, and measure size with `len(pickle.dumps(obj,
protocol=pickle.HIGHEST_PROTOCOL))`.

## 8. Fixing unpicklable callables

```python
import functools
import multiprocessing as mp


# BEFORE (fails): pool.map(lambda d: normalize(d, lower=True), docs)
# BEFORE (fails): def run(): def clean(d): ...; pool.map(clean, docs)

def normalize(doc: str, *, lower: bool) -> str:          # module level
    doc = " ".join(doc.split())
    return doc.lower() if lower else doc


class Chunker:
    def __init__(self, size: int) -> None:
        self.size = size

    def __call__(self, text: str) -> list:               # a picklable callable object
        return [text[i:i + self.size] for i in range(0, len(text), self.size)]


if __name__ == "__main__":
    docs = ["  Hello   World ", "RAG  Pipeline"]
    with mp.get_context("spawn").Pool(2) as pool:
        print(pool.map(functools.partial(normalize, lower=True), docs))   # ['hello world', 'rag pipeline']
        print(pool.map(Chunker(4), ["abcdefgh", "xyz"]))                  # [['abcd', 'efgh'], ['xyz']]
```

Patterns:
- **Parameters:** `functools.partial(module_func, key=value)` or a small callable class instance with only
  plain attributes.
- **Methods:** move the logic to a module-level function that takes the data it needs; keep heavy members
  (model, client) in worker globals set by the initializer instead of on `self`.
- **Instance holds a pool or client:** implement `__getstate__` to drop them, or (better) do not send the
  instance at all.
- **Classes defined in a notebook:** move them to a `.py` module next to the notebook and import them.

## 9. Exceptions must pickle too

A task exception is pickled in the worker and unpickled in the parent. Unpickling calls
`cls(*exc.args)`. If `__init__` takes different parameters than what ended up in `args`, unpickling
fails:

| Pool | Observed result (3.11 and 3.14) |
|------|----------------------------------|
| `ProcessPoolExecutor` | `BrokenProcessPool: A process in the process pool was terminated abruptly...` for every pending future |
| `multiprocessing.Pool` | `TypeError: ParseError.__init__() missing 1 required positional argument` in the result-handler thread; `get()` never returns |

Fix by passing every constructor argument to `super().__init__` (so `args` round-trips) or defining
`__reduce__`:

```python
import multiprocessing as mp
import pickle


class ParseError(Exception):
    def __init__(self, doc_id: str, reason: str) -> None:
        super().__init__(doc_id, reason)         # args == (doc_id, reason): round-trips through pickle
        self.doc_id, self.reason = doc_id, reason

    def __str__(self) -> str:
        return f"{self.doc_id}: {self.reason}"


class FetchError(Exception):
    def __init__(self, url: str, *, status: int) -> None:   # keyword-only: needs __reduce__
        super().__init__(f"{url} -> {status}")
        self.url, self.status = url, status

    def __reduce__(self):
        return (_rebuild_fetch_error, (self.url, self.status))


def _rebuild_fetch_error(url: str, status: int) -> "FetchError":
    return FetchError(url, status=status)


def parse(doc_id: str) -> str:
    raise ParseError(doc_id, "encrypted pdf")


if __name__ == "__main__":
    assert str(pickle.loads(pickle.dumps(FetchError("u", status=429)))) == "u -> 429"
    with mp.get_context("spawn").Pool(1) as pool:
        try:
            pool.apply(parse, ("doc-7",))
        except ParseError as err:
            print(err, err.doc_id)               # doc-7: encrypted pdf doc-7
```

Third-party exceptions (HTTP clients, DB drivers) sometimes do not pickle. Catch them in the worker and
re-raise your own picklable error, or return an error record instead of raising.

## 10. cloudpickle via joblib / loky

`cloudpickle` serializes lambdas, closures and interactively defined functions by value. You get it by
using `joblib` (its default `loky` backend) or `loky.get_reusable_executor()` directly; installing
`cloudpickle` alone does not change the stdlib pools.

```python
# pip install joblib
from joblib import Parallel, delayed

threshold = 0.5
scores = Parallel(n_jobs=4)(delayed(lambda s: s > threshold)(s) for s in [0.2, 0.7, 0.9])
# [False, True, True]
```

Costs: cloudpickle is slower than pickle for functions and ships the closure state with every task; large
captured objects are copied each time. joblib automatically memory-maps large numpy arguments (above
`max_nbytes`, default `"1M"`) to avoid copying them.

## 11. Notebooks and interactive sessions

- With spawn/forkserver (macOS, Windows, Linux 3.14+), functions defined in a notebook cell live in
  `__main__`, which the child cannot import: `AttributeError: Can't get attribute 'f' on <module
  '__main__' ...>`. Put task functions in a module and import them, or use joblib.
- With fork (Linux <= 3.13) notebook functions work, which is why notebooks "work on Linux" and break
  elsewhere or after upgrading.
- Interrupting a cell does not always stop workers: use a context manager and restart the kernel if
  orphans remain (`ps -ef | grep multiprocessing`).

## 12. Checklist

- [ ] Every task function, initializer and `Process` target is defined at module level (MP002)
- [ ] All work behind `if __name__ == "__main__":` (MP001)
- [ ] Start method chosen with `get_context`, not a library-level `set_start_method` (MP007)
- [ ] No fork with threads, CUDA, gRPC or open clients (MP008, MP015, MP017)
- [ ] Clients, models and file handles opened inside the worker
- [ ] Custom exceptions round-trip through `pickle.loads(pickle.dumps(e))`
- [ ] Code tested under spawn even when production uses fork
