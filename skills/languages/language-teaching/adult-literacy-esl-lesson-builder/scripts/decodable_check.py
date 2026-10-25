#!/usr/bin/env python3
"""Check how decodable a reading text is for adult literacy learners, given the letter-sound patterns taught.

A word is decodable when it can be split entirely into taught graphemes (single letters or patterns such as sh,
ch, th, ck, ee, ai). A common digraph that has not been taught makes the word non-decodable even if its letters
were taught singly (shop needs "sh", not s + h). Sight words learners have been taught as wholes (the, I, to,
is...) count as readable. Everything else is listed with the untaught part, so the teacher can swap the word or
pre-teach it.

Usage:
    python decodable_check.py text.txt --taught s a t p i n m d g o c k ck e u r h b f l --sight the I to is a
    python decodable_check.py text.txt --taught-file taught.txt --sight-file sight.txt --min 90

Exit codes: 0 at or above --min % readable (default 90), 1 below, 2 read error or nothing taught.
"""

import argparse
import re
import sys
from collections import Counter

DIGRAPHS = ["tch", "igh", "air", "ear", "ure", "sh", "ch", "th", "ph", "wh", "ck", "ng", "qu", "ee", "ea", "oa", "ai",
            "ay", "oo", "ou", "ow", "oi", "oy", "ar", "or", "er", "ir", "ur", "aw", "ew"]


def untaught_digraph(word, graphemes):
    return next((d for d in DIGRAPHS if d in word and d not in graphemes), None)


def split(word, graphemes):
    """Return a split into taught graphemes, or None. Longest graphemes are tried first."""
    if untaught_digraph(word, graphemes):
        return None
    best = {0: []}
    for i in range(len(word)):
        if i not in best:
            continue
        for g in graphemes:
            if word.startswith(g, i) and i + len(g) not in best:
                best[i + len(g)] = best[i] + [g]
    return best.get(len(word))


def first_gap(word, graphemes):
    d = untaught_digraph(word, graphemes)
    if d:
        return d
    i = 0
    while i < len(word):
        g = next((g for g in graphemes if word.startswith(g, i)), None)
        if not g:
            return word[i]
        i += len(g)
    return ""


def words_from(args_list, path):
    items = list(args_list or [])
    if path:
        items += open(path, encoding="utf-8").read().split()
    return items


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", help="text file, or - for stdin")
    ap.add_argument("--taught", nargs="*", help="graphemes taught so far")
    ap.add_argument("--taught-file")
    ap.add_argument("--sight", nargs="*", help="sight words taught")
    ap.add_argument("--sight-file")
    ap.add_argument("--min", type=float, default=90, help="minimum %% readable (default 90)")
    a = ap.parse_args()
    try:
        text = (sys.stdin if a.text == "-" else open(a.text, encoding="utf-8")).read()
        graphemes = sorted({g.lower() for g in words_from(a.taught, a.taught_file)}, key=len, reverse=True)
        sight = {w.lower() for w in words_from(a.sight, a.sight_file)}
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not graphemes:
        print("error: give the taught graphemes with --taught or --taught-file", file=sys.stderr)
        return 2
    tokens = [w.lower() for w in re.findall(r"[A-Za-z']+", text)]
    if not tokens:
        print("error: no words in the text", file=sys.stderr)
        return 2
    bad, ok_sight = Counter(), 0
    for w in tokens:
        clean = w.replace("'", "")
        if w in sight or clean in sight:
            ok_sight += 1
        elif not split(clean, graphemes):
            bad[clean] += 1
    readable = 100 * (len(tokens) - sum(bad.values())) / len(tokens)
    print(f"{len(tokens)} words: {readable:.0f}% readable ({ok_sight} sight-word tokens)")
    if bad:
        print("Not yet decodable (untaught part):")
        for w, n in bad.most_common():
            print(f"  {w}{f' x{n}' if n > 1 else ''}  ['{first_gap(w, graphemes)}']")
    gaps = Counter(first_gap(w, graphemes) for w in bad.elements())
    if gaps:
        print("Most useful next patterns: " + ", ".join(f"{g} ({n})" for g, n in gaps.most_common(5)))
    ok = readable >= a.min
    print(f"{'OK' if ok else 'BELOW'}: target {a.min:g}% readable")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
