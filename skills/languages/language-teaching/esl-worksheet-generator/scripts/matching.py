#!/usr/bin/env python3
"""Make a matching exercise from pairs (word-definition, question-answer, sentence halves, collocations).

Input CSV/TSV with two columns (left,right); a header row is optional. Right-hand items are shuffled so none stays
opposite its partner, then lettered; an answer key follows.

Usage:
    python matching.py pairs.csv --title "Match the phrasal verbs to their meanings" --seed 2
    python matching.py halves.tsv --markdown

Exit codes: 0 exercise printed, 2 read error or fewer than 3 pairs.
"""

import argparse
import csv
import random
import string
import sys


def read_pairs(path):
    fh = sys.stdin if path == "-" else open(path, newline="", encoding="utf-8-sig")
    with fh:
        text = fh.read()
    dialect = csv.Sniffer().sniff(text.splitlines()[0], delimiters=",\t;") if text.strip() else csv.excel
    rows = [r for r in csv.reader(text.splitlines(), dialect) if len(r) >= 2 and r[0].strip()]
    if rows and rows[0][0].strip().lower() in {"left", "word", "term", "question", "first half", "phrase"}:
        rows = rows[1:]
    return [(r[0].strip(), r[1].strip()) for r in rows]


def derange(n, rng):
    order = list(range(n))
    while any(i == j for i, j in enumerate(order)):
        rng.shuffle(order)
    return order


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pairs", help="CSV/TSV file of pairs, or - for stdin")
    ap.add_argument("--title", default="Match 1-{n} with a-{last}.")
    ap.add_argument("--markdown", action="store_true", help="print as a two-column Markdown table")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    try:
        pairs = read_pairs(a.pairs)
    except (OSError, csv.Error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not 3 <= len(pairs) <= 26:
        print(f"error: need 3-26 pairs, got {len(pairs)}", file=sys.stderr)
        return 2
    order = derange(len(pairs), random.Random(a.seed))
    letters = string.ascii_lowercase
    right = [pairs[j][1] for j in order]
    print(a.title.format(n=len(pairs), last=letters[len(pairs) - 1]) + "\n")
    if a.markdown:
        print("| # | | Letter | |\n|---|---|---|---|")
        for i, (l, _) in enumerate(pairs):
            print(f"| {i + 1} | {l} | {letters[i]} | {right[i]} |")
    else:
        width = max(len(l) for l, _ in pairs) + 4
        for i, (l, _) in enumerate(pairs):
            print(f"{i + 1:>2}. {l:<{width}}{letters[i]}) {right[i]}")
    key = {j: letters[pos] for pos, j in enumerate(order)}
    print("\nAnswer key: " + "  ".join(f"{i + 1}-{key[i]}" for i in range(len(pairs))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
