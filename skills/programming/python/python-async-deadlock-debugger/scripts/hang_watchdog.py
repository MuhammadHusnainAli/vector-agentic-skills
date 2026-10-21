#!/usr/bin/env python3
"""Run a Python script or module under a hang watchdog; dump every thread and asyncio task stack.

THIS TOOL EXECUTES CODE. `hang_watchdog.py app.py ARGS` runs app.py, and
`hang_watchdog.py -m pkg.module ARGS` runs a module, in a child Python process
(its own process group / session) with a small bootstrap in front of it. The
bootstrap:
  - registers faulthandler on SIGUSR1 (C-level dump of all threads, works even
    when the GIL is held by a stuck C extension) and enables it for fatal errors;
  - starts a daemon "dumper" thread that, on request from the watchdog, prints
    every thread (sys._current_frames + names) and every asyncio task of every
    open event loop, with the full await chain of each task and what it is
    waiting on. Tasks are collected inside the loop thread via
    call_soon_threadsafe; if the loop does not answer within 0.5 s the loop is
    reported as BLOCKED by synchronous code and tasks are read from outside.

The watchdog dumps when `--dump-after SECONDS` elapses or when the child shows
no progress (no stdout/stderr output and no heartbeat()) for `--idle SECONDS`.
`--kill-after SECONDS` is a hard timeout (default 600): the whole process group
gets SIGTERM, then SIGKILL after `--grace`. The group is also killed when the
target exits normally (leftover grandchildren) or when the watchdog itself is
interrupted, so no orphaned processes remain; on Linux the child also gets
PR_SET_PDEATHSIG so it dies if the watchdog is SIGKILLed. A grandchild that
calls setsid() itself escapes the group: that is the one case it cannot cover.

Usage:
    python hang_watchdog.py --dump-after 30 --kill-after 120 eval_harness.py --shard 3
    python hang_watchdog.py --idle 60 --kill-after 3600 -m myproj.embed_job --batch 512
    python hang_watchdog.py --dump-after 1 --kill-after 3 --json deadlock.py > report.json
    python hang_watchdog.py --kill-after 900 --dump-file hang.txt --fail-on-dump -- train.py --epochs 1

Options must come before the target; everything after the script path (or
after `-m MODULE`, or after `--`) is passed to the target unchanged.

Library use (inside your own app; no child process involved):
    from hang_watchdog import install, dump_all, heartbeat
    install()                 # `kill -USR1 <pid>` now prints threads + asyncio tasks to stderr
    install(dump_after=300)   # also dump automatically once after 300 s
    heartbeat()               # mark progress when running under --idle

Exit codes: 0 the target exited with status 0; 1 the target exited non-zero;
2 usage error (bad flag, missing script, unsupported platform); 3 the target
hung and was killed (or was dumped, with --fail-on-dump); 130 interrupted.

POSIX only (Linux, macOS). Standard library only, Python 3.9+.
"""

import argparse
import faulthandler
import gc
import json
import linecache
import os
import select
import signal
import subprocess
import sys
import sysconfig
import tempfile
import threading
import time

ENV_CTL = "HANG_WATCHDOG_CTL_FD"
ENV_TASKS = "HANG_WATCHDOG_DUMP_FILE"
ENV_THREADS = "HANG_WATCHDOG_THREADS_FILE"
ENV_HEARTBEAT = "HANG_WATCHDOG_HEARTBEAT"
ENV_PARENT = "HANG_WATCHDOG_PARENT_PID"
CHILD_FLAG = "--_hang_watchdog_child"
DUMPER_NAME = "hang-watchdog-dumper"
_STDLIB = tuple({os.path.normcase(p) for p in (sysconfig.get_paths().get("stdlib"),
                                               sysconfig.get_paths().get("platstdlib")) if p})

_SELF = os.path.normcase(os.path.abspath(__file__))

__all__ = ["install", "dump_all", "format_threads", "format_tasks", "heartbeat", "Dumper"]


# =============================================================== formatting (library + child)

def _is_stdlib(filename):
    f = os.path.normcase(filename or "")
    return f.startswith(_STDLIB) and "site-packages" not in f or f.startswith("<frozen")


def _frame_line(frame, lineno=None):
    code = frame.f_code
    lineno = lineno or frame.f_lineno
    src = linecache.getline(code.co_filename, lineno).strip()
    text = f'  File "{code.co_filename}", line {lineno}, in {code.co_name}\n'
    return text + (f"    {src}\n" if src else "")


def _short(frame):
    code = frame.f_code
    src = linecache.getline(code.co_filename, frame.f_lineno).strip()
    return f"{os.path.basename(code.co_filename)}:{frame.f_lineno} in {code.co_name}: {src}"


def _blocking_kind(src, filename):
    s = src.replace(" ", "")
    if ".acquire(" in s or (s.startswith(("with", "asyncwith")) and ("lock" in s.lower() or "sem" in s.lower())):
        return "lock acquire"
    for needle, kind in ((".join(", "join"), (".result(", "future result"), (".get(", "queue get"),
                         (".put(", "queue put"), (".wait(", "wait"), ("sleep(", "sleep"),
                         (".select(", "idle in select"), (".poll(", "idle in poll"), (".recv", "socket read"),
                         (".read(", "read")):
        if needle in s:
            return kind
    if os.path.basename(filename) in ("selectors.py", "base_events.py"):
        return "event loop idle"
    return "running"


def format_threads(skip_current=True):
    """All threads with names, daemon flag and stacks (most recent call last), plus a one-line summary each."""
    import traceback
    frames = sys._current_frames()
    by_id = {t.ident: t for t in threading.enumerate()}
    me = threading.get_ident()
    summary, detail = [], []
    for tid, frame in frames.items():
        t = by_id.get(tid)
        if skip_current and tid == me:
            continue
        if t is not None and t.name == DUMPER_NAME:
            continue
        label = f"thread {t.name!r}" if t else f"thread {tid:#x}"
        flags = (" daemon" if t and t.daemon else "") + (" main" if t is threading.main_thread() else "")
        top = frame
        user = frame
        while user is not None and _is_stdlib(user.f_code.co_filename):
            user = user.f_back
        user = user or top
        kind = _blocking_kind(linecache.getline(user.f_code.co_filename, user.f_lineno).strip(),
                              user.f_code.co_filename)
        if kind == "running" and user is not top:
            kind = _blocking_kind(linecache.getline(top.f_code.co_filename, top.f_lineno).strip(),
                                  top.f_code.co_filename)
        where = _short(user)
        if user is not top:
            where += f"  (inside {_short(top)})"
        summary.append(f"{label}{flags}: {where}   [{kind}]")
        stack = [fs for fs in traceback.extract_stack(frame) if not _is_bootstrap(fs.filename)]
        detail.append(f"{label} id={tid:#x}{flags} (most recent call last):\n"
                      + "".join(traceback.format_list(stack)))
    order = sorted(range(len(summary)), key=lambda i: " main" not in summary[i].split(":", 1)[0])
    return "\n".join(summary[i] for i in order), "\n".join(detail[i] for i in order)


def _is_bootstrap(filename):
    """Frames of this file and of runpy, shown in the child only because the target runs under them."""
    return filename == "<frozen runpy>" or os.path.normcase(os.path.abspath(filename)) == _SELF


def _await_chain(coro):
    """Frames of a coroutine and everything it awaits, outermost first, plus the leaf awaitable."""
    frames, obj, leaf = [], coro, None
    for _ in range(200):
        frame = getattr(obj, "cr_frame", None) or getattr(obj, "gi_frame", None) or getattr(obj, "ag_frame", None)
        if frame is not None:
            frames.append(frame)
        nxt = getattr(obj, "cr_await", None)
        if nxt is None:
            nxt = getattr(obj, "gi_yieldfrom", None)
        if nxt is None:
            nxt = getattr(obj, "ag_await", None)
        if nxt is None:
            break
        if not any(hasattr(nxt, a) for a in ("cr_frame", "gi_frame", "ag_frame")):
            leaf = nxt
            break
        obj = nxt
    return frames, leaf


def _name_of(obj, frames):
    """Best-effort variable name for a sync primitive, looked up in the awaiting user frames."""
    for frame in reversed(frames):
        if _is_stdlib(frame.f_code.co_filename):
            continue
        try:
            scopes = [frame.f_locals, frame.f_globals]
            owner = frame.f_locals.get("self")
            if owner is not None and hasattr(owner, "__dict__"):
                scopes.insert(1, {"self." + k: v for k, v in vars(owner).items()})
        except Exception:  # noqa: BLE001
            continue
        for scope in scopes:
            for k, v in list(scope.items()):
                if v is obj:
                    return f"`{k}` "
    return ""


def _describe_waiter(task, frames, asyncio):
    prims = tuple(getattr(asyncio, n) for n in ("Lock", "Semaphore", "Event", "Condition", "Queue")
                  if hasattr(asyncio, n))
    for frame in reversed(frames):
        try:
            obj = frame.f_locals.get("self")
        except Exception:  # noqa: BLE001 - frame proxies can fail during teardown
            obj = None
        if prims and isinstance(obj, prims):
            return f"{_name_of(obj, frames)}{repr(obj)[:160]}"
    waiter = getattr(task, "_fut_waiter", None)
    if waiter is None:
        return ""
    if isinstance(waiter, asyncio.Task):
        return f"task {waiter.get_name()!r}"
    children = getattr(waiter, "_children", None)
    if children:
        names = []
        for c in children:
            state = "done" if c.done() else "pending"
            names.append(f"{c.get_name()!r} ({state})" if hasattr(c, "get_name") else repr(c)[:60])
        return "gather of " + ", ".join(names)
    return repr(waiter)[:160]


def _format_loop_tasks(loop, asyncio, responsive):
    tasks = []
    for _ in range(10):
        try:
            tasks = list(asyncio.all_tasks(loop))
            break
        except RuntimeError:  # set changed size during iteration (read from another thread)
            time.sleep(0.01)
    try:
        current = asyncio.current_task(loop)
    except Exception:  # noqa: BLE001
        current = None
    summary, detail = [], []
    for task in sorted(tasks, key=lambda t: t.get_name()):
        frames, leaf = _await_chain(task.get_coro())
        user = [f for f in frames if not _is_stdlib(f.f_code.co_filename)]
        anchor = (user or frames or [None])[-1]
        where = _short(anchor) if anchor is not None else "(no frame)"
        if task is current:
            state = "RUNNING" + ("" if responsive else " and blocking the loop")
        elif task.done():
            state = "done"
        else:
            state = "waiting"
        waits = _describe_waiter(task, frames, asyncio) if task is not current else ""
        line = f"task {task.get_name()!r} [{state}]: {where}"
        if waits:
            line += f"\n    awaiting {waits}"
        summary.append(line)
        body = "".join(_frame_line(f) for f in frames) or "  (no Python frames)\n"
        if leaf is not None and "FutureIter" not in type(leaf).__name__:
            body += f"  -> awaiting {repr(leaf)[:160]}\n"
        detail.append(f"task {task.get_name()!r} [{state}] coro={getattr(task.get_coro(), '__qualname__', '?')}"
                      f" (outermost first):\n{body}")
    return tasks, "\n".join(summary), "\n".join(detail)


def format_tasks(loop_timeout=0.5):
    """Summary and detail text for every open asyncio event loop in the process ('' if none)."""
    asyncio = sys.modules.get("asyncio")
    if asyncio is None:
        return "", ""
    loops = []
    for obj in gc.get_objects():
        try:
            if isinstance(obj, asyncio.AbstractEventLoop) and not obj.is_closed():
                loops.append(obj)
        except Exception:  # noqa: BLE001 - exotic objects in gc can raise on isinstance
            continue
    names = {t.ident: t.name for t in threading.enumerate()}
    summary, detail = [], []
    for loop in loops:
        running = loop.is_running()
        tid = getattr(loop, "_thread_id", None)
        responsive = None
        holder = {}
        if running and tid != threading.get_ident():
            done = threading.Event()

            def collect(loop=loop, holder=holder, done=done):
                try:
                    holder["out"] = _format_loop_tasks(loop, asyncio, True)
                finally:
                    done.set()
            try:
                loop.call_soon_threadsafe(collect)
                responsive = done.wait(loop_timeout)
            except RuntimeError:
                responsive = False
        if "out" in holder:
            tasks, s, d = holder["out"]
        else:
            tasks, s, d = _format_loop_tasks(loop, asyncio, responsive is not False)
        where = f"thread {names.get(tid, tid)!r}" if tid else "no thread"
        if not running:
            state = "not running"
        elif responsive:
            state = "responsive (every task is suspended: look at what each one awaits)"
        else:
            state = (f"BLOCKED: did not run a callback within {loop_timeout}s; synchronous code is running "
                     "in the loop thread (see its thread stack)")
        head = f"event loop {type(loop).__name__} in {where}: {state}; {len(tasks)} task(s)"
        summary.append(head + ("\n" + s if s else ""))
        detail.append(head + ("\n" + d if d else ""))
    return "\n".join(summary), "\n".join(detail)


def dump_all(file=None, reason="manual", n=None, loop_timeout=0.5):
    """Build (and write to `file`, default stderr) a dump of all threads and asyncio tasks. Returns the text."""
    tag = f" {n}" if n is not None else ""
    t_sum, t_det = format_threads()
    a_sum, a_det = format_tasks(loop_timeout)
    parts = [f"=== hang_watchdog dump{tag} pid={os.getpid()} reason: {reason} ===",
             "--- summary ---", t_sum or "(no other threads)"]
    if a_sum:
        parts.append(a_sum)
    parts += ["--- threads ---", t_det]
    if a_det:
        parts += ["--- asyncio tasks ---", a_det]
    parts.append(f"=== end hang_watchdog dump{tag} ===\n")
    text = "\n".join(parts)
    out = file if file is not None else sys.stderr
    try:
        out.write(text)
        out.flush()
    except (OSError, ValueError):
        pass
    return text


class Dumper:
    """Daemon thread that dumps on request (pipe/signal) or on a timer. Created by install()."""

    def __init__(self, file=None, read_fd=None, dump_after=None, interval=None, loop_timeout=0.5):
        self.file = file
        self.loop_timeout = loop_timeout
        self.dump_after = dump_after
        self.interval = interval
        if read_fd is None:
            self._r, self._w = os.pipe()
        else:
            self._r, self._w = read_fd, None
        self._closed = False
        self._count = 0
        self._after_done = False
        self._started = time.monotonic()
        self.thread = threading.Thread(target=self._run, name=DUMPER_NAME, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def request(self, reason="request"):
        """Ask the dumper thread for a dump (safe from any thread or a signal handler)."""
        if self._w is not None:
            try:
                os.write(self._w, (reason.replace("\n", " ") + "\n").encode())
            except OSError:
                pass

    def close(self):
        self._closed = True
        if self._w is not None:
            try:
                os.close(self._w)
            except OSError:
                pass
            self._w = None

    def _next_timeout(self):
        now = time.monotonic() - self._started
        due = []
        if self.dump_after is not None and not self._after_done:
            due.append(self.dump_after - now)
        if self.interval:
            due.append(self.interval - (now % self.interval))
        return max(0.0, min(due)) if due else None

    def _run(self):
        buf = b""
        while not self._closed:
            try:
                ready, _, _ = select.select([self._r], [], [], self._next_timeout())
            except (OSError, ValueError):
                return
            if not ready:
                self._count += 1
                if self.dump_after is not None and time.monotonic() - self._started >= self.dump_after - 0.01:
                    self._after_done = True
                dump_all(self.file, reason="timer", loop_timeout=self.loop_timeout)
                continue
            try:
                chunk = os.read(self._r, 4096)
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                words = line.decode(errors="replace").split(" ", 2)
                self._count += 1
                if words[0] == "dump" and len(words) >= 2:
                    dump_all(self.file, reason=words[2] if len(words) > 2 else "watchdog", n=words[1],
                             loop_timeout=self.loop_timeout)
                else:
                    dump_all(self.file, reason=" ".join(words), loop_timeout=self.loop_timeout)


_installed = None


def install(signum=getattr(signal, "SIGUSR1", None), file=None, dump_after=None, interval=None,
            loop_timeout=0.5, c_level_signal=None):
    """Enable on-demand thread + asyncio task dumps in the current process.

    signum:          Python-level signal that triggers a dump (default SIGUSR1; None to skip). The handler
                     only writes to a pipe; the dump runs in a daemon thread, so it is safe to use while
                     the loop or the main thread is stuck. Installing it must happen in the main thread.
    file:            where dumps go (default sys.stderr at dump time).
    dump_after:      dump once automatically after this many seconds.
    interval:        dump every N seconds (use sparingly: a periodic "where is everyone" log).
    c_level_signal:  also register faulthandler on this signal (e.g. signal.SIGUSR2) for a C-level thread
                     dump that works even when the GIL is held by a C extension.
    Also calls faulthandler.enable() so segfaults/aborts print tracebacks. Returns the Dumper.
    """
    global _installed
    if _installed is not None:
        return _installed
    if not faulthandler.is_enabled():
        faulthandler.enable(file=file or sys.stderr)
    dumper = Dumper(file=file, dump_after=dump_after, interval=interval, loop_timeout=loop_timeout).start()
    if signum is not None and threading.current_thread() is threading.main_thread():
        signal.signal(signum, lambda s, f: dumper.request(f"signal {s}"))
    if c_level_signal is not None:
        faulthandler.register(c_level_signal, file=file or sys.stderr, all_threads=True, chain=False)
    _installed = dumper
    return dumper


_last_beat = [0.0]


def heartbeat():
    """Mark progress for `hang_watchdog.py --idle` (no-op when not running under the watchdog)."""
    path = os.environ.get(ENV_HEARTBEAT)
    now = time.monotonic()
    if not path or now - _last_beat[0] < 0.2:
        return
    _last_beat[0] = now
    try:
        with open(path, "a"):
            pass
        os.utime(path, None)
    except OSError:
        pass


# =============================================================== child bootstrap

def _set_pdeathsig():
    if not sys.platform.startswith("linux"):
        return
    try:
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        libc.prctl(1, int(signal.SIGKILL), 0, 0, 0)  # PR_SET_PDEATHSIG
        parent = os.environ.get(ENV_PARENT)
        if parent and os.getppid() != int(parent):  # watchdog already gone
            os._exit(137)
    except Exception:  # noqa: BLE001 - best effort only
        pass


def _child_main(argv):
    import runpy
    mode, target, rest = argv[0], argv[1], argv[2:]
    ctl_fd = int(os.environ.pop(ENV_CTL))
    os.set_inheritable(ctl_fd, False)
    tasks_path = os.environ.pop(ENV_TASKS)
    threads_path = os.environ.pop(ENV_THREADS)
    _set_pdeathsig()
    os.environ.pop(ENV_PARENT, None)
    threads_fh = open(threads_path, "w", encoding="utf-8")
    faulthandler.register(signal.SIGUSR1, file=threads_fh, all_threads=True, chain=False)
    if not faulthandler.is_enabled():
        faulthandler.enable(file=sys.stderr)
    tasks_fh = open(tasks_path, "a", encoding="utf-8")
    Dumper(file=tasks_fh, read_fd=ctl_fd).start()
    if mode == "script":
        sys.argv = [target] + rest
        sys.path[0] = os.path.dirname(os.path.abspath(target))
        runpy.run_path(target, run_name="__main__")
    else:
        sys.argv = [target] + rest
        sys.path[0] = os.getcwd()
        runpy.run_module(target, run_name="__main__", alter_sys=True)


# =============================================================== watchdog (parent)

VALUE_OPTS = {"--dump-after", "--idle", "--kill-after", "--grace", "--max-dumps", "--dump-file", "--python",
              "--dump-timeout"}


def split_argv(argv):
    """Split argv into (watchdog options, mode, target, target args). mode is 'script', 'module' or None."""
    own, i = [], 0
    while i < len(argv):
        tok = argv[i]
        if tok == "--":
            if i + 1 < len(argv):
                return own, "script", argv[i + 1], argv[i + 2:]
            return own, None, None, []
        if tok == "-m":
            if i + 1 >= len(argv):
                own.append(tok)
                return own, None, None, []
            return own, "module", argv[i + 1], argv[i + 2:]
        if tok.startswith("-m") and len(tok) > 2 and not tok.startswith("--"):
            return own, "module", tok[2:], argv[i + 1:]
        if tok.startswith("-") and tok != "-":
            own.append(tok)
            if tok in VALUE_OPTS and i + 1 < len(argv):
                own.append(argv[i + 1])
                i += 1
            i += 1
            continue
        return own, "script", tok, argv[i + 1:]
    return own, None, None, []


def build_parser():
    ap = argparse.ArgumentParser(
        prog="hang_watchdog.py",
        usage="%(prog)s [options] (script.py | -m module | -- script.py) [target args ...]",
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dump-after", type=float, metavar="SECONDS",
                    help="dump all thread + task stacks once if the target is still running after SECONDS")
    ap.add_argument("--idle", type=float, metavar="SECONDS",
                    help="dump when the target produced no output and no heartbeat() for SECONDS "
                         "(repeats every SECONDS while idle, up to --max-dumps)")
    ap.add_argument("--kill-after", type=float, default=600.0, metavar="SECONDS",
                    help="hard timeout: dump (if not done yet) and kill the whole process group (default 600)")
    ap.add_argument("--grace", type=float, default=1.0, metavar="SECONDS",
                    help="SIGTERM -> SIGKILL grace period when killing (default 1)")
    ap.add_argument("--max-dumps", type=int, default=3, metavar="N", help="at most N dumps per run (default 3)")
    ap.add_argument("--dump-timeout", type=float, default=3.0, metavar="SECONDS",
                    help="wait this long for the in-process dumper before falling back to a C-level "
                         "faulthandler dump (default 3)")
    ap.add_argument("--dump-file", metavar="PATH", help="also append every dump to PATH")
    ap.add_argument("--python", default=sys.executable, metavar="EXE",
                    help="interpreter for the target (default: the one running this script)")
    ap.add_argument("--json", action="store_true",
                    help="print a JSON summary on stdout (target stdout is relayed to stderr)")
    ap.add_argument("--fail-on-dump", action="store_true",
                    help="exit 3 if any dump happened, even if the target later exited by itself")
    return ap


class Relay(threading.Thread):
    """Copy a child pipe to one of our streams and remember when output last arrived."""

    def __init__(self, src, dst, state):
        super().__init__(daemon=True)
        self.src, self.dst, self.state = src, dst, state

    def run(self):
        fd = self.src.fileno()
        while True:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                return
            if not chunk:
                return
            self.state["last_output"] = time.monotonic()
            try:
                self.dst.write(chunk)
                self.dst.flush()
            except (OSError, ValueError):
                pass


def _exited(proc):
    """Exit status if the child has exited, without reaping it (so its pgid stays reserved)."""
    waitid = getattr(os, "waitid", None)
    if waitid is None:
        return proc.poll()
    try:
        res = waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    except ChildProcessError:
        return proc.poll()
    if res is None:
        return None
    return res.si_status if res.si_code == os.CLD_EXITED else -res.si_status


def _killpg(pgid, sig):
    try:
        os.killpg(pgid, sig)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _kill_group(proc, grace):
    _killpg(proc.pid, signal.SIGTERM)
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline and _exited(proc) is None:
        time.sleep(0.02)
    _killpg(proc.pid, signal.SIGKILL)  # the leader and anything left in its group
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def _say(*parts, file=None, **kw):
    """print() that never raises: a closed stdout/stderr (e.g. `| head`) must not stop the cleanup."""
    try:
        print(*parts, file=file or sys.stdout, **kw)
    except (OSError, ValueError):
        pass


def _read_from(path, offset):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            fh.seek(offset)
            return fh.read()
    except OSError:
        return ""


def _size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def run(args, mode, target, target_args):
    tmpdir = tempfile.mkdtemp(prefix="hang_watchdog_")
    tasks_path = os.path.join(tmpdir, "tasks.txt")
    threads_path = os.path.join(tmpdir, "threads.txt")
    hb_path = os.path.join(tmpdir, "heartbeat")
    open(tasks_path, "w").close()
    r, w = os.pipe()
    env = dict(os.environ)
    env.update({ENV_CTL: str(r), ENV_TASKS: tasks_path, ENV_THREADS: threads_path, ENV_HEARTBEAT: hb_path,
                ENV_PARENT: str(os.getpid()), "PYTHONUNBUFFERED": "1"})
    cmd = [args.python, os.path.abspath(__file__), CHILD_FLAG, mode, target, *target_args]
    log = sys.stderr
    out_dst = sys.stderr.buffer if args.json else sys.stdout.buffer
    state = {"last_output": time.monotonic()}
    dumps, killed, interrupted = [], False, False
    label = ("-m " + target if mode == "module" else target)
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, pass_fds=(r,),
                                start_new_session=True, env=env)
    except OSError as err:
        os.close(r)
        os.close(w)
        _say(f"hang_watchdog: cannot start {args.python}: {err}", file=log)
        return 2, None
    os.close(r)
    relays = [Relay(proc.stdout, out_dst, state), Relay(proc.stderr, sys.stderr.buffer, state)]
    for t in relays:
        t.start()
    start = time.monotonic()
    if not args.json:
        _say(f"hang_watchdog: running {label} as pid {proc.pid} (pgid {proc.pid}); "
              f"kill after {args.kill_after:g}s", file=log, flush=True)

    def do_dump(reason):
        n = len(dumps) + 1
        t_off, th_off = _size(tasks_path), _size(threads_path)
        marker = f"=== end hang_watchdog dump {n} ==="
        text = ""
        try:
            os.write(w, f"dump {n} {reason}\n".encode())
        except OSError:
            pass
        deadline = time.monotonic() + args.dump_timeout
        while time.monotonic() < deadline:
            text = _read_from(tasks_path, t_off)
            if marker in text or _exited(proc) is not None:
                break
            time.sleep(0.05)
        fallback = False
        if marker not in text and _exited(proc) is None:
            fallback = True
            try:
                os.kill(proc.pid, signal.SIGUSR1)
            except ProcessLookupError:
                pass
            time.sleep(0.5)
            text += (f"\n[in-process dumper did not answer within {args.dump_timeout:g}s: the GIL is probably "
                     "held by C code, or the interpreter is wedged]\n--- threads (faulthandler, C-level) ---\n"
                     + _read_from(threads_path, th_off))
        elapsed = time.monotonic() - start
        dumps.append({"n": n, "reason": reason, "elapsed_s": round(elapsed, 2), "faulthandler_fallback": fallback,
                      "text": text})
        if not args.json:
            _say(f"\nhang_watchdog: dump {n} at {elapsed:.2f}s ({reason})\n{text.rstrip()}\n",
                  file=log, flush=True)
        if args.dump_file:
            try:
                with open(args.dump_file, "a", encoding="utf-8") as fh:
                    fh.write(f"# {label} dump {n} at {elapsed:.2f}s ({reason})\n{text}\n")
            except OSError as err:
                _say(f"hang_watchdog: cannot write --dump-file: {err}", file=log)

    rc = None
    after_done = False
    last_dump = None
    try:
        while True:
            rc = _exited(proc)
            if rc is not None:
                break
            now = time.monotonic()
            elapsed = now - start
            idle = now - state["last_output"]
            try:
                idle = min(idle, time.time() - os.path.getmtime(hb_path))
            except OSError:
                pass
            reason = None
            if args.dump_after is not None and not after_done and elapsed >= args.dump_after:
                after_done = True
                reason = f"still running after --dump-after {args.dump_after:g}s"
            elif args.idle is not None and idle >= args.idle and (last_dump is None or now - last_dump >= args.idle):
                reason = f"no output or heartbeat for {idle:.1f}s (--idle {args.idle:g})"
            if reason and len(dumps) < args.max_dumps:
                do_dump(reason)
                last_dump = time.monotonic()
            if time.monotonic() - start >= args.kill_after:
                if not dumps and _exited(proc) is None:
                    do_dump(f"--kill-after {args.kill_after:g}s reached")
                if _exited(proc) is None:
                    killed = True
                    if not args.json:
                        _say(f"hang_watchdog: --kill-after {args.kill_after:g}s reached; killing process "
                              f"group {proc.pid}", file=log, flush=True)
                    _kill_group(proc, args.grace)
                break
            time.sleep(0.05)
    except KeyboardInterrupt:
        interrupted = True
    finally:
        if _exited(proc) is None:
            _kill_group(proc, args.grace if not interrupted else 0.2)
        else:
            _killpg(proc.pid, signal.SIGKILL)  # leftover grandchildren; the zombie leader keeps the pgid
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.close(w)
        except OSError:
            pass
        for t in relays:
            t.join(timeout=2)
        for p in (tasks_path, threads_path, hb_path):
            try:
                os.remove(p)
            except OSError:
                pass
        try:
            os.rmdir(tmpdir)
        except OSError:
            pass
    elapsed = round(time.monotonic() - start, 2)
    rc = proc.returncode
    if interrupted:
        code, status = 130, "interrupted"
    elif killed:
        code, status = 3, "hung"
    elif dumps and args.fail_on_dump:
        code, status = 3, "slow"
    else:
        code, status = (0, "ok") if rc == 0 else (1, "failed")
    summary = {"target": label, "argv": target_args, "pid": proc.pid, "status": status, "returncode": rc,
               "killed": killed, "elapsed_s": elapsed, "kill_after_s": args.kill_after, "dumps": dumps,
               "exit_code": code}
    return code, summary


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == [CHILD_FLAG]:
        _child_main(argv[1:])
        return 0
    own, mode, target, target_args = split_argv(argv)
    ap = build_parser()
    args = ap.parse_args(own)
    if mode is None:
        ap.error("no target: give a script path, -m MODULE, or -- script.py")
    if os.name != "posix" or not hasattr(os, "killpg"):
        ap.error("POSIX only (needs process groups and SIGUSR1); on Windows use faulthandler.dump_traceback_later")
    if mode == "script" and not os.path.isfile(target):
        ap.error(f"target script not found: {target}")
    if args.kill_after <= 0:
        ap.error("--kill-after must be > 0")
    for name in ("dump_after", "idle", "grace", "dump_timeout"):
        v = getattr(args, name)
        if v is not None and v <= 0 and name != "grace":
            ap.error(f"--{name.replace('_', '-')} must be > 0")
        if name == "grace" and v < 0:
            ap.error("--grace must be >= 0")
    if args.max_dumps < 1:
        ap.error("--max-dumps must be >= 1")
    code, summary = run(args, mode, target, target_args)
    if summary is None:
        return code
    if args.json:
        _say(json.dumps(summary, indent=2))
    else:
        if summary["status"] == "hung":
            msg = (f"HUNG: {summary['target']} was killed after {summary['elapsed_s']}s "
                   f"({len(summary['dumps'])} dump(s) above)")
        elif summary["status"] == "interrupted":
            msg = "interrupted: target process group killed"
        else:
            msg = (f"{summary['target']} exited with status {summary['returncode']} after "
                   f"{summary['elapsed_s']}s" + (f" ({len(summary['dumps'])} dump(s) above)" if summary["dumps"]
                                                  else ""))
        _say(f"hang_watchdog: {msg}; exit {code}", file=sys.stderr)
    return code


if __name__ == "__main__":
    _code = main()
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except (OSError, ValueError):
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stderr.fileno())
    sys.exit(_code)
