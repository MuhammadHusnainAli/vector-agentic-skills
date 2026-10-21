# Tools for Live and Stuck Processes

How to get stacks out of a Python process that is hung right now, and how to prepare processes so the next
hang dumps itself. Ordered from "no preparation needed" to "built into your app".

## Contents

- [Which tool when](#which-tool-when)
- [hang_watchdog.py (re-runnable targets)](#hang_watchdogpy-re-runnable-targets)
- [py-spy (attach without changes)](#py-spy-attach-without-changes)
- [gdb with the CPython extension](#gdb-with-the-cpython-extension)
- [Python 3.14: asyncio ps/pstree, pdb -p, sys.remote_exec](#python-314-asyncio-pspstree-pdb--p-sysremote_exec)
- [faulthandler](#faulthandler)
- [In-process introspection: sys._current_frames, threading.enumerate](#in-process-introspection-sys_current_frames-threadingenumerate)
- [asyncio task introspection](#asyncio-task-introspection)
- [asyncio debug mode and slow callbacks](#asyncio-debug-mode-and-slow-callbacks)
- [Library mode: install(), dump_all(), heartbeat()](#library-mode-install-dump_all-heartbeat)
- [Containers, Kubernetes and permissions](#containers-kubernetes-and-permissions)
- [OS-level evidence](#os-level-evidence)

## Which tool when

| Situation | First choice | Fallback |
|-----------|--------------|----------|
| You can re-run the command | `hang_watchdog.py --dump-after N --kill-after M` | `timeout -s USR1` + faulthandler |
| Live process, no preparation | `py-spy dump --pid PID` | `gdb -p PID` + `py-bt` |
| Live asyncio process on 3.14 | `python -m asyncio pstree PID` | `python -m pdb -p PID`, then inspect tasks |
| GIL held / C extension stuck | `py-spy dump --native --pid PID` | faulthandler signal, `gdb` `thread apply all bt` |
| Production service | `install()` or `faulthandler.register(SIGUSR1)` at startup | heartbeat watchdog thread |
| Test suite / CI job | pytest `faulthandler_timeout`, `pytest-timeout` | `faulthandler.dump_traceback_later(..., exit=True)` |
| Slow, not hung | `py-spy top` / `py-spy record` | asyncio debug mode, cProfile |

## hang_watchdog.py (re-runnable targets)

`scripts/hang_watchdog.py` **executes** the target in a child process in its own process group, with a
bootstrap that registers faulthandler on SIGUSR1 and starts a daemon dumper thread.

```bash
python scripts/hang_watchdog.py --dump-after 30 --kill-after 120 eval_harness.py --shard 3
python scripts/hang_watchdog.py --idle 60 --kill-after 3600 -m myproj.embed_job --batch 512
python scripts/hang_watchdog.py --dump-after 1 --kill-after 3 --json deadlock.py > report.json
```

What a dump contains:
- **summary**: each thread's innermost user frame (plus innermost frame overall) and a guess at what it
  blocks on (`[lock acquire]`, `[join]`, `[queue get]`, `[sleep]`, `[idle in poll]`); each event loop as
  `responsive` or `BLOCKED`; each task's deepest user frame and what it awaits (lock/event/queue with its
  variable name when found, another task, a gather and its children).
- **threads**: full stacks with thread names, daemon/main flags; the bootstrap frames are hidden.
- **asyncio tasks**: full await chain per task, outermost first (stdlib `Task.get_stack()` shows only one
  frame for a suspended coroutine; the watchdog follows `cr_await` all the way down).
- **fallback**: if the in-process dumper does not answer within `--dump-timeout`, the watchdog sends
  SIGUSR1 and includes faulthandler's C-level dump (works while the GIL is held).

Process hygiene: `--kill-after` always ends the whole process group (SIGTERM, then SIGKILL after
`--grace`), leftover grandchildren are killed even after a normal exit, the watchdog's own Ctrl+C kills the
group, and on Linux the child gets `PR_SET_PDEATHSIG`. A grandchild that calls `setsid()` leaves the group
and is not tracked.

Exit codes: 0 target exited 0, 1 target exited non-zero, 2 usage error, 3 hung and killed (or dumped with
`--fail-on-dump`), 130 interrupted. In `--json` mode the summary (status, return code, every dump's text) is
the only thing on stdout.

## py-spy (attach without changes)

[py-spy](https://github.com/benfred/py-spy) is a sampling profiler written in Rust that reads the target's
memory; no code changes, no restart, works when the GIL is held.

```bash
py-spy dump --pid 12345                # every thread's Python stack, innermost first, with thread names
py-spy dump --pid 12345 --native       # include C/C++/Rust frames (where a C extension is stuck)
py-spy dump --pid 12345 --locals       # local variables of each frame (which item? which lock?)
py-spy top --pid 12345                 # live view: is it spinning, and where
py-spy record -o profile.svg --pid 12345 --duration 30   # flame graph of a slow (not hung) process
```

Notes: needs ptrace permission (root, `CAP_SYS_PTRACE`, or `kernel.yama.ptrace_scope=0`); in Docker add
`--cap-add SYS_PTRACE`. It shows threads, not asyncio tasks: a deadlocked asyncio app appears as the loop
idling in `select`/`epoll`. New CPython releases need a py-spy release that knows their memory layout;
check its changelog for your version before relying on it.

## gdb with the CPython extension

When nothing else is installed but gdb is, CPython's gdb helpers (`python-gdb.py`, shipped with debug
symbols packages such as `python3-dbg` on Debian/Ubuntu, `python3-debuginfo` on Fedora) add `py-bt`,
`py-list`, `py-locals`:

```bash
gdb -p 12345 -batch -ex "thread apply all py-bt"     # Python stacks for every thread
gdb -p 12345 -batch -ex "thread apply all bt"        # C stacks: where a C extension is blocked
gdb -p 12345 -batch -ex "info threads"
```

Without the helpers you still get C stacks: frames in `PyThread_acquire_lock_timed` / `pthread_cond_wait`
mean a Python lock wait; `take_gil` means a thread waiting for the GIL; `sem_wait`/`futex` are generic waits.
Attaching pauses the process briefly; detaching resumes it.

## Python 3.14: asyncio ps/pstree, pdb -p, sys.remote_exec

PEP 768 (3.14) added a safe external debugger interface. Built on it:

```bash
python3.14 -m asyncio ps 12345        # table of every asyncio task: id, name, coroutine stack, awaiter
python3.14 -m asyncio pstree 12345    # tree of who awaits whom; reports cycles in the await graph
python3.14 -m pdb -p 12345            # attach the debugger to a running process
```

`sys.remote_exec(pid, "/path/script.py")` (3.14) makes the target run a Python file at its next safe point.
With it you can call `faulthandler.dump_traceback()` or this skill's `dump_all()` inside a process that
was not prepared for it. All of these need the same Python version on both sides, ptrace permission, and
can be disabled in the target (`PYTHON_DISABLE_REMOTE_DEBUG=1`, `-X disable-remote-debug`, or a build flag).
In-process, 3.14 also offers `asyncio.capture_call_graph()`, `asyncio.format_call_graph()` and
`asyncio.print_call_graph()` for the current or a given task.

## faulthandler

Stdlib, C-level, async-signal-safe dumping of all thread stacks. It works when the GIL is held and when the
interpreter is wedged, which is why it is the last-resort fallback everywhere.

```python
import faulthandler
import signal
import sys

faulthandler.enable(file=sys.stderr, all_threads=True)       # SIGSEGV, SIGFPE, SIGABRT, SIGBUS, SIGILL
faulthandler.register(signal.SIGUSR1, file=sys.stderr, all_threads=True, chain=False)  # POSIX only
faulthandler.dump_traceback_later(timeout=1800, repeat=False, exit=False)  # one timed dump
faulthandler.cancel_dump_traceback_later()
faulthandler.dump_traceback(file=sys.stderr, all_threads=True)             # dump right now
```

- From outside: `kill -USR1 PID` after `register`. Enable without code changes with `python -X faulthandler`
  or `PYTHONFAULTHANDLER=1` (fatal errors only, not the signal).
- CI: `faulthandler.dump_traceback_later(timeout, exit=True)` dumps and exits the process (hard
  `_exit`) before the CI runner kills it silently. pytest has this built in: `faulthandler_timeout = 300`
  in the ini file dumps stacks of tests that run longer than 300 s.
- Keep the file object alive (faulthandler stores the file descriptor, not the object); writing to a
  closed fd prints nothing.
- Output is "most recent call first" and lists threads by id; on recent versions (seen on 3.14) the OS
  thread name follows in brackets, truncated to 15 characters. No asyncio tasks, no locals.
- 3.14 also adds `faulthandler.dump_c_stack()` for C-level frames on supported platforms.

## In-process introspection: sys._current_frames, threading.enumerate

```python
import sys
import threading
import traceback


def dump_threads() -> str:
    names = {t.ident: (t.name, t.daemon) for t in threading.enumerate()}
    out = []
    for ident, frame in sys._current_frames().items():
        name, daemon = names.get(ident, (f"<unknown {ident:#x}>", None))
        out.append(f"--- thread {name!r} daemon={daemon}\n" + "".join(traceback.format_stack(frame)))
    return "\n".join(out)


worker = threading.Thread(target=threading.Event().wait, args=(0.5,), name="waiter")
worker.start()
text = dump_threads()
worker.join()
print("thread 'waiter'" in text, "thread 'MainThread'" in text)  # True True
```

`sys._current_frames()` is CPython-specific but stable for years. `threading.enumerate()` lists only
threads started through `threading` (and the main thread); `faulthandler` and py-spy also see threads
created by C libraries.

## asyncio task introspection

```python
import asyncio


def await_chain(coro):
    """Frames of a coroutine and everything it awaits, outermost first."""
    frames = []
    while coro is not None:
        frame = getattr(coro, "cr_frame", None) or getattr(coro, "gi_frame", None)
        if frame is not None:
            frames.append(frame)
        coro = getattr(coro, "cr_await", None) or getattr(coro, "gi_yieldfrom", None)
        if coro is not None and not hasattr(coro, "cr_frame") and not hasattr(coro, "gi_frame"):
            break
    return frames


async def tool_call():
    await asyncio.Event().wait()            # never set


async def agent_step():
    await tool_call()


async def main():
    t = asyncio.create_task(agent_step(), name="agent-step")
    await asyncio.sleep(0.01)
    for task in asyncio.all_tasks():
        if task is asyncio.current_task():
            continue
        names = [f.f_code.co_name for f in await_chain(task.get_coro())]
        print(task.get_name(), "->", " -> ".join(names))
    t.cancel()


asyncio.run(main())  # agent-step -> agent_step -> tool_call -> wait
```

- `asyncio.all_tasks(loop)` returns pending tasks; `asyncio.current_task()` the running one.
- `task.print_stack()` / `task.get_stack()` show only the task's own coroutine frame while it is suspended,
  not the frames it awaits: walk `cr_await` as above (or use the watchdog, or 3.14's call-graph API).
- Name tasks at creation (`name=` on `create_task`, 3.8+); `Task-123` is useless in a dump.
- Calling `all_tasks()` from **another thread** is not formally thread-safe; schedule the inspection on the
  loop with `loop.call_soon_threadsafe` and fall back to reading from outside only when the loop does not
  answer (that is what the watchdog does).

## asyncio debug mode and slow callbacks

```python
import asyncio
import logging
import time

logging.basicConfig(level=logging.WARNING)


async def blocking_handler():
    time.sleep(0.2)      # the bug debug mode reports


async def main():
    asyncio.get_running_loop().slow_callback_duration = 0.05   # default 0.1 s
    await blocking_handler()


asyncio.run(main(), debug=True)
# WARNING:asyncio:Executing <Task finished name='Task-1' coro=<main() ...> ...> took 0.200 seconds
```

Enable with `asyncio.run(main(), debug=True)`, `PYTHONASYNCIODEBUG=1`, or `python -X dev`. Debug mode also
reports never-awaited coroutines with the creation traceback, non-threadsafe calls from the wrong thread
(`call_soon` from another thread raises), and unclosed transports. It adds overhead: use it in tests and
staging, not permanently in production.

## Library mode: install(), dump_all(), heartbeat()

`hang_watchdog.py` is importable. Copy it next to your app (stdlib only) or add the scripts folder to
`sys.path`:

```python
import asyncio
import os
import signal
import sys

sys.path.insert(0, "skills/programming/python/python-async-deadlock-debugger/scripts")
from hang_watchdog import dump_all, heartbeat, install  # noqa: E402

install()                       # kill -USR1 <pid> -> threads + asyncio tasks on stderr
# install(dump_after=300)       # also dump once, automatically, after 300 s
# install(c_level_signal=signal.SIGUSR2)  # plus a faulthandler dump that works with the GIL held


async def main():
    heartbeat()                  # progress marker for `hang_watchdog.py --idle`
    os.kill(os.getpid(), signal.SIGUSR1)
    await asyncio.sleep(0.6)     # the dumper thread prints while we wait


asyncio.run(main())
text = dump_all(file=open(os.devnull, "w"), reason="on demand")
print("=== end hang_watchdog dump ===" in text)  # True
```

`install()` registers a Python-level signal handler that only writes to a pipe; a daemon thread does the
dump, so it works while the loop or the main thread is stuck, as long as the GIL is free. Run it from the
main thread (signal handlers can only be installed there).

## Containers, Kubernetes and permissions

- Attaching (py-spy, gdb, `pdb -p`, `asyncio ps`) needs `CAP_SYS_PTRACE` or root in the same PID namespace.
  Kubernetes: an ephemeral debug container (`kubectl debug -it POD --image=... --target=CONTAINER`) with the
  capability, or bake `install()`/faulthandler into the app so `kill -USR1 1` is enough.
- PID 1 in a container ignores signals it has no handler for: `kill -USR1 1` works only after `register`
  or `install()`; use `tini`/`dumb-init` as PID 1 so SIGTERM reaches Python.
- `kubectl logs` shows dumps written to stderr; write to a file on a volume if logs are rotated aggressively.

## OS-level evidence

```bash
ps -o pid,ppid,pgid,stat,pcpu,nlwp,etime,cmd -p 12345   # state D = uninterruptible IO, S = sleeping
cat /proc/12345/status | grep -E "State|Threads|VmRSS"
cat /proc/12345/task/*/wchan; echo                       # kernel wait channel per thread (futex_wait...)
ls -l /proc/12345/fd | wc -l                             # fd leak? sockets piling up?
ss -tanp | grep 12345                                    # connections stuck in ESTABLISHED/CLOSE_WAIT
strace -f -p 12345 -e trace=futex,read,recvfrom,epoll_wait   # what each thread waits on (Linux)
pstree -p 12345                                          # children and grandchildren
```

`futex` waits are lock/condition waits; `epoll_wait` with no events is an idle event loop (asyncio
deadlock or waiting on a silent server); `read`/`recvfrom` on a socket is an IO hang; state `D` means the
kernel is stuck on IO (NFS, a dead disk, a GPU driver) and no Python tool can help.
