#!/usr/bin/env python3
"""Audit Python exception handling with AST checks and suggest concrete fixes.

Static analysis only: the analysed code is parsed with `ast`, never imported
or executed. Rules:

  EXC001 bare-except            `except:` also catches KeyboardInterrupt, SystemExit, CancelledError
  EXC002 base-exception-swallow `except BaseException` without re-raising
  EXC003 broad-except-swallow   `except Exception` (or suppress(Exception)) that silently drops the error
  EXC004 raise-without-from     new exception raised inside `except` without `from err` / `from None`
  EXC005 generic-raise          `raise Exception(...)` / `raise BaseException(...)`
  EXC006 unreachable-handler    handler for a subclass placed after a handler for its base class
  EXC007 finally-control-flow   `return` / `break` / `continue` inside `finally` (swallows errors;
                                SyntaxWarning since 3.14, PEP 765)
  EXC008 cancellation-swallowed CancelledError / KeyboardInterrupt / SystemExit / GeneratorExit
                                caught without re-raise
  EXC009 assert-validation      `assert` on a function argument (stripped under `python -O`)
  EXC010 log-error-not-exception `logger.error(e)` in a handler instead of `logger.exception(...)`
  EXC011 try-too-large          try body with more than --max-try-body statements
  EXC012 useless-reraise        `except X: raise` with no later handler: a no-op
  EXC013 stringified-exception  `raise X(str(e))` / f"...{e}" without `from e`: type and traceback
                                of the original are flattened into a string
  EXC014 redundant-except-type  tuple member already covered by another member, e.g.
                                `except (json.JSONDecodeError, ValueError)`

Suppress a finding on its line with `# noqa` or `# noqa: EXC003,EXC010`.

Usage:
    python audit_exceptions.py app/llm_client.py
    python audit_exceptions.py src/ --json
    cat handler.py | python audit_exceptions.py -
    python audit_exceptions.py src/ --strict --ignore EXC011,EXC009
    python audit_exceptions.py src/ --select EXC001,EXC003,EXC008 --max-try-body 6

Exit codes: 0 no findings (or findings without --strict), 1 findings with
--strict, 2 usage error, unreadable file or syntax error.

No dependencies (standard library only, Python 3.9+).
"""

import argparse
import ast
import json
import os
import re
import sys

# ---------------------------------------------------------------- hierarchy

# child -> parents. Builtins plus common stdlib / AI-stack exceptions that are
# usually referenced by their last dotted name (json.JSONDecodeError, ...).
PARENTS = {
    "BaseException": (),
    "BaseExceptionGroup": ("BaseException",),
    "GeneratorExit": ("BaseException",),
    "KeyboardInterrupt": ("BaseException",),
    "SystemExit": ("BaseException",),
    "CancelledError": ("BaseException",),  # asyncio / concurrent.futures, 3.8+
    "Exception": ("BaseException",),
    "ExceptionGroup": ("BaseExceptionGroup", "Exception"),
    "ArithmeticError": ("Exception",),
    "FloatingPointError": ("ArithmeticError",),
    "OverflowError": ("ArithmeticError",),
    "ZeroDivisionError": ("ArithmeticError",),
    "AssertionError": ("Exception",),
    "AttributeError": ("Exception",),
    "BufferError": ("Exception",),
    "EOFError": ("Exception",),
    "ImportError": ("Exception",),
    "ModuleNotFoundError": ("ImportError",),
    "LookupError": ("Exception",),
    "IndexError": ("LookupError",),
    "KeyError": ("LookupError",),
    "MemoryError": ("Exception",),
    "NameError": ("Exception",),
    "UnboundLocalError": ("NameError",),
    "OSError": ("Exception",),
    "BlockingIOError": ("OSError",),
    "ChildProcessError": ("OSError",),
    "ConnectionError": ("OSError",),
    "BrokenPipeError": ("ConnectionError",),
    "ConnectionAbortedError": ("ConnectionError",),
    "ConnectionRefusedError": ("ConnectionError",),
    "ConnectionResetError": ("ConnectionError",),
    "FileExistsError": ("OSError",),
    "FileNotFoundError": ("OSError",),
    "InterruptedError": ("OSError",),
    "IsADirectoryError": ("OSError",),
    "NotADirectoryError": ("OSError",),
    "PermissionError": ("OSError",),
    "ProcessLookupError": ("OSError",),
    "TimeoutError": ("OSError",),  # asyncio.TimeoutError is an alias since 3.11
    "ReferenceError": ("Exception",),
    "RuntimeError": ("Exception",),
    "NotImplementedError": ("RuntimeError",),
    "RecursionError": ("RuntimeError",),
    "PythonFinalizationError": ("RuntimeError",),
    "StopAsyncIteration": ("Exception",),
    "StopIteration": ("Exception",),
    "SyntaxError": ("Exception",),
    "IndentationError": ("SyntaxError",),
    "TabError": ("IndentationError",),
    "SystemError": ("Exception",),
    "TypeError": ("Exception",),
    "ValueError": ("Exception",),
    "UnicodeError": ("ValueError",),
    "UnicodeDecodeError": ("UnicodeError",),
    "UnicodeEncodeError": ("UnicodeError",),
    "UnicodeTranslateError": ("UnicodeError",),
    "Warning": ("Exception",),
    "UserWarning": ("Warning",),
    "DeprecationWarning": ("Warning",),
    "PendingDeprecationWarning": ("Warning",),
    "RuntimeWarning": ("Warning",),
    "SyntaxWarning": ("Warning",),
    "FutureWarning": ("Warning",),
    "ImportWarning": ("Warning",),
    "UnicodeWarning": ("Warning",),
    "BytesWarning": ("Warning",),
    "ResourceWarning": ("Warning",),
    "EncodingWarning": ("Warning",),
    # stdlib extras
    "JSONDecodeError": ("ValueError",),
    "SubprocessError": ("Exception",),
    "CalledProcessError": ("SubprocessError",),
    "TimeoutExpired": ("SubprocessError",),
    "IncompleteReadError": ("EOFError",),
    "InvalidStateError": ("Exception",),
    "BrokenProcessPool": ("RuntimeError",),
    # torch.cuda.OutOfMemoryError (torch >= 1.13) subclasses RuntimeError
    "OutOfMemoryError": ("RuntimeError",),
}
ALIASES = {"IOError": "OSError", "EnvironmentError": "OSError", "WindowsError": "OSError"}
CANCELLATION = {"CancelledError", "KeyboardInterrupt", "SystemExit", "GeneratorExit"}
LOG_ATTRS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "fatal", "log",
             "print_exc", "print_exception", "capture_exception", "record_exception", "set_status"}
LOG_NAMES = {"print", "warn", "print_exc", "print_exception", "capture_exception"}
EXIT_CALLS = {"sys.exit", "exit", "quit", "os._exit", "pytest.fail", "pytest.skip", "os.abort"}
TRIVIAL = (ast.Pass, ast.Continue, ast.Break)

# ---------------------------------------------------------------- rules

RULES = {
    "EXC001": ("bare-except", "high"),
    "EXC002": ("base-exception-swallow", "high"),
    "EXC003": ("broad-except-swallow", "high"),
    "EXC004": ("raise-without-from", "medium"),
    "EXC005": ("generic-raise", "medium"),
    "EXC006": ("unreachable-handler", "high"),
    "EXC007": ("finally-control-flow", "high"),
    "EXC008": ("cancellation-swallowed", "high"),
    "EXC009": ("assert-validation", "medium"),
    "EXC010": ("log-error-not-exception", "medium"),
    "EXC011": ("try-too-large", "low"),
    "EXC012": ("useless-reraise", "low"),
    "EXC013": ("stringified-exception", "medium"),
    "EXC014": ("redundant-except-type", "low"),
}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def dotted(node):
    """Return 'a.b.c' for Name/Attribute chains, else ''."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


def canonical(name):
    last = name.rsplit(".", 1)[-1]
    return ALIASES.get(last, last)


def handler_types(handler):
    """List of (display name, canonical short name) caught by an except clause."""
    t = handler.type
    if t is None:
        return []
    elts = t.elts if isinstance(t, ast.Tuple) else [t]
    out = []
    for e in elts:
        d = dotted(e)
        if d:
            out.append((d, canonical(d)))
    return out


def walk_local(stmts):
    """ast.walk over statements without descending into nested functions, classes or lambdas."""
    stack = list(stmts)
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                stack.append(child)


def reraises(stmts):
    for n in walk_local(stmts):
        if isinstance(n, ast.Raise):
            return True
        if isinstance(n, ast.Call) and dotted(n.func) in EXIT_CALLS:
            return True
    return False


def logs(stmts):
    for n in walk_local(stmts):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr in LOG_ATTRS:
                return True
            if isinstance(f, ast.Name) and f.id in LOG_NAMES:
                return True
    return False


def uses_name(nodes, name):
    if not name:
        return False
    return any(isinstance(n, ast.Name) and n.id == name for n in walk_local(nodes))


def is_trivial_body(stmts):
    for s in stmts:
        if isinstance(s, TRIVIAL):
            continue
        if isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant):
            continue  # docstring / Ellipsis
        if isinstance(s, ast.Return) and (s.value is None or isinstance(s.value, ast.Constant)):
            continue
        return False
    return True


def count_statements(stmts):
    n = 0
    for s in stmts:
        n += 1
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for field in ("body", "orelse", "finalbody"):
            n += count_statements(getattr(s, field, []) or [])
        for h in getattr(s, "handlers", []) or []:
            n += count_statements(h.body)
        for c in getattr(s, "cases", []) or []:  # match statement (3.10+)
            n += count_statements(c.body)
    return n


def finally_escapes(stmts, in_loop=False):
    """Yield return/break/continue nodes that jump out of a finally block."""
    for s in stmts:
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(s, ast.Return):
            yield s
        elif isinstance(s, (ast.Break, ast.Continue)) and not in_loop:
            yield s
        elif isinstance(s, (ast.For, ast.AsyncFor, ast.While)):
            yield from finally_escapes(s.body, True)
            yield from finally_escapes(s.orelse, in_loop)
        else:
            for field in ("body", "orelse", "finalbody"):
                yield from finally_escapes(getattr(s, field, []) or [], in_loop)
            for h in getattr(s, "handlers", []) or []:
                yield from finally_escapes(h.body, in_loop)
            for c in getattr(s, "cases", []) or []:
                yield from finally_escapes(c.body, in_loop)


def stringifies(node, name):
    """True if expression builds a string out of the caught exception `name`."""
    if not name:
        return False
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("str", "repr", "format"):
            if any(isinstance(a, ast.Name) and a.id == name for a in n.args):
                return True
        if isinstance(n, ast.FormattedValue) and isinstance(n.value, ast.Name) and n.value.id == name:
            return True
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mod) and isinstance(n.left, ast.Constant) \
                and uses_name([n.right], name):
            return True
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "format" \
                and isinstance(n.func.value, ast.Constant) \
                and any(uses_name([a], name) for a in list(n.args) + [k.value for k in n.keywords]):
            return True
    return False


def is_test_file(path):
    base = os.path.basename(path)
    return base.startswith("test_") or base.endswith("_test.py") or base == "conftest.py"


class Auditor(ast.NodeVisitor):
    def __init__(self, path, source, max_try_body):
        self.path = path
        self.lines = source.splitlines()
        self.max_try_body = max_try_body
        self.findings = []
        self.handlers = []      # stack of (ExceptHandler, bound name)
        self.params = []        # stack of parameter-name sets
        self.local_parents = {}
        self.test_file = is_test_file(path)

    # ------------------------------------------------------------ helpers
    def add(self, rule, node, message, fix):
        line = getattr(node, "lineno", 1)
        src = self.lines[line - 1] if 0 < line <= len(self.lines) else ""
        m = re.search(r"#\s*noqa(?::\s*([A-Z0-9, ]+))?", src)
        if m and (not m.group(1) or rule in [c.strip() for c in m.group(1).split(",")]):
            return
        name, sev = RULES[rule]
        self.findings.append({
            "path": self.path, "line": line, "col": getattr(node, "col_offset", 0) + 1,
            "rule": rule, "name": name, "severity": sev, "message": message,
            "code": src.strip(), "fix": fix,
        })

    def ancestors(self, name):
        seen, todo = set(), [name]
        while todo:
            n = todo.pop()
            if n in seen:
                continue
            seen.add(n)
            todo.extend(self.local_parents.get(n, PARENTS.get(n, ())))
        return seen

    def collect_classes(self, tree):
        for n in ast.walk(tree):
            if isinstance(n, ast.ClassDef):
                bases = tuple(canonical(dotted(b)) for b in n.bases if dotted(b))
                if bases:
                    self.local_parents[n.name] = bases

    # ------------------------------------------------------------ scopes
    def _visit_function(self, node):
        args = node.args
        names = {a.arg for a in args.args + args.kwonlyargs + getattr(args, "posonlyargs", [])}
        if args.vararg:
            names.add(args.vararg.arg)
        if args.kwarg:
            names.add(args.kwarg.arg)
        names -= {"self", "cls"}
        saved, self.handlers = self.handlers, []
        self.params.append(names)
        self.generic_visit(node)
        self.params.pop()
        self.handlers = saved

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def visit_Lambda(self, node):
        saved, self.handlers = self.handlers, []
        self.generic_visit(node)
        self.handlers = saved

    # ------------------------------------------------------------ try
    def visit_Try(self, node):
        star = type(node).__name__ == "TryStar"
        kw = "except*" if star else "except"

        size = count_statements(node.body)
        if size > self.max_try_body:
            self.add("EXC011", node, f"try body has {size} statements (limit {self.max_try_body}); the handler "
                     "cannot tell which call failed",
                     "Keep only the call that can raise inside `try`; move the rest to `else:`:\n"
                     "    try:\n        resp = await client.chat(messages)\n"
                     "    except RateLimitError as err:\n        ...\n    else:\n        return parse(resp)")

        seen = []  # (canonical, display, line) of earlier handlers
        for i, h in enumerate(node.handlers):
            types = handler_types(h)
            canon = {c for _, c in types}
            body = h.body
            bound = h.name

            if h.type is None:
                if reraises(body):
                    self.add("EXC001", h, "bare `except:` catches KeyboardInterrupt, SystemExit and "
                             "asyncio.CancelledError (it re-raises, but say so explicitly)",
                             "Write `except BaseException:` when cleanup-then-reraise is intended, "
                             "or better, move cleanup into `finally:`.")
                else:
                    self.add("EXC001", h, "bare `except:` swallows everything, including Ctrl+C, sys.exit() "
                             "and task cancellation",
                             "Catch the specific errors you can handle:\n"
                             "    except (httpx.TimeoutException, httpx.ConnectError) as err:\n"
                             "        logger.warning(\"embedding call failed\", exc_info=err)\n"
                             "        raise EmbeddingError(\"embedding service unavailable\") from err")
            if "BaseException" in canon and not reraises(body):
                self.add("EXC002", h, f"`{kw} BaseException` without re-raise swallows KeyboardInterrupt, "
                         "SystemExit and CancelledError",
                         "Re-raise after cleanup:\n    except BaseException:\n        await stream.aclose()\n"
                         "        raise\nor catch `Exception` instead.")
            hit = sorted(canon & CANCELLATION)
            if hit and "BaseException" not in canon and not reraises(body):
                # A CLI turning Ctrl+C / exit into a return code, or a sandbox recording a
                # SystemExit, handles it deliberately; CancelledError/GeneratorExit never may.
                deliberate = set(hit) <= {"KeyboardInterrupt", "SystemExit"} and (
                    uses_name(body, bound) or any(isinstance(n, ast.Return) for n in walk_local(body)))
                if not deliberate:
                    self.add("EXC008", h, f"{', '.join(hit)} caught and not re-raised: the task/process "
                             "can no longer be cancelled or stopped",
                             "Always finish with a bare `raise`:\n    except asyncio.CancelledError:\n"
                             "        await client.aclose()  # cleanup only\n        raise")
            if "Exception" in canon and "BaseException" not in canon \
                    and not reraises(body) and not logs(body) and not uses_name(body, bound):
                trivial = is_trivial_body(body)
                what = "silently swallows every error" if trivial else "falls back silently (nothing logged)"
                self.add("EXC003", h, f"broad `{kw} Exception` {what}; bugs like TypeError/KeyError vanish",
                         "Narrow the type, or log and re-raise / translate:\n"
                         "    except Exception:\n        logger.exception(\"rerank failed; using vector order\", "
                         "extra={\"query_id\": qid})\n        return candidates  # explicit, observable fallback")

            # unreachable handlers
            for disp, c in types:
                anc = self.ancestors(c)
                for prev_c, prev_d, prev_line in seen:
                    if prev_c in anc:
                        self.add("EXC006", h, f"`{disp}` is never reached: it is a subclass of `{prev_d}`, "
                                 f"already caught on line {prev_line}",
                                 f"Move the `{kw} {disp}` handler above the `{kw} {prev_d}` handler "
                                 "(most specific first).")
                        break
            # redundant members within one tuple
            for disp, c in types:
                others = [(d2, c2) for d2, c2 in types if c2 != c and c2 in self.ancestors(c)]
                if others:
                    self.add("EXC014", h, f"`{disp}` is redundant in this tuple: `{others[0][0]}` already "
                             "covers it", f"Remove `{disp}` from the tuple.")
            seen.extend((c, d, h.lineno) for d, c in types)

            # useless re-raise: only `raise` / `raise err` and nothing later to fall through to
            if len(body) == 1 and isinstance(body[0], ast.Raise) and body[0].cause is None and (
                    body[0].exc is None or (isinstance(body[0].exc, ast.Name) and body[0].exc.id == bound)) \
                    and i == len(node.handlers) - 1:
                self.add("EXC012", h, f"`{kw} ...: raise` with no later handler does nothing",
                         "Delete the handler (keep `finally:` if you need cleanup), or add context first:\n"
                         "    except ProviderError as err:\n        err.add_note(f\"model={model}\")  # 3.11+\n"
                         "        raise")

        for s in finally_escapes(node.finalbody):
            word = type(s).__name__.lower()
            self.add("EXC007", s, f"`{word}` inside `finally` discards any in-flight exception "
                     "(SyntaxWarning since Python 3.14, PEP 765)",
                     "Move the `return`/`break` after the try statement; keep `finally` for cleanup only.")

        for n in node.body:
            self.visit(n)
        for h in node.handlers:
            if h.type is not None:
                self.visit(h.type)
            self.handlers.append((h, h.name))
            for n in h.body:
                self.visit(n)
            self.handlers.pop()
        for n in node.orelse + node.finalbody:
            self.visit(n)

    visit_TryStar = visit_Try

    # ------------------------------------------------------------ raise
    def visit_Raise(self, node):
        exc = node.exc
        target = exc.func if isinstance(exc, ast.Call) else exc
        name = dotted(target) if target is not None else ""
        if name in ("Exception", "BaseException"):
            self.add("EXC005", node, f"`raise {name}(...)` forces callers to catch everything",
                     "Raise a specific builtin (ValueError, TypeError, RuntimeError) or a domain error:\n"
                     "    class ProviderError(AppError): ...\n    raise ProviderError(\"upstream returned 500\", "
                     "provider=\"openai\")")
        if self.handlers and exc is not None and node.cause is None:
            h, bound = self.handlers[-1]
            new_exc = isinstance(exc, ast.Call) or (isinstance(exc, (ast.Name, ast.Attribute))
                                                    and name.rsplit(".", 1)[-1][:1].isupper())
            if new_exc and not (isinstance(exc, ast.Name) and exc.id == bound) \
                    and canonical(name) not in ("SystemExit", "KeyboardInterrupt", "StopIteration",
                                                "StopAsyncIteration", "GeneratorExit") \
                    and not (isinstance(exc, ast.Call) and isinstance(exc.func, ast.Attribute)
                             and dotted(exc.func.value) == bound):
                var = bound or "err"
                if isinstance(exc, ast.Call) and stringifies(exc, bound):
                    self.add("EXC013", node, f"exception message is built from `{bound}` but the original "
                             "is not chained; type and traceback are flattened into a string",
                             f"Keep a short message and chain the cause:\n    raise {name or 'AppError'}"
                             f"(\"model returned invalid JSON\") from {var}")
                else:
                    as_hint = "" if bound else " (bind it: `except X as err:`)"
                    self.add("EXC004", node, "new exception raised inside `except` without `from`; the "
                             "traceback reads 'During handling ... another exception occurred'" + as_hint,
                             f"raise {ast.unparse(exc)} from {var}    # translating: keep the cause\n"
                             f"raise {ast.unparse(exc)} from None    # deliberately hiding internals")
        self.generic_visit(node)

    # ------------------------------------------------------------ assert
    def visit_Assert(self, node):
        if not self.test_file and self.params:
            used = sorted({n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)} & self.params[-1])
            if used:
                cond = ast.unparse(node.test)
                self.add("EXC009", node, f"`assert` validates argument `{used[0]}`; asserts are removed "
                         "under `python -O`, so the check silently disappears",
                         f"if not ({cond}):\n    raise ValueError(f\"invalid {used[0]}: {{{used[0]}!r}}\")")
        self.generic_visit(node)

    # ------------------------------------------------------------ calls
    def visit_Call(self, node):
        f = node.func
        if self.handlers and isinstance(f, ast.Attribute) and f.attr in ("error", "critical"):
            _, bound = self.handlers[-1]
            recv_name = dotted(f.value)
            if bound and "log" in recv_name.lower() and not any(k.arg == "exc_info" for k in node.keywords) \
                    and any(uses_name([a], bound) for a in node.args):
                recv = recv_name
                self.add("EXC010", node, f"`{recv}.{f.attr}(... {bound} ...)` logs only str({bound}); the "
                         "traceback and exception type are lost",
                         f"{recv}.exception(\"embedding batch failed\", extra={{\"batch\": i}})  "
                         f"# or {recv}.{f.attr}(..., exc_info=True)")
        name = dotted(f)
        if name.rsplit(".", 1)[-1] == "suppress":
            for a in node.args:
                if canonical(dotted(a)) in ("Exception", "BaseException"):
                    self.add("EXC003", node, f"`suppress({dotted(a)})` silently swallows every error in "
                             "the block", "Suppress only the expected error, e.g. "
                             "`with suppress(FileNotFoundError):`, or log it in an explicit except.")
        self.generic_visit(node)


# ---------------------------------------------------------------- driver

def audit_source(source, path, max_try_body):
    tree = ast.parse(source, filename=path)
    a = Auditor(path, source, max_try_body)
    a.collect_classes(tree)
    a.visit(tree)
    return a.findings


def expand(paths):
    skip = {".git", ".venv", "venv", "__pycache__", "node_modules", ".tox", ".mypy_cache", "build", "dist"}
    for p in paths:
        if p != "-" and os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d not in skip)
                for f in sorted(files):
                    if f.endswith(".py"):
                        yield os.path.join(root, f)
        else:
            yield p


def parse_rule_list(values):
    out = []
    for v in values or []:
        for tok in v.split(","):
            tok = tok.strip()
            if not tok:
                continue
            matched = [rid for rid, (slug, _) in RULES.items() if rid.startswith(tok.upper()) or slug == tok]
            if not matched:
                raise ValueError(f"unknown rule {tok!r}; known: {', '.join(RULES)}")
            out.extend(matched)
    return set(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="Python files or directories, or - for stdin")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any finding is reported")
    ap.add_argument("--select", action="append", help="only these rules (ids, id prefixes or names; comma list)")
    ap.add_argument("--ignore", action="append", help="skip these rules (ids, id prefixes or names; comma list)")
    ap.add_argument("--max-try-body", type=int, default=10, metavar="N",
                    help="statements allowed in a try body before EXC011 (default 10)")
    args = ap.parse_args()

    try:
        select = parse_rule_list(args.select) or set(RULES)
        ignore = parse_rule_list(args.ignore)
    except ValueError as err:
        ap.error(str(err))
    if args.max_try_body < 1:
        ap.error("--max-try-body must be >= 1")

    findings, errors, files = [], [], 0
    for path in expand(args.paths):
        label = "<stdin>" if path == "-" else path
        try:
            if path == "-":
                source = sys.stdin.read()
            else:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
            findings.extend(audit_source(source, label, args.max_try_body))
            files += 1
        except SyntaxError as err:
            errors.append(f"{label}:{err.lineno}: cannot parse: {err.msg}")
        except (OSError, UnicodeDecodeError) as err:
            errors.append(f"{label}: cannot read: {err}")

    findings = [f for f in findings if f["rule"] in select and f["rule"] not in ignore]
    findings.sort(key=lambda f: (f["path"], f["line"], f["col"], f["rule"]))
    counts = {s: sum(f["severity"] == s for f in findings) for s in SEVERITY_ORDER}

    if args.json:
        print(json.dumps({"files": files, "summary": counts, "errors": errors, "findings": findings}, indent=2))
    else:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        if not findings and files:
            print(f"No exception-handling issues found in {files} file(s).")
        else:
            print(f"{len(findings)} finding(s) in {files} file(s): {counts['high']} high, "
                  f"{counts['medium']} medium, {counts['low']} low\n")
            for f in findings:
                print(f"{f['path']}:{f['line']}:{f['col']}: {f['rule']} [{f['severity']}] {f['name']}: "
                      f"{f['message']}")
                if f["code"]:
                    print(f"    > {f['code']}")
                print("    fix: " + f["fix"].replace("\n", "\n         "))
                print()
    if errors:
        sys.exit(2)
    sys.exit(1 if args.strict and findings else 0)


if __name__ == "__main__":
    main()
