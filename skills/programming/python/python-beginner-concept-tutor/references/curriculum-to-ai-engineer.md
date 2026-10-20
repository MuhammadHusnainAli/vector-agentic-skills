# Curriculum: From Zero to "Can Build an LLM App"

A staged path for data scientists, analysts, students and career switchers. Each stage lists the concepts, a time estimate for someone studying 5-8 hours a week, a milestone project and a "ready to move on when" check. Stages 0-11 are general Python; stages 12-14 apply it to AI engineering. Every code block runs on Python 3.10+ (most on 3.9).

## Contents

- [How to use this path](#how-to-use-this-path)
- [Overview](#overview)
- [Stage 0: Setup](#stage-0-setup)
- [Stage 1: Values, variables and strings](#stage-1-values-variables-and-strings)
- [Stage 2: Collections](#stage-2-collections)
- [Stage 3: Control flow](#stage-3-control-flow)
- [Stage 4: Functions and scope](#stage-4-functions-and-scope)
- [Stage 5: Modules, pip and virtual environments](#stage-5-modules-pip-and-virtual-environments)
- [Stage 6: Files and JSON](#stage-6-files-and-json)
- [Stage 7: Errors and exceptions](#stage-7-errors-and-exceptions)
- [Stage 8: Classes and dataclasses](#stage-8-classes-and-dataclasses)
- [Stage 9: Pythonic iteration](#stage-9-pythonic-iteration)
- [Stage 10: Decorators, type hints, context managers](#stage-10-decorators-type-hints-context-managers)
- [Stage 11: Async basics](#stage-11-async-basics)
- [Stage 12: numpy and pandas](#stage-12-numpy-and-pandas)
- [Stage 13: HTTP and calling an LLM API](#stage-13-http-and-calling-an-llm-api)
- [Stage 14: Embeddings and a tiny RAG](#stage-14-embeddings-and-a-tiny-rag)
- [Capstone ideas](#capstone-ideas)

## How to use this path

- Diagnose first. Someone who already uses pandas daily can skim stages 1-3 with the quiz questions from [concept-explanations.md](concept-explanations.md) and start at the first stage where they miss two or more.
- One milestone per stage. The milestone is the proof, not the reading. Do not move on until the "ready when" check passes.
- Keep the AI goal visible. Every stage below has an AI-flavoured project so learners see why loops and dicts matter.
- Use `scripts/explain_concepts.py concepts project.py --max-level N` to check that example code you show does not use concepts the learner has not met yet.

## Overview

| Stage | Topic | Time | Milestone |
|-------|-------|------|-----------|
| 0 | Setup: install, run, REPL, editor, venv | 2-4 h | `hello_model.py` runs from the terminal |
| 1 | Values, variables, strings, f-strings, numbers | 4-6 h | Prompt formatter |
| 2 | Lists, dicts, sets, tuples, indexing, slicing | 6-8 h | Chat history as a list of dicts |
| 3 | if/elif/else, for, while, range, enumerate, zip | 6-8 h | Token budget checker |
| 4 | Functions, parameters, return, scope | 6-8 h | `build_prompt()` library |
| 5 | Modules, import, pip, venv, uv | 3-4 h | Project with a pinned dependency |
| 6 | Files, pathlib, JSON, CSV | 4-6 h | FAQ loader |
| 7 | Tracebacks, try/except, raise | 4-6 h | Robust parser for model JSON |
| 8 | Classes, `__init__`, self, dataclasses | 6-8 h | `Conversation` class |
| 9 | Comprehensions, iterators, generators, lambda | 6-8 h | Streaming chunker |
| 10 | Decorators, type hints, context managers | 6-8 h | `@retry` + typed client wrapper |
| 11 | async/await, asyncio.gather | 4-6 h | Parallel fake-model calls |
| 12 | numpy, pandas | 8-10 h | Cosine similarity, eval table |
| 13 | HTTP with httpx/requests, env vars, LLM API | 4-6 h | CLI chatbot |
| 14 | Embeddings, vector search, chunking, RAG | 8-12 h | Tiny RAG over your notes |

Total: roughly 80-110 hours, i.e. 3-4 months part-time.

## Stage 0: Setup

**Concepts**: what an interpreter is, running `python file.py`, the REPL (`>>>`), an editor (VS Code with the Python extension), the terminal, `python -m venv`, `pip`, `uv`.

```bash
python3 --version                 # 3.12 or newer recommended
python3 -m venv .venv             # create a virtual environment in this folder
source .venv/bin/activate         # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
# or, with uv (fast, manages Python versions too):
uv venv && source .venv/bin/activate
uv pip install httpx
```

```python
# hello_model.py
model = "tiny-llm"
print("Hello from", model)
```

**Milestone**: create a folder, a venv, `hello_model.py`, and run it from the terminal and from the editor's Run button.

**Ready when** the learner can explain the difference between typing in the REPL and running a file, and can tell which Python their terminal uses (`which python` / `where python`).

## Stage 1: Values, variables and strings

**Concepts**: int, float, str, bool, None; `type()`; assignment as labels; arithmetic (`/` vs `//` vs `%`, `**`); string methods (`.strip()`, `.lower()`, `.split()`, `.replace()`, `.join()`); f-strings with format specs (`{x:.2f}`, `{n:,}`, `{x=}`); `input()` returns a str; converting with `int()`/`float()`/`str()`.

```python
user_name = input("Your name: ").strip()
question = "What is RAG?"
temperature = 0.2

prompt = f"""You are a helpful tutor.
Student: {user_name}
Question: {question}
Answer clearly (temperature={temperature:.1f})."""
print(prompt)
print(len(prompt), "characters,", len(prompt.split()), "words")
```

**Mini-projects**
- Prompt formatter: ask for a role, a task and a tone, print the assembled prompt.
- Cost estimator: tokens in, tokens out and price per 1,000 tokens -> cost with 4 decimals.

**Ready when** the learner can predict `type(7 / 7)`, `"3" + "4"`, `int("3") + 4` and `f"{2/3:.2f}"` before running them.

## Stage 2: Collections

**Concepts**: list (ordered, mutable), tuple (ordered, immutable), dict (key -> value), set (unique, unordered); indexing from 0 and from the end with -1; slicing `[start:stop:step]`; `len`, `in`; methods (`append`, `extend`, `pop`, `sort` vs `sorted`, `dict.get`, `dict.items`, `set.add`); nesting (list of dicts); references and copying.

```python
history = [
    {"role": "system", "content": "You are concise."},
    {"role": "user", "content": "Define embedding."},
]
history.append({"role": "assistant", "content": "A vector that represents meaning."})

print(history[-1]["content"])           # last message's text
print([m["role"] for m in history])     # preview of stage 9: ['system', 'user', 'assistant']
roles_seen = {m["role"] for m in history}
print("user" in roles_seen)             # True
last_two = history[-2:]                 # slicing keeps the list type
```

**Mini-projects**
- Chat history: build the list above, add two turns, print only user messages.
- Stop words: a set of stop words; filter a sentence's words that are not in it.

**Ready when** the learner can explain why `b = a; b.append(1)` changes `a`, and when to use a tuple vs a list vs a dict vs a set.

## Stage 3: Control flow

**Concepts**: `if`/`elif`/`else`, truthiness (empty list is falsy), comparison and boolean operators, `for` over any iterable, `range`, `enumerate`, `zip`, `while`, `break`/`continue`, loop accumulators.

```python
MAX_TOKENS = 50
messages = ["Hello there", "Explain transformers in detail please", "Thanks!"]

used = 0
for i, text in enumerate(messages):
    cost = len(text.split())          # pretend 1 word = 1 token
    if used + cost > MAX_TOKENS:
        print(f"Message {i} would exceed the budget, stopping.")
        break
    used += cost
    print(f"#{i}: {cost} tokens (total {used})")
else:
    print("All messages fit.")
```

**Mini-projects**
- Token budget checker (above), then keep the most recent messages instead of the first ones.
- Guessing game with `while` and `input()`.

**Ready when** the learner can rewrite a `range(len(x))` loop with `enumerate`, and can say how many times a `while` loop runs before running it.

## Stage 4: Functions and scope

**Concepts**: `def`, parameters vs arguments, `return` vs `print`, default values (and the mutable default trap), keyword arguments, docstrings, local vs global scope, functions calling functions, small pure functions.

```python
def build_prompt(question, context="", style="concise"):
    """Return a prompt string for the model."""
    parts = [f"Answer in a {style} style."]
    if context:
        parts.append(f"Context:\n{context}")
    parts.append(f"Question: {question}")
    return "\n\n".join(parts)


def truncate(text, max_words=20):
    words = text.split()
    return " ".join(words[:max_words]) + (" ..." if len(words) > max_words else "")


print(build_prompt("What is a vector store?", context=truncate("A vector store keeps embeddings " * 10)))
```

**Mini-projects**
- `build_prompt()` with optional context and few-shot examples.
- `normalise(text)` that lowercases, strips punctuation and collapses whitespace; reuse it everywhere after.

**Ready when** the learner can explain why a function that only prints returns `None`, and can fix an `UnboundLocalError`.

## Stage 5: Modules, pip and virtual environments

**Concepts**: `import x`, `from x import y`, the standard library (`math`, `random`, `json`, `pathlib`, `datetime`, `collections`), your own modules (a second `.py` file), `if __name__ == "__main__":`, `pip install`, why a venv per project, `requirements.txt` vs `pyproject.toml`, `uv add`.

```text
my_bot/
  .venv/
  pyproject.toml        # or requirements.txt
  prompts.py            # build_prompt, truncate
  main.py               # from prompts import build_prompt
```

```bash
python -m pip install httpx           # always "python -m pip" so pip matches the python
python -m pip freeze > requirements.txt
# with uv:
uv init my_bot && cd my_bot && uv add httpx && uv run main.py
```

**Ready when** the learner can fix `ModuleNotFoundError` by checking which Python runs and which venv is active (see [common-beginner-errors.md](common-beginner-errors.md)), and never names a file `json.py` or `random.py`.

## Stage 6: Files and JSON

**Concepts**: `with open(path, encoding="utf-8") as f`, read/write modes, `pathlib.Path`, `json.load`/`json.dump`/`json.loads`/`json.dumps`, CSV with `csv.DictReader`, relative paths are relative to the current working directory.

```python
import json
from pathlib import Path

faq_path = Path("faq.json")
faq_path.write_text(json.dumps([
    {"q": "What is RAG?", "a": "Retrieval-augmented generation."},
    {"q": "What is an embedding?", "a": "A vector representing meaning."},
], indent=2), encoding="utf-8")

with faq_path.open(encoding="utf-8") as f:
    faq = json.load(f)
for item in faq:
    print(f"Q: {item['q']}\nA: {item['a']}\n")
```

**Mini-project**: FAQ loader that answers a question by finding the FAQ entry sharing the most words with it.

**Ready when** the learner knows the difference between `json.load` (file) and `json.loads` (string) and always uses `with`.

## Stage 7: Errors and exceptions

**Concepts**: reading a traceback bottom-up, common error types, `try`/`except SpecificError as e`, `else`/`finally`, `raise ValueError("message")`, custom exception classes, not swallowing errors, validating model output.

```python
import json

FENCE = "`" * 3          # three backticks, the Markdown code fence models like to add


def parse_model_json(raw):
    """Model replies sometimes wrap JSON in Markdown fences or add chatter around it."""
    text = raw.strip()
    if text.startswith(FENCE):
        text = text.strip("`")
        text = text.removeprefix("json").strip()      # 3.9+
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object in model reply: {raw[:40]!r}")
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"model returned invalid JSON: {e}") from e


reply = f'Sure! {FENCE}json\n{{"sentiment": "positive", "score": 0.9}}\n{FENCE}'
print(parse_model_json(reply))      # {'sentiment': 'positive', 'score': 0.9}
```

**Ready when** the learner can name the error type and line from any traceback and explain why `except: pass` is dangerous.

## Stage 8: Classes and dataclasses

**Concepts**: a class as a blueprint, objects/instances, `__init__`, `self`, attributes, methods, `__repr__`, inheritance basics, `@dataclass` for data holders, when NOT to use a class (a function is enough).

```python
from dataclasses import dataclass, field


@dataclass
class Message:
    role: str
    content: str


@dataclass
class Conversation:
    system: str
    messages: list = field(default_factory=list)   # never a bare [] default

    def add(self, role, content):
        self.messages.append(Message(role, content))

    def as_payload(self):
        return [{"role": "system", "content": self.system}] + [
            {"role": m.role, "content": m.content} for m in self.messages
        ]


chat = Conversation(system="You are concise.")
chat.add("user", "What is a token?")
print(chat.as_payload())
```

**Ready when** the learner can explain what `self` is (the object the method was called on) and why `field(default_factory=list)` exists.

## Stage 9: Pythonic iteration

**Concepts**: list/dict/set comprehensions, generator expressions, the iteration protocol (`iter`, `next`), generator functions with `yield`, `sorted(key=...)`, `lambda`, `any`/`all`, `sum` with a generator, `itertools` basics.

```python
def chunk_words(text, size=50, overlap=10):
    """Yield chunks of `size` words, each overlapping the previous by `overlap` words."""
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    words = text.split()
    step = size - overlap
    for start in range(0, len(words), step):
        yield " ".join(words[start:start + size])
        if start + size >= len(words):
            break


doc = " ".join(f"w{i}" for i in range(120))
for n, chunk in enumerate(chunk_words(doc, size=50, overlap=10)):
    print(n, chunk.split()[0], "...", chunk.split()[-1])
```

**Ready when** the learner can convert a 4-line append loop into a comprehension and back, and can explain why a generator can only be looped over once.

## Stage 10: Decorators, type hints, context managers

**Concepts**: functions are values, functions inside functions, closures, decorators (`@`), `functools.wraps`; type hints (`list[str]`, `dict[str, float]`, `str | None` 3.10+), running a type checker (mypy/pyright); `with` and writing a context manager with `contextlib.contextmanager`.

```python
import functools
import random
import time


class RateLimitError(Exception):
    pass


def retry(times: int = 3, delay: float = 0.1):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(1, times + 1):
                try:
                    return fn(*args, **kwargs)
                except RateLimitError:
                    if attempt == times:
                        raise
                    time.sleep(delay * 2 ** (attempt - 1))   # exponential backoff
        return wrapper
    return decorator


@retry(times=5)
def flaky_model(prompt: str) -> str:
    if random.random() < 0.5:
        raise RateLimitError("429 Too Many Requests")
    return prompt.upper()


print(flaky_model("hello"))
```

**Ready when** the learner can explain that `@retry(times=5)` is the same as `flaky_model = retry(times=5)(flaky_model)`.

## Stage 11: Async basics

**Concepts**: why async (waiting on the network), `async def` creates a coroutine, `await` pauses without blocking, `asyncio.run`, `asyncio.gather` for fan-out, `asyncio.Semaphore` to limit concurrency, never `time.sleep` inside async code.

```python
import asyncio
import time


async def fake_model(prompt: str, delay: float = 0.5) -> str:
    await asyncio.sleep(delay)            # stands in for a network call
    return f"answer to {prompt!r}"


async def main():
    prompts = ["a", "b", "c", "d"]
    limit = asyncio.Semaphore(2)          # at most 2 calls at once

    async def guarded(p):
        async with limit:
            return await fake_model(p)

    start = time.perf_counter()
    answers = await asyncio.gather(*(guarded(p) for p in prompts))
    print(answers, f"{time.perf_counter() - start:.1f}s")   # ~1.0s, not 2.0s


asyncio.run(main())
```

**Ready when** the learner can predict roughly how long the program takes with and without the semaphore.

## Stage 12: numpy and pandas

**Concepts**: arrays vs lists, vectorised maths, shapes, `axis`, dot product, normalisation; DataFrames, columns as Series, filtering with boolean masks, `groupby`, reading CSV/JSON.

```python
import numpy as np
import pandas as pd

a = np.array([0.1, 0.3, 0.5])
b = np.array([0.2, 0.1, 0.4])
cosine = a @ b / (np.linalg.norm(a) * np.linalg.norm(b))
print(round(float(cosine), 3))

evals = pd.DataFrame({
    "model": ["small", "small", "large", "large"],
    "question": ["q1", "q2", "q1", "q2"],
    "correct": [True, False, True, True],
})
print(evals.groupby("model")["correct"].mean())    # accuracy per model
```

**Ready when** the learner can explain why `[1, 2] * 2` and `np.array([1, 2]) * 2` differ.

## Stage 13: HTTP and calling an LLM API

**Concepts**: HTTP requests, JSON bodies, headers, status codes (200, 400, 401, 429, 500), API keys in environment variables (never in code or git), timeouts, retries on 429/5xx, provider SDKs vs raw HTTP, streaming.

```python
import os

import httpx

API_URL = os.environ.get("LLM_API_URL", "https://api.example.com/v1/chat")
API_KEY = os.environ["LLM_API_KEY"]          # export LLM_API_KEY=... in the shell, or a .env file


def ask(question: str, model: str = "small-model") -> str:
    payload = {"model": model, "messages": [{"role": "user", "content": question}], "max_tokens": 200}
    response = httpx.post(API_URL, json=payload, headers={"Authorization": f"Bearer {API_KEY}"}, timeout=30)
    response.raise_for_status()               # turns 4xx/5xx into an exception
    data = response.json()
    return data["choices"][0]["message"]["content"]   # the shape depends on the provider: print(data) first!
```

Teach the pattern, then switch to the provider's official SDK, which handles auth, retries and types. Always `print(data)` once to learn the response shape before indexing into it.

**Milestone**: a CLI chatbot that keeps history in a list of dicts, sends it each turn, and handles `KeyboardInterrupt` to exit cleanly.

**Ready when** the learner can explain what a 401 and a 429 mean and where the API key lives.

## Stage 14: Embeddings and a tiny RAG

**Concepts**: an embedding is a list of numbers representing meaning; similar texts have vectors pointing the same way (cosine similarity); chunking documents; retrieving top-k chunks; putting them in the prompt; evaluating answers.

Pure-Python version first, so nothing is magic (a bag-of-words "embedding" stands in for a real model):

```python
import math
import re
from collections import Counter


def embed(text: str) -> Counter:
    """Toy embedding: word counts. Replace with a real embedding model later."""
    return Counter(re.findall(r"[a-z]+", text.lower()))


def cosine(a: Counter, b: Counter) -> float:
    dot = sum(a[w] * b[w] for w in a)
    norm = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return dot / norm if norm else 0.0


notes = [
    "Python lists are ordered and mutable.",
    "Embeddings map text to vectors so similar meanings are close.",
    "A virtual environment isolates project dependencies.",
]
index = [(chunk, embed(chunk)) for chunk in notes]


def retrieve(question: str, k: int = 2) -> list:
    q = embed(question)
    ranked = sorted(index, key=lambda pair: cosine(q, pair[1]), reverse=True)
    return [chunk for chunk, _ in ranked[:k]]


question = "How do embeddings represent meaning?"
context = "\n".join(f"- {c}" for c in retrieve(question))
prompt = f"Answer using only this context:\n{context}\n\nQuestion: {question}"
print(prompt)       # send this to ask() from stage 13
```

Then upgrade step by step: real embeddings from an API or `sentence-transformers`, vectors in a numpy matrix (`scores = matrix @ q / norms`), chunking with overlap from stage 9, and finally a vector database.

**Ready when** the learner can explain each step of RAG in their own words and point to which earlier stage each line of code comes from.

## Capstone ideas

| Project | Uses stages |
|---------|-------------|
| Notes Q&A bot (RAG over a folder of Markdown files) | 6, 9, 13, 14 |
| Prompt A/B tester: same questions, two prompts, accuracy table | 4, 12, 13 |
| Structured extractor: emails -> JSON with validation and retries | 7, 8, 10, 13 |
| Parallel summariser with a concurrency limit | 9, 11, 13 |
| Eval harness: JSONL test cases, exact-match and keyword scoring, CSV report | 6, 7, 12 |
