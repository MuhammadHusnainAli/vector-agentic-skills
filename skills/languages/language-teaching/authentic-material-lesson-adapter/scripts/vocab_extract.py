#!/usr/bin/env python3
"""Find what to pre-teach, gloss or ignore in an authentic text, and how long it takes to read.

Words outside the high-frequency list (references/high-frequency-words.txt) are ranked: words that repeat, appear
in the first sentence/title, or are needed for the task (--task-words) are pre-teach candidates (max --max, default
6); the rest are split into "gloss" (appear once but matter) and "ignore" (learners can skip them for the task).
Capitalised phrases are listed as names and cultural references to check.

Usage:
    python vocab_extract.py article.txt --level B1
    python vocab_extract.py menu.txt --level A2 --task-words vegetarian dessert --max 5

Exit codes: 0 printed, 2 read error or empty text.
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

WPM = {"A1": 60, "A2": 80, "B1": 110, "B2": 140, "C1": 170, "C2": 200}  # careful reading speed, rough
WORDLIST = Path(__file__).resolve().parent.parent / "references" / "high-frequency-words.txt"
ENDINGS = (("ies", "y"), ("ied", "y"), ("es", ""), ("s", ""), ("ed", ""), ("ed", "e"), ("ing", ""), ("ing", "e"),
           ("ly", ""), ("er", ""), ("est", ""))


def base(w, known):
    if w in known:
        return w, True
    for suf, rep in ENDINGS:
        if w.endswith(suf) and len(w) > len(suf) + 2:
            stem = w[: -len(suf)] + rep
            if stem in known or (stem[-1:] == stem[-2:-1] and stem[:-1] in known):
                return stem, True
    return w, False


def key(w):
    """Crude stem so that approve/approves/approved and hive/hives count as one item."""
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) > len(suf) + 2 and not w.endswith("ss"):
            w = w[: -len(suf)]
            break
    return w[:-1] if w.endswith("e") and len(w) > 3 else w


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", help="text file, or - for stdin")
    ap.add_argument("--level", type=str.upper, choices=WPM, default="B1")
    ap.add_argument("--task-words", nargs="*", default=[], help="words the task depends on")
    ap.add_argument("--max", type=int, default=6, help="maximum items to pre-teach (default 6)")
    a = ap.parse_args()
    try:
        text = (sys.stdin if a.text == "-" else open(a.text, encoding="utf-8")).read().strip()
        known = {w for line in WORDLIST.read_text(encoding="utf-8").splitlines() if not line.startswith("#")
                 for w in line.lower().split()}
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not re.search(r"[A-Za-z]", text):
        print("error: empty text", file=sys.stderr)
        return 2
    first = re.split(r"(?<=[.!?])\s+|\n+", text, maxsplit=1)[0].lower()
    rare, forms, words = Counter(), {}, 0
    for sent in re.split(r"(?<=[.!?])\s+|\n+", text):
        for i, m in enumerate(re.finditer(r"[A-Za-z][A-Za-z'-]*", sent)):
            words += 1
            w = m.group(0)
            if i > 0 and w[0].isupper():
                continue
            stem, ok = base(w.lower().replace("'s", ""), known)
            if not ok and len(stem) > 2:
                rare[key(stem)] += 1
                forms.setdefault(key(stem), Counter())[stem] += 1
    names = Counter(re.sub(r"^(The|A|An|In|On|At|Under|But|And)\s+", "", m.group(0))
                    for m in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", text))
    names = [n for n in names if " " in n]
    task = {key(t.lower()) for t in a.task_words}
    in_first = {key(w) for w in re.findall(r"[a-z][a-z'-]*", first)}
    score = {w: n * 2 + (3 if w in in_first else 0) + (10 if w in task else 0) for w, n in rare.items()}
    ranked = sorted(score, key=lambda w: (-score[w], w))
    show = {k: min(f, key=lambda x: (-f[x], len(x))) for k, f in forms.items()}
    preteach = ranked[:a.max]
    gloss = [w for w in ranked[a.max:] if rare[w] > 1 or w in in_first]
    ignore = [w for w in ranked[a.max:] if w not in gloss]
    cover = 100 * (words - sum(rare.values())) / words
    print(f"{words} words; {cover:.0f}% high-frequency; about {words / WPM[a.level]:.1f} min to read carefully at {a.level}")
    print(f"\nPre-teach (max {a.max}): " + (", ".join(f"{show[w]} ({rare[w]}x)" for w in preteach) or "none"))
    print("Gloss on the page: " + (", ".join(show[w] for w in gloss) or "none"))
    print("Let learners ignore for the task: " + (", ".join(show[w] for w in ignore[:20]) or "none")
          + (f" (+{len(ignore) - 20} more)" if len(ignore) > 20 else ""))
    if names:
        print("Names / cultural references to check: " + ", ".join(names))
    missing = sorted(t for t in a.task_words if key(t.lower()) not in rare and not base(t.lower(), known)[1])
    if missing:
        print("Task words not found in the text: " + ", ".join(missing))
    if cover < 85:
        print(f"\nCoverage {cover:.0f}% is low for unsupported reading: grade the task (gist, scanning) rather than "
              "asking for detail, or choose a different text")
    return 0


if __name__ == "__main__":
    sys.exit(main())
