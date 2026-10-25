#!/usr/bin/env python3
"""Build a word search from a vocabulary list, with a solution grid.

Difficulty sets the directions: easy (right, down), medium (+ diagonal down), hard (+ backwards and up).
Spaces and hyphens in phrases are removed (look after -> LOOKAFTER). Reproducible with --seed.

Usage:
    python wordsearch.py --words kitchen bedroom garden sofa lamp
    python wordsearch.py --file words.txt --size 12 --level hard --seed 4

Exit codes: 0 printed, 1 a word could not be placed (raise --size), 2 no words or a word longer than the grid.
"""

import argparse
import random
import re
import string
import sys

DIRS = {"easy": [(0, 1), (1, 0)], "medium": [(0, 1), (1, 0), (1, 1)],
        "hard": [(0, 1), (1, 0), (1, 1), (0, -1), (-1, 0), (-1, -1), (1, -1), (-1, 1)]}


def place(grid, word, dirs, rng, tries=400):
    n = len(grid)
    for _ in range(tries):
        dr, dc = rng.choice(dirs)
        r, c = rng.randrange(n), rng.randrange(n)
        cells = [(r + dr * i, c + dc * i) for i in range(len(word))]
        if all(0 <= y < n and 0 <= x < n and grid[y][x] in (None, ch) for (y, x), ch in zip(cells, word)):
            for (y, x), ch in zip(cells, word):
                grid[y][x] = ch
            return cells[0], (dr, dc)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--words", nargs="*", default=[])
    ap.add_argument("--file", help="one word or phrase per line")
    ap.add_argument("--size", type=int, help="grid size (default: longest word + 3, at least 10)")
    ap.add_argument("--level", choices=DIRS, default="medium")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    words = list(a.words)
    if a.file:
        try:
            words += [l.strip() for l in open(a.file, encoding="utf-8") if l.strip() and not l.startswith("#")]
        except OSError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
    clean = [re.sub(r"[^A-Za-z]", "", w).upper() for w in words]
    clean = [w for w in clean if w]
    if not clean:
        print("error: give --words or --file", file=sys.stderr)
        return 2
    n = a.size or max(10, max(map(len, clean)) + 3)
    if max(map(len, clean)) > n:
        print(f"error: '{max(clean, key=len)}' is longer than the {n}x{n} grid", file=sys.stderr)
        return 2
    rng = random.Random(a.seed)
    grid = [[None] * n for _ in range(n)]
    found = {}
    for w in sorted(set(clean), key=len, reverse=True):
        spot = place(grid, w, DIRS[a.level], rng)
        if not spot:
            print(f"error: could not place {w}; use a larger --size", file=sys.stderr)
            return 1
        found[w] = spot
    solution = [[ch or "." for ch in row] for row in grid]
    for row in grid:
        for i, ch in enumerate(row):
            row[i] = ch or rng.choice(string.ascii_uppercase)
    print(f"Find {len(found)} words ({a.level}).\n")
    print("\n".join(" ".join(row) for row in grid))
    print("\nWords: " + ", ".join(sorted(w.lower() for w in words if re.sub(r"[^A-Za-z]", "", w))))
    print("\nSolution\n" + "\n".join(" ".join(row) for row in solution))
    names = {(0, 1): "right", (1, 0): "down", (1, 1): "down-right", (0, -1): "left", (-1, 0): "up",
             (-1, -1): "up-left", (1, -1): "down-left", (-1, 1): "up-right"}
    print("\n" + "; ".join(f"{w} row {r + 1} col {c + 1} {names[d]}" for w, ((r, c), d) in sorted(found.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
