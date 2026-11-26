#!/usr/bin/env python3
"""Lint .proto files against protobuf correctness rules and the Google API / Buf style guides.

Checks:
  PL001 error  duplicate field number, field number in the reserved 19000-19999 range, or reuse of a reserved number/name
  PL002 error  enum whose first value isn't 0, or zero value not named <ENUM>_UNSPECIFIED
  PL003 error  'required' fields (proto2): can never be removed safely
  PL004 warn   package missing or not versioned (acme.orders.v1)
  PL005 warn   naming: messages/enums/services/RPCs PascalCase, fields lower_snake_case, enum values UPPER_SNAKE_CASE
               prefixed with the enum name
  PL006 warn   RPC request/response not dedicated (<Rpc>Request / <Rpc>Response); google.protobuf.Empty or shared messages
  PL007 warn   service name not ending in Service
  PL008 warn   List RPC without page_size/page_token in the request or next_page_token in the response
  PL009 warn   syntax missing or proto2
  PL010 info   language package options missing (go_package, java_package)

Usage:
    python proto_lint.py orders.proto [more.proto ...] [--json]

Exit codes: 0 no errors or warnings, 1 errors or warnings, 2 unreadable input.
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _proto import parse  # noqa: E402

PASCAL = re.compile(r"^[A-Z][A-Za-z0-9]*$")
SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")
UPPER = re.compile(r"^[A-Z][A-Z0-9_]*$")


def upper_snake(name):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).upper()


def lint(path, p):
    found = []
    add = lambda code, sev, where, msg: found.append({"code": code, "severity": sev, "where": f"{os.path.basename(path)}:{where}", "message": msg})
    if p["syntax"] in (None, "proto2"):
        add("PL009", "warn", "syntax", f"syntax is {p['syntax'] or 'missing'}; use proto3 (or editions)")
    if not p["package"]:
        add("PL004", "warn", "package", "no package")
    elif not re.search(r"\.v\d+((alpha|beta)\d*)?$", p["package"]):
        add("PL004", "warn", "package", f"package '{p['package']}' is not versioned (e.g. {p['package']}.v1)")
    missing = [o for o in ("go_package", "java_package") if o not in p["options"]]
    if missing:
        add("PL010", "info", "options", f"missing {', '.join(missing)}")
    used_as_io = {}
    for name, m in p["messages"].items():
        short = name.split(".")[-1]
        if not PASCAL.match(short):
            add("PL005", "warn", f"{m['line']}", f"message {name} should be PascalCase")
        seen = {}
        for f in m["fields"]:
            where = f"{f['line']}"
            if f["number"] in seen:
                add("PL001", "error", where, f"{name}.{f['name']} reuses field number {f['number']} (also {seen[f['number']]})")
            seen[f["number"]] = f["name"]
            if 19000 <= f["number"] <= 19999:
                add("PL001", "error", where, f"{name}.{f['name']} uses number {f['number']} in the reserved 19000-19999 range")
            if f["number"] in m["reserved_numbers"] or f["name"] in m["reserved_names"]:
                add("PL001", "error", where, f"{name}.{f['name']} reuses a reserved number or name")
            if f["label"] == "required":
                add("PL003", "error", where, f"{name}.{f['name']} is required; required fields can never be removed")
            if not SNAKE.match(f["name"]):
                add("PL005", "warn", where, f"field {name}.{f['name']} should be lower_snake_case")
    for name, e in p["enums"].items():
        short = name.split(".")[-1]
        prefix = upper_snake(short)
        if not PASCAL.match(short):
            add("PL005", "warn", f"{e['line']}", f"enum {name} should be PascalCase")
        if not e["values"] or e["values"][0][1] != 0:
            add("PL002", "error", f"{e['line']}", f"enum {name} must start with a zero value")
        elif e["values"][0][0] != f"{prefix}_UNSPECIFIED":
            add("PL002", "error", f"{e['line']}", f"enum {name} zero value should be {prefix}_UNSPECIFIED, not {e['values'][0][0]}")
        for v, _ in e["values"]:
            if not UPPER.match(v) or not v.startswith(prefix + "_"):
                add("PL005", "warn", f"{e['line']}", f"enum value {v} should be UPPER_SNAKE_CASE prefixed {prefix}_")
    for sname, s in p["services"].items():
        if not sname.endswith("Service"):
            add("PL007", "warn", f"{s['line']}", f"service {sname} should end in 'Service'")
        for rname, req, resp, _, _ in s["rpcs"]:
            if not PASCAL.match(rname):
                add("PL005", "warn", f"{s['line']}", f"rpc {rname} should be PascalCase")
            pascal = rname[:1].upper() + rname[1:]
            for kind, msg in (("Request", req), ("Response", resp)):
                short = msg.split(".")[-1]
                if msg.startswith("google.protobuf."):
                    add("PL006", "warn", f"{s['line']}", f"{rname} uses {msg}; use a dedicated {pascal}{kind} so fields can be added later")
                elif short != f"{pascal}{kind}":
                    add("PL006", "warn", f"{s['line']}", f"{rname} {kind.lower()} is {short}; use {pascal}{kind}")
                used_as_io.setdefault(msg, []).append(rname)
            if rname.startswith("List"):
                rq = p["messages"].get(req) or p["messages"].get(req.split(".")[-1], {"fields": []})
                rs = p["messages"].get(resp) or p["messages"].get(resp.split(".")[-1], {"fields": []})
                rqn, rsn = {f["name"] for f in rq["fields"]}, {f["name"] for f in rs["fields"]}
                if not {"page_size", "page_token"} <= rqn or "next_page_token" not in rsn:
                    add("PL008", "warn", f"{s['line']}", f"{rname} needs page_size + page_token in the request and next_page_token in the response")
    for msg, rpcs in used_as_io.items():
        if len(rpcs) > 1 and not msg.startswith("google.protobuf."):
            add("PL006", "warn", "service", f"message {msg} shared by RPCs {', '.join(rpcs)}")
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="+")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    found = []
    for path in a.files:
        try:
            text = open(path, encoding="utf-8").read()
        except OSError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        found += lint(path, parse(text))
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
