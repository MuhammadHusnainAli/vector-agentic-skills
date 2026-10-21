#!/usr/bin/env python3
"""Lint asyncio code: blocking calls, lost tasks, swallowed cancellation, unbounded fan-out.

Static analysis only: the analysed code is parsed with `ast`, never imported
or executed. Rules (run --list-rules for the why and a fix snippet of each):

  AIO001 blocking-sleep            time.sleep() inside async def
  AIO002 blocking-http             requests / urllib / sync httpx / sync OpenAI-style client in async def
  AIO003 blocking-subprocess       subprocess.run/call/check_output, os.system in async def
  AIO004 blocking-file-io          open(), Path.read_text/write_text, shutil copies in async def
  AIO005 blocking-db               sqlite3 / psycopg2 / pymysql / redis.Redis / sync vector-store client
  AIO006 blocking-socket-or-input  input(), blocking socket recv/accept/connect, DNS lookups
  AIO007 coroutine-not-awaited     coroutine called as a statement and never awaited
  AIO008 dangling-task             create_task / ensure_future result discarded (task can be GC'd)
  AIO009 nested-asyncio-run        asyncio.run() inside async def
  AIO010 get-event-loop            asyncio.get_event_loop() (deprecated pattern)
  AIO011 run-until-complete-in-async loop.run_until_complete() inside async def
  AIO012 unbounded-gather          gather(*[f(x) for x in items]) with no concurrency limit
  AIO013 sequential-await-loop     `for x in items: r = await f(x)` over independent items
  AIO014 cancellation-swallowed    bare except / BaseException / CancelledError not re-raised
  AIO015 wait-for-on-311           asyncio.wait_for when --target-version >= 3.11
  AIO016 thread-primitive-in-async threading.Lock / queue.Queue / threading.Event used in async def
  AIO017 async-without-await       async def that never awaits
  AIO018 sleep-zero-busy-wait      `while ...: await asyncio.sleep(0)` polling loop
  AIO019 client-without-async-with AsyncClient / ClientSession / aiofiles.open never closed
  AIO020 task-never-awaited        task stored in a variable that is never used again
  AIO021 unbounded-queue           asyncio.Queue() without maxsize used as a pipeline buffer
  AIO022 return-exceptions-unchecked gather(..., return_exceptions=True) results never checked
  AIO023 sync-route-asyncio-run    sync FastAPI/Starlette route that calls asyncio.run
  AIO024 version-feature           asyncio API newer than --target-version (TaskGroup, timeout, ...)

Suppress a finding on its line with `# noqa` or `# noqa: AIO001,AIO013`.

Usage:
    python async_lint.py app/llm_client.py
    python async_lint.py src/ tests/ --json
    cat worker.py | python async_lint.py -
    python async_lint.py src/ --strict --target-version 3.9
    python async_lint.py src/ --select AIO001,AIO008 --ignore sequential-await-loop
    python async_lint.py --list-rules

Exit codes: 0 no findings (or findings without --strict), 1 findings with
--strict, 2 usage error, or a file named on the command line that cannot be
read or parsed. Files found by walking a directory that cannot be parsed are
reported as warnings and skipped.

No dependencies (standard library only, Python 3.9+).
"""

import argparse
import ast
import json
import os
import re
import sys

# ---------------------------------------------------------------- rules

RULES = {
    "AIO001": {
        "name": "blocking-sleep", "severity": "high",
        "summary": "time.sleep() inside async def",
        "why": "time.sleep blocks the event loop thread, so every other task (in-flight LLM calls, the web "
               "server, heartbeats) freezes for the whole delay.",
        "fix": "await asyncio.sleep(delay)",
    },
    "AIO002": {
        "name": "blocking-http", "severity": "high",
        "summary": "synchronous HTTP (requests, urllib, httpx.Client, sync OpenAI/Anthropic client) in async def",
        "why": "A sync HTTP call holds the loop for the full network round trip; 100 concurrent LLM calls "
               "become 100 sequential ones and the server stops answering health checks.",
        "fix": "async with httpx.AsyncClient(timeout=30) as http:   # create once, reuse\n"
               "    resp = await http.get(url)\n"
               "# SDKs: openai.AsyncOpenAI / anthropic.AsyncAnthropic, then `await client....create(...)`\n"
               "# no async client available: resp = await asyncio.to_thread(requests.get, url, timeout=30)",
    },
    "AIO003": {
        "name": "blocking-subprocess", "severity": "high",
        "summary": "subprocess.run/call/check_output or os.system in async def",
        "why": "subprocess.run waits for the child process on the loop thread; nothing else runs until it exits.",
        "fix": "proc = await asyncio.create_subprocess_exec(\"ffmpeg\", \"-i\", src, dst,\n"
               "    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)\n"
               "out, err = await proc.communicate()\n"
               "# or: await asyncio.to_thread(subprocess.run, cmd, check=True)",
    },
    "AIO004": {
        "name": "blocking-file-io", "severity": "medium",
        "summary": "open() / Path.read_text() / shutil copy inside async def",
        "why": "Disk I/O is blocking (and slow on network filesystems / cold caches); large reads stall every "
               "task. Small config reads at startup are fine - suppress with # noqa: AIO004.",
        "fix": "text = await asyncio.to_thread(path.read_text, encoding=\"utf-8\")\n"
               "# many files / streaming: async with aiofiles.open(path) as f: data = await f.read()",
    },
    "AIO005": {
        "name": "blocking-db", "severity": "high",
        "summary": "sync DB / vector-store client (sqlite3, psycopg2, pymysql, redis.Redis, QdrantClient...) in async def",
        "why": "Every query blocks the loop for its full latency; under load p99 latency of unrelated requests explodes.",
        "fix": "# use the async driver: asyncpg / psycopg.AsyncConnection / aiosqlite / redis.asyncio /\n"
               "# AsyncQdrantClient, created once (FastAPI lifespan) and awaited:\n"
               "rows = await pool.fetch(\"SELECT id FROM docs WHERE tenant = $1\", tenant)\n"
               "# no async driver: rows = await asyncio.to_thread(run_query, sql, params)",
    },
    "AIO006": {
        "name": "blocking-socket-or-input", "severity": "high",
        "summary": "input(), blocking socket calls or DNS lookups in async def",
        "why": "input() and blocking socket recv/accept/connect park the loop thread until data arrives.",
        "fix": "reader, writer = await asyncio.open_connection(host, port)\n"
               "data = await reader.read(4096)\n"
               "# console input: line = await asyncio.to_thread(input, \"> \")",
    },
    "AIO007": {
        "name": "coroutine-not-awaited", "severity": "high",
        "summary": "coroutine function called as a statement without await",
        "why": "Calling an async def only creates a coroutine object; the body never runs and Python prints "
               "'RuntimeWarning: coroutine ... was never awaited' (often hidden in logs).",
        "fix": "await embed_batch(batch)\n"
               "# run it concurrently instead: task = asyncio.create_task(embed_batch(batch)) and await it later",
    },
    "AIO008": {
        "name": "dangling-task", "severity": "high",
        "summary": "create_task / ensure_future result discarded",
        "why": "The loop keeps only a weak reference to tasks: an unreferenced task can be garbage-collected "
               "mid-flight, and its exception is never retrieved (only 'Task exception was never retrieved' at exit).",
        "fix": "background: set[asyncio.Task] = set()\n"
               "task = asyncio.create_task(log_usage(event))\n"
               "background.add(task)\n"
               "task.add_done_callback(background.discard)\n"
               "# better (3.11+): create it inside `async with asyncio.TaskGroup() as tg:`",
    },
    "AIO009": {
        "name": "nested-asyncio-run", "severity": "high",
        "summary": "asyncio.run() inside async def",
        "why": "asyncio.run cannot be called while a loop is running in the thread: "
               "'RuntimeError: asyncio.run() cannot be called from a running event loop'.",
        "fix": "result = await main_coro()          # already inside a loop: just await it\n"
               "# Jupyter: top-level `await main_coro()` works in a cell (the kernel owns the loop)",
    },
    "AIO010": {
        "name": "get-event-loop", "severity": "medium",
        "summary": "asyncio.get_event_loop()",
        "why": "Outside a running loop it is deprecated (DeprecationWarning in several 3.10-3.13 releases) and "
               "raises RuntimeError in 3.14 when no loop is set; inside a coroutine get_running_loop() states the "
               "intent and never creates a stray loop.",
        "fix": "loop = asyncio.get_running_loop()   # inside async code\n"
               "asyncio.run(main())                 # at the entry point instead of get_event_loop().run_until_complete",
    },
    "AIO011": {
        "name": "run-until-complete-in-async", "severity": "high",
        "summary": "loop.run_until_complete() inside async def",
        "why": "The loop is already running: 'RuntimeError: This event loop is already running'.",
        "fix": "result = await coro()",
    },
    "AIO012": {
        "name": "unbounded-gather", "severity": "medium",
        "summary": "gather over a comprehension of calls with no concurrency limit",
        "why": "gather starts every coroutine at once: 10k prompts means 10k sockets, instant 429s from the "
               "provider, file-descriptor exhaustion and memory spikes. Fine when the input is known to be small.",
        "fix": "sem = asyncio.Semaphore(16)\n\n"
               "async def bounded(doc):\n"
               "    async with sem:\n"
               "        return await embed(doc)\n\n"
               "results = await asyncio.gather(*(bounded(d) for d in docs))",
    },
    "AIO013": {
        "name": "sequential-await-loop", "severity": "low",
        "summary": "await inside a for loop over independent items",
        "why": "Each iteration waits for the previous one, so N calls take N x latency. Only applies when the "
               "iterations are truly independent (no ordering requirement, no shared state, no rate-limit pacing).",
        "fix": "async with asyncio.TaskGroup() as tg:          # 3.11+\n"
               "    tasks = [tg.create_task(summarize(doc)) for doc in docs]\n"
               "summaries = [t.result() for t in tasks]\n"
               "# add a Semaphore when the list can be large",
    },
    "AIO014": {
        "name": "cancellation-swallowed", "severity": "high",
        "summary": "bare except / except BaseException / except CancelledError without re-raise in async def",
        "why": "CancelledError is a BaseException (3.8+). Swallowing it makes the task uncancellable: timeouts "
               "stop working, TaskGroup and shutdown hang, Ctrl+C does nothing.",
        "fix": "except asyncio.CancelledError:\n"
               "    await stream.aclose()   # cleanup only\n"
               "    raise",
    },
    "AIO015": {
        "name": "wait-for-on-311", "severity": "low",
        "summary": "asyncio.wait_for in 3.11+ code",
        "why": "asyncio.timeout() (3.11) scopes a deadline over a whole block, needs no extra task and composes "
               "with TaskGroup; wait_for wraps a single awaitable.",
        "fix": "async with asyncio.timeout(30):\n"
               "    resp = await client.chat.completions.create(**req)",
    },
    "AIO016": {
        "name": "thread-primitive-in-async", "severity": "medium",
        "summary": "threading.Lock / queue.Queue / threading.Event used inside async def",
        "why": "Thread primitives block the loop thread while waiting, and a threading.Lock held across an "
               "await deadlocks when another task on the same loop tries to take it.",
        "fix": "lock = asyncio.Lock()          # async with lock: ...\n"
               "queue = asyncio.Queue(maxsize=100)\n"
               "event = asyncio.Event()        # await event.wait()\n"
               "# talking to a worker thread: loop.call_soon_threadsafe / asyncio.run_coroutine_threadsafe",
    },
    "AIO017": {
        "name": "async-without-await", "severity": "low",
        "summary": "async def that never awaits",
        "why": "It runs synchronously on the loop anyway, so the async keyword adds overhead and misleads "
               "readers; if it does blocking work it should be sync and run via to_thread. Fine when it must "
               "match an async interface.",
        "fix": "def build_prompt(question: str, chunks: list[str]) -> str:   # make it a plain function\n"
               "    ...",
    },
    "AIO018": {
        "name": "sleep-zero-busy-wait", "severity": "medium",
        "summary": "polling loop whose only await is asyncio.sleep(0) / a tiny sleep",
        "why": "The loop spins at 100% CPU re-checking a flag and starves other tasks of fair scheduling.",
        "fix": "done = asyncio.Event()\n"
               "...\n"
               "await done.wait()        # the producer calls done.set()\n"
               "# or await queue.get() / await asyncio.wait_for(...) / async with asyncio.timeout(...)",
    },
    "AIO019": {
        "name": "client-without-async-with", "severity": "medium",
        "summary": "httpx.AsyncClient / aiohttp.ClientSession / aiofiles.open never closed",
        "why": "Unclosed clients leak connection pools and sockets ('Unclosed client session', ResourceWarning); "
               "creating one per request also throws away keep-alive and TLS reuse.",
        "fix": "async with httpx.AsyncClient(timeout=30) as http:\n"
               "    resp = await http.post(url, json=payload)\n"
               "# app-lifetime client: create in FastAPI lifespan, `await client.aclose()` after `yield`",
    },
    "AIO020": {
        "name": "task-never-awaited", "severity": "medium",
        "summary": "task assigned to a variable that is never awaited, gathered or stored",
        "why": "If the task fails, the exception is never retrieved; when the function returns the only "
               "reference disappears and the task may be garbage-collected or outlive its owner.",
        "fix": "task = asyncio.create_task(fetch_context(q))\n"
               "...\n"
               "context = await task      # or gather / TaskGroup / keep it in a set with a done callback",
    },
    "AIO021": {
        "name": "unbounded-queue", "severity": "low",
        "summary": "asyncio.Queue() without maxsize used as a pipeline buffer",
        "why": "With no maxsize a fast producer (file reader, scraper) never waits for slow consumers "
               "(embedding, GPU) and memory grows without limit: no backpressure.",
        "fix": "queue: asyncio.Queue[Doc] = asyncio.Queue(maxsize=2 * n_workers)\n"
               "await queue.put(doc)      # now blocks when consumers fall behind",
    },
    "AIO022": {
        "name": "return-exceptions-unchecked", "severity": "medium",
        "summary": "gather(..., return_exceptions=True) results never checked for exceptions",
        "why": "With return_exceptions=True failures come back as values in the result list; unless you check "
               "them they are silently written to the vector store / eval report as if they were results.",
        "fix": "results = await asyncio.gather(*coros, return_exceptions=True)\n"
               "ok = [r for r in results if not isinstance(r, BaseException)]\n"
               "failed = [(x, r) for x, r in zip(items, results) if isinstance(r, BaseException)]\n"
               "for item, err in failed:\n"
               "    logger.error(\"item %s failed\", item.id, exc_info=err)",
    },
    "AIO023": {
        "name": "sync-route-asyncio-run", "severity": "high",
        "summary": "sync def route (FastAPI/Starlette/Flask-style decorator) calls asyncio.run",
        "why": "Each request spins up and tears down a whole event loop in a threadpool thread, async clients "
               "created in lifespan cannot be used from it, and it breaks if the route is ever made async.",
        "fix": "@app.post(\"/summarize\")\n"
               "async def summarize(req: SummarizeRequest) -> SummarizeResponse:\n"
               "    text = await llm_summarize(req.text)\n"
               "    return SummarizeResponse(summary=text)",
    },
    "AIO024": {
        "name": "version-feature", "severity": "high",
        "summary": "asyncio API newer than --target-version",
        "why": "The code fails with AttributeError / SyntaxError on the Python version you said you support.",
        "fix": "# raise --target-version, or use the older equivalent:\n"
               "# TaskGroup -> gather (+ cancel siblings on error); asyncio.timeout -> asyncio.wait_for;\n"
               "# Runner -> asyncio.run; eager_task_factory -> plain create_task",
    },
}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
BLOCKING_RULES = {"AIO001", "AIO002", "AIO003", "AIO004", "AIO005", "AIO006", "AIO016"}

# ---------------------------------------------------------------- knowledge

HTTP_VERBS = {"get", "post", "put", "patch", "delete", "head", "options", "request", "stream"}
BLOCKING_CALLS = {
    "time.sleep": "AIO001",
    "urllib.request.urlopen": "AIO002", "urllib.request.urlretrieve": "AIO002",
    "urllib3.request": "AIO002",
    "subprocess.run": "AIO003", "subprocess.call": "AIO003", "subprocess.check_call": "AIO003",
    "subprocess.check_output": "AIO003", "subprocess.getoutput": "AIO003",
    "subprocess.getstatusoutput": "AIO003", "os.system": "AIO003", "os.popen": "AIO003",
    "os.waitpid": "AIO003",
    "shutil.copy": "AIO004", "shutil.copy2": "AIO004", "shutil.copyfile": "AIO004",
    "shutil.copytree": "AIO004", "shutil.rmtree": "AIO004", "shutil.move": "AIO004",
    "socket.gethostbyname": "AIO006", "socket.getaddrinfo": "AIO006", "socket.create_connection": "AIO006",
}
# constructors of synchronous clients -> rule used when they (or methods on them) appear in async def
SYNC_CLIENTS = {
    "requests.Session": "AIO002", "requests.session": "AIO002", "httpx.Client": "AIO002",
    "urllib3.PoolManager": "AIO002", "openai.OpenAI": "AIO002", "openai.AzureOpenAI": "AIO002",
    "anthropic.Anthropic": "AIO002", "cohere.Client": "AIO002", "cohere.ClientV2": "AIO002",
    "sqlite3.connect": "AIO005", "psycopg2.connect": "AIO005", "psycopg.connect": "AIO005",
    "pymysql.connect": "AIO005", "mysql.connector.connect": "AIO005", "pymongo.MongoClient": "AIO005",
    "redis.Redis": "AIO005", "redis.StrictRedis": "AIO005", "redis.from_url": "AIO005",
    "redis.Redis.from_url": "AIO005", "psycopg_pool.ConnectionPool": "AIO005",
    "qdrant_client.QdrantClient": "AIO005", "chromadb.Client": "AIO005",
    "chromadb.PersistentClient": "AIO005", "chromadb.HttpClient": "AIO005",
    "elasticsearch.Elasticsearch": "AIO005", "pinecone.Pinecone": "AIO005",
}
SOCKET_CTORS = {"socket.socket", "socket.socketpair", "socket.fromfd"}
SYNC_HTTP_METHODS = HTTP_VERBS | {"send", "create", "parse", "retrieve", "list", "update", "upload", "urlopen"}
NONBLOCKING_METHODS = {"setblocking", "settimeout", "setsockopt", "fileno", "getsockname", "getpeername",
                       "cursor", "with_options", "copy"}
SOCKET_BLOCKING = {"recv", "recv_into", "recvfrom", "accept", "sendall", "connect"}
PATH_IO = {"read_text", "write_text", "read_bytes", "write_bytes"}
THREAD_LOCKS = {"threading.Lock", "threading.RLock", "threading.Semaphore", "threading.BoundedSemaphore",
                "threading.Condition"}
THREAD_PRIMS = THREAD_LOCKS | {"threading.Event", "threading.Barrier", "queue.Queue", "queue.LifoQueue",
                               "queue.PriorityQueue", "queue.SimpleQueue", "multiprocessing.Queue"}
THREAD_BLOCKING_METHODS = {"acquire", "wait", "get", "join"}
ASYNC_QUEUES = {"asyncio.Queue", "asyncio.PriorityQueue", "asyncio.LifoQueue"}
ASYNC_PRIM_METHODS = {
    "asyncio.Queue": {"put", "get", "join"}, "asyncio.PriorityQueue": {"put", "get", "join"},
    "asyncio.LifoQueue": {"put", "get", "join"}, "asyncio.Event": {"wait"},
    "asyncio.Lock": {"acquire"}, "asyncio.Semaphore": {"acquire"}, "asyncio.BoundedSemaphore": {"acquire"},
    "asyncio.Condition": {"acquire", "wait", "wait_for"},
}
ASYNCIO_COROS = {"asyncio.sleep", "asyncio.wait_for", "asyncio.wait", "asyncio.gather", "asyncio.to_thread",
                 "asyncio.open_connection", "asyncio.start_server", "asyncio.open_unix_connection",
                 "asyncio.start_unix_server", "asyncio.create_subprocess_exec",
                 "asyncio.create_subprocess_shell"}
ALWAYS_ASYNC_ATTRS = {"aclose", "asend", "athrow", "__aenter__", "__aexit__", "__anext__"}
LOOP_APIS = {"create_task", "ensure_future", "get_running_loop", "current_task", "all_tasks", "call_soon",
             "call_later", "call_at", "run_in_executor", "create_future", "call_soon_threadsafe"}
ASYNC_RESOURCES = {"httpx.AsyncClient", "aiohttp.ClientSession", "aiofiles.open", "openai.AsyncOpenAI",
                   "openai.AsyncAzureOpenAI", "anthropic.AsyncAnthropic"}
ORDERED_METHODS = {"put", "put_nowait", "get", "send", "send_json", "send_text", "send_bytes", "write",
                   "drain", "commit", "rollback", "execute", "executemany", "flush", "sleep", "wait", "acquire",
                   "release", "join", "aclose", "close", "fetch", "fetchrow", "fetchval", "fetchone",
                   "fetchall", "ack", "nack", "publish", "emit", "readline", "read", "readexactly", "xadd"}
ROUTE_ATTRS = {"get", "post", "put", "patch", "delete", "head", "options", "api_route", "route", "websocket"}
INTERFACE_HINTS = ("callback", "handler", "hook", "mock", "fake", "stub", "noop", "dummy", "default_")
FANOUT_SAFE_HINTS = ("handler", "callback", "manager", "listener", "subscriber", "hook", "workers", "shards")
SEM_HINTS = ("sem", "limit", "throttle", "bucket", "rate", "pool", "slots")
VERSION_FEATURES = {
    "asyncio.TaskGroup": (3, 11), "asyncio.timeout": (3, 11), "asyncio.timeout_at": (3, 11),
    "asyncio.Timeout": (3, 11), "asyncio.Runner": (3, 11), "asyncio.Barrier": (3, 11),
    "asyncio.BrokenBarrierError": (3, 11),
    "asyncio.eager_task_factory": (3, 12), "asyncio.create_eager_task_factory": (3, 12),
    "asyncio.QueueShutDown": (3, 13), "asyncio.EventLoop": (3, 13),
}
EXIT_CALLS = {"sys.exit", "exit", "quit", "os._exit"}
TRY_TYPES = (ast.Try,) + ((ast.TryStar,) if hasattr(ast, "TryStar") else ())
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


# ---------------------------------------------------------------- helpers

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


def walk_local(stmts):
    """ast.walk over statements without descending into nested functions, classes or lambdas."""
    stack = list(stmts)
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, SCOPES):
            continue  # a nested def/class/lambda is its own scope
        for child in ast.iter_child_nodes(node):
            stack.append(child)


def parent(node):
    return getattr(node, "_aio_parent", None)


def reraises(stmts):
    for n in walk_local(stmts):
        if isinstance(n, ast.Raise):
            return True
        if isinstance(n, ast.Call) and dotted(n.func) in EXIT_CALLS:
            return True
    return False


CAPTURE_ATTRS = {"set_exception", "append", "add", "put_nowait", "throw", "cancel", "fail"}


def captures(stmts, name):
    """True if the caught exception is stored or handed on (err = e; fut.set_exception(e)) to be re-raised later."""
    if not name:
        return False
    for n in walk_local(stmts):
        if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)) and n.value is not None \
                and name in names_in(n.value):
            return True
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in CAPTURE_ATTRS \
                and any(name in names_in(a) for a in n.args):
            return True
    return False


def is_stub(body):
    for s in body:
        if isinstance(s, ast.Pass):
            continue
        if isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant):
            continue
        if isinstance(s, ast.Raise):
            continue
        return False
    return True


def names_in(node, ctx=ast.Load):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ctx)}


def small_literal_iter(it):
    if isinstance(it, (ast.List, ast.Tuple, ast.Set)):
        return True
    if isinstance(it, ast.Call) and dotted(it.func) == "range" and it.args:
        last = it.args[0] if len(it.args) == 1 else it.args[1]
        return isinstance(last, ast.Constant) and isinstance(last.value, int) and last.value <= 16
    if isinstance(it, ast.Subscript) and isinstance(it.slice, ast.Slice):
        up = it.slice.upper
        return isinstance(up, ast.Constant) and isinstance(up.value, int) and 0 <= up.value <= 16
    return False


def has_limit_hint(node):
    """True if the subtree shows a concurrency limit (Semaphore, limiter, acquire())."""
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            d = dotted(n.func)
            last = d.rsplit(".", 1)[-1]
            if last in ("Semaphore", "BoundedSemaphore", "CapacityLimiter", "Limiter", "AsyncLimiter") \
                    or last == "acquire":
                return True
            if last in ("Queue", "PriorityQueue", "LifoQueue") and (n.args or any(k.arg == "maxsize"
                                                                                  for k in n.keywords)):
                return True  # bounded queue: producers get backpressure
        if isinstance(n, ast.withitem):
            expr = n.context_expr
            d = dotted(expr.func if isinstance(expr, ast.Call) else expr).lower()
            if any(h in d for h in SEM_HINTS):
                return True
    return False


def fmt_version(v):
    return "%d.%d" % v


# ---------------------------------------------------------------- analyzer

class Analyzer:
    def __init__(self, path, source, tree, target):
        self.path = path
        self.lines = source.splitlines()
        self.tree = tree
        self.target = target
        self.findings = []
        self.seen = set()
        self.imports = {}
        self.module_funcs = {}       # name -> def node (module level)
        self.async_funcs, self.sync_funcs = set(), set()
        self.global_bindings, self.attr_bindings = {}, {}
        self.local_bindings, self.shadowed = {}, set()
        self.awaited_put = set()       # receivers of `await X.put(...)`: pipeline producers
        self.value_names = set()       # names loaded other than as the callee of a call
        self.nonblocking_sockets = False  # module calls setblocking(False) / settimeout(0)
        self.close_targets = set()   # dotted receivers of .aclose() / .close()

    # ------------------------------------------------------------ indexing
    def index(self):
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                child._aio_parent = node
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.asname:
                        self.imports[a.asname] = a.name
                    else:
                        head = a.name.split(".")[0]
                        self.imports[head] = head
            elif isinstance(node, ast.ImportFrom):
                mod = ("." * node.level) + (node.module or "")
                for a in node.names:
                    if a.name != "*":
                        self.imports[a.asname or a.name] = mod + "." + a.name
        for stmt in self._module_level_defs(self.tree.body):
            self.module_funcs[stmt.name] = stmt
            (self.async_funcs if isinstance(stmt, ast.AsyncFunctionDef) else self.sync_funcs).add(stmt.name)
        self.global_bindings = self.collect_bindings(walk_local(self.tree.body), plain=True)
        self.attr_bindings = self.collect_bindings(ast.walk(self.tree), plain=False)
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                p = parent(node)
                if not (isinstance(p, ast.Call) and p.func is node):
                    self.value_names.add(node.id)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "put" and isinstance(parent(node), ast.Await):
                    self.awaited_put.add(dotted(node.func.value))
                if node.func.attr in ("setblocking", "settimeout") and node.args \
                        and isinstance(node.args[0], ast.Constant) and node.args[0].value in (False, 0):
                    self.nonblocking_sockets = True
                if node.func.attr in ("aclose", "close"):
                    self.close_targets.add(dotted(node.func.value))

    def collect_bindings(self, nodes, plain):
        """Map variable keys to the constructor they were assigned from; ambiguous keys are dropped."""
        out, conflict = {}, set()

        def bind(key, ctor):
            if not key or ("." in key) == plain:
                return
            if key in out and out[key] != ctor:
                conflict.add(key)
            out[key] = ctor

        for node in nodes:
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
                ctor = self.resolve(node.value.func) if isinstance(node.value, ast.Call) else ""
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    bind(dotted(t), ctor or "?")
            elif isinstance(node, ast.withitem) and node.optional_vars is not None:
                expr = node.context_expr
                ctor = self.resolve(expr.func) if isinstance(expr, ast.Call) else ""
                bind(dotted(node.optional_vars), ctor or "?")
        return {k: v for k, v in out.items() if k not in conflict and v != "?"}

    def lookup(self, key):
        """Constructor a receiver was bound to, respecting function-local shadowing."""
        if "." in key:
            return self.attr_bindings.get(key)
        if key in self.local_bindings:
            return self.local_bindings[key]
        if key in self.shadowed:
            return None
        return self.global_bindings.get(key)

    def _module_level_defs(self, body):
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield stmt
            elif isinstance(stmt, (ast.If,) + TRY_TYPES):
                for field in ("body", "orelse", "finalbody"):
                    yield from self._module_level_defs(getattr(stmt, field, []) or [])

    def resolve(self, node):
        """Fully-qualified dotted name when the head of the chain is an imported name, else ''."""
        d = dotted(node)
        if not d:
            return ""
        head, _, rest = d.partition(".")
        if head not in self.imports:
            return ""
        base = self.imports[head]
        return base + ("." + rest if rest else "")

    def is_builtin(self, node, name):
        return isinstance(node, ast.Name) and node.id == name and name not in self.imports \
            and name not in self.module_funcs

    # ------------------------------------------------------------ reporting
    def add(self, rule, node, message, fix=None):
        line = getattr(node, "lineno", 1)
        if (rule, line) in self.seen:
            return
        self.seen.add((rule, line))
        src = self.lines[line - 1] if 0 < line <= len(self.lines) else ""
        m = re.search(r"#\s*noqa(?::\s*([A-Za-z0-9_, ]+))?", src)
        if m and (not m.group(1) or rule in [c.strip().upper() for c in m.group(1).split(",")]):
            return
        info = RULES[rule]
        self.findings.append({
            "path": self.path, "line": line, "col": getattr(node, "col_offset", 0) + 1,
            "rule": rule, "name": info["name"], "severity": info["severity"], "message": message,
            "code": src.strip(), "why": info["why"], "fix": fix or info["fix"],
        })

    # ------------------------------------------------------------ driver
    def run(self):
        self.index()
        self.scope(self.tree.body, None)
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.scope(node.body, node)
        self.check_versions()
        return self.findings

    def enclosing_class(self, func):
        p = parent(func) if func is not None else None
        return p if isinstance(p, ast.ClassDef) else None

    def class_method(self, cls, name):
        if cls is None:
            return None
        for s in cls.body:
            if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)) and s.name == name:
                return s
        return None

    def scope(self, body, func):
        is_async = isinstance(func, ast.AsyncFunctionDef)
        cls = self.enclosing_class(func)
        if func is None:
            self.local_bindings, self.shadowed = {}, set()
        else:
            self.local_bindings = self.collect_bindings(walk_local(func.body), plain=True)
            a = func.args
            self.shadowed = {x.arg for x in a.args + a.kwonlyargs + getattr(a, "posonlyargs", [])}
            self.shadowed |= {x.arg for x in (a.vararg, a.kwarg) if x is not None}
            self.shadowed |= {n.id for n in walk_local(func.body) if isinstance(n, ast.Name)
                              and isinstance(n.ctx, ast.Store)}
        for n in walk_local(body):
            if isinstance(n, ast.Call):
                self.check_call(n, func, is_async, cls)
            elif is_async and isinstance(n, TRY_TYPES):
                self.check_handlers(n, func)
            elif is_async and isinstance(n, ast.For):
                self.check_sequential_loop(n)
            elif is_async and isinstance(n, ast.While) and not func.name.startswith("test"):
                self.check_busy_wait(n)
            elif is_async and isinstance(n, ast.With):
                self.check_thread_lock_with(n)
        if func is None:
            return
        if is_async:
            self.check_no_await(func, cls)
        else:
            self.check_sync_route(func)
        self.check_unused_tasks(func)

    # ------------------------------------------------------------ calls
    def is_task_spawn(self, call):
        if not isinstance(call, ast.Call):
            return False
        name = self.resolve(call.func)
        if name in ("asyncio.create_task", "asyncio.ensure_future"):
            return True
        f = call.func
        if isinstance(f, ast.Attribute) and f.attr in ("create_task", "ensure_future"):
            recv = f.value
            if isinstance(recv, ast.Call) and self.resolve(recv.func) in (
                    "asyncio.get_running_loop", "asyncio.get_event_loop", "asyncio.new_event_loop"):
                return True
            if "loop" in dotted(recv).lower():
                return True
        return False

    def is_coroutine_call(self, call, cls):
        f = call.func
        name = self.resolve(f)
        if name in ASYNCIO_COROS:
            return name
        if isinstance(f, ast.Name) and f.id in self.async_funcs and f.id not in self.sync_funcs \
                and f.id not in self.imports:
            return f.id
        if isinstance(f, ast.Attribute):
            recv = dotted(f.value)
            if recv in ("self", "cls"):
                m = self.class_method(cls, f.attr)
                if isinstance(m, ast.AsyncFunctionDef):
                    return recv + "." + f.attr
            if f.attr in ALWAYS_ASYNC_ATTRS:
                return (recv or "<obj>") + "." + f.attr
            ctor = self.lookup(recv)
            if ctor in ASYNC_PRIM_METHODS and f.attr in ASYNC_PRIM_METHODS[ctor]:
                return recv + "." + f.attr
            if f.attr in ("drain", "wait_closed") and "writer" in recv.lower():
                return recv + "." + f.attr
        return ""

    def queue_key(self, call):
        p = parent(call)
        if isinstance(p, ast.Assign):
            return dotted(p.targets[0])
        if isinstance(p, ast.AnnAssign):
            return dotted(p.target)
        return ""

    def check_call(self, call, func, is_async, cls):
        f = call.func
        name = self.resolve(f)
        attr = f.attr if isinstance(f, ast.Attribute) else None
        par = parent(call)
        awaited = isinstance(par, ast.Await)
        statement = isinstance(par, ast.Expr)

        if statement:
            coro = self.is_coroutine_call(call, cls)
            if coro:
                self.add("AIO007", call, f"`{coro}(...)` is a coroutine but is never awaited; its body never runs",
                         f"await {ast.unparse(call)}")
            elif self.is_task_spawn(call):
                self.add("AIO008", call, f"result of `{dotted(f) or 'create_task'}(...)` is discarded: the task can "
                         "be garbage-collected mid-flight and its exception is never retrieved")
        if name == "asyncio.get_event_loop":
            where = "inside a coroutine use asyncio.get_running_loop()" if is_async else \
                "at the entry point use asyncio.run(main()) / asyncio.Runner"
            self.add("AIO010", call, f"asyncio.get_event_loop() is deprecated outside a running loop "
                     f"(RuntimeError in 3.14 when no loop is set); {where}")
        if name == "asyncio.wait_for" and self.target >= (3, 11):
            self.add("AIO015", call, "asyncio.wait_for in code targeting %s: prefer `async with asyncio.timeout(...)`"
                     % fmt_version(self.target))
        if name in ASYNC_QUEUES and self.queue_key(call) in self.awaited_put:
            maxsize = call.args[0] if call.args else next((k.value for k in call.keywords if k.arg == "maxsize"), None)
            if maxsize is None or (isinstance(maxsize, ast.Constant) and maxsize.value in (0, None)):
                self.add("AIO021", call, f"`{name}()` has no maxsize: producers never block, so there is no "
                         "backpressure and memory can grow without limit")
        if name == "asyncio.gather":
            self.check_gather(call, func, cls)
            if any(k.arg == "return_exceptions" and isinstance(k.value, ast.Constant) and k.value.value is True
                   for k in call.keywords):
                self.check_return_exceptions(call, func)
        if func is not None and name in ASYNC_RESOURCES:
            self.check_resource(call, func, cls, name)
        if not is_async:
            return

        # ---- inside async def only
        if name == "asyncio.run":
            self.add("AIO009", call, "asyncio.run() inside async def raises 'cannot be called from a running "
                     "event loop'", f"result = await {ast.unparse(call.args[0]) if call.args else 'coro()'}")
        if attr == "run_until_complete":
            self.add("AIO011", call, "run_until_complete() inside async def: the loop is already running",
                     f"result = await {ast.unparse(call.args[0]) if call.args else 'coro()'}")
        if awaited:
            return
        rule = BLOCKING_CALLS.get(name)
        if not rule and name:
            head, _, last = name.rpartition(".")
            if head in ("requests", "httpx") and last in HTTP_VERBS:
                rule = "AIO002"
            elif name in SYNC_CLIENTS:
                rule = SYNC_CLIENTS[name]
            elif name in THREAD_LOCKS:
                self.add("AIO016", call, f"`{name}()` created inside async def: thread primitives block the "
                         "event loop; use the asyncio equivalent")
                return
        if rule:
            label = dotted(f) or name
            self.add(rule, call, f"`{label}(...)` blocks the event loop inside `async def`")
            return
        if self.is_builtin(f, "open"):
            self.add("AIO004", call, "builtin open() inside async def does blocking disk I/O on the event loop")
            return
        if self.is_builtin(f, "input"):
            self.add("AIO006", call, "input() inside async def blocks the event loop until the user types")
            return
        if attr in PATH_IO and not (isinstance(f.value, ast.Name) and f.value.id in self.imports):
            self.add("AIO004", call, f"`.{attr}()` inside async def does blocking disk I/O on the event loop")
            return
        if attr:
            recv = dotted(f.value)
            parts = dotted(f).split(".")
            for i in range(len(parts) - 1, 0, -1):
                key = ".".join(parts[:i])
                ctor = self.lookup(key)
                if ctor in SYNC_CLIENTS and attr not in NONBLOCKING_METHODS and (
                        SYNC_CLIENTS[ctor] != "AIO002" or attr in SYNC_HTTP_METHODS):
                    self.add(SYNC_CLIENTS[ctor], call, f"`{dotted(f)}(...)` uses the synchronous `{ctor}` client "
                             "inside async def; it blocks the event loop")
                    return
                if ctor in THREAD_PRIMS and i == len(parts) - 1 and attr in THREAD_BLOCKING_METHODS:
                    self.add("AIO016", call, f"`{dotted(f)}()` on a `{ctor}` blocks the event loop thread")
                    return
            sockish = self.lookup(recv) in SOCKET_CTORS or "sock" in recv.lower().rsplit(".", 1)[-1]
            if attr in SOCKET_BLOCKING and sockish and not self.nonblocking_sockets:
                self.add("AIO006", call, f"`{dotted(f)}()` is a blocking socket call inside async def")

    # ------------------------------------------------------------ gather
    def find_assignment(self, func, name):
        if func is None:
            return None
        found = None
        for n in walk_local(func.body):
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) \
                    and n.targets[0].id == name:
                found = n.value
        return found

    def callee_def(self, call, func, cls):
        if not isinstance(call, ast.Call):
            return None
        f = call.func
        if isinstance(f, ast.Name):
            if func is not None:
                for n in ast.walk(func):
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == f.id and n is not func:
                        return n
            return self.module_funcs.get(f.id)
        if isinstance(f, ast.Attribute) and dotted(f.value) in ("self", "cls"):
            return self.class_method(cls, f.attr)
        return None

    def classes_defining(self, method):
        return [c for c in ast.walk(self.tree) if isinstance(c, ast.ClassDef)
                and any(isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name == method
                        for m in c.body)]

    def check_gather(self, call, func, cls):
        for arg in call.args:
            if not isinstance(arg, ast.Starred):
                continue
            v = arg.value
            if isinstance(v, ast.Name):
                v = self.find_assignment(func, v.id)
            elt, it = None, None
            if isinstance(v, (ast.ListComp, ast.GeneratorExp)):
                elt, it = v.elt, v.generators[0].iter
            elif isinstance(v, ast.Call) and dotted(v.func) == "map" and len(v.args) >= 2:
                elt, it = ast.Call(func=v.args[0], args=[], keywords=[]), v.args[1]
            if elt is None or not isinstance(elt, ast.Call) or small_literal_iter(it):
                continue
            if any(h in ast.unparse(it).lower() for h in FANOUT_SAFE_HINTS):
                continue  # callback handlers / run managers / listeners: small by construction
            if self.is_task_spawn(elt) and elt.args:
                elt = elt.args[0]
            if not isinstance(elt, ast.Call):
                continue
            if self.resolve(elt.func) == "asyncio.to_thread" or (
                    isinstance(elt.func, ast.Attribute) and elt.func.attr == "run_in_executor"):
                continue  # the executor's worker count bounds concurrency
            if func is not None and isinstance(it, ast.Name) and func.args.vararg is not None \
                    and func.args.vararg.arg == it.id:
                continue  # generic helper over *aws: the caller decides the fan-out
            if func is not None and has_limit_hint(func):
                continue
            callee = self.callee_def(elt, func, cls)
            if callee is not None and has_limit_hint(callee):
                continue
            if isinstance(elt.func, ast.Attribute) and any(
                    has_limit_hint(c) for c in self.classes_defining(elt.func.attr)):
                continue  # obj.method(...) where the class owns a Semaphore / bounded queue
            target = "TaskGroup + Semaphore" if self.target >= (3, 11) else "Semaphore"
            self.add("AIO012", call, f"gather fans out one coroutine per item of `{ast.unparse(it)}` with no "
                     f"concurrency limit (heuristic: fine if the input is small; otherwise bound it with a {target})")

    def check_return_exceptions(self, call, func):
        p = parent(call)
        holder = parent(p) if isinstance(p, ast.Await) else p
        if isinstance(holder, ast.Expr):
            fresh = any(isinstance(a, ast.Call) or (isinstance(a, ast.Starred)
                        and isinstance(a.value, (ast.ListComp, ast.GeneratorExp))
                        and not self.is_task_spawn(a.value.elt)) for a in call.args)
            if not fresh:
                return  # `await gather(*tasks, return_exceptions=True)` after cancel(): cleanup idiom
            self.add("AIO022", call, "gather(..., return_exceptions=True) result is discarded, so every failure "
                     "is silently dropped")
            return
        if func is None or not isinstance(holder, (ast.Assign, ast.AnnAssign)):
            return
        targets = holder.targets if isinstance(holder, ast.Assign) else [holder.target]
        names = set()
        for t in targets:
            names |= names_in(t, ast.Store)
        for n in ast.walk(func):
            if isinstance(n, ast.Call) and dotted(n.func) == "isinstance" and len(n.args) == 2:
                if any(("Exception" in x or "Error" in x) for x in names_in(n.args[1]) | {dotted(n.args[1])}):
                    return
                if any(isinstance(x, ast.Attribute) and ("Exception" in x.attr or "Error" in x.attr)
                       for x in ast.walk(n.args[1])):
                    return
            if isinstance(n, (ast.Return, ast.Yield)) and isinstance(n.value, ast.Name) and n.value.id in names:
                return  # raw results handed to the caller, who checks them
            if isinstance(n, ast.Call) and n is not call and dotted(n.func) not in (
                    "len", "print", "zip", "enumerate", "list", "dict", "sum", "sorted", "range", "iter"):
                if any(isinstance(a, ast.Name) and a.id in names for a in n.args):
                    return
        self.add("AIO022", call, "gather(..., return_exceptions=True) results are used without checking "
                 "`isinstance(r, BaseException)`; failures will be treated as results")

    # ------------------------------------------------------------ resources
    def check_resource(self, call, func, cls, name):
        node = call
        p = parent(call)
        while isinstance(p, (ast.Await, ast.IfExp, ast.BoolOp)):
            node, p = p, parent(p)
        if isinstance(p, ast.Attribute):          # AsyncOpenAI(...).embeddings stored, or inline .get(...)
            top = p
            while isinstance(parent(top), ast.Attribute):
                top = parent(top)
            holder = parent(top)
            if isinstance(holder, (ast.Assign, ast.AnnAssign)) and not isinstance(
                    (holder.targets[0] if isinstance(holder, ast.Assign) else holder.target), ast.Name):
                return
            self.add("AIO019", call, f"`{name}(...)` created inline and never closed: a new connection pool per "
                     "call that leaks sockets")
            return
        if isinstance(p, (ast.withitem, ast.Return, ast.Yield, ast.YieldFrom, ast.Call, ast.keyword,
                          ast.Dict, ast.List, ast.Tuple, ast.Subscript)):
            return  # async with / factory / handed to an owner (AsyncExitStack, Depends, container)
        if isinstance(p, (ast.Assign, ast.AnnAssign)):
            targets = p.targets if isinstance(p, ast.Assign) else [p.target]
            t = targets[0]
            if isinstance(t, ast.Attribute):
                key = dotted(t)
                if key in self.close_targets or not key.startswith(("self.", "cls.")):
                    return  # closed somewhere, or stored on app.state / another owner
                if cls is not None and any(self.class_method(cls, m) for m in ("aclose", "close", "__aexit__")):
                    return
                if name not in ("httpx.AsyncClient", "aiohttp.ClientSession", "aiofiles.open"):
                    return  # SDK clients held by a long-lived object close themselves at exit
                self.add("AIO019", call, f"`{key} = {name}(...)` is never closed (no `{key}.aclose()` / "
                         "`close()` anywhere in the module and the class has no aclose/__aexit__)")
                return
            if isinstance(t, ast.Name):
                if self.local_escapes_or_closed(func, t.id):
                    return
                self.add("AIO019", call, f"`{t.id} = {name}(...)` is never closed; use `async with` so the "
                         "connection pool is released on every exit path")
                return
            return
        self.add("AIO019", call, f"`{name}(...)` used without `async with`: it is created per call and never closed")

    def local_escapes_or_closed(self, func, var):
        for n in ast.walk(func):
            if isinstance(n, ast.Call):
                if isinstance(n.func, ast.Attribute) and n.func.attr in ("aclose", "close") \
                        and dotted(n.func.value) == var:
                    return True
                if any(isinstance(a, ast.Name) and a.id == var for a in n.args) or \
                        any(isinstance(k.value, ast.Name) and k.value.id == var for k in n.keywords):
                    return True
            elif isinstance(n, ast.withitem) and dotted(n.context_expr) == var:
                return True
            elif isinstance(n, (ast.Return, ast.Yield)) and n.value is not None and var in names_in(n.value):
                return True
            elif isinstance(n, ast.Assign) and isinstance(n.value, ast.Name) and n.value.id == var \
                    and not all(isinstance(t, ast.Name) for t in n.targets):
                return True
        return False

    # ------------------------------------------------------------ statements
    def awaits_cancelled_task(self, node, func):
        """`t.cancel(); try: await t; except CancelledError: pass` - reaping a task we cancelled ourselves."""
        awaited = set()
        for n in walk_local(node.body):
            if isinstance(n, ast.Await):
                v = n.value
                if isinstance(v, ast.Call) and self.resolve(v.func) in ("asyncio.wait_for", "asyncio.gather",
                                                                         "asyncio.shield") and v.args:
                    v = v.args[0]
                if dotted(v):
                    awaited.add(dotted(v))
        if not awaited or func is None:
            return False
        for n in walk_local(func.body):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "cancel" \
                    and dotted(n.func.value) in awaited:
                return True
        return False

    def check_handlers(self, node, func):
        for h in node.handlers:
            if h.type is None:
                kind = "bare `except:`"
            else:
                elts = h.type.elts if isinstance(h.type, ast.Tuple) else [h.type]
                names = {dotted(e).rsplit(".", 1)[-1] for e in elts}
                hit = sorted(names & {"BaseException", "CancelledError"})
                if not hit:
                    continue
                kind = f"`except {hit[0]}`"
            if kind != "bare `except:`" and self.awaits_cancelled_task(node, func):
                continue
            if not reraises(h.body) and not captures(h.body, h.name):
                self.add("AIO014", h, f"{kind} in async def does not re-raise: CancelledError is swallowed, so "
                         "timeouts, TaskGroup cancellation and shutdown stop working")

    def check_sequential_loop(self, loop):
        targets = names_in(loop.target, ast.Store)
        if not targets or small_literal_iter(loop.iter):
            return
        body = list(walk_local(loop.body))
        if any(isinstance(n, (ast.Break, ast.Return, ast.Yield, ast.YieldFrom)) for n in body):
            return
        awaits = [n for n in body if isinstance(n, ast.Await)]
        for a in awaits:
            v = a.value
            if isinstance(v, ast.Call) and self.resolve(v.func) == "asyncio.sleep":
                return  # deliberate pacing (rate limit)
        stored = set()
        for n in body:
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                stored.add(n.id)
        for n in body:
            if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                    if isinstance(t, (ast.Attribute, ast.Subscript)):
                        stored |= names_in(t.value) - targets  # obj.x = ... / d[k] = ...: shared state
        for a in awaits:
            call = a.value
            if not isinstance(call, ast.Call):
                continue
            f = call.func
            if isinstance(f, ast.Attribute) and f.attr in ORDERED_METHODS:
                continue
            holder = parent(a)
            collects = isinstance(holder, (ast.Assign, ast.AnnAssign, ast.AugAssign)) or (
                isinstance(holder, ast.Call) and isinstance(holder.func, ast.Attribute)
                and holder.func.attr in ("append", "extend", "add"))
            if not collects:
                continue
            used = set()
            for x in list(call.args) + [k.value for k in call.keywords]:
                used |= names_in(x)
            if not used & targets:
                continue
            receiver = names_in(f.value) if isinstance(f, ast.Attribute) else set()
            deps = (used | receiver) & (stored - targets)
            if isinstance(holder, (ast.Assign, ast.AnnAssign)):
                tnames = set()
                for t in (holder.targets if isinstance(holder, ast.Assign) else [holder.target]):
                    tnames |= names_in(t, ast.Store)
                deps |= (used | receiver) & tnames
            if deps:
                continue  # loop-carried dependency (e.g. history = await llm(history, x))
            hint = "TaskGroup" if self.target >= (3, 11) else "asyncio.gather"
            self.add("AIO013", a, f"`await {ast.unparse(call)}` runs one item at a time in this for loop; if the "
                     f"items are independent, run them concurrently with {hint} (+ Semaphore). Ignore if order, "
                     "shared state or rate-limit pacing requires sequential calls")
            return

    def check_busy_wait(self, loop):
        awaits = [n for n in walk_local(loop.body) if isinstance(n, ast.Await)]
        sleeps = []
        for a in awaits:
            v = a.value
            if isinstance(v, ast.Call) and self.resolve(v.func) == "asyncio.sleep":
                d = v.args[0] if v.args else next((k.value for k in v.keywords if k.arg == "delay"), None)
                if isinstance(d, ast.Constant) and isinstance(d.value, (int, float)) and d.value <= 0.01:
                    sleeps.append(a)
                    continue
            return  # another await: the loop does real async work
        if sleeps:
            self.add("AIO018", sleeps[0], f"`{ast.unparse(sleeps[0])}` is the only await in this while loop: it "
                     "busy-waits at 100% CPU; wait on an asyncio.Event / Queue / Condition instead")

    def check_thread_lock_with(self, node):
        for item in node.items:
            key = dotted(item.context_expr)
            ctor = self.lookup(key)
            if ctor in THREAD_LOCKS and any(isinstance(n, ast.Await) for n in walk_local(node.body)):
                self.add("AIO016", node, f"`with {key}:` holds a `{ctor}` across an await; another task on the "
                         "same loop that takes it blocks the loop thread forever (deadlock)")

    def check_no_await(self, func, cls):
        if func.decorator_list or func.name.startswith("__") or func.name.startswith("test") or cls is not None \
                or not isinstance(parent(func), ast.Module) or is_stub(func.body):
            return  # decorated (routes, fixtures), methods, nested callbacks, tests and stubs are exempt
        lname = func.name.lower()
        if any(h in lname for h in INTERFACE_HINTS):
            return
        a = func.args
        if any(x.arg.startswith("_") for x in a.args + a.kwonlyargs + getattr(a, "posonlyargs", [])):
            return  # unused `_params` signal a callback signature imposed by a framework
        if func.name in self.value_names:
            return  # passed around as a callable (stage function, callback): must stay async
        end = getattr(func, "end_lineno", func.lineno)
        if any(f["rule"] in BLOCKING_RULES and func.lineno <= f["line"] <= end and f["path"] == self.path
               for f in self.findings):
            return  # the blocking-call finding already says what to fix
        for n in walk_local(func.body):
            if isinstance(n, (ast.Await, ast.AsyncFor, ast.AsyncWith, ast.Yield, ast.YieldFrom)):
                return
            if isinstance(n, ast.comprehension) and n.is_async:
                return
            if isinstance(n, ast.Call):
                d = dotted(n.func)
                if d.rsplit(".", 1)[-1] in LOOP_APIS:
                    return
        self.add("AIO017", func, f"`async def {func.name}` never awaits; make it a plain def (run blocking work "
                 "with asyncio.to_thread) unless it must satisfy an async interface")

    def check_sync_route(self, func):
        is_route = False
        for d in func.decorator_list:
            if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr in ROUTE_ATTRS:
                is_route = True
        if not is_route:
            return
        for n in walk_local(func.body):
            if isinstance(n, ast.Call) and (self.resolve(n.func) == "asyncio.run"
                                            or (isinstance(n.func, ast.Attribute)
                                                and n.func.attr == "run_until_complete")):
                self.add("AIO023", n, f"sync route `{func.name}` starts a new event loop per request; declare it "
                         "`async def` and await the coroutine")

    def check_unused_tasks(self, func):
        for n in walk_local(func.body):
            if not (isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)):
                continue
            v = n.value
            spawn = self.is_task_spawn(v) or (isinstance(v, ast.ListComp) and self.is_task_spawn(v.elt))
            if not spawn:
                continue
            var = n.targets[0].id
            loads = sum(1 for x in ast.walk(func) if isinstance(x, ast.Name) and x.id == var
                        and isinstance(x.ctx, ast.Load))
            if not loads:
                self.add("AIO020", n, f"task(s) stored in `{var}` are never awaited, gathered, cancelled or kept: "
                         "exceptions are lost and the task can outlive (or be collected before) its owner")

    # ------------------------------------------------------------ versions
    def check_versions(self):
        t = self.target
        for n in ast.walk(self.tree):
            if isinstance(n, (ast.Attribute, ast.Name)) and not isinstance(parent(n), ast.Attribute):
                name = self.resolve(n)
                need = VERSION_FEATURES.get(name)
                if need and t < need:
                    self.add("AIO024", n, f"`{name}` needs Python {fmt_version(need)}+ but --target-version is "
                             f"{fmt_version(t)}")
            elif hasattr(ast, "TryStar") and isinstance(n, ast.TryStar) and t < (3, 11):
                self.add("AIO024", n, f"`except*` needs Python 3.11+ but --target-version is {fmt_version(t)}")
            elif isinstance(n, ast.AsyncFor) and isinstance(n.iter, ast.Call) \
                    and self.resolve(n.iter.func) == "asyncio.as_completed" and t < (3, 13):
                self.add("AIO024", n, "`async for` over asyncio.as_completed needs Python 3.13+ but "
                         f"--target-version is {fmt_version(t)}")
            elif isinstance(n, ast.Call) and self.resolve(n.func) == "asyncio.run" and t < (3, 12) \
                    and any(k.arg == "loop_factory" for k in n.keywords):
                self.add("AIO024", n, f"asyncio.run(loop_factory=...) needs Python 3.12+ but --target-version is "
                         f"{fmt_version(t)}")


# ---------------------------------------------------------------- CLI

def lint_source(source, path, target):
    tree = ast.parse(source, filename=path)
    return Analyzer(path, source, tree, target).run()


def collect(paths):
    """Yield (path, explicit) pairs; explicit=False for files found by walking a directory."""
    skip = {".git", ".venv", "venv", "__pycache__", "node_modules", ".tox", ".mypy_cache", "build", "dist"}
    for p in paths:
        if p != "-" and os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d not in skip)
                for f in sorted(files):
                    if f.endswith(".py"):
                        yield os.path.join(root, f), False
        else:
            yield p, True


def parse_rule_list(values):
    out = set()
    for v in values or []:
        for tok in v.split(","):
            tok = tok.strip()
            if not tok:
                continue
            matched = [rid for rid, info in RULES.items() if rid.startswith(tok.upper()) or info["name"] == tok]
            if not matched:
                raise ValueError(f"unknown rule {tok!r}; run --list-rules")
            out.update(matched)
    return out


def parse_version(text):
    m = re.match(r"^3\.(\d+)$", text.strip())
    if not m or not 9 <= int(m.group(1)) <= 15:
        raise ValueError(f"--target-version must look like 3.9 ... 3.15, got {text!r}")
    return (3, int(m.group(1)))


def print_rules():
    for rid, info in RULES.items():
        print(f"{rid} [{info['severity']}] {info['name']}: {info['summary']}")
        print(f"    why: {info['why']}")
        print("    fix: " + info["fix"].replace("\n", "\n         "))
        print()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="Python files or directories, or - for stdin")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any finding is reported")
    ap.add_argument("--select", action="append", metavar="IDS",
                    help="only these rules (ids, id prefixes or names; comma list)")
    ap.add_argument("--ignore", action="append", metavar="IDS",
                    help="skip these rules (ids, id prefixes or names; comma list)")
    ap.add_argument("--min-severity", choices=["low", "medium", "high"], default="low",
                    help="hide findings below this severity (default: low)")
    ap.add_argument("--target-version", default="3.11", metavar="3.N",
                    help="lowest Python version the code must run on (default 3.11); drives AIO015 and AIO024")
    ap.add_argument("--list-rules", action="store_true", help="print every rule with why and fix, then exit")
    args = ap.parse_args(argv)

    if args.list_rules:
        print_rules()
        return 0
    if not args.paths:
        ap.print_usage(sys.stderr)
        print("error: give at least one file, directory or - for stdin", file=sys.stderr)
        return 2
    try:
        select = parse_rule_list(args.select) or set(RULES)
        select -= parse_rule_list(args.ignore)
        target = parse_version(args.target_version)
    except ValueError as err:
        ap.print_usage(sys.stderr)
        print(f"error: {err}", file=sys.stderr)
        return 2

    findings, errors, warnings, files = [], [], [], 0
    for path, explicit in collect(args.paths):
        label = "<stdin>" if path == "-" else path
        try:
            if path == "-":
                source = sys.stdin.read()
            else:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
            findings.extend(lint_source(source, label, target))
            files += 1
        except SyntaxError as err:
            msg = f"{label}:{err.lineno}: cannot parse: {err.msg}"
            (errors if explicit else warnings).append(msg)
        except (OSError, UnicodeDecodeError, ValueError) as err:
            msg = f"{label}: cannot read: {err}"
            (errors if explicit else warnings).append(msg)

    floor = SEVERITY_ORDER[args.min_severity]
    findings = [f for f in findings if f["rule"] in select and SEVERITY_ORDER[f["severity"]] <= floor]
    findings.sort(key=lambda f: (f["path"], f["line"], f["col"], f["rule"]))
    counts = {s: sum(f["severity"] == s for f in findings) for s in SEVERITY_ORDER}

    if args.json:
        print(json.dumps({"files": files, "target_version": fmt_version(target), "summary": counts,
                          "errors": errors, "warnings": warnings, "findings": findings}, indent=2))
    else:
        for w in warnings:
            print(f"warning: skipped {w}", file=sys.stderr)
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        for f in findings:
            print(f"{f['path']}:{f['line']}:{f['col']}: {f['rule']} [{f['severity']}] {f['name']}: {f['message']}")
            if f["code"]:
                print(f"    > {f['code']}")
            print("    fix: " + f["fix"].replace("\n", "\n         "))
            print()
        if findings:
            print(f"{len(findings)} finding(s) in {files} file(s): {counts['high']} high, "
                  f"{counts['medium']} medium, {counts['low']} low (target Python {fmt_version(target)})")
        elif not errors:
            print(f"No asyncio issues found in {files} file(s) (target Python {fmt_version(target)}).")
    if errors:
        return 2
    return 1 if args.strict and findings else 0


if __name__ == "__main__":
    sys.exit(main())
