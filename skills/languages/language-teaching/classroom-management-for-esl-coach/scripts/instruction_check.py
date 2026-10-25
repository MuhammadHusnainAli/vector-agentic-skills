#!/usr/bin/env python3
"""Check a teacher's planned task instructions for a language class: length, graded language, demo, ICQs.

Input: the instructions as the teacher will say them, then ICQs as lines ending in '?' (answers in brackets).

Checks:
  IC001 medium  too long (over 40 words at A1-A2, over 60 at B1+)
  IC002 medium  no instruction-checking questions (ICQs)
  IC003 medium  ICQ that checks nothing ('Do you understand?', 'Is that clear?', 'OK?')
  IC004 medium  no demonstration or example
  IC005 low     sentence over 12 words at A1-A2 (over 18 at B1+)
  IC006 low     filler that adds words but no meaning ('what I'd like you to do is', 'basically', 'kind of')
  IC007 low     no grouping or no time limit stated

Usage:
    python instruction_check.py instructions.txt --level A2

Exit codes: 0 no findings above low, 1 medium findings, 2 read error or empty input.
"""

import argparse
import re
import sys

FILLER = re.compile(r"what (i'd|i would) like you to do is|so what we're going to do|basically|kind of|sort of|"
                    r"just|maybe you could|if you don't mind|i want you to try and", re.I)
USELESS = re.compile(r"\b(do you understand|is (that|it|everything) clear|ok\?|okay\?|any questions|got it)", re.I)
DEMO = re.compile(r"\b(demo|demonstrat|watch me|watch|example|for instance|like this|i'll do (one|the first)|"
                  r"let's do (one|the first)|model|show)", re.I)
GROUP = re.compile(r"\b(pairs?|partner|groups?|alone|individually|on your own|teams?|threes|fours)\b", re.I)
TIME = re.compile(r"\b(\d+|one|two|three|four|five|ten) (minutes?|mins?|seconds?)\b", re.I)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", help="instructions file, or - for stdin")
    ap.add_argument("--level", type=str.upper, default="B1", help="CEFR level of the class")
    a = ap.parse_args()
    try:
        lines = [l.strip() for l in (sys.stdin if a.text == "-" else open(a.text, encoding="utf-8")).read().splitlines() if l.strip()]
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not lines:
        print("error: no instructions", file=sys.stderr)
        return 2
    icqs = [l for l in lines if re.sub(r"\s*\(.*?\)\s*$", "", l).endswith("?")]
    instr = " ".join(l for l in lines if l not in icqs)
    low = a.level[:1] == "A"
    n = len(instr.split())
    f = []
    if n > (40 if low else 60):
        f.append(("IC001", "medium", f"{n} words of instructions; aim for under {40 if low else 60} at {a.level}"))
    real = [q for q in icqs if not USELESS.search(q)]
    for q in icqs:
        if USELESS.search(q):
            f.append(("IC003", "medium", f"'{q}' checks nothing: ask about the task ('Do you write or speak?')"))
    if not real:
        f.append(("IC002", "medium", "no ICQs: add 2-3 short questions about what learners will do"))
    if not DEMO.search(instr):
        f.append(("IC004", "medium", "no demonstration or example: show the first item"))
    limit = 12 if low else 18
    for s in re.split(r"(?<=[.!])\s+", instr):
        if len(s.split()) > limit:
            f.append(("IC005", "low", f"long sentence ({len(s.split())} words): '{s[:50]}...'"))
    fill = sorted({m.group(0).lower() for m in FILLER.finditer(instr)})
    if fill:
        f.append(("IC006", "low", "filler: " + ", ".join(fill)))
    if not GROUP.search(instr):
        f.append(("IC007", "low", "say who works with whom (alone, pairs, groups)"))
    if not TIME.search(instr):
        f.append(("IC007", "low", "say how long learners have"))
    print(f"{n} words of instructions, {len(icqs)} ICQ(s), level {a.level}")
    order = {"medium": 0, "low": 1}
    for code, sev, msg in sorted(f, key=lambda x: (order[x[1]], x[0])):
        print(f"{code} [{sev}] {msg}")
    if not f:
        print("OK: short, demonstrated and checked")
    return 1 if any(x[1] == "medium" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
