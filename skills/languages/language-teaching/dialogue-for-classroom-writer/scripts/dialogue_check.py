#!/usr/bin/env python3
"""Check a classroom dialogue: target language used, role balance, turn length for the level, natural features.

Dialogue format: one turn per line, "Speaker: words". Lines without a speaker are ignored (stage directions).

Checks:
  DC001 high    target phrase not used (--target)
  DC002 high    fewer than two speakers
  DC003 medium  one speaker has more than 65% of the words: roles are unequal for pair practice
  DC004 medium  turn longer than the level allows (A1 12, A2 18, B1 25, B2 35, C1-C2 50 words)
  DC005 low     no contractions although full forms are used (I am, do not): sounds written, not spoken
  DC006 low     no natural spoken features (oh, well, really?, right, so, OK, great, sorry?, hmm)
  DC007 low     dialogue length outside the guide for the level

Usage:
    python dialogue_check.py dialogue.txt --level A2 --target "Can I have" "How much is"

Exit codes: 0 no high findings, 1 high findings, 2 read error.
"""

import argparse
import re
import sys
from collections import Counter

MAX_TURN = {"A1": 12, "A2": 18, "B1": 25, "B2": 35, "C1": 50, "C2": 50}
TURNS = {"A1": (6, 10), "A2": (8, 14), "B1": (10, 18), "B2": (10, 24), "C1": (10, 30), "C2": (10, 30)}
FULL = re.compile(r"\b(I am|(?<!here )you are|we are|they are|it is|that is|do not|does not|did not|can not|cannot|"
                  r"will not|I have got|I would|I will|is not|are not|was not)\b", re.I)
CONTRACTION = re.compile(r"\b\w+'(m|re|s|t|ll|d|ve)\b", re.I)
NATURAL = re.compile(r"\b(oh|well|really|right|so|ok|okay|great|sorry|hmm|um|er|actually|anyway|you know|"
                     r"I mean|let me see|sure|no problem|cool|wow)\b", re.I)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dialogue", help="text file, or - for stdin")
    ap.add_argument("--level", type=str.upper, choices=MAX_TURN, default="B1")
    ap.add_argument("--target", nargs="*", default=[], help="phrases the dialogue must contain")
    a = ap.parse_args()
    try:
        lines = (sys.stdin if a.dialogue == "-" else open(a.dialogue, encoding="utf-8")).read().splitlines()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    turns = []
    for n, l in enumerate(lines, 1):
        m = re.match(r"^\s*([A-Z][\w .'-]{0,20}):\s*(.+)$", l)
        if m:
            turns.append((n, m.group(1).strip(), m.group(2).strip()))
    f, words = [], Counter()
    for n, who, said in turns:
        k = len(re.findall(r"[A-Za-z0-9']+", said))
        words[who] += k
        if k > MAX_TURN[a.level]:
            f.append(("DC004", "medium", f"line {n}: {who} speaks {k} words in one turn (max {MAX_TURN[a.level]} at {a.level})"))
    text = " ".join(t[2] for t in turns)
    print(f"{len(turns)} turns; " + ", ".join(f"{w}: {c} words" for w, c in words.items()))
    for t in a.target:
        hit = [n for n, _, said in turns if t.lower() in said.lower()]
        print(f"  target '{t}': " + (f"line {', '.join(map(str, hit))}" if hit else "MISSING"))
        if not hit:
            f.append(("DC001", "high", f"target phrase '{t}' is not in the dialogue"))
    if len(words) < 2:
        f.append(("DC002", "high", "needs at least two speakers ('Name: text' on each line)"))
    elif max(words.values()) > 0.65 * sum(words.values()):
        top = words.most_common(1)[0]
        f.append(("DC003", "medium", f"{top[0]} has {100 * top[1] / sum(words.values()):.0f}% of the words; balance the roles"))
    if FULL.search(text) and not CONTRACTION.search(text):
        f.append(("DC005", "low", f"full forms like '{FULL.search(text).group(0)}' and no contractions: use I'm, don't, it's"))
    if turns and not NATURAL.search(text):
        f.append(("DC006", "low", "no reactions or fillers (Oh, Really?, Well, Right, Great): add a few"))
    lo, hi = TURNS[a.level]
    if turns and not lo <= len(turns) <= hi:
        f.append(("DC007", "low", f"{len(turns)} turns; {lo}-{hi} suits {a.level}"))
    order = {"high": 0, "medium": 1, "low": 2}
    for code, sev, msg in sorted(f, key=lambda x: (order[x[1]], x[0])):
        print(f"{code} [{sev}] {msg}")
    if not f:
        print("OK: target language present, balanced, natural and level-appropriate")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
