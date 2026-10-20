#!/usr/bin/env python3
"""Audit Python type-annotation coverage and modernise legacy typing syntax.

Static analysis only (ast): the analysed code is never imported or executed.

For every function and method it reports which parameters and the return type
are unannotated, and suggests a type where one can be inferred safely
(literal defaults, simple return statements, f-strings, comparisons, returns
of annotated parameters, `return self` -> Self, generators -> Iterator[...]).
It computes coverage for parameters, returns and overall (self/cls excluded),
and can gate CI with --min-coverage.

It also flags, for a --target-version:
  legacy-generic     List[int] -> list[int], Dict/Set/Tuple/Type/Deque/...   (3.9+)
  legacy-optional    Optional[X] -> X | None                                 (3.10+)
  legacy-union       Union[A, B] -> A | B                                    (3.10+)
  legacy-abc         typing.Callable/Iterable/Sequence/... -> collections.abc (3.9+)
  legacy-import      the import lines to rewrite after the above
  legacy-backport    typing_extensions.X that the target's typing already has
  legacy-alias       X: TypeAlias = ... -> type X = ...                      (3.12+)
  legacy-typevar     T = TypeVar("T") / Generic[T] -> PEP 695 [T] syntax       (3.12+)
  any-usage          Any in an annotation (says where)
  mutable-default    def f(x: list[str] = []) -> x: list[str] | None = None
  implicit-optional  def f(x: str = None) -> x: str | None = None
  default-mismatch   def f(n: int = "5")
  missing-param / missing-return   unannotated parameter / return

Annotations are treated as deferred (strings) when the module has
`from __future__ import annotations` or the target is 3.14+, so `X | None`
is suggested for 3.9 targets only where it is safe; pydantic model fields
are always treated as evaluated at runtime.

Usage:
    python annotation_audit.py llm_client.py
    python annotation_audit.py src/ --target-version 3.12
    python annotation_audit.py src/ --min-coverage 90        # exit 1 if overall coverage < 90%
    python annotation_audit.py app.py --strict --json        # exit 1 on any finding
    python annotation_audit.py app.py --ignore any-usage,missing-return
    cat module.py | python annotation_audit.py -

Exit codes: 0 ok, 1 findings with --strict or coverage below --min-coverage,
2 usage, read or syntax error. No dependencies (standard library only).
"""

import argparse
import ast
import json
import os
import sys

TYPING_MODULES = ("typing", "typing_extensions")
BUILTIN = {"List": "list", "Dict": "dict", "Set": "set", "FrozenSet": "frozenset", "Tuple": "tuple",
           "Type": "type", "Text": "str"}
COLLECTIONS = {"Deque": "deque", "DefaultDict": "defaultdict", "OrderedDict": "OrderedDict",
               "Counter": "Counter", "ChainMap": "ChainMap"}
CONTEXTLIB = {"ContextManager": "AbstractContextManager", "AsyncContextManager": "AbstractAsyncContextManager"}
RE_NAMES = {"Pattern", "Match"}
ABC = {"Awaitable", "Coroutine", "AsyncIterable", "AsyncIterator", "AsyncGenerator", "Iterable", "Iterator",
       "Generator", "Reversible", "Container", "Collection", "Callable", "AbstractSet", "MutableSet", "Mapping",
       "MutableMapping", "Sequence", "MutableSequence", "MappingView", "KeysView", "ItemsView", "ValuesView",
       "Hashable", "Sized"}
# typing_extensions name -> first Python version whose `typing` has it (with the features people use it for)
BACKPORTS = {"Literal": (3, 8), "Final": (3, 8), "Protocol": (3, 8), "runtime_checkable": (3, 8),
             "final": (3, 8), "Annotated": (3, 9), "ParamSpec": (3, 10), "Concatenate": (3, 10),
             "TypeAlias": (3, 10), "TypeGuard": (3, 10), "ParamSpecArgs": (3, 10), "ParamSpecKwargs": (3, 10),
             "is_typeddict": (3, 10), "Self": (3, 11), "Never": (3, 11), "LiteralString": (3, 11),
             "assert_never": (3, 11), "assert_type": (3, 11), "reveal_type": (3, 11), "Required": (3, 11),
             "NotRequired": (3, 11), "Unpack": (3, 11), "TypeVarTuple": (3, 11), "dataclass_transform": (3, 11),
             "get_overloads": (3, 11), "clear_overloads": (3, 11), "TypedDict": (3, 11), "NamedTuple": (3, 11),
             "override": (3, 12), "TypeAliasType": (3, 12), "TypeIs": (3, 13), "ReadOnly": (3, 13),
             "NoDefault": (3, 13), "TypeVar": (3, 13), "get_protocol_members": (3, 13), "is_protocol": (3, 13)}
PYDANTIC_BASES = ("BaseModel", "BaseSettings", "SQLModel", "RootModel")
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
SEVERITY = {"missing-param": "medium", "missing-return": "medium", "mutable-default": "high",
            "implicit-optional": "high", "default-mismatch": "high", "any-usage": "low",
            "legacy-generic": "low", "legacy-optional": "low", "legacy-union": "low", "legacy-abc": "low",
            "legacy-import": "low", "legacy-backport": "low", "legacy-alias": "low", "legacy-typevar": "low"}


def src_of(source, node):
    seg = ast.get_source_segment(source, node)
    return " ".join(seg.split()) if seg else ast.unparse(node)


class Resolver:
    """Map local names to fully qualified import paths (typing.List, typing_extensions.Self, ...)."""

    def __init__(self, tree):
        self.names = {}
        self.star = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    top = a.name.split(".")[0]
                    self.names[a.asname or top] = a.name if a.asname else top
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                for a in node.names:
                    if a.name == "*":
                        self.star.add(node.module)
                    else:
                        self.names[a.asname or a.name] = node.module + "." + a.name

    def qualname(self, node):
        if isinstance(node, ast.Name):
            if node.id in self.names:
                return self.names[node.id]
            for mod in self.star & set(TYPING_MODULES):
                return mod + "." + node.id
            return None
        if isinstance(node, ast.Attribute):
            base = self.qualname(node.value)
            return base + "." + node.attr if base else None
        return None

    def typing_name(self, node):
        q = self.qualname(node)
        if q:
            mod, _, name = q.rpartition(".")
            if mod in TYPING_MODULES:
                return name
        return None


class Modernizer(ast.NodeTransformer):
    """Rewrite one type expression to modern syntax, recording which rules fired and imports needed."""

    def __init__(self, resolver, allow_604):
        self.r = resolver
        self.allow_604 = allow_604
        self.rules = []
        self.imports = []

    def _note(self, rule, imp=None):
        if rule not in self.rules:
            self.rules.append(rule)
        if imp and imp not in self.imports:
            self.imports.append(imp)

    def _replace(self, node):
        name = self.r.typing_name(node)
        if name in BUILTIN:
            self._note("legacy-generic")
            return ast.Name(BUILTIN[name], ast.Load())
        if name in COLLECTIONS:
            self._note("legacy-generic", "from collections import " + COLLECTIONS[name])
            return ast.Name(COLLECTIONS[name], ast.Load())
        if name in CONTEXTLIB:
            self._note("legacy-generic", "from contextlib import " + CONTEXTLIB[name])
            return ast.Name(CONTEXTLIB[name], ast.Load())
        if name in RE_NAMES:
            self._note("legacy-generic", "import re")
            return ast.Attribute(ast.Name("re", ast.Load()), name, ast.Load())
        if name in ABC and isinstance(node, ast.Attribute):
            alias = "Set as AbstractSet" if name == "AbstractSet" else name
            self._note("legacy-abc", "from collections.abc import " + alias)
            return ast.Name(name, ast.Load())
        return None

    def visit_Name(self, node):
        return self._replace(node) or node

    def visit_Attribute(self, node):
        return self._replace(node) or node

    def visit_Subscript(self, node):
        name = self.r.typing_name(node.value)
        if name in ("Optional", "Union") and self.allow_604:
            inner = self.visit(node.slice)
            elts = list(inner.elts) if name == "Union" and isinstance(inner, ast.Tuple) else [inner]
            if name == "Optional":
                elts.append(ast.Constant(None))
            self._note("legacy-optional" if name == "Optional" else "legacy-union")
            out = elts[0]
            for e in elts[1:]:
                out = ast.BinOp(out, ast.BitOr(), e)
            return out
        return self.generic_visit(node)


def forward_refs_in_union(node):
    """True if a string forward reference is an operand of `|` (TypeError at runtime unless quoted)."""
    for n in ast.walk(node):
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr):
            if any(isinstance(s, ast.Constant) and isinstance(s.value, str) for s in (n.left, n.right)):
                return True
    return False


class Unquote(ast.NodeTransformer):
    def visit_BinOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.BitOr):
            for side in ("left", "right"):
                v = getattr(node, side)
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    setattr(node, side, ast.Name(v.value, ast.Load()))
        return node


def split_union(t):
    """Split 'A | dict[str, B | C] | None' on top-level pipes only."""
    parts, depth, cur = [], 0, ""
    for ch in t:
        depth += ch in "[("
        depth -= ch in "])"
        if ch == "|" and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    return parts + [cur.strip()]


def join_types(types, allow_604):
    seen = []
    for t in types:
        for part in split_union(t):
            if part not in seen:
                seen.append(part)
    if "None" in seen:
        seen = [t for t in seen if t != "None"] + ["None"]
    if len(seen) == 1:
        return seen[0]
    if allow_604:
        return " | ".join(seen)
    if seen[-1] == "None" and len(seen) == 2:
        return "Optional[%s]" % seen[0]
    return "Union[%s]" % ", ".join(seen)


def walk_scope(nodes):
    """Yield nodes of a function body without entering nested functions, lambdas or classes."""
    stack = list(nodes)
    while stack:
        n = stack.pop()
        yield n
        for child in ast.iter_child_nodes(n):
            if not isinstance(child, SCOPES):
                stack.append(child)


def always_exits(stmts):
    if not stmts:
        return False
    last = stmts[-1]
    if isinstance(last, (ast.Return, ast.Raise)):
        return True
    if isinstance(last, ast.If):
        return always_exits(last.body) and always_exits(last.orelse)
    if isinstance(last, (ast.With, ast.AsyncWith)):
        return always_exits(last.body)
    if isinstance(last, ast.Try):
        if always_exits(last.finalbody):
            return True
        body_ok = always_exits(last.orelse) if last.orelse else always_exits(last.body)
        return body_ok and all(always_exits(h.body) for h in last.handlers)
    if isinstance(last, ast.While):
        test_true = isinstance(last.test, ast.Constant) and last.test.value is True
        return test_true and not any(isinstance(n, ast.Break) for n in walk_scope(last.body))
    return False


class Inferer:
    """Infer the type of simple expressions; returns None when unsure."""

    CALLS = {"int": "int", "str": "str", "float": "float", "bool": "bool", "bytes": "bytes", "len": "int",
             "repr": "str", "isinstance": "bool", "issubclass": "bool", "hasattr": "bool", "callable": "bool",
             "any": "bool", "all": "bool", "ord": "int", "chr": "str", "hash": "int", "id": "int", "hex": "str",
             "format": "str", "ascii": "str", "bin": "str", "oct": "str"}
    STR_METHODS = {"join", "format", "strip", "lstrip", "rstrip", "lower", "upper", "replace", "title",
                   "casefold", "removeprefix", "removesuffix", "capitalize", "zfill"}
    BOOL_METHODS = {"startswith", "endswith", "isdigit", "isalpha", "isalnum", "isspace", "islower",
                    "isupper", "isidentifier", "isnumeric", "isdecimal", "is_file", "is_dir", "exists"}
    QUALIFIED = {"json.dumps": "str", "os.getcwd": "str", "os.path.join": "str", "os.path.exists": "bool",
                 "os.path.isfile": "bool", "os.path.isdir": "bool", "time.time": "float",
                 "time.perf_counter": "float", "time.monotonic": "float", "math.sqrt": "float",
                 "uuid.uuid4": "uuid.UUID", "hashlib.sha256": "hashlib._Hash"}

    def __init__(self, env, resolver, allow_604):
        self.env = env
        self.r = resolver
        self.allow_604 = allow_604

    def infer(self, e):
        if isinstance(e, ast.Constant):
            if e.value is None or e.value is Ellipsis:
                return "None" if e.value is None else None
            return type(e.value).__name__
        if isinstance(e, ast.JoinedStr):
            return "str"
        if isinstance(e, ast.Compare):
            return "bool"
        if isinstance(e, ast.UnaryOp):
            if isinstance(e.op, ast.Not):
                return "bool"
            t = self.infer(e.operand)
            return t if t in ("int", "float", "complex") else None
        if isinstance(e, ast.BoolOp):
            parts = [self.infer(v) for v in e.values]
            return None if None in parts else join_types(parts, self.allow_604)
        if isinstance(e, ast.BinOp):
            lt, rt = self.infer(e.left), self.infer(e.right)
            if lt == "str" and (isinstance(e.op, ast.Mod) or (isinstance(e.op, ast.Add) and rt == "str")):
                return "str"
            if isinstance(e.op, ast.Mult) and {lt, rt} == {"str", "int"}:
                return "str"
            nums = ("int", "float")
            if lt in nums and rt in nums:
                if isinstance(e.op, ast.Div) or "float" in (lt, rt):
                    return "float"
                return "int" if not isinstance(e.op, ast.Pow) else None
            return None
        if isinstance(e, ast.IfExp):
            a, b = self.infer(e.body), self.infer(e.orelse)
            return None if None in (a, b) else join_types([a, b], self.allow_604)
        if isinstance(e, (ast.List, ast.Set)):
            kind = "list" if isinstance(e, ast.List) else "set"
            parts = [self.infer(x) for x in e.elts]
            if not parts or None in parts or any(isinstance(x, ast.Starred) for x in e.elts):
                return None
            return "%s[%s]" % (kind, join_types(parts, self.allow_604))
        if isinstance(e, ast.Tuple):
            parts = [self.infer(x) for x in e.elts]
            if None in parts or any(isinstance(x, ast.Starred) for x in e.elts):
                return None
            return "tuple[%s]" % ", ".join(parts) if parts else "tuple[()]"
        if isinstance(e, ast.Dict):
            if not e.keys or None in e.keys:
                return None
            ks, vs = [self.infer(k) for k in e.keys], [self.infer(v) for v in e.values]
            if None in ks:
                return None
            vt = join_types(vs, self.allow_604) if None not in vs else ("object" if ks == ["str"] * len(ks) else None)
            return "dict[%s, %s]" % (join_types(ks, self.allow_604), vt) if vt else None
        if isinstance(e, (ast.ListComp, ast.SetComp)):
            t = self.infer(e.elt)
            return ("list[%s]" if isinstance(e, ast.ListComp) else "set[%s]") % t if t else None
        if isinstance(e, ast.Name):
            return self.env.get(e.id)
        if isinstance(e, ast.Call):
            f = e.func
            if isinstance(f, ast.Name) and self.env.get(f.id) == "type[Self]":
                return "Self"
            if isinstance(f, ast.Name) and f.id in self.CALLS and f.id not in self.r.names:
                if f.id == "round":
                    return None
                return self.CALLS[f.id]
            q = self.r.qualname(f)
            if q in self.QUALIFIED:
                return self.QUALIFIED[q]
            if isinstance(f, ast.Attribute):
                if f.attr in self.BOOL_METHODS:
                    return "bool"
                if f.attr in self.STR_METHODS and self.infer(f.value) == "str":
                    return "str"
        return None


class Auditor(ast.NodeVisitor):
    def __init__(self, source, path, target, ignore):
        self.source = source
        self.path = path
        self.target = target
        self.ignore = ignore
        self.tree = ast.parse(source, filename=path)
        self.r = Resolver(self.tree)
        self.future = any(isinstance(n, ast.ImportFrom) and n.module == "__future__"
                          and any(a.name == "annotations" for a in n.names) for n in self.tree.body)
        self.deferred = self.future or target >= (3, 14)
        self.functions = []
        self.findings = []
        self.stack = []        # enclosing class/function nodes

    # -- helpers ---------------------------------------------------------
    def add(self, rule, node, message, suggestion=None, original=None, function=None):
        if rule in self.ignore:
            return
        self.findings.append({"rule": rule, "severity": SEVERITY[rule], "line": node.lineno,
                              "col": node.col_offset + 1, "function": function, "message": message,
                              "original": original, "suggestion": suggestion})

    def qual(self, name):
        return ".".join([n.name for n in self.stack] + [name])

    def modernize(self, node, deferred):
        allow_604 = self.target >= (3, 10) or deferred
        m = Modernizer(self.r, allow_604)
        new = m.visit(ast.parse(ast.unparse(node), mode="eval").body)
        text = ast.unparse(new)
        if m.rules and not deferred and self.target < (3, 14) and forward_refs_in_union(new):
            text = '"%s"' % ast.unparse(Unquote().visit(new)).replace('"', "'")
        return text, m.rules, m.imports

    def check_type_expr(self, node, deferred, context, function=None):
        """Report legacy syntax and Any inside one type expression."""
        quoted = isinstance(node, ast.Constant) and isinstance(node.value, str)
        if quoted:
            try:
                inner = ast.parse(node.value, mode="eval").body
            except SyntaxError:
                return
            for n in ast.walk(inner):
                ast.copy_location(n, node)
            node = inner
            deferred = True
        for n in ast.walk(node):
            if isinstance(n, (ast.Name, ast.Attribute)) and self.r.typing_name(n) == "Any":
                self.add("any-usage", node, "Any in %s disables checking; prefer object, a TypedDict/Protocol, "
                         "a TypeVar, or a JSON alias" % context, original=src_of(self.source, node),
                         function=function)
                break
        text, rules, imports = self.modernize(node, deferred)
        if quoted:
            text = '"%s"' % text.replace('"', "'")
        if rules:
            original = src_of(self.source, node)
            if text != original and text != ast.unparse(node):
                msg = "%s in %s" % (", ".join(rules), context)
                if imports:
                    msg += " (needs: %s)" % "; ".join(imports)
                self.add(rules[0], node, msg, suggestion=text, original=original, function=function)

    def class_is_runtime(self):
        for n in reversed(self.stack):
            if isinstance(n, ast.ClassDef):
                return any((getattr(b, "id", None) or getattr(b, "attr", "")) in PYDANTIC_BASES for b in n.bases)
            return False
        return False

    # -- imports ---------------------------------------------------------
    def visit_ImportFrom(self, node):
        if node.module not in TYPING_MODULES or node.level:
            return
        moved, keep, notes, typing_moves = {}, [], [], []
        for a in node.names:
            name, shown = a.name, a.name + (" as " + a.asname if a.asname else "")
            if name in BUILTIN:
                notes.append("%s -> %s" % (name, BUILTIN[name]))
            elif name in COLLECTIONS:
                moved.setdefault("collections", []).append(COLLECTIONS[name])
                notes.append("%s -> collections.%s" % (name, COLLECTIONS[name]))
            elif name in CONTEXTLIB:
                moved.setdefault("contextlib", []).append(CONTEXTLIB[name])
                notes.append("%s -> contextlib.%s" % (name, CONTEXTLIB[name]))
            elif name in RE_NAMES:
                notes.append("%s -> re.%s" % (name, name))
            elif name in ABC:
                moved.setdefault("collections.abc", []).append("Set as AbstractSet" if name == "AbstractSet" else shown)
                notes.append("%s -> collections.abc" % name)
            elif name in ("Optional", "Union") and self.target >= (3, 10):
                notes.append("%s -> X | Y syntax" % name)
            elif node.module == "typing_extensions" and name in BACKPORTS and self.target >= BACKPORTS[name]:
                typing_moves.append(shown)
                notes.append("%s is in typing since %d.%d" % ((name,) + BACKPORTS[name]))
            else:
                keep.append(shown)
        if not notes:
            return
        lines = ["from %s import %s" % (mod, ", ".join(names)) for mod, names in sorted(moved.items())]
        if node.module == "typing":
            keep = keep + typing_moves
        elif typing_moves:
            lines.append("from typing import " + ", ".join(typing_moves))
        if keep:
            lines.append("from %s import %s" % (node.module, ", ".join(keep)))
        rule = "legacy-backport" if node.module == "typing_extensions" and typing_moves and len(typing_moves) == len(notes) \
            else "legacy-import"
        self.add(rule, node, "import from %s: %s" % (node.module, "; ".join(notes)),
                 suggestion="\n".join(lines) or "(remove the import)", original=src_of(self.source, node))

    # -- definitions -----------------------------------------------------
    def visit_ClassDef(self, node):
        for d in node.decorator_list:
            self.visit(d)
        params, others = [], []
        for b in node.bases:
            tn = self.r.typing_name(b.value) if isinstance(b, ast.Subscript) else None
            if tn in ("Generic", "Protocol") and self.target >= (3, 12):
                sl = b.slice
                params += [ast.unparse(x) for x in (sl.elts if isinstance(sl, ast.Tuple) else [sl])]
                if tn == "Protocol":
                    others.append(ast.unparse(b.value))
            else:
                others.append(src_of(self.source, b))
                self.visit_expr(b, False)
        if params:
            sugg = "class %s[%s]%s:" % (node.name, ", ".join(params), "(%s)" % ", ".join(others) if others else "")
            self.add("legacy-typevar", node, "Generic[...]/Protocol[...] base: use PEP 695 type parameters (3.12+)",
                     suggestion=sugg, original="class %s(...)" % node.name)
        for k in node.keywords:
            self.visit_expr(k.value, False)
        self.stack.append(node)
        for s in node.body:
            self.visit(s)
        self.stack.pop()

    def visit_FunctionDef(self, node):
        self.audit_function(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def audit_function(self, node):
        qual = self.qual(node.name)
        parent = self.stack[-1] if self.stack else None
        decos = {getattr(d, "id", None) or getattr(d, "attr", None) for d in node.decorator_list}
        is_method = isinstance(parent, ast.ClassDef) and "staticmethod" not in decos
        a = node.args
        positional = a.posonlyargs + a.args
        pos_defaults = [None] * (len(positional) - len(a.defaults)) + list(a.defaults)
        params = list(zip(positional, pos_defaults))
        if a.vararg:
            params.append((a.vararg, None))
        params += list(zip(a.kwonlyargs, a.kw_defaults))
        if a.kwarg:
            params.append((a.kwarg, None))
        skipped = None
        if is_method and positional:
            skipped = positional[0].arg
            params = params[1:]
        prefix = {id(a.vararg): "*", id(a.kwarg): "**"}

        env = {}
        if skipped and "classmethod" not in decos:
            env[skipped] = "Self"
        elif skipped:
            env[skipped] = "type[Self]"
        allow_604 = self.target >= (3, 10) or self.deferred
        inf = Inferer(env, self.r, allow_604)
        missing, annotated = [], 0
        for arg, default in params:
            shown = prefix.get(id(arg), "") + arg.arg
            if arg.annotation is not None:
                annotated += 1
                env[arg.arg] = self.annotation_text(arg.annotation) if not prefix.get(id(arg)) else None
                self.check_type_expr(arg.annotation, self.deferred, "parameter '%s' of %s" % (arg.arg, qual), qual)
                self.check_default(arg, default, qual)
            else:
                sugg, note = self.suggest_param(arg, default, inf)
                missing.append({"name": shown, "suggestion": sugg, "note": note})
                self.add("missing-param", arg, "%s: parameter '%s' has no annotation%s" % (
                    qual, shown, "" if sugg else (" (" + note + ")" if note else "")),
                    suggestion=sugg, function=qual)
                if default is not None and self.is_mutable(default):
                    self.add("mutable-default", default, "%s: mutable default for '%s' is shared across calls"
                             % (qual, arg.arg), suggestion="%s: <type> | None = None  # then: if %s is None: %s = %s"
                             % (arg.arg, arg.arg, arg.arg, src_of(self.source, default)), function=qual)
        for _, default in params:
            if default is not None:
                self.visit_expr(default, False)
        for d in node.decorator_list:
            self.visit_expr(d, False)

        ret = {"annotated": node.returns is not None, "suggestion": None, "note": None}
        if node.returns is not None:
            self.check_type_expr(node.returns, self.deferred, "return of %s" % qual, qual)
        else:
            ret["suggestion"], ret["note"] = self.suggest_return(node, inf, decos, parent)
            note = ret["note"]
            self.add("missing-return", node, "%s: return type not annotated%s" % (
                qual, "" if ret["suggestion"] else (" (" + note + ")" if note else "")),
                suggestion=("-> " + ret["suggestion"]) if ret["suggestion"] else None, function=qual)

        self.functions.append({"name": qual, "line": node.lineno, "async": isinstance(node, ast.AsyncFunctionDef),
                               "params_total": len(params), "params_annotated": annotated,
                               "missing_params": missing, "return": ret})
        self.stack.append(node)
        for s in node.body:
            self.visit(s)
        self.stack.pop()

    @staticmethod
    def is_mutable(e):
        if isinstance(e, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)):
            return True
        return isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and \
            e.func.id in ("list", "dict", "set", "defaultdict", "deque", "OrderedDict", "Counter", "bytearray")

    def annotation_text(self, ann):
        """Modernised text of an annotation, with a string annotation unquoted."""
        if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
            try:
                ann = ast.parse(ann.value, mode="eval").body
            except SyntaxError:
                return ann.value
            return self.modernize(ann, True)[0]
        return self.modernize(ann, self.deferred)[0]

    def allows_none(self, ann):
        """True if None is a member of the annotation's top-level union (or it is Any/object/a TypeVar-free str)."""
        if isinstance(ann, ast.Constant):
            if ann.value is None:
                return True
            if isinstance(ann.value, str):
                try:
                    return self.allows_none(ast.parse(ann.value, mode="eval").body)
                except SyntaxError:
                    return True
            return False
        if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
            return self.allows_none(ann.left) or self.allows_none(ann.right)
        name = self.r.typing_name(ann.value if isinstance(ann, ast.Subscript) else ann)
        if name in ("Any", "Optional") or (isinstance(ann, ast.Name) and ann.id == "object"):
            return True
        if isinstance(ann, ast.Subscript) and name in ("Union", "Annotated"):
            sl = ann.slice
            elts = sl.elts if isinstance(sl, ast.Tuple) else [sl]
            return any(self.allows_none(e) for e in (elts if name == "Union" else elts[:1]))
        return False

    def check_default(self, arg, default, qual):
        if default is None:
            return
        ann_src = src_of(self.source, arg.annotation)
        ann = arg.annotation
        modern = self.annotation_text(ann)
        quoted = isinstance(ann, ast.Constant) and isinstance(ann.value, str)
        if isinstance(default, ast.Constant) and default.value is None:
            if self.allows_none(ann):
                return
            fixed = "%s | None" % modern if self.target >= (3, 10) or self.deferred or quoted else "Optional[%s]" % modern
            fixed = '"%s"' % fixed if quoted else fixed
            self.add("implicit-optional", arg, "%s: '%s' defaults to None but is annotated %s (implicit Optional "
                     "is rejected by mypy and pyright)" % (qual, arg.arg, ann_src),
                     suggestion="%s: %s = None" % (arg.arg, fixed), original="%s: %s = None" % (arg.arg, ann_src),
                     function=qual)
            return
        if self.is_mutable(default):
            fixed = "%s | None" % modern if self.target >= (3, 10) or self.deferred or quoted else "Optional[%s]" % modern
            fixed = '"%s"' % fixed if quoted else fixed
            self.add("mutable-default", default, "%s: mutable default for '%s' is created once and shared "
                     "across calls" % (qual, arg.arg),
                     suggestion="%s: %s = None  # then: if %s is None: %s = %s" % (
                         arg.arg, fixed, arg.arg, arg.arg, src_of(self.source, default)),
                     original="%s: %s = %s" % (arg.arg, ann_src, src_of(self.source, default)), function=qual)
            return
        if isinstance(ann, ast.Name) and isinstance(default, (ast.Constant, ast.UnaryOp)):
            val = default.operand if isinstance(default, ast.UnaryOp) else default
            if not isinstance(val, ast.Constant):
                return
            got = type(val.value).__name__
            ok = {"int": {"int", "bool"}, "float": {"int", "float"}, "complex": {"int", "float", "complex"},
                  "str": {"str"}, "bytes": {"bytes"}, "bool": {"bool"}}
            if ann.id in ok and got not in ok[ann.id]:
                self.add("default-mismatch", default, "%s: '%s' is annotated %s but defaults to %s %s"
                         % (qual, arg.arg, ann.id, got, src_of(self.source, default)),
                         suggestion=self.mismatch_fix(arg.arg, ann.id, val.value), function=qual)

    @staticmethod
    def mismatch_fix(name, ann, value):
        """Coerce a quoted number like "0.7" to the annotated type; otherwise say which side to change."""
        if isinstance(value, str) and ann in ("int", "float", "complex"):
            try:
                return "%s: %s = %r" % (name, ann, {"int": int, "float": float, "complex": complex}[ann](value))
            except ValueError:
                pass
        if ann == "bool" and isinstance(value, (int, str)):
            return "%s: bool = %r" % (name, bool(value) if isinstance(value, int) else value.lower() == "true")
        return "change the default to a %s, or the annotation to %s" % (ann, type(value).__name__)

    def suggest_param(self, arg, default, inf):
        if default is None:
            return None, "no default to infer from"
        if isinstance(default, ast.Constant) and default.value is None:
            t = "<T> | None" if inf.allow_604 else "Optional[<T>]"
            return "%s: %s = None" % (arg.arg, t), "default is None: fill in <T>"
        if self.is_mutable(default):
            return None, "mutable default: use None"
        t = inf.infer(default)
        if t and isinstance(default, ast.Tuple) and default.elts:
            parts = {inf.infer(x) for x in default.elts}
            if len(parts) == 1:
                t = "tuple[%s, ...]" % parts.pop()
        if t:
            return "%s: %s = %s" % (arg.arg, t, src_of(self.source, default)), None
        return None, "default is not a literal"

    def suggest_return(self, node, inf, decos, parent):
        body = node.body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            body = body[1:]
        nodes = list(walk_scope(body))
        yields = [n for n in nodes if isinstance(n, (ast.Yield, ast.YieldFrom))]
        returns = [n for n in nodes if isinstance(n, ast.Return)]
        is_async = isinstance(node, ast.AsyncFunctionDef)
        stub = all(isinstance(s, ast.Pass) or (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
                                               and s.value.value is Ellipsis) for s in body)
        protocolish = isinstance(parent, ast.ClassDef) and any(
            self.r.typing_name(b.value if isinstance(b, ast.Subscript) else b) == "Protocol" for b in parent.bases)
        if node.name in ("__init__", "__post_init__", "__init_subclass__", "__del__", "__set__", "__delete__",
                         "__setattr__", "__delattr__", "__setitem__", "__delitem__", "setUp", "tearDown"):
            return "None", None
        if stub and (decos & {"abstractmethod", "overload"} or protocolish or any(
                isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and s.value.value is Ellipsis
                for s in body)):
            return None, "stub/abstract body: annotate the intended type"
        if len(body) == 1 and isinstance(body[0], ast.Raise):
            exc = body[0].exc
            name = getattr(exc.func if isinstance(exc, ast.Call) else exc, "id", "")
            if name == "NotImplementedError":
                return None, "abstract body: annotate the intended type"
            return "NoReturn", None
        if yields:
            ytypes = [inf.infer(y.value) if isinstance(y, ast.Yield) and y.value else
                      ("None" if isinstance(y, ast.Yield) else None) for y in yields]
            kind = "AsyncIterator" if is_async else "Iterator"
            if None in ytypes:
                return None, "generator: annotate as %s[<yield type>] (from collections.abc)" % kind
            ret_vals = [r for r in returns if r.value is not None]
            yt = join_types(ytypes, inf.allow_604)
            if ret_vals and not is_async:
                rt = [inf.infer(r.value) for r in ret_vals]
                return ("Generator[%s, None, %s]" % (yt, join_types(rt, inf.allow_604)), None) if None not in rt \
                    else (None, "generator with return value: Generator[%s, None, <R>]" % yt)
            return "%s[%s]" % (kind, yt), None
        types = []
        for r in returns:
            t = "None" if r.value is None else inf.infer(r.value)
            if t is None:
                return None, "return value(s) not inferable from literals"
            types.append(t)
        if not always_exits(body):
            types.append("None")
        result = join_types(types, inf.allow_604) if types else "None"
        if "Self" in result and self.target < (3, 11):
            return result, "Self needs typing_extensions before 3.11"
        return result, None

    # -- other statements / runtime expressions --------------------------
    def visit_AnnAssign(self, node):
        in_function = any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in self.stack)
        tname = self.r.typing_name(node.annotation)
        target = src_of(self.source, node.target)
        if tname == "TypeAlias" and node.value is not None:
            if self.target >= (3, 12):
                text, _, imports = self.modernize(node.value, True)
                self.add("legacy-alias", node, "explicit TypeAlias: use the 3.12 `type` statement (lazily "
                         "evaluated, supports forward refs and type params)%s" % (
                             " (needs: %s)" % "; ".join(imports) if imports else ""),
                         suggestion="type %s = %s" % (target, text), original=src_of(self.source, node))
            else:
                self.check_type_expr(node.value, False, "type alias %s" % target)
            return
        deferred = in_function or (self.deferred and not self.class_is_runtime())
        self.check_type_expr(node.annotation, deferred, "annotation of %s" % target,
                             self.qual("") .rstrip(".") or None)
        if node.value is not None:
            self.visit_expr(node.value, False)

    def visit_Assign(self, node):
        v = node.value
        if not self.stack and isinstance(v, ast.Call) and self.target >= (3, 12) and \
                self.r.typing_name(v.func) in ("TypeVar", "ParamSpec", "TypeVarTuple") and len(node.targets) == 1:
            kind = self.r.typing_name(v.func)
            name = src_of(self.source, node.targets[0])
            if kind == "ParamSpec":
                tp = "**" + name
            elif kind == "TypeVarTuple":
                tp = "*" + name
            else:
                bound = [k.value for k in v.keywords if k.arg == "bound"]
                cons = v.args[1:]
                tp = name
                if bound:
                    tp += ": " + self.modernize(bound[0], True)[0]
                elif cons:
                    tp += ": (%s)" % ", ".join(self.modernize(c, True)[0] for c in cons)
                default = [k.value for k in v.keywords if k.arg == "default"]
                if default and self.target >= (3, 13):
                    tp += " = " + self.modernize(default[0], True)[0]
            self.add("legacy-typevar", node, "module-level %s: declare it inline with PEP 695 type parameters "
                     "(3.12+), scoped to the class/function that uses it" % kind,
                     suggestion="def fn[%s](...) / class Name[%s]: ..." % (tp, tp), original=src_of(self.source, node))
            return
        targets = ", ".join(src_of(self.source, t) for t in node.targets)
        self.visit_expr(v, False, "assignment to " + targets)

    def visit_expr(self, node, deferred, context="expression"):
        """Scan a runtime expression for legacy typing constructs (aliases, cast(), TypeVar bounds...)."""
        stack = [node]
        while stack:
            n = stack.pop()
            if isinstance(n, (ast.Subscript, ast.Name, ast.Attribute)) and isinstance(getattr(n, "ctx", None), ast.Load):
                head = n.value if isinstance(n, ast.Subscript) else n
                tn = self.r.typing_name(head)
                if tn and (tn in BUILTIN or tn in COLLECTIONS or tn in CONTEXTLIB or tn in RE_NAMES or
                           tn in ("Optional", "Union") or (tn in ABC and isinstance(head, ast.Attribute)) or tn == "Any"):
                    self.check_type_expr(n, deferred, context)
                    continue
            stack.extend(ast.iter_child_nodes(n))

    def generic_visit(self, node):
        if isinstance(node, ast.expr):
            self.visit_expr(node, False)
            return
        for child in ast.iter_child_nodes(node):
            self.visit(child)

    def visit_Import(self, node):
        pass


def pct(a, b):
    return round(100.0 * a / b, 1) if b else 100.0


def audit_source(source, path, target, ignore):
    aud = Auditor(source, path, target, ignore)
    aud.visit(aud.tree)
    aud.findings.sort(key=lambda f: (f["line"], f["col"], f["rule"]))
    return aud


def coverage(functions):
    pt = sum(f["params_total"] for f in functions)
    pa = sum(f["params_annotated"] for f in functions)
    rt = len(functions)
    ra = sum(f["return"]["annotated"] for f in functions)
    return {"functions": rt, "params_annotated": pa, "params_total": pt, "params_pct": pct(pa, pt),
            "returns_annotated": ra, "returns_total": rt, "returns_pct": pct(ra, rt),
            "overall_annotated": pa + ra, "overall_total": pt + rt, "overall_pct": pct(pa + ra, pt + rt)}


def collect_paths(paths):
    out = []
    for p in paths:
        if p == "-" or os.path.isfile(p):
            out.append((p, True))
        elif os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in (
                    "__pycache__", "node_modules", "venv", ".venv", "build", "dist", "site-packages"))
                out += [(os.path.join(root, f), False) for f in sorted(files) if f.endswith((".py", ".pyi"))]
        else:
            raise OSError("no such file or directory: %s" % p)
    return out


def fmt_cov(c):
    return ("params %d/%d (%.1f%%), returns %d/%d (%.1f%%), overall %d/%d (%.1f%%)" % (
        c["params_annotated"], c["params_total"], c["params_pct"], c["returns_annotated"], c["returns_total"],
        c["returns_pct"], c["overall_annotated"], c["overall_total"], c["overall_pct"]))


def print_text(results, total, target, gate):
    for r in results:
        print("== %s (target %d.%d)" % ((r["file"],) + target))
        print("Coverage: " + fmt_cov(r["coverage"]))
        incomplete = [f for f in r["functions"]
                      if f["missing_params"] or not f["return"]["annotated"]]
        if incomplete:
            print("\nFunctions missing annotations (%d of %d):" % (len(incomplete), len(r["functions"])))
            for f in incomplete:
                miss = [m["name"] for m in f["missing_params"]] + ([] if f["return"]["annotated"] else ["return"])
                print("  L%-4d %s%s  [missing: %s]" % (f["line"], "async " if f["async"] else "", f["name"],
                                                       ", ".join(miss)))
                for m in f["missing_params"]:
                    if m["suggestion"]:
                        print("         %-14s -> %s" % (m["name"], m["suggestion"]))
                    elif m["note"]:
                        print("         %-14s    (%s)" % (m["name"], m["note"]))
                rt = f["return"]
                if not rt["annotated"]:
                    if rt["suggestion"]:
                        print("         %-14s -> %s%s" % ("return", rt["suggestion"],
                                                            "  (%s)" % rt["note"] if rt["note"] else ""))
                    elif rt["note"]:
                        print("         %-14s    (%s)" % ("return", rt["note"]))
        other = [f for f in r["findings"] if f["rule"] not in ("missing-param", "missing-return")]
        if other:
            print("\nIssues (%d):" % len(other))
            for f in other:
                print("  L%-4d [%s] %s" % (f["line"], f["rule"], f["message"]))
                if f["original"]:
                    print("         was: " + f["original"].replace("\n", "\n              "))
                if f["suggestion"]:
                    print("         fix: " + f["suggestion"].replace("\n", "\n              "))
        if not incomplete and not other:
            print("No findings: fully annotated, no legacy typing for this target.")
        print()
    if len(results) > 1:
        print("TOTAL (%d files): %s" % (len(results), fmt_cov(total)))
    if gate is not None:
        status = "PASS" if total["overall_pct"] >= gate else "FAIL"
        print("Coverage gate: %s (overall %.1f%%, minimum %s%%)" % (status, total["overall_pct"], gate))


def parse_version(s):
    try:
        major, minor = (int(x) for x in s.split("."))
    except ValueError:
        raise argparse.ArgumentTypeError("expected a version like 3.10, got %r" % s)
    if (major, minor) < (3, 9) or major != 3:
        raise argparse.ArgumentTypeError("target version must be 3.9 or newer, got %s" % s)
    return major, minor


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="Python file(s) or directories, or - for stdin")
    ap.add_argument("--target-version", type=parse_version, default=(3, 10), metavar="X.Y",
                    help="lowest Python version the code must run on (default 3.10, minimum 3.9)")
    ap.add_argument("--min-coverage", type=float, metavar="N",
                    help="exit 1 if overall annotation coverage is below N percent")
    ap.add_argument("--strict", action="store_true", help="exit 1 if there is any finding")
    ap.add_argument("--ignore", default="", metavar="RULES", help="comma-separated rule ids to skip")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()
    ignore = {x.strip() for x in args.ignore.split(",") if x.strip()}
    unknown = ignore - set(SEVERITY)
    if unknown:
        ap.error("unknown rule id(s) for --ignore: %s" % ", ".join(sorted(unknown)))

    try:
        files = collect_paths(args.paths)
    except OSError as e:
        print("error: %s" % e, file=sys.stderr)
        sys.exit(2)
    results, all_functions = [], []
    skipped = 0
    for path, explicit in files:
        try:
            if path == "-":
                source, name = sys.stdin.read(), "<stdin>"
            else:
                with open(path, encoding="utf-8") as fh:
                    source, name = fh.read(), path
            aud = audit_source(source, name, args.target_version, ignore)
        except SyntaxError as e:
            if not explicit:   # found while walking a directory: skip it, keep auditing the rest
                print("warning: skipped %s:%s: syntax error: %s" % (path, e.lineno, e.msg), file=sys.stderr)
                skipped += 1
                continue
            print("error: %s:%s: syntax error: %s" % (path, e.lineno, e.msg), file=sys.stderr)
            sys.exit(2)
        except (OSError, UnicodeDecodeError) as e:
            print("error: cannot read %s: %s" % (path, e), file=sys.stderr)
            sys.exit(2)
        results.append({"file": name, "coverage": coverage(aud.functions), "functions": aud.functions,
                        "findings": aud.findings})
        all_functions += aud.functions

    total = coverage(all_functions)
    n_findings = sum(len(r["findings"]) for r in results)
    gate_failed = args.min_coverage is not None and total["overall_pct"] < args.min_coverage
    if args.json:
        print(json.dumps({"target_version": "%d.%d" % args.target_version, "coverage": total,
                          "min_coverage": args.min_coverage, "gate_failed": gate_failed,
                          "finding_count": n_findings, "skipped_files": skipped, "files": results}, indent=2))
    else:
        print_text(results, total, args.target_version, args.min_coverage)
    sys.exit(1 if gate_failed or (args.strict and n_findings) else 0)


if __name__ == "__main__":
    main()
