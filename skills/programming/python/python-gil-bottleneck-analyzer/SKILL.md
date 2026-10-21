---
name: python-gil-bottleneck-analyzer
description: "Find out why Python code does not scale across cores and pick the right fix: what the GIL does and does not block (I/O, numpy, hashlib, zlib, re, json, Rust tokenizers, switch interval), classify workloads as pure-Python CPU, GIL-releasing native, I/O-bound, memory-bandwidth-bound or lock-contended, measure wall vs CPU time and speedup curves, profile with cProfile, py-spy (--gil, --idle, --native), Scalene, perf -X perf, viztracer, line_profiler, tracemalloc and sys.monitoring, free-threaded 3.13t/3.14t (PEP 703/779, PYTHON_GIL, sys._is_gil_enabled), subinterpreters and InterpreterPoolExecutor, processes, numpy/polars vectorisation, numba nogil, Cython, mypyc, pyo3, OMP_NUM_THREADS oversubscription. Use when threads give no speedup, CPU sits at 100% of one core, a FastAPI endpoint stalls under CPU work, tokenization, JSON parsing, regex cleaning, pandas apply, reranking or data loading is slow, or someone asks whether the GIL is the bottleneck."
metadata:
  category: programming
  subcategory: python
  version: "1.0.0"
---

# Python GIL Bottleneck Analyzer

Turn "my threads don't make it faster" into a measured diagnosis and the cheapest fix that works. Measure first
(wall vs CPU time, a speedup curve across threads and processes), profile to see *where* time goes and whether
that code holds the GIL, classify the workload, then choose: fix the algorithm, vectorise, release the GIL in
native code, use processes, use asyncio for waits, or move to the free-threaded build. `scripts/gil_probe.py`
runs a function serially, in threads, in processes and in sub-interpreters and labels the result;
`scripts/profile_classify.py` reads a cProfile or py-spy profile and splits time into GIL-holding,
GIL-releasing, waiting and import buckets with ranked recommendations.

## Trigger Conditions

Activate this skill when the user:
- Added threads (`ThreadPoolExecutor`, `threading`, `asyncio.to_thread`, FastAPI `def` routes) and got no
  speedup, or a slowdown; or sees one core at 100% while the others idle
- Asks "is the GIL my bottleneck?", "threads or processes?", "should I try free-threaded / no-GIL Python?",
  "what are subinterpreters good for?", or "does numpy / hashlib / tokenizers release the GIL?"
- Has slow CPU-side AI work: tokenizing a corpus, parsing model JSON, cleaning text with regex, pandas
  `apply` in feature pipelines, embedding post-processing, CPU reranking, data loaders, server-side batching
- Runs a FastAPI / asyncio service whose latency spikes when one request does CPU work
- Has a process pool that is slower than expected because each worker spawns many BLAS/OpenMP/torch threads
- Wants to read py-spy, Scalene, perf or cProfile output, or set up a CI performance gate

Hangs and deadlocks belong to [python-async-deadlock-debugger](../python-async-deadlock-debugger/SKILL.md);
designing the pool itself to [python-multiprocessing-pool-designer](../python-multiprocessing-pool-designer/SKILL.md);
asyncio structure, rate limits and `to_thread` to [python-asyncio-pattern-advisor](../python-asyncio-pattern-advisor/SKILL.md).

## Workflow

```
1. BASELINE  -> one representative input; record wall time, CPU time (user/sys), RSS, cores busy
2. PROBE     -> python scripts/gil_probe.py --target mod:fn --arg ...   (serial vs threads vs processes)
3. PROFILE   -> py-spy record --native --format raw / python -m cProfile -o out.prof / scalene
4. CLASSIFY  -> python scripts/profile_classify.py out.prof stacks.txt -> bucket shares + verdict
5. CHOOSE    -> algorithm > vectorise/native (release GIL) > processes > free-threaded > threads/asyncio for waits
6. FIX       -> smallest change on the hot path; cap native thread pools; keep one owner of parallelism
7. VERIFY    -> same input, same outputs, best-of-N timings, speedup curve, CI gate on regressions
```

## What the GIL Is and Is Not

On the default (GIL) build of CPython, one thread at a time executes Python bytecode. A running thread is
asked to drop the GIL every `sys.getswitchinterval()` seconds (default `0.005`) so others can run, and C code
can release it voluntarily around work that does not touch Python objects. So the GIL serialises *bytecode and
GIL-holding C code*, not your program.

| Operation | GIL during the work | Threads scale? |
|-----------|--------------------|----------------|
| Socket/HTTP I/O, file reads/writes, `select`/`epoll`, `time.sleep`, `subprocess` waits, lock waits | released | yes (asyncio is often simpler) |
| `hashlib` on buffers > 2047 bytes, `zlib`/`bz2`/`lzma` compress/decompress | released | yes |
| numpy ufuncs, reductions, copies, BLAS (`@`, `dot`) on numeric dtypes | released (mostly) | yes, but BLAS is already multithreaded |
| numpy on `dtype=object`, `np.array(list_of_lists)`, `.tolist()` | held | no |
| torch / onnxruntime / most CUDA ops | released inside the op | yes, mind intra-op threads |
| HF `tokenizers` `encode_batch` (Rust, rayon) | released; parallel internally | already parallel |
| `re` matching and substitution, `json`/`orjson` parse and dump, `pickle` | held | no |
| `sorted`, `sum`, `str` methods, dict/list ops, any Python loop | held | no |
| pydantic-core validation, most pure-C helpers that build Python objects | held | no |

"Released" depends on the library version and input type; verify with `scripts/gil_probe.py` or py-spy
`--gil` instead of trusting a table. Details: [gil-fundamentals.md](references/gil-fundamentals.md).

## Classify the Workload

| Class | Signals | Right fix |
|-------|---------|-----------|
| CPU-bound pure Python | CPU/wall ≈ 1.0 on one core; threads 1.0x or worse; processes ≈ Nx; profile is Python frames | algorithm first, then vectorise/compile, processes, or free-threaded build |
| GIL-releasing native | CPU/wall ≈ N with N threads; threads ≈ processes | threads (or the library's own pool); cap nested threads |
| I/O-bound | CPU/wall ≪ 1 (e.g. < 0.25); time in `select`/`recv`/`sleep` | asyncio with a Semaphore, or threads; processes add nothing |
| Memory-bandwidth-bound | many cores busy, speedup flattens at 2-4x for threads *and* processes; large arrays | fewer workers, float32, fuse passes, chunk to fit cache |
| Lock-contended | cores busy or idle, speedup flat, py-spy shows `acquire` / `take_gil` | shrink critical sections, shard state, per-worker copies |

Mixed workloads are common (download, parse, embed, upsert): split the stages and give each its own tool.

## Measure Before Changing Anything

```python
import os
import time


def measure(fn, *args):
    """Return (wall_s, cpu_s, cpu_per_wall) for one call; cpu covers every thread of this process."""
    wall0, cpu0 = time.perf_counter(), time.process_time()
    fn(*args)
    wall, cpu = time.perf_counter() - wall0, time.process_time() - cpu0
    return wall, cpu, cpu / wall if wall else 0.0


def busy(n):
    return sum(i * i for i in range(n))


wall, cpu, ratio = measure(busy, 2_000_000)
print(f"wall={wall:.3f}s cpu={cpu:.3f}s cores_busy={ratio:.2f}")
print("user/sys:", os.times().user, os.times().system)
```

Read it: `cores_busy ≈ 1` CPU-bound on one core; `≈ N` parallel; `≪ 1` waiting. High `sys` time points at
syscalls, page faults or lock thrashing. Outside the process: `/usr/bin/time -v python app.py` (user, sys,
elapsed, max RSS, context switches), `top -H -p PID` or `pidstat -t -p PID 1` for per-thread CPU, and inside
a thread `time.thread_time()`. Then draw the **speedup curve**: the same N tasks at 1, 2, 4, 8 threads and
processes (harness in [measuring-and-profiling.md](references/measuring-and-profiling.md)). Thread speedup
flat at 1.0x while processes climb is the GIL fingerprint.

## Profile: Which Tool Answers Which Question

| Question | Tool and command |
|----------|------------------|
| Which functions take the time (deterministic)? | `python -m cProfile -o out.prof app.py`, then `python -m pstats out.prof` (`sort cumtime`, `stats 20`) |
| Where is a running process right now, all threads? | `py-spy dump --pid PID` / `py-spy top --pid PID` |
| Flame graph with low overhead, prod-safe | `py-spy record -o flame.svg --pid PID` (`--threads`, `--subprocesses`) |
| Is the hot code holding the GIL? | `py-spy record --gil -o gil.svg -- python app.py` (only GIL-holding samples) |
| Are threads idle/waiting? | `py-spy record --idle ...` keeps idle samples |
| Python vs C/Rust time split | `py-spy record --native`, or `scalene app.py` (Python / native / system columns) |
| Kernel + native + Python in one stack (Linux, 3.12+) | `perf record -F 999 -g -- python -X perf app.py`; `perf report` |
| Timeline of threads, GIL hand-offs, async tasks | `viztracer app.py` then `vizviewer result.json` |
| Which line in a hot function? | `@profile` + `kernprof -l -v app.py` (line_profiler) |
| Memory growth and allocation sites | `tracemalloc.start(25)` + snapshot diff; Scalene memory columns |
| Cheap custom counters (3.12+) | `sys.monitoring` callbacks on `PY_START` / `CALL` |

Feed the result to `scripts/profile_classify.py`: `py-spy record --format raw -o stacks.txt --native --
python app.py`, then `python scripts/profile_classify.py stacks.txt`. Exact flags, output reading and pitfalls
(cProfile only sees its own thread; operator calls on arrays are charged to the caller) are in
[measuring-and-profiling.md](references/measuring-and-profiling.md).

## Situation -> Right Tool

| Situation | Choose | Why / caveat |
|-----------|--------|--------------|
| O(n²) loop, repeated work, needless conversions | **fix the algorithm** | 10-1000x; parallelism multiplies waste |
| Numeric loop over arrays / columns | **numpy / polars / pandas column ops** | runs in C, releases the GIL, often 10-100x |
| Custom numeric kernel that resists vectorising | **numba `@njit(nogil=True)`** | compiled, GIL-free, threads then scale |
| Typed hot module, C-level loops | **Cython `with nogil:`** or **mypyc** | Cython can release the GIL; mypyc speeds up but keeps it |
| Heavy string/parsing logic, long-lived library | **Rust + pyo3** (`allow_threads` / `detach`) | fastest, release the GIL around pure-Rust work |
| Pure-Python CPU per item ≥ ~1 ms, items independent | **processes** ([pool skill](../python-multiprocessing-pool-designer/SKILL.md)) | one GIL each; pay pickling and startup |
| Network waits (LLM APIs, vector DB, scraping) | **asyncio** ([asyncio skill](../python-asyncio-pattern-advisor/SKILL.md)) or threads | waiting needs no cores |
| GIL-releasing native work (hashing, compression, numpy, decode) | **threads** | no pickling, shared memory |
| Pure-Python CPU, shared in-memory state, all deps support it | **free-threaded 3.14t + threads** | supported but optional build (PEP 779); verify extensions |
| Isolation without processes, stdlib-only code (3.14) | **`InterpreterPoolExecutor`** | one GIL per interpreter; many C extensions cannot load there |
| Big batched tensor math | **GPU** (torch, CuPy) | move the batch, not single items |

Decision tables, code for each hatch and when each loses: [escape-hatches.md](references/escape-hatches.md).

## Symptom -> Cause -> Fix

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| 8 threads, same wall time as 1, one core at 100% | pure-Python CPU holding the GIL | processes, vectorise, or free-threaded build |
| Threads slower than serial | GIL convoy: CPU threads + switch-interval hand-offs | fewer CPU threads; processes |
| Event loop latency spikes when one request is heavy | CPU work in `async def` (or GIL-holding work in the threadpool) | `run_in_executor(process_pool, ...)`, worker queue |
| Process pool: all cores 100% but slower than 4 workers | BLAS/OpenMP/torch threads per worker (oversubscription) | `OMP_NUM_THREADS=1`, `torch.set_num_threads(1)` per worker |
| Speedup flattens at ~3x whatever you do | memory bandwidth, or a serial parent stage | profile parent; fewer, fatter tasks; float32 |
| Profile shows `acquire` / `take_gil` / `futex` at the top | lock or GIL contention | smaller critical sections; processes |
| Free-threaded build still not parallel | an extension re-enabled the GIL on import | check `sys._is_gil_enabled()`; RuntimeWarning at import names the module |
| Free-threaded build is slower single-threaded | expected overhead (larger in 3.13 than 3.14) | only worth it when you actually use threads |
| `tokenizers` warning "process just got forked ... Disabling parallelism" | rayon pool used before fork | `TOKENIZERS_PARALLELISM=false` in workers, or spawn |
| Huge `sys` time, many context switches | oversubscription or lock thrash | cap threads; `perf stat -e context-switches` |

More cases and the oversubscription arithmetic: [troubleshooting-oversubscription-and-contention.md](references/troubleshooting-oversubscription-and-contention.md).

## Free-Threaded Python and Subinterpreters (Precise Status)

| Version | Status |
|---------|--------|
| 3.12 | PEP 684 per-interpreter GIL (C API only); PEP 669 `sys.monitoring`; `-X perf` |
| 3.13 | PEP 703 free-threaded build is **experimental**: separate `python3.13t` binary; `sys._is_gil_enabled()`; `PYTHON_GIL` / `-X gil`; noticeably slower single-threaded (specializing interpreter disabled in that build) |
| 3.14 | PEP 779: free-threaded build is **officially supported** but still optional, not the default (`python3.14t`); single-thread penalty much smaller; PEP 734 `concurrent.interpreters` and `concurrent.futures.InterpreterPoolExecutor` |

```python
import sys
import sysconfig

free_threaded_build = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
gil_fn = getattr(sys, "_is_gil_enabled", None)   # 3.13+
gil_on = gil_fn() if gil_fn else True
print(f"free-threaded build: {free_threaded_build}, GIL enabled now: {gil_on}")
```

Rules: check `sys._is_gil_enabled()` **after** importing everything, because importing an extension that has
not declared free-threading support re-enables the GIL with a RuntimeWarning (`PYTHON_GIL=0` or `-X gil=0`
forces it off, at your own risk). The build removes the GIL, not races: `counter += 1` and check-then-act on
shared dicts still need a `threading.Lock`. Subinterpreters give one GIL per interpreter in one process, but
extensions must support them (numpy 2.3 raised `ImportError` inside one when this was written), and objects cross by
pickling or shareable types. Full details: [free-threading-and-subinterpreters.md](references/free-threading-and-subinterpreters.md).

## Oversubscription: One Owner of Parallelism

Total runnable threads ≈ processes × (Python threads + native pool threads). Keep it ≤ usable cores.

```python
import os

# Set BEFORE importing numpy/torch/tokenizers in each worker process (pool initializer or top of module).
for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(var, "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
# import torch; torch.set_num_threads(1)
```

Pick one level: either N processes × 1 native thread, or 1 process × N native threads. Count usable cores
with `len(os.sched_getaffinity(0))` (Linux) or `os.process_cpu_count()` (3.13+); neither sees a cgroup CPU
quota, so read `/sys/fs/cgroup/cpu.max` in containers.

## AI-Engineering Cases

| Case | Usual diagnosis | Fix |
|------|----------------|-----|
| Tokenizing a corpus | HF fast tokenizers already parallel (Rust, GIL released); slow Python tokenizers hold the GIL | `encode_batch` on large batches; processes only for Python tokenizers; never both |
| JSON parsing of model outputs | `json.loads` holds the GIL; parse cost ≈ pickling cost | `orjson`/`msgspec` in place; parallelism rarely pays |
| Embedding post-processing | per-row Python loops (normalise, top-k) | one numpy call on the batch (`np.linalg.norm(axis=1)`, `argpartition`) |
| Batching in inference servers | Python collation/padding per request on the event loop | pre-tokenize to arrays, batch in one task, move CPU work off the loop |
| pandas `apply(axis=1)` in features | a Python call per row | column ops, `np.where`, `.str`/`.dt`, polars expressions |
| Regex cleaning for corpora | `re` holds the GIL | merge/precompile, prefilter, processes per shard; `regex` module `concurrent=True` |
| CPU reranking | cross-encoder in torch (GIL released) vs Python BM25 loops (held) | batch the model; vectorise scoring; cap torch threads |
| Data loaders | decode/augment in Python | `DataLoader(num_workers=...)` processes; threads for GIL-releasing decoders |
| FastAPI endpoint doing CPU work | `async def` blocks the loop; `def` competes for the GIL | process pool via `run_in_executor`, or a job queue |

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Optional

pool: Optional[ProcessPoolExecutor] = None   # created once in the app lifespan


def rerank_cpu(query: str, docs: list[str]) -> list[int]:
    """Module-level so it pickles: pure-Python scoring that holds the GIL."""
    q = set(query.lower().split())
    scores = [len(q & set(d.lower().split())) for d in docs]
    return sorted(range(len(docs)), key=scores.__getitem__, reverse=True)


async def rerank_endpoint(query: str, docs: list[str]) -> list[int]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(pool, rerank_cpu, query, docs)   # event loop stays responsive
```

Worked versions of every case: [ai-engineering-performance.md](references/ai-engineering-performance.md).

## Verify the Fix

1. Same input, same output: assert results match the serial version (order-insensitive where appropriate).
2. Time best-of-N (`timeit.repeat`, `--repeat 5`) on an idle machine; report median and spread, not one run.
3. Re-run the speedup curve: the fix should move the thread or process line, not just the 1-worker point.
4. Check cores busy (`cpu/wall`), RSS and `sys` time did not explode.
5. Gate regressions in CI with ratios (speedup ≥ X, Python CPU share ≤ Y%), not absolute seconds.

Statistics, pytest-benchmark, perf gates: [testing-and-benchmarking.md](references/testing-and-benchmarking.md).

## Output Format

When diagnosing, answer with:
1. **Measurements** - wall, CPU, cores busy, the speedup table (threads vs processes) and the interpreter
   (GIL build or free-threaded, `sys._is_gil_enabled()`); paste `gil_probe.py` output when available.
2. **Classification** - one class from the table above, with the evidence (profile shares from
   `profile_classify.py`, hot functions, GIL-holding vs releasing).
3. **Fix** - ranked options with expected impact and confidence; complete before/after code for the chosen one
   (including thread caps and pool lifecycle).
4. **Verification** - how to confirm: identical outputs, best-of-N timing, new speedup curve, CI gate.
5. **Caveats** - version-specific behaviour (3.13 vs 3.14), extension compatibility, noise in the numbers.

## Scripts

```bash
# Classify a profile (static: never runs the profiled code)
python -m cProfile -o out.prof ingest.py
python scripts/profile_classify.py out.prof                          # pstats file
py-spy record --format raw --native -o stacks.txt -- python ingest.py
python scripts/profile_classify.py stacks.txt --top 15               # py-spy / perf collapsed stacks
python scripts/profile_classify.py out.prof --collapsed stacks.txt   # both; shares are averaged
cat stacks.txt | python scripts/profile_classify.py -                # stdin
python scripts/profile_classify.py stacks.txt --format collapsed --json
python scripts/profile_classify.py stacks.txt --fail-if-python-cpu-over 50   # CI gate, exit 1
python scripts/profile_classify.py --demo                            # profiles a built-in workload
```
Buckets: python-cpu, native-hold, native-unknown, native-release, io-wait, gil-wait, import. Prints share of
time, top hot spots (with call counts for pstats), per-thread shares (py-spy `--threads`), a verdict
(GIL-BOUND, GIL-CONTENDED, I/O-BOUND, GIL-RELEASING NATIVE, STARTUP-DOMINATED, MIXED) and ranked
recommendations with confidence. A pstats file written by another Python version that cannot be loaded exits 2
with a "regenerate with this interpreter" message. Flags: `--top N`, `--json`, `--format
{auto,pstats,collapsed}`, `--collapsed FILE`, `--fail-if-python-cpu-over PCT`, `--demo`. Exit codes: 0
analysed, 1 gate failed, 2 usage/read/load error.

```bash
# Probe scaling (EXECUTES the target in a child process group, hard-killed after --timeout)
python scripts/gil_probe.py --builtin pure-python          # pure-python|native-release|native-hold|io|mixed
python scripts/gil_probe.py --target ingest.clean:normalize --arg '"some text"' --arg 3
python scripts/gil_probe.py --target ./bench.py:score_batch --arg 2000 --workers 8 --repeat 5 --interpreters
python scripts/gil_probe.py --builtin io --scale 0.5 --timeout 60 --json
python scripts/gil_probe.py --target ingest.clean:normalize --fail-if-gil-bound   # exit 1 if GIL-bound
```
Runs N tasks serially, in N threads, in N processes (forkserver/spawn, pre-warmed) and with `--interpreters`
in an `InterpreterPoolExecutor` (3.14+); reports wall, median, CPU, CPU/wall, per-worker CPU, speedup, CPU
availability (how busy the machine is), the interpreter (GIL build or free-threaded, GIL enabled) and a
classification: "GIL-bound: scales with processes but not threads", "releases the GIL", "I/O-bound", "mixed
I/O + CPU", "CPU-bound, does not scale", or a low-confidence "likely GIL-bound" when the machine is too busy.
Flags: `--target MODULE:FUNC` or `--builtin NAME`, `--arg VALUE` (Python literal, repeatable), `--workers`,
`--repeat`, `--scale`, `--interpreters`, `--timeout` (default 300 s), `--fail-if-gil-bound`, `--json`.
Exit codes: 0 measured, 1 gate failed, 2 usage error, target error or timeout.

## Additional Resources

| File | Content |
|------|---------|
| [gil-fundamentals.md](references/gil-fundamentals.md) | How the GIL works, switch interval, what releases it (stdlib, numpy, torch, tokenizers), atomicity myths, version history |
| [measuring-and-profiling.md](references/measuring-and-profiling.md) | Wall vs CPU, user/sys, per-thread CPU, speedup curves, cProfile, py-spy, Scalene, perf, viztracer, line_profiler, tracemalloc, sys.monitoring |
| [free-threading-and-subinterpreters.md](references/free-threading-and-subinterpreters.md) | 3.13t vs 3.14t status, PYTHON_GIL, extension compatibility, thread safety, concurrent.interpreters, InterpreterPoolExecutor |
| [escape-hatches.md](references/escape-hatches.md) | Decision table and code for algorithms, numpy/polars, numba, Cython, mypyc, Rust/pyo3, processes, GPU, asyncio |
| [ai-engineering-performance.md](references/ai-engineering-performance.md) | Tokenization, JSON outputs, embeddings, server batching, pandas, regex corpora, reranking, data loaders, FastAPI |
| [troubleshooting-oversubscription-and-contention.md](references/troubleshooting-oversubscription-and-contention.md) | Symptom tables, thread-pool env vars, torch threads, cgroups, lock and GIL contention, memory bandwidth |
| [testing-and-benchmarking.md](references/testing-and-benchmarking.md) | timeit, pytest-benchmark, noise and statistics, speedup assertions, CI perf gates, testing free-threaded code |
