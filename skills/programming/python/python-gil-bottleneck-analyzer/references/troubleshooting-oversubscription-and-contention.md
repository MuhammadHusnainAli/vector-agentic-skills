# Troubleshooting: Oversubscription and Contention

When parallel Python is slow even though the GIL is not (only) the problem: too many threads for the cores,
native thread pools nested inside process pools, locks and the GIL being fought over, memory bandwidth, and
containers that lie about CPU count. Start from the symptom table, then use the section it points to.

## Contents

1. [Symptom -> cause -> fix](#1-symptom---cause---fix)
2. [Counting usable cores (containers, affinity, cgroups)](#2-counting-usable-cores-containers-affinity-cgroups)
3. [Native thread pools and their knobs](#3-native-thread-pools-and-their-knobs)
4. [Oversubscription arithmetic](#4-oversubscription-arithmetic)
5. [Capping threads correctly](#5-capping-threads-correctly)
6. [GIL contention and the convoy effect](#6-gil-contention-and-the-convoy-effect)
7. [Lock contention in your code](#7-lock-contention-in-your-code)
8. [Memory-bandwidth-bound work](#8-memory-bandwidth-bound-work)
9. [Serial bottlenecks around a parallel stage](#9-serial-bottlenecks-around-a-parallel-stage)
10. [Diagnostic command cheat sheet](#10-diagnostic-command-cheat-sheet)

## 1. Symptom -> cause -> fix

| Symptom | Likely cause | Check | Fix |
|---------|-------------|-------|-----|
| More workers = slower; load average ≫ cores | oversubscription (workers × native threads) | `ps -o nlwp PID` per worker; `perf stat` involuntary context switches | one level of parallelism; `OMP_NUM_THREADS=1` per worker |
| Process pool at 100% CPU everywhere, throughput worse than 4 workers | BLAS/torch threads in each worker | `threadpoolctl.threadpool_info()` inside a worker | `threadpool_limits(1)` / env vars before import |
| Pool sized by `os.cpu_count()` is slow in Docker/Kubernetes | CPU quota smaller than host core count | `/sys/fs/cgroup/cpu.max` | size from the quota |
| Threads: one core 100%, others idle | GIL-held Python or C | `gil_probe.py`, py-spy `--gil` | processes / native / free-threaded |
| Threads: all cores busy but no speedup | spinning, lock contention, false sharing, bandwidth | `perf stat` IPC, py-spy `--native` | shard state, fewer threads |
| Async server p99 explodes when a background CPU thread runs | GIL convoy: I/O thread waits to re-acquire | py-spy `--native --idle` shows `take_gil` | move CPU to a process |
| `sys` time high, many context switches | thread churn, lock thrash, tiny tasks | `pidstat -w`, `/usr/bin/time -v` | batch tasks, fewer threads |
| Speedup flat at ~2-4x with processes too | memory bandwidth or serial parent stage | `perf stat -e cache-misses`, profile the parent | float32, fuse passes, parallelise the parent's work |
| Free-threaded build: threads still serial | GIL re-enabled by an extension, or contention on one shared object | `sys._is_gil_enabled()`, per-object hot spots | upgrade/replace extension; per-thread accumulators |
| tokenizers warning about fork, then slow | rayon disabled itself after fork | log message | `TOKENIZERS_PARALLELISM=false` + processes, or one process using rayon |

## 2. Counting usable cores (containers, affinity, cgroups)

`os.cpu_count()` returns the machine's logical CPUs, not what this process may use.

```python
import os


def usable_cpus() -> float:
    """Best estimate of CPUs this process can use: affinity, then cgroup v2 quota."""
    try:
        n = len(os.sched_getaffinity(0))                 # Linux: respects taskset / cpusets
    except AttributeError:
        n = os.cpu_count() or 1
    try:
        quota, period = open("/sys/fs/cgroup/cpu.max").read().split()
        if quota != "max":
            n = min(n, int(quota) / int(period))         # e.g. "200000 100000" = 2 CPUs
    except (OSError, ValueError):
        pass
    return n


print(os.cpu_count(), usable_cpus())
```

| API | Respects affinity | Respects cgroup quota |
|-----|------------------|----------------------|
| `os.cpu_count()` | no | no |
| `len(os.sched_getaffinity(0))` | yes (Linux) | no |
| `os.process_cpu_count()` (3.13+) | yes | no |
| `PYTHON_CPU_COUNT=N` / `-X cpu_count=N` (3.13+) | overrides both functions above | n/a |
| reading `cpu.max` (cgroup v2) or `cpu.cfs_quota_us` (v1) | n/a | yes |

In 3.13+ `ProcessPoolExecutor` and `ThreadPoolExecutor` default sizes use `os.process_cpu_count()`; in
containers set `PYTHON_CPU_COUNT` to the quota so defaults (and libraries that call `os.cpu_count()`) see it.
Hyper-threads count as CPUs: CPU-bound numeric code often peaks at the physical core count.

## 3. Native thread pools and their knobs

Set environment variables **before** the library is imported (they are read at load time); later changes
need the runtime APIs.

| Library | Env var(s) | Runtime API |
|---------|-----------|-------------|
| OpenMP-based (numpy with OpenBLAS-OpenMP, scikit-learn, numba's omp layer, many C extensions) | `OMP_NUM_THREADS` | `threadpoolctl.threadpool_limits(n)` |
| OpenBLAS | `OPENBLAS_NUM_THREADS` | threadpoolctl |
| Intel MKL | `MKL_NUM_THREADS` | threadpoolctl, `mkl.set_num_threads` |
| Apple Accelerate | `VECLIB_MAXIMUM_THREADS` | - |
| numexpr (pandas eval) | `NUMEXPR_NUM_THREADS`, `NUMEXPR_MAX_THREADS` | `numexpr.set_num_threads` |
| PyTorch intra-op | `OMP_NUM_THREADS` / `MKL_NUM_THREADS` at start | `torch.set_num_threads(n)` |
| PyTorch inter-op | - | `torch.set_num_interop_threads(n)` (once, before parallel work) |
| onnxruntime | - | `SessionOptions.intra_op_num_threads`, `inter_op_num_threads` |
| HF tokenizers (rayon) | `TOKENIZERS_PARALLELISM`, `RAYON_RS_NUM_CPUS` | - |
| polars | `POLARS_MAX_THREADS` | `pl.thread_pool_size()` (read-only) |
| numba | `NUMBA_NUM_THREADS` | `numba.set_num_threads(n)` |
| TensorFlow | - | `tf.config.threading.set_intra_op_parallelism_threads` |

Inspect what a process actually loaded:

```python
from threadpoolctl import threadpool_info, threadpool_limits
import numpy as np

for pool in threadpool_info():
    print(pool["internal_api"], pool["num_threads"], pool.get("filepath", "")[-40:])

with threadpool_limits(limits=1):          # temporarily single-threaded BLAS/OpenMP
    np.linalg.svd(np.random.rand(500, 500))
```

## 4. Oversubscription arithmetic

```
runnable threads ≈ processes × (CPU-busy Python threads + native threads per process)
```

| Setup on 16 cores | Runnable | Result |
|-------------------|----------|--------|
| 16 workers × BLAS default 16 threads | 256 | thrashing: slower than 1 worker |
| 16 workers × `OMP_NUM_THREADS=1` | 16 | good for many small matrices |
| 1 process × BLAS 16 threads | 16 | good for a few large matrices |
| 4 workers × 4 BLAS threads | 16 | good middle ground for medium matrices |
| uvicorn 4 workers × process pool 8 | 32 CPU-bound | oversubscribed: pool 4 or workers 2 |
| DataLoader 8 workers × torch 16 intra-op threads | 128 | set `torch.set_num_threads(1)` in `worker_init_fn` |

The fix is never "more workers": pick where the parallelism lives and give that level all the cores.

## 5. Capping threads correctly

Process pools: cap in the **initializer** (spawn/forkserver workers re-import modules, so the env must be set
before the first `import numpy` in the worker) or in the parent's environment before creating the pool.

```python
import os
from concurrent.futures import ProcessPoolExecutor

THREAD_VARS = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
               "VECLIB_MAXIMUM_THREADS")


def init_worker(threads_per_worker: int) -> None:
    for var in THREAD_VARS:
        os.environ[var] = str(threads_per_worker)
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    try:
        import torch
        torch.set_num_threads(threads_per_worker)
    except ImportError:
        pass


def work(seed: int) -> int:
    return sum(i * seed for i in range(10_000))


if __name__ == "__main__":
    for var in THREAD_VARS:                 # children inherit the parent's environment
        os.environ.setdefault(var, "1")
    with ProcessPoolExecutor(max_workers=4, initializer=init_worker, initargs=(1,)) as ex:
        print(sum(ex.map(work, range(8))))
```

Caveat: if numpy was already imported in the parent and the start method is `fork`, children inherit the
already-initialised BLAS pool; env vars set in the initializer then come too late. Use threadpoolctl at runtime
or a spawn/forkserver context (forkserver is the 3.14 default on Linux). The
[pool designer skill](../../python-multiprocessing-pool-designer/SKILL.md) lints for this (MP021).

## 6. GIL contention and the convoy effect

Evidence: py-spy with `--native --idle` shows stacks ending in `take_gil`, `PyEval_RestoreThread` or
`PyCOND_TIMEDWAIT` under Python frames; `profile_classify.py` reports a `gil-wait` share and the verdict
`GIL-CONTENDED`. Each waiting thread was ready to run but did not hold the GIL.

```bash
py-spy record --native --idle --threads --format raw -o stacks.txt --pid 4242 --duration 20
python scripts/profile_classify.py stacks.txt
```

Fixes, in order:

1. Move CPU-bound work out of the process (process pool, job queue). I/O threads then get the GIL immediately.
2. Make CPU work release the GIL (numpy, numba `nogil=True`, Cython `nogil`, PyO3 `allow_threads`/`detach`).
3. Reduce the number of CPU-bound threads to one.
4. Stop-gap: `sys.setswitchinterval(0.001)` to shorten the waits (costs some throughput).
5. Test the free-threaded build if all dependencies support it.

## 7. Lock contention in your code

A `threading.Lock` around a hot section serialises threads exactly like the GIL, on any build.

| Pattern | Fix |
|---------|-----|
| one global lock around a cache used on every request | `functools.lru_cache` for pure functions, or shard: `locks[hash(key) % 64]` |
| lock held during I/O (`with lock: client.post(...)`) | do I/O outside the lock; lock only the shared update |
| shared counter / metrics dict updated per item | per-thread counters merged at the end, or a `queue.Queue` to one aggregator |
| logging handler lock with very chatty DEBUG logs | `QueueHandler` + `QueueListener`; lower the level in hot loops |
| one `queue.Queue` feeding many fast consumers with tiny items | batch items per `put` |
| SQLite single writer | one writer thread, batch inserts in transactions |

Measure lock wait: py-spy `--idle` shows `acquire` frames; a quick in-code check is to time `lock.acquire()`.

## 8. Memory-bandwidth-bound work

Big numpy/torch element-wise passes (normalising, adding, casting) read and write memory faster than cores can
compute; adding cores stops helping once the memory bus is saturated (often at 2-6 cores per socket).

Signs: speedup flattens early for threads *and* processes; `perf stat` shows low instructions per cycle and
many cache misses; arrays far larger than the L3 cache.

Fixes: use `float32` (or `float16`/`int8` where acceptable) to halve traffic; fuse passes (one expression with
`numexpr`, or numba, instead of five temporaries); use in-place operations (`np.divide(x, n, out=x)`);
process in cache-sized chunks; avoid `.copy()` and Python ↔ numpy conversions; on NUMA machines pin processes
to sockets.

## 9. Serial bottlenecks around a parallel stage

Amdahl's law: if 20% of the run is serial, the maximum speedup is 5x however many workers you add. Usual
serial parts in AI pipelines: reading one big file in the parent, pickling arguments in the parent, a single
writer to the vector DB, a `json.dumps` of the whole result, progress bars updated per item.

```python
def amdahl(parallel_fraction: float, workers: int) -> float:
    return 1 / ((1 - parallel_fraction) + parallel_fraction / workers)


for p in (0.5, 0.8, 0.95):
    print(p, [round(amdahl(p, n), 1) for n in (2, 4, 8, 16)])
```

Profile the **parent** process during a parallel run (`py-spy record --pid PARENT`); move reading/parsing into
workers (send paths), write from workers (or batch writes), and update progress per chunk.

## 10. Diagnostic command cheat sheet

```bash
nproc; cat /sys/fs/cgroup/cpu.max                       # cores visible vs quota
ps -o pid,nlwp,pcpu,rss,cmd -p $(pgrep -d, -f ingest)   # threads per process (nlwp)
top -H -p PID                                           # per-thread CPU
pidstat -t -p PID 1                                     # per-thread CPU over time
pidstat -w -p PID 1                                     # voluntary / involuntary context switches
perf stat -e task-clock,context-switches,cpu-migrations,cache-misses,instructions,cycles -p PID -- sleep 10
py-spy dump --pid PID --native                          # where every thread is right now
py-spy record --native --idle --threads --format raw -o stacks.txt --pid PID --duration 20
python scripts/profile_classify.py stacks.txt
python scripts/gil_probe.py --target mymod:hot_fn --workers 8 --repeat 5
```
