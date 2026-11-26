#!/usr/bin/env python3
"""Lint an OpenAPI 3.0/3.1 spec for correctness, client usability and behaviour at scale.

Reads JSON, or YAML when PyYAML is installed. Local $refs (#/components/...) are resolved.

Checks:
  OA001 error  missing openapi version, info.title/version or paths
  OA002 error  operation without operationId
  OA003 error  duplicate operationId
  OA004 error  unresolved local $ref
  OA005 error  path template parameter not declared (or declared path parameter not in the template)
  OA006 warn   no error responses (4xx/5xx/default) documented
  OA007 warn   success response without a schema (except 204/304)
  OA008 warn   list GET returning an array with no pagination parameter (cursor/limit) or maxItems: unbounded
  OA009 warn   request body string without maxLength / array without maxItems (unbounded input)
  OA010 warn   no security requirement (global or per operation) and not explicitly public (security: [])
  OA011 warn   POST without an Idempotency-Key header parameter
  OA012 info   no 429 response documented (rate limiting)
  OA013 info   operation without summary or description
  OA014 info   no examples in request or response

Usage:
    python openapi_lint.py openapi.yaml
    python openapi_lint.py openapi.json --json

Exit codes: 0 no errors or warnings, 1 errors or warnings, 2 unreadable file.
"""

import argparse
import json
import re
import sys

METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")
PAGE_PARAMS = re.compile(r"^(cursor|page_?token|page|limit|page_?size|per_?page|offset|after|before|starting_after|max_?results)$", re.I)


def load(path):
    text = open(path, encoding="utf-8").read()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml
        except ImportError:
            raise ValueError("not JSON, and PyYAML is not installed to read YAML (pip install pyyaml)")
        return yaml.safe_load(text)


class Spec:
    def __init__(self, doc):
        self.doc = doc
        self.bad_refs = set()

    def resolve(self, node, depth=0):
        while isinstance(node, dict) and "$ref" in node and depth < 20:
            ref = node["$ref"]
            if not ref.startswith("#/"):
                return node
            cur = self.doc
            for part in ref[2:].split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                cur = cur.get(part) if isinstance(cur, dict) else None
                if cur is None:
                    self.bad_refs.add(ref)
                    return {}
            node, depth = cur, depth + 1
        return node

    def walk_schema(self, schema, fn, path="", seen=None):
        seen = seen if seen is not None else set()
        if isinstance(schema, dict) and "$ref" in schema:
            if schema["$ref"] in seen:
                return
            seen = seen | {schema["$ref"]}
        s = self.resolve(schema)
        if not isinstance(s, dict):
            return
        fn(s, path)
        for k, v in (s.get("properties") or {}).items():
            self.walk_schema(v, fn, f"{path}.{k}" if path else k, seen)
        if "items" in s:
            self.walk_schema(s["items"], fn, f"{path}[]", seen)
        for key in ("allOf", "oneOf", "anyOf"):
            for sub in s.get(key) or []:
                self.walk_schema(sub, fn, path, seen)


def schema_type(s):
    t = s.get("type")
    return t if isinstance(t, str) else next((x for x in (t or []) if x != "null"), None)


def lint(doc):
    found = []
    add = lambda code, sev, where, msg: found.append({"code": code, "severity": sev, "where": where, "message": msg})
    sp = Spec(doc)
    if not str(doc.get("openapi", "")).startswith("3"):
        add("OA001", "error", "root", "missing or unsupported 'openapi' version (need 3.x)")
    info = doc.get("info") or {}
    if not info.get("title") or not info.get("version"):
        add("OA001", "error", "info", "info.title and info.version are required")
    paths = doc.get("paths") or {}
    if not paths:
        add("OA001", "error", "paths", "no paths defined")
    global_sec = doc.get("security")
    op_ids = {}
    for route, item in paths.items():
        item = sp.resolve(item) or {}
        template = set(re.findall(r"\{([^}]+)\}", route))
        shared = [sp.resolve(p) for p in item.get("parameters", [])]
        for method in METHODS:
            op = item.get(method)
            if not isinstance(op, dict):
                continue
            where = f"{method.upper()} {route}"
            params = shared + [sp.resolve(p) for p in op.get("parameters", [])]
            names = {(p.get("in"), p.get("name")) for p in params if isinstance(p, dict)}
            oid = op.get("operationId")
            if not oid:
                add("OA002", "error", where, "no operationId (SDKs and docs need stable names)")
            elif oid in op_ids:
                add("OA003", "error", where, f"operationId '{oid}' already used by {op_ids[oid]}")
            else:
                op_ids[oid] = where
            declared = {n for i, n in names if i == "path"}
            if template - declared:
                add("OA005", "error", where, f"path parameter(s) not declared: {', '.join(sorted(template - declared))}")
            if declared - template:
                add("OA005", "error", where, f"declared path parameter(s) not in the template: {', '.join(sorted(declared - template))}")
            responses = op.get("responses") or {}
            codes = [str(c) for c in responses]
            if not any(c.startswith(("4", "5")) or c == "default" for c in codes):
                add("OA006", "warn", where, "no error responses documented (4xx/5xx/default)")
            has_example = False
            for code, resp in responses.items():
                resp = sp.resolve(resp) or {}
                content = resp.get("content") or {}
                if str(code).startswith("2") and str(code) not in ("204", "202") and not content:
                    add("OA007", "warn", where, f"{code} response has no content schema")
                for media in content.values():
                    has_example |= bool(media.get("example") or media.get("examples"))
                    schema = sp.resolve(media.get("schema") or {})
                    if method == "get" and str(code).startswith("2"):
                        arrays = []
                        sp.walk_schema(media.get("schema") or {}, lambda s, p: arrays.append((p, s)) if schema_type(s) == "array" and p.count("[]") == 0 and p.count(".") <= 1 else None)
                        paged = any(PAGE_PARAMS.match(n or "") for i, n in names if i == "query")
                        for p, s in arrays:
                            if not paged and "maxItems" not in s:
                                add("OA008", "warn", where, f"unbounded list '{p or 'body'}': add cursor pagination with a max page size")
                                break
            body = sp.resolve(op.get("requestBody") or {})
            for media in (body.get("content") or {}).values():
                has_example |= bool(media.get("example") or media.get("examples"))
                loose = []
                sp.walk_schema(media.get("schema") or {}, lambda s, p: loose.append(p or "body") if (
                    (schema_type(s) == "string" and "maxLength" not in s and "enum" not in s and "format" not in s)
                    or (schema_type(s) == "array" and "maxItems" not in s)) else None)
                if loose:
                    add("OA009", "warn", where, f"unbounded input: {', '.join(loose[:5])}{' ...' if len(loose) > 5 else ''} (add maxLength/maxItems)")
            if op.get("security") is None and not global_sec:
                add("OA010", "warn", where, "no security requirement; add one or declare security: [] for public endpoints")
            if method == "post" and ("header", "Idempotency-Key") not in {(i, (n or "").title()) for i, n in names}:
                add("OA011", "warn", where, "no Idempotency-Key header: retries can create duplicates")
            if "429" not in codes:
                add("OA012", "info", where, "no 429 response documented")
            if not op.get("summary") and not op.get("description"):
                add("OA013", "info", where, "no summary or description")
            if not has_example:
                add("OA014", "info", where, "no examples")
    for ref in sorted(sp.bad_refs):
        add("OA004", "error", ref, "unresolved $ref")
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("spec", help="OpenAPI file (JSON, or YAML with PyYAML)")
    ap.add_argument("--json", action="store_true", help="print findings as JSON")
    a = ap.parse_args()
    try:
        doc = load(a.spec)
        if not isinstance(doc, dict):
            raise ValueError("top level is not an object")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    found = lint(doc)
    order = {"error": 0, "warn": 1, "info": 2}
    found.sort(key=lambda f: (order[f["severity"]], f["code"], f["where"]))
    if a.json:
        print(json.dumps(found, indent=2))
    else:
        for f in found:
            print(f"{f['code']} [{f['severity']}] {f['where']}: {f['message']}")
        c = {s: sum(f["severity"] == s for f in found) for s in order}
        print(f"\n{c['error']} error(s), {c['warn']} warning(s), {c['info']} info")
    return 1 if any(f["severity"] in ("error", "warn") for f in found) else 0


if __name__ == "__main__":
    sys.exit(main())
