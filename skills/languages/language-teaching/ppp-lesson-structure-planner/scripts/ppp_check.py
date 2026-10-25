#!/usr/bin/env python3
"""Check a PPP target-language analysis: meaning, form, pronunciation, CCQs, context and practice tasks.

JSON:
  {
    "context": "Anna describes her childhood in a village",
    "items": [
      {"item": "used to + infinitive", "meaning": "past habit or state that is no longer true",
       "form": "subject + used to + base verb; negative didn't use to",
       "pronunciation": "/ˈjuːstə/ - weak form, no /d/ sound",
       "ccqs": ["Did Anna live in a village in the past? (yes)", "Does she live there now? (no)"]}
    ],
    "controlled": "Gap-fill: complete Anna's story with used to / didn't use to",
    "freer": "Pairs: tell your partner three things you used to do as a child"
  }

Checks:
  PP001 high    item without meaning, form or pronunciation analysis
  PP002 high    item with no CCQs
  PP003 medium  CCQ contains the target language itself (learners can answer by echoing it)
  PP004 medium  CCQ is 'Do you understand?' / 'Is that clear?' (tells you nothing)
  PP005 medium  no context for the presentation
  PP006 medium  no controlled practice, or no freer practice
  PP007 medium  'freer' task is still a controlled exercise (gap-fill, matching, drill)
  PP008 low     only one CCQ for an item
  PP009 low     pronunciation note has no stress, weak form or connected-speech detail

Usage:
    python ppp_check.py tla.json

Exit codes: 0 no high findings, 1 high findings, 2 read or JSON error.
"""

import argparse
import json
import re
import sys

USELESS = re.compile(r"\b(do you understand|is (that|it|everything) clear|any questions|ok\?|got it)", re.I)
CONTROLLED = re.compile(r"gap[- ]?fill|matching|match\b|drill|transformation|multiple choice|reorder|choose the correct", re.I)
PRON = re.compile(r"stress|weak|ə|schwa|linking|connected|intonation|elision|contraction|ˈ|●", re.I)
STOP = {"to", "a", "an", "the", "be", "+", "infinitive", "verb", "base", "ing", "-ing", "subject", "object"}


def tl_words(item):
    words = [w for w in re.findall(r"[a-z']+", item.lower()) if w not in STOP and len(w) > 1]
    return words[:3]


def check(t):
    f = []
    items = t.get("items") or []
    if not items:
        f.append(("PP001", "high", "no target language items"))
    for it in items:
        name = it.get("item", "?")
        missing = [k for k in ("meaning", "form", "pronunciation") if not it.get(k)]
        if missing:
            f.append(("PP001", "high", f"'{name}': no {', '.join(missing)}"))
        ccqs = it.get("ccqs") or []
        if not ccqs:
            f.append(("PP002", "high", f"'{name}': no concept-checking questions"))
        elif len(ccqs) == 1:
            f.append(("PP008", "low", f"'{name}': one CCQ; use 2-4 that check each part of the meaning"))
        words = tl_words(name)
        for q in ccqs:
            if USELESS.search(q):
                f.append(("PP004", "medium", f"'{q[:50]}' does not check meaning"))
            elif words and all(re.search(rf"\b{re.escape(w)}\b", q.split("(")[0], re.I) for w in words):
                f.append(("PP003", "medium", f"'{q[:50]}' repeats the target language '{name}'"))
        if it.get("pronunciation") and not PRON.search(it["pronunciation"]):
            f.append(("PP009", "low", f"'{name}': add stress, weak forms or connected speech"))
    if not t.get("context"):
        f.append(("PP005", "medium", "no context: present the language in a situation or text"))
    for k in ("controlled", "freer"):
        if not t.get(k):
            f.append(("PP006", "medium", f"no {k} practice task"))
    if t.get("freer") and CONTROLLED.search(t["freer"]):
        f.append(("PP007", "medium", f"freer task '{t['freer'][:50]}' is a controlled exercise"))
    return f


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tla", help="target language analysis JSON, or - for stdin")
    a = ap.parse_args()
    try:
        fh = sys.stdin if a.tla == "-" else open(a.tla, encoding="utf-8")
        with fh:
            t = json.load(fh)
        if not isinstance(t, dict):
            raise ValueError("JSON must be an object")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    f = check(t)
    print(f"{len(t.get('items') or [])} item(s), {len(f)} finding(s)")
    order = {"high": 0, "medium": 1, "low": 2}
    for code, sev, msg in sorted(f, key=lambda x: (order[x[1]], x[0])):
        print(f"{code} [{sev}] {msg}")
    if not f:
        print("OK: meaning, form, pronunciation, CCQs and practice are covered")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
