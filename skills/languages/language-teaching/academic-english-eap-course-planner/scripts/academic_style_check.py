#!/usr/bin/env python3
"""Check a learner's academic text for informal style, unhedged claims and missing citations, with alternatives.

Checks:
  AS001 medium  contractions (don't, it's, can't)
  AS002 medium  informal words or phrasal verbs, with a more academic alternative
  AS003 medium  absolute claims (always, never, prove, everyone) and no hedging anywhere in the text
  AS004 low     second person 'you' addressing the reader
  AS005 low     sentences starting with And / But / So
  AS006 low     rhetorical questions
  AS007 low     no citations found (author-date or numbered) in a text over 150 words

Usage:
    python academic_style_check.py essay.txt

Exit codes: 0 no medium findings, 1 medium findings, 2 read error or empty text.
"""

import argparse
import re
import sys

ALT = {
    "a lot of": "many / much / a considerable amount of", "lots of": "many / numerous", "get": "obtain / become / receive",
    "got": "obtained / became", "big": "large / substantial / significant", "really": "(omit) / considerably",
    "very": "(omit) / highly / particularly", "thing": "factor / aspect / issue", "things": "factors / aspects / issues",
    "stuff": "material / items", "kids": "children", "ok": "acceptable", "okay": "acceptable", "pretty": "fairly / rather",
    "find out": "discover / determine", "look into": "investigate / examine", "go up": "increase / rise",
    "go down": "decrease / decline", "cut down": "reduce", "set up": "establish", "deal with": "address / handle",
    "come up with": "propose / develop", "point out": "note / observe", "talk about": "discuss / examine",
    "nowadays": "currently / at present", "bad": "negative / harmful / poor", "good": "beneficial / effective / positive",
    "show up": "appear / emerge", "figure out": "determine / establish",
}
ABSOLUTE = re.compile(r"\b(always|never|everyone|everybody|nobody|all people|proves?|proved|certainly|undoubtedly|"
                      r"definitely|obvious(ly)?)\b", re.I)
HEDGE = re.compile(r"\b(may|might|could|suggests?|tends? to|appears?|seems?|likely|possibly|arguably|perhaps|"
                   r"to some extent|in many cases|indicates?)\b", re.I)
CITE = re.compile(r"\([A-Z][A-Za-z'-]+(?: et al\.)?(?: and [A-Z][A-Za-z'-]+)?,? \d{4}|[A-Z][A-Za-z'-]+ \(\d{4}\)|\[\d+\]")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", help="text file, or - for stdin")
    a = ap.parse_args()
    try:
        text = (sys.stdin if a.text == "-" else open(a.text, encoding="utf-8")).read()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    if not words:
        print("error: empty text", file=sys.stderr)
        return 2
    low = text.lower()
    f = []
    contractions = sorted({m.group(0).lower() for m in re.finditer(r"\b\w+n't\b|\b(it|that|there|he|she|they|we|i|you)'(s|re|ll|d|ve|m)\b", text, re.I)})
    if contractions:
        f.append(("AS001", "medium", "contractions: " + ", ".join(contractions)))
    informal = [(k, v) for k, v in ALT.items() if re.search(rf"\b{re.escape(k)}\b", low)]
    for k, v in informal:
        f.append(("AS002", "medium", f"'{k}' -> {v}"))
    absolutes = sorted({m.group(0).lower() for m in ABSOLUTE.finditer(text)})
    if absolutes and not HEDGE.search(text):
        f.append(("AS003", "medium", f"absolute claims ({', '.join(absolutes)}) and no hedging: use may, tend to, suggests, in many cases"))
    if re.search(r"\byou(r)?\b", low):
        f.append(("AS004", "low", "'you' addresses the reader: use impersonal forms (one, people, it is ...)"))
    starts = sorted({m.group(1) for m in re.finditer(r"(?:^|[.!?]\s+)(And|But|So)\b", text)})
    if starts:
        f.append(("AS005", "low", f"sentences start with {', '.join(starts)}: use However, Therefore, In addition"))
    if re.search(r"\?\s", text + " "):
        f.append(("AS006", "low", "rhetorical question(s): turn them into statements"))
    cites = len(CITE.findall(text))
    if len(words) > 150 and not cites:
        f.append(("AS007", "low", "no citations: support claims with sources (Author, year)"))
    print(f"{len(words)} words; hedges {len(HEDGE.findall(text))}; citations {cites}")
    order = {"medium": 0, "low": 1}
    for code, sev, msg in sorted(f, key=lambda x: (order[x[1]], x[0])):
        print(f"{code} [{sev}] {msg}")
    if not f:
        print("OK: formal, hedged and referenced")
    return 1 if any(x[1] == "medium" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
