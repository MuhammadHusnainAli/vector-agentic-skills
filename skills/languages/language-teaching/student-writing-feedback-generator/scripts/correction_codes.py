#!/usr/bin/env python3
"""Summarise a correction-coded learner text: errors by code, focus areas, marking density and a learner summary.

Mark errors in the learner's text with a code in square brackets right after the word or phrase:
    Yesterday I goed[T] to park[Art] with my freinds[Sp].
Codes (case-insensitive): Sp spelling, T tense, VF verb form, Agr agreement, WW wrong word, WF word form,
Art article, Prep preposition, WO word order, ^ missing word, X extra word, P punctuation, C capital letter,
Reg register, ? meaning unclear, // new sentence/paragraph needed.

Usage:
    python correction_codes.py coded.txt [--name Ana] [--clean]

--clean prints the text without codes (for the learner to correct in a redraft).

Exit codes: 0 printed, 1 unknown codes found, 2 read error or no codes.
"""

import argparse
import re
import sys
from collections import Counter

LABEL = {"sp": "Sp", "agr": "Agr", "art": "Art", "prep": "Prep", "reg": "Reg"}  # others print in capitals
KEY = {
    "sp": ("spelling", "check the spelling in a dictionary"),
    "t": ("tense", "think about when it happened"),
    "vf": ("verb form", "check the form of the verb (-ing, to, base form, past participle)"),
    "agr": ("agreement", "subject and verb must agree (he goes, they go)"),
    "ww": ("wrong word", "this word does not mean what you want; find a better one"),
    "wf": ("word form", "right word, wrong form (noun, verb, adjective, adverb)"),
    "art": ("article", "a, an, the or no article?"),
    "prep": ("preposition", "check the preposition (in, on, at, to...)"),
    "wo": ("word order", "change the order of the words"),
    "^": ("missing word", "something is missing here"),
    "x": ("extra word", "remove this word"),
    "p": ("punctuation", "check commas, full stops, apostrophes"),
    "c": ("capital letter", "use a capital (or small) letter"),
    "reg": ("register", "too formal or informal for this reader"),
    "?": ("unclear meaning", "I don't understand: say it another way"),
    "//": ("new sentence/paragraph", "start a new sentence or paragraph here"),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", help="coded text file, or - for stdin")
    ap.add_argument("--name", default="", help="learner's name for the summary")
    ap.add_argument("--clean", action="store_true", help="also print the text with codes removed")
    a = ap.parse_args()
    try:
        text = (sys.stdin if a.text == "-" else open(a.text, encoding="utf-8")).read()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    codes = [c.strip().lower() for c in re.findall(r"\[([^\]\s]{1,4})\]", text)]
    if not codes:
        print("error: no [codes] found", file=sys.stderr)
        return 2
    unknown = sorted({c for c in codes if c not in KEY})
    known = Counter(c for c in codes if c in KEY)
    clean = re.sub(r"\[[^\]\s]{1,4}\]", "", text)
    words = len(re.findall(r"[A-Za-z']+", clean))
    print(f"{sum(known.values())} coded errors in {words} words ({100 * sum(known.values()) / max(words, 1):.0f} per 100 words)")
    print("| Code | Area | Count |\n|------|------|-------|")
    for c, n in known.most_common():
        print(f"| {LABEL.get(c, c.upper())} | {KEY[c][0]} | {n} |")
    if sum(known.values()) > words / 8:
        print("\nNote: dense marking; code only the 2-3 most important patterns so the learner can act on them")
    focus = [c for c, _ in known.most_common(3)]
    who = f"{a.name}, " if a.name else ""
    summary = "; ".join(f"{KEY[c][0]} ({known[c]}) - {KEY[c][1]}" for c in focus)
    print(f"\nLearner summary: {who}your main areas to work on are {summary}" + ("" if summary.endswith("?") else "."))
    if unknown:
        print(f"\nUnknown codes: {', '.join(unknown)} (add them to the class code key)")
    if a.clean:
        print("\nText for redraft:\n" + clean.strip())
    return 1 if unknown else 0


if __name__ == "__main__":
    sys.exit(main())
