#!/usr/bin/env python3
"""Analyse a class error log: errors by category and student, persistent (possibly fossilised) errors, and the
correction strategy that suits each category.

CSV columns: student, date (YYYY-MM-DD), error, correction, category, pattern (optional, e.g. "3rd person -s")
Categories: grammar, vocabulary, pronunciation, spelling, word order, register, discourse (others are counted as given)

Errors are grouped by pattern when given, otherwise by the correction text. A pattern is persistent (possibly
fossilised) when the same student repeats it 3+ times on 2+ different dates.

Usage:
    python error_log.py errors.csv [--student Ana] [--top 5]

Exit codes: 0 printed, 2 read error or missing columns.
"""

import argparse
import csv
import sys
from collections import Counter, defaultdict

STRATEGY = {
    "grammar": "prompts (elicitation, metalinguistic clue, repetition) so the learner self-corrects; recasts alone are often not noticed",
    "vocabulary": "recast or elicitation, then record the word with collocations; recycle in later lessons",
    "pronunciation": "immediate modelling and drilling of the sound or stress; minimal pairs; recasts with emphasis",
    "spelling": "underline or code in written work; learner self-corrects; spelling rule or word family",
    "word order": "elicitation with finger technique (one finger per word) or reformulation on the board",
    "register": "delayed feedback with a formal/informal contrast; explain the effect on the reader or listener",
    "discourse": "delayed feedback on the whole text: model, reformulate, compare",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--student", help="show one student's profile")
    ap.add_argument("--top", type=int, default=5)
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        if not rows or not {"student", "error", "correction", "category"} <= set(rows[0]):
            raise ValueError("needs student, error, correction and category columns (date optional)")
    except (OSError, csv.Error, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if a.student:
        rows = [r for r in rows if r["student"].strip().lower() == a.student.lower()]
        if not rows:
            print(f"error: no errors logged for {a.student}", file=sys.stderr)
            return 2
    cats = Counter(r["category"].strip().lower() for r in rows)
    per = defaultdict(Counter)
    count, dates = Counter(), defaultdict(set)
    for i, r in enumerate(rows):
        r["_key"] = (r.get("pattern") or "").strip() or r["correction"].strip()
        key = (r["student"].strip(), r["_key"].lower(), r["category"].strip().lower())
        per[key[0]][key[2]] += 1
        count[key] += 1
        dates[key].add((r.get("date") or "").strip() or f"row {i}")
    print(f"{len(rows)} errors logged" + (f" for {a.student}" if a.student else f", {len(per)} students"))
    print("By category: " + ", ".join(f"{c} {n}" for c, n in cats.most_common()))
    common = Counter(r["_key"] for r in rows)
    print(f"\nMost frequent (class-wide) - top {a.top}:")
    for key, n in common.most_common(a.top):
        ex = next(r for r in rows if r["_key"] == key)
        print(f"  {n}x  {key}" + (f"  e.g. '{ex['error']}' -> '{ex['correction']}'" if key != ex["correction"].strip() else
                                 f"  e.g. '{ex['error']}'"))
    persistent = [(k, len(dates[k])) for k, n in count.items() if n >= 3 and len(dates[k]) >= 2]
    if persistent:
        print("\nPersistent errors (3+ times on 2+ dates) - plan targeted, explicit work:")
        for (s, corr, cat), d in sorted(persistent):
            print(f"  {s}: '{corr}' ({cat}), on {d} dates")
    if not a.student:
        print("\nBy student (top category):")
        for s, c in sorted(per.items()):
            cat, n = c.most_common(1)[0]
            print(f"  {s}: {sum(c.values())} errors, mostly {cat} ({n})")
    print("\nSuggested strategies:")
    for cat, _ in cats.most_common():
        print(f"  {cat}: {STRATEGY.get(cat, 'choose by stage: delayed in fluency work, immediate in accuracy work')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
