#!/usr/bin/env python3
"""ANSI/ASQ Z1.4 (ISO 2859-1) single sampling plan, normal inspection: code letter, sample size, Ac, Re.

Table I gives the code letter from lot size and inspection level; Table II-A gives n, Ac, Re from the code
letter and AQL. Table II-A is diagonal: one code letter down equals one AQL step left, acceptance numbers run
0, (up arrow), (down arrow), 1, 2, 3, 5, 7, 10, 14, 21, 30, 44 along each diagonal. Arrows are followed to the
first plan above or below, which changes the sample size - always use that plan's n with its Ac/Re.
AQLs above 10 apply only to nonconformities per 100 units (--per-100-units).

For tightened or reduced inspection use Tables II-B / II-C of the standard; switching rules are summarised in
references/z14-and-switching.md.

Usage:
    python z14_plan.py --lot 1000 --aql 1.0
    python z14_plan.py --lot 5000 --aql 0.65 --level S-3
    python z14_plan.py --lot 1000 --aql 25 --per-100-units

Exit codes: 0 plan printed, 2 usage error.
"""

import argparse
import sys

LOTS = [(8, "AAAAAAB"), (15, "AAAAABC"), (25, "AABBBCD"), (50, "ABBCCDE"), (90, "BBCCCEF"), (150, "BBCDDFG"),
        (280, "BCDEEGH"), (500, "BCDEFHJ"), (1200, "CCEFGJK"), (3200, "CDEGHKL"), (10000, "CDFGJLM"),
        (35000, "CDFHKMN"), (150000, "DEGJLNP"), (500000, "DEGJMPQ"), (float("inf"), "DEHKNQR")]
LEVELS = ["S-1", "S-2", "S-3", "S-4", "I", "II", "III"]
LETTERS = "ABCDEFGHJKLMNPQR"
SIZES = [2, 3, 5, 8, 13, 20, 32, 50, 80, 125, 200, 315, 500, 800, 1250, 2000]
AQLS = [0.010, 0.015, 0.025, 0.040, 0.065, 0.10, 0.15, 0.25, 0.40, 0.65, 1.0, 1.5, 2.5, 4.0, 6.5, 10, 15, 25,
        40, 65, 100, 150, 250, 400, 650, 1000]
AC = [1, 2, 3, 5, 7, 10, 14, 21, 30, 44]   # diagonal positions 17..26


def code_letter(lot, level):
    for cap, row in LOTS:
        if lot <= cap:
            return row[LEVELS.index(level)]
    raise ValueError(lot)


def plan(letter, aql_i, trail):
    """Follow Table II-A from (letter, AQL) to an actual plan; returns (letter index, Ac)."""
    li = LETTERS.index(letter)
    while True:
        k = li + aql_i
        if k < 14:                      # down arrow: first plan below
            li += 1
            trail.append("down")
        elif k == 14:
            return li, 0
        elif k == 15 or k > 26:         # up arrow: first plan above
            li -= 1
            trail.append("up")
        elif k == 16:                   # down arrow
            li += 1
            trail.append("down")
        else:
            return li, AC[k - 17]
        if not 0 <= li < len(LETTERS):
            return None, None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lot", type=int, required=True, help="lot or batch size")
    ap.add_argument("--aql", type=float, required=True, help="AQL (percent nonconforming, or per 100 units)")
    ap.add_argument("--level", choices=LEVELS, default="II", help="inspection level (default II)")
    ap.add_argument("--per-100-units", action="store_true", help="AQL is nonconformities per 100 units")
    a = ap.parse_args()
    if a.lot < 2:
        print("error: --lot must be at least 2", file=sys.stderr)
        return 2
    match = [i for i, q in enumerate(AQLS) if abs(q - a.aql) < 1e-9]
    if not match:
        print(f"error: AQL {a.aql:g} is not a preferred value; use one of {', '.join(f'{q:g}' for q in AQLS)}", file=sys.stderr)
        return 2
    if a.aql > 10 and not a.per_100_units:
        print("error: AQLs above 10 are only for nonconformities per 100 units (--per-100-units)", file=sys.stderr)
        return 2
    letter = code_letter(a.lot, a.level)
    trail = []
    li, ac = plan(letter, match[0], trail)
    print(f"Lot {a.lot}, inspection level {a.level} -> code letter {letter} (n = {SIZES[LETTERS.index(letter)]})")
    if li is None:
        print("No single sampling plan in the table for this combination: use 100% inspection or a lower level.")
        return 0
    n = SIZES[li]
    if trail:
        print(f"Table II-A arrow{'s' if len(trail) > 1 else ''} ({', '.join(trail)}) -> use the plan for code letter {LETTERS[li]}")
    if n >= a.lot:
        print(f"Sample size {n} >= lot size: inspect 100% of the lot (accept if nonconforming <= {ac}).")
        return 0
    unit = "nonconformities" if a.per_100_units else "nonconforming units"
    print(f"\nNormal inspection, single sampling: n = {n}, Ac = {ac}, Re = {ac + 1}")
    print(f"Inspect {n} randomly selected units; accept the lot if {unit} <= {ac}, reject if >= {ac + 1}.")
    print("Check the OC curve (oc_curve.py) to see the protection this plan gives against bad lots.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
