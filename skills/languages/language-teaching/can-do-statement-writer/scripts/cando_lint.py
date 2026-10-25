#!/usr/bin/env python3
"""Lint can-do statements: learner ability, observable action, context, one activity, quality, communicative purpose.

Input: one statement per line. Each is classified by mode (reception, production, interaction, mediation) from its
verb; a set that misses a mode is reported.

Checks:
  CD001 high    not phrased as learner ability ('I can' / 'Can' / 'Learners can')
  CD002 high    knowledge, not use: know, learn, be aware of, be familiar with, understand + a grammar term
  CD003 medium  no context (topic, text type, situation or audience)
  CD004 medium  two activities in one statement (read and write, listen and speak)
  CD005 low     vague quality word (well, correctly, fluently, properly) without a condition
  CD006 low     longer than 30 words
  CD007 low     names a grammar item as the outcome without a purpose ('use the past simple')
  CD008 low     the set has no statement for a mode

Usage:
    python cando_lint.py statements.txt

Exit codes: 0 no high findings, 1 high findings, 2 read error or no statements.
"""

import argparse
import re
import sys

START = re.compile(r"^(i can|can|learners can|students can|the learner can|we can)\b", re.I)
KNOW = re.compile(r"\b(know|learn|be aware of|be familiar with|recogni[sz]e the (form|rule))\b|\bunderstand (the )?"
                  r"(grammar|tense|present|past|future|conditional|passive|rules?|modals?|articles?)\b", re.I)
CONTEXT = re.compile(r"\b(about|on|in|at|for|with|from|when|during|to|if|using|such as|e\.g\.)\b", re.I)
GRAMMAR = re.compile(r"\buse (the |a |an )?(present|past|future|second|first|third|zero|passive|modal|article|"
                     r"comparative|superlative|conditional|gerund|infinitive|relative)\b", re.I)
VAGUE = re.compile(r"\b(well|correctly|fluently|properly|effectively|accurately|perfectly|appropriately)\b", re.I)
CONDITION = re.compile(r"\b(if|with (some|little|no|support|help)|when|provided|slowly|without)\b", re.I)
MODES = {
    "reception": r"\b(understand|read|listen|follow|identify|recogni[sz]e|find|scan|catch|watch|get the gist)",
    "interaction": r"\b(ask|answer|take part|discuss|exchange|chat|interact|negotiate|agree|respond|reply|order|book|"
                   r"make (a |an )?(request|arrangement|complaint|appointment)|participate|greet)",
    "mediation": r"\b(summari[sz]e|explain (to|what|the (main|gist|meaning|idea))|relay|translate|paraphrase|mediate|pass on|interpret|"
                 r"report (back|what)|facilitate)",
    "production": r"\b(write|speak|describe|tell|give (a )?(talk|presentation|reasons|opinion)|present|introduce|narrate|"
                  r"produce|report|express|talk about|say|fill in|complete (a )?form)",
}
TWO = re.compile(r"\b(read|write|listen|speak|talk)\b.*\b(and|&)\b.*\b(read|write|listen|speak|talk)\b", re.I)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("statements", help="text file, one statement per line, or - for stdin")
    a = ap.parse_args()
    try:
        lines = (sys.stdin if a.statements == "-" else open(a.statements, encoding="utf-8")).read().splitlines()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    items = [re.sub(r"^\s*(\d+[.)]|[-*])\s*", "", l).strip() for l in lines if l.strip() and not l.startswith("#")]
    if not items:
        print("error: no statements", file=sys.stderr)
        return 2
    f, seen = [], set()
    for i, s in enumerate(items, 1):
        mode = next((m for m, p in MODES.items() if re.search(p, s, re.I)), "?")
        seen.add(mode)
        print(f"[{i}] ({mode}) {s}")
        body = START.sub("", s).strip()
        if not START.search(s):
            f.append(("CD001", "high", f"[{i}] start with 'I can' (learner) or 'Can' (descriptor)"))
        if KNOW.search(s):
            f.append(("CD002", "high", f"[{i}] '{KNOW.search(s).group(0)}' is knowledge; say what the learner does with it"))
        if not CONTEXT.search(body) or len(body.split()) < 4:
            f.append(("CD003", "medium", f"[{i}] add a context: topic, text type, situation or audience"))
        if TWO.search(s):
            f.append(("CD004", "medium", f"[{i}] two activities in one statement: split it"))
        if VAGUE.search(s) and not CONDITION.search(s):
            f.append(("CD005", "low", f"[{i}] '{VAGUE.search(s).group(0)}' is vague: describe quality (e.g. 'with some hesitation', 'if speech is slow')"))
        if len(s.split()) > 30:
            f.append(("CD006", "low", f"[{i}] {len(s.split())} words: shorten to one clear outcome"))
        if GRAMMAR.search(s) and not re.search(r"\bto (talk|describe|say|ask|tell|write|explain|give|make|compare)\b", s, re.I):
            f.append(("CD007", "low", f"[{i}] names a grammar item: say what it is used for (e.g. 'to talk about...')"))
    for m in MODES:
        if m not in seen and len(items) >= 4:
            f.append(("CD008", "low", f"no {m} statement in the set"))
    print()
    order = {"high": 0, "medium": 1, "low": 2}
    for code, sev, msg in sorted(f, key=lambda x: (order[x[1]], x[0])):
        print(f"{code} [{sev}] {msg}")
    if not f:
        print("OK: all statements are observable, contextualised learner outcomes")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
