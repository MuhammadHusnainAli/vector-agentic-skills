#!/usr/bin/env python3
"""Review a language lesson plan (the JSON used by plan_scaffold.py) for the faults trainers flag most often.

Checks:
  LP001 high    main aim missing or teacher-centred ('to teach', 'to present', 'T will')
  LP002 high    stage minutes do not add up to the lesson length (more than 2 min out), or a stage has no time
  LP003 medium  main aim uses an unobservable verb (understand, know, learn, be aware of)
  LP004 medium  stage without a stage aim
  LP005 medium  teacher-fronted (T-Ss) time above 40% of the lesson
  LP006 medium  pair or group task not followed by a feedback stage
  LP007 medium  language-focus lesson with no freer practice / production stage
  LP008 low     stage longer than 20 minutes: split it or change the interaction
  LP009 low     no anticipated problems and solutions

Usage:
    python plan_check.py lesson.json

Exit codes: 0 no high findings, 1 high findings, 2 read or JSON error.
"""

import argparse
import json
import re
import sys

TEACHER_AIM = re.compile(r"^\s*(to (teach|present|introduce|explain|show|revise)|(the )?(t|teacher) will)\b", re.I)
VAGUE = re.compile(r"\b(understand|know|learn|be aware of|be familiar with|appreciate|grasp)\b", re.I)
GROUP = re.compile(r"\b(s-s|ss-ss|pairs?|groups?|pw|gw)\b", re.I)
TEACHER = re.compile(r"^\s*t\s*-\s*ss?\s*$", re.I)
FEEDBACK = re.compile(r"feedback|fb\b|check answers|error correction|delayed correction", re.I)
LANGUAGE = re.compile(r"\b(grammar|tense|vocabulary|lexis|form|structure|modal|conditional|past|present|future|phrases?)\b", re.I)
FREER = re.compile(r"freer|free practice|production|speaking task|role ?play|discussion|personali[sz]", re.I)


def check(sp):
    f = []
    stages = sp.get("stages") or []
    aim = str(sp.get("main_aim") or "")
    if not aim:
        f.append(("LP001", "high", "no main aim: state what learners will be able to do by the end"))
    elif TEACHER_AIM.search(aim):
        f.append(("LP001", "high", f"main aim '{aim[:50]}' describes the teacher; rewrite as a learner outcome"))
    elif VAGUE.search(aim):
        f.append(("LP003", "medium", f"main aim uses '{VAGUE.search(aim).group(0)}': name something learners can be seen doing"))
    mins = [int(s.get("minutes") or 0) for s in stages]
    total = int(sp.get("minutes") or 0)
    untimed = [s.get("name", "?") for s in stages if not s.get("minutes")]
    if untimed:
        f.append(("LP002", "high", f"no minutes for: {', '.join(untimed)}"))
    elif total and abs(sum(mins) - total) > 2:
        f.append(("LP002", "high", f"stages add up to {sum(mins)} min but the lesson is {total} min"))
    span = total or sum(mins) or 1
    t_time = 0
    for i, (s, m) in enumerate(zip(stages, mins)):
        name = s.get("name", f"stage {i + 1}")
        if not s.get("aim"):
            f.append(("LP004", "medium", f"'{name}' has no stage aim"))
        inter = str(s.get("interaction", ""))
        if TEACHER.match(inter):
            t_time += m
        nxt = stages[i + 1] if i + 1 < len(stages) else {}
        if GROUP.search(inter) and not FEEDBACK.search(f"{s.get('procedure', '')} {nxt.get('name', '')} {nxt.get('procedure', '')}"):
            f.append(("LP006", "medium", f"'{name}' is pair/group work with no feedback stage after it"))
        if m > 20:
            f.append(("LP008", "low", f"'{name}' runs {m} min: split it or change the interaction"))
    if t_time / span > 0.4:
        f.append(("LP005", "medium", f"T-Ss stages take {100 * t_time / span:.0f}% of the lesson; aim for 40% or less"))
    names = " ".join(f"{s.get('name', '')} {s.get('aim', '')}" for s in stages)
    if LANGUAGE.search(aim) and not FREER.search(names):
        f.append(("LP007", "medium", "language-focus lesson with no freer practice: learners never use it for themselves"))
    if not sp.get("problems"):
        f.append(("LP009", "low", "add anticipated problems (meaning, form, pronunciation, task) with solutions"))
    return f


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", help="lesson JSON, or - for stdin")
    a = ap.parse_args()
    try:
        fh = sys.stdin if a.spec == "-" else open(a.spec, encoding="utf-8")
        with fh:
            sp = json.load(fh)
        if not isinstance(sp, dict):
            raise ValueError("lesson JSON must be an object")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    f = check(sp)
    print(f"{sp.get('title', '(untitled)')}: {len(sp.get('stages') or [])} stages, {len(f)} finding(s)")
    order = {"high": 0, "medium": 1, "low": 2}
    for code, sev, msg in sorted(f, key=lambda x: (order[x[1]], x[0])):
        print(f"{code} [{sev}] {msg}")
    if not f:
        print("OK: aims, timing, interaction and staging look sound")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
