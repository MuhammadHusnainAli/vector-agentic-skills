#!/usr/bin/env python3
"""List the Python concepts a snippet uses, or step through it like Python Tutor.

Two modes:

  concepts (default)  Static analysis with `ast`. Lists every Python concept the
                      code uses (60+ detected: assignment, f-strings, slicing,
                      loops, functions, *args, comprehensions, generators,
                      classes, decorators, async, walrus, match, ...) with line
                      numbers, a difficulty level (1 beginner .. 4 advanced) and
                      a one-sentence plain-English explanation, ordered easiest
                      first so it doubles as a reading/learning order. Also
                      flags beginner pitfalls (mutable default argument,
                      `is` with a literal, `x = x.sort()`, range(len(x)), ...)
                      with a suggested fix. NEVER runs the code.

  trace               EXECUTES the snippet (it really runs it, in this Python
                      process) under sys.settrace and prints a step table:
                      line number, source line and the local variables that
                      changed, with print() output shown inline and the
                      exception plus its line if one is raised. Only run small
                      beginner snippets you trust: files over 200 lines are
                      refused, execution stops after --max-steps line events
                      (default 500) and after --timeout seconds (POSIX only).
                      input() reads from --input text, never from the terminal.

Usage:
    python explain_concepts.py lesson.py                      # concepts mode
    python explain_concepts.py concepts lesson.py --level 3   # only level 3+
    python explain_concepts.py concepts lesson.py --max-level 2 --strict
    cat lesson.py | python explain_concepts.py concepts - --json
    python explain_concepts.py trace snippet.py
    python explain_concepts.py trace snippet.py --max-steps 200 --input "Ada"
    python explain_concepts.py trace - --json < snippet.py

Exit codes:
    0  ok (in trace mode also when the snippet raised: explaining errors is the point)
    1  concepts --strict: a beginner pitfall was found, or a concept is above --max-level
       trace --strict: the snippet raised an exception or hit the step limit
    2  usage error, unreadable file, file too long for trace, or a SyntaxError
       (shown with a caret and a beginner-friendly explanation)

Standard library only. Python 3.9+.
"""

import argparse
import ast
import builtins
import io
import json
import os
import re
import signal
import sys
import textwrap

LEVEL_NAMES = {1: "beginner", 2: "elementary", 3: "intermediate", 4: "advanced"}

# id: (title, level, plain-English explanation)
CONCEPTS = {
    "assignment": ("assignment", 1, "`name = value` sticks a name label on a value so you can use it later."),
    "number": ("numbers (int / float)", 1, "Whole numbers are int, numbers with a decimal point are float; floats are approximate."),
    "string": ("string literal", 1, "Text in quotes is a str; single or double quotes mean the same thing."),
    "bool-none": ("True / False / None", 1, "True and False are the two booleans; None means 'no value here'."),
    "arithmetic": ("arithmetic operators", 1, "+ - * / ** do maths; `/` always gives a float, even 4 / 2 == 2.0."),
    "augmented-assignment": ("augmented assignment (+=)", 1, "`x += 1` is shorthand for `x = x + 1`."),
    "f-string": ("f-string", 1, "f\"Hi {name}\" builds a string by dropping the value of each {expression} into the text."),
    "list-literal": ("list", 1, "[a, b, c] is an ordered, changeable (mutable) collection; positions start at 0."),
    "dict-literal": ("dictionary", 1, "{key: value} maps keys to values, like a word to its definition."),
    "indexing": ("indexing", 1, "seq[0] is the first item and seq[-1] the last; a missing position raises IndexError."),
    "comparison": ("comparison", 1, "== != < > <= >= compare two values and give True or False."),
    "boolean-ops": ("and / or / not", 1, "Combine conditions; `and` needs both true, `or` needs at least one, `not` flips."),
    "if": ("if statement", 1, "Runs the indented block only when the condition is true."),
    "elif": ("elif", 1, "'else if': checked only when every condition above it was false."),
    "else": ("else", 1, "The block that runs when none of the if/elif conditions were true."),
    "for": ("for loop", 1, "Runs the indented block once for each item in a collection, naming the current item."),
    "while": ("while loop", 1, "Repeats the block as long as the condition stays true; make sure something changes."),
    "range": ("range()", 1, "range(n) counts 0, 1, ..., n-1: it stops BEFORE n."),
    "call": ("calling a function", 1, "name(arguments) runs a function and gives back its result."),
    "print": ("print()", 1, "Shows values on the screen; it returns None, so don't assign its result."),
    "len": ("len()", 1, "Counts the items in a string, list, dict or other collection."),
    "function-def": ("defining a function", 1, "`def name(params):` packages steps under a name so you can reuse them."),
    "return": ("return", 1, "Sends a value back to the caller and ends the function; no return means None."),
    "pass": ("pass", 1, "A placeholder that does nothing, used where Python needs a block."),
    "tuple-literal": ("tuple", 2, "(a, b) is an ordered collection that cannot be changed (immutable)."),
    "set-literal": ("set", 2, "{a, b} holds unique items with no order; great for 'have I seen this?' checks."),
    "slicing": ("slicing", 2, "seq[start:stop:step] copies a range of items; stop is NOT included."),
    "unpacking": ("tuple unpacking", 2, "`a, b = pair` splits a collection into several names in one go."),
    "floor-mod": ("// and %", 2, "`//` divides and rounds down to a whole number, `%` gives the remainder."),
    "comparison-chain": ("chained comparison", 2, "`0 <= x < 10` means `0 <= x and x < 10`."),
    "membership": ("in / not in", 2, "`x in collection` asks 'is x one of the items (or keys)?'."),
    "identity": ("is / is not", 2, "`is` asks 'same object in memory?', not 'equal value?'; use it for None."),
    "ternary": ("conditional expression", 2, "`a if condition else b` picks one of two values in a single expression."),
    "enumerate": ("enumerate()", 2, "Gives (position, item) pairs so you get the index without range(len(...))."),
    "zip": ("zip()", 2, "Walks several collections side by side, pairing their items up."),
    "break-continue": ("break / continue", 2, "`break` leaves the loop now; `continue` skips to the next round."),
    "dict-items": ("looping over a dict", 2, ".items() gives (key, value) pairs; looping a dict directly gives keys."),
    "method-call": ("methods (obj.method())", 2, "A function that belongs to a value, e.g. text.upper() or items.append(x)."),
    "keyword-args": ("keyword arguments", 2, "f(x, sep=', ') names an argument so order doesn't matter and intent is clear."),
    "default-args": ("default parameter values", 2, "`def f(x, n=3)` lets callers skip n; the default is created ONCE."),
    "docstring": ("docstring", 2, "A string right under def/class that documents what it does; help() shows it."),
    "import": ("import", 2, "Loads code from another module (standard library or pip-installed) so you can use it."),
    "main-guard": ("if __name__ == \"__main__\"", 2, "Runs that block only when the file is executed directly, not when imported."),
    "list-comprehension": ("list comprehension", 2, "[expr for x in items if cond] builds a new list in one line."),
    "try-except": ("try / except", 2, "Runs risky code and catches a specific error type instead of crashing."),
    "raise": ("raise", 2, "Signals an error on purpose so the caller must deal with it."),
    "with": ("with (context manager)", 2, "Sets something up and guarantees clean-up, e.g. closing a file even on error."),
    "open": ("open() / files", 2, "Opens a file for reading ('r') or writing ('w'); use it inside `with`."),
    "assert": ("assert", 2, "Crashes with AssertionError if the condition is false; a sanity check, not validation."),
    "del": ("del", 2, "Removes a name, a list position or a dict key."),
    "loop-else": ("for/while ... else", 3, "The else block runs only if the loop finished without hitting break."),
    "keyword-only": ("keyword-only parameters", 3, "Parameters after `*` must be passed by name: f(x, *, retries=3)."),
    "star-args": ("*args", 3, "Collects any extra positional arguments into a tuple."),
    "star-kwargs": ("**kwargs", 3, "Collects any extra keyword arguments into a dict."),
    "call-unpacking": ("unpacking into a call (*x, **d)", 3, "f(*items, **options) spreads a list/dict out into separate arguments."),
    "star-assign": ("extended unpacking (a, *rest)", 3, "`first, *rest = items` puts the leftovers in a list."),
    "lambda": ("lambda", 3, "A tiny unnamed function written inline, often as key= for sorted()."),
    "closure": ("nested function / closure", 3, "A function defined inside another can remember the outer function's variables."),
    "recursion": ("recursion", 3, "A function that calls itself on a smaller problem; it needs a base case to stop."),
    "global-nonlocal": ("global / nonlocal", 3, "Lets a function rebind a variable from module or enclosing scope; use sparingly."),
    "dict-comprehension": ("dict comprehension", 3, "{k: v for ...} builds a dictionary in one expression."),
    "set-comprehension": ("set comprehension", 3, "{x for ...} builds a set of unique values in one expression."),
    "generator-expression": ("generator expression", 3, "(x for x in items) produces values lazily, one at a time, without a list."),
    "yield": ("yield / generator function", 3, "A function with yield hands out values one by one and pauses in between."),
    "class": ("class", 3, "A blueprint for creating objects that bundle data (attributes) and behaviour (methods)."),
    "init-self": ("__init__ and self", 3, "__init__ fills in a new object; self is the object the method is working on."),
    "inheritance": ("inheritance", 3, "class Child(Parent) reuses the parent's methods and can override some of them."),
    "super": ("super()", 3, "Calls the parent class's version of a method, usually super().__init__(...)."),
    "dunder": ("special (dunder) methods", 3, "Methods like __repr__, __len__, __eq__ let your objects work with built-in syntax."),
    "decorator": ("decorator (@)", 3, "@something above a def wraps the function to add behaviour (logging, caching, ...)."),
    "property": ("@property", 3, "Lets a method be read like an attribute: obj.area instead of obj.area()."),
    "dataclass": ("@dataclass", 3, "Auto-writes __init__, __repr__ and __eq__ for a class that mainly holds data."),
    "static-class-method": ("@staticmethod / @classmethod", 3, "Methods that don't need the instance (static) or receive the class (classmethod)."),
    "type-hints": ("type hints", 3, "`def f(x: int) -> str` documents expected types; Python does not enforce them at runtime."),
    "finally": ("finally", 3, "Runs no matter what, error or not; used for clean-up."),
    "try-else": ("try ... else", 3, "Runs only if the try block raised nothing."),
    "custom-exception": ("custom exception class", 3, "class MyError(Exception) creates your own error type that callers can catch."),
    "positional-only": ("positional-only parameters (/)", 4, "Parameters before `/` cannot be passed by name (3.8+)."),
    "yield-from": ("yield from", 4, "Hands out every value of another generator before continuing."),
    "raise-from": ("raise ... from", 4, "Raises a new error while recording the original cause in the traceback."),
    "walrus": ("walrus operator (:=)", 4, "`if (n := len(x)) > 10:` assigns and tests in one expression (3.8+)."),
    "match": ("match / case", 4, "Structural pattern matching: compare a value against shapes and pull parts out (3.10+)."),
    "async-def": ("async def (coroutine)", 4, "Defines a coroutine that can pause at await so other work runs meanwhile."),
    "await": ("await", 4, "Pauses this coroutine until the awaited result is ready, without blocking the program."),
    "async-for-with": ("async for / async with", 4, "Loop or manage resources whose steps are themselves awaitable."),
    "except-star": ("except* (exception groups)", 4, "Handles several errors raised together, e.g. by asyncio.TaskGroup (3.11+)."),
    "type-alias": ("type statement", 4, "`type Vector = list[float]` declares a type alias (3.12+)."),
    "generics": ("generic classes/functions [T]", 4, "class Box[T]: / def first[T](...) declares type parameters (3.12+)."),
}

SHADOWABLE = {"list", "dict", "str", "int", "float", "set", "tuple", "input", "sum", "max", "min", "id",
              "type", "len", "print", "range", "map", "filter", "sorted", "open", "object", "bytes", "format",
              "hash", "iter", "next", "all", "any", "round", "abs", "vars", "dir", "zip"}
NONE_RETURNING = {"sort", "append", "extend", "reverse", "insert", "remove", "clear", "update", "add", "discard"}
MUTATORS = {"append", "remove", "insert", "pop", "extend", "clear", "add", "discard"}


class ConceptFinder(ast.NodeVisitor):
    def __init__(self, source):
        self.lines = source.splitlines()
        self.found = {}
        self.pitfalls = []
        self.func_stack = []
        self.docstring_nodes = set()
        self.with_open_calls = set()
        self.unpack_targets = set()

    # --- helpers -----------------------------------------------------------
    def add(self, cid, node):
        line = getattr(node, "lineno", None)
        self.found.setdefault(cid, set())
        if line:
            self.found[cid].add(line)

    def pit(self, rule, node, message, fix):
        self.pitfalls.append({"rule": rule, "line": node.lineno, "message": message, "fix": fix,
                              "code": self.src(node.lineno)})

    def src(self, lineno):
        return self.lines[lineno - 1].strip() if 0 < lineno <= len(self.lines) else ""

    def _mark_docstring(self, node):
        body = getattr(node, "body", None)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            self.docstring_nodes.add(id(body[0].value))
            if not isinstance(node, ast.Module):
                self.add("docstring", body[0])

    # --- structure ---------------------------------------------------------
    def visit_Module(self, node):
        self._mark_docstring(node)
        self.generic_visit(node)

    def _visit_func(self, node, is_async):
        self._mark_docstring(node)
        self.add("async-def" if is_async else "function-def", node)
        if self.func_stack:
            self.add("closure", node)
        a = node.args
        if a.posonlyargs:
            self.add("positional-only", node)
        if a.kwonlyargs:
            self.add("keyword-only", node)
        if a.vararg:
            self.add("star-args", node)
        if a.kwarg:
            self.add("star-kwargs", node)
        defaults = list(a.defaults) + [d for d in a.kw_defaults if d is not None]
        if defaults:
            self.add("default-args", node)
        for d in defaults:
            mutable = isinstance(d, (ast.List, ast.Dict, ast.Set)) or (
                isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id in ("list", "dict", "set"))
            if mutable:
                self.pit("mutable-default", d, "Mutable default argument: the same list/dict is shared by every call "
                         "and keeps growing.", "use `param=None` and inside: `if param is None: param = []`")
        all_args = a.posonlyargs + a.args + a.kwonlyargs + [x for x in (a.vararg, a.kwarg) if x]
        if node.returns is not None or any(x.annotation is not None for x in all_args):
            self.add("type-hints", node)
        if getattr(node, "type_params", None):
            self.add("generics", node)
        for dec in node.decorator_list:
            self._decorator(dec)
        self.func_stack.append(node.name)
        self.generic_visit(node)
        self.func_stack.pop()

    def visit_FunctionDef(self, node):
        self._visit_func(node, False)

    def visit_AsyncFunctionDef(self, node):
        self._visit_func(node, True)

    def _decorator(self, dec):
        target = dec.func if isinstance(dec, ast.Call) else dec
        name = target.id if isinstance(target, ast.Name) else target.attr if isinstance(target, ast.Attribute) else ""
        self.add("decorator", dec)
        if name == "property" or (isinstance(target, ast.Attribute) and target.attr in ("setter", "getter")):
            self.add("property", dec)
        elif name == "dataclass":
            self.add("dataclass", dec)
        elif name in ("staticmethod", "classmethod"):
            self.add("static-class-method", dec)

    def visit_ClassDef(self, node):
        self._mark_docstring(node)
        self.add("class", node)
        for b in node.bases:
            self.add("inheritance", node)
            if isinstance(b, ast.Name) and (b.id.endswith("Exception") or b.id.endswith("Error")):
                self.add("custom-exception", node)
        for dec in node.decorator_list:
            self._decorator(dec)
        if getattr(node, "type_params", None):
            self.add("generics", node)
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("__") \
                    and item.name.endswith("__"):
                self.add("init-self" if item.name == "__init__" else "dunder", item)
        self.func_stack.append(None)  # methods are not closures
        self.generic_visit(node)
        self.func_stack.pop()

    def visit_Return(self, node):
        self.add("return", node)
        self.generic_visit(node)

    def visit_Pass(self, node):
        self.add("pass", node)

    def visit_Global(self, node):
        self.add("global-nonlocal", node)

    visit_Nonlocal = visit_Global

    def visit_Import(self, node):
        self.add("import", node)

    visit_ImportFrom = visit_Import

    def visit_Delete(self, node):
        self.add("del", node)
        self.generic_visit(node)

    def visit_Assert(self, node):
        self.add("assert", node)
        self.generic_visit(node)

    # --- assignment --------------------------------------------------------
    def visit_Assign(self, node):
        self.add("assignment", node)
        for t in node.targets:
            self._target(t)
            if isinstance(t, ast.Name) and t.id in SHADOWABLE:
                self.pit("shadow-builtin", node, f"`{t.id} = ...` hides the built-in {t.id}(); later calls to "
                         f"{t.id}() will fail with TypeError.", f"rename it, e.g. `{t.id}_` or `my_{t.id}`")
        v = node.value
        if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and v.func.attr in NONE_RETURNING:
            self.pit("none-returning-method", node, f".{v.func.attr}() changes the object in place and returns None, "
                     "so this assigns None.", f"call it on its own line: `{ast.unparse(v)}` (or use sorted(x) for a "
                     "new sorted list)")
        if isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == "print":
            self.pit("assign-print", node, "print() returns None, so this variable will be None.",
                     "build the value first (`msg = f\"...\"`), then `print(msg)`")
        if isinstance(v, ast.BinOp) and isinstance(v.op, ast.Mult) and isinstance(v.left, ast.List) \
                and v.left.elts and isinstance(v.left.elts[0], ast.List):
            self.pit("list-multiply-alias", node, "[[...]] * n repeats the SAME inner list n times; changing one "
                     "row changes them all.", "use a comprehension: `[[0] * cols for _ in range(rows)]`")
        self.generic_visit(node)

    def _target(self, t):
        if isinstance(t, (ast.Tuple, ast.List)):
            self.add("unpacking", t)
            self.unpack_targets.add(id(t))
            for e in t.elts:
                if isinstance(e, ast.Starred):
                    self.add("star-assign", e)

    def visit_AugAssign(self, node):
        self.add("augmented-assignment", node)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        self.add("assignment", node)
        self.add("type-hints", node)
        self.generic_visit(node)

    def visit_NamedExpr(self, node):
        self.add("walrus", node)
        self.generic_visit(node)

    # --- literals & expressions -------------------------------------------
    def visit_Constant(self, node):
        if id(node) in self.docstring_nodes:
            return
        v = node.value
        if isinstance(v, bool) or v is None:
            self.add("bool-none", node)
        elif isinstance(v, (int, float, complex)):
            self.add("number", node)
        elif isinstance(v, (str, bytes)):
            self.add("string", node)

    def visit_JoinedStr(self, node):
        self.add("f-string", node)
        for part in node.values:  # skip literal pieces: they are not separate strings
            if isinstance(part, ast.FormattedValue):
                self.visit(part.value)

    def visit_List(self, node):
        if id(node) not in self.unpack_targets and isinstance(node.ctx, ast.Load):
            self.add("list-literal", node)
        self.generic_visit(node)

    def visit_Tuple(self, node):
        if id(node) not in self.unpack_targets and isinstance(node.ctx, ast.Load):
            self.add("tuple-literal", node)
        self.generic_visit(node)

    def visit_Dict(self, node):
        self.add("dict-literal", node)
        if any(k is None for k in node.keys):
            self.add("call-unpacking", node)
        self.generic_visit(node)

    def visit_Set(self, node):
        self.add("set-literal", node)
        self.generic_visit(node)

    def visit_BinOp(self, node):
        if isinstance(node.op, (ast.FloorDiv, ast.Mod)) and not (
                isinstance(node.op, ast.Mod) and isinstance(node.left, ast.Constant)
                and isinstance(node.left.value, str)):
            self.add("floor-mod", node)
        else:
            self.add("arithmetic", node)
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        self.add("boolean-ops", node)
        if isinstance(node.op, ast.Or) and any(isinstance(v, ast.Compare) for v in node.values) and any(
                isinstance(v, ast.Constant) and not isinstance(v.value, bool) for v in node.values[1:]):
            self.pit("or-constant", node, "`x == a or b` is always truthy: Python reads it as `(x == a) or b`.",
                     "write `x == a or x == b`, or `x in (a, b)`")
        self.generic_visit(node)

    def visit_UnaryOp(self, node):
        if isinstance(node.op, ast.Not):
            self.add("boolean-ops", node)
        self.generic_visit(node)

    def visit_Compare(self, node):
        if len(node.ops) > 1:
            self.add("comparison-chain", node)
        for op, right in zip(node.ops, node.comparators):
            if isinstance(op, (ast.In, ast.NotIn)):
                self.add("membership", node)
            elif isinstance(op, (ast.Is, ast.IsNot)):
                self.add("identity", node)
                if isinstance(right, ast.Constant) and right.value is not None and not isinstance(right.value, bool):
                    self.pit("is-literal", node, "`is` compares identity, not value; with numbers or strings it "
                             "works only by accident (SyntaxWarning in 3.8+).", "use `==` / `!=` for values")
            else:
                self.add("comparison", node)
                if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(right, ast.Constant):
                    if right.value is None:
                        self.pit("eq-none", node, "Comparing to None with == works but is unidiomatic and can be "
                                 "fooled by custom __eq__ (e.g. numpy arrays).", "use `is None` / `is not None`")
                    elif isinstance(right.value, float):
                        self.pit("float-equality", node, "Floats are approximate (0.1 + 0.2 != 0.3), so == on "
                                 "floats is fragile.", "use `math.isclose(a, b)` or compare with a tolerance")
        left = node.left
        if isinstance(left, ast.Call) and isinstance(left.func, ast.Name) and left.func.id == "type" \
                and isinstance(node.ops[0], (ast.Eq, ast.Is)):
            self.pit("type-equality", node, "type(x) == T ignores subclasses (bool is a subclass of int).",
                     "use `isinstance(x, T)`")
        self.generic_visit(node)

    def visit_IfExp(self, node):
        self.add("ternary", node)
        self.generic_visit(node)

    def visit_Subscript(self, node):
        sl = node.slice
        if sys.version_info < (3, 9) and isinstance(sl, ast.Index):  # pragma: no cover
            sl = sl.value
        if isinstance(sl, ast.Slice):
            self.add("slicing", node)
        else:
            self.add("indexing", node)
            if isinstance(sl, ast.BinOp) and isinstance(sl.op, ast.Div):
                self.pit("float-index", node, "`/` always returns a float, and list indices must be integers "
                         "(TypeError).", "use `//` for integer division: `items[len(items) // 2]`")
        self.generic_visit(node)

    def visit_Lambda(self, node):
        self.add("lambda", node)
        self.generic_visit(node)

    def visit_ListComp(self, node):
        self.add("list-comprehension", node)
        self.generic_visit(node)

    def visit_DictComp(self, node):
        self.add("dict-comprehension", node)
        self.generic_visit(node)

    def visit_SetComp(self, node):
        self.add("set-comprehension", node)
        self.generic_visit(node)

    def visit_GeneratorExp(self, node):
        self.add("generator-expression", node)
        self.generic_visit(node)

    def visit_Yield(self, node):
        self.add("yield", node)
        self.generic_visit(node)

    def visit_YieldFrom(self, node):
        self.add("yield-from", node)
        self.generic_visit(node)

    def visit_Await(self, node):
        self.add("await", node)
        self.generic_visit(node)

    def visit_Starred(self, node):
        if isinstance(node.ctx, ast.Load):
            self.add("call-unpacking", node)
        self.generic_visit(node)

    def visit_Call(self, node):
        f = node.func
        self.add("call", node)
        if isinstance(f, ast.Name):
            special = {"print": "print", "len": "len", "range": "range", "enumerate": "enumerate", "zip": "zip",
                       "open": "open", "super": "super"}
            if f.id in special:
                self.add(special[f.id], node)
            if f.id == "open" and id(node) not in self.with_open_calls:
                self.pit("open-without-with", node, "open() outside `with` may leave the file open if an error "
                         "happens.", "`with open(path, encoding=\"utf-8\") as f:`")
            if self.func_stack and f.id == self.func_stack[-1]:
                self.add("recursion", node)
        elif isinstance(f, ast.Attribute):
            self.add("method-call", node)
            if f.attr == "items" and not node.args:
                self.add("dict-items", node)
        if node.keywords:
            self.add("keyword-args", node)
            if any(k.arg is None for k in node.keywords):
                self.add("call-unpacking", node)
        self.generic_visit(node)

    # --- control flow ------------------------------------------------------
    def visit_If(self, node):
        test = node.test
        if isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and test.left.id == "__name__":
            self.add("main-guard", node)
        is_elif = self.src(node.lineno).startswith("elif")
        self.add("elif" if is_elif else "if", node)
        if node.orelse:
            first = node.orelse[0]
            if not (len(node.orelse) == 1 and isinstance(first, ast.If) and self.src(first.lineno).startswith("elif")):
                self.add("else", first)
        self.generic_visit(node)

    def _loop(self, node, kind):
        self.add(kind, node)
        if node.orelse:
            self.add("loop-else", node.orelse[0])
        for sub in ast.walk(node):
            if isinstance(sub, (ast.Break, ast.Continue)):
                self.add("break-continue", sub)

    def visit_For(self, node):
        self._loop(node, "for")
        self._target(node.target)
        it = node.iter
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == "range" and it.args \
                and isinstance(it.args[0], ast.Call) and isinstance(it.args[0].func, ast.Name) \
                and it.args[0].func.id == "len" and len(it.args) == 1:
            self.pit("range-len", node, "range(len(x)) then x[i] is the long way round.",
                     "`for item in x:` or, if you need the index, `for i, item in enumerate(x):`")
        if isinstance(it, ast.Name):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr in MUTATORS \
                        and isinstance(sub.func.value, ast.Name) and sub.func.value.id == it.id:
                    self.pit("mutate-while-iterating", sub, f"Changing `{it.id}` while looping over it skips or "
                             "repeats items.", f"loop over a copy (`for x in {it.id}[:]`) or build a new list "
                             "with a comprehension")
                    break
        self.generic_visit(node)

    def visit_AsyncFor(self, node):
        self.add("async-for-with", node)
        self._loop(node, "for")
        self.generic_visit(node)

    def visit_While(self, node):
        self._loop(node, "while")
        self.generic_visit(node)

    def _with(self, node):
        self.add("with", node)
        for item in node.items:
            c = item.context_expr
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "open":
                self.with_open_calls.add(id(c))

    def visit_With(self, node):
        self._with(node)
        self.generic_visit(node)

    def visit_AsyncWith(self, node):
        self.add("async-for-with", node)
        self._with(node)
        self.generic_visit(node)

    def _try(self, node, star=False):
        self.add("except-star" if star else "try-except", node)
        if node.finalbody:
            self.add("finally", node.finalbody[0])
        if node.orelse:
            self.add("try-else", node.orelse[0])
        for h in node.handlers:
            swallow = len(h.body) == 1 and isinstance(h.body[0], ast.Pass)
            if h.type is None:
                self.pit("bare-except", h, "A bare `except:` also catches KeyboardInterrupt and typos (NameError), "
                         "hiding real bugs.", "catch what you expect: `except (KeyError, ValueError) as e:`")
            elif swallow:
                self.pit("silent-except", h, "`except ...: pass` swallows the error silently; you will never "
                         "know it happened.", "log it (`print(f\"skipped: {e}\")` / logging.warning) or re-raise")
        self.generic_visit(node)

    def visit_Try(self, node):
        self._try(node)

    def visit_TryStar(self, node):  # 3.11+
        self._try(node, star=True)

    def visit_Raise(self, node):
        self.add("raise-from" if node.cause is not None else "raise", node)
        self.generic_visit(node)

    def visit_Match(self, node):  # 3.10+
        self.add("match", node)
        self.generic_visit(node)

    def visit_TypeAlias(self, node):  # 3.12+
        self.add("type-alias", node)
        self.generic_visit(node)


def analyse(source):
    tree = ast.parse(source)
    finder = ConceptFinder(source)
    # mark with-open calls and unpack targets before visiting
    for node in ast.walk(tree):
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                c = item.context_expr
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "open":
                    finder.with_open_calls.add(id(c))
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, (ast.Tuple, ast.List)):
                    finder.unpack_targets.add(id(t))
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            if isinstance(node.target, (ast.Tuple, ast.List)):
                finder.unpack_targets.add(id(node.target))
                if isinstance(node, ast.comprehension):
                    finder.add("unpacking", node.target)
    finder.visit(tree)
    order = list(CONCEPTS)
    concepts = []
    for cid, lines in finder.found.items():
        title, level, text = CONCEPTS[cid]
        concepts.append({"id": cid, "concept": title, "level": level, "level_name": LEVEL_NAMES[level],
                         "lines": sorted(lines), "explanation": text})
    concepts.sort(key=lambda c: (c["level"], order.index(c["id"])))
    seen, pitfalls = set(), []
    for p in sorted(finder.pitfalls, key=lambda p: (p["line"], p["rule"])):
        if (p["rule"], p["line"]) not in seen:
            seen.add((p["rule"], p["line"]))
            pitfalls.append(p)
    return concepts, pitfalls


def fmt_lines(lines, limit=8):
    shown = ", ".join(map(str, lines[:limit]))
    return f"line{'s' if len(lines) > 1 else ''} {shown}" + (f" (+{len(lines) - limit} more)" if len(lines) > limit else "")


def run_concepts(args, source, name):
    try:
        concepts, pitfalls = analyse(source)
    except SyntaxError as e:
        return syntax_error_exit(e, source, args.json)
    shown = [c for c in concepts if c["level"] >= args.level]
    over = [c for c in concepts if args.max_level and c["level"] > args.max_level]
    if args.json:
        print(json.dumps({"file": name, "concepts": shown, "pitfalls": pitfalls,
                          "above_max_level": [c["id"] for c in over],
                          "learning_order": [c["concept"] for c in shown]}, indent=2))
    else:
        if not concepts:
            print(f"No Python concepts found in {name} (empty file?).")
        else:
            filt = f", level {args.level}+ only" if args.level > 1 else ""
            print(f"Concepts used in {name}: {len(shown)} shown{filt}, easiest first (= suggested reading order)\n")
            current = None
            for c in shown:
                if c["level"] != current:
                    current = c["level"]
                    print(f"Level {current} - {LEVEL_NAMES[current]}")
                print(f"  [L{c['level']}] {c['concept']:<34} {fmt_lines(c['lines'])}")
                print(textwrap.fill(c["explanation"], 96, initial_indent=" " * 7, subsequent_indent=" " * 7))
            if shown:
                print("\nLearning order: " + " -> ".join(c["concept"] for c in shown))
        if over:
            print(f"\nAbove --max-level {args.max_level}: " + ", ".join(
                f"{c['concept']} (L{c['level']}, {fmt_lines(c['lines'], 3)})" for c in over))
            print("  Teach these first, or simplify the example for this learner.")
        if pitfalls:
            print(f"\nBeginner pitfalls to talk through ({len(pitfalls)}):")
            for p in pitfalls:
                print(f"  line {p['line']}: [{p['rule']}] {p['message']}")
                print(f"      code: {p['code']}")
                print(f"      fix:  {p['fix']}")
        elif concepts:
            print("\nNo beginner pitfalls detected.")
    return 1 if args.strict and (pitfalls or over) else 0


# ----------------------------------------------------------------------------- trace mode

SNIPPET = "<snippet>"
ERROR_HINTS = {
    "NameError": "Python doesn't know that name yet: a typo, a variable used before it is assigned, or a "
                 "missing import.",
    "TypeError": "An operation got the wrong type of value, e.g. adding a str and an int, calling something "
                 "that isn't a function, or passing the wrong number of arguments.",
    "ZeroDivisionError": "Something was divided by zero. Check the value of the divisor (an empty list's len?).",
    "IndexError": "You asked for a position that doesn't exist. Positions run 0 .. len-1 (off-by-one?).",
    "KeyError": "That key isn't in the dictionary. Check spelling/case, or use d.get(key, default).",
    "AttributeError": "The value doesn't have that attribute or method. If it says 'NoneType', a variable is "
                      "None, often because a function didn't return anything or .sort()/.append() was assigned.",
    "ValueError": "Right type, wrong value, e.g. int('abc') or unpacking the wrong number of items.",
    "UnboundLocalError": "You assign to this name somewhere in the function, so Python treats it as local "
                         "everywhere in that function, and it is read before that assignment.",
    "RecursionError": "The function kept calling itself: the base case is missing or never reached.",
    "ModuleNotFoundError": "The module isn't installed in THIS Python. Check the virtual env is activated and "
                           "run `python -m pip install <package>` with the same python.",
    "ImportError": "The module was found but the name you import from it isn't there (typo, or wrong version).",
    "FileNotFoundError": "No file at that path. Paths are relative to where you run python, not to the script.",
    "AssertionError": "An assert condition was False: the code's own sanity check failed.",
    "EOFError": "input() had nothing to read. In trace mode pass text with --input \"answer\".",
    "IndentationError": "The indentation doesn't line up. Use 4 spaces per level and don't mix tabs and spaces.",
    "StopIteration": "next() was called on an iterator that has no items left.",
    "OverflowError": "A number got too big for a float.",
    "SystemExit": "The snippet called exit()/sys.exit().",
}
SYNTAX_HINTS = [
    ("expected ':'", "Lines that start a block (if, for, while, def, class, else, try) must end with a colon."),
    ("was never closed", "A bracket or parenthesis is opened but never closed; the real mistake may be above."),
    ("unterminated string", "A string is missing its closing quote."),
    ("unmatched", "There is a closing bracket without a matching opening one."),
    ("Perhaps you forgot a comma", "Two values sit next to each other; you probably need a comma between them."),
    ("expected an indented block", "After a line ending in ':' the next line must be indented (4 spaces)."),
    ("unexpected indent", "This line is indented more than it should be; line it up with the block it belongs to."),
    ("unindent does not match", "This line's indentation doesn't match any outer level; count the spaces."),
    ("inconsistent use of tabs", "Tabs and spaces are mixed; configure your editor to insert 4 spaces."),
    ("Maybe you meant '==' or ':='", "`=` assigns; to compare inside an if/while use `==`."),
    ("cannot assign to", "The left side of `=` must be a name (or item/attribute), not an expression or literal."),
    ("invalid syntax", "Python couldn't read this line. Look for a missing colon, quote, bracket or comma at or "
                       "just before the caret."),
]


GENERATOR_FLAGS = 0x20 | 0x80 | 0x200  # CO_GENERATOR | CO_COROUTINE | CO_ASYNC_GENERATOR
ADDRESS_RE = re.compile(r" at 0x[0-9a-fA-F]+")


class EchoInput(io.StringIO):
    """Fake stdin for input(): echoes each answer into the captured output, like a terminal would."""

    def __init__(self, text, echo_to):
        super().__init__(text)
        self.echo_to = echo_to

    def readline(self, *args):
        line = super().readline(*args)
        self.echo_to.write(line)
        return line


class StepLimit(BaseException):
    pass


def safe_repr(value, width):
    try:
        if isinstance(value, type(sys)):
            text = f"<module {value.__name__}>"
        elif callable(value) and hasattr(value, "__qualname__") and not isinstance(value, type):
            text = f"<function {value.__qualname__}>"
        else:
            text = repr(value)
    except Exception as e:  # a broken __repr__ in the snippet
        text = f"<repr failed: {type(e).__name__}>"
    text = ADDRESS_RE.sub("", text.replace("\n", "\\n")).replace("__main__.", "")
    return text if len(text) <= width else text[: width - 3] + "..."


def is_mutable(value):
    return isinstance(value, (list, dict, set, bytearray)) or (
        hasattr(value, "__dict__") and not isinstance(value, (type, type(sys))) and not callable(value))


class Tracer:
    def __init__(self, lines, max_steps, width):
        self.lines, self.max_steps, self.width = lines, max_steps, width
        self.rows, self.frames, self.steps = [], {}, 0
        self.out = io.StringIO()
        self.out_pos = 0
        self.active = []
        self.truncated = None

    def source(self, lineno):
        return self.lines[lineno - 1].strip() if 0 < lineno <= len(self.lines) else ""

    def snapshot(self, frame):
        snap = {}
        names = frame.f_globals if frame.f_code.co_name == "<module>" else frame.f_locals
        for k, v in dict(names).items():
            if (k.startswith("__") and k.endswith("__")) or k.startswith("."):  # dunders, hidden ".0" iterators
                continue
            snap[k] = (safe_repr(v, self.width), id(v), is_mutable(v))
        return snap

    def new_output(self):
        text = self.out.getvalue()[self.out_pos:]
        self.out_pos += len(text)
        return text

    def emit(self, frame, state, note=None):
        lineno = state.get("line")
        if lineno is None and note is None:
            return
        new = self.snapshot(frame)
        old = state.get("snap", {})
        changes = {}
        for k, (r, oid, mut) in new.items():
            if k not in old or old[k][0] != r or old[k][1] != oid:
                alias = [o for o, (_, oid2, _) in new.items() if o != k and oid2 == oid] if mut else []
                changes[k] = r + (f"   (same object as {', '.join(alias)})" if alias else "")
        for k in old:
            if k not in new:
                changes[k] = "(deleted)"
        self.rows.append({"step": len(self.rows) + 1, "line": lineno or frame.f_lineno, "where": state["name"],
                          "depth": state["depth"], "source": self.source(lineno or frame.f_lineno),
                          "changes": changes, "note": note, "output": self.new_output()})
        state["snap"], state["line"] = new, None

    def global_trace(self, frame, event, arg):
        if frame.f_code.co_filename != SNIPPET:
            return None
        if event == "call":
            code = frame.f_code
            name = code.co_name
            st = self.frames.get(frame)
            resumed = st is not None
            if not resumed:
                if code.co_flags & GENERATOR_FLAGS:
                    kind = "generator"
                elif name != "<module>" and self.source(code.co_firstlineno).startswith("class "):
                    kind = "class"
                else:
                    kind = "function"
                st = {"name": name, "kind": kind, "line": None, "snap": {}, "exc": None}
                self.frames[frame] = st
            st["depth"] = len(self.active)
            self.active.append(frame)
            if name != "<module>":
                if resumed:
                    note = f"resume {name} where it paused"
                elif st["kind"] == "class":
                    note = f"build class {name}: run its body"
                else:
                    args = ", ".join(f"{k}={r}" for k, (r, _, _) in self.snapshot(frame).items())
                    note = f"call {name}({args})"
                self.rows.append({"step": len(self.rows) + 1, "line": frame.f_lineno, "where": name,
                                  "depth": st["depth"], "source": self.source(frame.f_lineno), "changes": {},
                                  "note": note, "output": self.new_output()})
                st["snap"] = self.snapshot(frame)
            return self.local_trace
        return None

    def local_trace(self, frame, event, arg):
        st = self.frames.get(frame)
        if st is None:
            return None
        if event == "line":
            self.steps += 1
            if self.steps > self.max_steps:
                self.emit(frame, st)
                self.truncated = f"stopped after {self.max_steps} steps (infinite loop? raise --max-steps)"
                raise StepLimit()
            self.emit(frame, st)
            st["line"], st["exc"] = frame.f_lineno, None
        elif event == "exception":
            exc_type, exc, _ = arg
            if exc_type in (StopIteration, StopAsyncIteration, GeneratorExit, StepLimit) or st.get("exc") is exc:
                return self.local_trace
            st["exc"] = exc
            if st["line"] is None:
                st["line"] = frame.f_lineno
            self.emit(frame, st, note=f"raises {exc_type.__name__}: {exc}")
        elif event == "return":
            if frame in self.active:
                self.active.remove(frame)
            current = self.source(st["line"] or frame.f_lineno)
            paused = st["kind"] == "generator" and st["exc"] is None and (
                "yield" in current or "await" in current)
            if st["exc"] is not None or st["kind"] == "class" or st["name"] == "<module>":
                note = None  # errors were already shown as "raises ..."; class bodies return nothing useful
            elif paused:
                verb = "yields" if "yield" in current else "pauses at await"
                note = f"{st['name']} {verb}" + (f" {safe_repr(arg, self.width)}" if verb == "yields" else "")
            else:
                note = f"{st['name']} returns {safe_repr(arg, self.width)}"
            if st["line"] is not None or note:
                self.emit(frame, st, note=note)
            if not paused:
                self.frames.pop(frame, None)
        return self.local_trace


def syntax_error_exit(e, source, as_json):
    lines = source.splitlines()
    lineno = e.lineno or 0
    text = lines[lineno - 1] if 0 < lineno <= len(lines) else (e.text or "").rstrip("\n")
    offset = max((e.offset or 1) - 1 - (len(text) - len(text.lstrip())), 0)
    hint = next((h for key, h in SYNTAX_HINTS if key in (e.msg or "")), SYNTAX_HINTS[-1][1])
    if isinstance(e, IndentationError) and "indent" not in (e.msg or "") and "tab" not in (e.msg or ""):
        hint = ERROR_HINTS["IndentationError"]
    kind = type(e).__name__
    if as_json:
        print(json.dumps({"error": kind, "message": e.msg, "line": lineno, "column": e.offset, "code": text,
                          "hint": hint}, indent=2))
    else:
        print(f"{kind} on line {lineno}: {e.msg}", file=sys.stderr)
        print(f"    {text.strip()}", file=sys.stderr)
        print("    " + " " * offset + "^", file=sys.stderr)
        print(f"What it usually means: {hint}", file=sys.stderr)
        print("Python reads the whole file before running it, so nothing ran.", file=sys.stderr)
    return 2


def snippet_frame_line(tb):
    line = None
    while tb is not None:
        if tb.tb_frame.f_code.co_filename == SNIPPET:
            line = (tb.tb_lineno, tb.tb_frame.f_code.co_name)
        tb = tb.tb_next
    return line


def render_trace(tracer, name, exc_info, as_json, strict):
    full_output = tracer.out.getvalue()
    if as_json:
        print(json.dumps({"file": name, "steps": tracer.rows, "output": full_output, "exception": exc_info,
                          "truncated": tracer.truncated}, indent=2))
    else:
        print(f"Trace of {name} (the code was executed; {len(tracer.rows)} steps)\n")
        print(f"{'Step':>4}  {'Line':>4}  {'Code':<44} Changes")
        for r in tracer.rows:
            code = ("  " * r["depth"] + r["source"])
            code = code if len(code) <= 44 else code[:41] + "..."
            changes = ", ".join(f"{k} = {v}" for k, v in r["changes"].items())
            extra = f"  <- {r['note']}" if r["note"] else ""
            print(f"{r['step']:>4}  {r['line']:>4}  {code:<44} {changes}{extra}".rstrip())
            for out_line in r["output"].splitlines():
                print(f"{'':>12}printed: {out_line}")
        if tracer.truncated:
            print(f"\n[!] {tracer.truncated}")
        print("\nProgram output:" if full_output else "\nProgram output: (nothing printed)")
        for out_line in full_output.splitlines():
            print(f"  {out_line}")
        if exc_info:
            where = f" in {exc_info['function']}()" if exc_info["function"] not in ("<module>", None) else ""
            print(f"\nThe program stopped with {exc_info['type']}: {exc_info['message']}")
            print(f"  on line {exc_info['line']}{where}: {exc_info['code']}")
            print(f"  What it means: {exc_info['hint']}")
    return 1 if strict and (exc_info or tracer.truncated) else 0


def run_trace(args, source, name):
    lines = source.splitlines()
    if len(lines) > 200:
        print(f"error: {name} has {len(lines)} lines; trace mode only runs small snippets (<= 200 lines). "
              "Use `concepts` mode for big files.", file=sys.stderr)
        return 2
    try:
        code = compile(source, SNIPPET, "exec")
    except SyntaxError as e:
        return syntax_error_exit(e, source, args.json)

    tracer = Tracer(lines, args.max_steps, args.width)
    real_stdout, real_stdin = sys.stdout, sys.stdin
    exc_info = None

    def finish_and_exit(*_):
        sys.settrace(None)
        sys.stdout, sys.stdin = real_stdout, real_stdin
        tracer.truncated = tracer.truncated or f"stopped after {args.timeout}s (--timeout)"
        code_ = render_trace(tracer, name, None, args.json, args.strict)
        sys.stdout.flush()
        os._exit(code_)

    if args.timeout and hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, finish_and_exit)
        signal.alarm(args.timeout)
    namespace = {"__name__": "__main__", "__builtins__": builtins}
    real_argv, sys.argv = sys.argv, [name]  # the snippet sees itself as the program, with no arguments
    sys.stdout, sys.stdin = tracer.out, EchoInput(args.input.replace("\\n", "\n") + "\n" if args.input else "",
                                                 tracer.out)
    sys.settrace(tracer.global_trace)
    try:
        exec(code, namespace)
    except StepLimit:
        pass
    except (Exception, SystemExit) as e:
        where = snippet_frame_line(e.__traceback__) or (None, None)
        exc_info = {"type": type(e).__name__, "message": str(e), "line": where[0], "function": where[1],
                    "code": tracer.source(where[0]) if where[0] else "",
                    "hint": next((ERROR_HINTS[c.__name__] for c in type(e).__mro__ if c.__name__ in ERROR_HINTS),
                                 "Read the last line of the message: it names the error type and what went wrong.")}
    finally:
        sys.settrace(None)
        sys.stdout, sys.stdin, sys.argv = real_stdout, real_stdin, real_argv
        if args.timeout and hasattr(signal, "SIGALRM"):
            signal.alarm(0)
    if tracer.truncated and isinstance(exc_info, dict) and exc_info["type"] == "StepLimit":
        exc_info = None
    return render_trace(tracer, name, exc_info, args.json, args.strict)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in ("concepts", "trace", "-h", "--help"):
        argv.insert(0, "concepts")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode")
    c = sub.add_parser("concepts", help="list concepts used (static, never runs the code) [default]")
    c.add_argument("file", help="Python file, or - for stdin")
    c.add_argument("--level", type=int, default=1, choices=[1, 2, 3, 4],
                   help="only show concepts at or above this level (1 beginner .. 4 advanced)")
    c.add_argument("--max-level", type=int, default=0, choices=[0, 1, 2, 3, 4],
                   help="learner's level: report concepts above it (with --strict, exit 1 if any)")
    c.add_argument("--strict", action="store_true",
                   help="exit 1 if a beginner pitfall is found or a concept is above --max-level")
    c.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    t = sub.add_parser("trace", help="EXECUTE a small snippet step by step (runs the code!)",
                       description="EXECUTES the snippet under sys.settrace and prints each step with the variables "
                                   "that changed. Only run small code you trust. Refuses files over 200 lines.")
    t.add_argument("file", help="Python file (<= 200 lines), or - for stdin")
    t.add_argument("--max-steps", type=int, default=500, help="stop after this many executed lines (default 500)")
    t.add_argument("--timeout", type=int, default=5, help="wall-clock limit in seconds, POSIX only (default 5; 0=off)")
    t.add_argument("--input", default="", help="text fed to input(); separate answers with \\n")
    t.add_argument("--width", type=int, default=60, help="truncate variable reprs to this many chars (default 60)")
    t.add_argument("--strict", action="store_true", help="exit 1 if the snippet raised or hit a limit")
    t.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    if not argv:
        ap.print_usage(sys.stderr)
        print("error: give a Python file (or - for stdin)", file=sys.stderr)
        return 2
    args = ap.parse_args(argv)
    try:
        if args.file == "-":
            source, name = sys.stdin.read(), "<stdin>"
        else:
            with open(args.file, encoding="utf-8") as f:
                source, name = f.read(), args.file
    except (OSError, UnicodeDecodeError) as e:
        print(f"error: cannot read {args.file}: {e}", file=sys.stderr)
        return 2
    if args.mode == "trace":
        if args.max_steps < 1:
            print("error: --max-steps must be >= 1", file=sys.stderr)
            return 2
        return run_trace(args, source, name)
    return run_concepts(args, source, name)


if __name__ == "__main__":
    sys.exit(main())
