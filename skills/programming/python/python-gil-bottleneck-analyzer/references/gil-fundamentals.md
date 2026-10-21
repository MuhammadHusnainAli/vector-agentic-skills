# GIL Fundamentals

What the Global Interpreter Lock actually serialises, how threads take turns, which code releases it, and the
myths that lead to wrong fixes. Everything here describes the default CPython build unless a section says
"free-threaded"; that build is covered in [free-threading-and-subinterpreters.md](free-threading-and-subinterpreters.md).

## Contents

1. [What the GIL protects](#1-what-the-gil-protects)
2. [How threads take turns: the switch interval](#2-how-threads-take-turns-the-switch-interval)
3. [Who releases the GIL](#3-who-releases-the-gil)
4. [Library-by-library table](#4-library-by-library-table)
5. [Checking a library yourself](#5-checking-a-library-yourself)
6. [The GIL is not a lock for your code](#6-the-gil-is-not-a-lock-for-your-code)
7. [Convoy effect: CPU threads hurt I/O threads](#7-convoy-effect-cpu-threads-hurt-io-threads)
8. [Version history](#8-version-history)
9. [Myths and corrections](#9-myths-and-corrections)

## 1. What the GIL protects

CPython's memory management (reference counts, the allocator, many internal caches) is not thread-safe on its
own. The GIL is one mutex per interpreter that a thread must hold to touch Python objects or run bytecode.
Consequences:

- Only one thread executes Python bytecode at any instant, regardless of core count.
- C code called from Python runs *with* the GIL unless it explicitly releases it
  (`Py_BEGIN_ALLOW_THREADS ... Py_END_ALLOW_THREADS` in C, `with nogil:` in Cython, `allow_threads`/`detach`
  in PyO3, `nogil=True` in numba).
- While a thread is blocked in a system call that released the GIL (socket read, `sleep`, file I/O), other
  threads run Python freely.
- Each *process* has its own interpreter and GIL, so processes run Python in parallel.
- Since 3.12 each *sub-interpreter* may have its own GIL (PEP 684), and 3.14 exposes that in the stdlib
  (`concurrent.interpreters`, `InterpreterPoolExecutor`).

Mental model: the GIL makes threads *concurrent* (interleaved) for Python code and *parallel* only for the
parts that release it.

## 2. How threads take turns: the switch interval

Since Python 3.2 a thread that wants the GIL waits on a condition variable with a timeout equal to the switch
interval. If the holder has not released it by then, the waiter sets a "drop request" flag; the holder checks
the flag between bytecodes (at "eval breaker" points), releases the GIL and the waiter takes it.

```python
import sys

print(sys.getswitchinterval())    # 0.005 seconds by default
sys.setswitchinterval(0.001)      # more responsive I/O threads, more hand-off overhead
sys.setswitchinterval(0.005)      # restore the default
```

What tuning it does and does not do:

| Change | Effect |
|--------|--------|
| Lower (e.g. 1 ms) | I/O and UI threads get the GIL back sooner; CPU throughput drops slightly from more hand-offs |
| Higher (e.g. 50 ms) | Fewer switches for pure CPU threads; latency for other threads rises |
| Any value | Never makes two Python threads run bytecode at the same time |

The hand-off is not free: the dropping thread signals, the OS wakes the waiter, caches are cold. Two CPU-bound
threads on a GIL build typically finish *slightly slower* than running the same work serially. That is why
`gil_probe.py` often reports 0.9x for "threads" on pure-Python work.

Long-running C calls that hold the GIL (a huge `re.sub`, `sorted` on a million items, `json.loads` of a
100 MB string) do not check the drop request until they return, so they can starve other threads for the whole
call regardless of the switch interval.

## 3. Who releases the GIL

Released (other threads run while this happens):

- Blocking I/O in the stdlib: `socket` send/recv/connect/accept, `select`/`poll`/`epoll`, file `read`/`write`
  on `io.FileIO` and buffered files, `os.read`/`os.write`, `subprocess` waits, `time.sleep`, DNS
  (`getaddrinfo`).
- Waiting on synchronisation: `threading.Lock.acquire`, `Event.wait`, `queue.Queue.get`, `Future.result`.
- Hashing buffers larger than 2047 bytes in `hashlib` (OpenSSL-backed and, in recent versions, the built-in
  implementations). Hashing many tiny strings holds the GIL for the Python loop around them.
- `zlib`, `bz2`, `lzma` compression and decompression.
- `sqlite3` while the SQLite engine executes a statement.
- Most numpy computation on numeric dtypes (ufunc inner loops, reductions, copies, sorting, BLAS/LAPACK).
- Most torch / onnxruntime / TensorFlow operator kernels, CUDA synchronisation, and model inference calls.
- Rust extensions that call `allow_threads` (`detach` in newer PyO3), e.g. HF `tokenizers` batch encoding,
  `polars` query execution.
- Pillow and OpenCV for many decode/resize operations.

Held (threads serialise):

- All Python bytecode: loops, comprehensions, function calls, attribute access, f-strings.
- Built-ins that operate on Python objects: `sorted`, `sum`, `min`, `max`, `len`, `str` methods, dict/list/set
  operations, `isinstance`.
- `re` (the stdlib engine does not release the GIL), `json` and `orjson` (they build Python objects),
  `pickle`, `marshal`, `csv`, `struct`, `ast`, `compile`/`exec`.
- numpy with `dtype=object`, conversions between Python lists and arrays (`np.array(list_of_lists)`,
  `.tolist()`), and small-array operations dominated by Python-level overhead.
- pydantic-core validation, most C helpers that create many Python objects.

## 4. Library-by-library table

| Library / call | GIL | Notes |
|----------------|-----|-------|
| `requests`, `httpx` (sync) | released while waiting on the socket | threads fine; asyncio for thousands of calls |
| `httpx.AsyncClient`, `aiohttp` | n/a (event loop) | one thread; CPU in callbacks blocks the loop |
| `hashlib.sha256(big_bytes)` | released (> 2047 bytes) | threads scale for big buffers |
| `zlib.compress`, `gzip` | released in the C part | `gzip.open` line iteration is Python and holds it |
| `re.sub`, `re.findall` | held | third-party `regex` can release with `concurrent=True` |
| `json.loads`, `orjson.loads`, `msgspec.json.decode` | held | faster libraries help; threads do not |
| `pickle.dumps` / `loads` | held | the hidden cost of process pools |
| numpy ufuncs, `@`, `np.dot`, `np.sort` on float arrays | released | BLAS spawns its own threads too |
| numpy object arrays, `np.vectorize` | held | `np.vectorize` is a Python loop |
| pandas column arithmetic | released inside numpy | `apply(axis=1)`, `iterrows` hold it |
| polars expressions | released, parallel internally | don't wrap in more threads |
| torch ops, `model(x)` | released inside kernels | intra-op threads: `torch.set_num_threads` |
| HF `tokenizers` `encode_batch` | released, rayon-parallel | `TOKENIZERS_PARALLELISM` controls it |
| HF slow (Python) tokenizers | held | use the fast tokenizer or processes |
| `sentence-transformers.encode` | mostly released (torch) | batch size matters more than threads |
| `lxml` parse | partly released for parsing from files/bytes | element-tree walking holds it |
| `PIL.Image.resize`, decode | released in most operations | good thread-pool candidate |
| `sqlite3` execute | released while the engine runs | one connection per thread |
| `time.sleep`, `select`, `socket` | released | the classic I/O-bound case |

Treat this as a starting hypothesis. Library versions change; verify (next section).

## 5. Checking a library yourself

Three quick ways, from cheapest to most precise:

1. **Probe it**: wrap one call in a function and run `python scripts/gil_probe.py --target mymod:fn`. If
   threads give ≈ Nx with CPU/wall ≈ N, the call releases the GIL.
2. **Sample it**: `py-spy record --gil -o gil.svg -- python bench.py` records only samples where a thread holds
   the GIL. If the call disappears from the `--gil` flame graph but dominates the normal one, it releases it.
3. **Read the source**: search for `Py_BEGIN_ALLOW_THREADS` (C), `with nogil` (Cython), `allow_threads` or
   `detach` (PyO3), `nogil=True` (numba).

A self-contained check with threads (prints the speedup; > 1.5x on 4 threads means the GIL is released):

```python
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor

BUF = bytes(range(256)) * 4096          # 1 MiB


def hash_many(_):
    for _ in range(40):
        hashlib.sha256(BUF).digest()


def timed(fn):
    t0 = time.perf_counter()
    fn()
    return time.perf_counter() - t0


serial = timed(lambda: [hash_many(i) for i in range(4)])
with ThreadPoolExecutor(4) as ex:
    threaded = timed(lambda: list(ex.map(hash_many, range(4))))
print(f"thread speedup: {serial / threaded:.1f}x")
```

## 6. The GIL is not a lock for your code

The GIL guarantees that the interpreter's internals stay consistent; it does not make *your* multi-step
operations atomic. A thread can be switched out between any two bytecodes.

```python
import dis


def bump(counter):
    counter["n"] += 1


dis.dis(bump)   # BINARY_SUBSCR / BINARY_OP / STORE_SUBSCR: a switch can happen between them
```

| Operation | Safe without a lock on the GIL build? |
|-----------|----------------------------------------|
| `lst.append(x)`, `dict[k] = v`, `deque.popleft()` (single C call) | yes, in practice (do not rely on it across implementations) |
| `x += 1` on a shared int / dict value | no (read-modify-write) |
| `if k not in d: d[k] = make()` | no (check-then-act) |
| iterating a dict while another thread inserts | no (`RuntimeError: dictionary changed size during iteration`) |
| lazy singletons (`if _client is None: _client = Client()`) | no (two clients get built) |

Use `threading.Lock`, `queue.Queue`, or per-thread state. Code that is "correct because of the GIL" is the code
that breaks first on the free-threaded build.

## 7. Convoy effect: CPU threads hurt I/O threads

When one thread is CPU-bound and another does I/O, every time the I/O thread's syscall completes it must
re-acquire the GIL, and may wait up to one switch interval for the CPU thread to drop it. With many short I/O
operations (a socket read per message), throughput collapses: each read pays up to 5 ms of waiting.

Symptoms: an asyncio or threaded server whose p99 latency jumps when a background CPU task runs, py-spy
`--native` stacks ending in `take_gil` / `PyEval_RestoreThread`, `profile_classify.py` verdict
`GIL-CONTENDED`.

Fixes, best first: move the CPU work to a process (`run_in_executor(process_pool, ...)`); make the CPU work
release the GIL (numpy, numba `nogil=True`); lower the switch interval as a stop-gap; on 3.14t, test the
free-threaded build.

## 8. Version history

| Version | Change relevant to the GIL |
|---------|---------------------------|
| 3.2 | "New GIL": time-based switching (`sys.setswitchinterval`), replaces the bytecode-count `sys.setcheckinterval` (removed in 3.9) |
| 3.7 | GIL always created at startup (earlier versions created it lazily when the first thread started) |
| 3.8 | `ThreadPoolExecutor` default workers `min(32, os.cpu_count() + 4)` |
| 3.9 | `sys.setcheckinterval`/`getcheckinterval` removed |
| 3.12 | PEP 684 per-interpreter GIL (C API); PEP 683 immortal objects; PEP 669 `sys.monitoring`; `-X perf` for Linux perf |
| 3.13 | PEP 703 free-threaded build (experimental, `python3.13t`), `sys._is_gil_enabled()`, `PYTHON_GIL`/`-X gil`; `os.process_cpu_count()`; `PYTHON_CPU_COUNT`/`-X cpu_count`; `-X perf_jit` |
| 3.14 | PEP 779: free-threaded build officially supported (still optional); PEP 734 `concurrent.interpreters`; `concurrent.futures.InterpreterPoolExecutor`; `forkserver` default start method on Linux/POSIX except macOS |

If a detail matters for a release decision, check the "What's New" page for the exact version you run.

## 9. Myths and corrections

| Myth | Reality |
|------|---------|
| "Python can't use multiple cores" | Processes, GIL-releasing native code, sub-interpreters and the free-threaded build all can |
| "Threads are useless in Python" | They are excellent for I/O and for native work that releases the GIL |
| "asyncio gets around the GIL" | asyncio is one thread; it overlaps waiting, never computation |
| "numpy is always parallel" | Only BLAS-backed ops (matmul, dot, linalg) use several cores by default; ufuncs are single-threaded but release the GIL, so *you* can thread them |
| "The GIL makes my code thread-safe" | Only single C-level operations are atomic; compound updates race |
| "Lowering the switch interval makes threads faster" | It shifts latency vs throughput; never adds parallelism |
| "Processes are always faster for CPU work" | Not when per-item work is < ~1 ms or arguments are large: pickling and IPC dominate |
| "Free-threaded Python is a drop-in speedup" | Single-threaded code is slower on it; it only pays when you run CPU work in threads and every extension supports it |
| "C extensions release the GIL" | Only where the author wrote it; `re`, `json`, `pickle` do not |
