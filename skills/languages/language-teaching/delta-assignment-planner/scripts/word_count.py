#!/usr/bin/env python3
"""Count words per section of an assignment draft and check them against limits.

Sections are Markdown headings (# or ##). Sections named References, Bibliography or Appendix are excluded by
default; --no-tables and --no-quotes also exclude Markdown tables and block quotes ("> ..."). Check your
handbook for exactly what counts towards the limit.

Usage:
    python word_count.py essay.md --limit "Background essay=2000-2500"
    python word_count.py m3.md --total 4000-4500 --limit "Needs analysis=900-1100" --no-tables

Exit codes: 0 all within limits, 1 a section or the total is outside its limit, 2 read error or bad limit.
"""

import argparse
import re
import sys

EXCLUDED = re.compile(r"^(references?|bibliography|appendi(x|ces)|works cited)\b", re.I)


def rng(spec):
    lo, _, hi = spec.partition("-")
    return int(lo), int(hi or lo)


def count(text, tables, quotes):
    keep = []
    for line in text.splitlines():
        if tables and line.lstrip().startswith("|"):
            continue
        if quotes and line.lstrip().startswith(">"):
            continue
        keep.append(line)
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", "\n".join(keep)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("draft")
    ap.add_argument("--limit", action="append", default=[], help='"Section title=min-max" (repeatable)')
    ap.add_argument("--total", help="min-max for the whole counted text")
    ap.add_argument("--no-tables", action="store_true")
    ap.add_argument("--no-quotes", action="store_true")
    a = ap.parse_args()
    try:
        text = open(a.draft, encoding="utf-8").read()
        limits = {k.strip().lower(): rng(v) for k, _, v in (s.partition("=") for s in a.limit)}
        total_lim = rng(a.total) if a.total else None
    except (OSError, ValueError) as e:
        print(f"error: {e} (limits look like \"Title=2000-2500\")", file=sys.stderr)
        return 2
    parts = re.split(r"^(#{1,2})\s+(.+)$", text, flags=re.M)
    sections = [("(before first heading)", parts[0])] + [(parts[i + 1].strip(), parts[i + 2]) for i in range(1, len(parts) - 1, 3)]
    bad, total = [], 0
    print("| Section | Words | Limit | Status |\n|---------|-------|-------|--------|")
    for title, body in sections:
        n = count(body, a.no_tables, a.no_quotes)
        if title == "(before first heading)" and n == 0:
            continue
        if EXCLUDED.match(title):
            print(f"| {title} | {n} | - | excluded |")
            continue
        total += n
        lim = limits.pop(title.lower(), None)
        status = "-" if not lim else "OK" if lim[0] <= n <= lim[1] else ("UNDER" if n < lim[0] else "OVER")
        if status in ("UNDER", "OVER"):
            bad.append(title)
        print(f"| {title} | {n} | {f'{lim[0]}-{lim[1]}' if lim else '-'} | {status} |")
    tstatus = "" if not total_lim else " OK" if total_lim[0] <= total <= total_lim[1] else " OUTSIDE"
    print(f"\nCounted total: {total}" + (f" (limit {total_lim[0]}-{total_lim[1]}){tstatus}" if total_lim else ""))
    for missing in limits:
        print(f"warning: no section titled '{missing}'")
    if tstatus == " OUTSIDE":
        bad.append("total")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
