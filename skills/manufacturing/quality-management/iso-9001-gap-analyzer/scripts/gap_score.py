#!/usr/bin/env python3
"""Score a filled ISO 9001 gap worksheet (from gap_template.py) and list the gaps by severity.

Scoring: met = 1, partial = 0.5, not-met = 0; n/a rows are excluded. Gap grades mirror how a
certification auditor would likely grade them:
  GA001 major   core clause not met (system element missing: scope, processes, policy, objectives,
                risks, document control, suppliers, release, nonconforming output, audit, review, CAPA)
  GA002 minor   other clause not met
  GA003 minor   partial implementation
  GA004 check   marked met but no evidence written (an auditor will ask for it)
  GA005 error   n/a on a clause that cannot be excluded (only 7.1.5, 8.3, 8.5.3, 8.5.5 may be)
  GA006 check   clause missing from the sheet or status blank / unknown

Verdict: READY (no majors, >= 90%), CLOSE (no majors, >= 75%), NOT READY otherwise.

Usage:
    python gap_score.py gap.csv
    python gap_score.py gap.csv --json
    cat gap.csv | python gap_score.py -

Exit codes: 0 no major gaps, 1 major gaps or errors, 2 usage or read error.
"""

import argparse
import csv
import json
import sys

from _clauses import BY_CLAUSE, CLAUSES, MAY_NOT_APPLY

SCORE = {"met": 1.0, "partial": 0.5, "not-met": 0.0}
ALIASES = {"yes": "met", "y": "met", "compliant": "met", "no": "not-met", "n": "not-met", "not met": "not-met",
           "missing": "not-met", "part": "partial", "partially": "partial", "na": "n/a", "not applicable": "n/a"}
RANK = {"error": 0, "major": 1, "minor": 2, "check": 3}


def read_rows(path):
    fh = sys.stdin if path == "-" else open(path, newline="", encoding="utf-8-sig")
    with fh:
        rows = list(csv.DictReader(fh))
    if rows and not {"clause", "status"} <= set(rows[0]):
        raise ValueError("CSV needs at least 'clause' and 'status' columns (see gap_template.py)")
    return rows


def assess(rows):
    findings, seen, scores = [], set(), {}
    for r in rows:
        clause = (r.get("clause") or "").strip()
        if clause not in BY_CLAUSE:
            continue
        seen.add(clause)
        _, title, _, doc, core = BY_CLAUSE[clause]
        status = (r.get("status") or "").strip().lower()
        status = ALIASES.get(status, status)
        evidence = (r.get("evidence") or "").strip()
        label = f"{clause} {title}"
        if status == "n/a":
            if clause not in MAY_NOT_APPLY:
                findings.append(("GA005", "error", label, "marked n/a but this requirement always applies; "
                                 "only 7.1.5, 8.3, 8.5.3, 8.5.5 can be justified as not applicable in 4.3"))
            elif not evidence:
                findings.append(("GA006", "check", label, "n/a needs a justification recorded in the scope (4.3)"))
            continue
        if status not in SCORE:
            findings.append(("GA006", "check", label, f"status {status or 'blank'!r}; use met, partial, not-met or n/a"))
            continue
        scores[clause] = SCORE[status]
        need = f" (needs a {doc.replace('maintain', 'document').replace('retain', 'record')})" if doc else ""
        if status == "not-met":
            sev = "major" if core else "minor"
            findings.append(("GA001" if core else "GA002", sev, label, f"not implemented{need}"))
        elif status == "partial":
            findings.append(("GA003", "minor", label, f"partially implemented{need}: {evidence or 'no detail given'}"))
        elif not evidence:
            findings.append(("GA004", "check", label, "marked met with no evidence; name the document, record or interview"))
    for clause, title, *_ in CLAUSES:
        if clause not in seen:
            findings.append(("GA006", "check", f"{clause} {title}", "missing from the worksheet"))
    findings.sort(key=lambda f: (RANK[f[1]], [int(x) for x in f[2].split()[0].split(".")]))
    return scores, findings


def section_scores(scores):
    out = {}
    for sec in "4 5 6 7 8 9 10".split():
        vals = [v for c, v in scores.items() if c.split(".")[0] == sec]
        if vals:
            out[sec] = round(100 * sum(vals) / len(vals), 1)
    return out


def verdict(pct, findings):
    majors = sum(f[1] in ("major", "error") for f in findings)
    if majors:
        return "NOT READY"
    return "READY" if pct >= 90 else "CLOSE" if pct >= 75 else "NOT READY"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="filled worksheet, or - for stdin")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args()
    try:
        rows = read_rows(a.csv)
    except (OSError, ValueError, csv.Error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    scores, findings = assess(rows)
    pct = round(100 * sum(scores.values()) / len(scores), 1) if scores else 0.0
    sections = section_scores(scores)
    v = verdict(pct, findings)
    counts = {s: sum(f[1] == s for f in findings) for s in RANK}
    if a.json:
        print(json.dumps({"readiness_pct": pct, "verdict": v, "sections": sections, "counts": counts,
                          "findings": [dict(zip(("code", "severity", "clause", "message"), f)) for f in findings]}, indent=2))
    else:
        print(f"Readiness: {pct}% across {len(scores)} assessed clauses  ->  {v}")
        print("By section:  " + "  ".join(f"{s}: {p:g}%" for s, p in sections.items()))
        print(f"Gaps: {counts['major']} major, {counts['minor']} minor, {counts['error']} errors, {counts['check']} to check\n")
        for code, sev, label, msg in findings:
            print(f"{code} [{sev}] {label}: {msg}")
    return 1 if counts["major"] or counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
