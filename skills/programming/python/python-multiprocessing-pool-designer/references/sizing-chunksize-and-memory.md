# Sizing Workers, Chunksize and Memory

How many workers, how big a chunk, how much memory, and what speedup to expect. Ends with the exact model
used by `scripts/pool_tool.py plan`, so its numbers can be checked and recalibrated.

## Contents

- [1. Measure before you size](#1-measure-before-you-size)
- [2. Counting usable cores](#2-counting-usable-cores)
- [3. Hyperthreading and physical cores](#3-hyperthreading-and-physical-cores)
- [4. Thread oversubscription inside workers](#4-thread-oversubscription-inside-workers)
- [5. Memory per worker](#5-memory-per-worker)
- [6. Chunksize and overhead math](#6-chunksize-and-overhead-math)
- [7. Where the speedup goes (Amdahl for pools)](#7-where-the-speedup-goes-amdahl-for-pools)
- [8. The planner's model](#8-the-planners-model)
- [9. Calibrating the constants](#9-calibrating-the-constants)
- [10. Worked examples](#10-worked-examples)

## 1. Measure before you size

The planner needs five numbers. Measure them on real data, single process:

| Input | How to measure |
|-------|----------------|
| `--items` | Number of work items after batching (files, pages, rows, batches of 64 texts) |
| `--item-ms` | Median of `time.perf_counter()` around the task function over 50-200 real items, after warm-up |
| `--payload-kb` | `len(pickle.dumps(args, protocol=pickle.HIGHEST_PROTOCOL)) / 1024` for typical args |
| `--result-kb` | Same for the return value |
| `--init-s` | Time of the initializer (model/tokenizer load, imports) in a fresh process |
| `--mem-per-worker-mb` | Peak RSS of one worker after init and a few tasks (`resource.getrusage(RUSAGE_SELF).ru_maxrss` is KB on Linux) |

```python
import pickle
import statistics
import time


def task(text: str) -> list:                     # stand-in for parse/chunk/tokenize
    return [w for w in text.split() if len(w) > 3]


samples = [" ".join(f"word{i}" for i in range(200)) for _ in range(100)]
for s in samples[:5]:
    task(s)                                       # warm-up
times = []
for s in samples:
    t = time.perf_counter()
    out = task(s)
    times.append((time.perf_counter() - t) * 1000)
print(f"--item-ms {statistics.median(times):.3f}",
      f"--payload-kb {len(pickle.dumps(samples[0], protocol=5)) / 1024:.1f}",
      f"--result-kb {len(pickle.dumps(out, protocol=5)) / 1024:.1f}")
```

If item times vary a lot (PDFs of 1 vs 400 pages), use the mean for throughput and keep chunks small
(the tail is set by the slowest chunk). Sort items largest-first to shorten the tail.

## 2. Counting usable cores

| Source | Respects affinity (`taskset`, `cpuset`) | Respects container CPU quota | Version |
|--------|------------------------------------------|------------------------------|---------|
| `os.cpu_count()` | No | No | all |
| `len(os.sched_getaffinity(0))` | Yes | No | Linux |
| `os.process_cpu_count()` | Yes | No | 3.13 |
| cgroup v2 `/sys/fs/cgroup/cpu.max` (`quota period`) | n/a | Yes | Linux |
| cgroup v1 `cpu.cfs_quota_us / cpu.cfs_period_us` | n/a | Yes | Linux |
| `PYTHON_CPU_COUNT` env / `-X cpu_count=N` | Overrides `cpu_count` and `process_cpu_count` | Set it to the quota yourself | 3.13 |

A Kubernetes pod with `limits.cpu: 2` on a 64-core node sees `os.cpu_count() == 64`. A pool of 64 workers is
then throttled by the CFS quota: every worker gets 1/32 of a core in bursts, latency spikes and memory is 32x
higher than needed.

```python
import math
import os


def usable_cores() -> int:
    if hasattr(os, "process_cpu_count"):
        n = os.process_cpu_count() or 1                  # 3.13+
    elif hasattr(os, "sched_getaffinity"):
        n = len(os.sched_getaffinity(0))
    else:
        n = os.cpu_count() or 1
    try:
        with open("/sys/fs/cgroup/cpu.max") as fh:       # cgroup v2: "max 100000" or "200000 100000"
            quota, period = fh.read().split()
        if quota != "max":
            n = min(n, max(1, math.ceil(int(quota) / int(period))))
    except (OSError, ValueError):
        pass
    return n


print(usable_cores() >= 1)   # True
```

Leave headroom when the parent does real work (writing results, a web server) or other services share
the box: `workers = usable - 1` is a common choice for services; batch jobs use all.

## 3. Hyperthreading and physical cores

Two hardware threads share one core's execution units. Pure-Python interpreter loops gain little from the
second hardware thread (often 0-30%); memory-bound or branchy code sometimes more. There is no stdlib way
to count physical cores (`psutil.cpu_count(logical=False)` does). Benchmark `workers = physical` vs
`workers = logical` on the real task; pick the smaller when within 10%, since each worker costs memory.

## 4. Thread oversubscription inside workers

numpy (OpenBLAS/MKL), torch, onnxruntime, faiss, polars and HF tokenizers start their own thread pools sized
to the core count. `W` workers x `C` threads each on `C` cores means `W x C` runnable threads: context
switching, cache thrash, often slower than one worker.

Set limits **before** the library is imported in the worker (spawn imports fresh, so the initializer or
environment works):

```python
import os


def init_worker() -> None:
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[var] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    try:
        import torch
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)        # only valid before any parallel work in this process
    except ImportError:
        pass


init_worker()
print(os.environ["OMP_NUM_THREADS"])   # 1
```

Rules of thumb: either many single-threaded workers, or one process with a multi-threaded library, or a
few workers with `cores // workers` threads each. `threadpoolctl.threadpool_limits(1)` (third-party)
limits BLAS pools at runtime.

## 5. Memory per worker

```
workers_by_memory = floor(0.85 x memory_limit / peak_rss_per_worker)        (planner: MEM_HEADROOM = 0.85)
total_memory      = parent_rss + workers x peak_rss_per_worker
```

What counts in a worker's RSS:
- The interpreter and imports: 15-30 MB bare, 300-800 MB with torch + transformers imported.
- Models: weights in RAM (a 110M-parameter fp32 encoder is ~440 MB; int8 ONNX ~110 MB).
- The working set of the in-flight chunk (input + output), times chunksize.
- With fork: pages shared with the parent are counted in each RSS but exist once (use PSS/USS:
  `smem`, `/proc/<pid>/smaps_rollup`). They become private when written, including by refcount updates.
- Allocator fragmentation that grows over time: cap with `maxtasksperchild` / `max_tasks_per_child`.

Where the memory limit comes from: cgroup v2 `memory.max`, v1 `memory.limit_in_bytes`, otherwise
`MemAvailable` in `/proc/meminfo` (the planner reads these when `--mem-limit-mb` is omitted). When the
limit is hit, the kernel OOM-killer sends SIGKILL to one worker: `ProcessPoolExecutor` raises
`BrokenProcessPool`, `Pool.map` hangs (see the debugging reference).

## 6. Chunksize and overhead math

Per chunk, the stdlib pools pay a fixed cost: pickling the call frame, a write and a read on a pipe, lock
acquisitions on both queues, waking a worker and the result-handler thread. Per item they pay pickling of
argument and result proportional to size and object count.

```
per_chunk_fixed   ~ 35-90 us   (measured below; Pool > ProcessPoolExecutor)
per_KB_pickled    ~ 0.4 us (bytes) | 1 us (str) | 2 us (list of floats) | 13 us (list of small dicts)
overhead_share    = (n_chunks x per_chunk + N x KB x per_KB) / (N x item_time + overhead)
```

Choosing chunksize:
1. **Floor (overhead):** chunk work >= 100 x per-chunk cost keeps overhead <= 1%. With ~150 us budgeted per
   chunk that is >= 15 ms; the planner uses 20 ms (`MIN_CHUNK_S`).
2. **Ceiling (balance):** at least ~4 chunks per worker so a slow chunk does not leave the other workers
   idle: `chunksize <= ceil(N / (4 x workers))` (the `Pool.map` default).
3. **Ceiling (latency/memory):** results of a chunk arrive together, so progress bars jump and memory holds
   a whole chunk of results.
4. When the floor exceeds the ceiling, items are too small for this many workers: batch them into bigger
   items or use fewer workers.

| item time | sensible chunksize (8 workers, 100k items) |
|-----------|---------------------------------------------|
| 0.02 ms | 1000+ (and batch items: per-item IPC still dominates) |
| 1 ms | 20-50 |
| 10 ms | 2-8 |
| 100 ms+ | 1 |

## 7. Where the speedup goes (Amdahl for pools)

```
T_parallel = startup + init + max(T_workers, T_parent) + stragglers + shutdown
T_workers  = (N x (item + ipc_item) + n_chunks x worker_chunk_cost) / workers
T_parent   = N x (per_item_bookkeeping + ipc_item) + n_chunks x per_chunk_cost
speedup    = T_serial / T_parallel
```

`T_parent` is the hidden serial part: the parent pickles every argument and unpickles every result on
its own (task-feeder and result-handler threads share the GIL). If `T_parent > T_workers`, adding workers
changes nothing. Remedies: smaller payloads (paths instead of contents), smaller results (write to disk in
the worker, return ids), bigger items, shared memory for arrays.

## 8. The planner's model

`pool_tool.py plan` evaluates every worker count `w` from 1 to the cap and, for each, every candidate
chunksize `c` in `{1, 2, 4, ..., ceil(N / w)} U {ceil(N / (4w))}`. All times in seconds.

Inputs: `N` items, `t` = item_ms / 1000, `P` payload KB, `R` result KB, `S` init seconds, method `m`.

Constants (in `pool_tool.py`):

| Constant | Value | Meaning |
|----------|-------|---------|
| `ITEM_OVERHEAD_US` | 5 | Parent bookkeeping per item |
| `CHUNK_OVERHEAD_US` | 150 | Parent cost per chunk message (measured 35-90 us; conservative) |
| `WORKER_CHUNK_US` | 50 | Worker cost per chunk |
| `IPC_US_PER_KB` | 2.0 | Pickle + pipe + unpickle per KB (measured 0.4-13 us depending on object shape) |
| `LAUNCH_S` | fork 0.003, forkserver 0.005, spawn 0.02 | Parent-side cost per worker, sequential |
| `BOOT_S` | fork 0, forkserver 0.08, spawn 0.12 | Child interpreter boot, once (children boot in parallel) |
| `SHUTDOWN_S` | 0.05 | Joining workers |
| `TAIL_FRACTION` | 0.5 | Expected straggler cost in chunk durations (uneven items) |
| `MIN_CHUNK_S` | 0.02 | Preferred minimum chunk duration |
| `MEM_HEADROOM` | 0.85 | Share of the memory limit usable by workers |

Formulas:

```
ipc_item   = (P + R) x IPC_US_PER_KB / 1e6
n_chunks   = ceil(N / c)
parent     = N x (ITEM_OVERHEAD_US / 1e6 + ipc_item) + n_chunks x CHUNK_OVERHEAD_US / 1e6
workers    = (N x (t + ipc_item) + n_chunks x WORKER_CHUNK_US / 1e6) / w
rounds     = ceil(n_chunks / w)
balanced   = rounds x c x (t + ipc_item) + rounds x WORKER_CHUNK_US / 1e6      # quantization: last round
tail       = TAIL_FRACTION x c x (t + ipc_item)      if w > 1 and n_chunks > 1 else 0
compute    = max(workers, balanced, parent) + tail
startup    = w x LAUNCH_S[m] + BOOT_S[m] + S
wall(w, c) = startup + compute + SHUTDOWN_S
serial     = N x t + S
ipc_share  = overhead / (overhead + N x t),
             overhead = 2 x N x ipc_item + N x ITEM_OVERHEAD_US / 1e6 + n_chunks x (CHUNK_OVERHEAD_US + WORKER_CHUNK_US) / 1e6
```

Selection:
1. Worker cap = `min(cores, N, floor(MEM_HEADROOM x mem_limit / mem_per_worker))` (memory term only when
   `--mem-per-worker-mb` is given; the limit defaults to cgroup / MemAvailable).
2. For each `w`: among chunk candidates within 1% of that `w`'s fastest wall time, take the smallest whose
   chunk lasts >= `MIN_CHUNK_S`; if none lasts that long, the largest near-fastest one.
3. Recommended `w`: the smallest worker count whose wall time is within 5% of the overall best (saves
   memory and cores for the same speed).

Warnings emitted:

| Condition | Warning |
|-----------|---------|
| speedup < 1 | processes slower than serial |
| 1 <= speedup < 1.5 | probably not worth it |
| item_ms < 1 and ipc_share > 30% | task too small for processes |
| ipc_share > 50% | IPC/pickling dominates |
| parent >= 0.95 x compute and w > 1 | parent is the bottleneck |
| startup / wall > 25% | init dominates: reuse the pool |
| memory cap < min(cores, N) | memory limit caps workers (or cannot fit one) |
| N < cores | not enough items |
| P or R >= 1024 KB | use shared memory / paths |
| fork and S > 0 | load read-only state before forking, gc.freeze(), never after CUDA |
| spawn/forkserver and S > 0 | every worker pays init: initializer, not per task |

What the model ignores: per-item variance beyond the tail term, memory bandwidth saturation, CPU frequency
scaling with all cores busy (expect 10-20% less than linear), NUMA, disk contention, and GIL contention
between the parent's feeder/handler threads and a busy parent main thread. It is a sizing aid; confirm
with a benchmark on 1-5% of the data.

## 9. Calibrating the constants

Measured on a 12-core Linux machine, Python 3.14, forkserver, 4 workers:

| Measurement | ProcessPoolExecutor | Pool |
|-------------|--------------------|------|
| Per chunk, chunksize=1, trivial task | 34 us | 88 us |
| Per item at chunksize=1000, trivial task | 0.18 us | 0.08 us |
| 100 KB distinct `bytes` payload + result | 0.44 us/KB | |
| ~100 KB `str` | 0.97 us/KB | |
| ~35 KB `list[float]` | 1.98 us/KB | |
| ~6 KB `list[dict]` (500 small dicts) | 12.8 us/KB | |

Reproduce on your hardware:

```python
import concurrent.futures as cf
import multiprocessing as mp
import time


def ident(x):
    return x


def per_chunk_us(n: int = 5000) -> float:
    with cf.ProcessPoolExecutor(2, mp_context=mp.get_context("spawn")) as ex:
        list(ex.map(ident, range(8)))                          # warm up workers
        t = time.perf_counter()
        list(ex.map(ident, range(n), chunksize=1))
        return (time.perf_counter() - t) / n * 1e6


if __name__ == "__main__":
    print(f"{per_chunk_us():.0f} us per chunk")               # e.g. 30-150 us
```

Note that the same object repeated in one chunk is pickled once (pickle memoizes within a message), so
benchmark with distinct objects.

## 10. Worked examples

**Tokenizing 200k documents, 4 ms each, 8 KB in, 2 KB out, 8 cores:**
`plan --items 200000 --item-ms 4 --payload-kb 8 --result-kb 2 --cores 8` -> 8 workers, chunksize 8,
~101 s vs 13.3 min serial (7.9x), IPC 1.7%. Fine as is.

**Row-level feature extraction, 1M rows at 0.02 ms:**
`plan --items 1000000 --item-ms 0.02 --cores 16` -> 3 workers, ~2.2x, IPC 40%, "parent is the bottleneck".
Fix the shape, not the pool: map over batches of 10k rows (`--items 100 --item-ms 200`) or vectorize.

**CPU reranker, 5000 queries at 120 ms, 6 s model load, 1.8 GB per worker, 8 GB pod, spawn:**
`plan --items 5000 --item-ms 120 --init-s 6 --mem-per-worker-mb 1800 --mem-limit-mb 8192 --start-method spawn --cores 16`
-> memory caps workers at 3, ~2.9x. Options: quantize to shrink RSS, or share one model across threads
when the runtime releases the GIL (onnxruntime and torch inference do).

**Embedding with large payloads, 50k items at 30 ms, 2 MB in, fork:**
the parent spends ~3.5 min pickling: "parent is the bottleneck" and "payload >= 1 MB". Send file paths and
let workers read, or place arrays in shared memory.
