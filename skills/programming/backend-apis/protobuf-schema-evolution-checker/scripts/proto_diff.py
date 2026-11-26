#!/usr/bin/env python3
"""Compare two versions of a .proto file and classify every change for wire, JSON and generated-code compatibility.

Breaking (error):
  PE001 field removed without reserving its number and name (the number can be reused by accident)
  PE002 field number reused for a different field, or a field's number changed
  PE003 field type changed incompatibly (e.g. string -> int64, message -> scalar)
  PE004 repeated <-> singular, or map changed
  PE005 field moved into or out of a oneof
  PE006 message or enum removed
  PE007 enum value removed without reserving, or its number changed
  PE008 RPC removed, its request/response type changed, or streaming mode changed
  PE009 service removed or package changed
Risky (warn):
  PW001 field renamed (wire-compatible, breaks JSON and generated code)
  PW002 type changed within a wire-compatible group (int32 <-> int64 etc.): truncation or sign issues
  PW003 optional (presence) added or removed
Safe (info):
  PI001 field, message, enum value, RPC or service added   PI002 field removed and reserved

Usage:
    python proto_diff.py old.proto new.proto [--json]

Exit codes: 0 no breaking changes, 1 breaking changes, 2 unreadable files.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _proto import parse  # noqa: E402

COMPAT = [{"int32", "uint32", "int64", "uint64", "bool"}, {"sint32", "sint64"}, {"fixed32", "sfixed32"},
          {"fixed64", "sfixed64"}, {"string", "bytes"}]


def type_change(a, b):
    if a == b:
        return None
    if any(a in g and b in g for g in COMPAT):
        return "warn"
    return "error"


def diff(old, new):
    found = []
    add = lambda code, sev, msg: found.append({"code": code, "severity": sev, "message": msg})
    if old["package"] != new["package"]:
        add("PE009", "error", f"package changed {old['package']} -> {new['package']}")
    for mname, om in old["messages"].items():
        nm = new["messages"].get(mname)
        if nm is None:
            add("PE006", "error", f"message {mname} removed")
            continue
        o_by_num = {f["number"]: f for f in om["fields"]}
        n_by_num = {f["number"]: f for f in nm["fields"]}
        n_by_name = {f["name"]: f for f in nm["fields"]}
        for num, of in o_by_num.items():
            nf = n_by_num.get(num)
            where = f"{mname}.{of['name']} ({num})"
            if nf is None:
                moved = n_by_name.get(of["name"])
                if moved:
                    add("PE002", "error", f"{where}: number changed to {moved['number']}")
                elif num in nm["reserved_numbers"] and of["name"] in nm["reserved_names"]:
                    add("PI002", "info", f"{where}: removed and reserved")
                elif num in nm["reserved_numbers"]:
                    add("PW001", "warn", f"{where}: removed, number reserved but name not (JSON/text format may reuse it)")
                else:
                    add("PE001", "error", f"{where}: removed without 'reserved {num}; reserved \"{of['name']}\";'")
                continue
            if nf["name"] != of["name"]:
                if of["name"] in n_by_name:
                    add("PE002", "error", f"{where}: number {num} now used by '{nf['name']}' while '{of['name']}' moved")
                else:
                    add("PW001", "warn", f"{where}: renamed to {nf['name']} (wire-compatible; breaks JSON and generated code)")
            map_change = of["type"].startswith("map") != nf["type"].startswith("map")
            kind = None if map_change else type_change(of["type"], nf["type"])   # PE004 reports map changes
            if kind == "error":
                add("PE003", "error", f"{where}: type {of['type']} -> {nf['type']}")
            elif kind == "warn":
                add("PW002", "warn", f"{where}: type {of['type']} -> {nf['type']} (wire-compatible group; check truncation and sign)")
            if (of["label"] == "repeated") != (nf["label"] == "repeated") or of["type"].startswith("map") != nf["type"].startswith("map"):
                add("PE004", "error", f"{where}: cardinality changed ({of['label'] or 'singular'} -> {nf['label'] or 'singular'})")
            elif (of["label"] == "optional") != (nf["label"] == "optional"):
                add("PW003", "warn", f"{where}: presence changed ({of['label'] or 'implicit'} -> {nf['label'] or 'implicit'})")
            if of["oneof"] != nf["oneof"]:
                add("PE005", "error", f"{where}: oneof membership changed ({of['oneof'] or 'none'} -> {nf['oneof'] or 'none'})")
        for num, nf in n_by_num.items():
            if num not in o_by_num:
                if num in om["reserved_numbers"]:
                    add("PE002", "error", f"{mname}.{nf['name']} ({num}): reuses a number reserved in the old version")
                elif nf["name"] not in {f["name"] for f in om["fields"]}:
                    add("PI001", "info", f"{mname}.{nf['name']} ({num}): field added")
    for mname in new["messages"]:
        if mname not in old["messages"]:
            add("PI001", "info", f"message {mname} added")
    for ename, oe in old["enums"].items():
        ne = new["enums"].get(ename)
        if ne is None:
            add("PE006", "error", f"enum {ename} removed")
            continue
        nvals = dict(ne["values"])
        nnums = {n: v for v, n in ne["values"]}
        for v, n in oe["values"]:
            if v in nvals and nvals[v] != n:
                add("PE007", "error", f"{ename}.{v}: number {n} -> {nvals[v]}")
            elif v not in nvals and n not in nnums:
                add("PE007", "error", f"{ename}.{v} ({n}): removed")
            elif v not in nvals:
                add("PW001", "warn", f"{ename}.{v} ({n}): renamed to {nnums[n]} (breaks JSON and generated code)")
        for v, n in ne["values"]:
            if v not in dict(oe["values"]) and n not in {num for _, num in oe["values"]}:
                add("PI001", "info", f"{ename}.{v} ({n}): value added (clients must handle unknown values)")
    for sname, os_ in old["services"].items():
        ns = new["services"].get(sname)
        if ns is None:
            add("PE009", "error", f"service {sname} removed")
            continue
        nr = {r[0]: r for r in ns["rpcs"]}
        for r in os_["rpcs"]:
            if r[0] not in nr:
                add("PE008", "error", f"{sname}.{r[0]}: RPC removed")
            elif nr[r[0]][1:3] != r[1:3]:
                add("PE008", "error", f"{sname}.{r[0]}: request/response changed {r[1]}->{r[2]} to {nr[r[0]][1]}->{nr[r[0]][2]}")
            elif nr[r[0]][3:] != r[3:]:
                add("PE008", "error", f"{sname}.{r[0]}: streaming mode changed")
        for name in nr:
            if name not in {r[0] for r in os_["rpcs"]}:
                add("PI001", "info", f"{sname}.{name}: RPC added")
    for sname in new["services"]:
        if sname not in old["services"]:
            add("PI001", "info", f"service {sname} added")
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        old, new = parse(open(a.old, encoding="utf-8").read()), parse(open(a.new, encoding="utf-8").read())
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    found = diff(old, new)
    order = {"error": 0, "warn": 1, "info": 2}
    found.sort(key=lambda f: (order[f["severity"]], f["code"], f["message"]))
    if a.json:
        print(json.dumps(found, indent=2))
    else:
        for f in found:
            print(f"{f['code']} [{f['severity']}] {f['message']}")
        c = {s: sum(f["severity"] == s for f in found) for s in order}
        print(f"\n{c['error']} breaking, {c['warn']} risky, {c['info']} safe change(s)")
    return 1 if any(f["severity"] == "error" for f in found) else 0


if __name__ == "__main__":
    sys.exit(main())
