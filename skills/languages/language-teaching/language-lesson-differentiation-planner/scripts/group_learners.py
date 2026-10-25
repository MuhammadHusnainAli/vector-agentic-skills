#!/usr/bin/env python3
"""Group a mixed-level language class and flag learners who need extra support or extension.

CSV columns: name, level (CEFR like A2, B1+ or a 0-100 score), l1 (optional)

Modes:
  mixed  every group spans the class range (snake draft by level); same-L1 learners spread out where possible
  same   groups of similar level, for tiered tasks

Learners more than one CEFR level (or 25 points) from the class median are flagged.

Usage:
    python group_learners.py class.csv --size 4 --mode mixed
    python group_learners.py class.csv --size 3 --mode same

Exit codes: 0 groups printed, 2 read error or bad CSV.
"""

import argparse
import csv
import statistics
import sys

CEFR = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}


def score(level):
    s = level.strip().upper()
    if s.rstrip("+-") in CEFR:
        return CEFR[s.rstrip("+-")] + (0.5 if s.endswith("+") else 0)
    return float(s)


def snake(learners, n_groups):
    groups = [[] for _ in range(n_groups)]
    for i, l in enumerate(learners):
        rnd, pos = divmod(i, n_groups)
        groups[pos if rnd % 2 == 0 else n_groups - 1 - pos].append(l)
    return groups


def spread_l1(groups):
    """Swap learners of equal level between groups when it reduces same-L1 clustering."""
    def clash(g):
        l1s = [x["l1"] for x in g if x["l1"]]
        return len(l1s) - len(set(l1s))
    for g in groups:
        for i, x in enumerate(g):
            if clash(g) == 0:
                break
            for h in groups:
                if h is g:
                    continue
                for j, y in enumerate(h):
                    if y["score"] == x["score"] and y["l1"] != x["l1"]:
                        before = clash(g) + clash(h)
                        g[i], h[j] = y, x
                        if clash(g) + clash(h) < before:
                            break
                        g[i], h[j] = x, y
                else:
                    continue
                break
    return groups


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--size", type=int, default=4, help="target group size (default 4)")
    ap.add_argument("--mode", choices=["mixed", "same"], default="mixed")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        learners = [{"name": r["name"].strip(), "level": r["level"].strip(), "score": score(r["level"]),
                     "l1": (r.get("l1") or "").strip()} for r in rows]
    except (OSError, KeyError, ValueError, AttributeError) as e:
        print(f"error: needs name and level columns with CEFR levels or scores ({e})", file=sys.stderr)
        return 2
    if len(learners) < 2:
        print("error: need at least two learners", file=sys.stderr)
        return 2
    learners.sort(key=lambda x: -x["score"])
    n = max(1, round(len(learners) / max(2, a.size)))
    if a.mode == "same":
        size = -(-len(learners) // n)
        groups = [learners[i:i + size] for i in range(0, len(learners), size)]
    else:
        groups = spread_l1(snake(learners, n))
    med = statistics.median(x["score"] for x in learners)
    gap = 1 if max(x["score"] for x in learners) <= 6 else 25
    print(f"{len(learners)} learners, median level {med:g}, {len(groups)} {a.mode} groups\n")
    for i, g in enumerate(groups, 1):
        members = ", ".join(f"{x['name']} ({x['level']}{', ' + x['l1'] if x['l1'] else ''})" for x in g)
        print(f"Group {i}: {members}")
    flags = [x for x in learners if abs(x["score"] - med) > gap]
    if flags:
        print()
    for x in flags:
        need = "extension / challenge role" if x["score"] > med else "support: scaffolds, pre-task time, partner"
        print(f"FLAG {x['name']} ({x['level']}) is far from the class median: {need}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
