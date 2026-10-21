# API Mapping: asyncio -> anyio -> trio

The complete translation table. "R" marks rows that `scripts/migrate_async.py` rewrites automatically (when
the call site is safe); every other row is reported as a manual item with the rule id shown. anyio entries
are for anyio 4.x (verified against 4.14.2 and 4.15.1); trio entries are for current trio (0.25+). Rows
marked *4.14+* / *4.15+* exist only in recent anyio releases.

## Contents

- [Running and time](#running-and-time)
- [Tasks and task groups](#tasks-and-task-groups)
- [Timeouts, cancellation and shielding](#timeouts-cancellation-and-shielding)
- [Synchronisation primitives](#synchronisation-primitives)
- [Queues and memory object streams](#queues-and-memory-object-streams)
- [Threads, processes and the loop from outside](#threads-processes-and-the-loop-from-outside)
- [Subprocesses](#subprocesses)
- [Sockets, streams and TLS](#sockets-streams-and-tls)
- [Files and paths](#files-and-paths)
- [Signals](#signals)
- [Introspection](#introspection)
- [Exceptions](#exceptions)
- [asyncio APIs with no direct equivalent](#asyncio-apis-with-no-direct-equivalent)

## Running and time

| asyncio | anyio | trio | Rule |
|---------|-------|------|------|
| `asyncio.run(main())` | `anyio.run(main)` | `trio.run(main)` | R MIG002 |
| `asyncio.run(main(a, b))` | `anyio.run(main, a, b)` | `trio.run(main, a, b)` | R MIG002 |
| `asyncio.run(main(a, k=1))` | `anyio.run(functools.partial(main, a, k=1))` | `trio.run(functools.partial(main, a, k=1))` | R MIG002 |
| `asyncio.run(main(), debug=True)` | `anyio.run(main, backend_options={"debug": True})` | (no debug mode; use instruments) | MIG002 manual |
| `asyncio.run(main(), loop_factory=uvloop.new_event_loop)` (3.12+) | `anyio.run(main, backend_options={"use_uvloop": True})` | n/a | MIG002 manual |
| `asyncio.Runner()` reused for several calls | `with anyio.from_thread.start_blocking_portal() as portal: portal.call(f)` | `trio.run` per call | MIG018 |
| choose loop at run time | `anyio.run(main, backend="trio")` | n/a | - |
| `await asyncio.sleep(s)` | `await anyio.sleep(s)` | `await trio.sleep(s)` (s >= 0) | R MIG003 |
| `await asyncio.sleep(0)` | `await anyio.sleep(0)` or `await anyio.lowlevel.checkpoint()` | `await trio.lowlevel.checkpoint()` | R MIG003 |
| `await asyncio.sleep(s, result)` | `await anyio.sleep(s); x = result` | same | MIG003 manual |
| `await asyncio.Event().wait()` (sleep forever) | `await anyio.sleep_forever()` | `await trio.sleep_forever()` | - |
| `loop.time()` | `anyio.current_time()` | `trio.current_time()` | MIG018 |
| sleep until a loop-time deadline | `await anyio.sleep_until(deadline)` | `await trio.sleep_until(deadline)` | - |

anyio's `backend_options` for asyncio are `debug`, `use_uvloop` and `loop_factory`; on trio they are passed
to `trio.run` (for example `clock=`).

## Tasks and task groups

| asyncio | anyio | trio | Rule |
|---------|-------|------|------|
| `async with asyncio.TaskGroup() as tg:` (3.11+) | `async with anyio.create_task_group() as tg:` | `async with trio.open_nursery() as nursery:` | R MIG007 |
| `tg.create_task(f(a, b))` (result unused) | `tg.start_soon(f, a, b)` | `nursery.start_soon(f, a, b)` | R MIG008 |
| `tg.create_task(f(a, k=1), name="x")` | `tg.start_soon(functools.partial(f, a, k=1), name="x")` | same with `nursery` | R MIG008 |
| `t = tg.create_task(f())` then `t.result()` | write into a container in the child; *4.14+*: `h = tg.create_task(f())`, `await h` / `h.return_value` | container | MIG007 manual |
| `asyncio.create_task(f())` fire-and-forget | `tg.start_soon(f)` in a group that outlives it | `nursery.start_soon(f)` | MIG014 |
| `asyncio.ensure_future(coro)` | same as create_task | same | MIG014 |
| `loop.create_task(coro)` | same | same | MIG014 |
| `await asyncio.gather(a(), b())` | task group + results list; *4.15+*: `await anyio.gather(a(), b())` | nursery + results list | MIG011 |
| `gather(..., return_exceptions=True)` | each child catches `Exception` and stores it | same | MIG012 |
| `asyncio.wait(ts, return_when=FIRST_COMPLETED)` | children store result and cancel `tg.cancel_scope` | same with `nursery.cancel_scope` | MIG022 |
| `asyncio.wait(ts, return_when=FIRST_EXCEPTION)` | default task-group behaviour | default nursery behaviour | MIG022 |
| `asyncio.as_completed(aws)` | children send results into a memory stream; *4.15+*: `async with anyio.as_completed(*aws) as handles:` | memory channel | MIG023 |
| Event-based readiness ("server started") | `value = await tg.start(f)`; child calls `task_status.started(value)` | `await nursery.start(f)` | - |
| `tg` type annotation `asyncio.TaskGroup` | `anyio.abc.TaskGroup` | `trio.Nursery` | MIG007 manual |
| cancel all children | `tg.cancel_scope.cancel()` (*4.14+*: `tg.cancel()`) | `nursery.cancel_scope.cancel()` | - |
| `Task.cancel()` on one task | give that child its own `CancelScope`, return it via `tg.start`, call `scope.cancel()` | same | MIG030 |

## Timeouts, cancellation and shielding

| asyncio | anyio | trio | Rule |
|---------|-------|------|------|
| `async with asyncio.timeout(s):` (3.11+) | `with anyio.fail_after(s):` | `with trio.fail_after(s):` | R MIG006 |
| `async with asyncio.timeout(None):` | `with anyio.fail_after(None):` | `with trio.fail_after(math.inf):` | R MIG006 (anyio) / manual (trio) |
| `async with asyncio.timeout(s) as cm: cm.reschedule(t)` | `with anyio.fail_after(s) as scope: scope.deadline = t` | `with trio.fail_after(s) as scope: scope.deadline = t` | MIG032 |
| `asyncio.timeout_at(when)` | `with anyio.CancelScope(deadline=when):` / *4.15+* `anyio.fail_at(when)` | `with trio.fail_at(when):` | MIG032 |
| `await asyncio.wait_for(aw, s)` | `with anyio.fail_after(s): r = await aw` | `with trio.fail_after(s): r = await aw` | MIG013 |
| give up silently after s | `with anyio.move_on_after(s) as scope:` then `scope.cancelled_caught` | `with trio.move_on_after(s) as scope:` | - |
| `await asyncio.shield(aw)` | `with anyio.CancelScope(shield=True): await aw` | `with trio.CancelScope(shield=True): await aw` | MIG024 |
| `except asyncio.CancelledError:` | `except anyio.get_cancelled_exc_class():` | `except trio.Cancelled:` | R MIG009 |
| `raise asyncio.CancelledError` | cancel a scope: `scope.cancel()` | same | MIG009 manual |
| `task.cancelling()` / `uncancel()` (3.11+) | not needed: scopes know their own cancellation (`scope.cancel_called`, `cancelled_caught`) | same | MIG099 |
| `asyncio.TimeoutError` | builtin `TimeoutError` | `trio.TooSlowError` | R MIG010 |
| nearest deadline | `anyio.current_effective_deadline()` | `trio.current_effective_deadline()` | - |

`fail_after`, `move_on_after` and `CancelScope` are **synchronous** context managers (`with`, not
`async with`); the rewriter turns `async with asyncio.timeout(x):` into `with anyio.fail_after(x):`.

## Synchronisation primitives

| asyncio | anyio | trio | Rule / caveat |
|---------|-------|------|---------------|
| `asyncio.Lock()` | `anyio.Lock()` | `trio.Lock()` | R MIG004. Must be released by the task that acquired it (RuntimeError otherwise); explicit `.release()` makes the item manual |
| `lock.locked()` | `lock.locked()` | `lock.locked()` | - |
| `asyncio.Event()` | `anyio.Event()` | `trio.Event()` | R MIG004. No `clear()`: replace the object; `wait()` returns `None` (asyncio returns `True`) |
| `asyncio.Semaphore(n)` / `Semaphore()` | `anyio.Semaphore(n)` / `anyio.Semaphore(1)` | `trio.Semaphore(n)` | R MIG004. initial value is required; no `locked()`, use `sem.value == 0` |
| `asyncio.BoundedSemaphore(n)` | `anyio.Semaphore(n, max_value=n)` | `trio.Semaphore(n, max_value=n)` | R MIG004 |
| "at most N concurrent" (Semaphore as limiter) | `anyio.CapacityLimiter(n)` (borrower-aware, `total_tokens` adjustable at run time) | `trio.CapacityLimiter(n)` | - |
| `asyncio.Condition(lock)` | `anyio.Condition(lock)` | `trio.Condition(lock)` | R MIG004 |
| `await cond.wait_for(pred)` | `await cond.wait_for(pred)` (anyio 4.11+) | loop: `while not pred(): await cond.wait()` | manual on trio |
| `asyncio.Barrier(n)` (3.11+) | no primitive: counter + `anyio.Event` | same with `trio.Event` | MIG099 |
| `defaultdict(asyncio.Lock)` | `defaultdict(anyio.Lock)` | `defaultdict(trio.Lock)` | R MIG004 (Event/Lock/Condition as factories) |
| exclusive use of a resource | `anyio.ResourceGuard("reading")` | `trio`'s `ConflictDetector` is internal; use a Lock | - |

## Queues and memory object streams

| asyncio | anyio | trio | Rule |
|---------|-------|------|------|
| `q = asyncio.Queue(maxsize=n)` | `send, recv = anyio.create_memory_object_stream[T](max_buffer_size=n)` | `send, recv = trio.open_memory_channel(n)` | MIG015 |
| `asyncio.Queue()` (unbounded) | `create_memory_object_stream[T](math.inf)` (think twice: no backpressure) | `trio.open_memory_channel(math.inf)` | MIG015 |
| `maxsize=0` means unbounded in asyncio | `max_buffer_size=0` means *rendezvous* (send waits for a receiver) | same as anyio | MIG015 |
| `await q.put(x)` | `await send.send(x)` | `await send.send(x)` | MIG015 |
| `q.put_nowait(x)` / `QueueFull` | `send.send_nowait(x)` / `anyio.WouldBlock` | `send.send_nowait(x)` / `trio.WouldBlock` | MIG015 |
| `await q.get()` | `await recv.receive()` | `await recv.receive()` | MIG015 |
| `q.get_nowait()` / `QueueEmpty` | `recv.receive_nowait()` / `anyio.WouldBlock` | `recv.receive_nowait()` / `trio.WouldBlock` | MIG015 |
| loop with sentinel `None` | `async for item in recv:` ends when every send clone is closed | same | MIG015 |
| `q.task_done()` / `await q.join()` | close send clones; leaving the task group means all consumers finished | same | MIG016 |
| `q.shutdown()` (3.13+) | `await send.aclose()` (consumers drain, then stop); `recv.close()` makes senders fail | same | MIG015 |
| several producers | `send.clone()` per producer; stream ends when the last clone closes | same | - |
| several consumers | `recv.clone()` per consumer (each item goes to one consumer) | same | - |
| `q.qsize()` | `send.statistics().current_buffer_used` | `send.statistics().current_buffer_used` | - |
| `asyncio.PriorityQueue` / `LifoQueue` | no stream equivalent: `heapq` + `anyio.Condition`, or a Lock-guarded list + Event | same | MIG015 |

Errors on streams: `receive()` after all senders closed -> `anyio.EndOfStream` (trio: `trio.EndOfChannel`);
`send()` after all receivers closed -> `anyio.BrokenResourceError` (trio: `trio.BrokenResourceError`); using a
handle you closed yourself -> `anyio.ClosedResourceError` (trio: `trio.ClosedResourceError`). anyio warns
with a `ResourceWarning` when a stream object is garbage-collected without being closed.

## Threads, processes and the loop from outside

| asyncio | anyio | trio | Rule |
|---------|-------|------|------|
| `await asyncio.to_thread(f, *a)` | `await anyio.to_thread.run_sync(f, *a)` | `await trio.to_thread.run_sync(f, *a)` | R MIG005 |
| `await asyncio.to_thread(f, *a, k=v)` | `await anyio.to_thread.run_sync(functools.partial(f, *a, k=v))` | same with trio | R MIG005 |
| `loop.run_in_executor(None, f, *a)` | `await anyio.to_thread.run_sync(f, *a)` | `await trio.to_thread.run_sync(f, *a)` | MIG017 |
| `loop.run_in_executor(pool_of_8, f)` | `limiter = anyio.CapacityLimiter(8)`; `run_sync(f, limiter=limiter)` | `trio.CapacityLimiter(8)`; `run_sync(f, limiter=...)` | MIG017 |
| `loop.run_in_executor(ProcessPoolExecutor(), f)` | `await anyio.to_process.run_sync(f, *a)` (or keep a tuned pool and call it via to_thread) | trio-parallel (third-party) or a pool via to_thread | MIG017 |
| default executor size | `anyio.to_thread.current_default_thread_limiter().total_tokens` (40) | `trio.to_thread.current_default_thread_limiter()` (40) | - |
| cancellation while the thread runs | waits for the thread; `abandon_on_cancel=True` returns immediately (anyio 4.1+) | `abandon_on_cancel=True` (trio 0.23+) | note |
| `asyncio.run_coroutine_threadsafe(coro, loop).result()` from a worker thread | `anyio.from_thread.run(async_fn, *a)` | `trio.from_thread.run(async_fn, *a)` | MIG028 |
| `loop.call_soon_threadsafe(f, *a)` from a worker thread | `anyio.from_thread.run_sync(f, *a)` | `trio.from_thread.run_sync(f, *a)` | MIG019 |
| call async code from a foreign thread (Celery, Streamlit, CLI) | `with anyio.from_thread.start_blocking_portal() as portal: portal.call(f, *a)` | `trio.from_thread.run(f, *a, trio_token=token)` with `token = trio.lowlevel.current_trio_token()` | MIG028 |
| schedule without waiting from a foreign thread | `portal.start_task_soon(f, *a)` (returns `concurrent.futures.Future`) | `trio.from_thread.run_sync(nursery.start_soon, f)` | MIG028 |
| worker thread checks for cancellation | `anyio.from_thread.check_cancelled()` | `trio.from_thread.check_cancelled()` | - |
| subinterpreters (3.14 `InterpreterPoolExecutor`) | `anyio.to_interpreter.run_sync(f, *a)` (recent anyio; see its docs for Python-version caveats) | n/a | - |

## Subprocesses

| asyncio | anyio | trio | Rule |
|---------|-------|------|------|
| `p = await asyncio.create_subprocess_exec(*cmd, stdout=PIPE); out, _ = await p.communicate()` | `r = await anyio.run_process(cmd)`; `r.stdout` (bytes), `check=True` by default | `r = await trio.run_process(cmd, capture_stdout=True)` | MIG025 |
| `create_subprocess_shell("a | b")` | `await anyio.run_process("a | b")` (a `str` command runs through the shell) | `trio.run_process("a | b", shell=True)` | MIG025 |
| streaming output | `async with await anyio.open_process(cmd) as p: async for chunk in p.stdout:` | `p = await nursery.start(trio.run_process, cmd, ...)` | MIG025 |
| `p.kill()` / `p.terminate()` / `await p.wait()` | same names on `anyio.abc.Process` | same names on `trio.Process` | - |
| `asyncio.subprocess.PIPE` | `subprocess.PIPE` (stdlib) | `subprocess.PIPE` | MIG025 |
| cancellation | anyio kills the child when the awaiting scope is cancelled | trio terminates then kills (`deliver_cancel`) | - |

## Sockets, streams and TLS

| asyncio | anyio | trio | Rule |
|---------|-------|------|------|
| `reader, writer = await asyncio.open_connection(h, p)` | `stream = await anyio.connect_tcp(h, p)` | `stream = await trio.open_tcp_stream(h, p)` | MIG026 |
| `open_connection(h, p, ssl=ctx)` | `await anyio.connect_tcp(h, p, tls=True, ssl_context=ctx)` | `await trio.open_ssl_over_tcp_stream(h, p, ssl_context=ctx)` | MIG026 |
| `writer.write(b); await writer.drain()` | `await stream.send(b)` | `await stream.send_all(b)` | MIG026 |
| `await reader.read(n)` | `await stream.receive(n)` | `await stream.receive_some(n)` | MIG026 |
| `await reader.readline()` / `readuntil(b"\n")` | `BufferedByteReceiveStream(stream).receive_until(b"\n", max_bytes)` | manual buffer | MIG026 |
| `writer.close(); await writer.wait_closed()` | `await stream.aclose()` (or `async with stream:`) | `await stream.aclose()` | MIG026 |
| `await asyncio.start_server(handler, h, p)` | `listener = await anyio.create_tcp_listener(local_port=p)`; `await listener.serve(handler)` | `await trio.serve_tcp(handler, p)` | MIG026 |
| `loop.create_datagram_endpoint` | `await anyio.create_udp_socket(...)` | `trio.socket` | MIG026 |
| unix sockets | `anyio.connect_unix(path)` / `create_unix_listener(path)` | `trio.open_unix_socket(path)` | MIG026 |
| text decoding | `anyio.streams.text.TextReceiveStream(stream)` | decode manually | - |

## Files and paths

| asyncio (or aiofiles) | anyio | trio |
|-----------------------|-------|------|
| `await asyncio.to_thread(path.read_text)` | `await anyio.Path(path).read_text()` | `await trio.Path(path).read_text()` |
| `aiofiles.open(p)` | `async with await anyio.open_file(p) as f:` | `async with await trio.open_file(p) as f:` |
| iterate lines | `async for line in f:` | `async for line in f:` |
| wrap an open file object | `anyio.wrap_file(fobj)` | `trio.wrap_file(fobj)` |
| temp files | `anyio.TemporaryDirectory()`, `anyio.NamedTemporaryFile()` (recent anyio) | `trio` has none; use `to_thread` |

File I/O in all three runs in worker threads under the hood (operating systems have no general async file
API usable here), so it shares the thread limiter.

## Signals

| asyncio | anyio | trio | Rule |
|---------|-------|------|------|
| `loop.add_signal_handler(SIGTERM, cb)` | `with anyio.open_signal_receiver(SIGTERM, SIGINT) as sigs: async for s in sigs:` | `with trio.open_signal_receiver(SIGTERM) as sigs: async for s in sigs:` | MIG027 |
| `loop.remove_signal_handler(SIGTERM)` | leave the `with` block | same | MIG027 |
| Ctrl-C | asyncio backend: the main task sees `CancelledError` (cleanup runs), then `anyio.run` raises `KeyboardInterrupt` (verified) | `KeyboardInterrupt` raised in the main task (only at checkpoints with `restrict_keyboard_interrupt_to_checkpoints=True`) | - |

Signal receivers work on Unix only (asyncio's `add_signal_handler` is Unix-only as well).

## Introspection

| asyncio | anyio | trio | Rule |
|---------|-------|------|------|
| `asyncio.current_task()` | `anyio.get_current_task()` (`TaskInfo`: `id`, `name`, `parent_id`, `coro`) | `trio.lowlevel.current_task()` | MIG029 |
| `asyncio.all_tasks()` | `anyio.get_running_tasks()` | walk `trio.lowlevel.current_root_task()` children | MIG029 |
| `task.get_name()` | `anyio.get_current_task().name`; set with `start_soon(f, name="x")` | `trio.lowlevel.current_task().name` | MIG029 |
| `asyncio.iscoroutinefunction(f)` | `inspect.iscoroutinefunction(f)` | same | MIG033 |
| test helper: let everything settle | `await anyio.wait_all_tasks_blocked()` | `await trio.testing.wait_all_tasks_blocked()` | - |
| which library am I on? | `sniffio.current_async_library()` or `anyio`'s backend name in tests | `sniffio` | - |

## Exceptions

| asyncio | anyio | trio |
|---------|-------|------|
| `asyncio.CancelledError` (BaseException) | `anyio.get_cancelled_exc_class()` (= `asyncio.CancelledError` on asyncio) | `trio.Cancelled` (BaseException) |
| `asyncio.TimeoutError` / `TimeoutError` | `TimeoutError` from `fail_after` | `trio.TooSlowError` from `fail_after` |
| `ExceptionGroup` from `TaskGroup` | `ExceptionGroup` from every task group (anyio 4) | `ExceptionGroup` from every nursery (trio 0.25+ default) |
| `asyncio.QueueEmpty` / `QueueFull` | `anyio.WouldBlock` | `trio.WouldBlock` |
| `asyncio.IncompleteReadError` | `anyio.IncompleteRead` / `anyio.EndOfStream` | `trio.EndOfChannel` / empty `receive_some` |
| `asyncio.InvalidStateError` | n/a (no futures) | n/a |
| `ConnectionResetError` on a stream | `anyio.BrokenResourceError` | `trio.BrokenResourceError` |
| use of a closed stream | `anyio.ClosedResourceError` | `trio.ClosedResourceError` |
| two tasks receiving on one byte stream | `anyio.BusyResourceError` | `trio.BusyResourceError` |

On Python 3.9/3.10 install the `exceptiongroup` backport (anyio depends on it there) and use
`exceptiongroup.catch()` instead of `except*`.

## asyncio APIs with no direct equivalent

| asyncio API | Why there is no equivalent | Structured replacement |
|-------------|----------------------------|------------------------|
| `loop.call_soon(f)` / `call_later(d, f)` / `call_at` | no callback scheduling on the loop | a child task: `async def later(): await anyio.sleep(d); f()`; cancel via its scope |
| `fut.add_done_callback(cb)` | no futures/tasks to observe | do the follow-up at the end of the child (`try/finally`) or wrap: `async def run_then(cb): try: return await f() finally: cb()` |
| `asyncio.Future()` / `loop.create_future()` | one-shot cross-task value | `Event` + value slot, or `create_memory_object_stream(1)` (*4.15+*: `anyio.Future`) |
| `Task.cancel()` from outside | cancellation targets scopes, not tasks | child opens `with CancelScope() as scope:` and reports it via `task_status.started(scope)`; the parent calls `scope.cancel()` |
| `Queue.join()` / `task_done()` | completion is structural | close the send side; the task group exit is the join |
| `asyncio.get_event_loop()` / global loop | no loop object in the portable API | pass what you need explicitly; `anyio.current_time()`; portals for foreign threads |
| `asyncio.wait(..., FIRST_COMPLETED)` | needs task objects | race pattern: each child stores its result and cancels the group's scope |
| `loop.set_exception_handler` | errors are never orphaned in task groups | catch at the group (`except*`) or inside the child |
| `asyncio.set_event_loop_policy` / `eager_task_factory` (3.12+) | loop customisation is backend-specific | `backend_options` (asyncio backend) or keep that module asyncio-only |
| `contextvars` set in a task and read by a sibling | same rules: each child gets a copy of the parent context at spawn time | pass values explicitly |

Runnable versions of every replacement are in [migration-playbook.md](migration-playbook.md).
