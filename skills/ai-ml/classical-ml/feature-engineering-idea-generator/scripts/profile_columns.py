#!/usr/bin/env python3
"""Infer the semantic role of every column in a CSV: the starting point for feature ideas.

Roles:
  id            unique (or nearly) identifiers: never a raw feature
  entity_key    repeated identifiers (customer_id, card_id): group-by key for aggregate features
  year          calendar years (year_built): turn into age = reference year - value
  datetime      dates / timestamps (ISO, YYYY/MM/DD, with or without time, unix epoch s/ms)
  binary        two distinct values (flags)
  count         non-negative integers with repeats
  amount        non-negative continuous values, usually right-skewed (money, durations, sizes)
  continuous    other real-valued numbers
  percentage    proportions: values in [0, 1] or [0, 100] with a rate/share/score-like name
  categorical   low cardinality (<= 50 levels or <= 5% of rows)
  high_card     many levels but repeated (merchant, city, product): needs frequency/target encoding
  code          numeric-looking codes (zip, postcode, area/NAICS codes): categorical, not quantity
  geo_lat / geo_lon  latitude / longitude by name and range
  text          long free text (mean length >= 30 chars, many words)
  constant      a single value: drop

Usage:
    python profile_columns.py data.csv
    python profile_columns.py data.csv --target churned --json
    python profile_columns.py data.csv --sample 20000

Exit codes: 0 profiled, 2 read error.
"""

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter
from itertools import islice

MISSING = {"", "na", "n/a", "nan", "null", "none", "?"}
DATE_RE = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}([ T]\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$")
CODE_NAMES = re.compile(r"(zip|postcode|postal|area_code|naics|sic|icd|fips|_code$|^code$)", re.I)
ID_NAMES = re.compile(r"(^id$|_id$|^id_|uuid|guid|^key$|_key$)", re.I)
PCT_NAMES = re.compile(r"(pct|percent|ratio|rate|share|_frac|score|prob)", re.I)
YEAR_NAMES = re.compile(r"(year|yr)", re.I)
AMOUNT_NAMES = re.compile(r"(amount|price|cost|revenue|charge|spend|fee|salary|income|balance|value|total|duration|size|area|sqft|lot)", re.I)


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except ValueError:
        return None


def skew(xs):
    n = len(xs)
    if n < 3:
        return 0.0
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / n)
    return 0.0 if sd == 0 else sum(((x - m) / sd) ** 3 for x in xs) / n


def profile_column(name, values):
    n = len(values)
    present = [v.strip() for v in values if v.strip().lower() not in MISSING]
    info = {"column": name, "rows": n, "missing": round(1 - len(present) / n, 4) if n else 1.0}
    if not present:
        return {**info, "role": "constant", "distinct": 0, "note": "all missing"}
    counts = Counter(present)
    distinct = len(counts)
    info["distinct"] = distinct
    info["top"] = counts.most_common(1)[0][0][:30]
    nums = [num(v) for v in present]
    numeric = all(x is not None for x in nums)
    if distinct == 1:
        return {**info, "role": "constant"}
    if distinct == 2:
        return {**info, "role": "binary", "levels": sorted(counts)[:2]}
    if sum(bool(DATE_RE.match(v)) for v in present) / len(present) > 0.9:
        return {**info, "role": "datetime", "min": min(present), "max": max(present)}
    if numeric:
        xs = [x for x in nums if x is not None]
        lo, hi = min(xs), max(xs)
        info.update(min=lo, max=hi)
        integer = all(x.is_integer() for x in xs)
        lname = name.lower()
        if ("lat" in lname and -90 <= lo and hi <= 90) and "lon" not in lname:
            return {**info, "role": "geo_lat"}
        if (("lon" in lname or "lng" in lname) and -180 <= lo and hi <= 180):
            return {**info, "role": "geo_lon"}
        if re.search(r"(time|ts$|^ts|epoch|_at$|date)", lname) and (
                9.4e8 <= lo and hi <= 2.2e9 or 9.4e11 <= lo and hi <= 2.2e12):
            unit = "s" if hi <= 2.2e9 else "ms"
            return {**info, "role": "datetime", "note": f"unix epoch ({unit})"}
        if CODE_NAMES.search(name) and integer:
            return {**info, "role": "code", "note": "numeric-looking code: treat as categorical"}
        if ID_NAMES.search(name) and integer:
            return {**info, "role": "id" if distinct > 0.9 * len(xs) else "entity_key"}
        if YEAR_NAMES.search(name) and integer and 1800 <= lo and hi <= 2100:
            return {**info, "role": "year"}
        if PCT_NAMES.search(name) and lo >= 0 and (hi <= 1 or hi <= 100):
            return {**info, "role": "percentage"}
        sk = round(skew(xs), 3)
        info["skew"] = sk
        if integer and lo >= 0 and distinct <= 0.5 * len(xs) and not AMOUNT_NAMES.search(name):
            return {**info, "role": "count"}
        if lo >= 0 and (sk > 1 or AMOUNT_NAMES.search(name)):
            return {**info, "role": "amount"}
        return {**info, "role": "continuous"}
    if ID_NAMES.search(name) and distinct <= 0.5 * len(present):
        return {**info, "role": "entity_key", "rows_per_key": round(len(present) / distinct, 1)}
    if ID_NAMES.search(name) or distinct > 0.95 * len(present):
        mean_len = sum(len(v) for v in present) / len(present)
        words = sum(len(v.split()) for v in present) / len(present)
        if mean_len >= 30 and words >= 4:
            return {**info, "role": "text", "mean_len": round(mean_len, 1)}
        return {**info, "role": "id"}
    mean_len = sum(len(v) for v in present) / len(present)
    if mean_len >= 30 and sum(len(v.split()) for v in present) / len(present) >= 4:
        return {**info, "role": "text", "mean_len": round(mean_len, 1)}
    if distinct <= 50 or distinct <= 0.05 * len(present):
        rare = sum(1 for c in counts.values() if c < max(5, 0.005 * len(present)))
        return {**info, "role": "categorical", "rare_levels": rare}
    return {**info, "role": "high_card", "singletons": sum(1 for c in counts.values() if c == 1)}


def profile(path, sample=None):
    fh = sys.stdin if path == "-" else open(path, newline="", encoding="utf-8-sig")
    reader = csv.DictReader(fh)
    header = reader.fieldnames or []
    rows = list(islice(reader, sample)) if sample else list(reader)
    return header, rows, [profile_column(c, [r.get(c) or "" for r in rows]) for c in header]


def main():
    ap = argparse.ArgumentParser(description="Infer semantic column roles for feature engineering.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--target", help="mark this column as the target")
    ap.add_argument("--sample", type=int, help="profile only the first N rows")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        _, rows, prof = profile(a.csv, a.sample)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for p in prof:
        if p["column"] == a.target:
            p["role"] = "target"
    if a.json:
        print(json.dumps(prof, indent=2))
        return 0
    print(f"{len(rows)} rows, {len(prof)} columns")
    print(f"{'column':<24} {'role':<12} {'distinct':>8} {'missing':>8}  notes")
    for p in prof:
        notes = []
        for k in ("min", "max", "skew", "rare_levels", "singletons", "note", "mean_len"):
            if k in p:
                v = p[k]
                notes.append(f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}")
        print(f"{p['column']:<24} {p['role']:<12} {p['distinct']:>8} {p['missing']:>8.1%}  {' '.join(notes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
