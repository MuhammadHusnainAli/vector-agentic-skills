#!/usr/bin/env python3
"""Classify a set of reading (or listening) comprehension questions and check their order and balance.

One question per line (numbering optional). Types are detected from wording; tag a line with [gist], [detail],
[inference], [vocab], [response] or [tf] to override.

Checks:
  RQ001 high    no gist / main-idea task
  RQ002 medium  gist task is not first (learners should read for the overall idea before detail)
  RQ003 medium  no inference or evaluation question at B1 or above (--level)
  RQ004 medium  true/false items with only one kind of answer when a key is given (all T or all F)
  RQ005 low     no personal response / post-reading question
  RQ006 low     yes/no questions answerable without reading (start with Do/Is/Are and no text reference)

Usage:
    python question_mix.py questions.txt --level B1 [--key T F T T]

Exit codes: 0 no high findings, 1 high findings, 2 read error or no questions.
"""

import argparse
import re
import sys

PATTERNS = [
    ("gist", r"main (idea|point|purpose)|best title|mainly about|summar|gist|what is the (text|article|story) about|choose the (best )?heading"),
    ("vocab", r"what does .+ mean|meaning of|word in (line|paragraph)|find a word|closest in meaning|refer to"),
    ("inference", r"why do you think|suggest|impl(y|ies)|infer|probably|most likely|how does the (writer|author)|attitude|tone|feel about|what can we (learn|conclude)"),
    ("response", r"\b(do|would|have) you\b|your (opinion|own|country|life|view)|agree with|in your"),
    ("tf", r"\b(t\s*/\s*f|true or false|true/false|\(t\)|\(f\)|not given)\b"),
]
YESNO = re.compile(r"^(do|does|did|is|are|was|were|can|has|have)\b", re.I)
TEXT_REF = re.compile(r"\b(text|article|story|writer|author|paragraph|line|according)\b", re.I)


def classify(q):
    tag = re.search(r"\[(gist|detail|inference|vocab|response|tf)\]", q, re.I)
    if tag:
        return tag.group(1).lower()
    for kind, pat in PATTERNS:
        if re.search(pat, q, re.I):
            return kind
    return "detail"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("questions", help="text file, one question per line, or - for stdin")
    ap.add_argument("--level", type=str.upper, default="B1", help="CEFR level of the class (default B1)")
    ap.add_argument("--key", nargs="*", default=[], help="answers for the T/F items, in order (T, F, NG)")
    a = ap.parse_args()
    try:
        lines = (sys.stdin if a.questions == "-" else open(a.questions, encoding="utf-8")).read().splitlines()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    qs = [re.sub(r"^\s*(\d+[.)]|[-*])\s*", "", l).strip() for l in lines if l.strip()]
    if not qs:
        print("error: no questions", file=sys.stderr)
        return 2
    kinds = [classify(q) for q in qs]
    f = []
    if "gist" not in kinds:
        f.append(("RQ001", "high", "no gist task: add a main-idea, title or summary question first"))
    elif kinds[0] != "gist":
        f.append(("RQ002", "medium", f"gist question is number {kinds.index('gist') + 1}; move it first"))
    if a.level[:1] in "BC" and not {"inference", "response"} & set(kinds):
        f.append(("RQ003", "medium", f"no inference or evaluation question for {a.level}"))
    key = {k.upper() for k in a.key}
    if kinds.count("tf") >= 3 and len(key) == 1:
        f.append(("RQ004", "medium", f"all true/false answers are {key.pop()}: mix true, false (and not given)"))
    if "response" not in kinds:
        f.append(("RQ005", "low", "no personal response question to finish"))
    for i, q in enumerate(qs, 1):
        if kinds[i - 1] == "detail" and YESNO.match(q) and not TEXT_REF.search(q):
            f.append(("RQ006", "low", f"Q{i} '{q[:50]}' is yes/no: learners can guess; ask wh- or quote the text"))
    print(f"{len(qs)} questions: " + ", ".join(f"{k} {kinds.count(k)}" for k in
                                              ("gist", "detail", "inference", "vocab", "tf", "response") if k in kinds))
    print("Order: " + " -> ".join(kinds))
    order = {"high": 0, "medium": 1, "low": 2}
    for code, sev, msg in sorted(f, key=lambda x: (order[x[1]], x[0])):
        print(f"{code} [{sev}] {msg}")
    if not f:
        print("OK: gist first, a range of question types, and a personal response")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
