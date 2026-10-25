#!/usr/bin/env python3
"""List the 18 PPAP elements to submit or retain for a submission level (AIAG PPAP 4th edition, Table 4.2)
and check which are missing.

S = submit to the customer, R = retain at the supplier and make available, * = as the customer defines
(level 4). Level 5 means complete data reviewed at the supplier's site.

Usage:
    python ppap_package.py --level 3
    python ppap_package.py --level 3 --have have.txt            # one element number or name per line
    python ppap_package.py --level 2 --no-appearance --no-design

Exit codes: 0 package complete (or no --have given), 1 elements to submit are missing, 2 usage error.
"""

import argparse
import re
import sys

# (number, element, requirement per level 1..5)
ELEMENTS = [
    (1, "Design records", "RSS*R"),
    (2, "Authorized engineering change documents", "RSS*R"),
    (3, "Customer engineering approval", "RRS*R"),
    (4, "Design FMEA", "RRS*R"),
    (5, "Process flow diagram", "RRS*R"),
    (6, "Process FMEA", "RRS*R"),
    (7, "Control plan", "RRS*R"),
    (8, "Measurement system analysis studies", "RRS*R"),
    (9, "Dimensional results", "RSS*R"),
    (10, "Material and performance test results", "RSS*R"),
    (11, "Initial process studies", "RRS*R"),
    (12, "Qualified laboratory documentation", "RSS*R"),
    (13, "Appearance approval report", "SSS*R"),
    (14, "Sample production parts", "RSS*R"),
    (15, "Master sample", "RRR*R"),
    (16, "Checking aids", "RRR*R"),
    (17, "Customer-specific requirements records", "RRS*R"),
    (18, "Part submission warrant (PSW)", "SSSSR"),
]
LEVELS = {1: "PSW only (plus appearance approval report for appearance items)",
          2: "PSW with product samples and limited supporting data",
          3: "PSW with product samples and complete supporting data (default)",
          4: "PSW and other requirements as defined by the customer",
          5: "PSW with product samples and complete supporting data reviewed at the supplier's site"}
ALIASES = {"psw": 18, "aar": 13, "dfmea": 4, "pfmea": 6, "msa": 8, "gage r&r": 8, "pfd": 5, "cp": 7,
           "ecn": 2, "cpk": 11, "ppk": 11, "csr": 17}
WORD = {"S": "submit", "R": "retain", "*": "as customer defines"}


def parse_have(path):
    text = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    have = set()
    for line in text.splitlines():
        line = line.strip().lower()
        if not line:
            continue
        m = re.match(r"^(\d{1,2})\b", line)
        if m:
            have.add(int(m.group(1)))
            continue
        if line in ALIASES:
            have.add(ALIASES[line])
            continue
        have.update(n for n, name, _ in ELEMENTS if line in name.lower() or name.lower() in line)
    return have


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--level", type=int, choices=range(1, 6), default=3)
    ap.add_argument("--have", help="file listing elements already prepared (number or name per line), or -")
    ap.add_argument("--no-appearance", action="store_true", help="part has no appearance requirements (element 13 n/a)")
    ap.add_argument("--no-design", action="store_true", help="supplier has no design responsibility (element 4 n/a)")
    a = ap.parse_args()
    try:
        have = parse_have(a.have) if a.have else None
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"PPAP level {a.level}: {LEVELS[a.level]}\n")
    print(f"{'#':>2}  {'Element':<42}{'Requirement':<22}" + ("Status" if have is not None else ""))
    missing_s, missing_r = [], []
    for n, name, req in ELEMENTS:
        r = req[a.level - 1]
        if (n == 13 and a.no_appearance) or (n == 4 and a.no_design):
            print(f"{n:>2}  {name:<42}{'n/a':<22}")
            continue
        status = ""
        if have is not None:
            status = "ready" if n in have else "MISSING"
            if n not in have:
                (missing_s if r == "S" else missing_r).append(f"{n} {name}")
        print(f"{n:>2}  {name:<42}{WORD[r]:<22}{status}")
    if a.level == 4:
        print("\nLevel 4: confirm with the customer which elements to submit (marked 'as customer defines').")
    if have is None:
        return 0
    print()
    if missing_s:
        print("Missing, must be SUBMITTED: " + "; ".join(missing_s))
    if missing_r:
        print("Missing, must be RETAINED and available: " + "; ".join(missing_r))
    if not (missing_s or missing_r):
        print("Package complete for this level.")
    return 1 if missing_s else 0


if __name__ == "__main__":
    sys.exit(main())
