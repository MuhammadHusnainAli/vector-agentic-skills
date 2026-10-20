# Review Checklist

How to run a Python idiom review end to end, grade severity consistently, avoid false positives, and write comments that get acted on. Pairs with `scripts/review_idioms.py`.

## Contents

1. [Before you start](#before-you-start)
2. [Running the scanner](#running-the-scanner)
3. [Manual pass checklist](#manual-pass-checklist)
4. [Grading severity](#grading-severity)
5. [Rule reference and false positives](#rule-reference-and-false-positives)
6. [Writing review comments](#writing-review-comments)
7. [Rewriting safely](#rewriting-safely)
8. [Reporting](#reporting)
9. [CI integration](#ci-integration)

---

## Before you start

Answer these before judging any line:

| Question | Why it changes the review |
|----------|---------------------------|
| Minimum Python version? | Decides whether `match`, `X \| Y`, `TaskGroup`, `batched`, `StrEnum` are allowed |
| Library, service, CLI, notebook or one-off script? | `print` is fine in CLIs/notebooks, not in libraries; module-level clients matter more in services |
| Sync or async? | Blocking-call rules only matter in async code |
| Hot path? | Micro-idioms (join vs +=, set membership) matter in loops over corpora, not in config loading |
| Existing style tools? (ruff, black, mypy) | Do not duplicate what the formatter already enforces; focus on semantics |
| Tests present? | Determines how aggressive the rewrite can be |

## Running the scanner

```bash
python scripts/review_idioms.py path/to/file.py                 # full review with rewrites
python scripts/review_idioms.py src/ --min-severity medium      # triage a whole package
python scripts/review_idioms.py src/ --json > review.json       # feed into another tool
python scripts/review_idioms.py src/ --select PY036,PY037,PY038,PY039,PY040,PY041   # production-risk sweep
git diff --name-only main -- '*.py' | xargs python scripts/review_idioms.py   # only changed files
```

JSON shape:

```json
{
  "files": 1,
  "summary": {"high": 1, "medium": 0, "low": 2},
  "findings": [
    {"path": "app.py", "line": 14, "col": 1, "rule": "PY036", "name": "hardcoded-secret",
     "severity": "high", "message": "...", "source": "OPENAI_API_KEY = \"sk-...\"", "fix": "..."}
  ],
  "errors": []
}
```

The scanner is a first pass. Treat each finding as a question ("is this really a problem here?"), not a verdict.

## Manual pass checklist

Go through the code once more with this list; most items cannot be detected statically.

### Correctness

- [ ] Every rewrite candidate is behaviour-equivalent (see [Rewriting safely](#rewriting-safely))
- [ ] Functions return one type; no `None`-or-list mixes; errors raise, not return strings
- [ ] No shared mutable state: module-level lists/dicts mutated by functions, class attributes used as instance state
- [ ] Float comparisons use tolerances (`math.isclose`, `np.allclose`)
- [ ] Integer division and off-by-one in slicing, chunk overlap, pagination
- [ ] `dict.get(k, default)` vs stored `None` values
- [ ] Iterators consumed twice (generators, `zip`, `map`, file handles)
- [ ] Late-binding closures in loops (`lambda: i` captures the variable, not the value)

### Errors

- [ ] No bare `except:`; broad `except Exception` only at boundaries (request handler, worker loop) and always logged
- [ ] `raise ... from err` when translating exceptions
- [ ] `try` blocks contain only the call that can fail
- [ ] Cleanup in `finally` or a context manager, never only on the happy path

### Resources

- [ ] Files, sockets, sessions, DB connections, locks use `with` / `async with`
- [ ] Text I/O passes `encoding="utf-8"`
- [ ] Clients are created once and reused; closed on shutdown

### Async and concurrency

- [ ] No blocking calls in `async def` (including sync SDK methods and CPU-heavy work)
- [ ] Every coroutine is awaited; created tasks are kept or owned by a `TaskGroup`
- [ ] Concurrency is bounded (Semaphore) and matched to rate limits
- [ ] Timeouts on every network call and an overall deadline per request

### AI specifics

- [ ] No secrets in code, notebooks, test fixtures or default args
- [ ] Retries bounded, only on retryable errors, with jittered backoff; not stacked on top of SDK retries unknowingly
- [ ] Model output is parsed and validated (pydantic / JSON schema), never `eval`ed
- [ ] Prompts are templates with named fields; untrusted text is delimited
- [ ] Token counting uses the tokenizer, not `len(str)`
- [ ] Prompts/completions/PII not logged at INFO
- [ ] numpy/torch truthiness not used on arrays/tensors

### Readability

- [ ] Names say what, not how (`relevant_chunks`, not `lst2`)
- [ ] Functions do one thing; flag arguments split into two functions
- [ ] Comments explain why; no commented-out code
- [ ] Type hints on public functions

## Grading severity

| Severity | Test | Typical rules | Action |
|----------|------|---------------|--------|
| high | Can this cause wrong output, data loss, a security incident or an outage in normal operation? | PY001–PY005, PY036–PY038, PY040 | Must fix before merge |
| medium | Correct today but breaks on a plausible edge case, input type or load pattern | PY006, PY008–PY010, PY012, PY039, PY041 | Fix before merge unless justified |
| low | Readability, idiom, consistency, minor perf | PY007, PY011, PY013–PY035, PY042–PY046 | Suggest; batch into one comment |

Adjust by context:

- Raise by one level when the code is on a hot path, handles user input, or runs unattended (workers, cron jobs).
- Lower by one level in throwaway scripts, notebooks, or tests (except secrets: always high).
- A low finding repeated 50 times is still low; mention the pattern once with a count.

## Rule reference and false positives

| Rule | Name | Common false positive / exception | What to do |
|------|------|-----------------------------------|------------|
| PY001 | mutable-default | Sentinel used only for identity, never mutated | Still prefer `None`; or use a module-level `_MISSING = object()` |
| PY002 | bare-except | Top-level crash reporter that re-raises | Use `except BaseException:` explicitly and re-raise |
| PY003 | swallowed-exception | Best-effort telemetry/cleanup | Log at debug, or `contextlib.suppress(SpecificError)` |
| PY004 | eval-exec | Sandboxed code-execution tool (agent code interpreter) | Must run in a separate process/container with limits; document it |
| PY005 | shell-injection | Constant command string with no interpolation | Still prefer a list; acceptable with a `# noqa: PY005` and comment |
| PY006 | compare-none | numpy/pandas element-wise `== None` intended | Use `pd.isna` / `np.equal(x, None)` explicitly |
| PY007 | compare-bool | Tri-state values where `None` must differ from `False` | Use `is True` / `is False` |
| PY008 | type-compare | Deliberate exact-type check (exclude `bool` from `int`) | `type(x) is int` with a comment |
| PY009 | open-without-with | Handle returned to the caller who closes it | Document ownership; return a context manager instead if possible |
| PY010 | star-import | Package `__init__` re-export with `__all__` | Acceptable with `__all__` defined |
| PY011 | raise-without-from | Intentionally hiding the cause | `from None` makes it explicit |
| PY012 | range-len | Loop that mutates `xs[i]` in place | `for i, x in enumerate(xs): xs[i] = f(x)` or a new list |
| PY013 | manual-counter | Counter incremented conditionally | Not a counter; ignore |
| PY014 | dict-keys | Iterating while deleting keys | `for k in list(d):` is the idiom |
| PY015 | append-loop | Loop body with side effects (logging, I/O) | Keep the loop |
| PY016 | any-all-loop | Loop does work before returning | Keep the loop |
| PY017 | setdefault | Expensive default constructor | `defaultdict(factory)` still fine |
| PY018 | str-concat-loop | Few iterations, readability wins | Low; leave in small loops |
| PY019 | old-format | Templates filled later (`TEMPLATE.format(...)`), logging, SQL params | Templates with `.format` on a constant are fine |
| PY020 | len-truthiness | numpy arrays, DataFrames, tensors | Keep `len()` / `.size` / `.empty` |
| PY021 | not-in | — | Always fix |
| PY022 | isinstance-chain | — | Always fix |
| PY023 | lambda-assign | — | Always fix |
| PY024 | shadow-builtin | Pydantic/dataclass fields named `id`, `type` (class level is not flagged) | Parameters mirroring an external API (`input=`) can stay |
| PY025 | os-path | `os.path` in hot loops over millions of strings (slightly faster) | Measure first |
| PY026 | open-encoding | Binary data, or locale encoding genuinely intended | `encoding="locale"` (3.10+) makes intent explicit |
| PY027 | utcnow | Interop with a library expecting naive UTC | Convert at the boundary |
| PY028 | global-stmt | Tiny scripts | Low |
| PY029 | elif-chain | Conditions that are not simple equality | Not flagged; fine |
| PY030 | lbyl-exists | Exists check that chooses between two code paths | Fine if no race matters |
| PY031 | typing-generics | Must support 3.8 | Keep until 3.9 is the floor |
| PY032 | semicolon | — | Always fix |
| PY033 | backslash | `with` statements before 3.10 | Allowed for multi-item `with` below 3.10 |
| PY034 | print-debug | CLI output, notebooks, functions whose job is printing | `print*`/`show*`/`report*`/`main` are exempt; others `# noqa` |
| PY035 | logging-format | Message built once at startup | Low |
| PY036 | hardcoded-secret | Test fixtures with fake keys | Use obviously fake values (`"test-key"`) or env in tests |
| PY037 | sleep-in-async | Code in a thread started via `to_thread` but defined `async` | Not possible; always fix |
| PY038 | blocking-in-async | Startup code in an async lifespan that runs once | Low impact; still prefer async |
| PY039 | http-no-timeout | Session with a mounted adapter enforcing timeouts | Document it |
| PY040 | unbounded-retry | Worker main loop that polls a queue (not a retry) | Fine if errors are logged and not tight-looping |
| PY041 | import-time-client | Tiny scripts, notebooks | Fine there |
| PY042 | llm-client-no-timeout | Timeout set via `with_options` per call | Fine |
| PY043 | prompt-concat | Two-piece concatenation in a tiny helper | Low |
| PY044 | sequential-await | Calls that depend on the previous result, or strict ordering/rate limits | Keep sequential; say why |
| PY045 | suppress | — | Fix |
| PY046 | walrus | Target codebase below 3.8, or team prefers explicit lines | Optional |

Suppress a reviewed exception inline: `do_thing()  # noqa: PY034 - CLI output`.

## Writing review comments

A good comment has four parts: **where**, **what**, **why it matters here**, **concrete fix**.

```
L14 [high] PY036 hardcoded key
The OpenAI key is committed in source; anyone with repo access (and any bot scanning
GitHub) can use it. Please revoke it and read it from the environment:

    api_key = os.environ["OPENAI_API_KEY"]
```

```
L30 [high] PY037 time.sleep inside async def
fetch_context() runs on the event loop; time.sleep(1) pauses every request in this
worker for a second. Use `await asyncio.sleep(1)`.
```

```
L24, L41, L57 [low] PY012 range(len(...)) (3 places)
Iterating directly reads better and avoids index bugs:

    for text in texts: ...
    for i, text in enumerate(texts): ...   # if you need i
```

Tone and form:

- Lead with the impact, not the rule name.
- Be specific about the fix; include the code.
- Group repeated low findings into one comment.
- Mark optional suggestions as "nit:" or "optional:"; do not block a merge on them.
- Ask a question when intent is unclear ("Is swallowing this deliberate? If so, a comment would help").
- Praise good patterns briefly when they are non-obvious (a correct `TaskGroup`, a clean retry policy).

## Rewriting safely

Equivalence traps to check before suggesting a rewrite:

| Rewrite | Trap |
|---------|------|
| loop → comprehension | Loop variable no longer exists after a comprehension; side effects in the loop body are lost |
| loop → `any()`/`all()` | Generator stops at the first hit, same as the loop; but `all([])` is `True` |
| `len(x) == 0` → `not x` | Breaks for numpy arrays/DataFrames; changes meaning if `x` can be `None` |
| `== None` → `is None` | Changes behaviour for objects with custom `__eq__` (intended) |
| `range(len(a))` → `zip(a, b)` | `zip` truncates silently; use `strict=True` (3.10+) |
| `except Exception` → specific errors | Errors that were swallowed now propagate; call it out |
| `%`/`.format` → f-string | f-strings evaluate immediately; templates filled later must stay templates |
| `os.path.join` → `Path /` | Returns `Path`, not `str`; callers doing string ops may break (`str(p)` at the boundary) |
| `dict[k]` init → `defaultdict` | Reading a missing key now inserts it; convert with `dict(dd)` before returning |
| `if os.path.exists` → `try/except` | Make sure the except catches only the not-found case |
| `requests` → `httpx` | Different defaults (httpx does not follow redirects by default) |
| sequential await → `gather` | Order of side effects changes; rate limits may be hit |

After rewriting: re-run the scanner, run the tests, and spot-check edge inputs (empty list, `None`, one item, unicode, very large input).

## Reporting

```
## Summary
Solid structure, but two production risks: a committed API key and blocking calls in
async handlers. Assumed Python 3.11.

## Findings
| # | Line | Rule  | Severity | Issue                         | Fix                          |
|---|------|-------|----------|-------------------------------|------------------------------|
| 1 | 14   | PY036 | high     | OpenAI key in source          | env var + rotate             |
| 2 | 30   | PY037 | high     | time.sleep in async def       | await asyncio.sleep          |
| 3 | 22   | PY039 | medium   | requests.post without timeout | timeout=(5, 60)              |
| 4 | 46   | PY018 | low      | += string building in loop    | "\n".join(...)               |

## Rewritten code
...

## Behaviour changes
- Requests now raise after 60 s instead of hanging.

## Not changed
- print() in main(): CLI output, intended.

## Next steps
- Add `python scripts/review_idioms.py src --strict` to CI.
- Test for the retry path (mock a 429 then 200).
```

## CI integration

GitHub Actions step:

```yaml
- name: Idiom review
  run: python skills/programming/python/python-idiomatic-code-reviewer/scripts/review_idioms.py src --strict --min-severity medium
```

pre-commit local hook:

```yaml
repos:
  - repo: local
    hooks:
      - id: review-idioms
        name: review idioms
        entry: python tools/review_idioms.py --strict
        language: system
        types: [python]
```

Rollout on a legacy codebase:

1. Start with `--select` on the high rules only; fix or `# noqa` existing hits.
2. Add medium rules once high is clean.
3. Keep low rules advisory (no `--strict`), or run them only on changed files.
