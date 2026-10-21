#!/usr/bin/env python3
"""Migrate asyncio code to AnyIO (runs on asyncio or trio) or to trio.

Static analysis and source rewriting only: the analysed code is parsed with
`ast` and rewritten by source segment; it is never imported or executed.

Every asyncio usage gets a rule id, a line, a classification and a suggested
replacement:

  mechanical  rewritten automatically and exactly by --diff / --write
  manual      semantics differ; the report explains what to write instead

Mechanical rewrites (only when provably equivalent at that call site):
  MIG001 import-asyncio       `import asyncio` -> `import anyio`; asyncio import kept only if still used
  MIG002 asyncio-run          asyncio.run(main(a, k=v)) -> anyio.run(main, a) / functools.partial for kwargs
  MIG003 sleep                asyncio.sleep(x) -> anyio.sleep(x)
  MIG004 sync-primitive       asyncio.Event/Lock/Semaphore/BoundedSemaphore/Condition -> anyio equivalents
  MIG005 to-thread            asyncio.to_thread(f, *a, **kw) -> anyio.to_thread.run_sync(f, *a) / partial
  MIG006 timeout-block        `async with asyncio.timeout(x):` -> `with anyio.fail_after(x):`
  MIG007 task-group           asyncio.TaskGroup() -> anyio.create_task_group()
  MIG008 task-group-spawn     tg.create_task(coro(a)) -> tg.start_soon(coro, a) (result unused)
  MIG009 cancelled-error      `except asyncio.CancelledError` -> `except anyio.get_cancelled_exc_class()`
  MIG010 timeout-error        asyncio.TimeoutError -> TimeoutError (anyio) / trio.TooSlowError (trio)
Manual (reported with guidance):
  MIG011 gather  MIG012 gather-return-exceptions  MIG013 wait-for  MIG014 create-task
  MIG015 queue  MIG016 queue-join-task-done  MIG017 run-in-executor  MIG018 event-loop-access
  MIG019 loop-callbacks  MIG020 future  MIG021 done-callback  MIG022 wait  MIG023 as-completed
  MIG024 shield  MIG025 subprocess  MIG026 streams-and-sockets  MIG027 signal-handlers
  MIG028 run-coroutine-threadsafe  MIG029 task-introspection  MIG030 task-cancel-from-outside
  MIG031 cancellation-swallowed  MIG032 timeout-advanced  MIG033 coroutine-checks
  MIG099 other-asyncio-api
A mechanical rule falls back to manual (with the reason) when the call site is
not provably safe, e.g. Event.clear() is used, a task result is stored, or the
timeout block binds `as cm`. Run --list-rules for the why and fix of each rule.

Usage:
    python migrate_async.py app/service.py                      # report (default)
    python migrate_async.py src/ --target trio --json
    cat worker.py | python migrate_async.py - --diff
    python migrate_async.py app/service.py --diff               # unified diff of automatic rewrites
    python migrate_async.py app/service.py --write              # in place, keeps app/service.py.bak
    python migrate_async.py app/service.py --write --force      # write even with manual items left
    python migrate_async.py src/ --check                        # CI gate: exit 1 if asyncio remains
    python migrate_async.py src/ --strict                       # exit 1 if any manual item
    python migrate_async.py src/ --select MIG003,MIG004 --ignore gather
    python migrate_async.py --list-rules --target trio

Silence one line (and skip its rewrite) with `# noqa: MIG013` or a bare `# noqa`.
stdin (`-`) works with report, --diff and --check; --write needs real files.

Exit codes: 0 success; 1 --check found asyncio usage, --strict found manual
items, or --write refused a file with manual items; 2 usage error, unreadable
or unparsable file named on the command line (files found while walking a
directory are skipped with a warning), or a rewrite that fails ast.parse.

No dependencies (standard library only, Python 3.9+).
"""

import argparse
import ast
import difflib
import json
import os
import re
import shutil
import sys

# ---------------------------------------------------------------- rules
# id: (name, default kind, severity, summary, why, anyio fix, trio fix)
RULES = {
    "MIG001": ("import-asyncio", "mechanical", "low", "asyncio import",
               "After migration the module should import the target library; `import asyncio` stays only while "
               "something still needs it (asyncio-only libraries, manual items).",
               "import anyio", "import trio"),
    "MIG002": ("asyncio-run", "mechanical", "low", "asyncio.run(coro) entry point",
               "anyio.run/trio.run take the coroutine *function* plus positional args, not a coroutine object, "
               "so the backend can be chosen at run time.",
               "anyio.run(main, arg1)                                  # backend='trio' to switch\n"
               "anyio.run(functools.partial(main, limit=8))            # keyword arguments\n"
               "anyio.run(main, backend_options={'debug': True})       # was asyncio.run(main(), debug=True)",
               "trio.run(main, arg1)\ntrio.run(functools.partial(main, limit=8))"),
    "MIG003": ("sleep", "mechanical", "low", "asyncio.sleep",
               "Same semantics; anyio.sleep/trio.sleep are checkpoints. sleep(delay, result) has no equivalent.",
               "await anyio.sleep(0.5)", "await trio.sleep(0.5)   # trio rejects negative delays"),
    "MIG004": ("sync-primitive", "mechanical", "low", "asyncio synchronisation primitive",
               "anyio/trio Lock, Event, Semaphore and Condition are drop-in for `async with`/wait/set, but: Events "
               "cannot be cleared, Locks may only be released by the owning task, Semaphore needs an explicit "
               "initial value and has no locked(), trio.Condition has no wait_for().",
               "lock = anyio.Lock()\nevent = anyio.Event()          # one-shot: replace it instead of clear()\n"
               "sem = anyio.Semaphore(8)\nlimiter = anyio.CapacityLimiter(8)   # preferred for 'max N in flight'",
               "lock = trio.Lock()\nevent = trio.Event()\nsem = trio.Semaphore(8)\nlimiter = trio.CapacityLimiter(8)"),
    "MIG005": ("to-thread", "mechanical", "low", "asyncio.to_thread",
               "anyio.to_thread.run_sync takes positional args only (wrap kwargs in functools.partial) and uses a "
               "40-thread CapacityLimiter by default. Unlike asyncio.to_thread, cancellation waits for the thread "
               "unless abandon_on_cancel=True.",
               "await anyio.to_thread.run_sync(parse_pdf, path)\n"
               "await anyio.to_thread.run_sync(functools.partial(embed, texts, normalize=True), limiter=limiter)",
               "await trio.to_thread.run_sync(parse_pdf, path)\n"
               "await trio.to_thread.run_sync(functools.partial(embed, texts, normalize=True), limiter=limiter)"),
    "MIG006": ("timeout-block", "mechanical", "low", "async with asyncio.timeout(x)",
               "fail_after is a plain (sync) context manager wrapping a cancel scope; it raises TimeoutError "
               "(anyio) / trio.TooSlowError (trio) when the deadline passes.",
               "with anyio.fail_after(30):\n    reply = await llm.complete(prompt)\n"
               "with anyio.move_on_after(30) as scope:   # give up silently\n    ...\nif scope.cancelled_caught: ...",
               "with trio.fail_after(30):        # raises trio.TooSlowError\n    reply = await llm.complete(prompt)"),
    "MIG007": ("task-group", "mechanical", "low", "asyncio.TaskGroup",
               "Both are structured: the block waits for every child and an error cancels the siblings and raises "
               "an ExceptionGroup. anyio/trio spawn with start_soon(func, *args).",
               "async with anyio.create_task_group() as tg:\n    for doc in docs:\n        tg.start_soon(embed_doc, doc)",
               "async with trio.open_nursery() as nursery:\n    for doc in docs:\n        nursery.start_soon(embed_doc, doc)"),
    "MIG008": ("task-group-spawn", "mechanical", "low", "tg.create_task(coro(...))",
               "start_soon takes the coroutine function and positional args. Before anyio 4.14 (and always in trio) "
               "it returns None, so results must be written somewhere (dict, list, memory stream).",
               "tg.start_soon(embed_doc, doc)\ntg.start_soon(functools.partial(fetch, url, timeout=10), name=url)",
               "nursery.start_soon(embed_doc, doc)"),
    "MIG009": ("cancelled-error", "mechanical", "low", "except asyncio.CancelledError",
               "The cancellation exception depends on the backend. Catch it only to clean up, then re-raise: under "
               "level-triggered cancellation a swallowed cancel breaks the enclosing cancel scope.",
               "except anyio.get_cancelled_exc_class():\n    with anyio.CancelScope(shield=True):\n"
               "        await client.aclose()\n    raise",
               "except trio.Cancelled:\n    with trio.CancelScope(shield=True):\n        await client.aclose()\n    raise"),
    "MIG010": ("timeout-error", "mechanical", "low", "asyncio.TimeoutError",
               "asyncio.TimeoutError is an alias of the builtin TimeoutError since 3.11, and anyio.fail_after raises "
               "the builtin. trio.fail_after raises trio.TooSlowError instead.",
               "except TimeoutError:", "except trio.TooSlowError:"),
    "MIG011": ("gather", "manual", "medium", "asyncio.gather",
               "gather returns results in order and, without return_exceptions, does NOT cancel the other "
               "awaitables when one fails. A task group cancels siblings on the first error and raises an "
               "ExceptionGroup; results go into a pre-sized list. (anyio >= 4.15 also ships anyio.gather.)",
               "results = [None] * len(prompts)\n\nasync def run_one(i, prompt):\n    results[i] = await llm(prompt)\n\n"
               "async with anyio.create_task_group() as tg:\n    for i, p in enumerate(prompts):\n"
               "        tg.start_soon(run_one, i, p)",
               "results = [None] * len(prompts)\n\nasync def run_one(i, prompt):\n    results[i] = await llm(prompt)\n\n"
               "async with trio.open_nursery() as nursery:\n    for i, p in enumerate(prompts):\n"
               "        nursery.start_soon(run_one, i, p)"),
    "MIG012": ("gather-return-exceptions", "manual", "medium", "asyncio.gather(..., return_exceptions=True)",
               "Partial success: every awaitable runs to completion and errors come back as values. Catch inside "
               "each child and store the exception, so the group never cancels siblings.",
               "async def run_one(i, prompt):\n    try:\n        results[i] = await llm(prompt)\n"
               "    except Exception as exc:          # never get_cancelled_exc_class()\n        results[i] = exc\n\n"
               "async with anyio.create_task_group() as tg:\n    for i, p in enumerate(prompts):\n"
               "        tg.start_soon(run_one, i, p)",
               "async def run_one(i, prompt):\n    try:\n        results[i] = await llm(prompt)\n"
               "    except Exception as exc:\n        results[i] = exc\n\nasync with trio.open_nursery() as nursery:\n"
               "    for i, p in enumerate(prompts):\n        nursery.start_soon(run_one, i, p)"),
    "MIG013": ("wait-for", "manual", "medium", "asyncio.wait_for",
               "Use a cancel scope around the await. Note wait_for returns the value; with fail_after the value "
               "is assigned inside the block.",
               "with anyio.fail_after(10):\n    reply = await llm.complete(prompt)",
               "with trio.fail_after(10):\n    reply = await llm.complete(prompt)"),
    "MIG014": ("create-task", "manual", "high", "asyncio.create_task / ensure_future / loop.create_task",
               "There are no free-floating tasks: every task belongs to a task group/nursery whose block outlives "
               "it. Fire-and-forget becomes a long-lived group (e.g. in the FastAPI lifespan); stored results "
               "become writes into a dict/list or a memory object stream.",
               "async with anyio.create_task_group() as tg:      # owned by the caller or the app lifespan\n"
               "    tg.start_soon(refresh_cache)\n# value needed? tg.start_soon(run_one, i, prompt) writing results[i]",
               "async with trio.open_nursery() as nursery:\n    nursery.start_soon(refresh_cache)"),
    "MIG015": ("queue", "manual", "medium", "asyncio.Queue",
               "Use a memory object stream (anyio) / memory channel (trio): a send and a receive end, a "
               "max_buffer_size for backpressure (0 = rendezvous), clone() per producer and closing semantics that "
               "end consumers' `async for` cleanly instead of sentinels.",
               "send, receive = anyio.create_memory_object_stream[str](max_buffer_size=64)\n"
               "async with send:                 # producer: closing ends the consumer's loop\n"
               "    await send.send(chunk)\nasync with receive:\n    async for chunk in receive: ...",
               "send, receive = trio.open_memory_channel(64)\nasync with send:\n    await send.send(chunk)\n"
               "async with receive:\n    async for chunk in receive: ..."),
    "MIG016": ("queue-join-task-done", "manual", "medium", "Queue.join() / task_done()",
               "Memory streams have no join/task_done. Completion is structural: close every send clone, let "
               "consumers drain and exit, and the task group block returns when all work is done.",
               "async with anyio.create_task_group() as tg:\n    for _ in range(4):\n"
               "        tg.start_soon(worker, receive.clone())\n    async with send:\n        for doc in docs:\n"
               "            await send.send(doc)\n# leaving the group == queue.join()",
               "async with trio.open_nursery() as nursery:\n    for _ in range(4):\n"
               "        nursery.start_soon(worker, receive.clone())\n    async with send:\n        for doc in docs:\n"
               "            await send.send(doc)"),
    "MIG017": ("run-in-executor", "manual", "medium", "loop.run_in_executor",
               "Use to_thread.run_sync with a CapacityLimiter for the pool size; for processes use "
               "anyio.to_process.run_sync (anyio) or trio's trio-parallel / a ProcessPoolExecutor via to_thread.",
               "limiter = anyio.CapacityLimiter(8)\n"
               "text = await anyio.to_thread.run_sync(ocr_page, page, limiter=limiter)\n"
               "vec = await anyio.to_process.run_sync(cpu_heavy, chunk)",
               "limiter = trio.CapacityLimiter(8)\ntext = await trio.to_thread.run_sync(ocr_page, page, limiter=limiter)"),
    "MIG018": ("event-loop-access", "manual", "high", "get_event_loop / get_running_loop / Runner / loop.run_*",
               "There is no loop object to pass around. Use anyio.run at the entry point, anyio.current_time() for "
               "the clock, from_thread/BlockingPortal from foreign threads, and keep loop-specific code behind "
               "the asyncio backend only.",
               "anyio.run(main)\nnow = anyio.current_time()\nwith anyio.from_thread.start_blocking_portal() as portal:\n"
               "    portal.call(async_fn, arg)",
               "trio.run(main)\nnow = trio.current_time()\ntoken = trio.lowlevel.current_trio_token()"),
    "MIG019": ("loop-callbacks", "manual", "high", "loop.call_soon / call_later / call_at",
               "Callbacks become tasks: start a child that sleeps then acts; cancel it through its cancel scope.",
               "async def later(delay, fn, *args):\n    await anyio.sleep(delay)\n    fn(*args)\n\n"
               "tg.start_soon(later, 5, flush_metrics)",
               "async def later(delay, fn, *args):\n    await trio.sleep(delay)\n    fn(*args)\n\n"
               "nursery.start_soon(later, 5, flush_metrics)"),
    "MIG020": ("future", "manual", "high", "asyncio.Future / loop.create_future",
               "A future set by one task and awaited by another becomes an Event plus a value slot, or a "
               "1-item memory stream. (anyio >= 4.15 has anyio.Future; older versions and trio do not.)",
               "class Result:\n    def __init__(self):\n        self.event = anyio.Event()\n        self.value = None\n"
               "    def set(self, value):\n        self.value = value\n        self.event.set()\n"
               "    async def get(self):\n        await self.event.wait()\n        return self.value",
               "send, receive = trio.open_memory_channel(1)\nawait send.send(value)     # producer\n"
               "value = await receive.receive()   # consumer"),
    "MIG021": ("done-callback", "manual", "high", "add_done_callback",
               "Do the follow-up at the end of the child coroutine itself (try/finally), or wrap the coroutine in "
               "a small function that calls the callback after it returns.",
               "async def run_and_report(i, prompt):\n    try:\n        results[i] = await llm(prompt)\n"
               "    finally:\n        progress.update(1)      # was task.add_done_callback(...)",
               "async def run_and_report(i, prompt):\n    try:\n        results[i] = await llm(prompt)\n"
               "    finally:\n        progress.update(1)"),
    "MIG022": ("wait", "manual", "medium", "asyncio.wait (FIRST_COMPLETED / FIRST_EXCEPTION)",
               "FIRST_COMPLETED = race: each child stores its result and cancels the group's scope. "
               "FIRST_EXCEPTION is the default behaviour of a task group.",
               "async def race(*fns):\n    winner = None\n    async with anyio.create_task_group() as tg:\n"
               "        async def run(fn):\n            nonlocal winner\n            winner = await fn()\n"
               "            tg.cancel_scope.cancel()\n        for fn in fns:\n            tg.start_soon(run, fn)\n"
               "    return winner",
               "async def race(*fns):\n    winner = None\n    async with trio.open_nursery() as nursery:\n"
               "        async def run(fn):\n            nonlocal winner\n            winner = await fn()\n"
               "            nursery.cancel_scope.cancel()\n        for fn in fns:\n            nursery.start_soon(run, fn)\n"
               "    return winner"),
    "MIG023": ("as-completed", "manual", "medium", "asyncio.as_completed",
               "Children send (index, result) into a memory stream; the parent iterates the receive end and "
               "handles results in completion order.",
               "send, receive = anyio.create_memory_object_stream[tuple[int, str]](len(prompts))\n"
               "async with anyio.create_task_group() as tg:\n    async def run(i, p, out):\n"
               "        async with out:\n            await out.send((i, await llm(p)))\n"
               "    async with send:\n        for i, p in enumerate(prompts):\n"
               "            tg.start_soon(run, i, p, send.clone())\n    async with receive:\n"
               "        async for i, text in receive:\n            print(i, text)",
               "send, receive = trio.open_memory_channel(len(prompts))\n# same shape with trio.open_nursery()"),
    "MIG024": ("shield", "manual", "medium", "asyncio.shield",
               "Shielding is a property of a cancel scope, not of an awaitable. Shield cleanup only, and put a "
               "timeout on it so shutdown cannot hang.",
               "with anyio.CancelScope(shield=True), anyio.move_on_after(5):\n    await store.flush()",
               "with trio.CancelScope(shield=True):\n    with trio.move_on_after(5):\n        await store.flush()"),
    "MIG025": ("subprocess", "manual", "medium", "asyncio subprocess",
               "Use run_process for run-to-completion and open_process for streaming; output is bytes, check=True "
               "raises CalledProcessError, cancellation kills the child.",
               "result = await anyio.run_process([\"ffprobe\", \"-v\", \"error\", path], check=True)\n"
               "async with await anyio.open_process([\"ollama\", \"serve\"]) as proc:\n"
               "    async for chunk in proc.stdout: ...",
               "result = await trio.run_process([\"ffprobe\", path], capture_stdout=True)"),
    "MIG026": ("streams-and-sockets", "manual", "medium", "open_connection / start_server / loop sockets",
               "anyio has byte streams: connect_tcp (tls=True), create_tcp_listener + serve, BufferedByteReceiveStream "
               "for readline-style framing.",
               "async with await anyio.connect_tcp(host, 443, tls=True) as stream:\n"
               "    await stream.send(payload)\n    data = await stream.receive()",
               "stream = await trio.open_ssl_over_tcp_stream(host, 443)\nawait stream.send_all(payload)"),
    "MIG027": ("signal-handlers", "manual", "medium", "loop.add_signal_handler",
               "Receive signals as an async iterator in a dedicated task and cancel the app scope on SIGTERM.",
               "with anyio.open_signal_receiver(signal.SIGTERM, signal.SIGINT) as signals:\n"
               "    async for signum in signals:\n        tg.cancel_scope.cancel()\n        return",
               "with trio.open_signal_receiver(signal.SIGTERM) as signals:\n    async for signum in signals:\n"
               "        nursery.cancel_scope.cancel()\n        return"),
    "MIG028": ("run-coroutine-threadsafe", "manual", "medium", "asyncio.run_coroutine_threadsafe",
               "From a worker thread started by to_thread.run_sync use from_thread.run(func, *args); from a "
               "foreign thread use a BlockingPortal (start_blocking_portal) owned by the event loop side.",
               "anyio.from_thread.run(send_update, job_id)          # inside to_thread.run_sync workers\n"
               "with anyio.from_thread.start_blocking_portal() as portal:\n    portal.call(client.embed, texts)",
               "trio.from_thread.run(send_update, job_id)"),
    "MIG029": ("task-introspection", "manual", "low", "current_task / all_tasks / asyncio.Task",
               "Use anyio.get_current_task() / get_running_tasks() (TaskInfo objects) for logging and debugging; "
               "there is no Task object to cancel or await.",
               "info = anyio.get_current_task()\nlog.info(\"in %s\", info.name)",
               "task = trio.lowlevel.current_task()\nlog.info(\"in %s\", task.name)"),
    "MIG030": ("task-cancel-from-outside", "manual", "high", "task.cancel() on a stored task",
               "Cancel a cancel scope instead: give the child its own CancelScope (or task group) and call "
               "scope.cancel(). tg.start(...) can hand the scope back to the parent.",
               "async def cancellable(job, *, task_status=anyio.TASK_STATUS_IGNORED):\n"
               "    with anyio.CancelScope() as scope:\n        task_status.started(scope)\n        await job()\n\n"
               "scope = await tg.start(cancellable, job)\nscope.cancel()",
               "async def cancellable(job, *, task_status=trio.TASK_STATUS_IGNORED):\n"
               "    with trio.CancelScope() as scope:\n        task_status.started(scope)\n        await job()\n\n"
               "scope = await nursery.start(cancellable, job)\nscope.cancel()"),
    "MIG031": ("cancellation-swallowed", "manual", "high", "cancellation caught without re-raise",
               "Under anyio/trio cancellation is level-triggered: a swallowed cancel exception leaves the task "
               "running inside a cancelled scope, the next checkpoint raises again, and task groups can hang or "
               "report errors. Always end the handler with `raise`.",
               "except anyio.get_cancelled_exc_class():\n    log.info(\"cancelled\")\n    raise",
               "except trio.Cancelled:\n    log.info(\"cancelled\")\n    raise"),
    "MIG032": ("timeout-advanced", "manual", "medium", "asyncio.timeout(...) as cm / timeout_at / Timeout",
               "Use the cancel scope returned by fail_after/move_on_after: scope.deadline can be read and moved "
               "(reschedule), scope.cancelled_caught tells whether it fired. Deadlines use anyio.current_time().",
               "with anyio.fail_after(30) as scope:\n    scope.deadline = anyio.current_time() + 60   # reschedule\n"
               "    ...",
               "with trio.fail_after(30) as scope:\n    scope.deadline = trio.current_time() + 60"),
    "MIG033": ("coroutine-checks", "manual", "low", "asyncio.iscoroutinefunction / iscoroutine",
               "Use inspect.iscoroutinefunction / inspect.iscoroutine (asyncio.iscoroutinefunction is deprecated in "
               "3.14). inspect does not recognise mock/legacy markers; check tests that pass AsyncMock.",
               "import inspect\nif inspect.iscoroutinefunction(tool.fn): ...",
               "import inspect\nif inspect.iscoroutinefunction(tool.fn): ..."),
    "MIG099": ("other-asyncio-api", "manual", "medium", "other asyncio API",
               "No direct equivalent known to this tool. Check the mapping table in "
               "references/api-mapping-asyncio-anyio-trio.md or keep it behind the asyncio backend.",
               "# see references/api-mapping-asyncio-anyio-trio.md", "# see references/api-mapping-asyncio-anyio-trio.md"),
}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

NAME_RULES = {
    "gather": "MIG011", "wait_for": "MIG013", "create_task": "MIG014", "ensure_future": "MIG014",
    "Queue": "MIG015", "PriorityQueue": "MIG015", "LifoQueue": "MIG015", "QueueEmpty": "MIG015",
    "QueueFull": "MIG015", "QueueShutDown": "MIG015",
    "get_event_loop": "MIG018", "get_running_loop": "MIG018", "new_event_loop": "MIG018",
    "set_event_loop": "MIG018", "get_event_loop_policy": "MIG018", "set_event_loop_policy": "MIG018",
    "Runner": "MIG018", "AbstractEventLoop": "MIG018", "BaseEventLoop": "MIG018", "EventLoop": "MIG018",
    "SelectorEventLoop": "MIG018", "ProactorEventLoop": "MIG018", "DefaultEventLoopPolicy": "MIG018",
    "AbstractEventLoopPolicy": "MIG018", "set_task_factory": "MIG018", "eager_task_factory": "MIG018",
    "Handle": "MIG019", "TimerHandle": "MIG019",
    "Future": "MIG020", "wrap_future": "MIG020", "isfuture": "MIG020", "InvalidStateError": "MIG020",
    "wait": "MIG022", "FIRST_COMPLETED": "MIG022", "FIRST_EXCEPTION": "MIG022", "ALL_COMPLETED": "MIG022",
    "as_completed": "MIG023", "shield": "MIG024",
    "create_subprocess_exec": "MIG025", "create_subprocess_shell": "MIG025", "subprocess": "MIG025",
    "open_connection": "MIG026", "start_server": "MIG026", "open_unix_connection": "MIG026",
    "start_unix_server": "MIG026", "StreamReader": "MIG026", "StreamWriter": "MIG026", "Server": "MIG026",
    "Protocol": "MIG026", "BaseProtocol": "MIG026", "DatagramProtocol": "MIG026", "Transport": "MIG026",
    "IncompleteReadError": "MIG026", "LimitOverrunError": "MIG026",
    "run_coroutine_threadsafe": "MIG028",
    "current_task": "MIG029", "all_tasks": "MIG029", "Task": "MIG029",
    "timeout": "MIG032", "timeout_at": "MIG032", "Timeout": "MIG032",
    "iscoroutine": "MIG033", "iscoroutinefunction": "MIG033",
}
METHOD_RULES = {
    "run_in_executor": "MIG017",
    "call_soon": "MIG019", "call_later": "MIG019", "call_at": "MIG019", "call_soon_threadsafe": "MIG019",
    "create_future": "MIG020",
    "add_done_callback": "MIG021", "remove_done_callback": "MIG021",
    "add_signal_handler": "MIG027", "remove_signal_handler": "MIG027",
    "run_until_complete": "MIG018", "run_forever": "MIG018", "set_exception_handler": "MIG018",
    "set_default_executor": "MIG018", "shutdown_default_executor": "MIG018", "set_debug": "MIG018",
    "create_connection": "MIG026", "create_server": "MIG026", "create_unix_server": "MIG026",
    "create_datagram_endpoint": "MIG026", "sock_recv": "MIG026", "sock_sendall": "MIG026",
    "sock_connect": "MIG026", "sock_accept": "MIG026", "add_reader": "MIG026", "add_writer": "MIG026",
    "connect_read_pipe": "MIG026", "connect_write_pipe": "MIG026", "start_tls": "MIG026",
    "subprocess_exec": "MIG025", "subprocess_shell": "MIG025",
}
SUBMODULES = {"events", "tasks", "locks", "queues", "futures", "exceptions", "timeouts", "taskgroups",
              "runners", "coroutines", "base_events", "streams", "protocols", "transports"}
PRIMITIVES = {"Event", "Lock", "Semaphore", "BoundedSemaphore", "Condition"}
# methods that exist on asyncio primitives but not on the target's (or differ in semantics)
UNSUPPORTED_METHODS = {
    "Event": {"anyio": {"clear"}, "trio": {"clear"}},
    "Lock": {"anyio": {"release"}, "trio": {"release"}},
    "Semaphore": {"anyio": {"locked"}, "trio": {"locked"}},
    "BoundedSemaphore": {"anyio": {"locked"}, "trio": {"locked"}},
    "Condition": {"anyio": set(), "trio": {"wait_for"}},
}
METHOD_REASON = {
    "clear": "Event.clear() is used; anyio/trio Events are one-shot: replace the Event object instead",
    "release": "explicit Lock.release() is used; anyio/trio Locks must be released by the task that acquired "
               "them (RuntimeError otherwise): use `async with lock:`",
    "locked": "Semaphore.locked() is used; anyio/trio Semaphores expose .value instead (`sem.value == 0`)",
    "wait_for": "Condition.wait_for() is used; trio.Condition has no wait_for (loop on `await cond.wait()`)",
}
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".tox", ".mypy_cache", "build", "dist"}


def dotted(node):
    """Return 'a.b.c' for Name/Attribute chains, else ''."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


def root_name(node):
    while isinstance(node, ast.Attribute):
        node = node.value
    return node if isinstance(node, ast.Name) else None


def walk_local(stmts):
    """ast.walk over statements without entering nested functions, classes or lambdas."""
    stack = list(stmts)
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                stack.append(child)


def normalise(qual):
    parts = qual.split(".")
    if len(parts) > 1 and parts[0] in SUBMODULES:
        parts = parts[1:]
    return ".".join(parts)


class SourceMap:
    """Convert ast (line, utf-8 byte column) positions to string offsets."""

    def __init__(self, text):
        self.text = text
        self.lines = text.split("\n")
        self.starts = [0]
        for line in self.lines:
            self.starts.append(self.starts[-1] + len(line) + 1)

    def offset(self, lineno, col):
        line = self.lines[lineno - 1] if 0 < lineno <= len(self.lines) else ""
        return self.starts[lineno - 1] + len(line.encode("utf-8")[:col].decode("utf-8", "replace"))

    def start(self, node):
        return self.offset(node.lineno, node.col_offset)

    def end(self, node):
        return self.offset(node.end_lineno, node.end_col_offset)

    def seg(self, node):
        return self.text[self.start(node):self.end(node)]

    def line_of(self, off):
        lo, hi = 0, len(self.starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.starts[mid] <= off:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1


def apply_edits(text, edits):
    out, pos = [], 0
    for s, e, rep in sorted(edits, key=lambda x: (x[0], x[1])):
        out.append(text[pos:s])
        out.append(rep)
        pos = e
    out.append(text[pos:])
    return "".join(out)


def overlaps(a, b):
    (s1, e1, _), (s2, e2, _) = a, b
    if s1 == e1:  # insertion
        return s2 < s1 < e2
    if s2 == e2:
        return s1 < s2 < e1
    return s1 < e2 and s2 < e1


class Finding:
    def __init__(self, rule, node, sm, kind=None, reason="", note=""):
        self.rule = rule
        self.line = getattr(node, "lineno", 1)
        self.col = getattr(node, "col_offset", 0) + 1
        self.kind = kind or RULES[rule][1]
        self.reason = reason
        self.note = note
        self.edits = []
        self.group = None      # task-group ctor + its spawns are rewritten together or not at all
        self.roots = []        # asyncio alias Name nodes this finding consumes
        self.needs = set()     # imports the rewrite introduces: "target", "functools"
        self.after = None
        line_text = sm.lines[self.line - 1] if 0 < self.line <= len(sm.lines) else ""
        self.code = line_text.strip()

    def to_dict(self, path, target):
        name, _, severity, summary, why, fix_a, fix_t = RULES[self.rule]
        d = {"path": path, "line": self.line, "col": self.col, "rule": self.rule, "name": name,
             "kind": self.kind, "severity": "low" if self.kind == "mechanical" else severity,
             "message": self.message(), "code": self.code}
        if self.kind == "mechanical":
            d["replacement"] = self.after
        else:
            d["fix"] = fix_t if target == "trio" else fix_a
        if self.note:
            d["note"] = self.note
        return d

    def message(self):
        summary = RULES[self.rule][3]
        if self.kind == "mechanical":
            return f"{summary}: rewritten automatically"
        return f"{summary}: {self.reason}" if self.reason else f"{summary}: migrate by hand"


class Migrator:
    def __init__(self, text, path, target, select, ignore):
        self.text = text
        self.path = path
        self.target = target
        self.select = select
        self.ignore = ignore
        self.sm = SourceMap(text)
        self.tree = ast.parse(text, filename=path)
        self.parents = {}
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                self.parents[child] = node
        self.findings = []
        self.handled = set()
        self.module_aliases = set()
        self.from_names = {}
        self.asyncio_imports = []
        self.T = target
        self.F = "functools"
        self.has_target_import = False
        self.has_functools_import = False
        self.annotation_nodes = set()
        self.noqa = {}
        for i, line in enumerate(self.sm.lines, 1):
            m = re.search(r"#\s*noqa(?::\s*([A-Za-z]+[0-9]+(?:\s*,\s*[A-Za-z]+[0-9]+)*))?", line)
            if m:
                self.noqa[i] = None if not m.group(1) else {c.strip().upper() for c in m.group(1).split(",")}
        self._collect_imports()
        self._collect_annotations()
        self.uses_asyncio = bool(self.module_aliases or self.from_names)

    # ------------------------------------------------------------ setup
    def _collect_imports(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                hit = False
                for a in node.names:
                    if a.name == "asyncio" or a.name.startswith("asyncio."):
                        self.module_aliases.add(a.asname or "asyncio")
                        hit = True
                    top_level = node in self.tree.body
                    if a.name == self.target and top_level:
                        self.T = a.asname or self.target
                        self.has_target_import = True
                    if a.name == "functools" and top_level:
                        self.F = a.asname or "functools"
                        self.has_functools_import = True
                if hit:
                    self.asyncio_imports.append(node)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module and (
                    node.module == "asyncio" or node.module.startswith("asyncio.")):
                prefix = normalise(node.module[len("asyncio."):]) if node.module != "asyncio" else ""
                if prefix in SUBMODULES:
                    prefix = ""
                for a in node.names:
                    if a.name == "*":
                        continue
                    self.from_names[a.asname or a.name] = normalise(f"{prefix}.{a.name}" if prefix else a.name)
                self.asyncio_imports.append(node)

    def _collect_annotations(self):
        roots = []
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = node.args
                for a in args.args + args.kwonlyargs + getattr(args, "posonlyargs", []) + \
                        [x for x in (args.vararg, args.kwarg) if x]:
                    if a.annotation is not None:
                        roots.append(a.annotation)
                if node.returns is not None:
                    roots.append(node.returns)
            elif isinstance(node, ast.AnnAssign):
                roots.append(node.annotation)
        for r in roots:
            for n in ast.walk(r):
                self.annotation_nodes.add(n)

    # ------------------------------------------------------------ helpers
    def resolve(self, node):
        """Normalised asyncio name ('sleep', 'subprocess.PIPE') for a Name/Attribute reference, or None."""
        if isinstance(node, ast.Name) and node.id in self.from_names and isinstance(node.ctx, ast.Load):
            return self.from_names[node.id]
        d = dotted(node)
        if d and "." in d:
            head, rest = d.split(".", 1)
            if head in self.module_aliases:
                return normalise(rest)
        return None

    def suppressed(self, rule, line):
        if line in self.noqa:
            codes = self.noqa[line]
            if codes is None or rule in codes:
                return True
        return False

    def add(self, rule, node, kind=None, reason="", note="", roots=()):
        f = Finding(rule, node, self.sm, kind, reason, note)
        f.roots = [r for r in roots if r is not None]
        self.findings.append(f)
        return f

    def ref_root(self, node):
        r = root_name(node)
        return r if r is not None and (r.id in self.module_aliases or r.id in self.from_names) else None

    def mark(self, node):
        self.handled.add(node)
        if isinstance(node, ast.Attribute):
            self.mark(node.value)

    def edit(self, f, s, e, text):
        f.edits.append((s, e, text))

    def methods_on(self, target_text):
        out = set()
        if not target_text:
            return out
        for n in ast.walk(self.tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and dotted(n.func.value) == target_text:
                out.add(n.func.attr)
        return out

    def assigned_target(self, call):
        p = self.parents.get(call)
        if isinstance(p, ast.Assign) and len(p.targets) == 1 and p.value is call:
            return dotted(p.targets[0])
        if isinstance(p, ast.AnnAssign) and p.value is call:
            return dotted(p.target)
        return ""

    def enclosing_scope(self, node):
        p = self.parents.get(node)
        while p is not None and not isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            p = self.parents.get(p)
        return p if p is not None else self.tree

    def call_spread(self, f, inner):
        """Turn `X(inner_func(a, k=v))` into `X(inner_func, a)` or `X(functools.partial(inner_func, a, k=v))`.

        Returns False when the inner call cannot be spread safely.
        """
        if not dotted(inner.func):
            return False
        sm = self.sm
        func_end = sm.end(inner.func)
        call_end = sm.end(inner)
        if inner.keywords:
            self.edit(f, sm.start(inner), sm.start(inner), f"{self.F}.partial(")
            first = min([sm.start(a) for a in inner.args] + [sm.start(k) for k in inner.keywords])
            self.edit(f, func_end, first, ", ")
            f.needs.add("functools")
            return True
        if not inner.args:
            self.edit(f, func_end, call_end, "")
            return True
        self.edit(f, func_end, sm.start(inner.args[0]), ", ")
        self.edit(f, sm.end(inner.args[-1]), call_end, "")
        return True

    # ------------------------------------------------------------ passes
    def analyse(self):
        if not self.uses_asyncio:
            return
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ExceptHandler):
                self.visit_handler(node)
            elif isinstance(node, ast.AsyncWith):
                self.visit_async_with(node)
        self.stored_tasks = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                self.visit_call(node)
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.Attribute, ast.Name)) and node not in self.handled:
                self.visit_ref(node)
        self.visit_methods()
        everything = self.findings
        kept = [f for f in everything if f.rule in self.select and f.rule not in self.ignore
                and not self.suppressed(f.rule, f.line)]
        groups = {}
        for f in everything:
            if f.group is not None:
                groups.setdefault(f.group, []).append(f)
        kept_ids = {id(f) for f in kept}
        for members in groups.values():
            if all(id(m) in kept_ids for m in members):
                continue
            for m in members:
                if m.rule == "MIG007" and id(m) in kept_ids:
                    m.kind, m.edits = "manual", []
                    m.reason = "part of this task group is excluded (noqa / --select / --ignore); migrate by hand"
                elif id(m) in kept_ids:
                    kept_ids.discard(id(m))
        out, seen = [], set()
        for f in sorted(kept, key=lambda x: (x.line, x.col)):
            if id(f) not in kept_ids:
                continue
            if f.kind == "manual" and f.rule != "MIG031":
                if (f.line, f.rule) in seen:
                    continue  # one manual item per rule and line is enough
                seen.add((f.line, f.rule))
            out.append(f)
        self.findings = out

    def visit_handler(self, h):
        if h.type is None:
            return
        elts = h.type.elts if isinstance(h.type, ast.Tuple) else [h.type]
        for e in elts:
            if self.resolve(e) != "CancelledError":
                continue
            self.mark(e)
            note = "re-raise after cleanup: a swallowed cancellation breaks the enclosing cancel scope"
            f = self.add("MIG009", e, note=note, roots=[self.ref_root(e)])
            rep = f"{self.T}.Cancelled" if self.target == "trio" else f"{self.T}.get_cancelled_exc_class()"
            self.edit(f, self.sm.start(e), self.sm.end(e), rep)
            f.needs.add("target")
            reraises = any(isinstance(n, ast.Raise) and (n.exc is None or (
                isinstance(n.exc, ast.Name) and n.exc.id == h.name)) for n in walk_local(h.body))
            if not reraises:
                self.add("MIG031", h, reason="handler does not re-raise; end it with `raise`")

    def visit_async_with(self, node):
        for item in node.items:
            ctx = item.context_expr
            if not isinstance(ctx, ast.Call):
                continue
            name = self.resolve(ctx.func)
            if name == "timeout":
                self.mark(ctx.func)
                self.timeout_block(node, item, ctx)
            elif name == "TaskGroup":
                self.mark(ctx.func)
                self.task_group(node, item, ctx)

    def timeout_block(self, node, item, ctx):
        roots = [self.ref_root(ctx.func)]
        sm = self.sm
        header = self.text[sm.start(node):sm.start(ctx)]
        reason = ""
        if len(node.items) != 1:
            reason = "other context managers share this `async with`; split it into nested blocks first"
        elif item.optional_vars is not None:
            reason = "the Timeout object is bound with `as`; use the cancel scope from fail_after (deadline)"
        elif len(ctx.args) != 1 or ctx.keywords or isinstance(ctx.args[0], ast.Starred):
            reason = "unexpected arguments"
        elif not re.fullmatch(r"async\s+with\s+", header):
            reason = "parenthesised or unusual header; rewrite by hand"
        elif self.target == "trio":
            arg = ctx.args[0]
            if isinstance(arg, ast.Constant) and arg.value is None:
                reason = "trio.fail_after does not accept None; use math.inf or drop the timeout"
            else:
                builtin = self.builtin_timeout_handlers()
                if builtin:
                    reason = (f"trio.fail_after raises trio.TooSlowError, which `except TimeoutError` on line "
                              f"{builtin[0]} does not catch; update the handler, then rewrite")
        if reason:
            self.add("MIG032", ctx, reason=reason, roots=roots)
            return
        note = "raises trio.TooSlowError" if self.target == "trio" else ""
        f = self.add("MIG006", node, note=note, roots=roots)
        self.edit(f, sm.start(node), sm.end(ctx.func), f"with {self.T}.fail_after")
        f.needs.add("target")

    def builtin_timeout_handlers(self):
        lines = []
        for n in ast.walk(self.tree):
            if isinstance(n, ast.ExceptHandler) and n.type is not None:
                elts = n.type.elts if isinstance(n.type, ast.Tuple) else [n.type]
                if any(isinstance(e, ast.Name) and e.id == "TimeoutError" and e.id not in self.from_names
                       for e in elts):
                    lines.append(n.lineno)
        return sorted(lines)

    def task_group(self, node, item, ctx):
        sm = self.sm
        roots = [self.ref_root(ctx.func)]
        reason, spawns = "", []
        target = item.optional_vars
        if ctx.args or ctx.keywords:
            reason = "TaskGroup() called with arguments"
        elif target is not None and not isinstance(target, ast.Name):
            reason = "task group bound to a non-name target"
        elif target is not None:
            name = target.id
            scope = self.enclosing_scope(node)
            for n in ast.walk(scope):
                if not (isinstance(n, ast.Name) and n.id == name) or n is target:
                    continue
                owner = self.owning_group(n, name)
                if owner is None:
                    reason = f"`{name}` is used outside the `async with` block (line {n.lineno})"
                    break
                if owner is not node:
                    continue
                if self.enclosing_scope(n) is not scope:
                    reason = f"`{name}` is captured by a nested function or lambda (line {n.lineno})"
                    break
                attr = self.parents.get(n)
                call = self.parents.get(attr)
                stmt = self.parents.get(call)
                if not (isinstance(attr, ast.Attribute) and attr.attr == "create_task"
                        and isinstance(call, ast.Call) and call.func is attr):
                    reason = f"`{name}` is used for something other than create_task (line {n.lineno})"
                    break
                if not isinstance(stmt, ast.Expr):
                    reason = f"the task returned by create_task is used (line {n.lineno}); start_soon returns no task"
                    break
                if len(call.args) != 1 or not isinstance(call.args[0], ast.Call) \
                        or not dotted(call.args[0].func) \
                        or any(k.arg not in ("name",) for k in call.keywords):
                    reason = (f"create_task on line {n.lineno} is not `create_task(func(...))` with only name=; "
                              "spread it by hand")
                    break
                spawns.append(call)
        if reason:
            self.add("MIG007", ctx, kind="manual", reason=reason, roots=roots)
            return
        f = self.add("MIG007", ctx, roots=roots)
        f.group = id(node)
        rep = f"{self.T}.open_nursery()" if self.target == "trio" else f"{self.T}.create_task_group()"
        self.edit(f, sm.start(ctx), sm.end(ctx), rep)
        f.needs.add("target")
        for call in spawns:
            g = self.add("MIG008", call)
            g.group = id(node)
            attr = call.func
            self.edit(g, sm.end(attr.value), sm.end(attr), ".start_soon")
            self.call_spread(g, call.args[0])
            self.handled.add(attr)

    def owning_group(self, n, name):
        p = self.parents.get(n)
        while p is not None:
            if isinstance(p, ast.AsyncWith):
                for it in p.items:
                    if isinstance(it.optional_vars, ast.Name) and it.optional_vars.id == name:
                        if self.sm.start(p.body[0]) <= self.sm.start(n):
                            return p
            p = self.parents.get(p)
        return None

    def visit_call(self, node):
        name = self.resolve(node.func)
        if name is None or node.func in self.handled:
            return
        self.mark(node.func)
        roots = [self.ref_root(node.func)]
        sm = self.sm
        func_rep = None
        if name == "run":
            self.asyncio_run(node, roots)
        elif name == "sleep":
            if len(node.args) == 1 and not node.keywords and not isinstance(node.args[0], ast.Starred):
                f = self.add("MIG003", node, roots=roots)
                func_rep = f"{self.T}.sleep"
                self.edit(f, sm.start(node.func), sm.end(node.func), func_rep)
                f.needs.add("target")
                if self.target == "trio":
                    f.note = "trio.sleep raises ValueError for negative delays"
            else:
                self.add("MIG003", node, kind="manual", roots=roots,
                         reason="sleep(delay, result) has no equivalent; sleep, then use the value")
        elif name in PRIMITIVES:
            self.primitive_call(node, name, roots)
        elif name == "to_thread":
            if any(isinstance(a, ast.Starred) for a in node.args) and any(k.arg is None for k in node.keywords):
                self.add("MIG005", node, kind="manual", roots=roots, reason="*args and **kwargs together")
                return
            f = self.add("MIG005", node, roots=roots,
                         note="cancellation now waits for the thread; pass abandon_on_cancel=True to keep "
                              "asyncio's behaviour")
            self.edit(f, sm.start(node.func), sm.end(node.func), f"{self.T}.to_thread.run_sync")
            f.needs.add("target")
            if node.keywords:
                if not node.args:
                    self.add("MIG005", node, kind="manual", roots=roots, reason="function passed by keyword")
                    self.findings.remove(f)
                    return
                last = max([sm.end(a) for a in node.args] + [sm.end(k) for k in node.keywords])
                self.edit(f, sm.start(node.args[0]), sm.start(node.args[0]), f"{self.F}.partial(")
                self.edit(f, last, last, ")")
                f.needs.add("functools")
        elif name == "TaskGroup":
            self.add("MIG007", node, kind="manual", roots=roots,
                     reason="TaskGroup not used directly in `async with ... as tg`")
        elif name == "gather":
            rex = [k for k in node.keywords if k.arg == "return_exceptions"]
            if rex and not (isinstance(rex[0].value, ast.Constant) and rex[0].value.value is False):
                self.add("MIG012", node, roots=roots,
                         reason="return_exceptions=True: catch per child and store the exception")
            else:
                self.add("MIG011", node, roots=roots,
                         reason="becomes a task group writing into a results list (siblings get cancelled on error)")
        elif name in ("create_task", "ensure_future"):
            stored = not isinstance(self.parents.get(node), ast.Expr)
            if stored:
                tgt = self.assigned_target(node)
                if tgt:
                    self.stored_tasks.add(tgt)
            self.add("MIG014", node, roots=roots,
                     reason="task result is stored; write results into a container from a task-group child"
                     if stored else "fire-and-forget task; start it in a task group that outlives it")
        elif name == "run_coroutine_threadsafe":
            self.add("MIG028", node, roots=roots, reason="use from_thread.run / a BlockingPortal")
        else:
            self.visit_ref(node.func, force=True)

    def asyncio_run(self, node, roots):
        sm = self.sm
        reason = ""
        inner = node.args[0] if len(node.args) == 1 else None
        if node.keywords:
            reason = "keyword arguments (debug=, loop_factory=) map to backend_options; rewrite by hand"
        elif inner is None or not isinstance(inner, ast.Call):
            reason = "argument is not a direct coroutine call; pass the coroutine function and its args"
        elif not dotted(inner.func):
            reason = "coroutine function is a complex expression; bind it to a name first"
        elif any(isinstance(a, ast.Starred) for a in inner.args) and any(k.arg is None for k in inner.keywords):
            reason = "*args and **kwargs together; use functools.partial by hand"
        if reason:
            self.add("MIG002", node, kind="manual", reason=reason, roots=roots)
            return
        f = self.add("MIG002", node, roots=roots)
        self.edit(f, sm.start(node.func), sm.end(node.func), f"{self.T}.run")
        f.needs.add("target")
        self.call_spread(f, inner)

    def primitive_call(self, node, name, roots):
        sm = self.sm
        new = "Semaphore" if name == "BoundedSemaphore" else name
        reason = ""
        tgt = self.assigned_target(node)
        bad = UNSUPPORTED_METHODS[name][self.target] & self.methods_on(tgt)
        if name == "Event" and self.event_clear_used():
            bad.add("clear")
        if bad:
            reason = METHOD_REASON[sorted(bad)[0]]
        elif any(isinstance(a, ast.Starred) for a in node.args) or any(k.arg is None for k in node.keywords):
            reason = "star-arguments"
        elif name in ("Event", "Lock") and (node.args or node.keywords):
            reason = "unexpected arguments (the loop= parameter was removed in 3.10)"
        elif name == "Condition" and (len(node.args) > 1 or node.keywords and node.keywords[0].arg != "lock"):
            reason = "unexpected arguments"
        elif name in ("Semaphore", "BoundedSemaphore"):
            if len(node.args) + len(node.keywords) > 1 or (node.keywords and node.keywords[0].arg != "value"):
                reason = "unexpected arguments"
        if reason:
            self.add("MIG004", node, kind="manual", reason=reason, roots=roots)
            return
        f = self.add("MIG004", node, roots=roots)
        f.needs.add("target")
        if name in ("Semaphore", "BoundedSemaphore"):
            val = node.args[0] if node.args else (node.keywords[0].value if node.keywords else None)
            if name == "BoundedSemaphore":
                if val is None:
                    self.edit(f, sm.start(node), sm.end(node), f"{self.T}.Semaphore(1, max_value=1)")
                    return
                if not isinstance(val, (ast.Constant, ast.Name)):
                    self.findings.remove(f)
                    self.add("MIG004", node, kind="manual", roots=roots,
                             reason="BoundedSemaphore value is an expression; use Semaphore(n, max_value=n)")
                    return
            if val is None:
                self.edit(f, sm.start(node), sm.end(node), f"{self.T}.Semaphore(1)")
                return
            self.edit(f, sm.start(node.func), sm.end(node.func), f"{self.T}.Semaphore")
            if node.keywords:
                kw = node.keywords[0]
                self.edit(f, sm.start(kw), sm.start(kw.value), "")
            if name == "BoundedSemaphore":
                self.edit(f, sm.end(val), sm.end(val), f", max_value={sm.seg(val)}")
            return
        self.edit(f, sm.start(node.func), sm.end(node.func), f"{self.T}.{new}")

    def event_clear_used(self):
        if not hasattr(self, "_event_clear"):
            targets = set()
            for n in ast.walk(self.tree):
                if isinstance(n, ast.Call) and self.resolve(n.func) == "Event":
                    t = self.assigned_target(n)
                    if t:
                        targets.add(t)
            hit = False
            for n in ast.walk(self.tree):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "clear" \
                        and not n.args:
                    d = dotted(n.func.value)
                    if d in targets or "event" in d.rsplit(".", 1)[-1].lower():
                        hit = True
            self._event_clear = hit
        return self._event_clear

    def visit_ref(self, node, force=False):
        if node in self.handled and not force:
            return
        if isinstance(node, ast.Name) and node.id in self.module_aliases and isinstance(node.ctx, ast.Load):
            p = self.parents.get(node)
            if not (isinstance(p, ast.Attribute) and p.value is node):
                self.mark(node)
                self.add("MIG099", node, reason="the asyncio module object itself is used", roots=[node])
            return
        name = self.resolve(node)
        if name is None:
            return
        p = self.parents.get(node)
        if isinstance(p, ast.Attribute) and p.value is node and self.resolve(p) is not None and not force:
            return  # visit the outermost chain only
        self.mark(node)
        roots = [self.ref_root(node)]
        sm = self.sm
        if name == "TimeoutError":
            f = self.add("MIG010", node, roots=roots)
            rep = f"{self.T}.TooSlowError" if self.target == "trio" else "TimeoutError"
            self.edit(f, sm.start(node), sm.end(node), rep)
            if self.target == "trio":
                f.needs.add("target")
            else:
                f.note = "identical on 3.11+; on 3.9/3.10 only once the raiser (wait_for) is migrated too"
            return
        if name in ("Event", "Lock", "Condition", "Semaphore") and (
                node in self.annotation_nodes or name in ("Event", "Lock", "Condition")):
            if name == "Event" and self.event_clear_used():
                self.add("MIG004", node, kind="manual", reason=METHOD_REASON["clear"], roots=roots)
                return
            f = self.add("MIG004", node, roots=roots)
            self.edit(f, sm.start(node), sm.end(node), f"{self.T}.{name}")
            f.needs.add("target")
            return
        if name in PRIMITIVES:
            self.add("MIG004", node, kind="manual", roots=roots,
                     reason="used as a factory; anyio/trio Semaphore needs an explicit initial value")
            return
        if name == "CancelledError":
            self.add("MIG009", node, kind="manual", roots=roots,
                     reason="CancelledError used outside an except clause; use get_cancelled_exc_class() / "
                            "cancel a scope instead of raising it")
            return
        if name == "run":
            self.add("MIG002", node, kind="manual", roots=roots, reason="asyncio.run used as a value")
            return
        if name in ("sleep", "to_thread"):
            rule = "MIG003" if name == "sleep" else "MIG005"
            self.add(rule, node, kind="manual", roots=roots, reason="used as a value, not called")
            return
        if name == "TaskGroup":
            self.add("MIG007", node, kind="manual", roots=roots,
                     reason="TaskGroup referenced as a type; use anyio.abc.TaskGroup / trio.Nursery")
            return
        head = name.split(".", 1)[0]
        rule = NAME_RULES.get(name) or NAME_RULES.get(head) or "MIG099"
        reason = "" if rule != "MIG099" else f"asyncio.{name} has no mapping in this tool"
        self.add(rule, node, roots=roots, reason=reason)

    def visit_methods(self):
        queues = ("Queue", "PriorityQueue", "LifoQueue")
        queue_used = any(self.resolve(n) in queues
                         for n in ast.walk(self.tree) if isinstance(n, (ast.Name, ast.Attribute)))
        queue_targets = set()
        for n in ast.walk(self.tree):
            if isinstance(n, ast.Call) and self.resolve(n.func) in queues:
                queue_targets.add(self.assigned_target(n))
            elif isinstance(n, ast.arg) and n.annotation is not None:
                ann = n.annotation.value if isinstance(n.annotation, ast.Subscript) else n.annotation
                if self.resolve(ann) in queues:
                    queue_targets.add(n.arg)
        queue_targets.discard("")
        modules = {a.asname or a.name.split(".")[0] for n in ast.walk(self.tree) if isinstance(n, ast.Import)
                   for a in n.names} - self.module_aliases
        tg_names = set()
        for n in ast.walk(self.tree):
            if isinstance(n, ast.AsyncWith):
                for it in n.items:
                    if isinstance(it.optional_vars, ast.Name):
                        tg_names.add(it.optional_vars.id)
        seen = {(f.line, f.rule) for f in self.findings}
        for n in ast.walk(self.tree):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)) or n.func in self.handled:
                continue
            attr = n.func.attr
            recv = dotted(n.func.value)
            root = root_name(n.func.value)
            if root is not None and root.id in modules:
                continue  # socket.create_connection, subprocess.run, ...: not an event loop method
            rule, reason = METHOD_RULES.get(attr), ""
            if attr == "create_task" and recv not in tg_names:
                rule, reason = "MIG014", "loop.create_task: start it in a task group instead"
            elif attr == "task_done" and queue_used:
                rule = "MIG016"
            elif attr == "join" and queue_used and not n.args and (
                    recv in queue_targets or isinstance(self.parents.get(n), ast.Await)):
                rule = "MIG016"
            elif attr == "cancel" and recv and recv in self.stored_tasks:
                rule = "MIG030"
            if rule and (n.lineno, rule) not in seen:
                seen.add((n.lineno, rule))
                self.add(rule, n, reason=reason)

    # ------------------------------------------------------------ rewrite
    def rewrite(self):
        """Apply mechanical findings; return (new_text, import findings)."""
        accepted, units, seen_groups = [], [], {}
        for f in sorted(self.findings, key=lambda x: (x.line, x.col)):
            if f.kind != "mechanical" or not f.edits:
                continue
            if f.group is None:
                units.append([f])
            elif f.group in seen_groups:
                seen_groups[f.group].append(f)
            else:
                seen_groups[f.group] = [f]
                units.append(seen_groups[f.group])
        for unit in units:
            edits = [e for f in unit for e in f.edits]
            if any(overlaps(e, a) for e in edits for a in accepted):
                for f in unit:
                    f.kind, f.reason = "manual", "overlapping rewrite with another item; migrate by hand"
                continue
            accepted.extend(edits)
        applied = [f for f in self.findings if f.kind == "mechanical" and f.edits]
        for f in applied:
            f.after = self.preview(f.edits)
        new_text = apply_edits(self.text, accepted)
        consumed = {id(r) for f in applied for r in f.roots}
        needs = set().union(*[f.needs for f in applied]) if applied else set()
        return self.fix_imports(new_text, consumed, needs)

    def preview(self, edits):
        lo = min(e[0] for e in edits)
        hi = max(e[1] for e in edits)
        first = self.sm.line_of(lo)
        last = self.sm.line_of(max(hi - 1, lo))
        s, e = self.sm.starts[first - 1], self.sm.starts[last] - 1
        local = [(a - s, b - s, t) for a, b, t in edits]
        out = apply_edits(self.text[s:e], local).strip("\n").splitlines()
        indent = min((len(x) - len(x.lstrip()) for x in out if x.strip()), default=0)
        out = [x[indent:] for x in out]
        return "\n".join(out[:6] + (["..."] if len(out) > 6 else []))

    def fix_imports(self, new_text, consumed, needs):
        """Drop asyncio imports nobody uses any more and add the target / functools imports."""
        still = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name) and (node.id in self.module_aliases or node.id in self.from_names) \
                    and id(node) not in consumed and not isinstance(node.ctx, ast.Store):
                still.add(node.id)
        tree2 = ast.parse(new_text)
        sm2 = SourceMap(new_text)
        parents2 = {c: p for p in ast.walk(tree2) for c in ast.iter_child_nodes(p)}
        imports2 = [n for n in ast.walk(tree2) if isinstance(n, (ast.Import, ast.ImportFrom))
                    and any(self._is_asyncio_alias(n, a) for a in n.names)]
        imports1 = [n for n in ast.walk(self.tree) if isinstance(n, (ast.Import, ast.ImportFrom))
                    and any(self._is_asyncio_alias(n, a) for a in n.names)]
        original_line = {id(b): a.lineno for a, b in zip(imports1, imports2)}
        edits, import_findings = [], []
        need_lines = []
        if "target" in needs and not self.has_target_import:
            need_lines.append(f"import {self.target}")
        if "functools" in needs and not self.has_functools_import:
            need_lines.append("import functools")
        need_lines.sort()
        placed = False
        for node in imports2:
            keep = [a for a in node.names if not self._is_asyncio_alias(node, a)
                    or (a.asname or a.name.split(".")[0]) in still
                    or self.suppressed("MIG001", original_line.get(id(node), node.lineno))
                    or "MIG001" not in self.select or "MIG001" in self.ignore]
            dropped = [a for a in node.names if a not in keep]
            f = Finding("MIG001", node, self.sm)
            f.line = original_line.get(id(node), node.lineno)
            f.code = (self.sm.lines[f.line - 1] if f.line <= len(self.sm.lines) else "").strip()
            if not dropped:
                if not self.suppressed("MIG001", f.line) and "MIG001" in self.select \
                        and "MIG001" not in self.ignore:
                    f.kind = "manual"
                    left = sorted(a.asname or a.name for a in node.names if self._is_asyncio_alias(node, a))
                    f.reason = f"kept: {', '.join(left)} still used by items above (asyncio-only code left)"
                    import_findings.append(f)
                continue
            s, e = sm2.start(node), sm2.end(node)
            if keep:
                rep = self._render_import(node, keep)
            else:
                rep = ""
            top = parents2.get(node) is tree2
            if not placed and top and need_lines and not keep:
                rep = "\n".join(need_lines)
                placed = True
            line_start = sm2.starts[node.lineno - 1]
            line_end = sm2.starts[node.end_lineno] - 1 if node.end_lineno < len(sm2.starts) else len(new_text)
            before = new_text[line_start:s]
            after = new_text[e:line_end]
            if not rep:
                parent = parents2.get(node)
                siblings = getattr(parent, "body", None)
                alone = isinstance(siblings, list) and node in siblings and len(siblings) == 1
                if alone or before.strip() or (after.strip() and not after.strip().startswith("#")):
                    rep = "pass"
                else:
                    s, e = line_start, min(line_end + 1, len(new_text))
            edits.append((s, e, rep))
            f.kind = "mechanical"
            f.after = rep.strip() or "(removed)"
            import_findings.append(f)
        if need_lines and not placed:
            pos = self._insert_point(tree2, sm2, new_text)
            edits.append((pos, pos, "\n".join(need_lines) + "\n"))
        final = apply_edits(new_text, edits) if edits else new_text
        import_findings = [f for f in import_findings if "MIG001" in self.select and "MIG001" not in self.ignore
                           and not self.suppressed("MIG001", f.line)]
        return final, import_findings

    def _is_asyncio_alias(self, node, alias):
        if isinstance(node, ast.Import):
            return alias.name == "asyncio" or alias.name.startswith("asyncio.")
        return node.level == 0 and bool(node.module) and (
            node.module == "asyncio" or node.module.startswith("asyncio.")) and alias.name != "*"

    @staticmethod
    def _render_import(node, aliases):
        names = ", ".join(a.name + (f" as {a.asname}" if a.asname else "") for a in aliases)
        if isinstance(node, ast.Import):
            return f"import {names}"
        return f"from {node.module} import {names}"

    @staticmethod
    def _insert_point(tree, sm, text):
        body = tree.body
        idx = 0
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            idx = 1
        while idx < len(body) and isinstance(body[idx], ast.ImportFrom) and body[idx].module == "__future__":
            idx += 1
        for node in body[idx:]:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                return sm.starts[node.lineno - 1]
        if idx == 0:
            return 0
        prev = body[idx - 1]
        return min(sm.starts[prev.end_lineno], len(text)) if prev.end_lineno < len(sm.starts) else len(text)


# ---------------------------------------------------------------- driver

def migrate_source(text, path, target, select, ignore):
    m = Migrator(text, path, target, select, ignore)
    m.analyse()
    new_text, import_findings = m.rewrite()
    findings = sorted(m.findings + import_findings, key=lambda f: (f.line, f.col, f.rule))
    return findings, new_text


def expand(paths, warnings):
    for p in paths:
        if p != "-" and os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                for name in sorted(files):
                    if name.endswith(".py"):
                        yield os.path.join(root, name), True
        else:
            yield p, False


def parse_rule_list(values):
    out = set()
    for v in values or []:
        for tok in v.split(","):
            tok = tok.strip()
            if not tok:
                continue
            matched = [rid for rid, meta in RULES.items() if rid.startswith(tok.upper()) or meta[0] == tok]
            if not matched:
                raise ValueError(f"unknown rule {tok!r}; run --list-rules")
            out.update(matched)
    return out


def print_rules(target, as_json):
    rows = []
    for rid, (name, kind, sev, summary, why, fix_a, fix_t) in RULES.items():
        rows.append({"rule": rid, "name": name, "kind": kind, "severity": sev, "summary": summary, "why": why,
                     "fix": fix_t if target == "trio" else fix_a})
    if as_json:
        print(json.dumps({"target": target, "rules": rows}, indent=2))
        return
    for r in rows:
        print(f"{r['rule']} {r['name']} [{r['kind']}, {r['severity']}]: {r['summary']}")
        print(f"    why: {r['why']}")
        print("    fix: " + r["fix"].replace("\n", "\n         "))
        print()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="Python files or directories, or - for stdin")
    ap.add_argument("--target", choices=("anyio", "trio"), default="anyio", help="library to migrate to (default anyio)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--diff", action="store_true", help="print a unified diff of the automatic rewrites")
    mode.add_argument("--write", action="store_true", help="rewrite files in place (keeps <file>.bak)")
    mode.add_argument("--check", action="store_true", help="exit 1 if any asyncio usage remains (CI gate)")
    ap.add_argument("--force", action="store_true", help="with --write: write even when manual items remain")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any manual item is reported")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--select", action="append", help="only these rules (ids, id prefixes or names; comma list)")
    ap.add_argument("--ignore", action="append", help="skip these rules (ids, id prefixes or names; comma list)")
    ap.add_argument("--list-rules", action="store_true", help="print every rule with why and fix, then exit")
    args = ap.parse_args(argv)

    if args.list_rules:
        print_rules(args.target, args.json)
        return 0
    if not args.paths:
        ap.error("give at least one file, directory or - (stdin)")
    if args.force and not args.write:
        ap.error("--force only applies to --write")
    if args.write and "-" in args.paths:
        ap.error("--write cannot rewrite stdin; use --diff")
    if args.paths.count("-") > 1:
        ap.error("stdin (-) can be given only once")
    try:
        select = parse_rule_list(args.select) or set(RULES)
        ignore = parse_rule_list(args.ignore)
    except ValueError as err:
        ap.error(str(err))

    results, errors, warnings = [], [], []
    hard_error = False
    for path, walked in expand(args.paths, warnings):
        label = "<stdin>" if path == "-" else path
        try:
            if path == "-":
                text = sys.stdin.read()
            else:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
            findings, new_text = migrate_source(text, label, args.target, select, ignore)
        except SyntaxError as err:
            msg = f"{label}:{err.lineno}: cannot parse: {err.msg}"
            (warnings if walked else errors).append(msg)
            hard_error |= not walked
            continue
        except (OSError, UnicodeDecodeError) as err:
            msg = f"{label}: cannot read: {err}"
            (warnings if walked else errors).append(msg)
            hard_error |= not walked
            continue
        try:
            ast.parse(new_text, filename=label)
        except SyntaxError as err:
            errors.append(f"{label}: rewrite produced invalid Python at line {err.lineno} ({err.msg}); "
                          "nothing written. Please report this with the input file.")
            hard_error = True
            continue
        results.append({"path": label, "text": text, "new": new_text, "findings": findings})

    refused = 0
    out_files = []
    for r in results:
        fl = r["findings"]
        mech = sum(f.kind == "mechanical" for f in fl)
        man = sum(f.kind == "manual" for f in fl)
        entry = {"path": r["path"], "mechanical": mech, "manual": man, "changed": r["new"] != r["text"],
                 "findings": [f.to_dict(r["path"], args.target) for f in fl]}
        if args.diff:
            entry["diff"] = "".join(difflib.unified_diff(
                r["text"].splitlines(True), r["new"].splitlines(True),
                fromfile=f"a/{r['path'].lstrip('/')}", tofile=f"b/{r['path'].lstrip('/')}"))
            if entry["diff"] and not entry["diff"].endswith("\n"):
                entry["diff"] += "\n\\ No newline at end of file\n"
        if args.write:
            if man and not args.force:
                entry["refused"] = f"{man} manual item(s) remain; migrate them or pass --force"
                refused += 1
            elif entry["changed"]:
                backup = r["path"] + ".bak"
                try:
                    shutil.copy2(r["path"], backup)
                    with open(r["path"], "w", encoding="utf-8") as fh:
                        fh.write(r["new"])
                except OSError as err:
                    errors.append(f"{r['path']}: cannot write: {err}")
                    hard_error = True
                    continue
                entry["written"], entry["backup"] = True, backup
        out_files.append(entry)

    total_mech = sum(e["mechanical"] for e in out_files)
    total_man = sum(e["manual"] for e in out_files)
    mode_name = "diff" if args.diff else "write" if args.write else "check" if args.check else "report"
    if args.json:
        print(json.dumps({"target": args.target, "mode": mode_name, "files": out_files,
                          "summary": {"files": len(out_files), "mechanical": total_mech, "manual": total_man,
                                      "refused": refused},
                          "errors": errors, "warnings": warnings}, indent=2))
    else:
        for w in warnings:
            print(f"warning: skipped {w}", file=sys.stderr)
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        if args.diff:
            for e in out_files:
                sys.stdout.write(e["diff"])
            print(f"# {total_mech} automatic rewrite(s), {total_man} manual item(s) left "
                  f"(target: {args.target}); run without --diff for the manual guidance", file=sys.stderr)
        elif args.write:
            for e in out_files:
                if e.get("refused"):
                    print(f"refused {e['path']}: {e['refused']}")
                elif e.get("written"):
                    print(f"wrote {e['path']} ({e['mechanical']} rewrite(s); backup {e['backup']})"
                          + (f"; {e['manual']} manual item(s) left" if e["manual"] else ""))
                else:
                    print(f"unchanged {e['path']}")
        else:
            print_report(out_files, args.target, args.check, total_mech, total_man)
    if hard_error:
        return 2
    if args.check and (total_mech or total_man):
        return 1
    if args.write and refused:
        return 1
    if args.strict and total_man:
        return 1
    return 0


def print_report(files, target, check, mech, man):
    n_files = len(files)
    if not mech and not man:
        if n_files:
            print(f"No asyncio usage found in {n_files} file(s); nothing to migrate (target: {target}).")
        return
    for e in files:
        for f in e["findings"]:
            print(f"{f['path']}:{f['line']}:{f['col']}: {f['rule']} [{f['kind']}] {f['name']}: {f['message']}")
            if f["code"]:
                print(f"    > {f['code']}")
            if f["kind"] == "mechanical":
                print("    = " + (f.get("replacement") or "").replace("\n", "\n      "))
            else:
                print("    fix: " + f["fix"].replace("\n", "\n         "))
            if f.get("note"):
                print(f"    note: {f['note']}")
            print()
    head = "asyncio usage remains" if check else "Migration report"
    print(f"{head}: {mech + man} item(s) in {n_files} file(s): {mech} mechanical, {man} manual "
          f"(target: {target})")
    if mech:
        print("Apply the mechanical rewrites with --diff (preview) or --write.")


if __name__ == "__main__":
    sys.exit(main())
