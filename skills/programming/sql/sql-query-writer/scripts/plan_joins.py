#!/usr/bin/env python3
"""Plan JOINs from a schema and print a ready-to-edit SELECT skeleton.

Reads CREATE TABLE statements (any common dialect), builds the foreign-key
graph, finds the shortest join path between the tables you name, and prints a
query with aliases and ON clauses filled in. No dependencies.

Usage:
    python plan_joins.py schema.sql --list
    python plan_joins.py schema.sql --tables customers order_items
    python plan_joins.py schema.sql --tables orders products --columns customers.email,products.name
    python plan_joins.py schema.sql --tables orders customers --json

Tables that sit between the ones you name (e.g. orders between customers and
order_items) are added automatically. Exit code 1 if no path exists.
"""

import argparse
import json
import re
import sys
from collections import deque

IDENT = r'[`"\[]?([A-Za-z_][\w$]*)[`"\]]?'
QUALIFIED = rf"(?:{IDENT}\s*\.\s*)?{IDENT}"


def strip_comments(sql):
    sql = re.sub(r"--[^\n]*", "", sql)
    return re.sub(r"/\*.*?\*/", "", sql, flags=re.S)


def split_top_level(body):
    parts, depth, cur = [], 0, []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur).strip())
    return parts


def unquote(name):
    return name.strip('`"[] ').lower()


def parse_schema(sql):
    """Return {table: {"columns": [...], "pk": [...], "fks": [(cols, ref_table, ref_cols)]}}."""
    sql = strip_comments(sql)
    tables = {}
    for m in re.finditer(rf"CREATE\s+(?:OR\s+REPLACE\s+)?(?:TEMP(?:ORARY)?\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?{QUALIFIED}\s*\(",
                         sql, re.I):
        name = unquote(m.group(2))
        depth, i = 1, m.end()
        while i < len(sql) and depth:
            depth += {"(": 1, ")": -1}.get(sql[i], 0)
            i += 1
        body = sql[m.end():i - 1]
        info = {"columns": [], "pk": [], "fks": []}
        for part in split_top_level(body):
            head = part.split(None, 1)[0].upper() if part.split() else ""
            if head in ("CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "INDEX", "KEY"):
                pk = re.search(r"PRIMARY\s+KEY\s*\(([^)]*)\)", part, re.I)
                if pk:
                    info["pk"] = [unquote(c) for c in pk.group(1).split(",")]
                fk = re.search(rf"FOREIGN\s+KEY\s*\(([^)]*)\)\s*REFERENCES\s+{QUALIFIED}\s*\(([^)]*)\)", part, re.I)
                if fk:
                    info["fks"].append(([unquote(c) for c in fk.group(1).split(",")], unquote(fk.group(3)),
                                        [unquote(c) for c in fk.group(4).split(",")]))
                continue
            col = re.match(IDENT, part)
            if not col:
                continue
            cname = unquote(col.group(1))
            info["columns"].append(cname)
            if re.search(r"PRIMARY\s+KEY", part, re.I):
                info["pk"] = [cname]
            ref = re.search(rf"REFERENCES\s+{QUALIFIED}\s*(?:\(([^)]*)\))?", part, re.I)
            if ref:
                ref_cols = [unquote(c) for c in ref.group(3).split(",")] if ref.group(3) else []
                info["fks"].append(([cname], unquote(ref.group(2)), ref_cols))
        tables[name] = info
    # Fill implicit FK targets (REFERENCES t without column list) with the target's PK.
    for info in tables.values():
        info["fks"] = [(c, t, rc or tables.get(t, {}).get("pk", ["id"])) for c, t, rc in info["fks"]]
    return tables


def build_graph(tables):
    """Undirected adjacency: table -> [(neighbour, [(left_col, right_col), ...])]."""
    graph = {t: [] for t in tables}
    for t, info in tables.items():
        for cols, ref, ref_cols in info["fks"]:
            if ref not in graph:
                continue
            pairs = list(zip(cols, ref_cols))
            graph[t].append((ref, pairs))
            graph[ref].append((t, [(b, a) for a, b in pairs]))
    return graph


def shortest_path(graph, start, goal):
    prev = {start: None}
    q = deque([start])
    while q:
        node = q.popleft()
        if node == goal:
            break
        for nxt, pairs in graph[node]:
            if nxt not in prev:
                prev[nxt] = (node, pairs)
                q.append(nxt)
    if goal not in prev:
        return None
    path, node = [], goal
    while prev[node]:
        parent, pairs = prev[node]
        path.append((parent, node, pairs))
        node = parent
    return list(reversed(path))


def make_alias(table, used):
    base = "".join(w[0] for w in table.split("_")) or table[0]
    alias, n = base, 2
    while alias in used:
        alias, n = f"{base}{n}", n + 1
    used.add(alias)
    return alias


def plan(tables, wanted):
    graph = build_graph(tables)
    root = wanted[0]
    edges, joined = [], {root}
    for target in wanted[1:]:
        if target in joined:
            continue
        best = None
        for src in joined:
            p = shortest_path(graph, src, target)
            if p is not None and (best is None or len(p) < len(best)):
                best = p
        if best is None:
            raise ValueError(f"no foreign-key path from {sorted(joined)} to {target!r}")
        for parent, child, pairs in best:
            if child not in joined:
                edges.append((parent, child, pairs))
                joined.add(child)
    return root, edges


def render(root, edges, tables, columns):
    used, alias = set(), {}
    for t in [root] + [c for _, c, _ in edges]:
        alias[t] = make_alias(t, used)
    if columns:
        select = []
        for c in columns:
            t, _, col = c.partition(".")
            select.append(f"{alias.get(t.lower(), t)}.{col}" if col else c)
    else:
        select = [f"{alias[root]}.{c}" for c in tables[root]["columns"][:3]] or [f"{alias[root]}.*"]
    lines = ["SELECT", "    " + ",\n    ".join(select), f"FROM {root} AS {alias[root]}"]
    for parent, child, pairs in edges:
        on = " AND ".join(f"{alias[child]}.{b} = {alias[parent]}.{a}" for a, b in pairs)
        lines.append(f"JOIN {child} AS {alias[child]}\n    ON {on}")
    lines += ["WHERE 1 = 1  -- add filters", "ORDER BY 1;"]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("schema", help="file with CREATE TABLE statements, or - for stdin")
    ap.add_argument("--tables", nargs="+", help="tables the query needs, first one drives FROM")
    ap.add_argument("--columns", help="comma-separated table.column list for SELECT")
    ap.add_argument("--list", action="store_true", help="print the parsed schema and relationships")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    text = sys.stdin.read() if args.schema == "-" else open(args.schema, encoding="utf-8").read()
    tables = parse_schema(text)
    if not tables:
        print("No CREATE TABLE statements found.", file=sys.stderr)
        sys.exit(1)

    if args.list or not args.tables:
        if args.json:
            print(json.dumps(tables, indent=2))
            return
        for t, info in tables.items():
            pk = f" (pk: {', '.join(info['pk'])})" if info["pk"] else ""
            print(f"{t}{pk}: {', '.join(info['columns'])}")
            for cols, ref, ref_cols in info["fks"]:
                print(f"    {', '.join(cols)} -> {ref}.{', '.join(ref_cols)}")
        return

    wanted = [t.lower() for t in args.tables]
    missing = [t for t in wanted if t not in tables]
    if missing:
        print(f"Unknown table(s): {', '.join(missing)}. Known: {', '.join(tables)}", file=sys.stderr)
        sys.exit(1)
    try:
        root, edges = plan(tables, wanted)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    columns = [c.strip() for c in args.columns.split(",")] if args.columns else []
    sql = render(root, edges, tables, columns)
    if args.json:
        print(json.dumps({
            "from": root,
            "joins": [{"table": c, "to": p, "on": [{"left": a, "right": b} for a, b in pairs]} for p, c, pairs in edges],
            "sql": sql,
        }, indent=2))
    else:
        added = [c for _, c, _ in edges if c not in wanted]
        if added:
            print(f"-- bridge tables added: {', '.join(added)}")
        print(sql)


if __name__ == "__main__":
    main()
