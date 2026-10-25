#!/usr/bin/env python3
"""Check report comments before they go home: wrong names, missing next steps, vague praise, jargon, length.

Input: Markdown with one "## Student name" heading per comment, the comment text below it.

Checks:
  RC001 high    another student's name appears in the comment (copy-paste error)
  RC002 medium  no next step (focus on, work on, next term, try to, should, target, aim)
  RC003 medium  only vague praise with no skill or example (good student, works hard, nice, keep it up)
  RC004 medium  no strength mentioned (only problems)
  RC005 low     teacher jargon parents may not know (CCQ, TL, TTT, L1, CEFR codes without words)
  RC006 low     shorter than 40 or longer than 150 words

Usage:
    python comment_check.py comments.md

Exit codes: 0 no high findings, 1 high findings, 2 read error or no comments.
"""

import argparse
import re
import sys

NEXT = re.compile(r"\b(focus on|work on|next (term|step|year)|try to|should|target|aim to|practi[sc]e|would benefit|"
                  r"encourage .* to|keep (reading|practising|practicing|working))\b", re.I)
VAGUE = re.compile(r"\b(good student|works hard|hard[- ]working|nice|keep it up|lovely|pleasure to teach|"
                   r"satisfactory|doing well|good job)\b", re.I)
SKILL = re.compile(r"\b(speak|listen|read|writ|grammar|vocabular|pronunciation|spelling|fluen|accura|essay|"
                   r"presentation|test|score|tense|sentence|word|conversation)", re.I)
STRENGTH = re.compile(r"\b(good|well|strong|improv|progress|confident|excellent|great|clear|accurate|fluent|enjoy|"
                      r"pleased|impressive|effort|better)\b", re.I)
JARGON = re.compile(r"\b(CCQs?|TL|TTT|STT|L1|L2|ICQs?|[ABC][12]\+?)\b")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comments")
    a = ap.parse_args()
    try:
        text = open(a.comments, encoding="utf-8").read()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    blocks = re.findall(r"^##\s+(.+?)\s*\n(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    if not blocks:
        print("error: no '## Name' sections found", file=sys.stderr)
        return 2
    names = [n.strip() for n, _ in blocks]
    firsts = {n: n.split()[0] for n in names}
    f = []
    for name, body in blocks:
        name, body = name.strip(), body.strip()
        n_words = len(body.split())
        for other in names:
            if other != name and firsts[other] != firsts[name] and re.search(rf"\b{re.escape(firsts[other])}\b", body):
                f.append(("RC001", "high", f"{name}: mentions {firsts[other]} - wrong name pasted?"))
        if not NEXT.search(body):
            f.append(("RC002", "medium", f"{name}: no next step"))
        if VAGUE.search(body) and not SKILL.search(body):
            f.append(("RC003", "medium", f"{name}: '{VAGUE.search(body).group(0)}' with no skill or example"))
        if not STRENGTH.search(body):
            f.append(("RC004", "medium", f"{name}: no strength mentioned"))
        jar = sorted({m.group(0) for m in JARGON.finditer(body)})
        if jar:
            f.append(("RC005", "low", f"{name}: jargon {', '.join(jar)} - explain in plain words"))
        if not 40 <= n_words <= 150:
            f.append(("RC006", "low", f"{name}: {n_words} words"))
    print(f"{len(blocks)} comments checked")
    order = {"high": 0, "medium": 1, "low": 2}
    for code, sev, msg in sorted(f, key=lambda x: (order[x[1]], x[0])):
        print(f"{code} [{sev}] {msg}")
    if not f:
        print("OK: personal, specific, balanced comments with next steps")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
