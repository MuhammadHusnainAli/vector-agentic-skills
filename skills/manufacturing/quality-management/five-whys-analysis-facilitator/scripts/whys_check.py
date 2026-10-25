#!/usr/bin/env python3
"""Check a 5 Why analysis for logic gaps and print the reverse 'therefore' test.

Text format (one chain per leg; legs are optional):
    Problem: 40 of 200 VB-2210 parts had bore 12.021-12.030 mm (max 12.018)
    ## Occurrence
    Why: The boring insert wore beyond the size limit before the tool change
    Why: Tool change interval is 400 parts but the new insert grade wears out at about 250
    Why: The interval was not re-validated when the insert grade changed
    Why: Tooling changes are not covered by the change-control procedure
    ## Escape
    Why: In-process bore check is 1 in 50 parts
    ...

Checks:
  WY001 high    no problem statement, or the problem statement already contains a cause
  WY002 high    chain ends in blame or human error ('operator forgot', 'not trained')
  WY003 medium  chain under 3 whys (probably stopped at a symptom) or over 7 (drifting off scope)
  WY004 medium  an answer repeats the previous one (circular, no new information)
  WY005 medium  chain ends outside your control (customer, weather, supplier, management) - ask what in your process allowed it
  WY006 medium  an answer contains two causes ('and', ';') - split into branches
  WY007 low     vague answer ('lack of', 'poor', 'insufficient') with nothing specific
  WY008 low     only one leg: add an escape leg (why was it not detected?)

Usage:
    python whys_check.py analysis.txt

Exit codes: 0 no high findings, 1 high findings, 2 read or format error.
"""

import argparse
import re
import sys

BLAME = re.compile(r"\b(operator|worker|inspector|he|she|they|someone|person)\b.{0,30}\b(forgot|error|mistake|careless|did not (follow|check|notice)|wasn'?t paying|ignored)|\bhuman error\b|\bnot (properly )?trained\b|\black of (attention|care|discipline)\b", re.I)
CAUSE = re.compile(r"\b(because|due to|caused by)\b", re.I)
OUTSIDE = re.compile(r"\b(customer|weather|supplier|vendor|management|budget|market|government|act of god|bad luck)\b", re.I)
VAGUE = re.compile(r"\b(lack of|poor|insufficient|inadequate|not enough|bad|improper)\b", re.I)
STOP = set("the a an is are was were be to of in on for and or not no it this that with by at as from".split())


def words(s):
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP}


def parse(text):
    problem, legs, cur = "", {}, "Chain"
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^(problem|issue)\s*:\s*(.+)$", line, re.I)
        if m:
            problem = m.group(2)
            continue
        m = re.match(r"^#+\s*(.+)$", line)
        if m:
            cur = m.group(1).strip()
            continue
        m = re.match(r"^(why\s*\d*|\d+[.)])\s*[:.)-]?\s*(.+)$", line, re.I)
        if m:
            legs.setdefault(cur, []).append(m.group(2).strip())
    return problem, legs


def check(problem, legs):
    f = []
    if not problem:
        f.append(("WY001", "high", "start with 'Problem:' stating the effect (what, where, how many)"))
    elif CAUSE.search(problem):
        f.append(("WY001", "high", "the problem statement contains a cause; state the effect only"))
    for leg, chain in legs.items():
        last = chain[-1]
        if BLAME.search(last):
            f.append(("WY002", "high", f"{leg}: ends in blame ('{last[:60]}'): ask why the process allowed or did not catch it"))
        if len(chain) < 3:
            f.append(("WY003", "medium", f"{leg}: only {len(chain)} why(s); keep asking until you reach a process or system cause you can change"))
        elif len(chain) > 7:
            f.append(("WY003", "medium", f"{leg}: {len(chain)} whys; you have probably left the scope of the problem"))
        for i in range(1, len(chain)):
            a, b = words(chain[i - 1]), words(chain[i])
            if a and b and len(a & b) / len(b) > 0.7:
                f.append(("WY004", "medium", f"{leg} why {i + 1} repeats why {i}: add new information"))
        if OUTSIDE.search(last) and not re.search(r"\b(our|we|procedure|process|specification|requirement|contract)\b", last, re.I):
            f.append(("WY005", "medium", f"{leg}: ends outside your control ('{OUTSIDE.search(last).group(1)}'): ask what in your process allowed it"))
        for i, ans in enumerate(chain, 1):
            if re.search(r"\band\b.+\b(also|because)\b|;|\band also\b", ans):
                f.append(("WY006", "medium", f"{leg} why {i} has two causes: branch them"))
            if VAGUE.search(ans) and len(words(ans)) < 6:
                f.append(("WY007", "low", f"{leg} why {i} '{ans[:50]}' is vague: say what exactly is missing"))
    if len(legs) == 1:
        f.append(("WY008", "low", "only one leg: add '## Escape' (why was it not detected?) and optionally '## Systemic'"))
    return f


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="5 Why text file, or - for stdin")
    a = ap.parse_args()
    try:
        text = sys.stdin.read() if a.file == "-" else open(a.file, encoding="utf-8").read()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    problem, legs = parse(text)
    if not legs:
        print("error: no 'Why:' lines found", file=sys.stderr)
        return 2
    print("Therefore test (read bottom-up; each line must lead to the next):")
    for leg, chain in legs.items():
        print(f"  [{leg}]")
        for ans in reversed(chain):
            print(f"    {ans}")
            print("      -> therefore")
        print(f"    {problem or '(problem not stated)'}")
    f = check(problem, legs)
    print()
    for code, sev, msg in f:
        print(f"{code} [{sev}] {msg}")
    print(f"\n{len(f)} issue(s)" if f else "Chains reach controllable causes; confirm each link with evidence.")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
