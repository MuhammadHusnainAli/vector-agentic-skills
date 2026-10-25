#!/usr/bin/env python3
"""Build a quiz from a plain-text question bank: filter by topic and level, sample evenly across topics,
shuffle questions and MCQ options reproducibly, and print the quiz and an answer key with explanations.

Bank format: see references/bank-format.md (blocks starting "## topic | level | type").

Usage:
    python quiz_build.py bank.txt --n 10 --level A2 --seed 3
    python quiz_build.py bank.txt --topic "present perfect" --n 5 --no-key

Exit codes: 0 quiz printed, 1 fewer matching items than --n (prints what there is), 2 bank unreadable or empty.
"""

import argparse
import random
import re
import sys
from collections import defaultdict


def parse(text):
    items = []
    for block in re.split(r"\n\s*\n", text):
        lines = [l.rstrip() for l in block.strip().splitlines() if l.strip() and not re.match(r"^#(?!#)", l)]
        if not lines or not lines[0].startswith("## "):
            continue
        parts = [p.strip() for p in lines[0][3:].split("|")]
        item = {"topic": parts[0], "level": (parts[1] if len(parts) > 1 else "").upper(),
                "type": (parts[2] if len(parts) > 2 else "mcq").lower(), "options": [], "answer": "", "q": "", "e": ""}
        for l in lines[1:]:
            if l.startswith("Q:"):
                item["q"] = l[2:].strip()
            elif l.startswith("E:"):
                item["e"] = l[2:].strip()
            elif l.startswith("ANS:"):
                item["answer"] = l[4:].strip()
            elif re.match(r"^[A-H]\)", l):
                opt = l[2:].strip()
                item["options"].append((opt.rstrip("*").strip(), opt.endswith("*")))
        items.append(item)
    return items


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bank")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--level", type=str.upper)
    ap.add_argument("--topic", help="substring of the topic, e.g. 'past'")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--no-key", action="store_true")
    a = ap.parse_args()
    try:
        items = parse(open(a.bank, encoding="utf-8").read())
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not items:
        print("error: no items found; see references/bank-format.md", file=sys.stderr)
        return 2
    pool = [i for i in items if (not a.level or i["level"] == a.level) and (not a.topic or a.topic.lower() in i["topic"].lower())]
    rng = random.Random(a.seed)
    by = defaultdict(list)
    for i in pool:
        by[i["topic"]].append(i)
    for v in by.values():
        rng.shuffle(v)
    chosen, topics = [], sorted(by)
    while len(chosen) < a.n and any(by.values()):
        for t in topics:
            if by[t] and len(chosen) < a.n:
                chosen.append(by[t].pop())
    if not chosen:
        print("No items match --level / --topic.")
        return 1
    rng.shuffle(chosen)
    key = []
    letters = "ABCDEFGH"
    for n, it in enumerate(chosen, 1):
        print(f"{n}. {it['q']}" + ("  (True / False)" if it["type"] == "tf" else ""))
        if it["type"] == "mcq":
            opts = it["options"][:]
            rng.shuffle(opts)
            for j, (o, _) in enumerate(opts):
                print(f"   {letters[j]}) {o}")
            ans = next((f"{letters[j]}) {o}" for j, (o, ok) in enumerate(opts) if ok), "?")
        else:
            ans = it["answer"]
        key.append(f"{n}. {ans}" + (f" - {it['e']}" if it["e"] else ""))
        print()
    if not a.no_key:
        print("Answer key\n" + "\n".join(key))
    if len(chosen) < a.n:
        print(f"\nonly {len(chosen)} matching items for --n {a.n}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
