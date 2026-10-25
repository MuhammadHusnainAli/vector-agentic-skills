#!/usr/bin/env python3
"""Draft control plan rows from a PFMEA (AIAG control plan columns), one row per step and control.

Reads the PFMEA CSV used by process-fmea-builder (step, function, failure_mode, cause, prevention, detection,
special, S ...). For each row it creates:
  - a product-characteristic row from the step function, controlled by the detection control
  - a process-characteristic row from the cause, controlled by the prevention control
Sample size / frequency are parsed when the control text says '1 in 50', 'every 10th', '100%', 'per shift',
'at setup'; anything not derivable is left as TODO. Reaction plans are drafted with containment
('since the last good check') and must be completed by the team.

Usage:
    python cp_from_pfmea.py pfmea.csv --part VB-2210 --phase production > control_plan.csv

Exit codes: 0 written, 2 read error or missing columns.
"""

import argparse
import csv
import re
import sys

COLS = ["part", "phase", "op", "process", "char_no", "product_char", "process_char", "special", "spec",
        "method", "sample_size", "frequency", "control_method", "reaction_plan"]


def sampling(text):
    t = text.lower()
    m = re.search(r"\b1\s*(in|of|per)\s*(\d+)", t)
    if m:
        return "1", f"every {m.group(2)} parts"
    m = re.search(r"every\s*(\d+)(st|nd|rd|th)?\s*(part|pc)?", t)
    if m:
        return "1", f"every {m.group(1)} parts"
    if "100%" in t or "automatic" in t or "sensor" in t or "interlock" in t:
        return "100%", "continuous"
    m = re.search(r"(\d+)\s*(per|/)\s*(shift|pallet|lot|batch|hour)", t)
    if m:
        return m.group(1), f"per {m.group(3)}"
    if "setup" in t or "set-up" in t or "first-off" in t or "first off" in t:
        return "1", "at setup / first-off"
    return "TODO", "TODO"


def control_method(text, special):
    t = text.lower()
    if re.search(r"poka|error[- ]?proof|sensor|interlock|automatic", t):
        return "Error-proofing"
    if "spc" in t or "chart" in t:
        return "X-bar/R or I-MR chart"
    if special:
        return "TODO: SPC or 100% / error-proofing required for special characteristic"
    return "Check sheet"


def spec_of(function):
    m = re.search(r"(\d+(?:\.\d+)?\s*(?:\+/-|±|\+)\s*[\d./+-]+.*)$", function)
    return m.group(1).strip() if m else "TODO"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pfmea", help="PFMEA CSV, or - for stdin")
    ap.add_argument("--part", default="TODO", help="part number")
    ap.add_argument("--phase", choices=["prototype", "pre-launch", "production"], default="production")
    a = ap.parse_args()
    try:
        fh = sys.stdin if a.pfmea == "-" else open(a.pfmea, newline="", encoding="utf-8-sig")
        with fh:
            rows = list(csv.DictReader(fh))
    except (OSError, csv.Error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not rows or not {"step", "function", "detection", "prevention"} <= set(rows[0]):
        print("error: PFMEA CSV needs step, function, prevention and detection columns", file=sys.stderr)
        return 2
    out = csv.writer(sys.stdout, lineterminator="\n")
    out.writerow(COLS)
    seen, n = set(), 0
    for r in rows:
        g = lambda k: (r.get(k) or "").strip()
        step = g("step")
        op, _, proc = step.partition(" ")
        special = g("special").upper()
        for kind, ctrl in (("product", g("detection")), ("process", g("prevention"))):
            if not ctrl:
                continue
            char = g("function") if kind == "product" else g("cause")
            key = (step, kind, char, ctrl)
            if key in seen:
                continue
            seen.add(key)
            n += 1
            size, freq = sampling(ctrl)
            reaction = ("Stop; quarantine parts since the last good check; 100% inspect; correct; notify supervisor "
                        "and quality; record on NCR") if kind == "product" else \
                       ("Stop; restore the process condition; verify the next part; check parts since the last confirmed "
                        "good condition; record")
            out.writerow([a.part, a.phase, op, proc or op, n,
                          char if kind == "product" else "", char if kind == "process" else "",
                          special, spec_of(char) if kind == "product" else "TODO process setting",
                          ctrl, size, freq, control_method(ctrl, special in ("CC", "SC")), reaction])
    print(f"{n} control plan rows drafted; complete every TODO and review with the team", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
