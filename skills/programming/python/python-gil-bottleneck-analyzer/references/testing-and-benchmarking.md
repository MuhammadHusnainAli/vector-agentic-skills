# Testing and Benchmarking

Performance claims need the same rigour as correctness claims: a fixed input, repeated measurements, a
statistic that resists noise, and a test that fails when the property you care about (speedup, GIL release,
responsiveness) regresses. This file covers micro and macro benchmarks, noise, CI gates, and tests for
parallel code on both the GIL and free-threaded builds.

## Contents

1. [What to measure](#1-what-to-measure)
2. [timeit and best-of-N](#2-timeit-and-best-of-n)
3. [Statistics and noise](#3-statistics-and-noise)
4. [pyperf for stable numbers](#4-pyperf-for-stable-numbers)
5. [pytest-benchmark](#5-pytest-benchmark)
6. [Testing that a fix scales](#6-testing-that-a-fix-scales)
7. [Testing that the event loop stays responsive](#7-testing-that-the-event-loop-stays-responsive)
8. [Testing thread caps and GIL state](#8-testing-thread-caps-and-gil-state)
9. [Stress-testing thread safety (GIL and free-threaded)](#9-stress-testing-thread-safety-gil-and-free-threaded)
10. [CI performance gates](#10-ci-performance-gates)
11. [Checklist](#11-checklist)

## 1. What to measure

| Question | Metric | Tool |
|----------|--------|------|
| Is function X faster? | best-of-N or median time per call | `timeit`, pyperf, pytest-benchmark |
| Does the pipeline scale? | speedup at 1/2/4/8 workers | speedup harness, `gil_probe.py` |
| Does the GIL still bind? | thread speedup, CPU/wall, Python CPU share | `gil_probe.py --json`, `profile_classify.py --json` |
| Is the server responsive under CPU load? | event-loop lag, p99 latency | lag probe, load generator |
| Are results identical? | equality of outputs | plain asserts |
| Did memory explode? | peak RSS per worker | `resource.getrusage`, tracemalloc |

Always assert outputs are identical between the serial and the parallel version before comparing times.

## 2. timeit and best-of-N

```python
import timeit

setup = "import re; rx = re.compile(r'\\s+'); text = 'a  b   c ' * 2000"
stmts = {
    "re.sub": "rx.sub(' ', text)",
    "split/join": "' '.join(text.split())",
}
for name, stmt in stmts.items():
    runs = timeit.repeat(stmt, setup=setup, repeat=5, number=200)
    best = min(runs) / 200
    print(f"{name:<11} best {best * 1e6:8.1f} us/call   spread {(max(runs) - min(runs)) / min(runs):.0%}")
```

```bash
python -m timeit -s "import json; s = json.dumps(list(range(1000)))" "json.loads(s)"
```

Best-of-N (the minimum) estimates the cost with the least interference and is right for micro-benchmarks of
deterministic code. For end-to-end runs, report the median and the spread; the minimum hides real variance
users will see.

## 3. Statistics and noise

Noise sources: CPU frequency scaling and turbo, thermal throttling, other processes (CI neighbours), the first
call paying imports/JIT/caches, garbage collection, ASLR and memory layout, hyper-threading siblings, page
cache state for file I/O.

```python
import statistics
import time


def bench(fn, repeat=15, warmup=2):
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    q = statistics.quantiles(samples, n=4)
    return {"min": min(samples), "median": statistics.median(samples), "iqr": q[2] - q[0]}


r = bench(lambda: sorted(range(200_000), key=lambda x: -x))
print({k: f"{v * 1000:.2f} ms" for k, v in r.items()})
```

Rules:

- Warm up; discard the first runs.
- Compare A and B interleaved (A, B, A, B...) in the same session, not hours apart.
- Treat differences smaller than the IQR as noise.
- For parallel benchmarks, check `gil_probe.py`'s "CPU availability" line: below ~90% the machine is busy and
  speedups are understated.
- Pin the environment: same Python build (GIL vs free-threaded!), same library versions, same thread caps.

## 4. pyperf for stable numbers

pyperf spawns worker processes, calibrates loops, and reports mean ± std dev; it can tune the system for
benchmarking.

```bash
pip install pyperf
python -m pyperf system tune                       # needs root: fixed frequency, isolated CPUs (undo: system reset)
python -m pyperf timeit -s "import json; s = json.dumps(list(range(1000)))" "json.loads(s)" -o json.json
python -m pyperf timeit -s "import orjson; s = b'[' + b','.join(b'%d' % i for i in range(1000)) + b']'" \
    "orjson.loads(s)" -o orjson.json
python -m pyperf compare_to json.json orjson.json  # "Mean +- std dev: ... -> ...: 5.2x faster"
```

## 5. pytest-benchmark

Benchmarks live next to tests and can be compared across commits.

```python
# test_bench_clean.py
import re

import pytest

WS = re.compile(r"\s+")
DOC = "Some   scraped\ttext with   extra  spaces. " * 500


def clean_regex(s: str) -> str:
    return WS.sub(" ", s).strip()


def clean_split(s: str) -> str:
    return " ".join(s.split())


@pytest.mark.parametrize("fn", [clean_regex, clean_split], ids=["regex", "split"])
def test_clean_speed(benchmark, fn):
    out = benchmark(fn, DOC)
    assert out == clean_split(DOC)          # correctness is asserted in the benchmark too
```

```bash
pytest test_bench_clean.py --benchmark-only --benchmark-autosave           # saves .benchmarks/
pytest test_bench_clean.py --benchmark-only --benchmark-compare --benchmark-compare-fail=median:10%
pytest --benchmark-disable                                                # in normal test runs
```

`--benchmark-compare-fail=median:10%` fails when the median regresses more than 10% against the saved run;
only meaningful on the same, quiet hardware.

## 6. Testing that a fix scales

Assert *ratios* with generous thresholds, never absolute seconds, and skip when the machine cannot show
parallelism.

```python
import os
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import pytest


def cpu_task(n: int) -> int:
    return sum(i % 7 for i in range(n))


def wall(fn) -> float:
    t0 = time.perf_counter()
    fn()
    return time.perf_counter() - t0


@pytest.mark.skipif(len(os.sched_getaffinity(0)) < 4, reason="needs 4 usable CPUs")
def test_processes_scale_pure_python():
    n, workers = 400_000, 4
    serial = min(wall(lambda: [cpu_task(n) for _ in range(workers)]) for _ in range(2))
    with ProcessPoolExecutor(workers) as ex:
        list(ex.map(cpu_task, [10] * workers))                     # warm up workers
        parallel = min(wall(lambda: list(ex.map(cpu_task, [n] * workers))) for _ in range(2))
    assert serial / parallel > 1.8, f"speedup only {serial / parallel:.2f}x"


def test_threads_do_not_help_pure_python_on_gil_build():
    import sys
    if not getattr(sys, "_is_gil_enabled", lambda: True)():
        pytest.skip("free-threaded interpreter: threads are expected to scale")
    n, workers = 300_000, 4
    serial = wall(lambda: [cpu_task(n) for _ in range(workers)])
    with ThreadPoolExecutor(workers) as ex:
        threaded = wall(lambda: list(ex.map(cpu_task, [n] * workers)))
    assert serial / threaded < 1.5                                 # GIL-bound: no meaningful speedup
```

Or call the probe from CI and assert on its classification:

```bash
python scripts/gil_probe.py --target ingest.clean:normalize_shard --arg 2000 --workers 4 --repeat 3 --json \
  > probe.json
python -c "import json; r = json.load(open('probe.json')); assert 'releases the GIL' in r['classification'], r['classification']"
python scripts/gil_probe.py --target ingest.clean:normalize_shard --fail-if-gil-bound   # exit 1 if GIL-bound
```

## 7. Testing that the event loop stays responsive

Measure loop lag: schedule a ticker and record how late it wakes while the endpoint does CPU work.

```python
import asyncio
import time
from concurrent.futures import ProcessPoolExecutor


def cpu_heavy(n: int) -> int:
    return sum(i * i for i in range(n))


async def max_loop_lag(during, interval: float = 0.01) -> float:
    lags: list[float] = []
    done = asyncio.Event()

    async def ticker():
        while not done.is_set():
            t0 = time.perf_counter()
            await asyncio.sleep(interval)
            lags.append(time.perf_counter() - t0 - interval)

    tick = asyncio.create_task(ticker())
    await asyncio.sleep(interval * 2)       # let the ticker start sleeping before the work begins
    await during()
    done.set()
    await tick
    return max(lags, default=0.0)


async def main() -> None:
    async def blocking():                   # CPU on the loop thread: lag ~ the whole computation
        cpu_heavy(3_000_000)

    with ProcessPoolExecutor(1) as pool:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(pool, cpu_heavy, 10)            # warm up the worker

        async def offloaded():
            await loop.run_in_executor(pool, cpu_heavy, 3_000_000)

        print(f"blocking lag  {await max_loop_lag(blocking) * 1000:7.1f} ms")
        print(f"offloaded lag {await max_loop_lag(offloaded) * 1000:7.1f} ms")


if __name__ == "__main__":
    asyncio.run(main())
```

In a test, assert `max_loop_lag(...) < 0.05` for the offloaded path. For FastAPI, drive the app with
`httpx.AsyncClient(transport=httpx.ASGITransport(app=app))`, fire one heavy request and many light ones
concurrently, and assert the light ones' p95 stays low.

## 8. Testing thread caps and GIL state

```python
import os
import sys


def cap_threads(n: str) -> None:            # module-level: picklable initializer
    os.environ["OMP_NUM_THREADS"] = n


def read_env(name: str):
    return os.environ.get(name)


def test_worker_thread_caps():
    from concurrent.futures import ProcessPoolExecutor

    with ProcessPoolExecutor(1, initializer=cap_threads, initargs=("1",)) as ex:
        assert ex.submit(read_env, "OMP_NUM_THREADS").result() == "1"


def test_gil_state_matches_deployment():
    expected_free_threaded = os.environ.get("EXPECT_FREE_THREADED") == "1"
    check = getattr(sys, "_is_gil_enabled", None)
    gil_on = check() if check else True
    assert gil_on is not expected_free_threaded, "an extension re-enabled the GIL (see RuntimeWarning at import)"
```

With threadpoolctl installed, assert BLAS really is capped inside a worker:
`assert all(p["num_threads"] == 1 for p in threadpool_info())`.

## 9. Stress-testing thread safety (GIL and free-threaded)

Code that is "safe because of the GIL" often fails on the free-threaded build. Hammer shared objects from many
threads that start at the same instant, and run the test on both builds in CI.

```python
import threading


class TokenCounter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.total = 0

    def add(self, n: int) -> None:
        with self._lock:                     # remove the lock and this test fails on 3.14t (and sometimes on GIL builds)
            self.total += n


def hammer(counter: TokenCounter, threads: int = 8, iters: int = 20_000) -> None:
    barrier = threading.Barrier(threads)

    def worker() -> None:
        barrier.wait()                       # maximise overlap
        for _ in range(iters):
            counter.add(1)

    ts = [threading.Thread(target=worker) for _ in range(threads)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()


c = TokenCounter()
hammer(c)
assert c.total == 8 * 20_000, c.total
print("ok", c.total)
```

Tips: lower `sys.setswitchinterval(1e-6)` on GIL builds to provoke more interleavings; repeat the test many
times (`pytest --count=50` with pytest-repeat); run with `PYTHON_GIL=0` on a free-threaded build to keep the
GIL off even if an extension would re-enable it (test-only); ThreadSanitizer builds of CPython find data races
in C extensions.

## 10. CI performance gates

| Gate | Command | Robust because |
|------|---------|---------------|
| Python CPU share of a fixed benchmark | `python scripts/profile_classify.py bench.prof --fail-if-python-cpu-over 40` | shares are ratios, insensitive to machine speed |
| Hot path must release the GIL | `python scripts/gil_probe.py --target pkg.mod:fn --fail-if-gil-bound` | classification uses ratios and a CPU-availability check |
| Micro-benchmark regression | `pytest --benchmark-compare-fail=median:15%` on dedicated runners | same hardware comparison |
| Speedup floor | test asserting `speedup > 0.5 * workers` | ratio, skip when cores are missing |
| Responsiveness | loop-lag assertion | absolute but generous (50 ms) |

Run perf gates on dedicated or at least consistent runners, keep thresholds generous, and record raw numbers as
CI artifacts (`--json`) so trends are visible even when the gate passes. A `.prof` artifact written in CI
should be analysed with the same Python version; `profile_classify.py` exits 2 with a "regenerate" message
otherwise.

## 11. Checklist

- [ ] Outputs identical between serial and parallel versions
- [ ] Warm-up runs discarded; best-of-N or median with spread reported
- [ ] Interpreter recorded (version, GIL or free-threaded, `sys._is_gil_enabled()`)
- [ ] Thread caps recorded (`OMP_NUM_THREADS`, torch threads, tokenizers parallelism)
- [ ] Speedup curve at several worker counts, threads and processes
- [ ] CPU availability ≥ 90% during measurement (or results labelled as noisy)
- [ ] Ratio-based CI gates with generous thresholds; raw JSON kept as artifacts
- [ ] Thread-safety stress test passes on the free-threaded build if you ship for it
