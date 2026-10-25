#!/usr/bin/env python3
"""Check a plain-text question bank (references/bank-format.md) for item-writing flaws.

Checks:
  QC001 high    MCQ with no correct option or more than one marked *
  QC002 high    gap or true/false item without ANS (tf must be T or F)
  QC003 medium  MCQ with fewer than 3 options, or duplicate options
  QC004 medium  'all of the above' / 'none of the above' option
  QC005 medium  correct option much longer than the distractors (test-wise learners pick it)
  QC006 low     gap item whose stem has no ___ blank
  QC007 low     negative stem (NOT, EXCEPT) not in capitals
  QC008 low     no explanation (E:)

Prints counts by topic, level and type.

Usage:
    python quiz_check.py bank.txt

Exit codes: 0 no high findings, 1 high findings, 2 read error or no items.
"""

import argparse
import re
import sys
from collections import Counter


def parse(text):
    items = []
    for block in re.split(r"\n\s*\n", text):
        lines = [l.rstrip() for l in block.strip().splitlines() if l.strip() and not re.match(r"^#(?!#)", l)]
        if not lines or not lines[0].startswith("## "):
            continue
        parts = [p.strip() for p in lines[0][3:].split("|")]
        it = {"head": lines[0][3:], "topic": parts[0], "level": parts[1].upper() if len(parts) > 1 else "",
              "type": parts[2].lower() if len(parts) > 2 else "mcq", "opts": [], "ans": None, "q": "", "e": ""}
        for l in lines[1:]:
            if l.startswith("Q:"):
                it["q"] = l[2:].strip()
            elif l.startswith("E:"):
                it["e"] = l[2:].strip()
            elif l.startswith("ANS:"):
                it["ans"] = l[4:].strip()
            elif re.match(r"^[A-H]\)", l):
                o = l[2:].strip()
                it["opts"].append((o.rstrip("*").strip(), o.endswith("*")))
        items.append(it)
    return items


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bank")
    a = ap.parse_args()
    try:
        items = parse(open(a.bank, encoding="utf-8").read())
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not items:
        print("error: no items found", file=sys.stderr)
        return 2
    f = []
    for n, it in enumerate(items, 1):
        tag = f"item {n} ({it['topic']})"
        if it["type"] == "mcq":
            keys = [o for o, ok in it["opts"] if ok]
            if len(keys) != 1:
                f.append(("QC001", "high", f"{tag}: {len(keys)} options marked correct"))
            texts = [o.lower() for o, _ in it["opts"]]
            if len(texts) < 3 or len(set(texts)) != len(texts):
                f.append(("QC003", "medium", f"{tag}: needs 3+ different options"))
            if any(re.search(r"(all|none) of the above", t) for t in texts):
                f.append(("QC004", "medium", f"{tag}: avoid 'all/none of the above'"))
            others = [len(o) for o, ok in it["opts"] if not ok]
            if len(keys) == 1 and others and len(keys[0]) > 1.75 * (sum(others) / len(others)) and len(keys[0]) > 12:
                f.append(("QC005", "medium", f"{tag}: correct option is much longer than the distractors"))
        elif it["type"] in ("gap", "tf"):
            if not it["ans"] or (it["type"] == "tf" and it["ans"].upper() not in ("T", "F")):
                f.append(("QC002", "high", f"{tag}: missing or invalid ANS"))
            if it["type"] == "gap" and "___" not in it["q"]:
                f.append(("QC006", "low", f"{tag}: no ___ in the stem"))
        if re.search(r"\b(which|what)\b.*\b(not|except)\b", it["q"], re.I) and not re.search(r"\b(NOT|EXCEPT)\b", it["q"]):
            f.append(("QC007", "low", f"{tag}: write NOT / EXCEPT in capitals"))
        if not it["e"]:
            f.append(("QC008", "low", f"{tag}: add an explanation for the answer key"))
    print(f"{len(items)} items")
    print("By type: " + ", ".join(f"{k} {v}" for k, v in Counter(i["type"] for i in items).most_common()))
    print("By level: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(i["level"] for i in items).items())))
    print("By topic: " + ", ".join(f"{k} {v}" for k, v in Counter(i["topic"] for i in items).most_common()))
    order = {"high": 0, "medium": 1, "low": 2}
    for code, sev, msg in sorted(f, key=lambda x: (order[x[1]], x[0])):
        print(f"{code} [{sev}] {msg}")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
