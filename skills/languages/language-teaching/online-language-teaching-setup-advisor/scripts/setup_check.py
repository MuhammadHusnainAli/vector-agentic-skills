#!/usr/bin/env python3
"""Check an online language-teaching setup against the class it must serve.

JSON:
  {
    "class_size": 8, "age_group": "adults",          # young learners / teens / adults
    "upload_mbps": 2.5, "download_mbps": 20, "connection": "wifi",     # wifi / ethernet / mobile
    "microphone": "headset",                        # built-in / headset / usb
    "camera": "built-in", "light": "front",         # front / side / behind
    "platform": {"breakout_rooms": true, "screen_share_audio": true, "whiteboard": false, "chat": true,
                 "polls": true, "recording": true},
    "recording_lessons": true, "recording_consent": false,
    "safeguarding_policy": false, "backup_plan": ""
  }

Checks:
  OS001 high    upload below 1.5 Mbps (video drops; aim for 3+ for HD with margin)
  OS002 high    young learners or teens with no safeguarding policy
  OS003 high    lessons recorded without consent
  OS004 medium  class of 4+ with no breakout rooms (no pair or group work)
  OS005 medium  built-in microphone (echo and noise): use a headset or USB microphone
  OS006 medium  no computer-audio sharing: listening tasks will not reach learners clearly
  OS007 medium  mobile connection as the main line
  OS008 low     light behind the teacher (face in shadow; lip reading matters in language classes)
  OS009 low     no shared whiteboard or annotation tool
  OS010 low     no backup plan (second device, hotspot, alternative link, offline task)
  OS011 low     more than 15 learners in a live speaking class

Usage:
    python setup_check.py setup.json

Exit codes: 0 no high findings, 1 high findings, 2 read or JSON error.
"""

import argparse
import json
import sys


def check(s):
    f, p = [], s.get("platform") or {}
    size = int(s.get("class_size") or 1)
    up = float(s.get("upload_mbps") or 0)
    if up < 1.5:
        f.append(("OS001", "high", f"upload {up:g} Mbps: video will freeze; aim for 3+ Mbps or use ethernet"))
    age = str(s.get("age_group", "")).lower()
    if age in ("young learners", "children", "teens", "teenagers") and not s.get("safeguarding_policy"):
        f.append(("OS002", "high", f"{age}: agree a safeguarding policy (parent consent, no private chats, recordings, adult present)"))
    if s.get("recording_lessons") and not s.get("recording_consent"):
        f.append(("OS003", "high", "recording without consent: get written consent and state storage and deletion"))
    if size >= 4 and not p.get("breakout_rooms"):
        f.append(("OS004", "medium", f"{size} learners and no breakout rooms: no simultaneous pair or group speaking"))
    if str(s.get("microphone", "")).lower() == "built-in":
        f.append(("OS005", "medium", "built-in microphone: a headset gives clearer models for pronunciation and less echo"))
    if not p.get("screen_share_audio"):
        f.append(("OS006", "medium", "cannot share computer audio: share recordings as links or upgrade the platform"))
    if str(s.get("connection", "")).lower() == "mobile":
        f.append(("OS007", "medium", "mobile data as the main connection: use ethernet or reliable wifi, keep mobile as backup"))
    if str(s.get("light", "")).lower() == "behind":
        f.append(("OS008", "low", "light behind you: face a window or lamp so learners can see your mouth"))
    if not p.get("whiteboard"):
        f.append(("OS009", "low", "no whiteboard: add one (built-in, slides with annotation, or a shared document)"))
    if not s.get("backup_plan"):
        f.append(("OS010", "low", "no backup plan: second device, hotspot, alternative meeting link, offline task"))
    if size > 15:
        f.append(("OS011", "low", f"{size} learners: speaking time per learner will be low; use breakout rooms most of the time"))
    return f


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("setup", help="setup JSON, or - for stdin")
    a = ap.parse_args()
    try:
        fh = sys.stdin if a.setup == "-" else open(a.setup, encoding="utf-8")
        with fh:
            s = json.load(fh)
        if not isinstance(s, dict):
            raise ValueError("JSON must be an object")
        f = check(s)
    except (OSError, ValueError, TypeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"Setup for {s.get('class_size', '?')} {s.get('age_group', 'learners')}: {len(f)} finding(s)")
    order = {"high": 0, "medium": 1, "low": 2}
    for code, sev, msg in sorted(f, key=lambda x: (order[x[1]], x[0])):
        print(f"{code} [{sev}] {msg}")
    if not f:
        print("OK: connection, audio, platform and policies fit the class")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
