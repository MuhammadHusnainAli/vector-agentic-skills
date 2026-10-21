# Measuring and Profiling

How to get numbers you can trust before changing code: wall vs CPU time, the user/sys split, per-thread CPU,
speedup curves, and every profiler that matters for GIL questions, with exact commands and how to read the
output. Feed profiles into `scripts/profile_classify.py`; run scaling experiments with `scripts/gil_probe.py`.

## Contents

1. [The four numbers](#1-the-four-numbers)
2. [Per-thread CPU](#2-per-thread-cpu)
3. [Speedup curves](#3-speedup-curves)
4. [cProfile and pstats](#4-cprofile-and-pstats)
5. [py-spy](#5-py-spy)
6. [Scalene](#6-scalene)
7. [perf with -X perf (Linux, 3.12+)](#7-perf-with--x-perf-linux-312)
8. [viztracer](#8-viztracer)
9. [line_profiler](#9-line_profiler)
10. [tracemalloc](#10-tracemalloc)
11. [sys.monitoring (3.12+)](#11-sysmonitoring-312)
12. [Choosing a profiler](#12-choosing-a-profiler)
13. [From profile to verdict with profile_classify.py](#13-from-profile-to-verdict-with-profile_classifypy)

## 1. The four numbers

| Number | How | Meaning |
|--------|-----|---------|
| Wall time | `time.perf_counter()` around the work | what users wait for |
| CPU time (process) | `time.process_time()` (all threads, user + sys) | how much computing happened |
| Cores busy | CPU / wall | ≈1 one core busy; ≈N parallel; ≪1 waiting |
| User vs sys | `os.times()`, `resource.getrusage`, `/usr/bin/time -v` | high sys = syscalls, page faults, lock thrash |

```python
import os
import resource
import time


def work():
    return sum(i % 7 for i in range(3_000_000))


wall0, cpu0, t0 = time.perf_counter(), time.process_time(), os.times()
work()
wall, cpu, t1 = time.perf_counter() - wall0, time.process_time() - cpu0, os.times()
ru = resource.getrusage(resource.RUSAGE_SELF)
print(f"wall {wall:.3f}s  cpu {cpu:.3f}s  cores busy {cpu / wall:.2f}")
print(f"user {t1.user - t0.user:.3f}s  sys {t1.system - t0.system:.3f}s")
print(f"max RSS {ru.ru_maxrss / 1024:.0f} MiB (Linux reports KiB)  ctx switches vol={ru.ru_nvcsw} invol={ru.ru_nivcsw}")
```

From the shell:

```bash
/usr/bin/time -v python ingest.py        # GNU time: User/System time, Elapsed, Max RSS, context switches
perf stat -e task-clock,context-switches,cpu-migrations,page-faults -- python ingest.py
```

`perf stat` prints "CPUs utilized" (task-clock / elapsed), the same as cores busy. Many involuntary context
switches mean more runnable threads than cores (oversubscription); many voluntary ones mean blocking (I/O or
locks).

`resource` is Unix-only; on Windows use `psutil.Process().cpu_times()` and `memory_info()`.

## 2. Per-thread CPU

Inside a thread, `time.thread_time()` is that thread's CPU. To read another thread's CPU on Linux, use its
clock id:

```python
import threading
import time


def spin(n):
    while n:
        n -= 1


t = threading.Thread(target=spin, args=(20_000_000,))
t.start()
clock = time.pthread_getcpuclockid(t.ident)   # Unix only; the thread must still be running
time.sleep(0.05)
print(f"worker CPU so far: {time.clock_gettime(clock):.3f}s")   # OSError EINVAL once the thread has exited
t.join()
```

From outside: `top -H -p PID` (threads as rows), `pidstat -t -p PID 1`, or `py-spy top --pid PID` (Python
functions per thread). On a GIL build with N CPU-bound threads, each thread shows roughly 100/N % of one core:
that pattern alone diagnoses GIL serialisation.

## 3. Speedup curves

One timing point proves little. Run the same total work with 1, 2, 4, 8 workers for threads and for processes
and plot or tabulate speedup = serial wall / parallel wall.

```python
import os
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor


def task(n):
    acc = 0
    for i in range(n):
        acc += i % 7
    return acc


def run(executor_cls, workers, tasks, n):
    with executor_cls(max_workers=workers) as ex:
        list(ex.map(task, [1000] * workers))          # warm up: start every worker first
        t0 = time.perf_counter()
        list(ex.map(task, [n] * tasks))
        return time.perf_counter() - t0


if __name__ == "__main__":
    TASKS, N = 8, 400_000
    t0 = time.perf_counter()
    for _ in range(TASKS):
        task(N)
    serial = time.perf_counter() - t0
    print(f"serial {serial:.3f}s on {os.cpu_count()} CPUs")
    for workers in (1, 2, 4):
        th = run(ThreadPoolExecutor, workers, TASKS, N)
        pr = run(ProcessPoolExecutor, workers, TASKS, N)
        print(f"{workers} workers: threads {serial / th:4.1f}x   processes {serial / pr:4.1f}x")
```

| Curve shape | Diagnosis |
|-------------|-----------|
| threads flat ≈1x, processes ≈ linear | GIL-bound Python or GIL-holding C |
| threads ≈ processes ≈ linear | GIL released (native) |
| threads ≈ linear way past core count | I/O-bound (waiting) |
| both rise then flatten at 2-4x | memory bandwidth, serial parent stage, or shared lock |
| processes worse than serial | per-task work too small vs pickling/IPC, or start-up dominates |
| everything worse as workers grow | oversubscription (native thread pools × workers) |

`scripts/gil_probe.py` automates one point of this curve (N workers) including CPU/wall ratios, per-worker
CPU, a CPU-availability check for busy machines and a classification. Run it at several `--workers` values to
get the curve.

## 4. cProfile and pstats

Deterministic: records every function call in the thread where it is enabled.

```bash
python -m cProfile -o out.prof ingest.py --limit 1000      # profile a whole script
python -m cProfile -s cumtime ingest.py | head -40         # print sorted by cumulative time
python -m pstats out.prof                                  # interactive: sort cumtime / stats 20 / callers fn
python scripts/profile_classify.py out.prof                # bucket shares + verdict
```

```python
import cProfile
import pstats


def hot():
    return sorted(str(i) for i in range(200_000))


with cProfile.Profile() as prof:          # context manager form: 3.8+
    hot()
stats = pstats.Stats(prof).sort_stats("tottime")
stats.print_stats(5)
stats.dump_stats("hot.prof")
```

Reading the table:

| Column | Meaning |
|--------|---------|
| `ncalls` | calls (`a/b` = total/primitive for recursion) |
| `tottime` | self time inside this function, excluding callees |
| `cumtime` | including callees |
| `{built-in method ...}` / `{method ... of ... objects}` | C functions: classify by name (GIL-holding or not) |

Pitfalls:

- **Only one thread.** cProfile records the thread that enabled it. Worker threads need their own profiler
  (`threading.setprofile`, or since 3.12 `threading.setprofile_all_threads`) or a sampling profiler.
- **Overhead.** Every call costs extra, so code with millions of tiny calls looks slower than it is and its
  share is inflated. Confirm with py-spy.
- **Operators are invisible.** `a + b` on numpy arrays or `x @ w` are not function calls; their time lands in
  the calling Python function's `tottime`. numpy-heavy code can therefore look like "pure Python".
- **C callables that are objects** (e.g. the `_json` scanner) do not appear; their time lands in the Python
  wrapper (`json/decoder.py:raw_decode`). `profile_classify.py` knows the common wrappers.
- **Wall-clock timer.** cProfile's default timer is wall time, so `time.sleep` and blocking I/O show up as
  time in those built-ins, which is what you want for "where does the time go".
- **Version-specific files.** `.prof` files are marshal data; load them with the same Python that wrote them
  when possible. `profile_classify.py` exits 2 with a "regenerate" message if loading fails.

## 5. py-spy

A sampling profiler that reads the target's memory from outside: no code changes, low overhead, safe in
production. Needs ptrace permission (run as the same user with `kernel.yama.ptrace_scope` permitting it, use
`sudo`, or add `--cap-add SYS_PTRACE` in Docker). Check that your py-spy release supports your Python version
before relying on it for a brand-new interpreter.

```bash
py-spy top --pid 4242                                     # live "top" of Python functions
py-spy dump --pid 4242                                    # one stack per thread right now (--locals for variables)
py-spy record -o flame.svg --pid 4242 --duration 30       # flame graph from a running process
py-spy record -o flame.svg -- python ingest.py            # launch and profile
py-spy record --threads --subprocesses -o all.svg -- python serve.py
py-spy record --gil -o gil.svg -- python ingest.py        # only samples where a thread holds the GIL
py-spy record --idle -o idle.svg -- python ingest.py      # include idle/waiting threads
py-spy record --native -o native.svg -- python ingest.py  # include C/C++/Rust frames
py-spy record --format raw --native --threads -o stacks.txt -- python ingest.py
python scripts/profile_classify.py stacks.txt
```

| Flag | Use it to answer |
|------|------------------|
| `--gil` | Which code holds the GIL? Compare with a normal recording: what vanishes released it |
| `--idle` | Where do threads wait? Without it, idle samples are dropped and waiting is invisible |
| `--native` | Is the time in numpy/BLAS/tokenizers (`native-release`) or in `re`/`json` (`native-hold`)? Shows `take_gil` waits |
| `--threads` | Per-thread breakdown (`profile_classify.py` prints shares per thread) |
| `--subprocesses` | Profile pool workers too |
| `--rate N` | Samples per second (default 100); raise for short runs |
| `--format raw` | Collapsed stacks text (`frame;frame;frame COUNT`) for scripts and FlameGraph tools |
| `--format speedscope` | JSON for speedscope.app |

Reading a flame graph: width = share of samples; the top edge of each tower is where the CPU actually was
(self time). Wide plateaus at `select`/`epoll_wait`/`acquire` with `--idle` = waiting; wide plateaus at Python
functions with `--gil` = GIL-holding CPU work.

## 6. Scalene

A sampling CPU + memory (+ GPU) profiler that separates **Python time, native time and system time** per line
and estimates memory allocation and copy volume. It is the quickest way to see "is this line slow because of
Python or because of C?".

```bash
pip install scalene
scalene ingest.py                               # opens a web UI (or terminal output when headless)
scalene --cli --cpu ingest.py                   # CPU only, text output
scalene --cli --reduced-profile ingest.py       # only lines with significant time
scalene --json --outfile profile.json ingest.py
scalene --profile-all ingest.py                 # include library code, not just your files
```

Flag names have shifted between releases; check `scalene --help` for your version.

| Column | Reading |
|--------|---------|
| Time Python | bytecode: holds the GIL; vectorise or use processes |
| Time native | C/Rust: may or may not hold the GIL; check with py-spy `--gil` or the probe |
| Time system | syscalls/I-O; high values suggest waiting or OS overhead |
| Memory / copy volume | large copies (Python ↔ numpy conversions) are a hidden cost |

## 7. perf with -X perf (Linux, 3.12+)

Linux `perf` sees kernel, native and (with the trampoline) Python frames together: the best tool for
memory-bandwidth, cache and lock questions.

```bash
perf record -F 999 -g -- python -X perf ingest.py          # 3.12+: Python frames appear as py::func:file
perf report --no-children                                   # self time
PYTHONPERFSUPPORT=1 perf record -F 999 -g -- python ingest.py   # same, via environment
perf record -F 999 --call-graph dwarf -- python -X perf_jit ingest.py   # 3.13+: DWARF-based variant
perf script | stackcollapse-perf.pl > stacks.txt            # FlameGraph tools; then profile_classify.py
perf stat -e cycles,instructions,cache-misses,LLC-load-misses -- python bench.py
```

From code: `sys.activate_stack_trampoline("perf")` / `sys.deactivate_stack_trampoline()` (3.12+, Linux).
Without the trampoline, every Python frame shows as `_PyEval_EvalFrameDefault`; `profile_classify.py` then
counts that interpreter frame as pure-Python CPU. Low instructions-per-cycle with high cache misses points at
memory bandwidth, not the GIL. `perf` needs `kernel.perf_event_paranoid` permissions (or root).

## 8. viztracer

A tracing profiler that records every function entry/exit with timestamps per thread and process and shows a
timeline. Ideal for *seeing* the GIL: threads that should overlap appear as alternating, never simultaneous
bars.

```bash
pip install viztracer
viztracer ingest.py                      # writes result.json
vizviewer result.json                    # timeline UI in the browser
viztracer --log_sparse ingest.py         # only functions decorated with @log_sparse (low overhead)
viztracer -o trace.json -- python -m mypkg.cli run
```

Tracing overhead is high (every call); use it on a short representative run, and use `--log_sparse` or
filters for long jobs. It also traces asyncio tasks and multiprocessing children.

## 9. line_profiler

When the profile points at one function, line_profiler tells you which line.

```bash
pip install line_profiler
kernprof -l -v ingest.py                 # functions decorated with @profile are timed line by line
python -m line_profiler ingest.py.lprof  # re-print a saved result
```

```python
try:
    profile                              # injected by kernprof
except NameError:                        # running without kernprof: no-op decorator
    def profile(fn):
        return fn


@profile
def chunk(text, size=200):
    words = text.split()
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size)]


print(len(chunk("token " * 10_000)))
```

## 10. tracemalloc

Memory matters for GIL decisions: process pools multiply RSS, and memory-bound code does not scale with any
tool.

```python
import tracemalloc

tracemalloc.start(25)                    # keep 25 frames per allocation
before = tracemalloc.take_snapshot()
cache = [{"id": i, "text": "chunk " * 20} for i in range(50_000)]
after = tracemalloc.take_snapshot()
for stat in after.compare_to(before, "lineno")[:3]:
    print(stat)
current, peak = tracemalloc.get_traced_memory()
print(f"current {current / 2**20:.1f} MiB, peak {peak / 2**20:.1f} MiB")
tracemalloc.stop()
```

tracemalloc sees Python allocations only (not numpy/torch buffers allocated outside PyMem, depending on the
library). Use RSS (`resource.getrusage`, `psutil`) and Scalene for the whole picture.

## 11. sys.monitoring (3.12+)

PEP 669 gives low-overhead event hooks that can be switched on and off per code location; good for custom
call counters in long-running services where cProfile is too heavy.

```python
import sys
from collections import Counter

calls = Counter()
TOOL = sys.monitoring.PROFILER_ID
sys.monitoring.use_tool_id(TOOL, "call-counter")


def on_start(code, instruction_offset):
    calls[code.co_qualname] += 1         # co_qualname: 3.11+


sys.monitoring.register_callback(TOOL, sys.monitoring.events.PY_START, on_start)
sys.monitoring.set_events(TOOL, sys.monitoring.events.PY_START)


def normalize(s):
    return " ".join(s.split())


for doc in ["a  b", "c   d"] * 1000:
    normalize(doc)

sys.monitoring.set_events(TOOL, 0)
sys.monitoring.free_tool_id(TOOL)
print(calls.most_common(2))
```

Return `sys.monitoring.DISABLE` from a callback to stop events for that location: cost drops to zero after
the first hit, which makes "which functions ever run?" coverage-style questions cheap.

## 12. Choosing a profiler

| Need | First choice | Second |
|------|-------------|--------|
| Where is time going, quick | py-spy record | cProfile |
| Prod process, no restart | py-spy (attach by PID) | perf |
| Python vs native vs system split | Scalene | py-spy `--native` + profile_classify.py |
| Is the GIL held? | py-spy `--gil` | gil_probe.py |
| Threads waiting for the GIL | py-spy `--native --idle` (look for `take_gil`) | perf |
| Which line | line_profiler | Scalene |
| Timeline of threads/tasks | viztracer | py-spy `--threads` |
| Memory | tracemalloc + RSS | Scalene / memray |
| Cache misses, bandwidth | perf stat | Intel VTune / AMD uProf |
| Lightweight custom counters | sys.monitoring | logging + timers |

Newer CPython releases are adding a stdlib sampling profiler (the `profiling` package proposed in PEP 799,
targeted at 3.15); check your version's documentation before relying on it.

## 13. From profile to verdict with profile_classify.py

```bash
python scripts/profile_classify.py out.prof stacks.txt --top 10
```

1. Look at **Share of time**. GIL-held = pure-Python + native-hold + native-unknown.
2. Check the **notes**: no native frames means native time hides inside Python lines; cProfile means only one
   thread was seen.
3. Read the **verdict**: GIL-BOUND, GIL-CONTENDED, I/O-BOUND, GIL-RELEASING NATIVE, STARTUP-DOMINATED, MIXED.
4. Take the **top recommendation** whose confidence is high or medium, then confirm with `gil_probe.py` on the
   hot function.
5. In CI, gate with `--fail-if-python-cpu-over PCT` on a profile of a fixed benchmark input.
