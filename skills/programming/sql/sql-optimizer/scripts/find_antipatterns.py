#!/usr/bin/env python3
"""Scan SQL for performance anti-patterns and suggest rewrites.

Flags non-sargable predicates (functions or arithmetic on filtered columns),
leading-wildcard LIKE, NOT IN with subqueries, SELECT *, ORDER BY random,
deep OFFSET pagination, UNION without ALL, DISTINCT hiding join fan-out,
correlated subqueries in the SELECT list, COUNT(*) > 0 existence checks,
HAVING filters that belong in WHERE, huge IN lists and implicit cross joins.
Static analysis only: confirm with EXPLAIN before and after a rewrite.

Usage:
    python find_antipatterns.py query.sql
    cat query.sql | python find_antipatterns.py - --json
    python find_antipatterns.py query.sql --strict      # exit 1 on any high-severity finding

No dependencies.
"""

import argparse
import json
import re
import sys

FUNCS = (r"UPPER|LOWER|TRIM|LTRIM|RTRIM|SUBSTR|SUBSTRING|LEFT|RIGHT|DATE|YEAR|MONTH|DAY|DATE_TRUNC|DATE_FORMAT|"
         r"TO_CHAR|TO_DATE|CAST|CONVERT|COALESCE|IFNULL|ISNULL|NVL|ABS|ROUND|FLOOR|CONCAT|EXTRACT|DATEPART|STRFTIME")


def mask(sql):
    """Blank string contents and comments so patterns don't match inside them."""
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
        elif sql[i] == "'":
            j = i + 1
            while j < n and not (sql[j] == "'" and sql[j + 1:j + 2] != "'"):
                j += 2 if sql[j:j + 2] == "''" else 1
            out[i + 1:j] = " " * (j - i - 1)
            i = j + 1
        else:
            i += 1
    return "".join(out)


def clause_spans(masked, keyword, stops):
    """Yield (start, end) of each `keyword` clause body, ending at the next stop keyword at the same depth."""
    for m in re.finditer(rf"\b{keyword}\b", masked, re.I):
        depth, i = 0, m.end()
        while i < len(masked):
            ch = masked[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0 and re.match(rf"\b({stops})\b", masked[i:i + 12], re.I) and masked[i - 1:i].isspace():
                break
            elif ch == ";":
                break
            i += 1
        yield m.end(), i


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


RULES = []


def rule(rid, severity, title, fix):
    def wrap(fn):
        RULES.append({"id": rid, "severity": severity, "title": title, "fix": fix, "fn": fn})
        return fn
    return wrap


@rule("non-sargable-function", "high", "Function wrapped around a filtered column",
      "Compare the bare column to a transformed constant (e.g. created_at >= '2026-01-01' AND created_at < '2027-01-01' "
      "instead of YEAR(created_at) = 2026), or add an expression index.")
def _(m, sql):
    hits = []
    for kw in ("WHERE", "ON", "HAVING"):
        for s, e in clause_spans(m, kw, "GROUP|ORDER|HAVING|LIMIT|UNION|JOIN|LEFT|RIGHT|INNER|FULL|CROSS|WINDOW"):
            for f in re.finditer(rf"\b({FUNCS})\s*\(\s*(?:[A-Za-z_]\w*\.)?[A-Za-z_]\w*\s*(?:[,)]|AS\b)", m[s:e], re.I):
                tail = m[s + f.end():s + f.end() + 40]
                if re.match(r"[^=<>]*?(=|<|>|\bLIKE\b|\bIN\b|\bBETWEEN\b)", tail, re.I) or re.search(r"(=|<|>)\s*$", m[s:s + f.start()]):
                    hits.append(s + f.start())
    return hits


@rule("non-sargable-arithmetic", "medium", "Arithmetic on a column inside a filter",
      "Move the arithmetic to the constant side: price * 1.2 > 100  ->  price > 100 / 1.2.")
def _(m, sql):
    hits = []
    for s, e in clause_spans(m, "WHERE", "GROUP|ORDER|HAVING|LIMIT|UNION"):
        for f in re.finditer(r"\b[A-Za-z_][\w.]*\s*[-+*/]\s*[\w.]+\s*(=|<=|>=|<|>)", m[s:e]):
            if not re.match(r"\s*\d", m[s + f.start():]):
                hits.append(s + f.start())
    return hits


@rule("leading-wildcard", "high", "LIKE pattern starts with a wildcard",
      "A leading % prevents index range scans. Use full-text search, a trigram index (pg_trgm), or a reversed-column index.")
def _(m, sql):
    return [f.start() for f in re.finditer(r"\bLIKE\s+'", m, re.I) if sql[f.end():f.end() + 1] == "%"]


@rule("not-in-subquery", "high", "NOT IN with a subquery",
      "Use NOT EXISTS: if the subquery returns any NULL, NOT IN returns no rows at all, and it often blocks anti-join plans.")
def _(m, sql):
    return [f.start() for f in re.finditer(r"\bNOT\s+IN\s*\(\s*SELECT\b", m, re.I)]


@rule("select-star", "medium", "SELECT * returns every column",
      "List only the columns you need so covering indexes can be used and less data crosses the network.")
def _(m, sql):
    return [f.start() for f in re.finditer(r"\bSELECT\s+(?:DISTINCT\s+)?(?:TOP\s+\d+\s+)?\*", m, re.I)]


@rule("order-by-random", "high", "ORDER BY random value sorts the whole table",
      "Sample with TABLESAMPLE, pick random ids in a range, or pre-shuffle; RAND()/NEWID() sorting is O(n log n) per call.")
def _(m, sql):
    return [f.start() for f in re.finditer(r"\bORDER\s+BY\s+(RAND|RANDOM|NEWID|DBMS_RANDOM\.VALUE)\b", m, re.I)]


@rule("deep-offset", "medium", "Large OFFSET pagination",
      "Use keyset pagination: WHERE (created_at, id) < (:last_created_at, :last_id) ORDER BY created_at DESC, id DESC LIMIT n.")
def _(m, sql):
    return [f.start() for f in re.finditer(r"\bOFFSET\s+\d{4,}\b|\bLIMIT\s+\d{4,}\s*,", m, re.I)]


@rule("union-distinct", "low", "UNION removes duplicates with an extra sort",
      "Use UNION ALL when the branches cannot overlap or duplicates are acceptable.")
def _(m, sql):
    return [f.start() for f in re.finditer(r"\bUNION\b(?!\s+ALL)", m, re.I)]


@rule("distinct-with-join", "medium", "DISTINCT on a joined query",
      "DISTINCT often hides a fan-out join. Aggregate the many side first or use EXISTS instead of joining.")
def _(m, sql):
    if re.search(r"\bSELECT\s+DISTINCT\b", m, re.I) and re.search(r"\bJOIN\b", m, re.I):
        return [re.search(r"\bSELECT\s+DISTINCT\b", m, re.I).start()]
    return []


@rule("correlated-select-subquery", "medium", "Correlated subquery in the SELECT list",
      "It runs once per row. Rewrite as a JOIN to a pre-aggregated derived table or use a window function.")
def _(m, sql):
    hits = []
    for f in re.finditer(r",\s*\(\s*SELECT\b", m, re.I):
        depth, i = 1, m.find("(", f.start()) + 1
        while i < len(m) and depth:
            depth += {"(": 1, ")": -1}.get(m[i], 0)
            i += 1
        if re.search(r"\bWHERE\b[^;]*\b\w+\.\w+\s*=\s*\w+\.\w+", m[f.start():i], re.I):
            hits.append(f.start())
    return hits


@rule("count-for-existence", "medium", "COUNT(*) used to test existence",
      "Use EXISTS (SELECT 1 ...), which stops at the first matching row.")
def _(m, sql):
    test = r"\s*(>\s*0|>=\s*1|<>\s*0|!=\s*0)"
    hits = [f.start() for f in re.finditer(r"\bCOUNT\s*\(\s*(\*|1)\s*\)" + test, m, re.I)]
    for f in re.finditer(r"\(\s*SELECT\s+COUNT\s*\(\s*(\*|1)\s*\)", m, re.I):  # (SELECT COUNT(*) ...) > 0
        depth, i = 1, f.start() + 1
        while i < len(m) and depth:
            depth += {"(": 1, ")": -1}.get(m[i], 0)
            i += 1
        if re.match(test, m[i:], re.I):
            hits.append(f.start())
    return hits


@rule("having-without-aggregate", "low", "HAVING condition without an aggregate",
      "Move non-aggregate conditions to WHERE so rows are filtered before grouping.")
def _(m, sql):
    hits = []
    for s, e in clause_spans(m, "HAVING", "ORDER|LIMIT|UNION|WINDOW"):
        for part in re.split(r"\bAND\b", m[s:e], flags=re.I):
            if part.strip() and not re.search(r"\b(COUNT|SUM|AVG|MIN|MAX|STRING_AGG|GROUP_CONCAT|ARRAY_AGG)\s*\(", part, re.I):
                hits.append(s)
                break
    return hits


@rule("huge-in-list", "low", "IN list with more than 100 literals",
      "Load the values into a temp table or VALUES list and JOIN; very long IN lists inflate parse and plan time.")
def _(m, sql):
    return [f.start() for f in re.finditer(r"\bIN\s*\(", m, re.I)
            if (lambda body: body.count(",") >= 100 and "SELECT" not in body.upper())(m[f.end():m.find(")", f.end())])]


@rule("implicit-cross-join", "high", "Comma join without a join condition",
      "Use explicit JOIN ... ON; a comma-separated FROM with no WHERE produces a cartesian product.")
def _(m, sql):
    hits = []
    for f in re.finditer(r"\bFROM\s+[\w.]+(?:\s+(?:AS\s+)?\w+)?\s*,\s*[\w.]+", m, re.I):
        rest = m[f.end():]
        stmt_end = rest.find(";")
        stmt = rest if stmt_end < 0 else rest[:stmt_end]
        if not re.search(r"\bWHERE\b", stmt, re.I):
            hits.append(f.start())
    return hits


def analyse(sql):
    masked = mask(sql)
    findings = []
    for r in RULES:
        for pos in sorted(set(r["fn"](masked, sql))):
            snippet = re.sub(r"\s+", " ", sql[pos:pos + 70]).strip()
            findings.append({"rule": r["id"], "severity": r["severity"], "line": line_of(sql, pos),
                             "title": r["title"], "snippet": snippet, "fix": r["fix"]})
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(findings, key=lambda f: (order[f["severity"]], f["line"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="SQL file, or - for stdin")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any high-severity issue is found")
    args = ap.parse_args()
    sql = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
    findings = analyse(sql)

    if args.json:
        print(json.dumps(findings, indent=2))
    elif not findings:
        print("No anti-patterns found. Still check the execution plan for scans on large tables.")
    else:
        counts = {s: sum(f["severity"] == s for f in findings) for s in ("high", "medium", "low")}
        print(f"{len(findings)} finding(s): {counts['high']} high, {counts['medium']} medium, {counts['low']} low\n")
        for i, f in enumerate(findings, 1):
            print(f"{i}. [{f['severity'].upper()}] line {f['line']}: {f['title']}")
            print(f"   near: {f['snippet']}")
            print(f"   fix:  {f['fix']}\n")
    sys.exit(1 if args.strict and any(f["severity"] == "high" for f in findings) else 0)


if __name__ == "__main__":
    main()
