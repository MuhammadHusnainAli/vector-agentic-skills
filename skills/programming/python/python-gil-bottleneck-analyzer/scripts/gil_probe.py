#!/usr/bin/env python3
"""Measure whether a workload scales with threads, processes or sub-interpreters.

WARNING: this script EXECUTES CODE. With --target it imports your module and calls
your function many times (serially, in N threads, in N worker processes and, with
--interpreters on Python 3.14+, in N sub-interpreters). Only point it at code you
trust and that is safe to run repeatedly. --builtin runs synthetic workloads that
ship with this script.

Everything runs in a child process placed in its own process group/session; the
parent enforces --timeout and hard-kills the whole group (child, pool workers,
forkserver) when it expires or on Ctrl-C, so a hung workload cannot outlive the probe.

For each mode it runs N tasks (N = --workers), keeps the best of --repeat runs, and
reports wall time, process CPU time, CPU/wall ratio (how many cores were busy),
per-worker CPU, and speedup over serial. It then classifies the workload:

  I/O-bound                                    mostly waiting; threads/asyncio scale
  releases the GIL                             CPU-heavy and threads scale
  GIL-bound: scales with processes, not threads
  likely GIL-bound                             threads never overlapped, processes did not scale
                                               either (busy machine: low confidence, re-run)
  mixed I/O + CPU                              waits overlap, the CPU part serialises
  CPU-bound, does not scale                    threads keep cores busy but no speedup
                                               (memory bandwidth, lock contention, false sharing)
  inconclusive                                 too few workers or ambiguous numbers; re-run

and reports the interpreter: GIL build or free-threaded, and sys._is_gil_enabled().

Built-in workloads (--builtin): pure-python (Python loop), native-release (hashlib on
1 MiB buffers; releases the GIL), native-hold (re.findall; C code holding the GIL),
io (time.sleep), mixed (half Python loop, half sleep).

Exit codes: 0 measured, 1 --fail-if-gil-bound and the workload is GIL-bound,
2 usage error, target import/call error, or --timeout expired, 130 Ctrl-C.

Examples:
    python gil_probe.py --builtin pure-python
    python gil_probe.py --builtin io --workers 8 --repeat 2 --json
    python gil_probe.py --target mypkg.text:clean_doc --arg '"some text"' --arg 3 --timeout 120
    python gil_probe.py --target ./bench.py:score_batch --arg 2000 --interpreters
"""

import argparse
import ast
import json
import os
import signal
import subprocess
import sys
import tempfile
import time

EXIT_OK, EXIT_GATE, EXIT_ERROR = 0, 1, 2
BUILTINS = ("pure-python", "native-release", "native-hold", "io", "mixed")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ----------------------------------------------------------------------------- workloads

def _py_loop(n):
    acc = 0
    for i in range(n):
        acc += (i * i) % 7
    return acc


def builtin_workload(name, scale):
    """Run one unit of a built-in workload (about 0.1-0.2 s on a modern core at scale 1)."""
    if name == "pure-python":
        return _py_loop(int(3_000_000 * scale))
    if name == "native-release":
        import hashlib

        buf = bytes(range(256)) * 4096  # 1 MiB: hashlib releases the GIL for inputs > 2 KiB
        digest = b""
        for _ in range(int(250 * scale)):
            digest = hashlib.sha256(buf).digest()
        return digest.hex()
    if name == "native-hold":
        import re

        text = "alpha beta gamma, delta! 123 epsilon zeta\n" * 40_000
        pattern = re.compile(r"(\w+)\s+(\w+)")
        found = 0
        for _ in range(max(1, int(3 * scale))):
            found += len(pattern.findall(text))
        return found
    if name == "io":
        time.sleep(0.15 * scale)
        return None
    if name == "mixed":
        _py_loop(int(1_500_000 * scale))
        time.sleep(0.08 * scale)
        return None
    raise ValueError(f"unknown builtin workload {name!r}")


_TARGET_CACHE = {}


def resolve_target(spec, cwd):
    """Import 'module:function' or 'path/to/file.py:function' and return the callable."""
    if spec in _TARGET_CACHE:
        return _TARGET_CACHE[spec]
    import importlib
    import importlib.util

    if ":" not in spec:
        raise ValueError(f"--target must look like module:function or file.py:function, got {spec!r}")
    mod_part, func_name = spec.rsplit(":", 1)
    if cwd and cwd not in sys.path:
        sys.path.insert(0, cwd)
    if mod_part.endswith(".py") or os.sep in mod_part or "/" in mod_part:
        path = mod_part if os.path.isabs(mod_part) else os.path.join(cwd or os.getcwd(), mod_part)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"target file not found: {path}")
        mod_name = "_gil_probe_target_" + os.path.splitext(os.path.basename(path))[0].replace("-", "_")
        module = sys.modules.get(mod_name)
        if module is None:
            spec_obj = importlib.util.spec_from_file_location(mod_name, path)
            module = importlib.util.module_from_spec(spec_obj)
            sys.modules[mod_name] = module
            spec_obj.loader.exec_module(module)
    else:
        module = importlib.import_module(mod_part)
    func = module
    for attr in func_name.split("."):
        func = getattr(func, attr)
    if not callable(func):
        raise TypeError(f"{spec} is not callable")
    _TARGET_CACHE[spec] = func
    return func


def run_task(job):
    """Run one unit of work; return (wall_s, thread_cpu_s). Module-level so it pickles by reference."""
    kind, name, args, scale, cwd = job
    fn = None
    if kind == "target":
        fn = resolve_target(name, cwd)
    wall0, cpu0 = time.perf_counter(), time.thread_time()
    if kind == "builtin":
        builtin_workload(name, scale)
    else:
        fn(*args)
    return time.perf_counter() - wall0, time.thread_time() - cpu0


def _warm(_):
    time.sleep(0.05)
    return os.getpid()


# ----------------------------------------------------------------------------- measurement (child)

def measure_serial(job, n):
    wall0, cpu0 = time.perf_counter(), time.process_time()
    per = [run_task(job) for _ in range(n)]
    return wall0, cpu0, per


def measure_threads(job, n):
    import threading

    results = [None] * n
    errors = []
    barrier = threading.Barrier(n + 1)

    def worker(i):
        try:
            barrier.wait()
            results[i] = run_task(job)
        except BaseException as err:  # reported to the parent, never swallowed
            errors.append(err)

    threads = [threading.Thread(target=worker, args=(i,), daemon=True, name=f"probe-{i}") for i in range(n)]
    for t in threads:
        t.start()
    wall0, cpu0 = time.perf_counter(), time.process_time()
    barrier.wait()
    for t in threads:
        t.join()
    if errors:
        raise errors[0]
    return wall0, cpu0, results


def measure_pool(executor, job, n):
    list(executor.map(_warm, range(n)))  # start every worker before timing
    wall0, cpu0 = time.perf_counter(), time.process_time()
    futures = [executor.submit(run_task, job) for _ in range(n)]
    per = [f.result() for f in futures]
    return wall0, cpu0, per


def run_mode(mode, job, n, repeat):
    import concurrent.futures as cf

    samples = []
    executor = None
    try:
        if mode == "processes":
            import multiprocessing as mp

            method = "forkserver" if "forkserver" in mp.get_all_start_methods() else "spawn"
            executor = cf.ProcessPoolExecutor(max_workers=n, mp_context=mp.get_context(method))
        elif mode == "interpreters":
            executor = cf.InterpreterPoolExecutor(max_workers=n)
        for _ in range(repeat):
            if mode == "serial":
                wall0, cpu0, per = measure_serial(job, n)
            elif mode == "threads":
                wall0, cpu0, per = measure_threads(job, n)
            else:
                wall0, cpu0, per = measure_pool(executor, job, n)
            wall = time.perf_counter() - wall0
            proc_cpu = time.process_time() - cpu0
            worker_cpu = [round(c, 4) for _w, c in per]
            cpu = sum(worker_cpu) if mode in ("processes", "interpreters") else proc_cpu
            samples.append({"wall": wall, "cpu": cpu, "worker_cpu": worker_cpu,
                            "task_wall": [round(w, 4) for w, _c in per]})
    finally:
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)
    best = min(samples, key=lambda s: s["wall"])
    walls = sorted(s["wall"] for s in samples)
    return {"mode": mode, "wall_s": round(best["wall"], 4), "median_wall_s": round(walls[len(walls) // 2], 4),
            "cpu_s": round(best["cpu"], 4), "cpu_per_wall": round(best["cpu"] / best["wall"], 2) if best["wall"]
            else 0.0, "worker_cpu_s": best["worker_cpu"], "task_wall_s": best["task_wall"], "runs": len(samples)}


def interpreter_info():
    import platform
    import sysconfig

    gil_fn = getattr(sys, "_is_gil_enabled", None)
    return {"python": platform.python_version(), "implementation": platform.python_implementation(),
            "free_threaded_build": bool(sysconfig.get_config_var("Py_GIL_DISABLED")),
            "gil_enabled": gil_fn() if gil_fn else True, "switch_interval_s": sys.getswitchinterval(),
            "cpu_count": os.cpu_count(), "usable_cpus": usable_cpus()}


def usable_cpus():
    try:
        return len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        return os.cpu_count() or 1


def cpu_availability():
    """Share of one core this process actually gets right now (1.0 idle, lower when the machine is busy)."""
    ratios = []
    for _ in range(7):
        wall0, cpu0 = time.perf_counter(), time.process_time()
        _py_loop(1_000_000)
        wall = time.perf_counter() - wall0
        if wall > 0:
            ratios.append((time.process_time() - cpu0) / wall)
    ratios.sort()
    return round(min(1.0, max(ratios[len(ratios) // 2] if ratios else 1.0, 0.05)), 2)


def classify(modes, n, avail=1.0):
    """Label the workload from speedups and CPU/wall ratios (ratios are robust to a busy machine)."""
    serial, threads = modes["serial"], modes["threads"]
    procs = modes.get("processes") if "wall_s" in modes.get("processes", {}) else None
    s_t = serial["wall_s"] / threads["wall_s"] if threads["wall_s"] else 0.0
    s_p = serial["wall_s"] / procs["wall_s"] if procs and procs["wall_s"] else None
    ser_ratio = serial["cpu_per_wall"]
    cpu_norm = ser_ratio / avail if avail else ser_ratio
    scale_bar = max(1.5, 0.4 * n)
    if n < 2:
        return "inconclusive: need --workers >= 2", "low"
    if cpu_norm < 0.25:
        if s_t >= max(1.5, 0.5 * n):
            return "I/O-bound: threads and asyncio scale (waiting, not computing)", "high"
        return "I/O-bound but threads did not overlap the waits (shared lock or serial resource?)", "medium"
    if cpu_norm <= 0.7:
        return ("mixed I/O + CPU: threads overlap the waits, the CPU part still serialises on the GIL"
                if s_t > 1.2 else "mixed I/O + CPU: no thread speedup"), "medium"
    # CPU-bound: how many more cores did threads / processes keep busy than the serial run?
    p_t = threads["cpu_per_wall"] / ser_ratio
    p_p = procs["cpu_per_wall"] / ser_ratio if procs else None
    if p_t >= 1.4:
        if s_t >= scale_bar:
            return "releases the GIL: CPU-bound and threads scale", "high"
        if s_t >= 1.2:
            return "releases the GIL: threads scale (limited by free cores)", "medium"
        return ("CPU-bound, does not scale: threads keep cores busy without speedup (memory bandwidth, lock "
                "contention or false sharing)"), "medium"
    if p_t < 1.2:
        if p_p is None:
            return "GIL-bound: threads run one at a time (processes not measured)", "medium"
        if p_p >= 1.25:
            return ("GIL-bound: scales with processes but not threads",
                    "high" if s_p is not None and s_p >= scale_bar else "medium")
        return ("likely GIL-bound: threads never ran in parallel, but processes did not scale either, so the "
                "machine may be too busy to tell; re-run on an idle machine"), "low"
    return "inconclusive: threads ran partly in parallel; re-run with --repeat 5 on an idle machine", "low"


def child_main(cfg_path):
    with open(cfg_path) as fh:
        cfg = json.load(fh)
    out_path = cfg["out"]
    result = {"interpreter": interpreter_info()}
    try:
        sys.path.insert(0, SCRIPT_DIR)
        import gil_probe as me  # import by name so workers and sub-interpreters can unpickle run_task

        job = tuple(cfg["job"])
        if job[0] == "target":
            try:
                me.resolve_target(job[1], job[4])  # fail fast on import errors
            except Exception as err:
                raise ProbeError(f"cannot load target {job[1]}: {type(err).__name__}: {err}") from err
        n, repeat = cfg["workers"], cfg["repeat"]
        avail = me.cpu_availability()
        result["interpreter"]["cpu_availability"] = avail
        modes = {}
        for mode in ["serial", "threads", "processes"] + (["interpreters"] if cfg["interpreters"] else []):
            if mode == "interpreters" and sys.version_info < (3, 14):
                modes[mode] = {"mode": mode, "error": "InterpreterPoolExecutor needs Python 3.14+"}
                continue
            try:
                modes[mode] = me.run_mode(mode, job, n, repeat)
            except Exception as err:
                if mode in ("serial", "threads"):
                    raise ProbeError(f"workload raised during the {mode} run: {type(err).__name__}: {err}") from err
                modes[mode] = {"mode": mode, "error": f"{type(err).__name__}: {err}"[:400]}
        for m in modes.values():
            if "wall_s" in m and m["mode"] != "serial":
                m["speedup"] = round(modes["serial"]["wall_s"] / m["wall_s"], 2) if m["wall_s"] else None
        label, confidence = me.classify(modes, n, avail)
        result.update({"modes": modes, "classification": label, "confidence": confidence})
    except ProbeError as err:
        result["error"] = str(err)
    except BaseException as err:
        result["error"] = f"{type(err).__name__}: {err}"
    with open(out_path, "w") as fh:
        json.dump(result, fh)
    return 0


# ----------------------------------------------------------------------------- parent

class ProbeError(Exception):
    """A failure reported to the user as a one-line message."""


def kill_group(proc):
    """Kill the child and everything in its process group (pool workers, forkserver)."""
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, check=False)
    except (ProcessLookupError, PermissionError, OSError):
        pass
    if proc.poll() is None:
        try:
            proc.kill()
        except OSError:
            pass
        proc.wait()


def parse_arg_value(text):
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text


def advice(label, info):
    if label.startswith("I/O-bound"):
        return ["Use asyncio with a Semaphore (or a ThreadPoolExecutor) to overlap the waits; processes add "
                "nothing (python-asyncio-pattern-advisor)."]
    if label.startswith("releases the GIL"):
        return ["Threads are fine: ThreadPoolExecutor(max_workers≈cores); cap library thread pools "
                "(OMP_NUM_THREADS, torch.set_num_threads) so they do not oversubscribe."]
    if label.startswith("likely GIL-bound"):
        return ["Re-run with --repeat 5 when the machine is idle (check the CPU availability line); if threads "
                "still show no speedup while processes do, treat it as GIL-bound."]
    if label.startswith("GIL-bound"):
        tips = ["Use processes for this function (python-multiprocessing-pool-designer), or move the loop into "
                "native code that releases the GIL (numpy, numba nogil=True, Cython nogil, Rust allow_threads)."]
        if not info.get("free_threaded_build"):
            tips.append("Or try a free-threaded build (python3.14t) where pure-Python threads run in parallel, "
                        "if every extension you import supports it.")
        return tips
    if label.startswith("mixed"):
        return ["Split the stages: asyncio/threads for the waits, a process pool for the CPU part "
                "(loop.run_in_executor(process_pool, fn))."]
    if label.startswith("CPU-bound, does not scale"):
        return ["Look for a shared lock, memory-bandwidth limits (large arrays) or oversubscribed native thread "
                "pools; measure with perf stat and fewer workers."]
    return ["Re-run with --workers >= 2 and --repeat 3 on an idle machine."]


def render(res, args):
    info = res["interpreter"]
    lines = [f"gil_probe: {args.target or args.builtin}  (workers={args.workers}, repeat={args.repeat})",
             f"Interpreter: Python {info['python']} ({info['implementation']}), "
             f"{'free-threaded build' if info['free_threaded_build'] else 'GIL build'}, "
             f"GIL {'enabled' if info['gil_enabled'] else 'DISABLED'} at runtime, "
             f"switch interval {info['switch_interval_s'] * 1000:.1f} ms, usable CPUs {info['usable_cpus']}",
             f"CPU availability: {info.get('cpu_availability', 1.0) * 100:.0f}% of one core"
             + ("  (machine is busy: speedups will be understated)" if info.get("cpu_availability", 1.0) < 0.9
                else ""),
             "",
             f"  {'mode':<13}{'wall s':>9}{'median s':>10}{'cpu s':>9}{'cpu/wall':>10}{'speedup':>9}  per-worker cpu s"]
    for m in res["modes"].values():
        if "error" in m:
            lines.append(f"  {m['mode']:<13} unavailable: {m['error']}")
            continue
        sp = f"{m['speedup']:.2f}x" if m.get("speedup") else "1.00x"
        lines.append(f"  {m['mode']:<13}{m['wall_s']:>9.3f}{m['median_wall_s']:>10.3f}{m['cpu_s']:>9.3f}"
                     f"{m['cpu_per_wall']:>10.2f}{sp:>9}  {', '.join(f'{c:.3f}' for c in m['worker_cpu_s'])}")
    lines += ["", f"Classification: {res['classification']}  (confidence: {res['confidence']})"]
    lines += [f"Next step: {tip}" for tip in advice(res["classification"], info)]
    lines.append("Note: timings are noisy on shared machines; trust ratios and repeat on an idle box before "
                 "deciding.")
    return "\n".join(lines)


def build_parser():
    p = argparse.ArgumentParser(
        prog="gil_probe.py",
        description="EXECUTES CODE: runs a workload serially, in N threads, in N processes and optionally in N "
                    "sub-interpreters (3.14+), measures wall/CPU time and speedup, and classifies it as GIL-bound, "
                    "GIL-releasing, I/O-bound or mixed. Only use --target with code you trust. The run happens in "
                    "a child process group that is hard-killed after --timeout seconds.",
        epilog="Exit codes: 0 measured, 1 --fail-if-gil-bound gate failed, 2 usage/target error or timeout.")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--target", metavar="MODULE:FUNC",
                     help="function to run: package.module:func or path/to/file.py:func (imported and called)")
    src.add_argument("--builtin", choices=BUILTINS, help="built-in synthetic workload")
    p.add_argument("--arg", action="append", default=[], metavar="VALUE",
                   help="positional argument for --target (Python literal, else a string); repeatable")
    p.add_argument("--workers", type=int, default=None,
                   help="threads/processes/interpreters and tasks per run (default max(2, min(4, usable CPUs)))")
    p.add_argument("--repeat", type=int, default=3, help="runs per mode; the fastest is reported (default 3)")
    p.add_argument("--scale", type=float, default=1.0, help="work multiplier for --builtin (default 1.0)")
    p.add_argument("--interpreters", action="store_true",
                   help="also measure concurrent.futures.InterpreterPoolExecutor (Python 3.14+)")
    p.add_argument("--timeout", type=float, default=300.0,
                   help="hard limit in seconds for the whole probe; everything is killed after it (default 300)")
    p.add_argument("--fail-if-gil-bound", action="store_true",
                   help="CI gate: exit 1 when the classification is GIL-bound")
    p.add_argument("--json", action="store_true", help="emit JSON instead of text")
    p.add_argument("--_child", help=argparse.SUPPRESS)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args._child:
        return child_main(args._child)
    if not (args.target or args.builtin):
        parser.error("one of the arguments --target --builtin is required")
    if args.workers is None:
        args.workers = max(2, min(4, usable_cpus()))
    if not 1 <= args.workers <= 256:
        parser.error("--workers must be between 1 and 256")
    if not 1 <= args.repeat <= 50:
        parser.error("--repeat must be between 1 and 50")
    if args.timeout <= 0:
        parser.error("--timeout must be > 0")
    if args.scale <= 0:
        parser.error("--scale must be > 0")
    if args.arg and not args.target:
        parser.error("--arg only applies to --target")
    if args.target and ":" not in args.target:
        parser.error("--target must look like module:function or path/to/file.py:function")
    job = (["target", args.target, [parse_arg_value(a) for a in args.arg], 1.0, os.getcwd()] if args.target
           else ["builtin", args.builtin, [], args.scale, os.getcwd()])

    tmpdir = tempfile.mkdtemp(prefix="gil_probe_")
    cfg_path, out_path = os.path.join(tmpdir, "cfg.json"), os.path.join(tmpdir, "out.json")
    with open(cfg_path, "w") as fh:
        json.dump({"job": job, "workers": args.workers, "repeat": args.repeat,
                   "interpreters": args.interpreters, "out": out_path}, fh)
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"   # do not leave __pycache__ next to this script or the target
    env["PYTHONPATH"] = os.pathsep.join([SCRIPT_DIR, os.getcwd()] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH")
                                                                      else []))
    popen_kw = {"start_new_session": True} if os.name == "posix" else {
        "creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    # the workload's own prints go to stderr so --json output stays clean
    proc = subprocess.Popen([sys.executable, os.path.abspath(__file__), "--_child", cfg_path],
                            stdout=sys.stderr.fileno(), env=env, **popen_kw)
    try:
        proc.wait(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        kill_group(proc)
        print(f"gil_probe.py: error: timed out after {args.timeout:g}s; killed the probe and all its workers",
              file=sys.stderr)
        return EXIT_ERROR
    except KeyboardInterrupt:
        kill_group(proc)
        print("gil_probe.py: interrupted; killed the probe and all its workers", file=sys.stderr)
        return 130
    finally:
        kill_group(proc)  # also reaps stragglers left in the group (e.g. a forkserver)
    try:
        with open(out_path) as fh:
            res = json.load(fh)
    except (OSError, ValueError):
        print(f"gil_probe.py: error: probe process exited with code {proc.returncode} without a result",
              file=sys.stderr)
        return EXIT_ERROR
    finally:
        for path in (cfg_path, out_path):
            try:
                os.unlink(path)
            except OSError:
                pass
        try:
            os.rmdir(tmpdir)
        except OSError:
            pass
    if "error" in res:
        print(f"gil_probe.py: error: {res['error']}", file=sys.stderr)
        return EXIT_ERROR
    res["advice"] = advice(res["classification"], res["interpreter"])
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(render(res, args))
    if args.fail_if_gil_bound and "GIL-bound" in res["classification"]:
        return EXIT_GATE
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
