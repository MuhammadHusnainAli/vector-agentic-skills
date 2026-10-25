#!/usr/bin/env python3
"""Make a gap-fill exercise from a text: numbered gaps, a shuffled word bank and an answer key.

Gap chosen target words (first occurrence of each, or every occurrence with --all), or make a cloze by gapping
every Nth word with --every. Distractors can be added to the word bank.

Usage:
    python gap_fill.py text.txt --words went saw bought "used to"
    python gap_fill.py text.txt --every 7 --skip-first 1 --no-bank
    python gap_fill.py text.txt --words went saw --distractors goed seen --hint --seed 3

Exit codes: 0 exercise printed, 1 a target word is not in the text, 2 read error or nothing to gap.
"""

import argparse
import random
import re
import sys


def gap_targets(text, words, every_occurrence):
    spans, missing = [], []
    for w in words:
        pat = re.compile(rf"(?<![\w'-]){re.escape(w)}(?![\w'-])", re.I)
        found = list(pat.finditer(text)) if every_occurrence else [m for m in [pat.search(text)] if m]
        if not found:
            missing.append(w)
        spans += [(m.start(), m.end()) for m in found]
    return sorted(spans), missing


def gap_every(text, n, skip_sentences):
    sentences = re.split(r"(?<=[.!?])\s+", text)
    start = len(" ".join(sentences[:skip_sentences])) if skip_sentences else 0
    words = [m for m in re.finditer(r"[A-Za-z][A-Za-z'-]*", text) if m.start() >= start]
    return [(m.start(), m.end()) for m in words[n - 1::n]]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", help="text file, or - for stdin")
    ap.add_argument("--words", nargs="*", default=[], help="words or phrases to gap")
    ap.add_argument("--all", action="store_true", help="gap every occurrence, not just the first")
    ap.add_argument("--every", type=int, help="cloze: gap every Nth word instead")
    ap.add_argument("--skip-first", type=int, default=1, help="cloze: leave the first N sentences intact (default 1)")
    ap.add_argument("--distractors", nargs="*", default=[], help="extra words for the bank")
    ap.add_argument("--no-bank", action="store_true", help="omit the word bank (harder)")
    ap.add_argument("--hint", action="store_true", help="show the first letter in each gap")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    try:
        text = (sys.stdin if a.text == "-" else open(a.text, encoding="utf-8")).read().strip()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if a.every:
        spans, missing = gap_every(text, a.every, a.skip_first), []
    else:
        spans, missing = gap_targets(text, a.words, a.all)
    if missing:
        print(f"error: not in the text: {', '.join(missing)}", file=sys.stderr)
        return 1
    if not spans:
        print("error: nothing to gap; give --words or --every", file=sys.stderr)
        return 2
    out, key, last = [], [], 0
    for i, (s, e) in enumerate(spans, 1):
        word = text[s:e]
        out.append(text[last:s] + f"({i}) " + (word[0] + "______" if a.hint else "________"))
        key.append(f"{i}. {word}")
        last = e
    out.append(text[last:])
    print("Complete the text" + (" with words from the box." if not a.no_bank else ".") + "\n")
    if not a.no_bank:
        bank = sorted({text[s:e].lower() for s, e in spans} | {d.lower() for d in a.distractors})
        random.Random(a.seed).shuffle(bank)
        print("[ " + " | ".join(bank) + " ]\n")
    print("".join(out))
    print("\nAnswer key\n" + "\n".join(key))
    return 0


if __name__ == "__main__":
    sys.exit(main())
