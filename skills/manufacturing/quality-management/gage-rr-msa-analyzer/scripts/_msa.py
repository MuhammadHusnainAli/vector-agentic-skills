"""Shared input handling and acceptance rules for the Gage R&R scripts (stdlib only)."""

import csv
from collections import defaultdict


def load_crossed(path, part="part", operator="operator", value="value"):
    """Return data[part][operator] = [trials...] for a crossed study, checking it is balanced."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if not rows or not {part, operator, value} <= set(rows[0]):
        raise ValueError(f"CSV needs columns {part}, {operator}, {value}")
    data = defaultdict(lambda: defaultdict(list))
    for r in rows:
        data[r[part].strip()][r[operator].strip()].append(float(r[value]))
    parts, ops = list(data), sorted({o for p in data.values() for o in p})
    trials = {len(data[p][o]) for p in parts for o in ops}
    if len(trials) != 1 or 0 in trials:
        raise ValueError("unbalanced study: every operator must measure every part the same number of times")
    r = trials.pop()
    if len(parts) < 2 or len(ops) < 2 or r < 2:
        raise ValueError("need at least 2 parts, 2 operators and 2 trials (10 x 3 x 3 recommended)")
    return data, parts, ops, r


def verdict(pct_grr, ndc):
    if pct_grr < 10 and ndc >= 5:
        return "ACCEPTABLE"
    if pct_grr <= 30 and ndc >= 5:
        return "CONDITIONALLY ACCEPTABLE (depends on application, cost, customer approval)"
    return "NOT ACCEPTABLE"
