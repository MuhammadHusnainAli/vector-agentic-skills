#!/usr/bin/env python3
"""Lint a GraphQL schema (SDL) for scale, evolvability and naming.

Parses type, interface, input, enum and extend type blocks from .graphql/.graphqls files (comments and descriptions
ignored).

Checks:
  GQ001 warn  list of object types without pagination arguments (first/after, limit/cursor): unbounded at scale
              (Connection, Payload and Error wrapper types and scalar lists are exempt)
  GQ002 warn  list with nullable items ([User] instead of [User!]!)
  GQ003 warn  mutation not taking a single input argument (input: XInput!) or not returning a payload type
  GQ004 warn  identifier field typed String/Int instead of ID
  GQ005 warn  type names not PascalCase, field/argument names not camelCase, enum values not UPPER_SNAKE_CASE
  GQ006 warn  Query field named like an RPC (getUser, fetchOrders, listItems)
  GQ007 warn  @deprecated without a reason
  GQ008 info  foreign-key style field (authorId) with no matching object field (author)
  GQ009 info  type without a description

Usage:
    python graphql_schema_lint.py schema.graphql [more.graphql ...] [--json]

Exit codes: 0 no warnings, 1 warnings, 2 unreadable input or no types found.
"""

import argparse
import json
import re
import sys

BLOCK = re.compile(r'("""[\s\S]*?"""\s*|"[^"\n]*"\s*)?(extend\s+)?(type|interface|input|enum)\s+(\w+)[^{]*\{([^{}]*)\}')
FIELD = re.compile(r'(?:"""[\s\S]*?"""|"[^"\n]*")?\s*(\w+)\s*(\(([^)]*)\))?\s*:\s*([\[\]\w!]+)([^\n]*)')
PAGE_ARGS = {"first", "after", "last", "before", "limit", "cursor", "pagesize", "pagetoken", "offset"}


def strip_comments(text):
    return re.sub(r"#[^\n]*", "", text)


def parse(text):
    types = []
    for m in BLOCK.finditer(strip_comments(text)):
        desc, kind, name, body = m.group(1), m.group(3), m.group(4), m.group(5)
        line = text[: m.start()].count("\n") + 1
        fields = []
        if kind == "enum":
            fields = [(v, None, None, "") for v in re.findall(r"^\s*(\w+)", body, re.M)]
        else:
            for f in FIELD.finditer(body):
                args = {}
                for a in re.finditer(r"(\w+)\s*:\s*([\[\]\w!]+)", f.group(3) or ""):
                    args[a.group(1)] = a.group(2)
                fields.append((f.group(1), args, f.group(4), f.group(5)))
        types.append({"kind": kind, "name": name, "line": line, "desc": bool(desc), "fields": fields})
    return types


def lint(types):
    found = []
    add = lambda code, sev, where, msg: found.append({"code": code, "severity": sev, "where": where, "message": msg})
    names = {t["name"] for t in types}
    objects = {t["name"] for t in types if t["kind"] in ("type", "interface")}
    for t in types:
        tn, kind = t["name"], t["kind"]
        if not re.fullmatch(r"[A-Z][A-Za-z0-9]*", tn):
            add("GQ005", "warn", tn, "type name should be PascalCase")
        if not t["desc"] and tn not in ("Query", "Mutation", "Subscription") and kind != "input":
            add("GQ009", "info", tn, "no description")
        if kind == "enum":
            for v, *_ in t["fields"]:
                if not re.fullmatch(r"[A-Z][A-Z0-9_]*", v):
                    add("GQ005", "warn", f"{tn}.{v}", "enum values should be UPPER_SNAKE_CASE")
            continue
        field_names = {f[0] for f in t["fields"]}
        for fname, args, ftype, rest in t["fields"]:
            where = f"{tn}.{fname}"
            if not re.fullmatch(r"[a-z][A-Za-z0-9]*", fname):
                add("GQ005", "warn", where, "field names should be camelCase")
            for an in args or {}:
                if not re.fullmatch(r"[a-z][A-Za-z0-9]*", an):
                    add("GQ005", "warn", f"{where}({an})", "argument names should be camelCase")
            if "@deprecated" in rest and "reason" not in rest:
                add("GQ007", "warn", where, "@deprecated without a reason")
            if kind == "input":
                continue
            is_list = ftype.startswith("[")
            if is_list and re.search(r"\[\w+\]", ftype):
                add("GQ002", "warn", where, f"list {ftype} has nullable items; use [{re.sub(r'[\[\]!]', '', ftype)}!]!")
            base_t = re.sub(r"[\[\]!]", "", ftype)
            wrapper = re.search(r"(Connection|Payload|Error|Errors)$", tn)
            if is_list and base_t in objects and not wrapper and not ({a.lower() for a in (args or {})} & PAGE_ARGS):
                add("GQ001", "warn", where, f"unbounded list {ftype}; use a Connection with first/after (max page size)")
            base = re.sub(r"[\[\]!]", "", ftype)
            if re.fullmatch(r"(id|\w+Id)", fname) and base in ("String", "Int"):
                add("GQ004", "warn", where, f"identifier typed {base}; use ID")
            if fname.endswith("Id") and fname != "id" and fname[:-2] not in field_names and tn not in ("Query", "Mutation"):
                add("GQ008", "info", where, f"exposes {fname} but no '{fname[:-2]}' object field; consider a relationship")
            if tn == "Query" and re.match(r"(get|fetch|list|retrieve|find)[A-Z]", fname):
                add("GQ006", "warn", where, "RPC-style name; name queries after what they return (user, orders)")
            if tn == "Mutation":
                arg_types = list((args or {}).values())
                if len(arg_types) != 1 or not arg_types[0].rstrip("!").endswith("Input"):
                    add("GQ003", "warn", where, "mutations should take one argument: input: XInput!")
                if not base.endswith("Payload") and base in names | {"String", "Boolean", "Int", "ID"}:
                    add("GQ003", "warn", where, f"returns {base}; return an XPayload type (room for errors and new fields)")
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="+", help="SDL files")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        text = "\n".join(open(f, encoding="utf-8").read() for f in a.files)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    types = parse(text)
    if not types:
        print("error: no type, input, interface or enum definitions found", file=sys.stderr)
        return 2
    found = lint(types)
    found.sort(key=lambda f: (f["severity"] != "warn", f["code"], f["where"]))
    if a.json:
        print(json.dumps(found, indent=2))
    else:
        for f in found:
            print(f"{f['code']} [{f['severity']}] {f['where']}: {f['message']}")
        w = sum(f["severity"] == "warn" for f in found)
        print(f"\n{len(types)} type(s): {w} warning(s), {len(found) - w} info")
    return 1 if any(f["severity"] == "warn" for f in found) else 0


if __name__ == "__main__":
    sys.exit(main())
