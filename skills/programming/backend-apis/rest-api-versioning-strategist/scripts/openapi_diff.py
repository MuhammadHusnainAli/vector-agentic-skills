#!/usr/bin/env python3
"""Compare two OpenAPI 3.x specs and classify each change as breaking or non-breaking for existing clients.

Breaking (error):
  BC001 operation removed                     BC006 required parameter added, or optional parameter made required
  BC002 documented success status removed     BC007 request enum value removed (previously valid input now rejected)
  BC003 response property removed             BC008 request constraint tightened (maxLength, maximum, maxItems down; minimum up)
  BC004 property or parameter type changed    BC009 operationId changed (generated SDK method renamed)
  BC005 new required request-body property    BC010 security scope added to an operation
Potentially breaking (warn):
  PB001 response enum value added (strict clients may fail)   PB002 response property became optional/nullable
Non-breaking (info):
  NB001 operation added   NB002 optional request property or parameter added   NB003 response property added

Usage:
    python openapi_diff.py old.yaml new.yaml
    python openapi_diff.py old.json new.json --json

Exit codes: 0 no breaking changes, 1 breaking changes, 2 unreadable files.
"""

import argparse
import json
import sys

METHODS = ("get", "put", "post", "delete", "patch", "head", "options")


def load(path):
    text = open(path, encoding="utf-8").read()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml
        except ImportError:
            raise ValueError(f"{path}: not JSON, and PyYAML is not installed to read YAML")
        return yaml.safe_load(text)


def resolver(doc):
    def resolve(node, depth=0):
        while isinstance(node, dict) and "$ref" in node and depth < 30:
            cur = doc
            for part in node["$ref"].lstrip("#/").split("/"):
                cur = cur.get(part, {}) if isinstance(cur, dict) else {}
            node, depth = cur, depth + 1
        return node if isinstance(node, dict) else {}
    return resolve


def stype(s):
    t = s.get("type")
    if isinstance(t, list):
        return "|".join(sorted(x for x in t if x != "null"))
    return t or ("object" if "properties" in s else None)


def nullable(s):
    t = s.get("type")
    return s.get("nullable") is True or (isinstance(t, list) and "null" in t)


def ops(doc):
    out = {}
    res = resolver(doc)
    for route, item in (doc.get("paths") or {}).items():
        item = res(item)
        shared = [res(p) for p in item.get("parameters", [])]
        for m in METHODS:
            if isinstance(item.get(m), dict):
                op = item[m]
                out[f"{m.upper()} {route}"] = (op, shared + [res(p) for p in op.get("parameters", [])])
    return out


def compare_schema(old, new, ro, rn, where, direction, add, seen=frozenset()):
    """direction: 'request' or 'response'."""
    key = (id(old), id(new))
    if key in seen:
        return
    seen = seen | {key}
    old, new = ro(old), rn(new)
    to, tn = stype(old), stype(new)
    if to and tn and to != tn:
        add("BC004", "error", f"{where}: type changed {to} -> {tn}")
        return
    if direction == "request":
        lost = set(old.get("enum") or []) - set(new.get("enum") or old.get("enum") or [])
        if old.get("enum") and new.get("enum") and lost:
            add("BC007", "error", f"{where}: enum value(s) removed {sorted(map(str, lost))}")
        for k, tighter in (("maxLength", lambda a, b: b < a), ("maximum", lambda a, b: b < a), ("maxItems", lambda a, b: b < a),
                           ("minimum", lambda a, b: b > a), ("minLength", lambda a, b: b > a)):
            if k in new and (k not in old or tighter(old[k], new[k])):
                add("BC008", "error", f"{where}: {k} tightened {old.get(k, 'unset')} -> {new[k]}")
    else:
        added = set(new.get("enum") or []) - set(old.get("enum") or [])
        if old.get("enum") and added:
            add("PB001", "warn", f"{where}: enum value(s) added {sorted(map(str, added))}")
    op_, np_ = old.get("properties") or {}, new.get("properties") or {}
    oreq, nreq = set(old.get("required") or []), set(new.get("required") or [])
    for name in op_:
        path = f"{where}.{name}"
        if name not in np_:
            if direction == "response":
                add("BC003", "error", f"{path}: response property removed")
            continue
        if direction == "response" and name in oreq and (name not in nreq or (not nullable(ro(op_[name])) and nullable(rn(np_[name])))):
            add("PB002", "warn", f"{path}: response property became optional or nullable")
        compare_schema(op_[name], np_[name], ro, rn, path, direction, add, seen)
    for name in np_:
        if name not in op_:
            if direction == "request" and name in nreq:
                add("BC005", "error", f"{where}.{name}: new required request property")
            elif direction == "request":
                add("NB002", "info", f"{where}.{name}: optional request property added")
            else:
                add("NB003", "info", f"{where}.{name}: response property added")
    if direction == "request":
        for name in (nreq - oreq) & set(op_):
            add("BC005", "error", f"{where}.{name}: request property became required")
    if "items" in old and "items" in new:
        compare_schema(old["items"], new["items"], ro, rn, f"{where}[]", direction, add, seen)


def diff(old_doc, new_doc):
    found = []
    add = lambda code, sev, msg: found.append({"code": code, "severity": sev, "message": msg})
    ro, rn = resolver(old_doc), resolver(new_doc)
    old_ops, new_ops = ops(old_doc), ops(new_doc)
    for key, (op, params) in old_ops.items():
        if key not in new_ops:
            add("BC001", "error", f"{key}: operation removed")
            continue
        nop, nparams = new_ops[key]
        if op.get("operationId") and nop.get("operationId") and op["operationId"] != nop["operationId"]:
            add("BC009", "error", f"{key}: operationId {op['operationId']} -> {nop['operationId']}")
        po = {(p.get("in"), p.get("name")): p for p in params}
        pn = {(p.get("in"), p.get("name")): p for p in nparams}
        for k, p in pn.items():
            where = f"{key} param {k[1]} ({k[0]})"
            if k not in po:
                add("BC006" if p.get("required") else "NB002", "error" if p.get("required") else "info",
                    f"{where}: {'required parameter added' if p.get('required') else 'optional parameter added'}")
            elif p.get("required") and not po[k].get("required"):
                add("BC006", "error", f"{where}: parameter became required")
            else:
                compare_schema(po[k].get("schema") or {}, p.get("schema") or {}, ro, rn, where, "request", add)
        sco = {s for req in (op.get("security") or old_doc.get("security") or []) for v in req.values() for s in v}
        scn = {s for req in (nop.get("security") or new_doc.get("security") or []) for v in req.values() for s in v}
        if scn - sco:
            add("BC010", "error", f"{key}: new scope(s) required {sorted(scn - sco)}")
        ob = (ro(op.get("requestBody") or {}).get("content") or {})
        nb = (rn(nop.get("requestBody") or {}).get("content") or {})
        for media in ob:
            if media in nb:
                compare_schema(ob[media].get("schema") or {}, nb[media].get("schema") or {}, ro, rn, f"{key} body", "request", add)
        oresp, nresp = op.get("responses") or {}, nop.get("responses") or {}
        for code, r in oresp.items():
            if str(code).startswith("2") and code not in nresp:
                add("BC002", "error", f"{key}: {code} response removed")
                continue
            if code not in nresp:
                continue
            oc, nc = ro(r).get("content") or {}, rn(nresp[code]).get("content") or {}
            for media in oc:
                if media in nc:
                    compare_schema(oc[media].get("schema") or {}, nc[media].get("schema") or {}, ro, rn, f"{key} {code}", "response", add)
    for key in new_ops:
        if key not in old_ops:
            add("NB001", "info", f"{key}: operation added")
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        old_doc, new_doc = load(a.old), load(a.new)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    found = diff(old_doc, new_doc)
    order = {"error": 0, "warn": 1, "info": 2}
    found.sort(key=lambda f: (order[f["severity"]], f["code"], f["message"]))
    if a.json:
        print(json.dumps(found, indent=2))
    else:
        for f in found:
            print(f"{f['code']} [{f['severity']}] {f['message']}")
        b = sum(f["severity"] == "error" for f in found)
        print(f"\n{b} breaking, {sum(f['severity'] == 'warn' for f in found)} potentially breaking, "
              f"{sum(f['severity'] == 'info' for f in found)} non-breaking change(s)")
    return 1 if any(f["severity"] == "error" for f in found) else 0


if __name__ == "__main__":
    sys.exit(main())
