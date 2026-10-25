#!/usr/bin/env python3
"""Code a teacher's oral corrective feedback in a classroom transcript and report uptake and repair.

Transcript: one turn per line, "T: ..." for the teacher, any other "Name: ..." for a learner. End a learner turn
with " *" when it contains an error. The teacher turn right after an error turn is coded as:
  explicit       gives the correct form and says it was wrong ("not go - went", "you should say")
  metalinguistic comments on form ("past tense?", "check the verb", "is that right?")
  clarification  "Sorry?", "Pardon?", "What do you mean?"
  elicitation    prompts completion or reformulation ("Yesterday I...?", "How do we say...", "Try again")
  repetition     repeats the learner's words with rising intonation (mostly the same words + "?")
  recast         reformulates the learner's words correctly without signalling the error
  none           carries on without feedback
A learner turn after the feedback is uptake; uptake without " *" is repair.

Findings:
  CF001 medium  over 70% of feedback moves are recasts: add prompts so learners self-correct
  CF002 medium  over half the errors get no feedback in an accuracy stage (--stage accuracy)
  CF003 low     prompts given but learners rarely repair (under 50%): give more wait time or a clearer cue

Usage:
    python feedback_coder.py transcript.txt [--stage accuracy|fluency]

Exit codes: 0 printed, 2 read error or no learner errors marked.
"""

import argparse
import re
import sys
from collections import Counter

PROMPTS = ("metalinguistic", "clarification", "elicitation", "repetition")


def words(s):
    return re.findall(r"[a-z']+", s.lower())


def stems(ws):
    return {re.sub(r"(ed|es|s|ing)$", "", w) if len(w) > 4 else w for w in ws}


def code(teacher, learner):
    t = teacher.strip()
    tl = t.lower()
    if re.search(r"\bnot\b[^.?!]*\s[-–:]\s*\w|\byou should say\b|\bwe say\b|\bdon't say\b|\bthe correct\b|\bit's not\b", tl):
        return "explicit"
    if re.search(r"^(sorry|pardon|excuse me|what do you mean|i don't understand)\b[?!. ]*", tl) and len(words(t)) <= 5:
        return "clarification"
    if re.search(r"\b(tense|verb|plural|singular|article|preposition|past|present|ending|is that right|grammar|-ed|word order)\b", tl) and "?" in t:
        return "metalinguistic"
    if re.search(r"(\.\.\.|…)\s*\??$|how do (we|you) say|try again|say (it|that) again|can you correct|what's the", tl):
        return "elicitation"
    lw, tw = words(learner), words(t)
    if t.endswith("?") and tw and set(tw) <= set(lw) and len(tw) >= 0.6 * len(set(lw)):
        return "repetition"
    common = len(stems(lw) & stems(tw))
    if common >= min(2, max(1, len(stems(lw)) - 1)) and max(common / len(stems(lw)), common / len(stems(tw))) >= 0.5:
        return "recast"
    return "none"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transcript", help="text file, or - for stdin")
    ap.add_argument("--stage", choices=["accuracy", "fluency"], default="fluency")
    a = ap.parse_args()
    try:
        lines = (sys.stdin if a.transcript == "-" else open(a.transcript, encoding="utf-8")).read().splitlines()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    turns = [(m.group(1).strip(), m.group(2).strip()) for m in
             (re.match(r"^\s*([^:]{1,20}):\s*(.*)$", l) for l in lines) if m]
    moves, uptake, repair, log = Counter(), Counter(), Counter(), []
    for i, (who, said) in enumerate(turns):
        if who == "T" or not said.endswith("*") or i + 1 >= len(turns) or turns[i + 1][0] != "T":
            continue
        fb = turns[i + 1][1]
        move = code(fb, said.rstrip("* "))
        moves[move] += 1
        nxt = turns[i + 2] if i + 2 < len(turns) else None
        up = bool(nxt and nxt[0] != "T" and move != "none")
        rep = up and not nxt[1].endswith("*")
        uptake[move] += up
        repair[move] += rep
        log.append(f"  {who}: {said.rstrip('* ')}\n    T: {fb}  -> {move}" + (" | repair" if rep else " | uptake" if up else ""))
    if not moves:
        print("error: no learner error turns (end them with ' *') followed by a teacher turn", file=sys.stderr)
        return 2
    total = sum(moves.values())
    given = total - moves["none"]
    print(f"{total} errors marked; feedback on {given}")
    print("| Move | Count | Uptake | Repair |\n|------|-------|--------|--------|")
    for m, n in moves.most_common():
        print(f"| {m} | {n} | {uptake[m]} | {repair[m]} |")
    print("\n" + "\n".join(log))
    f = []
    if given and moves["recast"] / given > 0.7:
        f.append(("CF001", "medium", f"{100 * moves['recast'] / given:.0f}% of feedback is recasts; try elicitation or a metalinguistic clue"))
    if a.stage == "accuracy" and moves["none"] / total > 0.5:
        f.append(("CF002", "medium", f"{moves['none']} of {total} errors get no feedback in an accuracy stage"))
    p = sum(moves[m] for m in PROMPTS)
    if p >= 2 and sum(repair[m] for m in PROMPTS) / p < 0.5:
        f.append(("CF003", "low", "prompts rarely lead to repair: wait 3-5 seconds, make the cue clearer, then give the form"))
    if f:
        print()
    for code_, sev, msg in f:
        print(f"{code_} [{sev}] {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
