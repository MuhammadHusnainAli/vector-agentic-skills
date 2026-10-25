#!/usr/bin/env python3
"""Design a document numbering scheme, or check existing IDs against one.

Scheme: <TYPE>[-<AREA>]-<NNN> with a revision held separately (never in the ID). Types and areas are short
upper-case codes. The scheme is printed with its regex, examples and the next free number per type.

Usage:
    python numbering_scheme.py --types QM QP WI QF EXT --areas PRD QA PUR
    python numbering_scheme.py --types QP WI QF --digits 4 --check ids.txt     # one ID per line
    python numbering_scheme.py --types QP WI QF --check -                      # IDs on stdin

Exit codes: 0 scheme printed / all IDs valid, 1 invalid or duplicate IDs found, 2 usage error.
"""

import argparse
import re
import sys
from collections import Counter

TYPE_NAMES = {"QM": "Quality manual", "QP": "Procedure", "WI": "Work instruction", "QF": "Form / template",
              "SP": "Specification", "DWG": "Drawing", "PL": "Policy", "CP": "Control plan", "EXT": "External document",
              "REC": "Record series"}
CODE = re.compile(r"^[A-Z]{2,4}$")


def build_regex(types, areas, digits):
    t = "|".join(map(re.escape, types))
    a = f"(?:-(?:{'|'.join(map(re.escape, areas))}))" if areas else ""
    return re.compile(rf"^(?P<type>{t}){a}-(?P<num>\d{{{digits}}})$")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--types", nargs="+", required=True, help="document type codes, e.g. QM QP WI QF")
    ap.add_argument("--areas", nargs="*", default=[], help="optional area/department codes, e.g. PRD QA")
    ap.add_argument("--digits", type=int, default=3, choices=range(2, 6), help="sequence digits (default 3)")
    ap.add_argument("--check", help="file with existing IDs (one per line) or - for stdin")
    a = ap.parse_args()
    bad = [c for c in a.types + a.areas if not CODE.match(c)]
    if bad:
        print(f"error: codes must be 2-4 upper-case letters: {', '.join(bad)}", file=sys.stderr)
        return 2
    rx = build_regex(a.types, a.areas, a.digits)
    if not a.check:
        fmt = "<TYPE>" + ("-<AREA>" if a.areas else "") + "-" + "N" * a.digits
        print(f"Format: {fmt}   (revision is a separate field: QP-007 rev C, never QP-007C)")
        print(f"Regex:  {rx.pattern}\n")
        print("Types:")
        for t in a.types:
            ex = f"{t}-{a.areas[0]}-{1:0{a.digits}d}" if a.areas else f"{t}-{1:0{a.digits}d}"
            print(f"  {t:<5}{TYPE_NAMES.get(t, 'custom type'):<22}e.g. {ex}")
        if a.areas:
            print("Areas: " + ", ".join(a.areas))
        print(f"\nCapacity: {10 ** a.digits - 1} documents per type" + (" per area" if a.areas else ""))
        print("Rules: never reuse a retired number; keep the ID when the title changes; forms carry the parent "
              "procedure in their title, not their ID.")
        return 0
    try:
        ids = [l.strip() for l in (sys.stdin if a.check == "-" else open(a.check, encoding="utf-8")) if l.strip()]
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    problems = 0
    for doc_id, n in Counter(ids).items():
        if n > 1:
            print(f"DUPLICATE  {doc_id} appears {n} times")
            problems += 1
    nxt = {}
    for doc_id in dict.fromkeys(ids):
        m = rx.match(doc_id)
        if not m:
            hint = " (revision letter in the ID?)" if re.search(r"\d[A-Z]$|[-_ ]rev", doc_id, re.I) else ""
            print(f"INVALID    {doc_id}{hint}")
            problems += 1
        else:
            key = doc_id.rsplit("-", 1)[0]
            nxt[key] = max(nxt.get(key, 0), int(m.group("num")))
    for key, last in sorted(nxt.items()):
        print(f"next free  {key}-{last + 1:0{a.digits}d}")
    print(f"\n{len(ids)} ID(s), {problems} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
