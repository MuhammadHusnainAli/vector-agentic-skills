# Python skill script cases. Syntax: see tests/run_tests.sh.

t 'review_idioms: ai pipeline risks' 1 'PY037 [high] time.sleep() in async def' \
  "$PY/python-idiomatic-code-reviewer/scripts/review_idioms.py" "$FX/python/idiom_ai_pipeline.py" --strict
t 'review_idioms: general idioms' 1 'PY001 [high] mutable default `[]` in add_doc()' \
  "$PY/python-idiomatic-code-reviewer/scripts/review_idioms.py" "$FX/python/idiom_general.py" --strict
t 'review_idioms: clean file' 0 'No findings in 1 file(s)' \
  "$PY/python-idiomatic-code-reviewer/scripts/review_idioms.py" "$FX/python/idiom_clean.py" --strict
STDIN=$'OPENAI_API_KEY = "sk-proj-abc123def456ghi789jkl012mno345"\n' t 'review_idioms: stdin secret' 1 'PY036 [high]' \
  "$PY/python-idiomatic-code-reviewer/scripts/review_idioms.py" - --strict --select PY036
t 'find_comprehension_candidates: walrus loop rewrite' 1 'answers = [parsed for raw in raw_outputs if (parsed := parse(raw)) is not None]' \
  "$PY/python-comprehension-refactorer/scripts/find_comprehension_candidates.py" "$FX/python/compr_rag_pipeline.py" --strict
t 'find_comprehension_candidates: counter loop' 1 'counts = Counter(tokens)' \
  "$PY/python-comprehension-refactorer/scripts/find_comprehension_candidates.py" "$FX/python/compr_rag_pipeline.py" --strict
t 'find_comprehension_candidates: clean file' 0 'no comprehension refactors suggested' \
  "$PY/python-comprehension-refactorer/scripts/find_comprehension_candidates.py" "$FX/python/compr_clean.py" --strict
STDIN=$'xs = [1]\n[print(x) for x in xs]\n' t 'find_comprehension_candidates: side-effect comprehension on stdin' 1 side-effect-comprehension \
  "$PY/python-comprehension-refactorer/scripts/find_comprehension_candidates.py" - --strict
t 'annotation_audit: legacy typing rewrites' 1 'fix: list[dict[str, Any]] | None' \
  "$PY/python-type-hints-annotator/scripts/annotation_audit.py" "$FX/python/hints_legacy_typing.py" --strict
t 'annotation_audit: coverage gate fails' 1 'Coverage gate: FAIL (overall 0.0%, minimum 50.0%)' \
  "$PY/python-type-hints-annotator/scripts/annotation_audit.py" "$FX/python/hints_untyped_llm_client.py" --min-coverage 50
t 'annotation_audit: infers return types' 1 'return         -> Iterator[str]' \
  "$PY/python-type-hints-annotator/scripts/annotation_audit.py" "$FX/python/hints_untyped_llm_client.py" --strict
t 'annotation_audit: clean 3.12 module' 0 'Coverage gate: PASS' \
  "$PY/python-type-hints-annotator/scripts/annotation_audit.py" "$FX/python/hints_typed_clean.py" --target-version 3.12 --strict --min-coverage 100
STDIN=$'def f(stop: list[str] = None) -> None:\n    pass\n' t 'annotation_audit: stdin implicit optional' 1 'fix: stop: list[str] | None = None' \
  "$PY/python-type-hints-annotator/scripts/annotation_audit.py" - --strict
t 'to_dataclass: class mode converts boilerplate' 1 'stop: list = field(default_factory=list, hash=False)' \
  "$PY/python-dataclass-converter/scripts/to_dataclass.py" class "$FX/python/dc_legacy_models.py" --strict
t 'to_dataclass: json mode nested + aliases' 0 'x_request_id: str = field(metadata={"json_key": "x-request-id"})' \
  "$PY/python-dataclass-converter/scripts/to_dataclass.py" json "$FX/python/dc_llm_response.json" --name ChatCompletion
t 'to_dataclass: pydantic style' 0 'latency_ms: float = Field(alias="latencyMs")' \
  "$PY/python-dataclass-converter/scripts/to_dataclass.py" json "$FX/python/dc_llm_response.json" --style pydantic
STDIN=$'class A:\n    def __init__(self, x, tags=[]):\n        self.x = x\n        self.tags = tags\n' t 'to_dataclass: stdin mutable default' 1 DC001 \
  "$PY/python-dataclass-converter/scripts/to_dataclass.py" class - --strict
STDIN='{bad' t 'to_dataclass: bad json exits 2' 2 'cannot parse' \
  "$PY/python-dataclass-converter/scripts/to_dataclass.py" json -
t 'audit_exceptions: smells in llm client' 1 'EXC008 [high] cancellation-swallowed' \
  "$PY/python-exception-handling-designer/scripts/audit_exceptions.py" "$FX/python/exc_bad_handlers.py" --strict
t 'audit_exceptions: clean handlers' 0 'No exception-handling issues found' \
  "$PY/python-exception-handling-designer/scripts/audit_exceptions.py" "$FX/python/exc_good_handlers.py" --strict
STDIN=$'try:\n    x()\nexcept Exception:\n    pass\n' t 'audit_exceptions: stdin swallow' 1 broad-except-swallow \
  "$PY/python-exception-handling-designer/scripts/audit_exceptions.py" - --strict
t 'scaffold_exceptions: json spec' 0 'class RateLimitError(ProviderError):' \
  "$PY/python-exception-handling-designer/scripts/scaffold_exceptions.py" --spec "$FX/python/exc_errors_spec.json"
STDIN='{"package": "kit", "errors": ["ChildError(MissingParent)"]}' t 'scaffold_exceptions: unknown parent' 2 "unknown parent 'MissingParent'" \
  "$PY/python-exception-handling-designer/scripts/scaffold_exceptions.py" --spec -
t 'ctx_tool: leaky pipeline' 1 'cleanup after `yield` in `vector_transaction`' \
  "$PY/python-context-manager-writer/scripts/ctx_tool.py" leaks "$FX/python/ctx_leaky_pipeline.py" --strict
t 'ctx_tool: clean pipeline' 0 'No resource-handling issues found' \
  "$PY/python-context-manager-writer/scripts/ctx_tool.py" leaks "$FX/python/ctx_clean_pipeline.py" --strict
STDIN=$'import threading\nlock = threading.Lock()\ndef f(d):\n    lock.acquire()\n    d[\'k\'] = 1\n    lock.release()\n' t 'ctx_tool: acquire without finally (stdin)' 1 'CTX002 acquire-without-finally' \
  "$PY/python-context-manager-writer/scripts/ctx_tool.py" leaks - --strict
t 'ctx_tool: atomic-write recipe' 0 'os.replace(tmp_name, target)' \
  "$PY/python-context-manager-writer/scripts/ctx_tool.py" scaffold --recipe atomic-write
t 'explain_concepts: beginner pitfalls' 1 none-returning-method \
  "$PY/python-beginner-concept-tutor/scripts/explain_concepts.py" concepts "$FX/python/tutor_beginner.py" --strict
t 'explain_concepts: above learner level' 1 'walrus operator (:=) (L4' \
  "$PY/python-beginner-concept-tutor/scripts/explain_concepts.py" concepts "$FX/python/tutor_advanced.py" --max-level 2 --strict
t 'explain_concepts: trace shows aliasing' 1 '(same object as prompt_parts)' \
  "$PY/python-beginner-concept-tutor/scripts/explain_concepts.py" trace "$FX/python/tutor_trace.py" --strict
t 'explain_concepts: trace syntax error' 2 "expected ':'" \
  "$PY/python-beginner-concept-tutor/scripts/explain_concepts.py" trace "$FX/python/tutor_syntax_error.py"
STDIN=$'n = 0\nwhile n < 3:\n    print(n)\n' t 'explain_concepts: trace step limit' 1 'stopped after 20 steps' \
  "$PY/python-beginner-concept-tutor/scripts/explain_concepts.py" trace - --max-steps 20 --strict
t 'hang_scan: reentrant lock in async cache' 1 'DLK002 [high] reentrant-acquire' \
  "$PY/python-async-deadlock-debugger/scripts/hang_scan.py" "$FX/python/dead_bad_patterns.py" --strict
t 'hang_scan: thread lock-order cycle' 1 'lock-order cycle model_lock -> tokenizer_lock -> model_lock' \
  "$PY/python-async-deadlock-debugger/scripts/hang_scan.py" "$FX/python/dead_thread_deadlock.py" --strict
t 'hang_scan: clean patterns' 0 'No hang risks found in 1 file(s).' \
  "$PY/python-async-deadlock-debugger/scripts/hang_scan.py" "$FX/python/dead_clean_patterns.py" --strict
STDIN=$'import time\nasync def poll():\n    time.sleep(1)\n' t 'hang_scan: stdin sleep in async' 1 'DLK004 [high] sleep-in-async' \
  "$PY/python-async-deadlock-debugger/scripts/hang_scan.py" - --strict
t 'hang_watchdog: clean script exits 0' 0 'clean pipeline finished' \
  "$PY/python-async-deadlock-debugger/scripts/hang_watchdog.py" --kill-after 30 "$FX/python/dead_clean_patterns.py"
t 'hang_watchdog: dumps and kills thread deadlock' 3 "thread 'cache-refresher': dead_thread_deadlock.py:27 in cache_refresher: with model_lock:   [lock acquire]" \
  "$PY/python-async-deadlock-debugger/scripts/hang_watchdog.py" --dump-after 1 --kill-after 3 "$FX/python/dead_thread_deadlock.py"
t 'hang_watchdog: missing target' 2 'target script not found' \
  "$PY/python-async-deadlock-debugger/scripts/hang_watchdog.py" --kill-after 5 "$FX/python/no_such_script.py"
t 'async_lint: blocking pipeline' 1 'AIO002 [high] blocking-http: `requests.post(...)`' \
  "$PY/python-asyncio-pattern-advisor/scripts/async_lint.py" "$FX/python/aio_bad_pipeline.py" --strict
t 'async_lint: clean pipeline' 0 'No asyncio issues found in 1 file(s) (target Python 3.11)' \
  "$PY/python-asyncio-pattern-advisor/scripts/async_lint.py" "$FX/python/aio_clean_pipeline.py" --strict
t 'async_lint: TaskGroup on 3.9 target' 1 'AIO024 [high] version-feature: `asyncio.TaskGroup` needs Python 3.11+' \
  "$PY/python-asyncio-pattern-advisor/scripts/async_lint.py" "$FX/python/aio_clean_pipeline.py" --target-version 3.9 --strict
STDIN=$'import asyncio\nasync def log(e):\n    await asyncio.sleep(0)\nasync def handle(e):\n    asyncio.create_task(log(e))\n' t 'async_lint: stdin dangling task' 1 'AIO008 [high] dangling-task' \
  "$PY/python-asyncio-pattern-advisor/scripts/async_lint.py" - --strict
t 'gil_probe: io builtin scales with threads' 0 'Classification: I/O-bound' \
  "$PY/python-gil-bottleneck-analyzer/scripts/gil_probe.py" --builtin io --scale 0.2 --repeat 1 --workers 2
t 'gil_probe: target raises' 2 'workload raised during the serial run: JSONDecodeError' \
  "$PY/python-gil-bottleneck-analyzer/scripts/gil_probe.py" --target "$FX/python/gil_probe_targets.py:broken_parser" --repeat 1 --workers 2
t 'gil_probe: timeout kills stuck target' 2 'timed out after 2s; killed the probe and all its workers' \
  "$PY/python-gil-bottleneck-analyzer/scripts/gil_probe.py" --target "$FX/python/gil_probe_targets.py:stuck_worker" --timeout 2 --repeat 1 --workers 2
t 'profile_classify: py-spy gil-bound gate' 1 'Gate: FAIL (pure-Python CPU 78.6%, limit 50.0%)' \
  "$PY/python-gil-bottleneck-analyzer/scripts/profile_classify.py" "$FX/python/gil_pyspy_gil_bound.txt" --fail-if-python-cpu-over 50
t 'profile_classify: gil contention' 0 'Verdict: GIL-CONTENDED: 64% of samples wait to take the GIL' \
  "$PY/python-gil-bottleneck-analyzer/scripts/profile_classify.py" "$FX/python/gil_pyspy_contended.txt"
t 'profile_classify: pstats file' 0 'embed (python/gil_workload.py:42)' \
  "$PY/python-gil-bottleneck-analyzer/scripts/profile_classify.py" "$FX/python/gil_profile_sample.prof"
STDIN_FILE="$FX/python/gil_pyspy_releasing.txt" t 'profile_classify: stdin gil-releasing' 0 'Verdict: GIL-RELEASING NATIVE' \
  "$PY/python-gil-bottleneck-analyzer/scripts/profile_classify.py" - --fail-if-python-cpu-over 50
t 'pool_tool: check bad patterns' 1 'MP004 [high] async-result-after-with' \
  "$PY/python-multiprocessing-pool-designer/scripts/pool_tool.py" check "$FX/python/mp_bad_patterns.py" --strict
t 'pool_tool: check clean pipeline' 0 'No multiprocessing issues found in 1 file(s).' \
  "$PY/python-multiprocessing-pool-designer/scripts/pool_tool.py" check "$FX/python/mp_clean_pipeline.py" --strict
STDIN=$'from multiprocessing import Pool\nwith Pool() as p:\n    p.map(lambda x: x, range(10))\n' t 'pool_tool: check stdin lambda' 1 'MP002 [high] unpicklable-callable: a lambda passed to map()' \
  "$PY/python-multiprocessing-pool-designer/scripts/pool_tool.py" check - --strict
t 'pool_tool: plan memory-capped workers' 0 'memory limit caps workers at 3' \
  "$PY/python-multiprocessing-pool-designer/scripts/pool_tool.py" plan --items 5000 --item-ms 120 --init-s 6 --mem-per-worker-mb 1800 --mem-limit-mb 8192 --cores 16 --start-method spawn
t 'pool_tool: plan min-speedup gate' 1 'GATE FAILED: estimated speedup 0.14x < --min-speedup 2' \
  "$PY/python-multiprocessing-pool-designer/scripts/pool_tool.py" plan --items 1000 --item-ms 0.05 --payload-kb 64 --cores 8 --start-method spawn --min-speedup 2
t 'executor_tool: check bad patterns' 1 'TPE009 [high] executor-self-wait' \
  "$PY/python-threadpool-executor-builder/scripts/executor_tool.py" check "$FX/python/tpe_bad_patterns.py" --strict
t 'executor_tool: check ai services' 1 'TPE016 [medium] executor-per-call: executor created per request in handler answer()' \
  "$PY/python-threadpool-executor-builder/scripts/executor_tool.py" check "$FX/python/tpe_ai_services.py" --strict
t 'executor_tool: check clean pipeline' 0 'No thread-pool issues found in 1 file(s).' \
  "$PY/python-threadpool-executor-builder/scripts/executor_tool.py" check "$FX/python/tpe_clean_pipeline.py" --strict
STDIN=$'from concurrent.futures import ThreadPoolExecutor\ndef f(x):\n    return x\ndef main(items):\n    with ThreadPoolExecutor(4) as ex:\n        for i in items:\n            ex.submit(f, i)\n' t 'executor_tool: check stdin dropped future' 1 'TPE001 [high] future-never-read' \
  "$PY/python-threadpool-executor-builder/scripts/executor_tool.py" check - --strict
t 'executor_tool: scaffold bounded-map' 0 'done, _ = wait(pending, timeout=timeout, return_when=FIRST_COMPLETED)' \
  "$PY/python-threadpool-executor-builder/scripts/executor_tool.py" scaffold --recipe bounded-map
t 'executor_tool: scaffold unknown recipe' 2 "unknown recipe 'nope'" \
  "$PY/python-threadpool-executor-builder/scripts/executor_tool.py" scaffold --recipe nope
t 'migrate_async: service has manual items' 1 'MIG099 [manual] other-asyncio-api: other asyncio API: asyncio.Barrier' \
  "$PY/python-trio-anyio-migrator/scripts/migrate_async.py" "$FX/python/anyio_asyncio_service.py" --strict
t 'migrate_async: mechanical-only diff' 0 '+        self.lock: anyio.Lock = anyio.Lock()' \
  "$PY/python-trio-anyio-migrator/scripts/migrate_async.py" "$FX/python/anyio_mechanical_only.py" --diff
t 'migrate_async: check gate on already-anyio' 0 'No asyncio usage found in 1 file(s); nothing to migrate' \
  "$PY/python-trio-anyio-migrator/scripts/migrate_async.py" "$FX/python/anyio_already_anyio.py" --check
STDIN=$'import asyncio\nasync def main():\n    await asyncio.sleep(1)\nasyncio.run(main())\n' t 'migrate_async: stdin diff to trio' 0 '+trio.run(main)' \
  "$PY/python-trio-anyio-migrator/scripts/migrate_async.py" - --diff --target trio
