#!/usr/bin/env python3
"""Estimate how hard an English text is for learners and show what to adapt for a target CEFR level.

Measures: average sentence length, coverage by the high-frequency word list (references/high-frequency-words.txt,
regular endings stripped, names and numbers ignored), Flesch reading ease, and long sentences / rare words.
Each measure maps to a CEFR band; the estimate is the harder of the two (an approximation, not a test score).

Usage:
    python text_level.py article.txt
    python text_level.py article.txt --target A2        # flag sentences and words above A2

Exit codes: 0 at or below the target (or no target), 1 above the target, 2 read error or empty text.
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
MAX_ASL = [8, 11, 15, 20, 25]           # average sentence length ceilings for A1..C1
MIN_COVER = [92, 88, 82, 75, 68]        # % high-frequency coverage floors for A1..C1 (1,000-word list)
LONG = {"A1": 10, "A2": 14, "B1": 20, "B2": 25, "C1": 30, "C2": 40}
WORDLIST = Path(__file__).resolve().parent.parent / "references" / "high-frequency-words.txt"


def load_words(path):
    words = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            words.update(line.lower().split())
    return words


def known(w, words):
    if w in words:
        return True
    for suf, rep in (("ies", "y"), ("ied", "y"), ("ier", "y"), ("iest", "y"), ("ily", "y"), ("es", ""), ("s", ""),
                     ("ed", ""), ("ed", "e"), ("ing", ""), ("ing", "e"), ("ly", ""), ("er", ""), ("est", ""),
                     ("'s", ""), ("n't", "")):
        if w.endswith(suf) and len(w) > len(suf) + 1:
            stem = w[: -len(suf)] + rep
            if stem in words or (len(stem) > 2 and stem[-1] == stem[-2] and stem[:-1] in words):
                return True
    return False


def syllables(w):
    return max(1, len(re.findall(r"[aeiouy]+", w.lower())) - (1 if w.lower().endswith("e") and len(w) > 3 else 0))


def band(asl, cover):
    a = next((i for i, m in enumerate(MAX_ASL) if asl <= m), 5)
    c = next((i for i, m in enumerate(MIN_COVER) if cover >= m), 5)
    return max(a, c), a, c


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", help="text file, or - for stdin")
    ap.add_argument("--target", type=str.upper, choices=LEVELS, help="CEFR level the text should suit")
    ap.add_argument("--wordlist", default=WORDLIST)
    ap.add_argument("--top", type=int, default=15, help="rare words to list (default 15)")
    a = ap.parse_args()
    try:
        text = (sys.stdin if a.text == "-" else open(a.text, encoding="utf-8")).read()
        words = load_words(a.wordlist)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if re.search(r"[A-Za-z]", s)]
    if not sentences:
        print("error: no sentences found", file=sys.stderr)
        return 2
    tokens, rare = [], Counter()
    for s in sentences:
        for i, m in enumerate(re.finditer(r"[A-Za-z][A-Za-z'-]*", s)):
            w = m.group(0)
            if i > 0 and w[0].isupper():
                continue  # proper noun
            tokens.append(w)
            if not known(w.lower(), words) and "-" not in w:
                rare[w.lower()] += 1
    asl = len(tokens) / len(sentences)
    cover = 100 * (len(tokens) - sum(rare.values())) / max(1, len(tokens))
    flesch = 206.835 - 1.015 * asl - 84.6 * sum(syllables(t) for t in tokens) / max(1, len(tokens))
    est, by_asl, by_cov = band(asl, cover)
    print(f"{len(tokens)} words, {len(sentences)} sentences")
    print(f"Average sentence length: {asl:.1f} words  (suits {LEVELS[by_asl]})")
    print(f"High-frequency coverage: {cover:.1f}%  (suits {LEVELS[by_cov]})")
    print(f"Flesch reading ease: {flesch:.0f}")
    print(f"Estimated level: {LEVELS[est]} (approximate)")
    if rare:
        print("\nLess frequent words: " + ", ".join(f"{w} ({n})" if n > 1 else w for w, n in rare.most_common(a.top)))
    if not a.target:
        return 0
    limit = LONG[a.target]
    long_s = [(i, s) for i, s in enumerate(sentences, 1) if len(re.findall(r"[A-Za-z][A-Za-z'-]*", s)) > limit]
    if long_s:
        print(f"\nSentences over {limit} words for {a.target}:")
        for i, s in long_s:
            print(f"  [{i}] {s[:90]}{'...' if len(s) > 90 else ''}")
    above = est > LEVELS.index(a.target)
    print(f"\nTarget {a.target}: {'ADAPT - text is above target' if above else 'OK'}")
    return 1 if above else 0


if __name__ == "__main__":
    sys.exit(main())
