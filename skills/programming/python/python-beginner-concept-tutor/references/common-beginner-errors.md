# Common Beginner Errors, Explained

How to read a traceback, then every error a beginner meets in the first months, with the exact message (Python 3.12/3.13 wording; older versions are terser), what it really means, the usual causes in AI-flavoured code, and the fix. When tutoring, give the "means" line and a hint first; give the fix after the learner has looked.

## Contents

- [Reading a traceback](#reading-a-traceback)
- [Quick lookup table](#quick-lookup-table)
- [SyntaxError](#syntaxerror)
- [IndentationError and TabError](#indentationerror-and-taberror)
- [NameError](#nameerror)
- [TypeError](#typeerror)
- [ValueError](#valueerror)
- [KeyError](#keyerror)
- [IndexError](#indexerror)
- [AttributeError, especially on None](#attributeerror-especially-on-none)
- [ModuleNotFoundError and virtual environment problems](#modulenotfounderror-and-virtual-environment-problems)
- [ImportError and circular imports](#importerror-and-circular-imports)
- [UnboundLocalError](#unboundlocalerror)
- [RecursionError](#recursionerror)
- [ZeroDivisionError](#zerodivisionerror)
- [FileNotFoundError and paths](#filenotfounderror-and-paths)
- [JSONDecodeError](#jsondecodeerror)
- [Errors with no traceback: silent bugs](#errors-with-no-traceback-silent-bugs)
- [Async errors](#async-errors)
- [Debugging routine to teach](#debugging-routine-to-teach)

## Reading a traceback

```
Traceback (most recent call last):
  File "/home/ada/bot/main.py", line 22, in <module>
    reply = ask(history)
            ^^^^^^^^^^^^
  File "/home/ada/bot/main.py", line 15, in ask
    return data["choices"][0]["message"]["content"]
           ~~~~^^^^^^^^^^^
KeyError: 'choices'
```

Teach this order:

1. **Bottom line first**: the error type (`KeyError`) and its message (`'choices'`): "the dict has no key `choices`".
2. **The frame just above**: file, line 15, function `ask`, and the code. The `~~~^^^` markers (3.11+) point at the exact sub-expression.
3. **Walk up** to see how execution got there: line 22 called `ask`.
4. **Ask "what value did Python have?"** Here: `print(data)` reveals `{"error": {"message": "invalid api key"}}`, so the real problem is authentication, not the indexing.
5. **Frames in library code** (`site-packages/...`) are rarely where the bug is; find the last frame in your own files.

"During handling of the above exception, another exception occurred" means a second error happened inside an `except` block. "The above exception was the direct cause of the following exception" comes from `raise ... from e`. Read both: the first is usually the root cause.

## Quick lookup table

| Error | Plain meaning | First thing to check |
|-------|---------------|----------------------|
| `SyntaxError` | Python can't read the code; nothing ran | Missing `:`, quote, bracket or comma at/just before the caret |
| `IndentationError` | Blocks don't line up | 4 spaces per level, no tabs, a body after every `:` |
| `NameError` | Unknown name | Typo, used before assignment, missing import, quotes forgotten |
| `TypeError` | Wrong type for the operation | `type(x)` of each value; argument count |
| `ValueError` | Right type, bad value | The actual value (`repr(x)`) |
| `KeyError` | Missing dict key | `print(d.keys())`, spelling, case |
| `IndexError` | Position doesn't exist | `len(x)` vs the index; empty list? |
| `AttributeError: 'NoneType'...` | A variable is `None` | Which function returned `None`? `x = x.sort()`? |
| `ModuleNotFoundError` | Package not installed in THIS Python | `sys.executable`, venv activated? |
| `UnboundLocalError` | Local name read before assignment | Assignment to that name later in the function |
| `RecursionError` | Function calls itself forever | Base case missing or not reached |
| `ZeroDivisionError` | Divided by 0 | Empty list, zero count, zero norm vector |
| `FileNotFoundError` | No file at that path | Current working directory, relative path |
| `JSONDecodeError` | Not valid JSON | Print the raw text: fences, chatter, truncation |

## SyntaxError

Python parses the whole file before running it, so a SyntaxError means **no line ran**, not even the ones above it.

```python
def greet(name)                 # SyntaxError: expected ':'
    print(f"Hi {name}")
```

| Message (3.10+) | Cause | Fix |
|-----------------|-------|-----|
| `expected ':'` | `if`/`for`/`def`/`class`/`else` line without colon | Add `:` |
| `'(' was never closed` | Missing `)`, `]` or `}` (often reported on the NEXT line) | Count brackets on the line above |
| `unterminated string literal` | Missing closing quote | Close it; use `"""` for multi-line text |
| `invalid syntax. Perhaps you forgot a comma?` | `["a" "b"]` style lists, dict literals | Add the comma |
| `invalid syntax. Maybe you meant '==' or ':=' instead of '='?` | `if x = 5:` | `==` to compare |
| `cannot assign to function call` | `len(x) = 3`, `f() = y` | Put the name on the left |
| `unmatched ')'` | Extra closing bracket | Remove it |
| `invalid character '“' (U+201C)` | Smart quotes pasted from a doc/chat | Retype as `"` |
| `'return' outside function` | `return` at module level or bad indentation | Indent into the function |
| `f-string: expecting '}'` | Unbalanced braces in an f-string | Double literal braces `{{ }}` |

AI-flavoured classic: pasting a JSON example into Python with `true`/`false`/`null` gives `NameError` (not SyntaxError) because Python spells them `True`/`False`/`None`. Use `json.loads('...')` on the JSON text instead.

## IndentationError and TabError

```python
for chunk in chunks:
print(chunk)                      # IndentationError: expected an indented block after 'for' statement on line 1

def score(x):
    if x > 0:
        return 1
      return 0                    # IndentationError: unindent does not match any outer indentation level
```

| Message | Fix |
|---------|-----|
| `expected an indented block after 'X' statement on line N` | Indent the body; use `pass` as a placeholder |
| `unexpected indent` | Remove extra leading spaces (common after copy-paste) |
| `unindent does not match any outer indentation level` | Line it up exactly with an outer block (count spaces) |
| `TabError: inconsistent use of tabs and spaces in indentation` | Configure the editor: "insert spaces", 4 per level; convert the file |

Teach: indentation IS the block structure. An `else` must align with its `if`; an `except` with its `try`. A line that is outdented ends the block, so a mis-indented `return` inside a loop returns after the first item:

```python
def total_tokens(chunks):
    total = 0
    for c in chunks:
        total += len(c.split())
        return total          # BUG: inside the loop, returns after the first chunk
```

## NameError

```
NameError: name 'respnse' is not defined. Did you mean: 'response'?
```

Causes:
- Typo (3.10+ suggests the right name).
- Used before assigned, e.g. a variable created only inside an `if` branch that didn't run, or in a cell you haven't run yet (Jupyter).
- Missing import: `name 'json' is not defined` -> `import json`.
- Forgot quotes: `model = gpt` instead of `model = "gpt"`.
- JSON literals: `true`, `false`, `null` -> `True`, `False`, `None`.
- Using a function's local variable outside the function.

## TypeError

The most varied error; read the message carefully.

| Message | Meaning | Fix |
|---------|---------|-----|
| `can only concatenate str (not "int") to str` | `"tokens: " + 42` | `f"tokens: {42}"` or `str(42)` |
| `unsupported operand type(s) for +: 'int' and 'str'` | `sum(["1", "2"])`, `count + input()` | Convert: `int(input())` |
| `'NoneType' object is not subscriptable` | `x[0]` where `x` is None | Find where `x` became None |
| `'int' object is not iterable` | `for i in len(items)` | `for i in range(len(items))` or `for item in items` |
| `'str' object does not support item assignment` | `text[0] = "H"` | Strings are immutable: `text = "H" + text[1:]` |
| `list indices must be integers or slices, not float` | `items[n / 2]` | `items[n // 2]` |
| `list indices must be integers or slices, not str` | Treating a list of dicts like a dict: `data["choices"]` when `data` is a list | Index first: `data[0]["choices"]`, print the structure |
| `string indices must be integers, not 'str'` | `msg["content"]` where `msg` is a JSON STRING not yet parsed | `json.loads(msg)` first |
| `f() missing 1 required positional argument: 'x'` | Called with too few args (or forgot `self` in a method) | Pass it, or add `self` |
| `f() takes 1 positional argument but 2 were given` | Method defined without `self` | `def f(self, x):` |
| `'str' object is not callable` | Shadowed a built-in: `str = "x"` then `str(5)`; or `text()` | Rename the variable |
| `'list' object is not callable` | `items(0)` instead of `items[0]`, or `list = [...]` earlier | Square brackets / rename |
| `unhashable type: 'list'` | List as dict key or set item | Use a tuple |
| `object of type 'generator' has no len()` | `len()` on a generator | `list(gen)` first, or count while iterating |
| `Object of type ndarray is not JSON serializable` | `json.dumps` on numpy arrays/floats | `.tolist()`, `float(x)` |

## ValueError

```python
int("3.5")                      # ValueError: invalid literal for int() with base 10: '3.5'
a, b = [1, 2, 3]                # ValueError: too many values to unpack (expected 2)
a, b, c = "ab".split()          # ValueError: not enough values to unpack (expected 3, got 2)
["a", "b"].index("z")           # ValueError: 'z' is not in list
import math; math.sqrt(-1)      # ValueError: math domain error
```

Fixes: inspect the actual value with `print(repr(x))` (it shows hidden spaces and newlines like `'42\n'`), validate before converting, use `str.partition` or `split(maxsplit=1)` when the number of parts varies.

## KeyError

```python
config = {"model": "small", "temperature": 0.2}
config["max_tokens"]            # KeyError: 'max_tokens'
```

Causes and fixes:
- Key genuinely optional -> `config.get("max_tokens", 256)`.
- Spelling or case (`"Temperature"`), trailing space in a key from a CSV header (`"model "`) -> `print(list(config))`.
- The API returned a different shape (an error object) -> print the whole response first.
- Counting -> `counts[w] = counts.get(w, 0) + 1` or `collections.Counter`.
- Grouping -> `collections.defaultdict(list)`.

## IndexError

```python
results = []
best = results[0]               # IndexError: list index out of range
```

Causes: empty list (no search results, empty file); off-by-one (`items[len(items)]`, `range(len(items) + 1)`); indexing the wrong level of a nested structure; deleting from a list while looping by index.

Fixes: check `if results:` before indexing; use `items[-1]` for the last item; iterate with `for item in items` instead of indexes; trace the loop to see the index on the failing step.

## AttributeError, especially on None

```
AttributeError: 'NoneType' object has no attribute 'strip'
```

It means a variable you expected to be a string/list/object is `None`. Ask "which function gave me None?":

| Cause | Example | Fix |
|-------|---------|-----|
| In-place method assigned | `items = items.sort()` / `.append()` / `.reverse()` | Call on its own line, or `items = sorted(items)` |
| Function without `return` | `def clean(t): t.strip()` | `return t.strip()` |
| `dict.get` / `re.match` / `find`-style lookups found nothing | `re.search(r"\d+", s).group()` | `m = re.search(...)`, then `if m:` |
| Print used as value | `msg = print(...)` | Build the value, then print it |
| Optional API field | `response.json().get("usage").get("total_tokens")` | Check each level or use `(... or {})` |

Other AttributeErrors: `'list' object has no attribute 'split'` (you have a list of strings, not a string: loop over it); `'str' object has no attribute 'append'` (strings are immutable); `module 'random' has no attribute 'choice'` (your file is named `random.py`); `'dict' object has no attribute 'content'` (use `msg["content"]`, not `msg.content`, unless the SDK returns objects).

## ModuleNotFoundError and virtual environment problems

```
ModuleNotFoundError: No module named 'httpx'
```

"The package is not installed **in the Python that is running this code**." The classic story: `pip install httpx` succeeded, the error persists, because `pip` belongs to a different Python than `python` (system vs venv vs conda vs the editor's interpreter).

Diagnose:

```bash
python -c "import sys; print(sys.executable)"   # which Python runs your code
python -m pip -V                                 # which Python pip installs into
python -m pip list | grep -i httpx              # is it there?
```

Fix:

```bash
source .venv/bin/activate          # or .venv\Scripts\activate on Windows
python -m pip install httpx        # ALWAYS python -m pip, so pip matches python
# with uv: uv add httpx && uv run main.py
```

Other causes:
- Package name differs from import name: `pip install scikit-learn` -> `import sklearn`; `pip install python-dotenv` -> `import dotenv`; `pip install beautifulsoup4` -> `import bs4`; `pip install pillow` -> `import PIL`; `pip install pyyaml` -> `import yaml`.
- Editor/Jupyter uses another interpreter: in VS Code "Python: Select Interpreter" -> `.venv`; in Jupyter `%pip install httpx` installs into the kernel's Python.
- Your own module: `ModuleNotFoundError: No module named 'utils'` when running from a different folder; run from the project root or use `python -m package.module`.
- `externally-managed-environment` error from pip (PEP 668, modern Linux/macOS Homebrew): create and activate a venv instead of installing globally.

## ImportError and circular imports

```
ImportError: cannot import name 'Client' from 'mylib' (/home/ada/bot/mylib.py)
ImportError: cannot import name 'build_prompt' from partially initialized module 'prompts' (most likely due to a circular import)
```

First: typo or version difference (the name moved in a newer release; check the installed version with `python -m pip show mylib`). Second: a file named like the library shadows it (`mylib.py` in your folder). Third: circular import: `a.py` imports `b.py` which imports `a.py`; move shared code into a third module or import inside the function.

## UnboundLocalError

```python
total_tokens = 0

def add(n):
    total_tokens += n          # UnboundLocalError: cannot access local variable 'total_tokens'
                               # where it is not associated with a value
```

Because the function assigns to `total_tokens`, Python decides at compile time that it is local for the whole function; `+=` reads it before any local value exists. Fix by passing and returning (`def add(total, n): return total + n`), using an object to hold state, or (last resort) `global total_tokens`. In nested functions use `nonlocal`.

## RecursionError

```
RecursionError: maximum recursion depth exceeded
```

A function keeps calling itself. Usual causes: missing base case, a base case that is never reached (`n - 1` on floats, wrong comparison), or recursing on the same input. Accidental recursion also happens with properties and `__getattr__` (`return self.name` inside the `name` property), and with `__repr__` of objects that reference each other. Fix the base case or use a loop; Python's default limit (~1000) is deliberately low.

```python
def flatten(items):
    out = []
    for x in items:
        if isinstance(x, list):
            out.extend(flatten(x))      # recursive case: smaller input
        else:
            out.append(x)               # base case: not a list
    return out

print(flatten([1, [2, [3, 4]], 5]))     # [1, 2, 3, 4, 5]
```

## ZeroDivisionError

`ZeroDivisionError: division by zero`. In AI code: average of an empty list of scores, accuracy with zero examples, cosine similarity with an all-zero vector (empty text embedding). Guard: `return dot / norm if norm else 0.0`, or `if not scores: return None`.

## FileNotFoundError and paths

```
FileNotFoundError: [Errno 2] No such file or directory: 'data/faq.json'
```

Relative paths are resolved from the **current working directory** (where you ran `python`), not from the script's folder. Fixes:

```python
from pathlib import Path

HERE = Path(__file__).resolve().parent          # folder containing this script
faq_path = HERE / "data" / "faq.json"
print(faq_path, faq_path.exists())               # debug: print the absolute path
```

On Windows, write paths with forward slashes or raw strings (`r"C:\new\data"`), because `"\n"` in a normal string is a newline. Related: `IsADirectoryError` (you passed a folder), `PermissionError` (file open in another program or no rights), `UnicodeDecodeError` (pass `encoding="utf-8"`).

## JSONDecodeError

```
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

"Expecting value at char 0" usually means the text is empty or is not JSON at all (an HTML error page, a model's prose). With model output also check: Markdown fences (```` ```json ````), single quotes (`{'a': 1}` is a Python repr, not JSON), trailing commas, truncated output because `max_tokens` was too low. Print `repr(raw)` first; then strip fences, extract from the first `{` to the last `}`, and ask the model for JSON mode / structured output where available.

## Errors with no traceback: silent bugs

These do not crash, which makes them worse. Teach them by tracing.

| Symptom | Cause | Fix |
|---------|-------|-----|
| Every call remembers old data | Mutable default argument `def f(history=[])` | `history=None` then create inside |
| Changing a copy changes the original | `b = a` is not a copy; nested copies are shallow | `a.copy()`, `copy.deepcopy(a)` |
| Grid rows change together | `[[0] * 3] * 3` | `[[0] * 3 for _ in range(3)]` |
| `if x == "a" or "b"` always true | Parsed as `(x == "a") or "b"` | `x in ("a", "b")` |
| Loop processes only some items | Removing from a list while iterating it | Build a new list |
| Function returns None | Missing `return`, or `return` inside the loop | Check indentation of `return` |
| `0.1 + 0.2 != 0.3` | Floating point | `math.isclose` |
| `"10" > "9"` is False | Comparing strings (alphabetical) | Convert with `int()` |
| `input()` maths gives "55" | `input()` returns str: `"5" + "5"` | `int(input())` |
| Generator is empty the second time | Iterators are single-use | Convert to a list if reused |
| `except: pass` hides everything | Swallowed exception | Catch specific errors, log them |

## Async errors

| Message | Meaning | Fix |
|---------|---------|-----|
| `RuntimeWarning: coroutine 'ask' was never awaited` | Called an async function without `await` | `await ask(...)` |
| `SyntaxError: 'await' outside async function` | `await` inside a normal `def` | Make it `async def`, or use `asyncio.run(...)` at the top |
| `RuntimeError: asyncio.run() cannot be called from a running event loop` | Jupyter already runs a loop | Use top-level `await main()` in the notebook |
| Program is no faster with async | Blocking calls inside coroutines (`time.sleep`, `requests`) | `asyncio.sleep`, `httpx.AsyncClient` |

## Debugging routine to teach

1. Read the last line of the traceback aloud in plain words.
2. Find the last frame in your own file; look at that exact line.
3. Ask "what were the values?" and print them with `print(f"{x=}, {type(x)=}")`, or run `scripts/explain_concepts.py trace snippet.py` on a small reproduction.
4. Make a 5-line reproduction: if it reproduces, you understand it; if not, the difference is the clue.
5. Change one thing, re-run, observe.
6. Afterwards, name the concept behind the bug (aliasing, scope, None from an in-place method) so it sticks.

Use `breakpoint()` (opens pdb: `n` next line, `s` step into, `p x` print, `c` continue, `q` quit) once the learner is comfortable with print debugging.
