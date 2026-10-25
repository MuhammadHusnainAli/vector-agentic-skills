---
name: online-language-teaching-setup-advisor
description: "Advise language teachers on setting up and teaching online: equipment priorities (connection and upload speed, headset microphone, headphones, front lighting, camera, backup), platform features that matter for language classes (breakout rooms, computer-audio sharing, whiteboard and annotation, chat, polls, recording, captions), complementary tools, safeguarding, consent and privacy for young learners and recordings, a first-lesson checklist, online lesson shapes, classroom activities adapted for video calls, one-to-one and young learner online teaching, participation strategies and asynchronous work. Checks a setup description for low upload bandwidth, missing safeguarding or recording consent, no breakout rooms for groups, built-in microphones, no audio sharing, mobile connections, backlighting, no whiteboard, no backup plan and oversized speaking classes. Use when a teacher is starting or improving online lessons, choosing equipment or a platform, or adapting activities for video calls."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Online Language Teaching Setup Advisor

Online language lessons depend on things a classroom takes for granted: clear audio, a stable connection, ways to
put learners in pairs, and safe policies. `scripts/setup_check.py` checks a setup against the class it must serve.

## Trigger Conditions

Activate this skill when the user:
- Starts teaching languages online (group or one-to-one) or moves a course online
- Asks what equipment, internet speed or platform they need
- Wants to adapt classroom activities to video calls
- Teaches children or teens online and needs safeguarding and consent guidance

Activities: [communicative-activity-generator](../communicative-activity-generator/SKILL.md) (use `--online`),
[warm-up-icebreaker-generator](../warm-up-icebreaker-generator/SKILL.md). Instructions:
[classroom-management-for-esl-coach](../classroom-management-for-esl-coach/SKILL.md).

## Workflow

```
1. CONTEXT  -> class size, ages, group or 1-to-1, live or blended, institution platform
2. CHECK    -> python scripts/setup_check.py setup.json
3. FIX      -> high findings first (bandwidth, safeguarding, consent) (references/setup-and-tools.md)
4. TEST     -> rehearse with a colleague: audio sharing, breakout rooms, whiteboard
5. ADAPT    -> lesson shape and activities for online (references/online-activities.md)
6. PREPARE  -> learner joining guide, tech check in lesson one, offline backup lesson
```

## Review Codes (setup_check.py)

| Code | Severity | Problem |
|------|----------|---------|
| OS001 | high | Upload under 1.5 Mbps |
| OS002 | high | Young learners or teens with no safeguarding policy |
| OS003 | high | Recording without consent |
| OS004 | medium | No breakout rooms for groups of 4+ |
| OS005 | medium | Built-in microphone |
| OS006 | medium | No computer-audio sharing |
| OS007 | medium | Mobile data as the main connection |
| OS008-OS011 | low | Backlight, no whiteboard, no backup plan, over 15 in a speaking class |

## Output Format

A prioritised setup plan (must fix, should fix, nice to have) with specific recommendations, a pre-lesson
checklist, and, if asked, an online version of a lesson with timings and tools per stage.

## Scripts

```bash
python scripts/setup_check.py setup.json
```
Keys: class_size, age_group, upload_mbps, download_mbps, connection, microphone, camera, light, platform
(breakout_rooms, screen_share_audio, whiteboard, chat, polls, recording), recording_lessons, recording_consent,
safeguarding_policy, backup_plan. Exit codes: 0 no high findings, 1 high findings, 2 read or JSON error.

## Additional Resources

| File | Content |
|------|---------|
| [setup-and-tools.md](references/setup-and-tools.md) | Equipment priorities, platform features, complementary tools, safeguarding and privacy, first-lesson preparation |
| [online-activities.md](references/online-activities.md) | Online lesson shape, adapted activities, one-to-one, young learners, participation, asynchronous work |
