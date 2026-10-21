# Sharing Data Between Processes

Processes do not share Python objects. Every byte a worker needs either travels through pickling (copy per
task), is inherited at fork (copy-on-write), or lives in memory both sides map (shared memory, memory-mapped
files). Choosing the right one is usually the difference between a 7x and a 0.7x speedup.

## Contents

- [1. Decision table](#1-decision-table)
- [2. Send less: paths, ids and offsets](#2-send-less-paths-ids-and-offsets)
- [3. Per-worker state via initializer](#3-per-worker-state-via-initializer)
- [4. Copy-on-write with fork and gc.freeze](#4-copy-on-write-with-fork-and-gcfreeze)
- [5. multiprocessing.shared_memory](#5-multiprocessingshared_memory)
- [6. numpy arrays over shared memory](#6-numpy-arrays-over-shared-memory)
- [7. SharedMemoryManager](#7-sharedmemorymanager)
- [8. Memory-mapped files and numpy memmap](#8-memory-mapped-files-and-numpy-memmap)
- [9. Arrow and Parquet](#9-arrow-and-parquet)
- [10. Manager proxies](#10-manager-proxies)
- [11. Queue and Pipe](#11-queue-and-pipe)
- [12. Value, Array and locks](#12-value-array-and-locks)
- [13. Returning results without the parent bottleneck](#13-returning-results-without-the-parent-bottleneck)

## 1. Decision table

| Data | Size | Read/write | Best mechanism |
|------|------|-----------|----------------|
| Config, small lookup tables | < 1 MB | read | Task args or `initargs` |
| Model, tokenizer, vocabulary | MBs-GBs | read | Load in the initializer (spawn) or before fork (COW) |
| Large numpy array (embeddings matrix, image batch) | > 10 MB | read, or disjoint writes | `shared_memory` + `np.ndarray(buffer=...)` |
| Dataset on disk | any | read | Pass paths/offsets; `np.memmap`, Arrow/Parquet memory map |
| Output arrays filled by workers | large | disjoint writes | Preallocated shared memory, each task writes its own slice |
| Progress counters, flags | tiny | read/write | `Value` with lock, `Event`, or results counted in the parent |
| Shared mutable dict | small, low rate | read/write | `Manager().dict()` (slow: one IPC per op) |
| Stream between stages | any | produce/consume | `Queue` (bounded), `Pipe` for 1:1 |
| Tensors (torch) | large | read/write | `torch.multiprocessing` (shares CPU tensors via shared memory) |

## 2. Send less: paths, ids and offsets

The cheapest data is the data you do not send. The parent pickles every argument and unpickles every
result on its own (the serial bottleneck in the sizing reference).

```python
import os
import tempfile
from concurrent.futures import ProcessPoolExecutor


def count_lines(path: str) -> tuple:
    with open(path, encoding="utf-8") as fh:
        return path, sum(1 for _ in fh)


if __name__ == "__main__":
    tmp = tempfile.mkdtemp()
    paths = []
    for i in range(20):
        p = os.path.join(tmp, f"doc{i}.txt")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("line\n" * (i + 1))
        paths.append(p)
    with ProcessPoolExecutor(max_workers=4) as ex:              # 20 short strings travel, not 20 files
        counts = dict(ex.map(count_lines, paths, chunksize=5))
    print(sum(counts.values()))   # 210
```

For one big file, send `(path, start_offset, end_offset)` byte ranges aligned to line boundaries and let
each worker `seek()` and read its shard.

## 3. Per-worker state via initializer

```python
import multiprocessing as mp

_lexicon = None


def init(words: list) -> None:
    global _lexicon
    _lexicon = frozenset(words)           # built once per worker, reused by every task


def known_ratio(text: str) -> float:
    toks = text.split()
    return sum(t in _lexicon for t in toks) / max(1, len(toks))


if __name__ == "__main__":
    words = ["rag", "vector", "chunk", "embed"]
    with mp.get_context("spawn").Pool(2, initializer=init, initargs=(words,)) as pool:
        print(pool.map(known_ratio, ["rag vector db", "hello world"]))   # [0.666..., 0.0]
```

`initargs` are pickled once per worker (spawn/forkserver) or inherited (fork), not once per task. Prefer
passing a path and loading in the initializer when the object is large: N workers reading a file in
parallel beats the parent pickling N copies.

## 4. Copy-on-write with fork and gc.freeze

With fork, pages of the parent are shared until someone writes to them. Python writes to objects even when
you only read them:
- every reference taken increments `ob_refcnt` in the object header, dirtying its page;
- the cyclic garbage collector writes `gc` header fields while traversing containers.

A 2 GB dict of Python strings loaded before forking therefore becomes 2 GB per worker within minutes.

Mitigations, best first:
1. **Store the data outside Python objects:** numpy arrays, `bytes`, `array.array`, Arrow buffers. Reading
   elements does not touch the buffer's pages (only the one array header). This alone fixes most cases.
2. **`gc.freeze()` before forking (3.7):** moves all current objects to a permanent generation that the
   collector ignores, avoiding GC-induced writes. Refcount writes still happen. Pair with `gc.disable()` in
   the parent until the fork, and expect partial, not total, savings for object-heavy structures.
3. **Immortal objects (3.12, PEP 683):** interpreter singletons (`None`, small ints, interned strings) no
   longer have refcount writes; your own objects still do.

```python
import gc
import multiprocessing as mp
import sys

BIG = None


def lookup(i: int) -> int:
    return BIG[i]                      # inherited via fork; never pickled


if __name__ == "__main__":
    if sys.platform.startswith("linux"):
        BIG = list(range(1_000_000))   # loaded in the parent before forking
        gc.disable()
        gc.freeze()                     # keep GC from dirtying the inherited pages
        with mp.get_context("fork").Pool(2) as pool:
            print(pool.map(lookup, [10, 999_999]))   # [10, 999999]
        gc.unfreeze()
        gc.enable()
```

Never use this pattern after threads were started or CUDA was initialised (see the start-methods
reference); prefer shared memory for anything that must also work on macOS, Windows or Linux 3.14+ defaults.
Measure with PSS, not RSS: `grep -E '^(Rss|Pss)' /proc/<pid>/smaps_rollup`.

## 5. multiprocessing.shared_memory

`SharedMemory(name=None, create=False, size=0)` (3.8; `track=` keyword 3.13) maps a named block of memory
into any process that opens it by name. You own its lifecycle:

| Call | Who | Effect |
|------|-----|--------|
| `SharedMemory(create=True, size=n)` | creator | Allocates the block, random name in `.name` |
| `SharedMemory(name=...)` | users | Attaches to an existing block |
| `shm.close()` | every process, when done | Unmaps it in this process |
| `shm.unlink()` | exactly one process (creator), once | Destroys the block (POSIX) |

- Forgetting `unlink()` leaks `/dev/shm` space until reboot; the resource tracker prints `UserWarning:
  resource_tracker: There appear to be N leaked shared_memory objects` at exit and cleans up.
- On POSIX before 3.13, attaching processes also registered the block with their resource tracker, which
  could unlink it when they exited (premature deletion when processes are unrelated). 3.13 adds
  `track=False` for attach-only users; within one multiprocessing pool tree this is usually harmless.
- `size` may be rounded up to the page size; store the real length separately.
- Docker's default `/dev/shm` is 64 MB: pass `--shm-size=2g` (or a `Memory`-medium `emptyDir` in
  Kubernetes) for large blocks, otherwise creation fails with `OSError: [Errno 28] No space left on device`
  or a later bus error.

## 6. numpy arrays over shared memory

The parent creates a block, copies the array in once, and workers wrap the same memory in an `ndarray`
without copying. Each task receives only `(name, shape, dtype, slice)`.

```python
import multiprocessing as mp
from multiprocessing import shared_memory

import numpy as np


def row_norms(shm_name: str, shape: tuple, dtype: str, start: int, stop: int) -> np.ndarray:
    shm = shared_memory.SharedMemory(name=shm_name)
    try:
        emb = np.ndarray(shape, dtype=dtype, buffer=shm.buf)        # zero-copy view
        out = np.linalg.norm(emb[start:stop], axis=1)               # a new array, not a view
        del emb                                                      # release the view before close()
        return out
    finally:
        shm.close()


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    emb = rng.standard_normal((10_000, 384)).astype(np.float32)     # e.g. a MiniLM embedding matrix
    shm = shared_memory.SharedMemory(create=True, size=emb.nbytes)
    try:
        shared = np.ndarray(emb.shape, dtype=emb.dtype, buffer=shm.buf)
        shared[:] = emb                                              # one copy, in the parent
        bounds = [(i, min(i + 2500, len(emb))) for i in range(0, len(emb), 2500)]
        with mp.get_context("spawn").Pool(4) as pool:
            parts = pool.starmap(row_norms, [(shm.name, emb.shape, str(emb.dtype), a, b) for a, b in bounds])
        norms = np.concatenate(parts)
        print(norms.shape, bool(np.allclose(norms, np.linalg.norm(emb, axis=1), rtol=1e-5)))   # (10000,) True
        del shared
    finally:
        shm.close()
        shm.unlink()
```

Writing results into shared memory works the same way: preallocate an output block, each task writes to
its own disjoint slice, and returns nothing (or a status). Overlapping writes need a lock or a different
design.

`BufferError: cannot close exported pointers exist` from `shm.close()` means an `ndarray` view still
references the buffer: `del` the views first.

## 7. SharedMemoryManager

`multiprocessing.managers.SharedMemoryManager` (3.8) tracks blocks and unlinks them all when the `with`
block exits, even on exceptions.

```python
import multiprocessing as mp
from multiprocessing.managers import SharedMemoryManager
from multiprocessing import shared_memory


def total(name: str, n: int) -> int:
    shm = shared_memory.SharedMemory(name=name)
    try:
        return sum(shm.buf[:n])
    finally:
        shm.close()


if __name__ == "__main__":
    with SharedMemoryManager() as smm:
        block = smm.SharedMemory(size=1000)
        block.buf[:1000] = bytes(range(250)) * 4
        with mp.get_context("spawn").Pool(2) as pool:
            print(pool.starmap(total, [(block.name, 1000), (block.name, 10)]))   # [124500, 45]
    # every block unlinked here
```

`smm.ShareableList([...])` gives a fixed-length list of ints, floats, bools, short str/bytes and None in
shared memory; it is handy for small shared tables but slower than numpy for bulk numbers.

## 8. Memory-mapped files and numpy memmap

When data already lives on disk (an `.npy` of embeddings, a tokenized corpus), let every worker map the
same file. The OS page cache holds one copy for everybody, and nothing is pickled.

```python
import multiprocessing as mp
import os
import tempfile

import numpy as np


def shard_sum(path: str, start: int, stop: int) -> float:
    arr = np.load(path, mmap_mode="r")         # maps; reads pages lazily
    return float(arr[start:stop].sum())


if __name__ == "__main__":
    path = os.path.join(tempfile.mkdtemp(), "tokens.npy")
    np.save(path, np.arange(1_000_000, dtype=np.int64))
    bounds = [(path, i, i + 250_000) for i in range(0, 1_000_000, 250_000)]
    with mp.get_context("spawn").Pool(4) as pool:
        print(sum(pool.starmap(shard_sum, bounds)))   # 499999500000.0
```

`np.memmap(path, dtype, mode="r+", shape=...)` allows workers to write disjoint regions of an output file;
call `.flush()` in each writer. For raw files, `mmap.mmap(fd, 0, access=mmap.ACCESS_READ)` gives a
`bytes`-like view.

## 9. Arrow and Parquet

Apache Arrow buffers are columnar and contain no Python objects, so they map and share cheaply:
- `pyarrow.memory_map(path)` + `pyarrow.ipc.open_file(...)` reads an Arrow IPC (Feather v2) file
  zero-copy in every worker.
- Parquet is compressed: each worker reads its own row groups (`pq.ParquetFile(path).read_row_group(i)`),
  so pass `(path, row_group)` tasks, not tables.
- Hugging Face `datasets` stores data as memory-mapped Arrow; `Dataset.map(fn, num_proc=8)` shards across
  processes for you and pickles `fn` with `dill`.
- Polars and DuckDB parallelise internally in native threads: often faster than any Python pool for
  tabular transforms.

```python
# pip install pyarrow
import pyarrow.parquet as pq


def count_rows(path: str, group: int) -> int:
    return pq.ParquetFile(path).read_row_group(group, columns=["text"]).num_rows

# tasks = [(path, g) for g in range(pq.ParquetFile(path).num_row_groups)]
# with Pool(8) as pool: total = sum(pool.starmap(count_rows, tasks))
```

## 10. Manager proxies

`multiprocessing.Manager()` starts a server process holding real objects; workers get proxies whose every
method call is a pickled request/response round trip (tens of microseconds, more under contention).

```python
import multiprocessing as mp


def record(status: dict, doc_id: str) -> None:
    status[doc_id] = "done"          # one IPC round trip: fine for coarse progress, not for per-token counts


if __name__ == "__main__":
    ctx = mp.get_context("spawn")
    with ctx.Manager() as mgr:
        status = mgr.dict()
        with ctx.Pool(2) as pool:
            pool.starmap(record, [(status, f"doc{i}") for i in range(5)])
        print(sorted(status.keys()))   # ['doc0', 'doc1', 'doc2', 'doc3', 'doc4']
```

Rules:
- Proxies pickle, so they can be passed as task arguments (unlike `multiprocessing.Queue`). `mgr.Queue()`
  is the standard fix for MP014.
- `proxy[k] += 1` is a get followed by a set: not atomic across processes. Use `mgr.Lock()` around it, or
  better, count locally and return the counts.
- Mutating a nested object in place does not propagate: `d["k"].append(x)` changes a copy; reassign
  `d["k"] = d["k"] + [x]`.
- Never touch a proxy in a hot loop (MP011). Aggregate in the worker, merge once.

## 11. Queue and Pipe

| | `Queue` | `SimpleQueue` | `JoinableQueue` | `Pipe` |
|-|---------|---------------|-----------------|--------|
| Producers/consumers | many/many | many/many | many/many + `task_done`/`join` | 1/1 (duplex by default) |
| Feeder thread | yes (buffers puts) | no | yes | no |
| `maxsize` | yes | no | yes | OS buffer |
| Timeouts | `get/put(timeout=)` | no | yes | `poll(timeout)` |

Rules (each one is a known deadlock; see the deadlock skill):
- Drain before join: a child does not exit until its buffered puts are flushed to the pipe (MP012).
- Use sentinels (`None` or a dedicated object) to stop consumers; one per consumer.
- Bounded `maxsize` gives back-pressure so a fast reader does not fill RAM.
- Always `get(timeout=...)` and check `p.is_alive()` / `p.exitcode` on timeout: a crashed producer never
  sends its sentinel.
- `queue.qsize()` raises `NotImplementedError` on macOS; do not depend on it.

## 12. Value, Array and locks

```python
import multiprocessing as mp


def bump(counter, n: int) -> None:
    for _ in range(n):
        with counter.get_lock():          # += is read-modify-write: needs the lock
            counter.value += 1


if __name__ == "__main__":
    ctx = mp.get_context("spawn")
    counter = ctx.Value("i", 0)           # shared by inheritance: Process args, not pool tasks
    procs = [ctx.Process(target=bump, args=(counter, 1000)) for _ in range(4)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    print(counter.value)   # 4000
```

`Value`/`Array` live in shared memory with an optional lock; like `Queue` they can only be passed by
inheritance (`Process(args=...)` or pool `initargs`). For progress reporting from pools, count completed
results in the parent instead; it needs no shared state.

## 13. Returning results without the parent bottleneck

If results are large (parsed documents, embedding batches), returning them makes the parent unpickle
everything serially. Alternatives:
- Workers write their output directly (one Parquet/`.npy`/JSONL file per task, named by task id) and
  return the path and a row count; the parent writes a manifest.
- Workers write into a preallocated shared-memory or memmap output at their own offset.
- Workers upsert to the vector store / database themselves (one client per worker, created in the
  initializer), and return ids and counts.

Then the parent's work per task is a few bytes, and adding workers scales again.
