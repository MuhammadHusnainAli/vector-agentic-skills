#!/usr/bin/env python3
"""Six Sigma Green Belt practice quiz: draw questions, grade answers, explain, and report weak domains.

Questions come from references/question-bank.md; options are shuffled per quiz. The same --seed and options
always draw the same quiz (same order, same option letters), so answers can be graded later.

Usage:
    python quiz.py --list
    python quiz.py --n 10 --seed 3                          # print a quiz (no answers)
    python quiz.py --n 10 --seed 3 --answers BCABDACBBA     # grade it
    python quiz.py --domain Measure --n 6 --seed 1 --answers-file my.txt
    python quiz.py --n 5 --seed 3 --key                     # answer key with explanations

Exit codes: 0 printed / passed (>= --pass-mark), 1 graded below the pass mark, 2 usage error.
"""

import argparse
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

BANK = Path(__file__).resolve().parent.parent / "references" / "question-bank.md"


def load():
    qs, cur = [], None
    for line in BANK.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^### (\S+) \| (\w+)$", line)
        if m:
            cur = {"id": m.group(1), "domain": m.group(2), "text": "", "opts": [], "answer": "", "why": ""}
            qs.append(cur)
        elif cur is None:
            continue
        elif re.match(r"^- [A-D]\) ", line):
            cur["opts"].append(line[2:])
        elif line.startswith("Answer:"):
            cur["answer"] = line.split(":", 1)[1].strip().upper()
        elif line.startswith("Why:"):
            cur["why"] = line.split(":", 1)[1].strip()
        elif line.strip() and not cur["opts"]:
            cur["text"] += (" " if cur["text"] else "") + line.strip()
    return qs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="list domains and question counts")
    ap.add_argument("--domain", help="draw only from one domain")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--answers", help="answers as letters in order, e.g. BCAD")
    ap.add_argument("--answers-file", help="file with one letter per line (or a single string)")
    ap.add_argument("--key", action="store_true", help="print the answer key with explanations")
    ap.add_argument("--pass-mark", type=float, default=0.7)
    a = ap.parse_args()
    qs = load()
    if a.list:
        for d, n in Counter(q["domain"] for q in qs).items():
            print(f"{d:<14}{n} questions")
        return 0
    pool = [q for q in qs if not a.domain or q["domain"].lower() == a.domain.lower()]
    if not pool:
        print(f"error: no questions for domain {a.domain!r} (see --list)", file=sys.stderr)
        return 2
    rng = random.Random(a.seed)
    quiz = rng.sample(pool, min(a.n, len(pool)))
    for q in quiz:   # shuffle options so the answer letter carries no pattern
        texts = [o[3:] for o in q["opts"]]
        right = texts["ABCD".index(q["answer"])]
        rng.shuffle(texts)
        q["opts"] = [f"{'ABCD'[i]}) {t}" for i, t in enumerate(texts)]
        q["answer"] = "ABCD"[texts.index(right)]
    answers = a.answers
    if a.answers_file:
        try:
            answers = "".join(Path(a.answers_file).read_text(encoding="utf-8").split())
        except OSError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
    if answers is None:
        for i, q in enumerate(quiz, 1):
            print(f"{i}. [{q['domain']}] {q['text']}")
            for o in q["opts"]:
                print(f"     {o}")
            if a.key:
                print(f"   Answer: {q['answer']} - {q['why']}")
            print()
        if not a.key:
            print(f"Grade with: python quiz.py --n {a.n} --seed {a.seed}" + (f" --domain {a.domain}" if a.domain else "") + " --answers <letters>")
        return 0
    answers = answers.strip().upper().replace(",", "")
    if len(answers) != len(quiz) or not set(answers) <= set("ABCD"):
        print(f"error: give {len(quiz)} answers using A-D", file=sys.stderr)
        return 2
    score, by = 0, defaultdict(lambda: [0, 0])
    for i, (q, ans) in enumerate(zip(quiz, answers), 1):
        ok = ans == q["answer"]
        score += ok
        by[q["domain"]][0] += ok
        by[q["domain"]][1] += 1
        if not ok:
            print(f"{i}. {q['id']} you answered {ans}, correct {q['answer']}: {q['why']}")
    pct = score / len(quiz)
    print(f"\nScore: {score}/{len(quiz)} = {pct:.0%}  ({'PASS' if pct >= a.pass_mark else 'below pass mark'} at {a.pass_mark:.0%})")
    print("By domain: " + ", ".join(f"{d} {c}/{n}" for d, (c, n) in by.items()))
    weak = [d for d, (c, n) in by.items() if c / n < a.pass_mark]
    if weak:
        print("Study next: " + ", ".join(weak) + " (see references/study-guide.md)")
    return 0 if pct >= a.pass_mark else 1


if __name__ == "__main__":
    sys.exit(main())
