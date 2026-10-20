#!/usr/bin/env python3
"""Break a SQL query into its parts, in logical execution order.

Prints the CTEs, source tables, joins (type and condition), filters, grouping,
window functions, ordering and limits, numbered in the order the database
logically evaluates them (FROM -> WHERE -> GROUP BY -> HAVING -> SELECT ->
ORDER BY -> LIMIT). Use it as the skeleton for a plain-language explanation.
No dependencies.

Usage:
    python outline_query.py query.sql
    cat query.sql | python outline_query.py -
    python outline_query.py query.sql --json
"""

import argparse
import json
import re
import sys

CLAUSES = ["SELECT", "FROM", "WHERE", "GROUP BY", "HAVING", "WINDOW", "QUALIFY", "ORDER BY", "LIMIT", "OFFSET", "FETCH"]
CLAUSE_RE = re.compile(r"\b(SELECT|FROM|WHERE|GROUP\s+BY|HAVING|WINDOW|QUALIFY|ORDER\s+BY|LIMIT|OFFSET|FETCH|"
                       r"UNION(?:\s+ALL)?|INTERSECT|EXCEPT|MINUS)\b", re.I)
JOIN_RE = re.compile(r"\b((?:NATURAL\s+)?(?:INNER\s+|CROSS\s+|(?:LEFT|RIGHT|FULL)(?:\s+OUTER)?\s+)?JOIN|"
                     r"CROSS\s+APPLY|OUTER\s+APPLY)\b", re.I)


def mask(sql):
    """Blank string literals and comments, keeping offsets."""
    out, i, n = list(sql), 0, len(sql)
    while i < n:
        if sql.startswith("--", i):
            j = sql.find("\n", i)
            j = n if j < 0 else j
            out[i:j] = " " * (j - i)
            i = j
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out[i:j] = [c if c == "\n" else " " for c in sql[i:j]]
            i = j
        elif sql[i] in "'\"`[":
            close = "]" if sql[i] == "[" else sql[i]
            j = i + 1
            while j < n and sql[j] != close:
                j += 1
            if sql[i] == "'":
                out[i + 1:j] = " " * (j - i - 1)
            i = j + 1
        else:
            i += 1
    return "".join(out)


def depth_map(masked):
    depths, d = [], 0
    for ch in masked:
        if ch == "(":
            d += 1
        depths.append(d)
        if ch == ")":
            d -= 1
    return depths


def top_level(regex, masked, depths, base=0):
    return [m for m in regex.finditer(masked) if depths[m.start()] == base]


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def split_and(text):
    masked = mask(text)
    depths = depth_map(masked)
    parts, last = [], 0
    for m in re.finditer(r"\bAND\b", masked, re.I):
        if depths[m.start()] == 0 and not re.search(r"\bBETWEEN\s+\S+\s*$", masked[last:m.start()], re.I):
            parts.append(text[last:m.start()])
            last = m.end()
    parts.append(text[last:])
    return [norm(p) for p in parts if norm(p)]


def parse_ctes(sql, masked, depths):
    """Return (list of (name, body), rest_offset)."""
    m = re.match(r"\s*WITH\s+(RECURSIVE\s+)?", masked, re.I)
    if not m:
        return [], 0
    ctes, i = [], m.end()
    while True:
        h = re.compile(r"\s*([A-Za-z_][\w]*)\s*(\([^)]*\))?\s*AS\s*(?:NOT\s+)?(?:MATERIALIZED\s*)?\(", re.I).match(masked, i)
        if not h:
            break
        start, d, j = h.end(), 1, h.end()
        while j < len(masked) and d:
            d += {"(": 1, ")": -1}.get(masked[j], 0)
            j += 1
        ctes.append((h.group(1), sql[start:j - 1]))
        c = re.compile(r"\s*,").match(masked, j)
        if not c:
            i = j
            break
        i = c.end()
    return ctes, i


def outline(sql):
    sql = sql.strip().rstrip(";")
    masked = mask(sql)
    depths = depth_map(masked)
    ctes, offset = parse_ctes(sql, masked, depths)
    body, mbody = sql[offset:], masked[offset:]
    dbody = depths[offset:]

    marks = top_level(CLAUSE_RE, mbody, dbody)
    set_ops = [norm(m.group(1)).upper() for m in marks if re.match(r"UNION|INTERSECT|EXCEPT|MINUS", m.group(1), re.I)]
    if set_ops:  # describe only the first branch, note the set operation
        cut = next(m.start() for m in marks if re.match(r"UNION|INTERSECT|EXCEPT|MINUS", m.group(1), re.I))
        body, mbody, dbody = body[:cut], mbody[:cut], dbody[:cut]
        marks = [m for m in marks if m.start() < cut]

    parts = {}
    for k, m in enumerate(marks):
        key = norm(m.group(1)).upper()
        end = marks[k + 1].start() if k + 1 < len(marks) else len(body)
        parts.setdefault(key, body[m.end():end].strip())

    result = {"ctes": [], "sources": [], "joins": [], "filters": [], "group_by": [], "having": [],
              "select": [], "windows": [], "order_by": None, "limit": None, "set_operations": set_ops,
              "subqueries": len(re.findall(r"\(\s*SELECT\b", masked[offset:], re.I))}
    for name, cte_body in ctes:
        src = re.findall(r"\bFROM\s+([\w.]+)", mask(cte_body), re.I)
        result["ctes"].append({"name": name, "reads": sorted(set(src)),
                               "aggregates": bool(re.search(r"\bGROUP\s+BY\b", cte_body, re.I))})

    if "FROM" in parts:
        frm = parts["FROM"]
        mfrm = mask(frm)
        dfrm = depth_map(mfrm)
        joins = top_level(JOIN_RE, mfrm, dfrm)
        first = frm[: joins[0].start()] if joins else frm
        result["sources"] = [norm(s) for s in first.split(",") if norm(s)]
        for k, j in enumerate(joins):
            end = joins[k + 1].start() if k + 1 < len(joins) else len(frm)
            seg = frm[j.end():end]
            on = re.search(r"\b(ON|USING)\b", mask(seg), re.I)
            result["joins"].append({
                "type": norm(j.group(1)).upper(),
                "table": norm(seg[: on.start()] if on else seg),
                "condition": norm(seg[on.end():]) if on else None,
                "keyword": on.group(1).upper() if on else None,
            })
    if "WHERE" in parts:
        result["filters"] = split_and(parts["WHERE"])
    if "GROUP BY" in parts:
        result["group_by"] = [norm(g) for g in parts["GROUP BY"].split(",")]
    if "HAVING" in parts:
        result["having"] = split_and(parts["HAVING"])
    if "SELECT" in parts:
        sel = parts["SELECT"]
        msel, dsel = mask(sel), depth_map(mask(sel))
        cuts = [i for i, ch in enumerate(msel) if ch == "," and dsel[i] == 0]
        items, last = [], 0
        for c in cuts + [len(sel)]:
            items.append(norm(sel[last:c]))
            last = c + 1
        items = [i for i in items if i]
        if items:  # DISTINCT / TOP n are reported separately
            items[0] = re.sub(r"^(DISTINCT\s+)?(TOP\s*\(?\s*\d+\s*\)?\s*(PERCENT\s+)?)?", "", items[0], flags=re.I)
        result["select"] = items
        result["windows"] = [i for i in result["select"] if re.search(r"\bOVER\s*\(|\bOVER\s+\w+", i, re.I)]
    if "ORDER BY" in parts:
        result["order_by"] = norm(parts["ORDER BY"])
    limit = " ".join(norm(parts[k]) and f"{k} {norm(parts[k])}" for k in ("LIMIT", "OFFSET", "FETCH") if k in parts)
    top = re.match(r"\s*(DISTINCT\s+)?TOP\s*\(?\s*(\d+)", parts.get("SELECT", ""), re.I)
    result["limit"] = limit or (f"TOP {top.group(2)}" if top else None)
    result["distinct"] = bool(re.match(r"\s*DISTINCT\b", parts.get("SELECT", ""), re.I))
    return result


def render(o):
    steps = []
    for c in o["ctes"]:
        steps.append(f"CTE {c['name']}: builds an intermediate result from {', '.join(c['reads']) or 'a subquery'}"
                     + (" (aggregated)" if c["aggregates"] else ""))
    if o["sources"]:
        steps.append(f"FROM: start with {', '.join(o['sources'])}")
    for j in o["joins"]:
        steps.append(f"{j['type']}: {j['table']}" + (f" {j['keyword']} {j['condition']}" if j["condition"] else ""))
    if o["filters"]:
        steps.append("WHERE: keep rows where\n" + "\n".join(f"        - {f}" for f in o["filters"]))
    if o["group_by"]:
        steps.append(f"GROUP BY: one row per {', '.join(o['group_by'])}")
    if o["having"]:
        steps.append("HAVING: keep groups where\n" + "\n".join(f"        - {h}" for h in o["having"]))
    if o["windows"]:
        steps.append(f"WINDOW FUNCTIONS: {len(o['windows'])} computed over the rows left after grouping/HAVING")
    if o["select"]:
        steps.append(f"SELECT{' DISTINCT' if o['distinct'] else ''}: return {len(o['select'])} column(s)\n"
                     + "\n".join(f"        - {s}" for s in o["select"]))
    if o["order_by"]:
        steps.append(f"ORDER BY: {o['order_by']}")
    if o["limit"]:
        steps.append(f"LIMIT: {o['limit']}")
    lines = ["Logical execution order:"] + [f"{i:>2}. {s}" for i, s in enumerate(steps, 1)]
    if o["set_operations"]:
        lines.append(f"\nNote: combined with {', '.join(o['set_operations'])}; only the first branch is outlined.")
    if o["subqueries"]:
        lines.append(f"Note: contains {o['subqueries']} subquery(ies); outline them separately if they matter.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="SQL file, or - for stdin")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()
    sql = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
    if not re.search(r"\bSELECT\b", sql, re.I):
        print("No SELECT statement found.", file=sys.stderr)
        sys.exit(1)
    o = outline(sql)
    print(json.dumps(o, indent=2) if args.json else render(o))


if __name__ == "__main__":
    main()
