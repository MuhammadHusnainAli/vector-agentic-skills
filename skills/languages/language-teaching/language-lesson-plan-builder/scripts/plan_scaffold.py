#!/usr/bin/env python3
"""Turn a JSON lesson outline into a staged language lesson plan in Markdown.

Stages without minutes share the time left over equally; start and end times are printed for every stage so the
plan can be followed with a clock.

Spec (JSON):
  {
    "title": "Past simple for holiday stories", "level": "A2", "minutes": 60, "learners": 12,
    "main_aim": "By the end of the lesson learners will be able to tell a partner about a past holiday
                 using regular and irregular past simple verbs",
    "subsidiary_aims": ["Listening for gist and detail"],
    "stages": [
      {"name": "Lead-in", "aim": "Generate interest in holidays", "minutes": 5, "interaction": "T-Ss",
       "procedure": "Show three holiday photos; Ss guess where T went", "materials": "Slides 1-3"}
    ],
    "problems": [{"problem": "Ss say *goed*", "solution": "Board the irregular verb list; drill"}]
  }

Usage:
    python plan_scaffold.py lesson.json > plan.md

Exit codes: 0 written, 1 stage minutes exceed the lesson length, 2 read or JSON error.
"""

import argparse
import json
import sys


def load(path):
    fh = sys.stdin if path == "-" else open(path, encoding="utf-8")
    with fh:
        spec = json.load(fh)
    if not isinstance(spec, dict) or not isinstance(spec.get("stages"), list) or not spec["stages"]:
        raise ValueError("spec must be an object with a non-empty 'stages' list")
    return spec


def fill_minutes(stages, total):
    fixed = sum(int(s.get("minutes") or 0) for s in stages)
    open_ = [s for s in stages if not s.get("minutes")]
    share = (total - fixed) // len(open_) if open_ and total > fixed else 0
    for s in open_:
        s["minutes"] = share
    return fixed + share * len(open_)


def render(sp, total):
    lines = [f"# {sp.get('title', 'Lesson plan')}", "",
             "| Level | Length | Learners |", "|-------|--------|----------|",
             f"| {sp.get('level', 'TODO')} | {total} min | {sp.get('learners', 'TODO')} |", "",
             "## Aims", "", f"**Main aim:** {sp.get('main_aim', 'TODO')}", ""]
    for a in sp.get("subsidiary_aims", []):
        lines.append(f"- Subsidiary: {a}")
    lines += ["", "## Procedure", "",
              "| Time | Stage | Stage aim | Interaction | Procedure | Materials |",
              "|------|-------|-----------|-------------|-----------|-----------|"]
    t = 0
    for s in sp["stages"]:
        m = int(s["minutes"])
        lines.append(f"| {t}-{t + m} | {s.get('name', 'TODO')} | {s.get('aim', 'TODO')} | "
                     f"{s.get('interaction', 'TODO')} | {s.get('procedure', 'TODO')} | {s.get('materials', '')} |")
        t += m
    lines += ["", "## Anticipated problems and solutions", "",
              "| Problem | Solution |", "|---------|----------|"]
    for p in sp.get("problems") or [{"problem": "TODO", "solution": "TODO"}]:
        lines.append(f"| {p.get('problem', '')} | {p.get('solution', '')} |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", help="lesson JSON, or - for stdin")
    a = ap.parse_args()
    try:
        sp = load(a.spec)
        total = int(sp.get("minutes") or 0)
        used = fill_minutes(sp["stages"], total)
    except (OSError, ValueError, TypeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if total and used > total:
        print(f"error: stages take {used} min but the lesson is {total} min", file=sys.stderr)
        return 1
    print(render(sp, total or used), end="")
    if total and used < total:
        print(f"\nNote: {total - used} min unplanned; add a flexi stage or extend one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
