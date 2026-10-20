#!/usr/bin/env python3
"""Find loops that should be comprehensions, and comprehensions that should be loops.

Static AST analysis (the analysed code is parsed, never executed). It reports:

  loop-to-list-comprehension   `x = []` followed by a for loop that only appends
  loop-to-set-comprehension    `x = set()` followed by a for loop that only adds
  loop-to-dict-comprehension   `x = {}` followed by a for loop that only assigns x[k] = v
  loop-to-counter              counting loop (d[k] = d.get(k, 0) + 1) -> collections.Counter
  loop-to-defaultdict          grouping loop (setdefault / "if k not in d") -> defaultdict(list)
  side-effect-comprehension    [print(x) for x in xs] used as a statement -> plain for loop
  complex-comprehension        too many for clauses / ifs, nested > 1 level, long lines or
                               side-effect calls inside -> unrolled loop or generator function
  materialised-reducer-arg     sum([...]), any([...]), max(list(...)) -> pass a generator
  len-of-comprehension         len([... if cond]) -> sum(1 for ... if cond)
  first-of-comprehension       [... if cond][0] -> next((... if cond), None)
  identity-comprehension       [x for x in y] -> list(y), {k: v for k, v in d.items()} -> dict(d)
  redundant-constructor        list([...]), set(x for ...), dict((k, v) for ...) -> comprehension
  map-filter-lambda            list(map(lambda x: ..., xs)) -> comprehension

Loop rewrites handle if-filters, `if cond: continue` guards, nested for loops,
if/else (conditional expressions), extend()/update() flattening, a temporary
assigned and then tested (rewritten with the walrus operator), and async for.
Each finding prints the exact replacement code produced with ast.unparse.

Usage:
    python find_comprehension_candidates.py pipeline.py
    python find_comprehension_candidates.py src/rag/*.py --json
    cat ingest.py | python find_comprehension_candidates.py - --strict
    python find_comprehension_candidates.py retriever.py --max-for 3 --max-line 120

Exit codes: 0 analysis ran (findings are advice), 1 findings exist and --strict
was given, 2 usage error, unreadable file or syntax error.

No dependencies (Python 3.9+ standard library).
"""

import argparse
import ast
import copy
import json
import sys

RULES = {
    "loop-to-list-comprehension": ("medium", "comprehension-patterns.md"),
    "loop-to-set-comprehension": ("medium", "comprehension-patterns.md"),
    "loop-to-dict-comprehension": ("medium", "comprehension-patterns.md"),
    "loop-to-counter": ("medium", "comprehension-patterns.md"),
    "loop-to-defaultdict": ("low", "comprehension-patterns.md"),
    "side-effect-comprehension": ("high", "when-not-to-use.md"),
    "complex-comprehension": ("medium", "when-not-to-use.md"),
    "materialised-reducer-arg": ("medium", "generators-and-itertools.md"),
    "len-of-comprehension": ("low", "generators-and-itertools.md"),
    "first-of-comprehension": ("low", "generators-and-itertools.md"),
    "identity-comprehension": ("low", "comprehension-patterns.md"),
    "redundant-constructor": ("low", "comprehension-patterns.md"),
    "map-filter-lambda": ("low", "performance-notes.md"),
}
SEV_ORDER = {"high": 0, "medium": 1, "low": 2}
COMPS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
REDUCERS = ("sum", "any", "all", "max", "min")
SIDE_EFFECT_FUNCS = {"print", "exec", "setattr", "delattr", "input"}
SIDE_EFFECT_METHODS = {
    "append", "extend", "add", "update", "insert", "pop", "remove", "discard", "clear", "write",
    "writelines", "send", "put", "put_nowait", "debug", "info", "warning", "error", "exception",
    "critical", "log", "setdefault", "commit", "upsert", "flush",
}
WRAP_WIDTH = 88


# ----------------------------------------------------------------------------- helpers

def names_in(*nodes):
    out = set()
    for n in nodes:
        if n is not None:
            out.update(x.id for x in ast.walk(n) if isinstance(x, ast.Name))
    return out


def has_yield(*nodes):
    return any(isinstance(x, (ast.Yield, ast.YieldFrom)) for n in nodes if n is not None for x in ast.walk(n))


def same(a, b):
    return ast.dump(a) == ast.dump(b)


def is_name_call(node, names, nargs=None):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in names
            and not node.keywords and (nargs is None or len(node.args) == nargs)
            and not any(isinstance(a, ast.Starred) for a in node.args))


def method_call(node, obj, attrs):
    """Return the attribute name if node is obj.<attr>(...) for attr in attrs."""
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in attrs
            and isinstance(node.func.value, ast.Name) and node.func.value.id == obj):
        return node.func.attr
    return None


def negate(test):
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return test.operand
    flips = {ast.In: ast.NotIn, ast.NotIn: ast.In, ast.Is: ast.IsNot, ast.IsNot: ast.Is,
             ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}
    if isinstance(test, ast.Compare) and len(test.ops) == 1 and type(test.ops[0]) in flips:
        return ast.Compare(left=test.left, ops=[flips[type(test.ops[0])]()], comparators=test.comparators)
    return ast.UnaryOp(op=ast.Not(), operand=test)


class _Sub(ast.NodeTransformer):
    """Replace Name loads of `name` (first one only, or all) without entering nested scopes."""

    def __init__(self, name, repl, first_only):
        self.name, self.repl, self.first_only, self.count = name, repl, first_only, 0

    def visit_Name(self, node):
        if node.id == self.name and isinstance(node.ctx, ast.Load) and not (self.first_only and self.count):
            self.count += 1
            return copy.deepcopy(self.repl)
        return node

    def _scope(self, node):
        return node

    visit_Lambda = visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = _scope


def substitute(node, name, repl, first_only):
    t = _Sub(name, repl, first_only)
    new = t.visit(copy.deepcopy(node))
    return new, t.count


def count_loads(node, name):
    return sum(1 for x in ast.walk(node) if isinstance(x, ast.Name) and x.id == name and isinstance(x.ctx, ast.Load))


try:  # ast._Unparser is private but present in 3.9-3.14; it lets f(x for x in y) print without (( )).
    class _Unparser(ast._Unparser):
        def visit_Call(self, node):
            if len(node.args) == 1 and not node.keywords and isinstance(node.args[0], ast.GeneratorExp):
                self.set_precedence(ast._Precedence.ATOM, node.func)
                self.traverse(node.func)
                self.traverse(node.args[0])
            else:
                super().visit_Call(node)
except AttributeError:  # pragma: no cover - fall back to the public API
    _Unparser = None


def unparse(node):
    node = ast.fix_missing_locations(node)
    if _Unparser is not None:
        try:
            return _Unparser().visit(node)
        except Exception:  # noqa: BLE001 - private API changed; use the public one
            pass
    return ast.unparse(node)


def call_text(func, arg):
    """sum(<genexp>) without the double parentheses ast.unparse emits."""
    inner = unparse(arg)
    if isinstance(arg, ast.GeneratorExp):
        inner = inner[1:-1]
    return f"{func}({inner})"


def comp_text(node, prefix=""):
    """Unparse a comprehension, wrapping one clause per line when it is long."""
    one = prefix + unparse(node)
    if len(one) <= WRAP_WIDTH or not isinstance(node, COMPS):
        return one
    opener, closer = {ast.ListComp: "[]", ast.SetComp: "{}", ast.DictComp: "{}", ast.GeneratorExp: "()"}[type(node)]
    head = f"{unparse(node.key)}: {unparse(node.value)}" if isinstance(node, ast.DictComp) else unparse(node.elt)
    lines = [prefix + opener, "    " + head]
    for g in node.generators:
        lines.append(f"    {'async ' if g.is_async else ''}for {unparse(g.target)} in {unparse(g.iter)}")
        lines.extend(f"    if {unparse(c)}" for c in g.ifs)
    lines.append(closer)
    return "\n".join(lines)


def fresh(used, base="item"):
    for cand in (base, "x", "elem", base + "_"):
        if cand not in used:
            return cand
    i = 2
    while f"{base}{i}" in used:
        i += 1
    return f"{base}{i}"


def build_loops(gens, inner):
    body = list(inner)
    for g in reversed(gens):
        if g.ifs:
            test = g.ifs[0] if len(g.ifs) == 1 else ast.BoolOp(op=ast.And(), values=list(g.ifs))
            body = [ast.If(test=test, body=body, orelse=[])]
        cls = ast.AsyncFor if g.is_async else ast.For
        body = [cls(target=g.target, iter=g.iter, body=body, orelse=[], type_comment=None)]
    return body


def module_text(stmts):
    return unparse(ast.Module(body=stmts, type_ignores=[]))


# ----------------------------------------------------------------------------- loop -> comprehension

class Clause:
    def __init__(self, target, it, is_async):
        self.target, self.iter, self.ifs, self.is_async = target, it, [], is_async

    def node(self):
        return ast.comprehension(target=self.target, iter=self.iter, ifs=self.ifs, is_async=int(self.is_async))


def init_kind(value):
    if isinstance(value, ast.List) and not value.elts:
        return "list"
    if isinstance(value, ast.Dict) and not value.keys:
        return "dict"
    if is_name_call(value, ("list", "dict", "set"), 0):
        return value.func.id
    return None


def accumulator(stmt):
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
        kind = init_kind(stmt.value)
        return (stmt.targets[0].id, kind, None) if kind else None
    if (isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None
            and stmt.simple):
        kind = init_kind(stmt.value)
        return (stmt.target.id, kind, stmt.annotation) if kind else None
    return None


def build_action(stmts, acc, kind):
    """Action of the innermost loop body: ('elt', e) / ('extend', it) / ('kv', k, v)."""
    if len(stmts) != 1:
        return None
    s = stmts[0]
    if kind in ("list", "set") and isinstance(s, ast.Expr):
        one, many = ("append", "extend") if kind == "list" else ("add", "update")
        attr = method_call(s.value, acc, (one, many))
        if attr and len(s.value.args) == 1 and not s.value.keywords and not isinstance(s.value.args[0], ast.Starred):
            return ("elt" if attr == one else "extend", s.value.args[0])
    if kind == "dict" and isinstance(s, ast.Assign) and len(s.targets) == 1:
        t = s.targets[0]
        if (isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == acc
                and not isinstance(t.slice, ast.Slice)):
            return ("kv", t.slice, s.value)
    return None


def group_action(stmts, acc, kind):
    """Counting / grouping actions: ('count', k) or ('group', k, v)."""
    if kind != "dict":
        return None
    guard_val = None
    if len(stmts) == 2:
        g = stmts[0]
        if (isinstance(g, ast.If) and not g.orelse and len(g.body) == 1 and isinstance(g.test, ast.Compare)
                and len(g.test.ops) == 1 and isinstance(g.test.ops[0], ast.NotIn)
                and isinstance(g.test.comparators[0], ast.Name) and g.test.comparators[0].id == acc
                and isinstance(g.body[0], ast.Assign) and len(g.body[0].targets) == 1
                and isinstance(g.body[0].targets[0], ast.Subscript)
                and isinstance(g.body[0].targets[0].value, ast.Name) and g.body[0].targets[0].value.id == acc
                and same(g.body[0].targets[0].slice, g.test.left)):
            guard_key, guard_val = g.test.left, g.body[0].value
            stmts = stmts[1:]
        else:
            return None
    if len(stmts) != 1:
        return None
    s = stmts[0]
    # d[k] = d.get(k, 0) + 1
    if (guard_val is None and isinstance(s, ast.Assign) and len(s.targets) == 1
            and isinstance(s.targets[0], ast.Subscript) and isinstance(s.targets[0].value, ast.Name)
            and s.targets[0].value.id == acc and isinstance(s.value, ast.BinOp) and isinstance(s.value.op, ast.Add)
            and isinstance(s.value.right, ast.Constant) and s.value.right.value == 1
            and method_call(s.value.left, acc, ("get",)) and len(s.value.left.args) == 2
            and same(s.value.left.args[0], s.targets[0].slice)
            and isinstance(s.value.left.args[1], ast.Constant) and s.value.left.args[1].value == 0):
        return ("count", s.targets[0].slice)
    # if k not in d: d[k] = 0 ; d[k] += 1
    if (guard_val is not None and isinstance(guard_val, ast.Constant) and guard_val.value == 0
            and isinstance(s, ast.AugAssign) and isinstance(s.op, ast.Add) and isinstance(s.value, ast.Constant)
            and s.value.value == 1 and isinstance(s.target, ast.Subscript) and same(s.target.slice, guard_key)):
        return ("count", guard_key)
    if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call) and isinstance(s.value.func, ast.Attribute) \
            and s.value.func.attr == "append" and len(s.value.args) == 1:
        recv = s.value.func.value
        # d.setdefault(k, []).append(v)
        if (guard_val is None and method_call(recv, acc, ("setdefault",)) and len(recv.args) == 2
                and isinstance(recv.args[1], ast.List) and not recv.args[1].elts):
            return ("group", recv.args[0], s.value.args[0])
        # if k not in d: d[k] = [] ; d[k].append(v)
        if (guard_val is not None and init_kind(guard_val) == "list" and isinstance(recv, ast.Subscript)
                and isinstance(recv.value, ast.Name) and recv.value.id == acc and same(recv.slice, guard_key)):
            return ("group", guard_key, s.value.args[0])
    return None


def single_branch(stmts, acc, kind, depth=0):
    """if/else (and one elif) whose branches each perform one action -> conditional expression."""
    if len(stmts) != 1:
        return None
    s = stmts[0]
    if isinstance(s, ast.If) and s.orelse and depth < 2:
        a = build_action(s.body, acc, kind)
        b = single_branch(s.orelse, acc, kind, depth + 1) or build_action(s.orelse, acc, kind)
        if not a or not b or a[0] != b[0] or a[0] == "extend":
            return None
        if a[0] == "elt":
            return ("elt", ast.IfExp(test=s.test, body=a[1], orelse=b[1]))
        if same(a[1], b[1]):
            return ("kv", a[1], ast.IfExp(test=s.test, body=a[2], orelse=b[2]))
    return None


def peel(stmts, acc, kind, clauses, notes, parser, in_class):
    stmts = list(stmts)
    while (len(stmts) > 1 and isinstance(stmts[0], ast.If) and not stmts[0].orelse and len(stmts[0].body) == 1
           and isinstance(stmts[0].body[0], ast.Continue)):
        clauses[-1].ifs.append(negate(stmts.pop(0).test))
    act = parser(stmts, acc, kind)
    if act:
        return act
    if (len(stmts) == 2 and isinstance(stmts[0], ast.Assign) and len(stmts[0].targets) == 1
            and isinstance(stmts[0].targets[0], ast.Name) and parser is build_action):
        tmp, val, nxt = stmts[0].targets[0].id, stmts[0].value, stmts[1]
        targets = names_in(*(c.target for c in clauses))
        if tmp == acc or tmp in targets:
            return None
        if isinstance(nxt, ast.If) and not nxt.orelse and not in_class:
            walrus = ast.NamedExpr(target=ast.Name(id=tmp, ctx=ast.Store()), value=val)
            test, n = substitute(nxt.test, tmp, walrus, True)
            if n:
                clauses[-1].ifs.append(test)
                notes.append(f"`{tmp}` is bound with the walrus operator so it is computed once per item "
                             "(Python 3.8+); it stays visible after the comprehension, like the loop variable did.")
                return peel(nxt.body, acc, kind, clauses, notes, parser, in_class)
        act = build_action([nxt], acc, kind)
        if act and sum(count_loads(e, tmp) for e in act[1:]) == 1 and not _top_comps(val):
            notes.append(f"temporary `{tmp}` was inlined; it is no longer assigned after the loop.")
            return (act[0],) + tuple(substitute(e, tmp, val, False)[0] for e in act[1:])
        return None
    if len(stmts) != 1:
        return None
    s = stmts[0]
    if isinstance(s, ast.If):
        if not s.orelse:
            clauses[-1].ifs.append(s.test)
            return peel(s.body, acc, kind, clauses, notes, parser, in_class)
        return single_branch([s], acc, kind) if parser is build_action else None
    if isinstance(s, (ast.For, ast.AsyncFor)) and not s.orelse:
        clauses.append(Clause(s.target, s.iter, isinstance(s, ast.AsyncFor)))
        return peel(s.body, acc, kind, clauses, notes, parser, in_class)
    return None


def loads_after(block, idx, names):
    """{name: first line} for names read in statements after block[idx]."""
    hits = {}
    for stmt in block[idx + 1:]:
        for x in ast.walk(stmt):
            if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load) and x.id in names and x.id not in hits:
                hits[x.id] = x.lineno
    return hits


def check_loop(block, i, in_class, max_for, max_ifs):
    acc_info = accumulator(block[i])
    loop = block[i + 1] if i + 1 < len(block) else None
    if not acc_info or not isinstance(loop, (ast.For, ast.AsyncFor)) or loop.orelse:
        return None
    acc, kind, ann = acc_info
    start, end = block[i].lineno, loop.end_lineno
    for parser in (build_action, group_action):
        clauses = [Clause(loop.target, loop.iter, isinstance(loop, ast.AsyncFor))]
        notes = []
        act = peel(loop.body, acc, kind, clauses, notes, parser, in_class)
        if not act:
            continue
        gens = [c.node() for c in clauses]
        exprs = [g.iter for g in gens] + [x for g in gens for x in g.ifs] + [g.target for g in gens] + list(act[1:])
        if acc not in names_in(*exprs) and not has_yield(*exprs):
            break
    else:
        return None
    if any(isinstance(x, ast.UnaryOp) and isinstance(x.op, ast.Not) and isinstance(x.operand, ast.Compare)
           for g in gens for x in g.ifs):
        notes.append("`continue` guards were negated as `not (a < b)` rather than `a >= b`, which differ for NaN; "
                     "simplify by hand if the values can never be NaN.")
    if act[0] == "extend":
        var = fresh(names_in(*exprs) | {acc})
        gens.append(ast.comprehension(target=ast.Name(id=var, ctx=ast.Store()), iter=act[1], ifs=[], is_async=0))
        act = ("elt", ast.Name(id=var, ctx=ast.Load()))
        notes.append("extend()/update() became an extra `for` clause (flattening).")
    if len(gens) > max_for or sum(len(g.ifs) for g in gens) > max_ifs:
        return None  # a comprehension would be harder to read than the loop
    lhs = f"{acc}: {unparse(ann)} = " if ann is not None else f"{acc} = "
    if act[0] == "count":
        counted = ast.GeneratorExp(elt=act[1], generators=gens)
        ident = is_identity(counted)
        suggestion = "from collections import Counter\n" + lhs + (
            f"Counter({ident})" if ident is not None else call_text("Counter", counted))
        rule, msg = "loop-to-counter", f"Loop counts occurrences into `{acc}`; collections.Counter does it in one pass."
        notes.append("Counter returns 0 for missing keys and adds most_common(); it is a dict subclass.")
    elif act[0] == "group":
        inner = [ast.Expr(value=ast.Call(
            func=ast.Attribute(value=ast.Subscript(value=ast.Name(id=acc, ctx=ast.Load()), slice=act[1], ctx=ast.Load()),
                               attr="append", ctx=ast.Load()), args=[act[2]], keywords=[]))]
        suggestion = ("from collections import defaultdict\n" + lhs + "defaultdict(list)\n"
                      + module_text(build_loops(gens, inner)))
        rule, msg = "loop-to-defaultdict", f"Loop groups values into `{acc}` by key; use defaultdict(list) instead of a comprehension."
        notes.append("A grouping comprehension would rescan the data once per key (O(n*k)); keep the loop. "
                     "Return dict(...) if callers must not auto-create keys on lookup.")
    else:
        if kind == "dict":
            comp = ast.DictComp(key=act[1], value=act[2], generators=gens)
        elif kind == "set":
            comp = ast.SetComp(elt=act[1], generators=gens)
        else:
            comp = ast.ListComp(elt=act[1], generators=gens)
        if comp_depth(comp) > 2 or any(len(unparse(e)) > 80 for e in act[1:]):
            return None  # the comprehension would be harder to read than the loop
        suggestion = comp_text(comp, lhs)
        verb = {"list": "appends to", "set": "adds to", "dict": "assigns keys of"}[kind]
        rule = f"loop-to-{kind}-comprehension"
        msg = f"`{acc}` is created empty and the loop only {verb} it; build it with one {kind} comprehension."
        if kind == "dict":
            notes.append("Duplicate keys keep the last value, exactly like the loop.")
    leaked = loads_after(block, i + 1, names_in(*(c.target for c in clauses)) - {acc})
    for name, line in sorted(leaked.items(), key=lambda kv: kv[1]):
        notes.append(f"loop variable `{name}` is read after the loop (line {line}); comprehension variables "
                     "do not leak, so keep that value some other way.")
    if in_class:
        notes.append("Class body: only the first iterable can see class-level names inside a comprehension.")
    return finding(rule, start, end, msg, suggestion, notes)


# ----------------------------------------------------------------------------- comprehension checks

def comp_depth(node):
    """1 for a flat comprehension, 2 when one comprehension sits inside another, and so on."""
    children = []
    for g in node.generators:
        children += [g.iter] + list(g.ifs)
    children += [node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]
    best = 0
    for ch in children:
        for x in _top_comps(ch):
            best = max(best, comp_depth(x))
    return 1 + best


def _top_comps(node):
    if isinstance(node, COMPS):
        return [node]
    out = []
    for ch in ast.iter_child_nodes(node):
        out += _top_comps(ch)
    return out


def side_effect_calls(node):
    found = []
    parts = [node.elt] if not isinstance(node, ast.DictComp) else [node.key, node.value]
    parts += [x for g in node.generators for x in g.ifs]
    for p in parts:
        for x in ast.walk(p):
            if not isinstance(x, ast.Call):
                continue
            if isinstance(x.func, ast.Name) and x.func.id in SIDE_EFFECT_FUNCS:
                found.append(x.func.id + "()")
            elif isinstance(x.func, ast.Attribute) and x.func.attr in SIDE_EFFECT_METHODS:
                found.append("." + x.func.attr + "()")
    return sorted(set(found))


def unroll(node, stmt, used):
    """Return (suggestion, note) turning a comprehension into explicit statements."""
    gens = node.generators
    elt = node.elt if not isinstance(node, ast.DictComp) else None
    if isinstance(stmt, ast.Expr) and stmt.value is node:
        inner = [ast.Expr(value=elt if elt is not None else ast.Tuple(elts=[node.key, node.value], ctx=ast.Load()))]
        return module_text(build_loops(gens, inner)), "A plain for loop states the intent and allocates nothing."
    target = None
    if isinstance(stmt, ast.Assign) and stmt.value is node and len(stmt.targets) == 1 \
            and isinstance(stmt.targets[0], ast.Name):
        target = stmt.targets[0].id
    elif isinstance(stmt, ast.AnnAssign) and stmt.value is node and isinstance(stmt.target, ast.Name):
        target = stmt.target.id
    elif isinstance(stmt, ast.Return) and stmt.value is node:
        target = fresh(used, "result")
    if target and not isinstance(node, ast.GeneratorExp):
        name = ast.Name(id=target, ctx=ast.Load())
        if isinstance(node, ast.DictComp):
            init = ast.Dict(keys=[], values=[])
            act = ast.Assign(targets=[ast.Subscript(value=name, slice=node.key, ctx=ast.Store())], value=node.value,
                             lineno=0)
        else:
            init = ast.List(elts=[], ctx=ast.Load()) if isinstance(node, ast.ListComp) else \
                ast.Call(func=ast.Name(id="set", ctx=ast.Load()), args=[], keywords=[])
            meth = "append" if isinstance(node, ast.ListComp) else "add"
            act = ast.Expr(value=ast.Call(func=ast.Attribute(value=name, attr=meth, ctx=ast.Load()),
                                          args=[elt], keywords=[]))
        body = [ast.Assign(targets=[ast.Name(id=target, ctx=ast.Store())], value=init, lineno=0)]
        body += build_loops(gens, [act])
        if isinstance(stmt, ast.Return):
            body.append(ast.Return(value=ast.Name(id=target, ctx=ast.Load())))
        return module_text(body), "Name intermediate values and add comments inside the loop where needed."
    yielded = elt if elt is not None else ast.Tuple(elts=[node.key, node.value], ctx=ast.Load())
    fn = ast.FunctionDef(name="iter_items", args=ast.arguments(posonlyargs=[], args=[], vararg=None, kwonlyargs=[],
                                                               kw_defaults=[], kwarg=None, defaults=[]),
                         body=build_loops(gens, [ast.Expr(value=ast.Yield(value=yielded))]),
                         decorator_list=[], returns=None, type_comment=None, lineno=0)
    if sys.version_info >= (3, 12):
        fn.type_params = []
    wrap = {ast.ListComp: "list(iter_items())", ast.SetComp: "set(iter_items())",
            ast.DictComp: "dict(iter_items())", ast.GeneratorExp: "iter_items()"}[type(node)]
    return (module_text([fn]),
            f"Extract a named generator function (pass the names it reads as parameters) and use {wrap} in place "
            "of the comprehension.")


def check_comprehension(node, stmt, lines, max_for, max_line, used, max_ifs):
    reasons = []
    n_for = len(node.generators)
    n_if = sum(len(g.ifs) for g in node.generators)
    if n_for > max_for:
        reasons.append(f"{n_for} for clauses (max {max_for})")
    if n_if > max_ifs:
        reasons.append(f"{n_if} if clauses (max {max_ifs})")
    depth = comp_depth(node)
    if depth > 2:
        reasons.append(f"comprehensions nested {depth} levels deep (max 2)")
    span = lines[node.lineno - 1:node.end_lineno]
    longest = max((len(x.rstrip("\n")) for x in span), default=0)
    if node.lineno == node.end_lineno:
        own = node.end_col_offset - node.col_offset
    else:
        own = max(len(span[0]) - node.col_offset, node.end_col_offset, *(len(x) for x in span[1:-1]))
    if longest > max_line and own * 2 >= longest:  # the comprehension itself makes the line long
        reasons.append(f"line length {longest} > {max_line}")
    effects = side_effect_calls(node)
    if effects:
        reasons.append("side-effect call(s) inside: " + ", ".join(effects))
    as_statement = isinstance(stmt, ast.Expr) and stmt.value is node
    if not reasons and not as_statement:
        return None
    suggestion, note = unroll(node, stmt, used)
    if as_statement:
        kind = type(node).__name__.replace("Comp", " comprehension").replace("GeneratorExp", "generator expression")
        msg = (f"{kind} is evaluated as a statement and its result thrown away; it exists only for side effects "
               "and builds a throwaway container.")
        return finding("side-effect-comprehension", node.lineno, node.end_lineno, msg, suggestion, [note])
    msg = "Comprehension is too complex to read at a glance: " + "; ".join(reasons) + ". Unroll it."
    return finding("complex-comprehension", node.lineno, node.end_lineno, msg, suggestion, [note])


def is_identity(node):
    if isinstance(node, ast.DictComp):
        if len(node.generators) != 1:
            return None
        g = node.generators[0]
        if (g.ifs or g.is_async or not isinstance(g.target, ast.Tuple) or len(g.target.elts) != 2
                or not all(isinstance(e, ast.Name) for e in g.target.elts)):
            return None
        k, v = g.target.elts
        if isinstance(node.key, ast.Name) and isinstance(node.value, ast.Name) and node.key.id == k.id \
                and node.value.id == v.id and k.id != v.id:
            it = g.iter
            if isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute) and it.func.attr == "items" \
                    and not it.args and not it.keywords:
                return f"dict({unparse(it.func.value)})"
            return f"dict({unparse(it)})"
        return None
    if len(node.generators) != 1:
        return None
    g = node.generators[0]
    if g.ifs or g.is_async:
        return None
    if isinstance(g.target, ast.Name) and isinstance(node.elt, ast.Name) and node.elt.id == g.target.id:
        return unparse(g.iter)
    if isinstance(g.target, ast.Tuple) and same_shape(g.target, node.elt):
        return unparse(g.iter)
    return None


def same_shape(target, elt):
    if not isinstance(elt, ast.Tuple) or len(elt.elts) != len(target.elts):
        return False
    return all(isinstance(t, ast.Name) and isinstance(e, ast.Name) and t.id == e.id
               for t, e in zip(target.elts, elt.elts))


def lambda_param(fn):
    a = fn.args
    params = a.posonlyargs + a.args
    if len(params) != 1 or a.vararg or a.kwarg or a.kwonlyargs or a.defaults:
        return None
    return params[0].arg


def check_calls(node, parents, handled):
    """Findings for wrappers and reducers around comprehensions / map / filter."""
    out = []
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.keywords and node.func.id not in REDUCERS:
        return out
    if id(node) in handled:
        return out
    fname = node.func.id
    args = node.args
    # sum([...]) / any(list(...))
    if fname in REDUCERS and args and not isinstance(args[0], ast.Starred) and len(args) == 1:
        arg = args[0]
        new = None
        if isinstance(arg, ast.ListComp):
            new = ast.GeneratorExp(elt=arg.elt, generators=arg.generators)
        elif is_name_call(arg, ("list",), 1):
            new = arg.args[0]
        if new is not None:
            handled.add(id(arg))
            kw = "".join(f", {unparse(k)}" for k in node.keywords)
            text = call_text(fname, new)
            if kw:
                text = text[:-1] + kw + ")"
            note = ("any()/all() stop at the first decisive item; the list forces every element to be computed "
                    "first.") if fname in ("any", "all") else "The generator avoids building an O(n) temporary list."
            if fname in ("max", "min") and not node.keywords:
                note += " Empty input still raises ValueError; add default=... if that can happen."
            out.append(finding("materialised-reducer-arg", node.lineno, node.end_lineno,
                               f"{fname}() receives a fully built list; feed it a generator instead.", text, [note]))
            return out
    if node.keywords:
        return out
    if fname == "len" and len(args) == 1 and isinstance(args[0], ast.ListComp) and any(
            g.ifs for g in args[0].generators):
        handled.add(id(args[0]))
        gen = ast.GeneratorExp(elt=ast.Constant(value=1), generators=args[0].generators)
        out.append(finding("len-of-comprehension", node.lineno, node.end_lineno,
                           "len() of a filtered list builds the list just to count it.", call_text("sum", gen),
                           ["Keep the list if you also use its items afterwards."]))
        return out
    if fname in ("list", "set", "dict", "tuple", "sorted") and len(args) == 1:
        arg = args[0]
        if isinstance(arg, (ast.ListComp, ast.GeneratorExp, ast.SetComp)) and fname != "dict":
            ident = is_identity(arg)
            if ident is not None:
                handled.add(id(arg))
                out.append(finding("identity-comprehension", node.lineno, node.end_lineno,
                                   "The comprehension copies items unchanged.", f"{fname}({ident})", []))
                return out
        if fname in ("list", "set") and isinstance(arg, (ast.ListComp, ast.GeneratorExp)):
            handled.add(id(arg))
            cls = ast.ListComp if fname == "list" else ast.SetComp
            new = cls(elt=arg.elt, generators=arg.generators)
            out.append(finding("redundant-constructor", node.lineno, node.end_lineno,
                               f"{fname}() around a comprehension or generator; write the {fname} comprehension directly.",
                               comp_text(new), ["The literal form is shorter and skips a function call."]))
            return out
        if fname == "dict" and isinstance(arg, (ast.ListComp, ast.GeneratorExp)) and isinstance(arg.elt, ast.Tuple) \
                and len(arg.elt.elts) == 2:
            handled.add(id(arg))
            new = ast.DictComp(key=arg.elt.elts[0], value=arg.elt.elts[1], generators=arg.generators)
            out.append(finding("redundant-constructor", node.lineno, node.end_lineno,
                               "dict() around (key, value) pairs; use a dict comprehension.", comp_text(new), []))
            return out
        if fname in ("list", "set") and isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) \
                and arg.func.id in ("map", "filter"):
            res = map_filter(arg)
            if res is not None:
                handled.add(id(arg))
                cls = ast.ListComp if fname == "list" else ast.SetComp
                out.append(finding("map-filter-lambda", node.lineno, node.end_lineno,
                                   f"{fname}({arg.func.id}(lambda ...)) is slower and harder to read than a comprehension.",
                                   comp_text(cls(elt=res.elt, generators=res.generators)),
                                   ["map()/filter() with a builtin or named function (map(str.strip, lines)) is fine."]))
                return out
    if fname in ("map", "filter") and id(node) not in handled:
        res = map_filter(node)
        if res is not None:
            out.append(finding("map-filter-lambda", node.lineno, node.end_lineno,
                               f"{fname}(lambda ...) reads better as a generator expression.", comp_text(res),
                               ["map()/filter() with a builtin or named function (map(str.strip, lines)) is fine."]))
    return out


def map_filter(call):
    if len(call.args) != 2 or call.keywords or not isinstance(call.args[0], ast.Lambda):
        return None
    lam = call.args[0]
    p = lambda_param(lam)
    if p is None:
        return None
    gen = ast.comprehension(target=ast.Name(id=p, ctx=ast.Store()), iter=call.args[1], ifs=[], is_async=0)
    if call.func.id == "map":
        return ast.GeneratorExp(elt=lam.body, generators=[gen])
    gen.ifs = [lam.body]
    return ast.GeneratorExp(elt=ast.Name(id=p, ctx=ast.Load()), generators=[gen])


# ----------------------------------------------------------------------------- driver

def finding(rule, line, end_line, message, suggestion, notes):
    sev, ref = RULES[rule]
    return {"rule": rule, "severity": sev, "line": line, "end_line": end_line, "message": message,
            "suggestion": suggestion, "notes": [n for n in notes if n], "reference": "references/" + ref}


def analyse(source, filename="<stdin>", max_for=2, max_line=100, max_ifs=2):
    tree = ast.parse(source, filename=filename)
    lines = source.splitlines()
    parents = {}
    for node in ast.walk(tree):
        for ch in ast.iter_child_nodes(node):
            parents[id(ch)] = node
    used = names_in(tree)
    findings, handled = [], set()

    for node in ast.walk(tree):
        for field, value in ast.iter_fields(node):
            if isinstance(value, list) and value and isinstance(value[0], ast.stmt):
                for i in range(len(value) - 1):
                    f = check_loop(value, i, isinstance(node, ast.ClassDef) and field == "body", max_for, max_ifs)
                    if f:
                        findings.append(f)

    for node in ast.walk(tree):
        findings += check_calls(node, parents, handled)
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.ListComp)
                and isinstance(node.slice, ast.Constant) and node.slice.value == 0
                and any(g.ifs for g in node.value.generators)):
            handled.add(id(node.value))
            gen = ast.GeneratorExp(elt=node.value.elt, generators=node.value.generators)
            findings.append(finding("first-of-comprehension", node.lineno, node.end_lineno,
                                    "Builds the whole filtered list to take its first item.",
                                    f"next({unparse(gen)}, None)",
                                    ["The original raises IndexError when nothing matches; next(..., None) returns "
                                     "None. Drop the default to get StopIteration instead."]))

    for node in ast.walk(tree):
        if not isinstance(node, COMPS):
            continue
        parent = parents.get(id(node))
        anc, nested = parent, False
        while anc is not None:
            if isinstance(anc, COMPS):
                nested = True
                break
            anc = parents.get(id(anc))
        if nested:
            continue
        stmt = parent
        while stmt is not None and not isinstance(stmt, ast.stmt):
            stmt = parents.get(id(stmt))
        f = check_comprehension(node, stmt, lines, max_for, max_line, used, max_ifs)
        if f:
            findings.append(f)
            continue
        if id(node) in handled or isinstance(node, ast.GeneratorExp):
            continue
        ident = is_identity(node)
        if ident is not None:
            ctor = {ast.ListComp: "list", ast.SetComp: "set"}.get(type(node))
            text = ident if isinstance(node, ast.DictComp) else f"{ctor}({ident})"
            note = ("dict(d) or d.copy() makes the same shallow copy." if isinstance(node, ast.DictComp)
                    else "Both make a shallow copy; xs[:] or xs.copy() also work when the source is already a list.")
            findings.append(finding("identity-comprehension", node.lineno, node.end_lineno,
                                    "The comprehension copies items unchanged.", text, [note]))

    findings.sort(key=lambda f: (f["line"], SEV_ORDER[f["severity"]], f["rule"]))
    return findings


def render(path, findings):
    out = []
    if not findings:
        out.append(f"{path}: no comprehension refactors suggested.")
        return "\n".join(out)
    counts = {s: sum(f["severity"] == s for f in findings) for s in SEV_ORDER}
    out.append(f"{path}: {len(findings)} finding(s) ({counts['high']} high, {counts['medium']} medium, "
               f"{counts['low']} low)\n")
    for n, f in enumerate(findings, 1):
        span = f"line {f['line']}" if f["line"] == f["end_line"] else f"lines {f['line']}-{f['end_line']}"
        out.append(f"{n}. [{f['severity'].upper()}] {f['rule']}  {path}:{span}")
        out.append(f"   {f['message']}")
        out.append("   suggested:")
        out.extend("       " + ln for ln in f["suggestion"].splitlines())
        for note in f["notes"]:
            out.append(f"   note: {note}")
        out.append(f"   see:  {f['reference']}\n")
    return "\n".join(out).rstrip() + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="Python file(s) to analyse, or - for stdin")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--strict", action="store_true", help="exit 1 when any finding is reported (CI gate)")
    ap.add_argument("--max-for", type=int, default=2, metavar="N",
                    help="for clauses allowed in one comprehension before suggesting a loop (default 2)")
    ap.add_argument("--max-ifs", type=int, default=2, metavar="N",
                    help="if clauses allowed in one comprehension before suggesting a loop (default 2)")
    ap.add_argument("--max-line", type=int, default=100, metavar="N",
                    help="flag comprehensions on lines longer than N characters (default 100)")
    args = ap.parse_args(argv)
    if args.max_for < 1 or args.max_ifs < 0 or args.max_line < 20:
        ap.error("--max-for must be >= 1, --max-ifs >= 0 and --max-line >= 20")

    results = []
    for path in args.paths:
        try:
            src = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
        except OSError as e:
            print(f"error: cannot read {path}: {e.strerror}", file=sys.stderr)
            return 2
        except UnicodeDecodeError:
            print(f"error: {path} is not UTF-8 text", file=sys.stderr)
            return 2
        name = "<stdin>" if path == "-" else path
        try:
            findings = analyse(src, name, args.max_for, args.max_line, args.max_ifs)
        except SyntaxError as e:
            print(f"error: {name}:{e.lineno}: syntax error: {e.msg}", file=sys.stderr)
            return 2
        results.append((name, findings))

    total = sum(len(f) for _, f in results)
    if args.json:
        print(json.dumps({"files": [{"path": p, "findings": f} for p, f in results],
                          "summary": {"files": len(results), "findings": total}}, indent=2))
    else:
        print("\n".join(render(p, f) for p, f in results).rstrip())
        if len(results) > 1:
            print(f"\n{total} finding(s) across {len(results)} file(s).")
    return 1 if args.strict and total else 0


if __name__ == "__main__":
    sys.exit(main())
