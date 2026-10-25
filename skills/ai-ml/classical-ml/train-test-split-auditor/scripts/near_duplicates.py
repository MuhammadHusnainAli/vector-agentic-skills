#!/usr/bin/env python3
"""Find near-duplicate rows between train and test (or inside one file) that exact matching misses.

Two detectors:
  fuzzy rows   numeric columns rounded to --decimals significant digits, text lower-cased and stripped,
               then matched exactly on the resulting key (catches re-exports, float noise, case changes)
  text         --text-col with character shingles (--shingle) and MinHash + LSH banding: pairs with
               estimated Jaccard similarity >= --threshold (catches edited copies of tickets, reviews,
               descriptions, product titles)
Reports the number of test rows with a near-duplicate in train and example pairs. Near duplicates
across the split make test scores optimistic, exactly like exact duplicates.

Usage:
    python near_duplicates.py train.csv test.csv --drop id label --decimals 3
    python near_duplicates.py train.csv test.csv --text-col body --threshold 0.8
    python near_duplicates.py data.csv --text-col title --threshold 0.9      # duplicates inside one file

Exit codes: 0 none found, 1 near-duplicates found, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import random
import re
import sys
import zlib
from collections import defaultdict


def read(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rd = csv.DictReader(fh)
        return rd.fieldnames or [], list(rd)


def norm_value(v, decimals):
    v = (v or "").strip()
    try:
        x = float(v)
        if math.isfinite(x):
            return f"{x:.{decimals}g}"
    except ValueError:
        pass
    return re.sub(r"\s+", " ", v.lower())


def shingles(text, k):
    t = re.sub(r"\s+", " ", (text or "").lower()).strip()
    return {t[i:i + k] for i in range(max(1, len(t) - k + 1))} if t else set()


def minhash(sh, seeds):
    hs = [zlib.crc32(s.encode()) for s in sh]
    return [min(((h ^ a) * b + a) & 0xFFFFFFFF for h in hs) if hs else 0 for a, b in seeds]


def main():
    ap = argparse.ArgumentParser(description="Near-duplicate rows across a split.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("train")
    ap.add_argument("test", nargs="?")
    ap.add_argument("--drop", nargs="*", default=[])
    ap.add_argument("--decimals", type=int, default=3, help="significant digits for numeric rounding")
    ap.add_argument("--text-col")
    ap.add_argument("--threshold", type=float, default=0.8)
    ap.add_argument("--shingle", type=int, default=5)
    ap.add_argument("--perms", type=int, default=64)
    ap.add_argument("--examples", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        h1, tr = read(a.train)
        h2, te = read(a.test) if a.test else (h1, tr)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    same = a.test is None
    cols = [c for c in h1 if c in h2 and c not in a.drop and c != a.text_col]
    if a.text_col and (a.text_col not in h1 or a.text_col not in h2):
        print(f"error: text column {a.text_col!r} missing", file=sys.stderr)
        return 2
    out = {"train_rows": len(tr), "test_rows": len(te), "within_one_file": same}
    keys = defaultdict(list)
    for i, r in enumerate(tr):
        keys[tuple(norm_value(r.get(c), a.decimals) for c in cols)].append(i)
    fuzzy = []
    for j, r in enumerate(te):
        k = tuple(norm_value(r.get(c), a.decimals) for c in cols)
        matches = [i for i in keys.get(k, []) if not (same and i >= j)]
        if matches:
            fuzzy.append((j, matches[0]))
    out["fuzzy_row_matches"] = len(fuzzy)
    text_pairs = []
    if a.text_col:
        rng = random.Random(0)
        seeds = [(rng.getrandbits(32) | 1, rng.getrandbits(32) | 1) for _ in range(a.perms)]
        bands = 16 if a.perms >= 64 else 8
        rows_per = a.perms // bands
        sig_tr = [(shingles(r[a.text_col], a.shingle)) for r in tr]
        mh_tr = [minhash(s, seeds) for s in sig_tr]
        buckets = defaultdict(list)
        for i, m in enumerate(mh_tr):
            for b in range(bands):
                buckets[(b, tuple(m[b * rows_per:(b + 1) * rows_per]))].append(i)
        for j, r in enumerate(te):
            sj = shingles(r[a.text_col], a.shingle)
            mj = minhash(sj, seeds)
            cand = set()
            for b in range(bands):
                cand.update(buckets.get((b, tuple(mj[b * rows_per:(b + 1) * rows_per])), []))
            best = None
            for i in cand:
                if same and i >= j:
                    continue
                inter = len(sj & sig_tr[i])
                union = len(sj | sig_tr[i]) or 1
                jac = inter / union
                if jac >= a.threshold and (best is None or jac > best[1]):
                    best = (i, jac)
            if best:
                text_pairs.append((j, best[0], best[1]))
        out["text_matches"] = len(text_pairs)
    affected = {j for j, _ in fuzzy} | {j for j, _, _ in text_pairs}
    out["test_rows_with_near_duplicate"] = len(affected)
    out["share"] = len(affected) / max(1, len(te))
    ex = []
    for j, i in fuzzy[:a.examples]:
        ex.append({"kind": "fuzzy-row", "test_line": j + 2, "train_line": i + 2})
    for j, i, s in sorted(text_pairs, key=lambda t: -t[2])[:a.examples]:
        ex.append({"kind": "text", "test_line": j + 2, "train_line": i + 2, "jaccard": round(s, 3),
                   "test_text": te[j][a.text_col][:80], "train_text": tr[i][a.text_col][:80]})
    out["examples"] = ex
    if a.json:
        print(json.dumps(out, indent=2))
        return 1 if affected else 0
    where = "inside the file" if same else "test rows with a near-duplicate in train"
    print(f"{len(affected)} {where} ({out['share']:.1%}): {len(fuzzy)} fuzzy-row matches"
          + (f", {len(text_pairs)} text matches (Jaccard >= {a.threshold:g})" if a.text_col else ""))
    for e in ex:
        if e["kind"] == "text":
            print(f"  text  line {e['test_line']} ~ line {e['train_line']} (J={e['jaccard']}): "
                  f"{e['test_text']!r} ~ {e['train_text']!r}")
        else:
            print(f"  row   line {e['test_line']} ~ line {e['train_line']}")
    if affected:
        print("Group near-duplicates together (one group id per cluster) and split by group, or deduplicate.")
    return 1 if affected else 0


if __name__ == "__main__":
    sys.exit(main())
