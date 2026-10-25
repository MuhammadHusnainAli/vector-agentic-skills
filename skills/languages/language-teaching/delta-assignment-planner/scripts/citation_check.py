#!/usr/bin/env python3
"""Cross-check author-date citations against the reference list of an assignment.

In-text forms recognised: (Thornbury, 2006), (Thornbury 2006: 45), Thornbury (2006), (Swan and Walter, 2011),
(Richards et al., 2002), multiple citations separated by ';'. The reference list is the text after a heading named
References or Bibliography; each entry starts with "Surname, Initials (Year)" or "Surname, I. Year".

Checks:
  CI001 high    cited in the text but not in the reference list
  CI002 medium  in the reference list but never cited
  CI003 medium  cited with a year that differs from the reference list
  CI004 low     direct quotation ("...") followed by a citation without a page number

Usage:
    python citation_check.py essay.md

Exit codes: 0 no high findings, 1 high findings, 2 read error or no reference list.
"""

import argparse
import re
import sys

YEAR = r"(\d{4}[a-z]?|n\.d\.)"
NAME = r"[A-Z][A-Za-z'’-]+"
CITE_PAREN = re.compile(r"\(([^()]*?\d{4}[a-z]?[^()]*)\)")
CITE_NARR = re.compile(rf"\b({NAME})(?:\s+(?:and|&)\s+{NAME}|\s+et al\.)?\s+\({YEAR}(?:[:,]\s*p*\.?\s*\d+(?:-\d+)?)?\)")
ONE = re.compile(rf"({NAME})(?:\s+(?:and|&)\s+{NAME}|\s+et al\.?)?,?\s+{YEAR}(?:[:,]\s*(?:pp?\.\s*)?(\d+))?")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("essay")
    a = ap.parse_args()
    try:
        text = open(a.essay, encoding="utf-8").read()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    m = re.search(r"^#{1,3}\s*(references|bibliography)\s*$", text, re.I | re.M)
    if not m:
        print("error: no '# References' or '# Bibliography' heading", file=sys.stderr)
        return 2
    body, refs_text = text[:m.start()], text[m.end():]
    refs, entries = {}, 0
    for line in refs_text.splitlines():
        r = re.match(rf"^\s*[-*]?\s*({NAME}),.*?\(?{YEAR}\)?", line)
        if r:
            entries += 1
            refs.setdefault(r.group(1), set()).add(r.group(2))
    cites = []  # (surname, year, page, position)
    for c in CITE_PAREN.finditer(body):
        for part in c.group(1).split(";"):
            o = ONE.search(part)
            if o:
                cites.append((o.group(1), o.group(2), o.group(3), c.start()))
    for c in CITE_NARR.finditer(body):
        page = re.search(r"[:,]\s*p*\.?\s*(\d+)\)", c.group(0))
        cites.append((c.group(1), c.group(2), page.group(1) if page else None, c.start()))
    f = []
    cited = set()
    for name, year, page, pos in cites:
        cited.add(name)
        if name not in refs:
            f.append(("CI001", "high", f"{name} ({year}) cited but not in the reference list"))
        elif year not in refs[name]:
            f.append(("CI003", "medium", f"{name}: cited as {year}, listed as {', '.join(sorted(refs[name]))}"))
        before = body[max(0, pos - 3):pos]
        if re.search(r"[\"”]\s*$", before) and not page:
            f.append(("CI004", "low", f"{name} ({year}): direct quotation without a page number"))
    for name in sorted(set(refs) - cited):
        f.append(("CI002", "medium", f"{name} is in the reference list but never cited"))
    print(f"{len(cites)} citations, {entries} reference entries")
    seen, order = set(), {"high": 0, "medium": 1, "low": 2}
    for code, sev, msg in sorted(f, key=lambda x: (order[x[1]], x[0])):
        if msg not in seen:
            seen.add(msg)
            print(f"{code} [{sev}] {msg}")
    if not f:
        print("OK: citations and reference list match")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
