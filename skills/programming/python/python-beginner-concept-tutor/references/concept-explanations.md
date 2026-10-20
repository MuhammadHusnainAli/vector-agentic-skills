# Concept Explanations

Ready-to-use explanations for every core concept on the path, in teaching order. Each entry has: **Definition** (one plain sentence), **Analogy**, **Example** (runnable, with outputs as comments), **Common mistakes**, and a **Quiz** with its answer. Adapt the wording to the learner; keep the example.

## Contents

Levels: L1 beginner, L2 elementary, L3 intermediate, L4 advanced.

- [Variables and assignment](#1-variables-and-assignment) (L1) · [Numbers and division](#2-numbers-and-division) (L1) · [Floating point](#3-floating-point) (L1) · [Strings and f-strings](#4-strings-and-f-strings) (L1)
- [Lists](#5-lists) (L1) · [Indexing, slicing and off-by-one](#6-indexing-slicing-and-off-by-one) (L1-2) · [Dictionaries](#7-dictionaries) (L1) · [Tuples and sets](#8-tuples-and-sets) (L2)
- [Mutable vs immutable, references and aliasing](#9-mutable-vs-immutable-references-and-aliasing) (L2) · [is vs ==](#10-is-vs-) (L2) · [if, elif, else and truthiness](#11-if-elif-else-and-truthiness) (L1) · [for loops, range, enumerate, zip](#12-for-loops-range-enumerate-zip) (L1-2)
- [while loops](#13-while-loops) (L1) · [Functions, parameters and return](#14-functions-parameters-and-return) (L1) · [Scope](#15-scope) (L2-3) · [Default arguments](#16-default-arguments) (L2)
- [Modules and import](#17-modules-and-import) (L2) · [Files and with](#18-files-and-with) (L2) · [Exceptions](#19-exceptions) (L2) · [Classes, objects and self](#20-classes-objects-and-self) (L3)
- [Comprehensions](#21-comprehensions) (L2-3) · [Iterators and generators](#22-iterators-and-generators) (L3) · [lambda and sorted(key=)](#23-lambda-and-sortedkey) (L3) · [Decorators](#24-decorators) (L3-4)
- [Type hints](#25-type-hints) (L3) · [Virtual environments, pip and uv](#26-virtual-environments-pip-and-uv) (L2) · [async and await](#27-async-and-await) (L4)

## 1. Variables and assignment

**Definition**: A variable is a name that refers to a value; `=` attaches the name on the left to the value on the right.

**Analogy**: A sticky-note label on a box. The box is the value; the label is the name. You can move a label to another box, and one box can carry several labels.

```python
model = "small-model"
max_tokens = 256
max_tokens = max_tokens + 44     # right side first (256 + 44), then the label moves to 300
print(model, max_tokens)          # small-model 300
```

**Common mistakes**
- Reading `=` as "equals". It means "make this name refer to". Comparison is `==`.
- Using a name before assigning it -> `NameError`.
- Naming variables after built-ins (`list = [...]`, `str = "x"`), which breaks `list()` and `str()` later.

**Quiz**: After `a = 5; b = a; a = 7`, what is `b`? **Answer**: 5. `b = a` labels the same 5; `a = 7` moves only the `a` label.

## 2. Numbers and division

**Definition**: `int` holds whole numbers of any size, `float` holds decimals; Python has three kinds of division.

**Analogy**: `/` is a calculator, `//` is "how many full boxes", `%` is "how many left over".

```python
print(7 / 2)     # 3.5   true division ALWAYS returns a float
print(8 / 2)     # 4.0   still a float
print(7 // 2)    # 3     floor division
print(-7 // 2)   # -4    floors toward minus infinity, not toward zero
print(7 % 2)     # 1     remainder: handy for "every other item"
batches = -(-103 // 32)   # ceiling division: 4 batches of 32 for 103 items
```

**Common mistakes**
- Using `/` for an index: `items[len(items) / 2]` -> `TypeError: list indices must be integers or slices, not float`.
- `2 ^ 3` is 1 (bitwise XOR), not 8; powers use `2 ** 3`.
- `int(3.9)` is 3 (truncates); use `round()` to round. `round(2.5)` is 2 (banker's rounding).

**Quiz**: How many batches of size 16 do 50 examples need, and how do you compute it? **Answer**: 4, `math.ceil(50 / 16)` or `-(-50 // 16)`.

## 3. Floating point

**Definition**: Floats are stored in binary, so most decimals (like 0.1) are tiny approximations.

**Analogy**: Writing 1/3 as 0.333333: close, never exact. Binary has the same problem with 1/10.

```python
import math

print(0.1 + 0.2)                     # 0.30000000000000004
print(0.1 + 0.2 == 0.3)              # False
print(math.isclose(0.1 + 0.2, 0.3))  # True
print(f"{0.1 + 0.2:.2f}")            # 0.30  format for display
from decimal import Decimal
print(Decimal("0.1") + Decimal("0.2"))   # 0.3  exact, for money
```

**Common mistakes**
- Testing similarity scores with `==` (`if score == 1.0`). Use a threshold: `if score >= 0.999`.
- Rounding before computing instead of only when displaying.

**Quiz**: Why can the cosine similarity of a vector with itself print `0.9999999999999998`? **Answer**: Each multiply, sum and square root rounds a little; compare with `math.isclose` or a tolerance.

## 4. Strings and f-strings

**Definition**: A string (`str`) is immutable text; an f-string fills `{expressions}` into text.

**Analogy**: A form letter with blanks; the f-string fills each blank with the current value.

```python
name, score = "Ada", 0.8734
print(f"{name} scored {score:.1%}")       # Ada scored 87.3%
print(f"{score=}")                        # score=0.8734  (3.8+, great for debugging)
text = "  Retrieval Augmented Generation  "
print(text.strip().lower().split())       # ['retrieval', 'augmented', 'generation']
print("-".join(["a", "b", "c"]))          # a-b-c
print(text.strip()[0:9])                  # Retrieval
```

**Common mistakes**
- `"Score: " + 0.87` -> `TypeError: can only concatenate str (not "float") to str`. Use an f-string.
- Expecting `text.upper()` to change `text`. Strings never change; methods return new strings: `text = text.upper()`.
- Forgetting the `f`: `"Hi {name}"` prints the braces literally.
- Using an f-string for a template that should be filled later; use `str.format` or a function instead.

**Quiz**: What does `"chunk".replace("c", "C")` return, and what is the value of the original string afterwards? **Answer**: `'Chunk'`; the original is still `'chunk'`.

## 5. Lists

**Definition**: A list is an ordered, changeable collection of items, written `[a, b, c]`.

**Analogy**: A numbered queue or a spreadsheet column: items keep their order and you can add, remove or replace them.

```python
messages = ["hi", "how are you?"]
messages.append("tell me about RAG")    # add at the end -> returns None
messages.insert(0, "SYSTEM: be brief")  # add at position 0
last = messages.pop()                   # remove and return the last item
print(len(messages), last)              # 3 tell me about RAG
scores = [0.2, 0.9, 0.5]
print(sorted(scores))                   # [0.2, 0.5, 0.9]  new list
scores.sort(reverse=True)               # sorts in place, returns None
print(scores)                           # [0.9, 0.5, 0.2]
```

**Common mistakes**
- `messages = messages.append(x)` -> `messages` becomes `None`.
- `list.sort()` vs `sorted(list)`: in-place vs new list.
- Removing items while looping over the same list skips items; build a new list instead.

**Quiz**: What is `[1, 2] + [3]` and what is `[1, 2] * 2`? **Answer**: `[1, 2, 3]` and `[1, 2, 1, 2]` (lists are not vectors; use numpy for element-wise maths).

## 6. Indexing, slicing and off-by-one

**Definition**: `x[i]` gets the item at position `i` (counting from 0); `x[a:b]` copies items from position `a` up to but not including `b`.

**Analogy**: Positions are the gaps between fence posts. `x[1:3]` cuts at gap 1 and gap 3, giving the two items in between.

```python
tokens = ["The", "cat", "sat", "on", "the", "mat"]
#          0      1      2      3     4      5      (-6 .. -1 from the end)
print(tokens[0], tokens[-1])      # The mat
print(tokens[1:3])                # ['cat', 'sat']
print(tokens[:3], tokens[3:])     # first 3 / the rest: never overlapping
print(tokens[::2])                # every second: ['The', 'sat', 'the']
print(tokens[::-1])               # reversed copy
print(tokens[4:100])              # ['the', 'mat']  slices never raise IndexError
print("embedding"[:5])            # 'embed'  strings slice the same way
window = 2
for i in range(len(tokens) - window + 1):     # +1 or you miss the last window
    print(tokens[i:i + window])
```

**Common mistakes**
- `tokens[len(tokens)]` -> `IndexError`; the last valid index is `len(tokens) - 1`.
- Expecting `range(1, 5)` to include 5.
- Sliding windows that miss the last window (forgetting `+ 1`) or overrun.

**Quiz**: `len(x[2:7])` when `x` has 10 items? **Answer**: 5 (`stop - start`).

## 7. Dictionaries

**Definition**: A dict maps unique keys to values; you look values up by key, not by position.

**Analogy**: A contact list (name -> number) or Excel's VLOOKUP table.

```python
config = {"model": "small-model", "temperature": 0.2}
config["max_tokens"] = 512                 # add or overwrite
print(config["model"])                     # small-model
print(config.get("seed"))                  # None, no crash
print(config.get("seed", 42))              # 42 (default)
for key, value in config.items():
    print(f"{key} = {value}")
counts = {}
for word in "the cat the mat".split():
    counts[word] = counts.get(word, 0) + 1
print(counts)                              # {'the': 2, 'cat': 1, 'mat': 1}
print("model" in config)                   # True: `in` checks KEYS
```

**Common mistakes**
- `config["Model"]` -> `KeyError: 'Model'` (case-sensitive).
- Expecting `value in config` to check values; use `value in config.values()`.
- Using a list as a key -> `TypeError: unhashable type: 'list'` (use a tuple).

**Quiz**: What does a model's JSON reply `{"label": "spam"}` become after `json.loads`, and how do you read the label safely? **Answer**: A dict; `data.get("label", "unknown")`.

## 8. Tuples and sets

**Definition**: A tuple is an ordered collection that cannot change; a set is an unordered collection of unique items.

**Analogy**: A tuple is a sealed envelope (a fixed record like coordinates); a set is a bag of distinct marbles.

```python
point = (3, 4)
x, y = point                       # unpacking
best = max([("doc1", 0.7), ("doc2", 0.9)], key=lambda pair: pair[1])
print(best)                        # ('doc2', 0.9)
seen_ids = set()
for doc_id in ["a", "b", "a", "c"]:
    if doc_id in seen_ids:         # fast membership test
        continue
    seen_ids.add(doc_id)
print(sorted(seen_ids))            # ['a', 'b', 'c']
print({1, 2, 3} & {2, 3, 4})       # {2, 3} intersection
empty = set()                      # {} is an empty DICT
```

**Common mistakes**
- `(5)` is just 5; `(5,)` is a tuple.
- `{}` creates a dict, not a set.
- Expecting a set to keep insertion order or allow indexing (`s[0]` -> `TypeError`).

**Quiz**: Fastest way to drop duplicate chunks while keeping their order? **Answer**: `list(dict.fromkeys(chunks))`.

## 9. Mutable vs immutable, references and aliasing

**Definition**: Mutable objects (list, dict, set, most objects) can change in place; immutable ones (int, float, str, tuple, None) cannot. Assignment never copies: it adds another name for the same object.

**Analogy**: Two people holding strings tied to the same balloon. If one paints the balloon, the other sees paint. If one lets go and grabs a new balloon, the other's balloon is unchanged.

```python
history = ["system: be brief"]
same = history                 # alias: one list, two names
same.append("user: hi")
print(history)                 # ['system: be brief', 'user: hi']
print(same is history)         # True

copy = history.copy()          # or list(history) or history[:]
copy.append("user: bye")
print(len(history), len(copy)) # 2 3

text = "hi"
other = text
other += "!"                   # strings are immutable: += builds a NEW string
print(text, other)             # hi hi!

nested = [[0, 0]] * 3          # THREE references to ONE inner list
nested[0][0] = 1
print(nested)                  # [[1, 0], [1, 0], [1, 0]]
grid = [[0, 0] for _ in range(3)]   # three separate lists
import copy as copy_module
deep = copy_module.deepcopy(grid)   # copies inner lists too
```

Function arguments work the same way: the function receives a reference, so `def add(msgs): msgs.append(...)` changes the caller's list, while `msgs = [...]` inside the function only moves the local name.

**Common mistakes**
- Thinking `b = a` copies a list or dict.
- Shallow copies of nested structures: `config.copy()` shares the inner dicts.
- Mutating a function's input unexpectedly (return a new list instead, or document it).

**Quiz**: `a = [1, 2]; b = a; b = b + [3]`. What is `a`? **Answer**: `[1, 2]`. `b + [3]` builds a new list and `b` moves to it. (With `b += [3]`, `a` would change too, because `+=` on a list mutates in place.)

## 10. is vs ==

**Definition**: `==` asks "do these have equal values?"; `is` asks "are these the exact same object?".

**Analogy**: Two copies of the same book are `==`; your copy and the one in your hand right now `is` the same book.

```python
a = [1, 2]
b = [1, 2]
print(a == b, a is b)     # True False
c = a
print(c is a)             # True
result = None
if result is None:        # the one place to use `is`: None (and True/False sentinels)
    print("no result yet")
```

**Common mistakes**
- `if x is 5:` or `if name is "Ada":` sometimes works because of interning or caching, then fails on other values. Python 3.8+ warns: `SyntaxWarning: "is" with a literal`.
- `== None` instead of `is None` (works, but numpy arrays and custom `__eq__` can surprise you).

**Quiz**: Why can `x = 1000; y = 1000; x is y` give different results in the REPL and in a file? **Answer**: Whether equal ints share one object is an implementation detail; never rely on it.

## 11. if, elif, else and truthiness

**Definition**: `if` runs a block only when its condition is true; `elif` adds more conditions checked in order; `else` catches everything else.

**Analogy**: A decision flowchart; you take the first arrow whose question is answered "yes".

```python
def label(score):
    if score >= 0.8:
        return "relevant"
    elif score >= 0.5:          # only checked when score < 0.8
        return "maybe"
    else:
        return "irrelevant"

print(label(0.9), label(0.6), label(0.1))   # relevant maybe irrelevant
docs = []
if not docs:                     # empty list, "", 0, None are all falsy
    print("no documents retrieved")
```

**Common mistakes**
- `if x == "a" or "b":` is always true (it is `(x == "a") or "b"`). Write `if x in ("a", "b"):`.
- Missing colon or wrong indentation after `if`.
- Order of `elif`s: put the most specific condition first.

**Quiz**: What does `label(0.8)` return? **Answer**: `"relevant"` (`>=` includes 0.8).

## 12. for loops, range, enumerate, zip

**Definition**: A `for` loop runs its block once for each item of an iterable, binding the item to a name.

**Analogy**: Going down a spreadsheet column, doing the same thing to each cell.

```python
questions = ["What is RAG?", "What is a token?"]
answers = ["Retrieval...", "A piece of text..."]

for q in questions:
    print(q)
for i, q in enumerate(questions, start=1):    # index and item
    print(f"{i}. {q}")
for q, a in zip(questions, answers):          # walk two lists together
    print(f"Q: {q} A: {a}")
for i in range(0, 10, 3):                     # 0 3 6 9
    print(i, end=" ")
```

**Common mistakes**
- `for i in range(len(xs)): x = xs[i]` where `for x in xs` or `enumerate` is clearer.
- `zip` silently stops at the shortest list (use `zip(a, b, strict=True)` in 3.10+ to catch mismatches).

**Quiz**: What is printed by `for i in range(3): pass` then `print(i)`? **Answer**: 2. The loop variable keeps its last value.

## 13. while loops

**Definition**: A `while` loop repeats its block as long as its condition is true.

**Analogy**: "Keep stirring while the sauce is lumpy": you must check, and something must change.

```python
attempts = 0
success = False
while not success and attempts < 3:
    attempts += 1
    success = attempts == 2           # pretend the second API call works
    print(f"attempt {attempts}: {'ok' if success else 'failed'}")
```

**Common mistakes**
- Forgetting to update the variable in the condition -> infinite loop (stop with Ctrl+C).
- Using `while` when a `for` over a known collection is simpler.

**Quiz**: How many times does `n = 10` / `while n > 0: n -= 3` run? **Answer**: 4 (10, 7, 4, 1).

## 14. Functions, parameters and return

**Definition**: A function is a named, reusable block of code; parameters are its inputs and `return` sends its output back.

**Analogy**: A recipe card: ingredients in (parameters), dish out (return value). Reading the card does nothing until someone cooks it (calls it).

```python
def count_tokens(text):
    """Very rough: one token per word."""
    return len(text.split())

def fits(text, budget=100):
    return count_tokens(text) <= budget

n = count_tokens("Embeddings capture meaning")   # call: run it and keep the result
print(n, fits("hi " * 150), fits("hi", budget=1))   # 3 False True
```

**Common mistakes**
- Printing instead of returning; the caller gets `None`.
- Forgetting the parentheses: `count_tokens` is the function itself, `count_tokens(x)` calls it.
- Code after `return` never runs.
- Wrong number of arguments -> `TypeError: count_tokens() missing 1 required positional argument: 'text'`.

**Quiz**: What does `def f(): print("hi")` then `x = f()` store in `x`? **Answer**: `None`, after printing `hi`.

## 15. Scope

**Definition**: Scope is where a name is visible. Names assigned inside a function are local to that call; functions can read names from outside but not rebind them without `global`/`nonlocal`.

**Analogy**: Each function call gets its own scratch notepad; it can read the whiteboard on the wall (globals) but writes go on its own notepad.

```python
MODEL = "small-model"          # global (module level)

def describe():
    return f"using {MODEL}"    # reading a global: fine

calls = 0
def track():
    global calls               # needed to REBIND the global
    calls += 1

def broken():
    print(calls)               # UnboundLocalError: `calls` is assigned below,
    calls = 5                  # so it is local for the WHOLE function

track(); track()
print(describe(), calls)       # using small-model 2
```

**Common mistakes**
- The `UnboundLocalError` above. Fix by passing values in and returning them out.
- Expecting a variable created inside a function to exist after the call.

**Quiz**: Better design than `global calls`? **Answer**: Return the new value (`calls = track(calls)`) or keep state in an object.

## 16. Default arguments

**Definition**: A parameter with `=value` is optional; the default is evaluated ONCE, when `def` runs.

```python
def add_turn(text, history=None):     # correct pattern for mutable defaults
    if history is None:
        history = []
    history.append(text)
    return history

def bad_add_turn(text, history=[]):   # one shared list for every call!
    history.append(text)
    return history

print(bad_add_turn("a"), bad_add_turn("b"))   # ['a', 'b'] ['a', 'b']
print(add_turn("a"), add_turn("b"))           # ['a'] ['b']
```

**Analogy**: A shared notebook left at the front desk: everyone who doesn't bring their own writes in the same one.

**Common mistakes**: `[]`, `{}`, `set()` or `datetime.now()` as defaults; defaults before required parameters (`def f(a=1, b)` is a SyntaxError).

**Quiz**: Why is `def log(msg, when=time.time())` buggy? **Answer**: The time is computed once at definition; every call reuses it.

## 17. Modules and import

**Definition**: A module is a `.py` file; `import` runs it once and gives you access to its names.

**Analogy**: Borrowing a toolbox from a shelf; `from toolbox import hammer` takes just the hammer.

```python
import json                          # whole module: json.dumps
from pathlib import Path             # one name
from collections import Counter as C # alias
import math

print(math.sqrt(16), C("aab").most_common(1), Path("notes") / "a.md")
```

A file can be both a module and a script:

```python
def main():
    print("running as a script")

if __name__ == "__main__":     # True only when run directly, not when imported
    main()
```

**Common mistakes**: naming your file `json.py`, `random.py`, `openai.py` or `numpy.py` (it shadows the real module); installing a package into a different Python than the one running the code (see errors reference).

**Quiz**: Why does `import random` then `random.choice(...)` fail with `AttributeError` in a file called `random.py`? **Answer**: The file imports itself instead of the standard library module.

## 18. Files and with

**Definition**: `open()` gives a file object; `with` guarantees the file is closed even if an error happens.

**Analogy**: `with` is a door that closes behind you automatically.

```python
from pathlib import Path

path = Path("prompts.txt")
with open(path, "w", encoding="utf-8") as f:     # "w" overwrites, "a" appends
    f.write("Summarise:\nTranslate:\n")
with open(path, encoding="utf-8") as f:
    for line in f:                               # line by line, keeps the "\n"
        print(line.rstrip("\n"))
print(path.read_text(encoding="utf-8").splitlines())   # ['Summarise:', 'Translate:']
```

**Common mistakes**: forgetting `encoding="utf-8"` (Windows defaults differ); opening with `"w"` and wiping a file you meant to read; relative paths resolve from the current working directory, not the script's folder (`Path(__file__).parent / "data.json"`).

**Quiz**: What is the difference between `f.read()` and iterating `for line in f`? **Answer**: `read()` loads the whole file into one string; iterating streams one line at a time (better for big files).

## 19. Exceptions

**Definition**: An exception is Python's way of saying "I can't continue"; `try`/`except` lets you handle specific ones.

**Analogy**: A smoke alarm. You want specific alarms in specific rooms, not one that you silence forever.

```python
import json

raw = '{"answer": 42'                       # truncated model output
try:
    data = json.loads(raw)
except json.JSONDecodeError as e:
    print(f"bad JSON at position {e.pos}: {e.msg}")
    data = {}
else:
    print("parsed fine")                    # runs only if no exception
finally:
    print("done")                           # always runs

def set_temperature(t):
    if not 0 <= t <= 2:
        raise ValueError(f"temperature must be between 0 and 2, got {t}")
    return t
```

**Common mistakes**: bare `except:` or `except Exception: pass` hiding real bugs; wrapping a huge block in one `try`; catching an error you can't handle instead of letting it surface.

**Quiz**: Which error does `int("3.5")` raise and how would you convert it? **Answer**: `ValueError`; `int(float("3.5"))` or `round(float(...))`.

## 20. Classes, objects and self

**Definition**: A class is a blueprint; each object made from it has its own data (attributes) and shares the class's functions (methods).

**Analogy**: A cookie cutter (class) and cookies (objects). `self` means "this particular cookie".

```python
class ChatSession:
    def __init__(self, system_prompt):          # runs when you create one
        self.system_prompt = system_prompt      # attribute stored on THIS object
        self.turns = []

    def add(self, role, text):                  # self is passed automatically
        self.turns.append((role, text))

    def __repr__(self):
        return f"ChatSession({len(self.turns)} turns)"

a = ChatSession("be brief")
b = ChatSession("be detailed")
a.add("user", "hi")                             # same as ChatSession.add(a, "user", "hi")
print(a, b)                                     # ChatSession(1 turns) ChatSession(0 turns)
```

**Common mistakes**: forgetting `self` as the first parameter (`TypeError: add() takes 2 positional arguments but 3 were given`); forgetting `self.` when storing an attribute (it becomes a local variable that disappears); mutable class attributes (`turns = []` at class level) shared by every object.

**Quiz**: Why does every new `ChatSession` start with an empty `turns`? **Answer**: `__init__` creates a new list for each object.

## 21. Comprehensions

**Definition**: A comprehension builds a list, dict or set from a loop in one expression: `[expression for item in iterable if condition]`.

**Analogy**: A recipe in one sentence: "for every chunk that is long enough, give me its first 30 characters".

```python
chunks = ["Python is fun.", "", "Embeddings are vectors.", "  "]
clean = [c.strip() for c in chunks if c.strip()]
lengths = {c: len(c) for c in clean}
first_words = {c.split()[0].lower() for c in clean}
print(clean, lengths, first_words, sep="\n")

# The same as a loop:
clean_loop = []
for c in chunks:
    if c.strip():
        clean_loop.append(c.strip())
```

**Common mistakes**: cramming nested logic into one unreadable line; using a comprehension only for side effects (`[print(x) for x in xs]`); confusing filter position (`if` at the end) with the ternary (`a if cond else b` at the start).

**Quiz**: Rewrite `[x * 2 for x in nums if x > 0]` as a loop. **Answer**: `out = []`, `for x in nums:`, `if x > 0:`, `out.append(x * 2)`.

## 22. Iterators and generators

**Definition**: An iterator hands out items one at a time with `next()`; a generator function uses `yield` to create one, pausing between items.

**Analogy**: A Pez dispenser: one candy per press, and when it is empty it is empty.

```python
def stream_tokens(text):
    for word in text.split():
        yield word                 # pause here, hand out word, resume on next()

gen = stream_tokens("tokens arrive one by one")
print(next(gen), next(gen))        # tokens arrive
print(list(gen))                   # ['one', 'by', 'one']  the rest
print(list(gen))                   # []  exhausted: generators are single-use

total = sum(len(w) for w in "a bb ccc".split())   # generator expression, no list built
print(total)                       # 6
```

**Common mistakes**: looping over a generator twice; expecting `len()` on a generator; forgetting that calling a generator function runs nothing until iterated.

**Quiz**: Why do LLM streaming APIs return iterators instead of a full string? **Answer**: So you can show each piece as it arrives instead of waiting for the whole response.

## 23. lambda and sorted(key=)

**Definition**: `lambda args: expression` makes a small unnamed function, usually passed to another function.

```python
results = [("doc_a", 0.71), ("doc_b", 0.93), ("doc_c", 0.42)]
top = sorted(results, key=lambda pair: pair[1], reverse=True)
print(top[0])                         # ('doc_b', 0.93)
```

**Analogy**: A sticky note with a one-line instruction ("sort by the score") handed to `sorted`.

**Common mistakes**: assigning lambdas to names (`f = lambda x: ...`; use `def`); `key=lambda x: x[1]()` vs the value; late binding in loops (`[lambda: i for i in range(3)]` all return 2).

**Quiz**: How do you sort chat messages by length, shortest first? **Answer**: `sorted(messages, key=len)`.

## 24. Decorators

**Definition**: A decorator is a function that takes a function and returns a new function with extra behaviour; `@name` above `def` applies it.

**Analogy**: Gift-wrapping: the present (function) is unchanged inside, but the wrapping adds something on the way in and out.

```python
import functools
import time

def timed(fn):
    @functools.wraps(fn)                      # keep the original name and docstring
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = fn(*args, **kwargs)
        print(f"{fn.__name__} took {time.perf_counter() - start:.3f}s")
        return result
    return wrapper

@timed                                        # same as: embed = timed(embed)
def embed(text):
    return [len(w) for w in text.split()]

print(embed("decorators wrap functions"))
```

**Common mistakes**: forgetting to `return result` in the wrapper (the function now returns `None`); forgetting `return wrapper`; writing `@timed()` for a decorator that takes no arguments.

**Quiz**: What does `functools.lru_cache` do when used as a decorator on an embedding function? **Answer**: Remembers results for arguments seen before, so repeated texts are not re-embedded.

## 25. Type hints

**Definition**: Annotations that document what types a function expects and returns; tools (mypy, pyright, your editor) check them, Python itself does not.

```python
def top_k(scores: dict[str, float], k: int = 3) -> list[str]:   # 3.9+ built-in generics
    return sorted(scores, key=scores.get, reverse=True)[:k]

def find(name: str, docs: list[str]) -> str | None:              # 3.10+ union syntax
    return next((d for d in docs if name in d), None)

print(top_k({"a": 0.1, "b": 0.9, "c": 0.5}, k=2))   # ['b', 'c']
# top_k("oops") is NOT stopped by the hint: Python calls it and it fails inside
# (AttributeError: 'str' object has no attribute 'get'). A type checker flags it before running.
```

**Common mistakes**: believing hints validate input at runtime (use pydantic for that); `list[str]` on 3.8 (needs `from __future__ import annotations` or `typing.List`); hints that lie.

**Quiz**: Will `top_k({"a": "high"})` be rejected because of the hint `dict[str, float]`? **Answer**: No. Python ignores hints at runtime; it fails or not based only on what the code does (here `sorted` compares strings and returns `['a']`). A type checker (mypy, pyright) would flag it before running.

## 26. Virtual environments, pip and uv

**Definition**: A virtual environment is a project-private folder with its own Python packages, so projects don't break each other.

**Analogy**: A separate toolbox per project; upgrading the drill in one doesn't change the others.

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install "httpx>=0.27" numpy
python -m pip freeze > requirements.txt
deactivate
# uv: one tool for Python versions, venvs and packages
uv venv --python 3.12 && uv pip install -r requirements.txt
uv init app && cd app && uv add httpx && uv run main.py
```

**Common mistakes**: `pip install` going to a different Python than `python` (always `python -m pip`); committing `.venv/` to git; forgetting to activate in a new terminal; the editor using a different interpreter (select `.venv` in VS Code).

**Quiz**: How do you check which Python and site-packages your code uses? **Answer**: `python -c "import sys; print(sys.executable)"` and `python -m pip -V`.

## 27. async and await

**Definition**: `async def` defines a coroutine that can pause at `await` while waiting (e.g. on the network) so other coroutines run meanwhile.

**Analogy**: A chef with several pots: while one simmers (waiting), they chop for another instead of staring at the first.

```python
import asyncio

async def call_model(prompt: str) -> str:
    await asyncio.sleep(1)                 # pretend network wait
    return prompt.upper()

async def main():
    results = await asyncio.gather(call_model("a"), call_model("b"), call_model("c"))
    print(results)                         # ['A', 'B', 'C'] after ~1s, not 3s

asyncio.run(main())
```

**Common mistakes**: calling `call_model("a")` without `await` (you get a coroutine object and a "never awaited" warning); using `time.sleep` or `requests` inside async code (blocks everything; use `asyncio.sleep`, `httpx.AsyncClient`); calling `asyncio.run` inside Jupyter (use top-level `await` there).

**Quiz**: Three 1-second calls with `gather`: roughly how long? With a `for` loop of `await`s? **Answer**: About 1 second; about 3 seconds.
