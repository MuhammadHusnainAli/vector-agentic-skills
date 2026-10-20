#!/usr/bin/env python3
"""Generate an `errors.py` exception hierarchy for a package from a compact spec.

Every generated class derives from one package base error (`<Package>Error`)
and carries a `retryable` flag, a stable `code`, keyword-only context
attributes, a readable `__str__`, `to_dict()` for structured logs/API bodies
and pickling support (multiprocessing, Celery, Ray). The module also gets
`is_retryable(exc)` for retry predicates (tenacity, custom backoff loops) and,
with --http, an HTTP status table plus `register_exception_handlers(app)` for
FastAPI/Starlette (fastapi is imported lazily inside that function).

Error spec grammar (one per --errors value):
    Name[(Parent)][:option,option,...]
options:
    retryable | retryable=false   transient failure, safe to retry with backoff
    http=429                      HTTP status for --http (otherwise guessed from the name)
    code=rate_limited             stable machine-readable code (default: snake_case name)
    attr | attr=type              keyword-only attribute, e.g. retry_after=float, tokens=int

JSON spec (--spec file.json, or --spec - for stdin):
    {"package": "ragkit", "base": "RagkitError", "http": true,
     "errors": ["ProviderError:retryable,provider=str",
                {"name": "RateLimitError", "parent": "ProviderError", "retryable": true,
                 "attrs": {"retry_after": "float"}, "http": 429, "doc": "Provider returned 429."}]}

Usage:
    python scaffold_exceptions.py --package ragkit --errors "ProviderError:retryable" \\
        "RateLimitError(ProviderError):retryable,retry_after=float" "ContextLengthError(ProviderError):tokens=int"
    python scaffold_exceptions.py --package ragkit --preset llm-app --http -o src/ragkit/errors.py
    python scaffold_exceptions.py --spec errors.json --json
    python scaffold_exceptions.py --package ragkit --preset llm-app --http --check src/ragkit/errors.py

The generated source is verified with ast.parse/compile before it is written.
Nothing is imported or executed.

Exit codes: 0 generated (or --check matches), 1 --check found drift,
2 usage error, invalid spec or generated code that does not compile.

No dependencies (standard library only, Python 3.9+).
"""

import argparse
import ast
import builtins
import json
import keyword
import re
import sys

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SPEC_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*(?:\(\s*([A-Za-z_]\w*)\s*\))?\s*(?::\s*(.*))?$")

# Name keyword -> HTTP status used when --http is on and no explicit http= is given.
HTTP_GUESS = [
    ("RateLimit", 429), ("Budget", 429), ("Quota", 429), ("NotFound", 404), ("Missing", 404),
    ("Validation", 422), ("ContentFilter", 422), ("Invalid", 400), ("ContextLength", 413),
    ("TooLarge", 413), ("Unauthorized", 401), ("Authentication", 401), ("Permission", 403),
    ("Forbidden", 403), ("Conflict", 409), ("Timeout", 504), ("Overloaded", 503),
    ("Unavailable", 503), ("CircuitOpen", 503), ("VectorStore", 503), ("ResourceExhausted", 503),
    ("Provider", 502), ("Upstream", 502), ("Output", 502), ("Embedding", 502),
]

PRESETS = {
    "llm-app": [
        {"name": "ConfigurationError", "http": 500,
         "doc": "Missing or invalid configuration: API keys, model names, index names, settings.\n\n"
                "A deployment bug. Never retry; fail fast at startup where possible."},
        {"name": "InputValidationError", "http": 422, "attrs": {"field": "str"},
         "doc": "Caller input was rejected before any model call (empty query, bad top_k, oversize upload)."},
        {"name": "NotFoundError", "http": 404, "attrs": {"resource": "str", "resource_id": "str"},
         "doc": "A document, collection, prompt template or conversation does not exist."},
        {"name": "ProviderError", "http": 502, "attrs": {"provider": "str", "model": "str"},
         "doc": "An LLM or embedding provider call failed.\n\n"
                "Base for all upstream model errors. Translate SDK exceptions (openai, anthropic, httpx)\n"
                "into a subclass at the client wrapper with `raise ... from err`."},
        {"name": "RateLimitError", "parent": "ProviderError", "retryable": True, "http": 429,
         "attrs": {"retry_after": "float"},
         "doc": "Provider returned HTTP 429. Honour `retry_after` (seconds) before retrying."},
        {"name": "ProviderOverloadedError", "parent": "ProviderError", "retryable": True, "http": 503,
         "attrs": {"status_code": "int"},
         "doc": "Provider returned 500/502/503/529 (overloaded). Retry with exponential backoff and jitter,\n"
                "then fall back to another model."},
        {"name": "ProviderTimeoutError", "parent": "ProviderError", "retryable": True, "http": 504,
         "attrs": {"timeout": "float"},
         "doc": "The request exceeded its deadline (connect, read or total timeout)."},
        {"name": "ProviderAuthError", "parent": "ProviderError", "http": 500,
         "doc": "The provider rejected our credentials (401/403). A configuration problem: do not retry."},
        {"name": "ContextLengthError", "parent": "ProviderError", "http": 413,
         "attrs": {"tokens": "int", "limit": "int"},
         "doc": "Prompt plus max_tokens exceeds the model's context window.\n\n"
                "Not retryable as-is: truncate history, drop retrieved chunks or switch to a larger model."},
        {"name": "ContentFilterError", "parent": "ProviderError", "http": 422, "attrs": {"category": "str"},
         "doc": "The provider refused or filtered the request/response (safety system)."},
        {"name": "StreamInterruptedError", "parent": "ProviderError", "retryable": True, "http": 502,
         "attrs": {"received_chars": "int"},
         "doc": "A streaming response broke mid-way. `received_chars` tells the caller how much was\n"
                "already delivered, so it can resume or restart instead of duplicating output."},
        {"name": "EmbeddingError", "parent": "ProviderError", "retryable": True, "http": 502,
         "attrs": {"failed_indices": "List[int]"},
         "doc": "Some or all inputs of an embedding batch failed; retry only `failed_indices`."},
        {"name": "StructuredOutputError", "retryable": True, "http": 502,
         "attrs": {"raw_output": "str", "errors": "List[str]"},
         "doc": "Model output was not valid JSON or failed schema validation.\n\n"
                "Retryable through a repair loop: send `errors` back to the model with the raw output."},
        {"name": "ToolExecutionError", "http": 500, "attrs": {"tool_name": "str", "call_id": "str"},
         "doc": "A tool/function call requested by the model raised.\n\n"
                "Usually reported back to the model as a tool result instead of being raised to the user."},
        {"name": "RetrievalError", "http": 503,
         "doc": "Retrieval failed (vector search, keyword search, reranking)."},
        {"name": "VectorStoreError", "parent": "RetrievalError", "retryable": True, "http": 503,
         "attrs": {"store": "str", "collection": "str"},
         "doc": "Vector database unreachable or returned an error (connection reset, timeout, 5xx)."},
        {"name": "ResourceExhaustedError", "http": 503, "attrs": {"device": "str"},
         "doc": "Local compute ran out (CUDA OOM, host RAM). Retry only after reducing batch size."},
        {"name": "CircuitOpenError", "retryable": True, "http": 503, "attrs": {"retry_after": "float"},
         "doc": "A circuit breaker is open for this dependency; calls are short-circuited until it half-opens."},
        {"name": "BudgetExceededError", "http": 429, "attrs": {"spent": "float", "budget": "float"},
         "doc": "A token or cost budget for the user/request/tenant was exhausted."},
    ],
}


class SpecError(ValueError):
    pass


def camel_words(name):
    words = re.findall(r"[A-Z]+(?=[A-Z][a-z]|\d|\b)|[A-Z]?[a-z]+|[A-Z]+|\d+", name)
    return [w.lower() for w in words]


def snake(name):
    words = camel_words(name)
    if len(words) > 1 and words[-1] == "error":
        words = words[:-1]
    return "_".join(words) or name.lower()


def package_class(package):
    parts = re.split(r"[^A-Za-z0-9]+", package)
    return "".join(p[:1].upper() + p[1:] for p in parts if p) + "Error"


def check_ident(name, what):
    if not IDENT.match(name) or keyword.iskeyword(name):
        raise SpecError(f"{what} {name!r} is not a valid Python identifier")


def check_type(text, attr):
    try:
        ast.parse(text, mode="eval")
    except SyntaxError:
        raise SpecError(f"attribute {attr!r}: type {text!r} is not a valid annotation") from None


def parse_compact(text):
    m = SPEC_RE.match(text)
    if not m:
        raise SpecError(f"cannot parse error spec {text!r}; expected Name[(Parent)][:opt,opt]")
    entry = {"name": m.group(1), "parent": m.group(2), "attrs": {}}
    for opt in filter(None, (o.strip() for o in (m.group(3) or "").split(","))):
        key, _, val = opt.partition("=")
        key, val = key.strip(), val.strip()
        if key == "retryable":
            if val.lower() not in ("", "true", "false", "yes", "no", "1", "0"):
                raise SpecError(f"{text!r}: retryable must be true/false")
            entry["retryable"] = val.lower() in ("", "true", "yes", "1")
        elif key == "http":
            if not val.isdigit():
                raise SpecError(f"{text!r}: http= needs a status code")
            entry["http"] = int(val)
        elif key == "code":
            entry["code"] = val
        else:
            entry["attrs"][key] = val or "Any"
    return entry


def normalise(entry):
    if isinstance(entry, str):
        entry = parse_compact(entry)
    elif not isinstance(entry, dict) or "name" not in entry:
        raise SpecError(f"each error must be a string or an object with 'name', got {entry!r}")
    attrs = entry.get("attrs") or {}
    if isinstance(attrs, list):
        attrs = {a: "Any" for a in attrs}
    out = {"name": entry["name"], "parent": entry.get("parent"), "retryable": bool(entry.get("retryable")),
           "http": entry.get("http"), "code": entry.get("code") or snake(entry["name"]),
           "doc": entry.get("doc"), "attrs": dict(attrs)}
    check_ident(out["name"], "error name")
    if out["parent"]:
        check_ident(out["parent"], "parent")
    if out["http"] is not None and not (isinstance(out["http"], int) and 100 <= out["http"] <= 599):
        raise SpecError(f"{out['name']}: http status must be an integer 100-599")
    for a, t in out["attrs"].items():
        check_ident(a, f"{out['name']} attribute")
        if a in ("message", "context", "args", "code", "retryable", "default_message"):
            raise SpecError(f"{out['name']}: attribute name {a!r} is reserved by the base class")
        check_type(t, a)
    return out


def order_errors(errors, base):
    by_name = {}
    for e in errors:
        if e["name"] in by_name:
            by_name[e["name"]] = e  # later definitions override (preset + --errors)
        else:
            by_name[e["name"]] = e
        if e["name"] == base:
            raise SpecError(f"{base!r} is the generated base class; do not declare it")
        if hasattr(builtins, e["name"]):
            raise SpecError(f"{e['name']!r} shadows a builtin exception; prefix it (e.g. Provider{e['name']})")
    ordered, state = [], {}

    def visit(name, chain):
        if state.get(name) == "done":
            return
        if state.get(name) == "active":
            raise SpecError("inheritance cycle: " + " -> ".join(chain + [name]))
        state[name] = "active"
        parent = by_name[name]["parent"]
        if parent and parent != base:
            if parent not in by_name:
                raise SpecError(f"{name}: unknown parent {parent!r} (declare it, or omit to use {base})")
            visit(parent, chain + [name])
        state[name] = "done"
        ordered.append(by_name[name])

    for name in by_name:
        visit(name, [])
    for e in ordered:
        if not e["parent"]:
            e["parent"] = base
    return ordered


def guess_http(e, by_name, base):
    if e["http"]:
        return e["http"]
    for key, status in HTTP_GUESS:
        if key in e["name"]:
            return status
    parent = e["parent"]
    if parent and parent != base and parent in by_name:
        return guess_http(by_name[parent], by_name, base)
    return 500


def tree_lines(errors, base):
    children = {}
    for e in errors:
        children.setdefault(e["parent"], []).append(e)
    lines = [base]

    def walk(name, prefix):
        kids = children.get(name, [])
        for i, k in enumerate(kids):
            last = i == len(kids) - 1
            flag = "  [retryable]" if k["retryable"] else ""
            lines.append(f"{prefix}{'`-- ' if last else '|-- '}{k['name']}{flag}")
            walk(k["name"], prefix + ("    " if last else "|   "))

    walk(base, "")
    return lines


def indent(text, n):
    pad = " " * n
    return "\n".join(pad + line if line.strip() else "" for line in text.splitlines())


def render(package, base, errors, http):
    by_name = {e["name"]: e for e in errors}
    names = [base] + [e["name"] for e in errors]
    out = []
    w = out.append
    tree = "\n".join("    " + line for line in tree_lines(errors, base))
    w(f'"""Exception hierarchy for {package}.\n\nGenerated by scaffold_exceptions.py. Catch `{base}` at '
      f'application boundaries;\ncatch subclasses where you can actually recover.\n\nHierarchy:\n{tree}\n"""')
    w("from __future__ import annotations\n")
    w("import asyncio")
    if http:
        w("import logging\nimport math")
    w("from typing import Any, ClassVar, Dict, List, Optional, Tuple, Type  # noqa: F401\n")
    all_names = names + ["is_retryable"] + (["HTTP_STATUS", "http_status_for", "register_exception_handlers"]
                                            if http else [])
    w("__all__ = [\n" + "".join(f'    "{n}",\n' for n in all_names) + "]\n")
    if http:
        w("logger = logging.getLogger(__name__)\n")
    w("\ndef _restore(cls: Type[BaseException], message: Optional[str], context: Dict[str, Any]) -> BaseException:")
    w('    """Unpickle helper: rebuild an error from its message and keyword context."""')
    w("    return cls(message, **context)\n")
    w(f'''
class {base}(Exception):
    """Base class for every error raised by {package}.

    Attributes:
        message: human-readable description (safe to log).
        context: keyword context passed by the raiser (ids, model names, counts).
    """

    retryable: ClassVar[bool] = False
    code: ClassVar[str] = "{"_".join(camel_words(base))}"
    default_message: ClassVar[str] = "{" ".join(camel_words(base)).capitalize()}"

    def __init__(self, message: Optional[str] = None, **context: Any) -> None:
        self.message = message or self.default_message
        self.context = context
        super().__init__(self.message)

    def __str__(self) -> str:
        details = ", ".join(f"{{k}}={{v!r}}" for k, v in self.context.items() if v is not None)
        return f"{{self.message}} ({{details}})" if details else self.message

    def __reduce__(self) -> Tuple[Any, ...]:
        # Keyword-only __init__ arguments break the default exception pickling.
        return (_restore, (type(self), self.message, self.context))

    def to_dict(self) -> Dict[str, Any]:
        """JSON-safe payload for structured logs and API error bodies."""
        details = {{
            k: v if isinstance(v, (str, int, float, bool)) else repr(v)
            for k, v in self.context.items()
            if v is not None
        }}
        return {{"error": self.code, "message": self.message, "retryable": self.retryable, **details}}
''')
    for e in errors:
        human = " ".join(camel_words(e["name"])).capitalize()
        doc = e["doc"] or f"{human}."
        if e["retryable"] and not e["doc"]:
            doc += "\n\nRetryable: callers may retry with exponential backoff and jitter."
        if e["attrs"]:
            doc += "\n\nAttributes:\n" + "\n".join(f"    {a}: {t}" for a, t in e["attrs"].items())
        w(f"\nclass {e['name']}({e['parent']}):")
        w(indent(f'"""{doc}\n"""', 4))
        w("")
        if e["retryable"]:
            w("    retryable: ClassVar[bool] = True")
        w(f'    code: ClassVar[str] = "{e["code"]}"')
        w(f'    default_message: ClassVar[str] = "{human}"')
        if e["attrs"]:
            params = ", ".join(f"{a}: Optional[{t}] = None" for a, t in e["attrs"].items())
            passes = ", ".join(f"{a}={a}" for a in e["attrs"])
            w("")
            w(f"    def __init__(self, message: Optional[str] = None, *, {params}, **context: Any) -> None:")
            for a in e["attrs"]:
                w(f"        self.{a} = {a}")
            w(f"        super().__init__(message, {passes}, **context)")
        w("")

    w('''
_TRANSIENT_BUILTINS: Tuple[Type[BaseException], ...] = (TimeoutError, ConnectionError, asyncio.TimeoutError)


def is_retryable(exc: BaseException) -> bool:
    """True if repeating the same call may succeed.

    Use as a retry predicate, e.g. tenacity's ``retry=retry_if_exception(is_retryable)``.
    asyncio.CancelledError, KeyboardInterrupt and programming errors are never retryable.
    """
    if isinstance(exc, ''' + base + '''):
        return exc.retryable
    return isinstance(exc, _TRANSIENT_BUILTINS)
''')
    if http:
        rows = "".join(f"    {n}: {500 if n == base else guess_http(by_name[n], by_name, base)},\n"
                       for n in names)
        w(f'''
HTTP_STATUS: Dict[Type[{base}], int] = {{
{rows}}}


def http_status_for(exc: BaseException) -> int:
    """Most specific HTTP status for an exception (walks the MRO); 500 for anything unknown."""
    for cls in type(exc).__mro__:
        if cls in HTTP_STATUS:
            return HTTP_STATUS[cls]
    return 500


def register_exception_handlers(app: Any) -> None:
    """Translate every {base} into a JSON error response on a FastAPI/Starlette app.

    4xx responses include the error context; 5xx responses hide it and log the traceback.
    A `retry_after` attribute becomes a Retry-After header.
    """
    from fastapi import Request
    from fastapi.responses import JSONResponse

    async def handle(request: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, {base}):  # registered for {base} only
            raise exc
        status = http_status_for(exc)
        headers: Dict[str, str] = {{}}
        retry_after = getattr(exc, "retry_after", None)
        if retry_after is not None:
            headers["Retry-After"] = str(max(1, math.ceil(retry_after)))
        if status >= 500:
            logger.error("request failed: %s", exc.code, exc_info=exc,
                         extra={{"path": request.url.path, "error_code": exc.code}})
            body = {{"error": exc.code, "message": exc.default_message, "retryable": exc.retryable}}
        else:
            body = exc.to_dict()
        return JSONResponse(status_code=status, content=body, headers=headers)

    app.add_exception_handler({base}, handle)
''')
    return "\n".join(out).rstrip() + "\n"


def build(args):
    spec = {}
    if args.spec:
        try:
            raw = sys.stdin.read() if args.spec == "-" else open(args.spec, encoding="utf-8").read()
            spec = json.loads(raw)
        except OSError as err:
            raise SpecError(f"cannot read spec: {err}") from err
        except json.JSONDecodeError as err:
            raise SpecError(f"spec is not valid JSON: {err}") from err
        if not isinstance(spec, dict):
            raise SpecError("spec must be a JSON object")
    package = args.package or spec.get("package")
    if not package:
        raise SpecError("--package is required (or 'package' in the JSON spec)")
    base = args.base or spec.get("base") or package_class(package)
    check_ident(base, "base class")
    preset = args.preset or spec.get("preset")
    entries = list(PRESETS[preset]) if preset else []
    entries += list(spec.get("errors") or [])
    entries += list(args.errors or [])
    if not entries:
        raise SpecError("no errors given: use --errors, --preset or a JSON spec")
    errors = order_errors([normalise(e) for e in entries], base)
    http = args.http or bool(spec.get("http"))
    return package, base, errors, http, render(package, base, errors, http)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package", help="package name, e.g. ragkit (base class becomes RagkitError)")
    ap.add_argument("--base", help="override the base class name")
    ap.add_argument("--errors", nargs="+", metavar="SPEC", help="compact error specs (see grammar above)")
    ap.add_argument("--spec", metavar="FILE", help="JSON spec file, or - for stdin")
    ap.add_argument("--preset", choices=sorted(PRESETS), help="start from a ready-made hierarchy")
    ap.add_argument("--http", action="store_true", help="add HTTP status mapping and FastAPI handler registration")
    ap.add_argument("-o", "--output", metavar="FILE", help="write to FILE instead of stdout")
    ap.add_argument("--force", action="store_true", help="overwrite --output if it exists")
    ap.add_argument("--check", metavar="FILE", help="exit 1 if FILE differs from what would be generated")
    ap.add_argument("--json", action="store_true", help="emit JSON (classes, statuses and the module source)")
    args = ap.parse_args()

    try:
        package, base, errors, http, code = build(args)
    except SpecError as err:
        print(f"error: {err}", file=sys.stderr)
        sys.exit(2)

    try:
        compile(ast.parse(code), "errors.py", "exec")
    except SyntaxError as err:
        print(f"error: generated code does not compile (line {err.lineno}): {err.msg}", file=sys.stderr)
        sys.exit(2)

    if args.check:
        try:
            current = open(args.check, encoding="utf-8").read()
        except OSError as err:
            print(f"error: cannot read {args.check}: {err}", file=sys.stderr)
            sys.exit(2)
        if current != code:
            print(f"{args.check} is out of date; regenerate with the same arguments and -o {args.check} --force")
            sys.exit(1)
        print(f"{args.check} is up to date ({len(errors) + 1} classes).")
        sys.exit(0)

    if args.output:
        import os
        if os.path.exists(args.output) and not args.force:
            print(f"error: {args.output} exists; pass --force to overwrite", file=sys.stderr)
            sys.exit(2)
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(code)

    if args.json:
        by_name = {e["name"]: e for e in errors}
        classes = [{"name": base, "parent": "Exception", "retryable": False, "code": "_".join(camel_words(base)), "attrs": {},
                    "http": 500 if http else None}]
        classes += [{"name": e["name"], "parent": e["parent"], "retryable": e["retryable"], "code": e["code"],
                     "attrs": e["attrs"], "http": guess_http(e, by_name, base) if http else None} for e in errors]
        print(json.dumps({"package": package, "base": base, "output": args.output, "classes": classes,
                          "source": code}, indent=2))
    elif args.output:
        print(f"wrote {args.output}: {base} + {len(errors)} subclasses"
              + (", HTTP mapping and FastAPI handler" if http else ""))
    else:
        sys.stdout.write(code)


if __name__ == "__main__":
    main()
