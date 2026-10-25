#!/usr/bin/env python3
"""Check a listening text's speed, length and speakers against a level, and split it into pause points.

Speech rate is words per minute from the transcript and the recording length. Lines starting with "Name:" count
as speaker turns. --segments N splits the recording into N parts at sentence ends with approximate timestamps
(proportional to words), for pause-and-predict or segment-by-segment detail tasks.

Usage:
    python transcript_stats.py transcript.txt --duration 2:10 --level B1
    python transcript_stats.py transcript.txt --duration 95 --level A2 --segments 3

Exit codes: 0 suitable, 1 too fast or too long for the level, 2 read error or bad duration.
"""

import argparse
import re
import sys

# level: (max comfortable wpm, max length in seconds for one task, plays)
LEVEL = {"A1": (110, 60, 3), "A2": (130, 120, 3), "B1": (150, 180, 2), "B2": (170, 300, 2), "C1": (190, 480, 1),
         "C2": (230, 900, 1)}


def seconds(text):
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return float(text)
    m = re.fullmatch(r"(\d+):([0-5]\d)", text)
    if not m:
        raise ValueError(f"duration '{text}' must be seconds or m:ss")
    return int(m.group(1)) * 60 + int(m.group(2))


def mmss(s):
    return f"{int(s) // 60}:{int(s) % 60:02d}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transcript", help="text file, or - for stdin")
    ap.add_argument("--duration", required=True, help="recording length: seconds or m:ss")
    ap.add_argument("--level", type=str.upper, choices=LEVEL, default="B1")
    ap.add_argument("--segments", type=int, default=0, help="split into N parts with timestamps")
    a = ap.parse_args()
    try:
        text = (sys.stdin if a.transcript == "-" else open(a.transcript, encoding="utf-8")).read()
        dur = seconds(a.duration)
        if dur <= 0:
            raise ValueError("duration must be positive")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    speakers = {m.group(1) for m in re.finditer(r"^\s*([A-Z][\w .'-]{0,20}):", text, re.M)}
    body = re.sub(r"^\s*[A-Z][\w .'-]{0,20}:", "", text, flags=re.M)
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", body)
    if not words:
        print("error: transcript has no words", file=sys.stderr)
        return 2
    wpm = len(words) / (dur / 60)
    max_wpm, max_len, plays = LEVEL[a.level]
    speed = "slow" if wpm < 120 else "moderate" if wpm < 150 else "natural" if wpm < 180 else "fast"
    print(f"{len(words)} words in {mmss(dur)}: {wpm:.0f} wpm ({speed}); speakers: {len(speakers) or 1}"
          + (f" ({', '.join(sorted(speakers))})" if speakers else ""))
    print(f"{a.level} guide: up to {max_wpm} wpm, up to {mmss(max_len)} per task, play {plays}x")
    problems = []
    if wpm > max_wpm:
        problems.append(f"speech is {wpm - max_wpm:.0f} wpm faster than the {a.level} guide: pause between segments, "
                        "grade the task (gist only), or choose a slower recording")
    if dur > max_len:
        problems.append(f"recording is longer than {mmss(max_len)}: use an extract or split it into segments")
    if len(speakers) > 3 and a.level in ("A1", "A2", "B1"):
        problems.append(f"{len(speakers)} speakers is a lot for {a.level}: give a speaker list with pictures")
    if a.segments > 1:
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", body.strip()) if s.strip()]
        target, count, t, cuts = len(words) / a.segments, 0, 0.0, []
        for s in sentences:
            n = len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", s))
            count += n
            if count >= target * (len(cuts) + 1) and len(cuts) < a.segments - 1:
                cuts.append((count, s.strip()[-40:]))
        print("\nPause points:")
        for i, (c, tail) in enumerate(cuts, 1):
            print(f"  {i}. ~{mmss(dur * c / len(words))} after '...{tail}'")
    for p in problems:
        print(f"ADJUST: {p}")
    if not problems:
        print("OK for the level")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
