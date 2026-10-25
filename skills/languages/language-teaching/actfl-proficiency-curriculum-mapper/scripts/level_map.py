#!/usr/bin/env python3
"""Look up approximate equivalences between ACTFL, CEFR and ILR levels, with what each level can do.

Alignments are approximate (based on ACTFL's published CEFR alignment for its tests and common ILR practice) and
differ by skill; never use them to convert an individual's score for high-stakes decisions.

Usage:
    python level_map.py "Intermediate High"       # ACTFL sublevel (case-insensitive; IH, AL... also work)
    python level_map.py --cefr B2
    python level_map.py --ilr 2
    python level_map.py --table

Exit codes: 0 found, 2 unknown level.
"""

import argparse
import sys

# ACTFL, short, CEFR, ILR, functions, text type
ROWS = [
    ("Novice Low", "NL", "Pre-A1", "0", "Isolated words; no real functional ability", "Words"),
    ("Novice Mid", "NM", "Pre-A1", "0+", "Memorised words and phrases on familiar topics", "Words, lists, phrases"),
    ("Novice High", "NH", "A1", "0+", "Mostly memorised language, some recombination; simple personal information", "Phrases, some simple sentences"),
    ("Intermediate Low", "IL", "A2", "1", "Create with language; simple Q&A in predictable everyday situations", "Discrete sentences"),
    ("Intermediate Mid", "IM", "A2", "1", "Handle uncomplicated tasks and social situations; ask and answer questions", "Strings of sentences"),
    ("Intermediate High", "IH", "B1", "1+", "Narrate and describe in major time frames, but not consistently", "Connected sentences, emerging paragraphs"),
    ("Advanced Low", "AL", "B1", "2", "Narrate and describe in past, present and future; handle a complication", "Paragraphs"),
    ("Advanced Mid", "AM", "B2", "2", "Narrate and describe with control and detail across time frames", "Connected paragraphs"),
    ("Advanced High", "AH", "B2", "2+", "Perform Advanced tasks with ease; emerging Superior functions", "Extended paragraphs"),
    ("Superior", "S", "C1", "3", "Support opinions, hypothesise, discuss abstract topics", "Extended discourse"),
    ("Distinguished", "D", "C2", "4", "Tailor language to audience; persuade; cultural and historical references", "Extended, sophisticated discourse"),
]


def show(r):
    print(f"ACTFL {r[0]} ({r[1]})  ~  CEFR {r[2]}  ~  ILR {r[3]}")
    print(f"  Functions: {r[4]}")
    print(f"  Text type: {r[5]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("actfl", nargs="?", help="ACTFL level or abbreviation")
    ap.add_argument("--cefr", type=str.upper)
    ap.add_argument("--ilr")
    ap.add_argument("--table", action="store_true")
    a = ap.parse_args()
    if a.table:
        print("| ACTFL | CEFR | ILR | Text type |\n|-------|------|-----|-----------|")
        for r in ROWS:
            print(f"| {r[0]} | {r[2]} | {r[3]} | {r[5]} |")
        return 0
    if a.actfl:
        key = a.actfl.strip().lower()
        hits = [r for r in ROWS if key in (r[0].lower(), r[1].lower())]
    elif a.cefr:
        hits = [r for r in ROWS if r[2].upper() == a.cefr]
    elif a.ilr:
        hits = [r for r in ROWS if r[3] == a.ilr.strip()]
    else:
        ap.print_usage(sys.stderr)
        return 2
    if not hits:
        print("error: unknown level", file=sys.stderr)
        return 2
    for r in hits:
        show(r)
    print("\nApproximate alignment: varies by skill (reading and listening ratings align differently from speaking).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
