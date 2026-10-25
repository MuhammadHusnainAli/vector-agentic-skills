#!/usr/bin/env python3
"""Profile an L2 learner's text to support (not replace) rubric scoring: length, paragraphing, sentences,
linkers, lexical variety, repetition and register.

Checks:
  WP001 high    under the minimum word count (or over the maximum by more than 10%)
  WP002 medium  one paragraph for a text over 120 words
  WP003 medium  fewer than 3 different linking words in a text over 100 words
  WP004 low     one linker used 4+ times
  WP005 low     contractions or informal words in a --formal task
  WP006 low     content word repeated 5+ times (vary with synonyms or pronouns)

Usage:
    python essay_profile.py essay.txt --min 140 --max 190 [--formal]

Exit codes: 0 no high findings, 1 high findings, 2 read error or empty text.
"""

import argparse
import re
import statistics
import sys
from collections import Counter

LINKERS = ["and", "but", "because", "so", "also", "however", "although", "though", "therefore", "moreover",
           "furthermore", "in addition", "on the other hand", "for example", "for instance", "firstly", "secondly",
           "finally", "in conclusion", "to sum up", "as a result", "while", "whereas", "despite", "in spite of",
           "nevertheless", "then", "after that", "consequently", "besides", "such as", "overall", "instead"]
INFORMAL = re.compile(r"\b\w+'(m|re|s|t|ll|d|ve)\b|\b(gonna|wanna|kids|stuff|lots of|a lot of|guys|ok|okay|"
                      r"really|so much|pretty|awesome)\b", re.I)
STOP = set("the a an and or but of to in on at for with is are was were be been it this that these those i you he "
           "she we they my your his her our their me him us them not no do does did have has had will would can "
           "could should there so as by from if than then also very more most some any all".split())


def mattr(tokens, window=50):
    if len(tokens) < window:
        return len(set(tokens)) / max(1, len(tokens))
    return statistics.mean(len(set(tokens[i:i + window])) / window for i in range(len(tokens) - window + 1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", help="text file, or - for stdin")
    ap.add_argument("--min", type=int, default=0, help="minimum words for the task")
    ap.add_argument("--max", type=int, default=0, help="maximum words for the task")
    ap.add_argument("--formal", action="store_true", help="formal register expected (essay, report, formal letter)")
    a = ap.parse_args()
    try:
        text = (sys.stdin if a.text == "-" else open(a.text, encoding="utf-8")).read().strip()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    tokens = [t.lower() for t in re.findall(r"[A-Za-z][A-Za-z'-]*", text)]
    if not tokens:
        print("error: empty text", file=sys.stderr)
        return 2
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    sents = [s for s in re.split(r"(?<=[.!?])\s+", text) if re.search(r"[A-Za-z]", s)]
    lens = [len(re.findall(r"[A-Za-z][A-Za-z'-]*", s)) for s in sents]
    low = " " + " ".join(tokens) + " "
    used = Counter({l: low.count(f" {l} ") for l in LINKERS if f" {l} " in low})
    content = Counter(t for t in tokens if t not in STOP and len(t) > 3)
    n = len(tokens)
    limits = f"{a.min}-{a.max}" if a.min and a.max else f"min {a.min}" if a.min else f"max {a.max}"
    print(f"Words: {n}" + (f" (task {limits})" if a.min or a.max else ""))
    print(f"Paragraphs: {len(paras)}; sentences: {len(sents)}; mean sentence {statistics.mean(lens):.1f} words "
          f"(range {min(lens)}-{max(lens)})")
    print(f"Linkers ({len(used)} different): " + ", ".join(f"{k} x{v}" for k, v in used.most_common()))
    print(f"Lexical variety (MATTR, 50-word window): {mattr(tokens):.2f}")
    f = []
    if a.min and n < a.min:
        f.append(("WP001", "high", f"{n} words is under the minimum of {a.min}"))
    if a.max and n > a.max * 1.1:
        f.append(("WP001", "high", f"{n} words is more than 10% over the maximum of {a.max}"))
    if len(paras) == 1 and n > 120:
        f.append(("WP002", "medium", "one paragraph: organise into introduction, body paragraphs and conclusion"))
    if n > 100 and len(used) < 3:
        f.append(("WP003", "medium", f"only {len(used)} different linkers"))
    for l, c in used.items():
        if c >= 4 and l not in ("and",):
            f.append(("WP004", "low", f"'{l}' used {c} times"))
    if a.formal and INFORMAL.search(text):
        found = sorted({m.group(0).lower() for m in INFORMAL.finditer(text)})
        f.append(("WP005", "low", "informal for the task: " + ", ".join(found[:8])))
    for w, c in content.most_common(3):
        if c >= 5:
            f.append(("WP006", "low", f"'{w}' repeated {c} times"))
    order = {"high": 0, "medium": 1, "low": 2}
    for code, sev, msg in sorted(f, key=lambda x: (order[x[1]], x[0])):
        print(f"{code} [{sev}] {msg}")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
