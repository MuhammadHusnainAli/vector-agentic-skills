#!/usr/bin/env python3
"""Make unique vocabulary bingo cards and a shuffled caller list.

The caller reads definitions, pictures or translations; learners cross out the matching word. Every card is a
different selection or arrangement. Use --free for a free centre square on 3x3 or 5x5 cards.

Usage:
    python bingo_cards.py --file words.txt --cards 20 --size 4
    python bingo_cards.py --words cat dog bird fish horse cow sheep goat duck --cards 6 --size 3 --free --seed 2

Exit codes: 0 printed, 2 too few words for the card size, or read error.
"""

import argparse
import random
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--words", nargs="*", default=[])
    ap.add_argument("--file", help="one word or phrase per line")
    ap.add_argument("--cards", type=int, default=10)
    ap.add_argument("--size", type=int, choices=[3, 4, 5], default=4)
    ap.add_argument("--free", action="store_true", help="free centre square (3x3 and 5x5 only)")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    words = list(a.words)
    if a.file:
        try:
            words += [l.strip() for l in open(a.file, encoding="utf-8") if l.strip() and not l.startswith("#")]
        except OSError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
    words = list(dict.fromkeys(words))
    free = a.free and a.size % 2 == 1
    need = a.size * a.size - (1 if free else 0)
    if len(words) < need:
        print(f"error: {a.size}x{a.size} cards need at least {need} different words, got {len(words)}", file=sys.stderr)
        return 2
    if len(words) == need:
        print(f"note: only {need} words, so cards differ in order only and everyone wins together; add more words",
              file=sys.stderr)
    rng = random.Random(a.seed)
    seen = set()
    for i in range(1, a.cards + 1):
        for _ in range(200):
            pick = rng.sample(words, need)
            if tuple(pick) not in seen:
                break
        seen.add(tuple(pick))
        if free:
            pick.insert(need // 2, "FREE")
        width = max(len(w) for w in pick)
        print(f"Card {i}")
        for r in range(a.size):
            print("| " + " | ".join(w.ljust(width) for w in pick[r * a.size:(r + 1) * a.size]) + " |")
        print()
    calls = words[:]
    rng.shuffle(calls)
    print("Caller list: " + ", ".join(calls))
    return 0


if __name__ == "__main__":
    sys.exit(main())
