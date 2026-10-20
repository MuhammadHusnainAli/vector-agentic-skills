#!/usr/bin/env python3
"""Convert boilerplate Python classes or JSON samples into dataclass code.

Two modes:

  class  Parse a .py file (never imports or runs it) and find classes whose
         __init__ only stores its parameters on self (plus simple defaults,
         None-sentinel mutable defaults, constant attributes and validation
         that can move to __post_init__). Prints the equivalent @dataclass:
         mutable defaults become field(default_factory=...), annotations are
         kept or inferred, hand-written __repr__/__eq__/__hash__/ordering
         methods that the decorator would generate are removed (fields they
         ignored get repr=False / compare=False / hash=False), other methods
         are kept verbatim. Classes it cannot convert safely are listed with
         the reason (rule ids S01..S10). Findings use rule ids DC001..DC020.

  json   Read a JSON sample (object, or list of objects) and generate nested
         typed classes: dataclasses with a from_dict() constructor (default),
         pydantic v2 models (--style pydantic) or TypedDicts (--style
         typeddict). Types are merged across list items, keys that are
         missing or null in any sample become Optional, keys are converted to
         valid snake_case identifiers with the original key kept as an alias.

Usage:
    python to_dataclass.py class models.py
    python to_dataclass.py class models.py --frozen --slots --kw-only
    python to_dataclass.py class models.py --json --strict   # exit 1 if any class is convertible
    cat models.py | python to_dataclass.py class -
    python to_dataclass.py json response.json --name ChatCompletion
    python to_dataclass.py json response.json --name ChatCompletion --style pydantic
    python to_dataclass.py json response.json --style typeddict --json

Exit codes: 0 ok, 1 convertible classes found with --strict, 2 usage, read
or parse error. Standard library only; generated code targets Python 3.9+
(KW_ONLY and slots=True need 3.10+, NotRequired needs 3.11+).
"""

import argparse
import ast
import json
import keyword
import re
import sys
import textwrap
from collections import OrderedDict

DATACLASS_DECORATORS = {
    "dataclass", "dataclasses.dataclass", "pydantic.dataclasses.dataclass", "attr.s", "attr.attrs",
    "attrs.define", "attrs.frozen", "attrs.mutable", "attr.define", "attr.frozen", "attr.mutable",
    "define", "frozen", "mutable", "attrs",
}
SPECIAL_BASES = {
    "BaseModel": "pydantic model: already declarative and validated",
    "BaseSettings": "pydantic-settings model: already declarative",
    "NamedTuple": "NamedTuple: already a declarative record",
    "TypedDict": "TypedDict: a typing-only dict shape, not a runtime class",
    "Enum": "Enum subclass", "IntEnum": "Enum subclass", "StrEnum": "Enum subclass",
    "Flag": "Enum subclass", "IntFlag": "Enum subclass",
    "Protocol": "Protocol: structural type, not a data container",
    "Struct": "msgspec.Struct: already declarative",
    "Model": "ORM model: fields are managed by the ORM",
    "DeclarativeBase": "SQLAlchemy model: fields are managed by the ORM",
}
MUTABLE_CALLS = {"list", "dict", "set", "bytearray", "defaultdict", "OrderedDict", "deque", "Counter",
                 "collections.defaultdict", "collections.OrderedDict", "collections.deque",
                 "collections.Counter"}
ARRAY_HINTS = ("ndarray", "np.", "numpy", "Tensor", "torch.", "jax", "DataFrame", "Series")


class Skip(Exception):
    def __init__(self, rule, line, reason):
        Exception.__init__(self, reason)
        self.rule, self.line, self.reason = rule, line, reason


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return base + "." + node.attr if base else node.attr
    if isinstance(node, ast.Call):
        return dotted(node.func)
    if isinstance(node, ast.Subscript):
        return dotted(node.value)
    return ""


def names_in(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def self_attr(node, selfname):
    """Return attr name if node is `<selfname>.attr`, else None."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == selfname:
        return node.attr
    return None


def attrs_of(node, name):
    return [n.attr for n in ast.walk(node)
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == name
            and not (n.attr.startswith("__") and n.attr.endswith("__"))]


def is_mutable(node):
    if isinstance(node, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)):
        return True
    return isinstance(node, ast.Call) and dotted(node.func) in MUTABLE_CALLS


def factory_src(node):
    """default_factory expression for a mutable default node."""
    if isinstance(node, ast.List) and not node.elts:
        return "list"
    if isinstance(node, ast.Dict) and not node.keys:
        return "dict"
    if isinstance(node, ast.Call) and not node.args and not node.keywords:
        return dotted(node.func)
    return "lambda: " + ast.unparse(node)


def is_none(node):
    return isinstance(node, ast.Constant) and node.value is None


def infer_type(node):
    """Best-effort annotation string from a default/value expression, or None."""
    if isinstance(node, ast.Constant):
        if node.value is None:
            return "Optional[Any]"
        return type(node.value).__name__ if isinstance(node.value, (bool, int, float, str, bytes)) else None
    if isinstance(node, ast.UnaryOp) and isinstance(node.operand, ast.Constant):
        return infer_type(node.operand)
    if isinstance(node, (ast.List, ast.ListComp)):
        kinds = {infer_type(e) for e in getattr(node, "elts", [])}
        return "list[%s]" % kinds.pop() if len(kinds) == 1 and None not in kinds else "list"
    if isinstance(node, (ast.Dict, ast.DictComp)):
        return "dict"
    if isinstance(node, (ast.Set, ast.SetComp)):
        return "set"
    if isinstance(node, ast.Tuple):
        return "tuple"
    if isinstance(node, ast.Call):
        name = dotted(node.func)
        if name in ("list", "dict", "set", "tuple", "str", "int", "float", "bool", "frozenset", "bytes"):
            return name
        if name in MUTABLE_CALLS:
            return name
        last = name.rsplit(".", 1)[-1]
        if last[:1].isupper():
            return name
    if isinstance(node, ast.JoinedStr):
        return "str"
    return None


def strip_optional(ann):
    """Remove None from Optional[X] / X | None / Union[X, None] annotations (AST in, AST out)."""
    if isinstance(ann, ast.Subscript) and dotted(ann.value).rsplit(".", 1)[-1] == "Optional":
        return ann.slice
    if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
        if is_none(ann.right):
            return ann.left
        if is_none(ann.left):
            return ann.right
    if isinstance(ann, ast.Subscript) and dotted(ann.value).rsplit(".", 1)[-1] == "Union" \
            and isinstance(ann.slice, ast.Tuple):
        rest = [e for e in ann.slice.elts if not is_none(e)]
        if len(rest) == 1:
            return rest[0]
    return ann


def ann_allows_none(src):
    return bool(re.search(r"\bOptional\b|\bNone\b|\bAny\b|\bobject\b", src))


def is_super_init(stmt):
    """super().__init__(...) or Base.__init__(self, ...)."""
    return (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Attribute) and stmt.value.func.attr == "__init__")


def none_default_pattern(value, params):
    """Recognise `p or <mut>`, `p if p is not None else <mut>`, `<mut> if p is None else p`."""
    if isinstance(value, ast.BoolOp) and isinstance(value.op, ast.Or) and len(value.values) == 2:
        a, b = value.values
        if isinstance(a, ast.Name) and a.id in params and (is_mutable(b) or isinstance(b, ast.Constant)):
            return a.id, b
    if isinstance(value, ast.IfExp) and isinstance(value.test, ast.Compare) and len(value.test.ops) == 1 \
            and isinstance(value.test.left, ast.Name) and value.test.left.id in params \
            and is_none(value.test.comparators[0]):
        p, op = value.test.left.id, value.test.ops[0]
        if isinstance(op, ast.IsNot) and isinstance(value.body, ast.Name) and value.body.id == p:
            return p, value.orelse
        if isinstance(op, ast.Is) and isinstance(value.orelse, ast.Name) and value.orelse.id == p:
            return p, value.body
    return None


class PostInitRewriter(ast.NodeTransformer):
    """Rewrite stored-parameter names to self.<name>; for frozen classes turn
    self.x = v into object.__setattr__(self, "x", v)."""

    def __init__(self, selfname, stored, frozen):
        self.selfname, self.stored, self.frozen = selfname, stored, frozen

    def visit_Name(self, node):
        if node.id in self.stored:
            return ast.copy_location(ast.Attribute(value=ast.Name(id=self.selfname, ctx=ast.Load()),
                                                   attr=node.id, ctx=node.ctx), node)
        return node

    def _setattr(self, attr, value, like):
        call = ast.Call(func=ast.Attribute(value=ast.Name(id="object", ctx=ast.Load()), attr="__setattr__",
                                           ctx=ast.Load()),
                        args=[ast.Name(id=self.selfname, ctx=ast.Load()), ast.Constant(value=attr), value],
                        keywords=[])
        return ast.copy_location(ast.Expr(value=call), like)

    def visit_Assign(self, node):
        self.generic_visit(node)
        if self.frozen and len(node.targets) == 1:
            attr = self_attr(node.targets[0], self.selfname)
            if attr:
                return self._setattr(attr, node.value, node)
        return node

    def visit_AnnAssign(self, node):
        self.generic_visit(node)
        attr = self_attr(node.target, self.selfname)
        if self.frozen and attr and node.value is not None:
            return self._setattr(attr, node.value, node)
        return node

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        attr = self_attr(node.target, self.selfname)
        if self.frozen and attr:
            load = ast.Attribute(value=ast.Name(id=self.selfname, ctx=ast.Load()), attr=attr, ctx=ast.Load())
            return self._setattr(attr, ast.BinOp(left=load, op=node.op, right=node.value), node)
        return node


class ClassConverter:
    def __init__(self, cls, lines, opts):
        self.cls, self.lines, self.opts = cls, lines, opts
        self.notes = []          # (rule, line, message)
        self.removed = []        # method names dropped as redundant
        self.imports_dc = {"dataclass"}

    def note(self, rule, line, msg):
        self.notes.append({"rule": rule, "line": line, "message": msg})

    def source_of(self, node):
        start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
        seg = "\n".join(self.lines[start - 1:node.end_lineno])
        return textwrap.indent(textwrap.dedent(seg), "    ")

    # ------------------------------------------------------------------ analysis
    def check_class(self):
        cls = self.cls
        for d in cls.decorator_list:
            if dotted(d) in DATACLASS_DECORATORS:
                raise Skip("S01", cls.lineno, "already decorated with @%s" % dotted(d))
        for b in cls.bases:
            last = dotted(b).rsplit(".", 1)[-1]
            if last in SPECIAL_BASES:
                raise Skip("S07", cls.lineno, "inherits %s (%s)" % (dotted(b), SPECIAL_BASES[last]))
            if last.endswith(("Error", "Exception", "Warning")) or last in ("BaseException", "Exception"):
                raise Skip("S07", cls.lineno, "exception class (%s): a generated __init__ skips "
                           "BaseException.__init__, so args/str()/pickling change; keep it hand-written"
                           % dotted(b))
        for kw in cls.keywords:
            if kw.arg == "metaclass":
                raise Skip("S08", cls.lineno, "custom metaclass %s" % ast.unparse(kw.value))

    def analyze(self):
        self.check_class()
        cls, opts = self.cls, self.opts
        init = None
        for st in cls.body:
            if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if st.name == "__init__":
                    init = st
                elif st.name == "__new__":
                    raise Skip("S08", st.lineno, "defines __new__; construction is customised")
        if init is None:
            raise Skip("S02", cls.lineno, "no __init__ to convert (if the class only declares "
                       "annotations, add @dataclass directly)")
        if init.decorator_list:
            raise Skip("S08", init.lineno, "__init__ is decorated")
        a = init.args
        if a.vararg or a.kwarg:
            raise Skip("S03", init.lineno, "__init__ takes *%s/**%s; a dataclass needs an explicit "
                       "parameter list" % (a.vararg.arg if a.vararg else "", a.kwarg.arg if a.kwarg else ""))
        positional = list(a.posonlyargs) + list(a.args)
        if not positional:
            raise Skip("S08", init.lineno, "__init__ has no self parameter")
        selfname = positional[0].arg
        self.selfname = selfname
        params = OrderedDict()
        defaults = [None] * (len(positional) - len(a.defaults)) + list(a.defaults)
        for i, arg in enumerate(positional[1:], start=1):
            params[arg.arg] = {"ann": arg.annotation, "default": defaults[i], "kind":
                               "posonly" if i < len(a.posonlyargs) else "pos", "line": arg.lineno}
        for arg, d in zip(a.kwonlyargs, a.kw_defaults):
            params[arg.arg] = {"ann": arg.annotation, "default": d, "kind": "kwonly", "line": arg.lineno}
        if any(p["kind"] == "posonly" for p in params.values()):
            self.note("DC012", init.lineno, "positional-only parameters become positional-or-keyword "
                      "fields (dataclasses cannot express '/')")
        for n in ast.walk(init):
            if isinstance(n, (ast.Return, ast.Yield, ast.YieldFrom)) and not (
                    isinstance(n, ast.Return) and n.value is None and n is init.body[-1]):
                raise Skip("S09", n.lineno, "__init__ contains return/yield; control flow cannot move "
                           "into __post_init__ safely")

        stored = OrderedDict()   # attr -> {"param", "ann", "factory", "line"}
        consts = OrderedDict()   # attr -> {"value", "ann", "line"}
        none_fix = {}            # param -> mutable node (from `if p is None: p = []`)
        extra = []               # statements for __post_init__
        reassigned = {}          # param -> first line it is reassigned in extra code
        body = list(init.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            body = body[1:]
        expanded = []
        for st in body:   # self.a, self.b = a, b  ->  self.a = a; self.b = b
            if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Tuple) \
                    and isinstance(st.value, ast.Tuple) and len(st.targets[0].elts) == len(st.value.elts) \
                    and all(self_attr(t, selfname) for t in st.targets[0].elts) \
                    and all(isinstance(v, (ast.Name, ast.Constant)) for v in st.value.elts):
                expanded += [ast.copy_location(ast.Assign(targets=[t], value=v), st)
                             for t, v in zip(st.targets[0].elts, st.value.elts)]
            else:
                expanded.append(st)
        body = expanded
        for idx, st in enumerate(body):
            if is_super_init(st):
                if cls.bases:
                    raise Skip("S04", st.lineno, "calls %s; convert the base class to a dataclass first, "
                               "then inherit its fields instead of calling super().__init__()"
                               % ast.unparse(st.value.func))
                continue
            if isinstance(st, ast.If) and not st.orelse and len(st.body) == 1 and isinstance(st.test, ast.Compare) \
                    and isinstance(st.test.left, ast.Name) and st.test.left.id in params \
                    and len(st.test.ops) == 1 and isinstance(st.test.ops[0], ast.Is) \
                    and is_none(st.test.comparators[0]) and isinstance(st.body[0], ast.Assign) \
                    and len(st.body[0].targets) == 1 and isinstance(st.body[0].targets[0], ast.Name) \
                    and st.body[0].targets[0].id == st.test.left.id \
                    and is_none(params[st.test.left.id]["default"] or ast.Constant(value=0)) \
                    and is_mutable(st.body[0].value):
                none_fix[st.test.left.id] = st.body[0].value
                continue
            target, value, ann = None, None, None
            if isinstance(st, ast.Assign) and len(st.targets) == 1:
                target, value = self_attr(st.targets[0], selfname), st.value
            elif isinstance(st, ast.AnnAssign) and st.value is not None:
                target, value, ann = self_attr(st.target, selfname), st.value, st.annotation
            if target and target not in stored and target not in consts:
                if isinstance(value, ast.Name) and value.id in params:
                    p = value.id
                    if p != target:
                        raise Skip("S05", st.lineno, "self.%s = %s: attribute name differs from the parameter; "
                                   "a dataclass would rename the __init__ argument to '%s'" % (target, p, target))
                    stored[target] = {"param": p, "ann": ann, "factory": none_fix.get(p), "line": st.lineno,
                                      "idx": idx, "pattern": "if-none" if p in none_fix else None}
                    continue
                pat = none_default_pattern(value, params)
                if pat and is_none(params[pat[0]]["default"] or ast.Constant(value=0)):
                    p, fallback = pat
                    if p != target:
                        raise Skip("S05", st.lineno, "self.%s = %s ...: attribute name differs from the "
                                   "parameter" % (target, p))
                    stored[target] = {"param": p, "ann": ann, "factory": fallback, "line": st.lineno,
                                      "idx": idx, "pattern": "or"}
                    continue
                if not (names_in(value) & (set(params) | {selfname})) and not any(
                        isinstance(n, (ast.Lambda, ast.Await)) for n in ast.walk(value)):
                    consts[target] = {"value": value, "ann": ann, "line": st.lineno}
                    continue
            extra.append((idx, st))
            for n in ast.walk(st):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id in params:
                    reassigned.setdefault(n.id, (idx, n.lineno))

        stored_params = {v["param"] for v in stored.values()}
        for p, (idx, line) in reassigned.items():
            if p in stored_params:
                s = [v for v in stored.values() if v["param"] == p][0]
                if s["idx"] < idx:
                    raise Skip("S06", line, "parameter '%s' is reassigned after it was stored on self; the "
                               "stored and local values diverge" % p)
        self.params, self.stored, self.consts, self.extra = params, stored, consts, extra
        self.initvars = [p for p in params if p not in stored_params]
        if not stored and not self.initvars:
            raise Skip("S10", init.lineno, "__init__ stores no parameters on self; nothing to generate")

        # derived attributes assigned in extra statements
        self.derived = OrderedDict()
        for idx, st in extra:
            top_level = isinstance(st, (ast.Assign, ast.AnnAssign, ast.AugAssign))
            for n in ast.walk(st):
                tgt = None
                if isinstance(n, ast.Assign):
                    for t in n.targets:
                        tattr = self_attr(t, selfname)
                        if tattr and tattr not in stored and tattr not in consts and tattr not in self.derived:
                            self.derived[tattr] = {"ann": None, "value": n.value, "line": n.lineno,
                                                   "conditional": not (top_level and n is st)}
                elif isinstance(n, ast.AnnAssign):
                    tgt = self_attr(n.target, selfname)
                    if tgt and tgt not in stored and tgt not in consts and tgt not in self.derived:
                        self.derived[tgt] = {"ann": n.annotation, "value": n.value, "line": n.lineno,
                                             "conditional": not (top_level and n is st)}
        return self

    # ------------------------------------------------------------- generation
    def class_annotations(self):
        out = {}
        for st in self.cls.body:
            if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
                out[st.target.id] = st
        return out

    def build(self):
        cls, opts, selfname = self.cls, self.opts, self.selfname
        cls_ann = self.class_annotations()
        fields = []   # dicts: name, ann, default, factory, init, repr, compare, hash, kind, initvar
        for p, info in self.params.items():
            entry = {"name": p, "kind": info["kind"], "line": info["line"], "init": True, "repr": True,
                     "compare": True, "hash": None, "default": None, "factory": None, "initvar": p in self.initvars}
            st = [v for v in self.stored.values() if v["param"] == p]
            ann_node = info["ann"] or (st[0]["ann"] if st else None)
            if ann_node is None and p in cls_ann:
                ann_node = cls_ann[p].annotation
            default = info["default"]
            ann = ast.unparse(ann_node) if ann_node is not None else None
            if st and st[0]["factory"] is not None:
                fb = st[0]["factory"]
                if is_mutable(fb):
                    entry["factory"] = factory_src(fb)
                    if ann_node is not None:
                        ann = ast.unparse(strip_optional(ann_node))
                    else:
                        ann = infer_type(fb) or "Any"
                    self.note("DC002", st[0]["line"], "'%s=None' + %s becomes field(default_factory=%s); "
                              "note: passing None explicitly now stores None instead of a fresh container"
                              % (p, "'if %s is None'" % p if st[0]["pattern"] == "if-none" else "'%s or ...'" % p,
                                 entry["factory"]))
                else:
                    entry["default"] = ast.unparse(fb)
                    if ann_node is not None:
                        ann = ast.unparse(strip_optional(ann_node))
                    self.note("DC002", st[0]["line"], "'%s or %s' becomes a plain default %s; falsy values "
                              "passed by callers are no longer replaced" % (p, ast.unparse(fb), ast.unparse(fb)))
            elif default is not None:
                if is_mutable(default):
                    entry["factory"] = factory_src(default)
                    self.note("DC001", info["line"], "mutable default %s=%s was one object shared by every "
                              "instance; field(default_factory=%s) gives each instance its own"
                              % (p, ast.unparse(default), entry["factory"]))
                else:
                    entry["default"] = ast.unparse(default)
                    if isinstance(default, ast.Call):
                        self.note("DC018", info["line"], "default %s is evaluated once and shared; if it is "
                                  "mutable or unhashable use field(default_factory=...)" % ast.unparse(default))
                if ann is None:
                    ann = infer_type(default)
                    if ann:
                        self.note("DC007", info["line"], "annotation for '%s' inferred as %s from its default"
                                  % (p, ann))
                elif is_none(default) and not ann_allows_none(ann):
                    self.note("DC019", info["line"], "'%s: %s = None' made explicit as Optional[%s]" % (p, ann, ann))
                    ann = "Optional[%s]" % ann
            if ann is None:
                ann = "Any"
                self.note("DC007", info["line"], "no annotation for '%s'; used Any - replace with the real type" % p)
            entry["ann"] = ann
            fields.append(entry)

        if self.initvars:
            self.imports_dc.add("InitVar")
            self.note("DC013", self.cls.lineno, "parameter(s) %s are used only during construction; they "
                      "become InitVar pseudo-fields passed to __post_init__" % ", ".join(self.initvars))

        tail = []
        for name, c in self.consts.items():
            ann = ast.unparse(c["ann"]) if c["ann"] is not None else (
                ast.unparse(cls_ann[name].annotation) if name in cls_ann else infer_type(c["value"]) or "Any")
            e = {"name": name, "ann": ann, "init": False, "repr": True, "compare": True, "hash": None,
                 "default": None, "factory": None, "kind": "internal", "initvar": False, "line": c["line"]}
            if is_mutable(c["value"]) or isinstance(c["value"], ast.Call):
                e["factory"] = factory_src(c["value"]) if is_mutable(c["value"]) or not (
                    c["value"].args or c["value"].keywords) else "lambda: " + ast.unparse(c["value"])
            else:
                e["default"] = ast.unparse(c["value"])
                if is_none(c["value"]) and not ann_allows_none(ann):
                    e["ann"] = "Optional[%s]" % ann
            if name.startswith("_"):
                e["repr"] = e["compare"] = False
                self.note("DC014", c["line"], "internal attribute %s becomes field(init=False, repr=False, "
                          "compare=False)" % name)
            tail.append(e)
        for name, d in self.derived.items():
            ann = ast.unparse(d["ann"]) if d["ann"] is not None else (
                ast.unparse(cls_ann[name].annotation) if name in cls_ann else
                (infer_type(d["value"]) if d["value"] is not None else None) or "Any")
            e = {"name": name, "ann": ann, "init": False, "repr": True, "compare": True, "hash": None,
                 "default": None, "factory": None, "kind": "derived", "initvar": False, "line": d["line"]}
            if d["conditional"]:
                e["default"] = "None"
                if not ann_allows_none(ann):
                    e["ann"] = "Optional[%s]" % ann
                self.note("DC008", d["line"], "self.%s is only set conditionally; declared with default None so "
                          "repr/eq never hit a missing attribute" % name)
            if name.startswith("_"):
                e["repr"] = e["compare"] = False
            tail.append(e)
        self.fields, self.tail = fields, tail
        all_fields = fields + tail
        real = [f for f in all_fields if not f["initvar"]]
        fieldnames = [f["name"] for f in real]

        # ------------------------------------------------ class body scan
        options = OrderedDict()
        if opts.frozen:
            options["frozen"] = "True"
        if opts.kw_only:
            options["kw_only"] = "True"
        if opts.slots:
            options["slots"] = "True"
        methods = {st.name: st for st in cls.body if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef))}
        drop = set()
        decorators = [d for d in cls.decorator_list]
        had_eq = "__eq__" in methods

        r = methods.get("__repr__")
        if r is not None and self.redundant_repr(r, fieldnames):
            used = set(attrs_of(r, self.method_self(r)))
            hidden = [n for n in fieldnames if n not in used]
            for f in real:
                if f["name"] in hidden:
                    f["repr"] = False
            drop.add("__repr__")
            self.note("DC003", r.lineno, "hand-written __repr__ is generated by @dataclass%s; output format "
                      "becomes ClassName(field=value, ...)" % (
                          " (fields it left out get repr=False: %s)" % ", ".join(hidden) if hidden else ""))
        e = methods.get("__eq__")
        eq_fields = None
        if e is not None:
            eq_fields = self.redundant_eq(e, fieldnames)
            if eq_fields is not None:
                for f in real:
                    if f["name"] not in eq_fields:
                        f["compare"] = False
                drop.add("__eq__")
                self.note("DC004", e.lineno, "hand-written __eq__ is generated by @dataclass (compares %s); "
                          "dataclass eq also requires the exact same class, not isinstance()" % ", ".join(eq_fields))
                ne = methods.get("__ne__")
                if ne is not None and self.simple_ne(ne):
                    drop.add("__ne__")
        h = methods.get("__hash__")
        if h is not None and (not had_eq or "__eq__" in drop):
            hf = self.redundant_hash(h, fieldnames)
            if hf is not None:
                drop.add("__hash__")
                for f in real:
                    if f["compare"] and f["name"] not in hf:
                        f["hash"] = "False"
                if not opts.frozen:
                    options["unsafe_hash"] = "True"
                    self.note("DC005", h.lineno, "__hash__ over mutable fields -> unsafe_hash=True; prefer "
                              "--frozen so the hash cannot change while the object sits in a set/dict")
                else:
                    self.note("DC005", h.lineno, "frozen=True with eq=True generates __hash__ from the compared "
                              "fields; hand-written __hash__ removed")
        order_names = [n for n in ("__lt__", "__le__", "__gt__", "__ge__") if n in methods]
        total = [d for d in decorators if dotted(d).rsplit(".", 1)[-1] == "total_ordering"]
        if order_names and ("__eq__" in drop or not had_eq):
            cmp_fields = [f["name"] for f in real if f["compare"]]
            if all(self.tuple_compare(methods[n], cmp_fields) for n in order_names) and (
                    len(order_names) == 4 or (total and order_names == ["__lt__"]) or order_names == ["__lt__"]):
                drop.update(order_names)
                options["order"] = "True"
                decorators = [d for d in decorators if d not in total]
                self.note("DC006", methods[order_names[0]].lineno, "%s compare (%s) tuples in field order -> "
                          "order=True%s" % ("/".join(order_names), ", ".join(cmp_fields),
                                            " (functools.total_ordering removed)" if total else ""))
        if "__eq__" not in drop and not had_eq and not opts.frozen and "unsafe_hash" not in options:
            self.note("DC016", cls.lineno, "the original class compared and hashed by identity; @dataclass adds "
                      "field-wise __eq__ and sets __hash__ = None, so instances can no longer be dict keys or set "
                      "members. Use --frozen, or @dataclass(eq=False) to keep identity semantics")
        for f in real:
            if f["compare"] and any(hint in f["ann"] for hint in ARRAY_HINTS):
                f["compare"] = False
                self.note("DC017", f["line"], "'%s: %s' is an array/tensor: generated __eq__ would raise "
                          "'truth value of an array is ambiguous'; set compare=False" % (f["name"], f["ann"]))

        # class-level statements
        head, body_items, cls_doc = [], [], None
        for i, st in enumerate(cls.body):
            if i == 0 and isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) \
                    and isinstance(st.value.value, str):
                cls_doc = self.source_of(st)
                continue
            if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if st.name == "__init__" or st.name in drop:
                    continue
                body_items.append(self.source_of(st))
                continue
            if isinstance(st, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__slots__" for t in st.targets):
                options["slots"] = "True"
                self.note("DC009", st.lineno, "__slots__ replaced by slots=True (Python 3.10+); a manual __slots__ "
                          "conflicts with field defaults")
                continue
            if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
                n = st.target.id
                if n in [f["name"] for f in all_fields]:
                    continue   # merged into the field
                if dotted(st.annotation).rsplit(".", 1)[-1] == "ClassVar":
                    head.append(self.source_of(st))
                elif st.value is not None:
                    head.append("    %s: ClassVar[%s] = %s" % (n, ast.unparse(st.annotation), ast.unparse(st.value)))
                    self.note("DC010", st.lineno, "annotated class attribute '%s' would become a field; wrapped "
                              "in ClassVar" % n)
                else:
                    tail.append({"name": n, "ann": ast.unparse(st.annotation), "init": False, "repr": False,
                                 "compare": False, "hash": None, "default": None, "factory": None,
                                 "kind": "declared", "initvar": False, "line": st.lineno})
                continue
            head.append(self.source_of(st))

        # notes on remaining methods
        for st in cls.body:
            if not isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)) or st.name in drop or st.name == "__init__":
                continue
            if opts.frozen:
                me = self.method_self(st)
                for n in ast.walk(st):
                    targets = n.targets if isinstance(n, ast.Assign) else [n.target] if isinstance(
                        n, (ast.AugAssign, ast.AnnAssign)) else []
                    for t in targets:
                        if me and self_attr(t, me):
                            self.note("DC015", n.lineno, "%s() assigns self.%s; with frozen=True that raises "
                                      "FrozenInstanceError - return dataclasses.replace(self, ...) instead"
                                      % (st.name, self_attr(t, me)))
            if options.get("slots"):
                for d in st.decorator_list:
                    if dotted(d).rsplit(".", 1)[-1] == "cached_property":
                        self.note("DC009", st.lineno, "@cached_property needs an instance __dict__; it fails with "
                                  "slots=True")
                for n in ast.walk(st):
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "super" and not n.args:
                        self.note("DC009", n.lineno, "zero-argument super() inside a slots=True dataclass fails "
                                  "on Python 3.10-3.13 (the class is recreated); use super(%s, self)" % cls.name)

        # post_init
        post = None
        if self.extra:
            rw = PostInitRewriter(selfname, {v["param"] for v in self.stored.values()}, opts.frozen)
            stmts = [rw.visit(ast.fix_missing_locations(ast.parse(ast.unparse(st)).body[0]))
                     for _, st in self.extra]
            mod = ast.Module(body=stmts, type_ignores=[])
            ast.fix_missing_locations(mod)
            args = ", ".join([selfname] + self.initvars)
            post = "    def __post_init__(%s) -> None:\n%s" % (args, textwrap.indent(ast.unparse(mod), "        "))
            self.note("DC008", self.extra[0][1].lineno, "%d statement(s) of __init__ logic moved to __post_init__%s "
                      "(comments in that code are not preserved)" % (
                          len(self.extra), " using object.__setattr__ because the class is frozen" if opts.frozen else ""))
        elif self.initvars:
            post = "    def __post_init__(%s) -> None:\n        pass  # %s unused in the original __init__" % (
                ", ".join([selfname] + self.initvars), ", ".join(self.initvars))

        # field ordering: positional fields, KW_ONLY sentinel, kw-only fields, then init=False fields
        pos = [f for f in fields if f["kind"] != "kwonly"]
        kwo = [f for f in fields if f["kind"] == "kwonly"]
        field_lines = [self.render_field(f) for f in pos]
        if kwo:
            if opts.kw_only:
                field_lines += [self.render_field(f) for f in kwo]
            else:
                self.imports_dc.add("KW_ONLY")
                field_lines.append("    _: KW_ONLY")
                field_lines += [self.render_field(f) for f in kwo]
                self.note("DC011", kwo[0]["line"], "keyword-only parameters (after *) placed after the KW_ONLY "
                          "sentinel (Python 3.10+; on 3.9 use field order + keyword calls)")
        field_lines += [self.render_field(f) for f in tail]
        if opts.kw_only:
            self.note("DC011", cls.lineno, "kw_only=True: every field must now be passed by keyword - update "
                      "positional call sites")
        if (options.get("slots") or opts.kw_only) and not any(
                n["rule"] == "DC009" and "3.10" in n["message"] for n in self.notes):
            self.note("DC009", cls.lineno, "slots=True / kw_only=True require Python 3.10+")

        deco = "@dataclass" + ("(%s)" % ", ".join("%s=%s" % kv for kv in options.items()) if options else "")
        out = [("@" + ast.unparse(d)) for d in decorators] + [deco]
        bases = [ast.unparse(b) for b in cls.bases] + [ast.unparse(k) for k in cls.keywords]
        out.append("class %s%s:" % (cls.name, "(%s)" % ", ".join(bases) if bases else ""))
        blocks = []
        if cls_doc:
            blocks.append(cls_doc)
        if head:
            blocks.append("\n".join(head))
        blocks.append("\n".join(field_lines))
        if post:
            blocks.append(post)
        blocks += body_items
        code = "\n".join(out) + "\n" + "\n\n".join(blocks) + "\n"
        self.removed = sorted(drop)
        self.options = dict(options)
        self.code = code
        return code

    def render_field(self, f):
        if f["initvar"]:
            d = " = %s" % f["default"] if f["default"] is not None else ""
            if f["factory"]:
                d = " = None  # was a mutable default; build it in __post_init__"
            return "    %s: InitVar[%s]%s" % (f["name"], f["ann"], d)
        kwargs = []
        if f["factory"]:
            kwargs.append("default_factory=%s" % f["factory"])
        elif f["default"] is not None and (not f["init"] or not f["repr"] or not f["compare"] or f["hash"]):
            kwargs.append("default=%s" % f["default"])
        if not f["init"]:
            kwargs.append("init=False")
        if not f["repr"]:
            kwargs.append("repr=False")
        if not f["compare"]:
            kwargs.append("compare=False")
        if f["hash"]:
            kwargs.append("hash=%s" % f["hash"])
        if kwargs:
            self.imports_dc.add("field")
            return "    %s: %s = field(%s)" % (f["name"], f["ann"], ", ".join(kwargs))
        if f["default"] is not None:
            return "    %s: %s = %s" % (f["name"], f["ann"], f["default"])
        return "    %s: %s" % (f["name"], f["ann"])

    # ---------------------------------------------------- redundancy checks
    @staticmethod
    def method_self(fn):
        args = list(fn.args.posonlyargs) + list(fn.args.args)
        return args[0].arg if args else None

    @staticmethod
    def body_without_doc(fn):
        b = fn.body
        if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) and isinstance(b[0].value.value, str):
            b = b[1:]
        return b

    def redundant_repr(self, fn, fieldnames):
        me = self.method_self(fn)
        body = self.body_without_doc(fn)
        if len(body) != 1 or not isinstance(body[0], ast.Return) or body[0].value is None:
            return False
        used = set(attrs_of(body[0].value, me))
        allowed = {me, "type", "repr", "str", "format", self.cls.name}
        if not used or not used <= set(fieldnames) or not names_in(body[0].value) <= allowed:
            return False
        return isinstance(body[0].value, (ast.JoinedStr, ast.BinOp, ast.Call))

    def redundant_eq(self, fn, fieldnames):
        args = list(fn.args.posonlyargs) + list(fn.args.args)
        if len(args) != 2:
            return None
        me, other = args[0].arg, args[1].arg
        body = self.body_without_doc(fn)
        if not body or not isinstance(body[-1], ast.Return) or body[-1].value is None:
            return None
        for st in body[:-1]:
            if not (isinstance(st, ast.If) and isinstance(st.test, ast.UnaryOp)
                    and isinstance(st.test.op, ast.Not) and isinstance(st.test.operand, ast.Call)
                    and dotted(st.test.operand.func) == "isinstance"
                    and len(st.body) == 1 and isinstance(st.body[0], ast.Return)):
                return None
        expr = body[-1].value
        if not names_in(expr) <= {me, other}:
            return None
        mine, theirs = attrs_of(expr, me), attrs_of(expr, other)
        if not mine or set(mine) != set(theirs) or not set(mine) <= set(fieldnames):
            return None
        return [n for n in fieldnames if n in set(mine)]

    def simple_ne(self, fn):
        body = self.body_without_doc(fn)
        return len(body) == 1 and isinstance(body[0], ast.Return) and isinstance(body[0].value, ast.UnaryOp) \
            and isinstance(body[0].value.op, ast.Not)

    def redundant_hash(self, fn, fieldnames):
        me = self.method_self(fn)
        body = self.body_without_doc(fn)
        if len(body) != 1 or not isinstance(body[0], ast.Return) or not isinstance(body[0].value, ast.Call) \
                or dotted(body[0].value.func) != "hash":
            return None
        expr = body[0].value
        if not names_in(expr) <= {me, "hash", "tuple", "frozenset"}:
            return None
        used = attrs_of(expr, me)
        return used if used and set(used) <= set(fieldnames) else None

    def tuple_compare(self, fn, cmp_fields):
        args = list(fn.args.posonlyargs) + list(fn.args.args)
        if len(args) != 2:
            return False
        me, other = args[0].arg, args[1].arg
        body = self.body_without_doc(fn)
        ret = body[-1] if body else None
        if not isinstance(ret, ast.Return) or not isinstance(ret.value, ast.Compare) or len(ret.value.ops) != 1:
            return False
        left, right = ret.value.left, ret.value.comparators[0]
        if not (isinstance(left, ast.Tuple) and isinstance(right, ast.Tuple)):
            return False
        lattrs = [self_attr(e, me) for e in left.elts]
        rattrs = [self_attr(e, other) for e in right.elts]
        return lattrs == rattrs == cmp_fields


def iter_classes(body, prefix=""):
    for st in body:
        if isinstance(st, ast.ClassDef):
            yield prefix + st.name, st
            for item in iter_classes(st.body, prefix + st.name + "."):
                yield item


def run_class_mode(src, filename, opts):
    try:
        tree = ast.parse(src, filename=filename)
    except SyntaxError as e:
        raise UsageError("cannot parse %s: line %s: %s" % (filename, e.lineno, e.msg))
    lines = src.splitlines()
    converted, skipped, dc_imports, typing_imports = [], [], set(), set()
    for qual, cls in iter_classes(tree.body):
        conv = ClassConverter(cls, lines, opts)
        try:
            conv.analyze()
            code = conv.build()
        except Skip as s:
            skipped.append({"class": qual, "line": cls.lineno, "rule": s.rule, "reason": s.reason,
                            "at_line": s.line})
            continue
        try:
            ast.parse(code)
        except SyntaxError as e:
            skipped.append({"class": qual, "line": cls.lineno, "rule": "S10",
                            "reason": "generated code did not parse (%s); convert by hand" % e.msg,
                            "at_line": cls.lineno})
            continue
        dc_imports |= conv.imports_dc
        for name in ("Any", "ClassVar", "Optional", "Union"):
            if re.search(r"\b%s\b" % name, code):
                typing_imports.add(name)
        converted.append({"class": qual, "line": cls.lineno, "options": conv.options,
                          "removed_methods": conv.removed, "notes": sorted(conv.notes, key=lambda n: n["line"]),
                          "code": code})
    imports = ["from dataclasses import " + ", ".join(sorted(dc_imports, key=lambda n: (n != "dataclass", n)))] \
        if converted else []
    if typing_imports:
        imports.append("from typing import " + ", ".join(sorted(typing_imports)))
    return {"mode": "class", "file": filename, "imports": imports, "converted": converted, "skipped": skipped}


def print_class_report(res):
    print("%s: %d convertible class(es), %d skipped" % (res["file"], len(res["converted"]), len(res["skipped"])))
    if res["converted"]:
        print("\n# --- imports ---")
        print("\n".join(res["imports"]))
    for c in res["converted"]:
        print("\n# === %s (line %d) -> @dataclass ===" % (c["class"], c["line"]))
        if c["removed_methods"]:
            print("# removed (generated by @dataclass): %s" % ", ".join(c["removed_methods"]))
        for n in c["notes"]:
            print("# %s line %d: %s" % (n["rule"], n["line"], n["message"]))
        print(c["code"].rstrip())
    if res["skipped"]:
        print("\n# --- skipped ---")
        for s in res["skipped"]:
            print("# %s %s (line %d): %s" % (s["rule"], s["class"], s["line"], s["reason"]))


# ======================================================================= JSON
class Shape:
    def __init__(self):
        self.types = set()
        self.elem = None
        self.is_list = False
        self.fields = OrderedDict()
        self.key_counts = {}
        self.obj_count = 0
        self.datetime_like = True
        self.str_count = 0
        self.cls = None

    def add(self, v):
        if v is None:
            self.types.add("null")
        elif isinstance(v, bool):
            self.types.add("bool")
        elif isinstance(v, int):
            self.types.add("int")
        elif isinstance(v, float):
            self.types.add("float")
        elif isinstance(v, str):
            self.types.add("str")
            self.str_count += 1
            if not re.match(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$", v):
                self.datetime_like = False
        elif isinstance(v, list):
            self.is_list = True
            if self.elem is None:
                self.elem = Shape()
            for item in v:
                self.elem.add(item)
        elif isinstance(v, dict):
            self.types.add("object")
            self.obj_count += 1
            for k, val in v.items():
                k = str(k)
                self.key_counts[k] = self.key_counts.get(k, 0) + 1
                self.fields.setdefault(k, Shape()).add(val)

    def nullable(self):
        return "null" in self.types

    def non_null_kinds(self):
        kinds = [t for t in ("bool", "int", "float", "str", "object") if t in self.types]
        if "int" in kinds and "float" in kinds:
            kinds.remove("int")
        if self.is_list:
            kinds.append("list")
        return kinds


def pascal(name):
    parts = re.split(r"[^0-9a-zA-Z]+", re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name))
    out = "".join(p[:1].upper() + p[1:] for p in parts if p)
    if not out:
        out = "Item"
    if out[0].isdigit():
        out = "N" + out
    return out


def singular(name):
    low = name.lower()
    if low.endswith("ies") and len(name) > 4:
        return name[:-3] + "y"
    if low.endswith(("sses", "ches", "shes", "xes")):
        return name[:-2]
    if low.endswith("s") and not low.endswith(("ss", "us", "is")) and len(name) > 3:
        return name[:-1]
    return name + "Item"


def snake(key):
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", key)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s).lower()
    s = re.sub(r"[^0-9a-z_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_") if not key.startswith("_") else "_" + re.sub(r"_+", "_", s).strip("_")
    if not s or s == "_":
        s = "field"
    if s[0].isdigit():
        s = "field_" + s
    if keyword.iskeyword(s) or s in ("match", "case", "type_", "_"):
        s += "_"
    return s


class JsonGen:
    def __init__(self, root_name, style):
        self.root_name, self.style = root_name, style
        self.classes = OrderedDict()     # name -> Shape (post-order)
        self.notes = []
        self.typing = set()

    def name_classes(self, shape, proposed, parent):
        if shape.is_list and shape.elem is not None:
            self.name_classes(shape.elem, singular(proposed), parent)
        if "object" not in shape.types:
            return
        name = proposed
        if name in self.classes or name == self.root_name and parent:
            name = parent + proposed
        base, i = name, 2
        while name in self.classes:
            name, i = "%s%d" % (base, i), i + 1
        shape.cls = name
        self.classes[name] = None   # reserve, filled post-order
        for key, sub in shape.fields.items():
            self.name_classes(sub, pascal(key), name)
        del self.classes[name]
        self.classes[name] = shape

    def type_of(self, shape):
        kinds = shape.non_null_kinds()
        parts = []
        for k in kinds:
            if k == "object":
                parts.append(shape.cls)
            elif k == "list":
                inner = self.type_of(shape.elem) if shape.elem is not None and (
                    shape.elem.types or shape.elem.is_list) else "Any"
                if inner == "Any":
                    self.typing.add("Any")
                parts.append("list[%s]" % inner)
            else:
                parts.append(k)
        if not parts:
            self.typing.add("Any")
            return "Any"
        if len(parts) > 1:
            self.typing.add("Union")
            t = "Union[%s]" % ", ".join(parts)
        else:
            t = parts[0]
        if shape.nullable():
            self.typing.add("Optional")
            t = "Optional[%s]" % t
        return t

    def field_specs(self, shape):
        specs, used = [], set()
        for key, sub in shape.fields.items():
            name = snake(key)
            base, i = name, 2
            while name in used:
                name, i = "%s_%d" % (base, i), i + 1
            used.add(name)
            missing = shape.key_counts[key] < shape.obj_count
            t = self.type_of(sub)
            optional = missing or sub.nullable()
            if missing and not sub.nullable():
                self.typing.add("Optional")
                t = "Optional[%s]" % t
            dt = "str" in sub.types and sub.datetime_like and sub.str_count > 0
            specs.append({"name": name, "json_key": key, "type": t, "optional": optional, "missing": missing,
                          "shape": sub, "datetime": dt})
        return specs

    def convert_expr(self, shape, expr, depth=0):
        kinds = shape.non_null_kinds()
        if kinds == ["object"]:
            return "%s.from_dict(%s)" % (shape.cls, expr)
        if kinds == ["list"] and shape.elem is not None:
            var = "x%d" % depth if depth else "x"
            inner = self.convert_expr(shape.elem, var, depth + 1)
            if inner != var:
                if shape.elem.nullable():
                    inner = "(%s if %s is not None else None)" % (inner, var)
                return "[%s for %s in %s]" % (inner, var, expr)
        return expr

    def generate(self):
        out = []
        if self.style == "dataclass":
            out.append("from dataclasses import dataclass, field")
        elif self.style == "pydantic":
            out.append("from pydantic import BaseModel, ConfigDict, Field")
        body = []
        for name, shape in self.classes.items():
            specs = self.field_specs(shape)
            gen = {"dataclass": self.gen_dataclass, "pydantic": self.gen_pydantic,
                   "typeddict": self.gen_typeddict}[self.style]
            shape.specs = specs
            body.append(gen(name, specs))
        typing_names = set(self.typing)
        if self.style == "dataclass":
            typing_names.add("Any")
        if self.style == "typeddict":
            typing_names.add("TypedDict")
            if any("NotRequired[" in b for b in body):
                typing_names.add("NotRequired")
                self.notes.append("NotRequired is in typing on 3.11+; import it from typing_extensions on 3.9/3.10")
        if self.style == "pydantic" and any(s["datetime"] for sh in self.classes.values() for s in sh.specs):
            out.insert(0, "from datetime import datetime")
        if typing_names:
            out.append("from typing import " + ", ".join(sorted(typing_names)))
        return "\n".join(out) + "\n\n\n" + "\n\n\n".join(body) + "\n"

    def gen_dataclass(self, name, specs):
        req = [s for s in specs if not s["optional"]]
        opt = [s for s in specs if s["optional"]]
        if req and opt and any(specs.index(o) < specs.index(r) for o in opt for r in req):
            self.notes.append("%s: optional fields moved after required ones (dataclass default-ordering rule)" % name)
        lines = ["@dataclass", "class %s:" % name]
        for s in req + opt:
            meta = 'metadata={"json_key": %s}' % json.dumps(s["json_key"]) if s["name"] != s["json_key"] else None
            comment = "  # ISO-8601 string: parse with datetime.fromisoformat" if s["datetime"] else ""
            if s["optional"]:
                val = "field(default=None, %s)" % meta if meta else "None"
                lines.append("    %s: %s = %s%s" % (s["name"], s["type"], val, comment))
            else:
                lines.append("    %s: %s%s%s" % (s["name"], s["type"], " = field(%s)" % meta if meta else "", comment))
        if not specs:
            lines.append("    pass")
        lines += ["", "    @classmethod", "    def from_dict(cls, d: dict[str, Any]) -> \"%s\":" % name,
                  "        return cls("]
        for s in req + opt:
            key = json.dumps(s["json_key"])
            if s["optional"]:
                get = "d.get(%s)" % key
                conv = self.convert_expr(s["shape"], get)
                if conv != get:
                    conv = "%s if %s is not None else None" % (conv, get)
            else:
                get = "d[%s]" % key
                conv = self.convert_expr(s["shape"], get)
            lines.append("            %s=%s," % (s["name"], conv))
        lines.append("        )")
        return "\n".join(lines)

    def gen_pydantic(self, name, specs):
        lines = ["class %s(BaseModel):" % name]
        if any(s["name"] != s["json_key"] for s in specs):
            lines.append("    model_config = ConfigDict(populate_by_name=True)")
            lines.append("")
        for s in specs:
            t = s["type"]
            if s["datetime"]:
                t = t.replace("str", "datetime")
            args = []
            if s["optional"]:
                args.append("default=None")
            if s["name"] != s["json_key"]:
                args.append("alias=%s" % json.dumps(s["json_key"]))
            if args and (len(args) > 1 or args[0].startswith("alias")):
                lines.append("    %s: %s = Field(%s)" % (s["name"], t, ", ".join(args)))
            elif args:
                lines.append("    %s: %s = None" % (s["name"], t))
            else:
                lines.append("    %s: %s" % (s["name"], t))
        if not specs:
            lines.append("    pass")
        if any(s["datetime"] for s in specs):
            self.notes.append("%s: ISO-8601 string fields typed as datetime (pydantic parses them)" % name)
        return "\n".join(lines)

    def gen_typeddict(self, name, specs):
        def ann(s):
            t = s["type"]
            if s["missing"]:
                inner = t[len("Optional["):-1] if t.startswith("Optional[") and not s["shape"].nullable() else t
                return "NotRequired[%s]" % inner
            return t
        if all(k["json_key"].isidentifier() and not keyword.iskeyword(k["json_key"]) for k in specs):
            lines = ["class %s(TypedDict):" % name]
            lines += ["    %s: %s" % (s["json_key"], ann(s)) for s in specs] or ["    pass"]
            return "\n".join(lines)
        self.notes.append("%s: keys that are not identifiers -> functional TypedDict syntax" % name)
        items = ",\n".join("    %s: %s" % (json.dumps(s["json_key"]), ann(s)) for s in specs)
        return '%s = TypedDict("%s", {\n%s,\n})' % (name, name, items)


def run_json_mode(src, filename, opts):
    try:
        data = json.loads(src)
    except ValueError as e:
        raise UsageError("cannot parse %s as JSON: %s" % (filename, e))
    if not opts.name.isidentifier() or keyword.iskeyword(opts.name):
        raise UsageError("--name %r is not a valid class name" % opts.name)
    root = Shape()
    if isinstance(data, list):
        for item in data:
            root.add(item)
        if "object" not in root.types:
            raise UsageError("top-level JSON list contains no objects; nothing to model")
        notes = ["top-level JSON is a list of %d objects: types were merged across all of them" % len(data)]
    elif isinstance(data, dict):
        root.add(data)
        notes = []
    else:
        raise UsageError("top-level JSON must be an object or a list of objects")
    gen = JsonGen(opts.name, opts.style)
    gen.notes += notes
    gen.name_classes(root, opts.name, "")
    code = gen.generate()
    try:
        ast.parse(code)
    except SyntaxError as e:  # pragma: no cover - defensive
        raise UsageError("internal error: generated code does not parse: %s" % e)
    classes = []
    for name, shape in gen.classes.items():
        classes.append({"name": name, "fields": [
            {"name": s["name"], "json_key": s["json_key"], "type": s["type"], "optional": s["optional"]}
            for s in shape.specs]})
    aliased = sum(1 for c in classes for f in c["fields"] if f["name"] != f["json_key"])
    if aliased and opts.style != "typeddict":
        gen.notes.append("%d key(s) renamed to snake_case identifiers; original keys kept as %s" % (
            aliased, {"dataclass": "field metadata['json_key'] and used by from_dict()",
                      "pydantic": "Field(alias=...); dump with model_dump(by_alias=True)",
                      "typeddict": "the TypedDict keys themselves"}[opts.style]))
    usage = {"dataclass": "obj = %s.from_dict(json.loads(text))" % opts.name,
             "pydantic": "obj = %s.model_validate_json(text)" % opts.name,
             "typeddict": "obj: %s = json.loads(text)  # static typing only, no runtime checks" % opts.name}[opts.style]
    if isinstance(data, list):
        usage = {"dataclass": "items = [%s.from_dict(x) for x in json.loads(text)]" % opts.name,
                 "pydantic": "items = TypeAdapter(list[%s]).validate_json(text)" % opts.name,
                 "typeddict": "items: list[%s] = json.loads(text)" % opts.name}[opts.style]
    return {"mode": "json", "file": filename, "style": opts.style, "root": opts.name, "classes": classes,
            "notes": gen.notes, "usage": usage, "code": code}


def print_json_report(res):
    print("# generated from %s (style=%s, %d classes)" % (res["file"], res["style"], len(res["classes"])))
    for n in res["notes"]:
        print("# NOTE: %s" % n)
    print("# usage: %s" % res["usage"])
    print(res["code"].rstrip())


class UsageError(Exception):
    pass


def read_source(path):
    if path == "-":
        return sys.stdin.read(), "<stdin>"
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read(), path
    except (OSError, UnicodeDecodeError) as e:
        raise UsageError("cannot read %s: %s" % (path, e))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode")
    pc = sub.add_parser("class", help="convert boilerplate classes in a .py file (static analysis, never executes it)")
    pc.add_argument("file", help="Python file, or - for stdin")
    pc.add_argument("--frozen", action="store_true", help="generate frozen=True (post_init uses object.__setattr__)")
    pc.add_argument("--slots", action="store_true", help="generate slots=True (Python 3.10+)")
    pc.add_argument("--kw-only", dest="kw_only", action="store_true", help="generate kw_only=True (Python 3.10+)")
    pc.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    pc.add_argument("--strict", action="store_true", help="exit 1 if any class can be converted")
    pj = sub.add_parser("json", help="generate typed classes from a JSON sample")
    pj.add_argument("file", help="JSON file, or - for stdin")
    pj.add_argument("--name", default="Root", help="name of the root class (default: Root)")
    pj.add_argument("--style", choices=("dataclass", "pydantic", "typeddict"), default="dataclass",
                    help="output style (default: dataclass with from_dict)")
    pj.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    pj.add_argument("--strict", action="store_true", help="accepted for symmetry; json mode exits 0 on success")
    args = ap.parse_args(argv)
    if not args.mode:
        ap.print_usage(sys.stderr)
        print("error: choose a mode: class FILE.py | json FILE.json", file=sys.stderr)
        return 2
    try:
        src, filename = read_source(args.file)
        res = run_class_mode(src, filename, args) if args.mode == "class" else run_json_mode(src, filename, args)
    except UsageError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(res, indent=2))
    elif args.mode == "class":
        print_class_report(res)
    else:
        print_json_report(res)
    if args.mode == "class" and args.strict and res["converted"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
