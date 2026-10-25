#!/usr/bin/env python3
"""Split a PPP (presentation, practice, production) lesson into timed stages.

Shares follow the usual PPP balance and shift with level: lower levels get more clarification and controlled
practice, higher levels more freer practice. Minutes always add up to the lesson length.

Usage:
    python ppp_timing.py --minutes 60 --level A2
    python ppp_timing.py --minutes 45 --level B2 --json     # stages for plan_scaffold.py

Exit codes: 0 printed, 2 bad arguments (lesson under 20 minutes or unknown level).
"""

import argparse
import json
import sys

# (stage, stage aim, interaction, share at A1-A2, share at B1, share at B2-C2)
STAGES = [
    ("Lead-in", "Generate interest and set the context", "T-Ss, S-S", 8, 8, 8),
    ("Presentation in context", "Show the target language in a meaningful situation or text", "T-Ss", 12, 10, 8),
    ("Clarification: meaning, form, pronunciation", "Check meaning with CCQs, board the form, drill", "T-Ss", 20, 17, 14),
    ("Controlled practice", "Accurate practice of the form", "Ind, S-S", 17, 15, 12),
    ("Feedback on controlled practice", "Check answers; correct form", "Ss-T", 5, 5, 4),
    ("Freer practice", "Use the target language for a personal, communicative purpose", "S-S, Ss-Ss", 25, 30, 38),
    ("Delayed error correction", "Correct key errors from the freer task", "T-Ss", 8, 10, 11),
    ("Flexi", "Extension or catch-up", "", 5, 5, 5),
]
BAND = {"A1": 3, "A2": 3, "B1": 4, "B2": 5, "C1": 5, "C2": 5}


def split(minutes, col):
    raw = [s[col] * minutes / 100 for s in STAGES]
    mins = [int(r) for r in raw]
    for i in sorted(range(len(raw)), key=lambda i: raw[i] - mins[i], reverse=True)[:minutes - sum(mins)]:
        mins[i] += 1  # largest remainder keeps the total exact
    return mins


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--minutes", type=int, required=True)
    ap.add_argument("--level", default="B1", help="CEFR level A1-C2 (default B1)")
    ap.add_argument("--json", action="store_true", help="print a stages list for plan_scaffold.py")
    a = ap.parse_args()
    col = BAND.get(a.level.upper())
    if col is None or a.minutes < 20:
        print("error: need --minutes >= 20 and --level A1-C2", file=sys.stderr)
        return 2
    mins = split(a.minutes, col)
    if a.json:
        print(json.dumps([{"name": s[0], "aim": s[1], "minutes": m, "interaction": s[2]}
                          for s, m in zip(STAGES, mins)], indent=2))
        return 0
    print(f"PPP lesson, {a.minutes} min, {a.level.upper()}\n")
    print("| Time | Stage | Stage aim | Interaction |\n|------|-------|-----------|-------------|")
    t = 0
    for s, m in zip(STAGES, mins):
        print(f"| {t}-{t + m} | {s[0]} | {s[1]} | {s[2]} |")
        t += m
    p1 = sum(mins[:3])
    p2 = sum(mins[3:5])
    p3 = sum(mins[5:7])
    print(f"\nPresentation {p1} min | Practice {p2} min | Production {p3} min | Flexi {mins[-1]} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
