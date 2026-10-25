#!/usr/bin/env python3
"""Pick communicative activities from references/activity-bank.md that fit a class.

Filters (all optional): CEFR level, skill, class size, time available, maximum preparation, online, grouping and a
language-focus keyword. Matches are sorted so activities that use the time best come first.

Usage:
    python activity_picker.py --level B1 --skill speaking --minutes 15 --students 9
    python activity_picker.py --level A2 --focus "past simple" --online --prep low
    python activity_picker.py --level C1 --grouping groups --show 3 --bank my-bank.md

Exit codes: 0 activities found, 1 nothing matches, 2 bank unreadable or bad level.
"""

import argparse
import re
import sys
from pathlib import Path

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
PREP = {"none": 0, "low": 1, "medium": 2, "high": 3}
DEFAULT_BANK = Path(__file__).resolve().parent.parent / "references" / "activity-bank.md"


def read_bank(path):
    rows, head = [], None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or re.match(r"^\|[\s|:-]+\|$", line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if head is None:
            head = [c.lower() for c in cells]
        elif len(cells) == len(head):
            rows.append(dict(zip(head, cells)))
    if not rows:
        raise ValueError(f"no activity table in {path}")
    return rows


def level_range(text):
    lo, _, hi = text.upper().partition("-")
    return LEVELS.index(lo.strip()), LEVELS.index((hi or lo).strip())


def fits(r, a):
    lo, hi = level_range(r["levels"])
    if a.level and not lo <= LEVELS.index(a.level) <= hi:
        return False
    if a.skill and a.skill.lower() not in r["skills"].lower():
        return False
    if a.students and a.students < int(r["min ss"]):
        return False
    if a.minutes and int(r["minutes"]) > a.minutes:
        return False
    if a.prep and PREP.get(r["prep"].lower(), 3) > PREP[a.prep]:
        return False
    if a.online and r["online"].lower() != "yes":
        return False
    if a.grouping and a.grouping.lower() not in r["grouping"].lower():
        return False
    if a.focus and a.focus.lower() not in f"{r['language focus']} {r['how it works']}".lower():
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--level", type=str.upper, help="CEFR level A1-C2")
    ap.add_argument("--skill", help="speaking, listening, reading, writing, vocabulary, grammar")
    ap.add_argument("--students", type=int, help="class size")
    ap.add_argument("--minutes", type=int, help="time available (maximum)")
    ap.add_argument("--prep", choices=PREP, help="maximum preparation")
    ap.add_argument("--online", action="store_true", help="must work in a video call")
    ap.add_argument("--grouping", help="pairs, groups, mingle, whole class, individual")
    ap.add_argument("--focus", help="keyword in the language focus, e.g. 'conditionals'")
    ap.add_argument("--show", type=int, default=5, help="how many to show (default 5)")
    ap.add_argument("--bank", default=DEFAULT_BANK, help="activity table in Markdown")
    a = ap.parse_args()
    if a.level and a.level not in LEVELS:
        print(f"error: level must be one of {', '.join(LEVELS)}", file=sys.stderr)
        return 2
    try:
        rows = read_bank(a.bank)
        hits = [r for r in rows if fits(r, a)]
    except (OSError, ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not hits:
        print("No activity matches; relax --minutes, --prep or --focus.")
        return 1
    hits.sort(key=lambda r: (a.minutes - int(r["minutes"])) if a.minutes else 0)
    print(f"{len(hits)} of {len(rows)} activities match; showing {min(a.show, len(hits))}\n")
    for r in hits[:a.show]:
        print(f"## {r['activity']}  ({r['levels']}, {r['grouping']}, {r['minutes']} min, prep {r['prep']}, online {r['online']})")
        print(f"Language: {r['language focus']}")
        print(f"How: {r['how it works']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
