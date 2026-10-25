#!/usr/bin/env python3
"""Print an ISO 9001:2015 gap-assessment worksheet, one row per auditable clause.

Fill in `status` (met / partial / not-met / n/a) and `evidence` for each row, then score it with
gap_score.py. Requirements are paraphrased; use the standard itself for the exact wording.

Usage:
    python gap_template.py > gap.csv
    python gap_template.py --clause 8          # only clause 8 rows
    python gap_template.py --markdown          # table for a report or workshop handout

Exit codes: 0 printed, 2 usage error.
"""

import argparse
import csv
import sys

from _clauses import CLAUSES

DOC = {"maintain": "document", "retain": "record", "maintain+retain": "document + record", "": ""}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clause", help="only clauses starting with this prefix, e.g. 8 or 8.5")
    ap.add_argument("--markdown", action="store_true", help="print a Markdown table instead of CSV")
    a = ap.parse_args()

    rows = [r for r in CLAUSES if not a.clause or r[0] == a.clause or r[0].startswith(a.clause.rstrip(".") + ".")]
    if not rows:
        print(f"error: no clause matches {a.clause!r} (valid: 4 to 10.3)", file=sys.stderr)
        return 2
    if a.markdown:
        print("| Clause | Title | Requirement | Documented info | Status | Evidence |")
        print("|--------|-------|-------------|-----------------|--------|----------|")
        for c, t, req, doc, _ in rows:
            print(f"| {c} | {t} | {req} | {DOC[doc]} |  |  |")
        return 0
    w = csv.writer(sys.stdout, lineterminator="\n")
    w.writerow(["clause", "title", "requirement", "documented_info", "status", "evidence", "notes"])
    for c, t, req, doc, _ in rows:
        w.writerow([c, t, req, DOC[doc], "", "", ""])
    return 0


if __name__ == "__main__":
    sys.exit(main())
