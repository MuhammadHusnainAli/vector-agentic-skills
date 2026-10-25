#!/usr/bin/env python3
"""Generate a two-level full or fractional factorial design with randomised run order, centre points and the
alias structure.

Factors: NAME:LOW:HIGH (numeric or categorical levels). Fractions use the standard minimum-aberration
generators (Box, Hunter and Hunter); the resolution and the aliases of main effects and two-factor
interactions are printed so you know what the design can and cannot separate.

Usage:
    python doe_design.py --factors Speed:800:1200 Feed:0.10:0.20 Insert:A:B Coolant:5:8
    python doe_design.py --factors A:1:2 B:1:2 C:1:2 D:1:2 E:1:2 --fraction 1 --center 3 --seed 7 > runs.csv
    python doe_design.py --factors ... --max-runs 16        # pick the highest-resolution design within 16 runs

The CSV goes to stdout; the design summary goes to stderr.
Exit codes: 0 design written, 2 usage error.
"""

import argparse
import csv
import itertools
import random
import sys

LET = "ABCDEFGHJK"
GEN = {  # (k, p): generators for the added factors, in terms of the base factors
    (3, 1): ["AB"], (4, 1): ["ABC"], (5, 1): ["ABCD"], (5, 2): ["AB", "AC"],
    (6, 1): ["ABCDE"], (6, 2): ["ABC", "BCD"], (6, 3): ["AB", "AC", "BC"],
    (7, 1): ["ABCDEF"], (7, 2): ["ABCD", "ABDE"], (7, 3): ["ABC", "BCD", "ACD"], (7, 4): ["AB", "AC", "BC", "ABC"],
    (8, 2): ["ABCD", "ABEF"], (8, 3): ["ABC", "ABD", "BCDE"], (8, 4): ["BCD", "ACD", "ABC", "ABD"],
}


def word_mul(a, b):
    return "".join(sorted(set(a) ^ set(b)))


def defining_relation(k, p):
    if p == 0:
        return []
    gens = [g + LET[k - p + i] for i, g in enumerate(GEN[(k, p)])]
    words = set()
    for r in range(1, p + 1):
        for combo in itertools.combinations(gens, r):
            w = ""
            for g in combo:
                w = word_mul(w, g)
            words.add(w)
    return sorted(words, key=lambda w: (len(w), w))


def aliases(effect, words):
    return sorted({word_mul(effect, w) for w in words}, key=lambda w: (len(w), w))


def parse_factor(s):
    parts = s.split(":")
    if len(parts) != 3 or not parts[0]:
        raise ValueError(f"factor {s!r} must be NAME:LOW:HIGH")
    return parts[0], parts[1], parts[2]


def numeric(*vals):
    try:
        [float(v) for v in vals]
        return True
    except ValueError:
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--factors", nargs="+", required=True, help="NAME:LOW:HIGH ...")
    ap.add_argument("--fraction", type=int, default=0, help="p in 2^(k-p) (0 = full factorial)")
    ap.add_argument("--max-runs", type=int, help="choose the largest fraction p that fits (highest resolution)")
    ap.add_argument("--replicates", type=int, default=1)
    ap.add_argument("--center", type=int, default=0, help="centre points (numeric factors only)")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    try:
        factors = [parse_factor(f) for f in a.factors]
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    k = len(factors)
    if not 2 <= k <= 8:
        print("error: 2 to 8 factors supported", file=sys.stderr)
        return 2
    p = a.fraction
    if a.max_runs:
        p = next((q for q in range(0, k) if 2 ** (k - q) <= a.max_runs and (q == 0 or (k, q) in GEN)), None)
        if p is None:
            print(f"error: no design for {k} factors within {a.max_runs} runs", file=sys.stderr)
            return 2
    if p and (k, p) not in GEN:
        print(f"error: no standard 2^({k}-{p}) generators; choose another --fraction", file=sys.stderr)
        return 2
    if a.center and not all(numeric(lo, hi) for _, lo, hi in factors):
        print("error: centre points need numeric levels for every factor", file=sys.stderr)
        return 2
    base = k - p
    words = defining_relation(k, p)
    res = min((len(w) for w in words), default=None)
    rows = []
    for std, levels in enumerate(itertools.product([-1, 1], repeat=base), 1):
        coded = dict(zip(LET[:base], reversed(levels)))   # A changes fastest (Yates order)
        for i, g in enumerate(GEN.get((k, p), [])):
            v = 1
            for ch in g:
                v *= coded[ch]
            coded[LET[base + i]] = v
        rows.append((std, [coded[LET[i]] for i in range(k)]))
    runs = [(std, c) for _ in range(a.replicates) for std, c in rows]
    runs += [(len(rows) + i + 1, [0] * k) for i in range(a.center)]
    order = list(range(len(runs)))
    random.Random(a.seed).shuffle(order)
    w = csv.writer(sys.stdout, lineterminator="\n")
    w.writerow(["run", "std_order"] + [f"{f[0]}_coded" for f in factors] + [f[0] for f in factors] + ["response"])
    for run, idx in enumerate(order, 1):
        std, c = runs[idx]
        actual = []
        for (name, lo, hi), v in zip(factors, c):
            actual.append(lo if v == -1 else hi if v == 1 else f"{(float(lo) + float(hi)) / 2:g}")
        w.writerow([run, std] + c + actual + [""])
    names = {LET[i]: f[0] for i, f in enumerate(factors)}
    roman = {3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII"}
    say = lambda s: print(s, file=sys.stderr)
    say(f"Design: 2^{k}" + (f"-{p}" if p else "") + f" = {len(rows)} runs x {a.replicates} replicate(s) + {a.center} centre point(s) = {len(runs)} runs")
    say("Factors: " + ", ".join(f"{LET[i]}={f[0]} ({f[1]} / {f[2]})" for i, f in enumerate(factors)))
    if p:
        say(f"Generators: " + ", ".join(f"{LET[base + i]}={g}" for i, g in enumerate(GEN[(k, p)])))
        say(f"Defining relation: I = {' = '.join(words)}   Resolution {roman.get(res, res)}")
        notes = {3: "main effects aliased with 2-factor interactions: screening only",
                 4: "main effects clear; 2-factor interactions aliased with each other",
                 5: "main effects and 2-factor interactions clear"}
        say(f"  {notes.get(res, 'high resolution')}")
        shown = set()
        for e in list(LET[:k]) + ["".join(c) for c in itertools.combinations(LET[:k], 2)]:
            group = tuple(sorted({e} | {x for x in aliases(e, words) if len(x) <= 2}, key=lambda w: (len(w), w)))
            if len(group) > 1 and group not in shown:
                shown.add(group)
                say("  " + " = ".join(group))
    else:
        say("Full factorial: all main effects and interactions estimable")
    if a.replicates == 1 and not a.center:
        say("No replicates or centre points: significance will rely on Lenth's method (effect sparsity).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
