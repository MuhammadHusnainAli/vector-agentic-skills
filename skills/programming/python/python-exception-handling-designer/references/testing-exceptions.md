# Testing Exceptions

How to prove that code raises the right error, with the right message and context, that retries and fallbacks
behave, that cancellation propagates, and that nothing is silently swallowed. Uses pytest (with
`pytest-asyncio` or `anyio` for async tests) and the standard library only.

## Contents

- [1. pytest.raises basics](#1-pytestraises-basics)
- [2. Matching messages safely](#2-matching-messages-safely)
- [3. Inspecting the exception: attributes, cause, notes](#3-inspecting-the-exception-attributes-cause-notes)
- [4. Exception groups](#4-exception-groups)
- [5. Warnings](#5-warnings)
- [6. Asserting logs](#6-asserting-logs)
- [7. Fault injection for retries and fallbacks](#7-fault-injection-for-retries-and-fallbacks)
- [8. Async: timeouts and cancellation](#8-async-timeouts-and-cancellation)
- [9. Testing the hierarchy itself](#9-testing-the-hierarchy-itself)
- [10. FastAPI error translation](#10-fastapi-error-translation)
- [11. CLI exit codes](#11-cli-exit-codes)
- [12. Anti-patterns in tests](#12-anti-patterns-in-tests)

## 1. pytest.raises basics

```python
import pytest

from ragkit.chunking import chunk
from ragkit.errors import InputValidationError


def test_overlap_must_be_smaller_than_size():
    with pytest.raises(ValueError, match=r"overlap \(64\) must be smaller than size \(32\)"):
        chunk("some text", size=32, overlap=64)


def test_domain_error_is_also_a_value_error():
    with pytest.raises(InputValidationError):
        chunk("", size=32, overlap=0)
```

| Feature | Usage |
|---------|-------|
| type | `pytest.raises(KeyError)`; a tuple `pytest.raises((KeyError, IndexError))` |
| subclass semantics | passes when a subclass is raised; assert exact type with `excinfo.type is X` |
| `match=` | `re.search` against `str(exc)` (3.11+: also against `__notes__`, pytest >= 8) |
| `excinfo` | `excinfo.value` (the exception), `excinfo.type`, `excinfo.traceback` |
| only the last statement should raise | keep the `with` block to a single call |
| `pytest.raises(..., check=fn)` | pytest >= 8.4: extra predicate on the exception |

Put only the raising call inside the block; otherwise setup code can raise the same type and the test passes
for the wrong reason.

```python
def test_missing_variable(prompt_registry):
    template = prompt_registry.get("qa")                   # outside: must not raise
    with pytest.raises(InputValidationError, match="missing variables: context"):
        template.render(question="What is RAG?")
```

## 2. Matching messages safely

`match` is a regular expression: escape user data.

```python
import re

model = "gpt-4o (2024-08-06)"
with pytest.raises(ProviderError, match=re.escape(f"unknown model {model!r}")):
    get_client(model)
```

Prefer asserting attributes over long message regexes; messages change, attributes are API.

## 3. Inspecting the exception: attributes, cause, notes

```python
def test_rate_limit_is_translated_with_retry_after(fake_openai):
    fake_openai.fail_with(status=429, headers={"retry-after": "7"})

    with pytest.raises(RateLimitError) as excinfo:
        client.chat([{"role": "user", "content": "hi"}], model="m")

    err = excinfo.value
    assert err.retryable is True
    assert err.retry_after == 7.0
    assert err.provider == "openai"
    assert isinstance(err.__cause__, openai.RateLimitError)     # chained with `from err`


def test_note_added_per_batch():
    with pytest.raises(ProviderError) as excinfo:
        embed_all(["a", "b"], embedder=AlwaysFailing())
    assert any("batch 0" in note for note in excinfo.value.__notes__)   # 3.11+


def test_lookup_hides_internal_key_error():
    with pytest.raises(ConfigurationError) as excinfo:
        price_for("no-such-model")
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__suppress_context__ is True          # raised `from None`
```

## 4. Exception groups

```python
async def test_taskgroup_reports_every_failure():
    with pytest.raises(ExceptionGroup) as excinfo:
        await fan_out([fail_with(RateLimitError("429", provider="a")), fail_with(ValueError("bad"))])

    group = excinfo.value
    assert group.subgroup(RateLimitError) is not None
    assert group.subgroup(ValueError) is not None
    assert len(group.exceptions) == 2
```

pytest >= 8.0 adds `excinfo.group_contains`, and pytest >= 8.4 adds `pytest.RaisesGroup` / `pytest.RaisesExc`:

```python
def test_group_contains():
    with pytest.raises(ExceptionGroup) as excinfo:
        validate_tools([{"name": "search"}, {"name": 3}])
    assert excinfo.group_contains(ValueError, match="tool=3")
    assert excinfo.group_contains(ValueError, depth=1)            # only direct children


def test_exact_group_shape():                                     # pytest >= 8.4
    with pytest.RaisesGroup(ValueError, ValueError, match="2 invalid tool schemas"):
        validate_tools([{"name": 1}, {"name": 2}])
```

`except*` coverage: test each clause by raising groups that contain only that type, mixed types (both clauses
run), and an unmatched type (must propagate).

## 5. Warnings

```python
def test_engine_argument_is_deprecated():
    with pytest.warns(DeprecationWarning, match="`engine` is deprecated"):
        chat("hi", engine="old-model")


def test_no_warnings_on_happy_path(recwarn):
    chat("hi", model="small")
    assert not recwarn.list
```

Make unexpected warnings fail the suite:

```toml
# pyproject.toml
[tool.pytest.ini_options]
filterwarnings = [
    "error",
    "ignore::DeprecationWarning:some_third_party.*",
]
```

## 6. Asserting logs

```python
import logging


def test_fallback_is_logged_with_traceback(caplog, failing_store):
    with caplog.at_level(logging.WARNING, logger="ragkit.retrieval"):
        docs = retrieve("what is hybrid search?", store=failing_store)

    assert docs                                                    # BM25 fallback returned results
    record = next(r for r in caplog.records if "falling back to BM25" in r.getMessage())
    assert record.levelno == logging.WARNING
    assert record.exc_info is not None                             # traceback attached
    assert isinstance(record.exc_info[1], VectorStoreError)
```

A swallowed-error regression test: assert that a fallback path logs, so a future `except Exception: pass`
breaks the test.

## 7. Fault injection for retries and fallbacks

Fakes that fail N times, then succeed:

```python
import itertools


class Flaky:
    """Callable that raises the given errors in order, then returns `result`."""

    def __init__(self, *errors: BaseException, result="ok"):
        self.errors = list(errors)
        self.result = result
        self.calls = 0

    async def __call__(self, *args, **kwargs):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return self.result


@pytest.fixture
def no_sleep(monkeypatch):
    slept = []

    async def fake_sleep(delay):
        slept.append(delay)

    monkeypatch.setattr("ragkit.retry.asyncio.sleep", fake_sleep)
    return slept


async def test_retries_transient_then_succeeds(no_sleep):
    call = Flaky(ProviderOverloadedError("503", provider="p"), RateLimitError("429", provider="p", retry_after=2))
    assert await retry_async(call, attempts=5) == "ok"
    assert call.calls == 3
    assert no_sleep[1] == 2                                        # honoured Retry-After


async def test_does_not_retry_permanent_errors(no_sleep):
    call = Flaky(ContextLengthError("too long", provider="p", tokens=9000, limit=8192))
    with pytest.raises(ContextLengthError):
        await retry_async(call, attempts=5)
    assert call.calls == 1
    assert no_sleep == []


async def test_gives_up_with_original_error(no_sleep):
    errors = [ProviderOverloadedError("503", provider="p") for _ in range(5)]
    with pytest.raises(ProviderOverloadedError):
        await retry_async(Flaky(*errors), attempts=3)


async def test_fallback_chain_uses_second_model(monkeypatch):
    monkeypatch.setitem(CLIENTS, "openai", FakeClient(fail=ProviderOverloadedError("529", provider="openai")))
    monkeypatch.setitem(CLIENTS, "anthropic", FakeClient(reply="answer"))
    assert await complete_with_fallback([{"role": "user", "content": "q"}]) == "answer"
```

Make jitter deterministic with `monkeypatch.setattr(random, "uniform", lambda a, b: b)` or by injecting an
`rng` parameter.

Parametrise the classification table so every provider status is covered:

```python
@pytest.mark.parametrize(
    ("status", "expected", "retryable"),
    [(429, RateLimitError, True), (500, ProviderOverloadedError, True), (503, ProviderOverloadedError, True),
     (400, ProviderError, False), (401, ProviderAuthError, False)],
)
def test_status_translation(fake_openai, status, expected, retryable):
    fake_openai.fail_with(status=status)
    with pytest.raises(expected) as excinfo:
        client.chat([], model="m")
    assert excinfo.type is expected
    assert is_retryable(excinfo.value) is retryable
```

Structured-output repair loop:

```python
async def test_repair_loop_feeds_errors_back(fake_llm):
    fake_llm.replies = ['{"company": "Acme", "amount": "lots"}', '{"company": "Acme", "amount": 12, "currency": "USD"}']
    result = await extract("invoice text", model="m", max_repairs=2)
    assert result.amount == 12
    repair_prompt = fake_llm.requests[1][-1]["content"]
    assert "amount" in repair_prompt                    # validation error was sent back


async def test_repair_loop_gives_up(fake_llm):
    fake_llm.replies = ["not json"] * 3
    with pytest.raises(StructuredOutputError, match="schema validation"):
        await extract("invoice text", model="m", max_repairs=2)
    assert len(fake_llm.requests) == 3
```

CUDA OOM halving without a GPU:

```python
def test_encode_halves_batch_on_oom(monkeypatch):
    seen = []

    class FakeModel:
        def encode(self, batch, convert_to_tensor=True):
            seen.append(len(batch))
            if len(batch) > 2:
                raise torch.cuda.OutOfMemoryError("CUDA out of memory")
            return torch.zeros(len(batch), 4)

    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: None)
    out = encode_adaptive(FakeModel(), ["t"] * 5, batch_size=8)
    assert out.shape == (5, 4)
    assert seen[:3] == [5, 4, 2]
```

## 8. Async: timeouts and cancellation

```python
import asyncio


async def test_stream_reraises_cancellation_and_closes(fake_stream):
    task = asyncio.create_task(consume(stream_tokens(fake_stream, "hi")))
    await asyncio.sleep(0)                          # let it start
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert fake_stream.closed                       # cleanup ran


async def test_deadline_raises_domain_timeout(slow_llm):
    with pytest.raises(ProviderTimeoutError) as excinfo:
        await chat_with_deadline([{"role": "user", "content": "hi"}], seconds=0.01)
    assert isinstance(excinfo.value.__cause__, TimeoutError)
```

A handler that swallows `CancelledError` makes the first test hang or fail: that is the point. Add a pytest
timeout (`pytest-timeout`) so a hang is reported as a failure.

## 9. Testing the hierarchy itself

```python
import pickle

import pytest

from ragkit import errors

ALL_ERRORS = [cls for cls in vars(errors).values()
              if isinstance(cls, type) and issubclass(cls, errors.RagkitError)]


@pytest.mark.parametrize("cls", ALL_ERRORS, ids=lambda c: c.__name__)
def test_every_error_derives_from_base_and_pickles(cls):
    err = cls("boom")
    assert isinstance(err, errors.RagkitError)
    assert str(err).startswith("boom")
    clone = pickle.loads(pickle.dumps(err))
    assert type(clone) is cls and clone.message == err.message


@pytest.mark.parametrize("cls", ALL_ERRORS, ids=lambda c: c.__name__)
def test_every_error_has_http_status(cls):
    assert 400 <= errors.http_status_for(cls("x")) <= 599


def test_retryable_flags():
    assert errors.RateLimitError("x").retryable
    assert not errors.ContextLengthError("x").retryable
    assert errors.is_retryable(TimeoutError())
    assert not errors.is_retryable(KeyError("k"))
```

These work unchanged on modules generated by `scripts/scaffold_exceptions.py` (whose constructors accept
`message` plus optional keyword attributes). Add `--check` to CI to catch hand edits drifting from the spec.

## 10. FastAPI error translation

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ragkit.errors import RateLimitError, register_exception_handlers

app = FastAPI()
register_exception_handlers(app)


@app.get("/boom")
async def boom():
    raise RateLimitError("slow down", retry_after=2.5, provider="openai")


def test_rate_limit_maps_to_429_with_retry_after():
    client = TestClient(app)
    resp = client.get("/boom")
    assert resp.status_code == 429
    assert resp.headers["retry-after"] == "3"
    assert resp.json()["error"] == "rate_limit"


def test_unexpected_errors_do_not_leak_internals():
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/crash")                     # route raising KeyError("api_key=sk-...")
    assert resp.status_code == 500
    assert "sk-" not in resp.text
```

`TestClient` re-raises unhandled server exceptions by default; pass `raise_server_exceptions=False` to assert
on the 500 response instead.

## 11. CLI exit codes

```python
def test_cli_reports_domain_error(capsys, monkeypatch):
    def fail(args):
        raise ConfigurationError("no API key")

    monkeypatch.setattr("ragkit.cli.run", fail)
    assert main(["ask", "hi"]) == 1
    assert "error: no API key" in capsys.readouterr().err


def test_argparse_errors_exit_2():
    with pytest.raises(SystemExit) as excinfo:
        main(["--no-such-flag"])
    assert excinfo.value.code == 2
```

## 12. Anti-patterns in tests

| Anti-pattern | Problem | Fix |
|--------------|---------|-----|
| `try: f(); assert False except X: pass` | `AssertionError` from `assert False` can be caught by a broad handler; noisy | `pytest.raises(X)` |
| `pytest.raises(Exception)` | passes for any bug (`TypeError` in the test itself) | the specific type plus `match=` |
| several statements inside `pytest.raises` | the wrong line may raise | one call per block |
| asserting on full traceback text | brittle across versions | assert type, attributes, `__cause__` |
| unescaped `match` with user data | regex metacharacters (`(`, `.`, `?`) | `re.escape` |
| real `sleep` in retry tests | slow, flaky | patch `asyncio.sleep` / inject a clock |
| testing only the happy path of a retry | exhaustion and non-retryable paths untested | test success-after-N, give-up, never-retry |
| catching `ExceptionGroup` with `pytest.raises(ValueError)` | TaskGroup wraps even a single error | `pytest.raises(ExceptionGroup)` + `group_contains` |
