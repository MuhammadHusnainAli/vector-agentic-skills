---
name: dialogue-for-classroom-writer
description: "Write natural model dialogues for language classes that contain the target language, suit the level and sound spoken rather than written: situation, speakers' goals and a small complication, contractions, reactions and backchannels, discourse markers, repair and softening, adjacency pairs, register, turn and dialogue length by CEFR level, balanced roles for pair practice and diverse characters. Checks a dialogue for missing target phrases, unbalanced roles, turns too long for the level, full forms with no contractions, no natural spoken features and wrong length, and plans exploitation: prediction, gist and detail listening, noticing, drilling, disappearing and jumbled dialogues, substitution, role cards and recording. Use when a teacher needs a dialogue or conversation script for a lesson, a listening script to record, or wants a coursebook dialogue made more natural."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Dialogue for Classroom Writer

A model dialogue should do two jobs: present the target language in context and show how people really talk.
`scripts/dialogue_check.py` checks a draft for the target phrases, role balance, turn length for the level and
natural spoken features.

## Trigger Conditions

Activate this skill when the user:
- Needs a dialogue for a functional language lesson (ordering, booking, complaining, inviting)
- Wants a script to record for a listening task
- Has a stiff coursebook dialogue to rewrite
- Needs role-play material derived from a model dialogue

Listening tasks on the recording: [listening-task-builder](../listening-task-builder/SKILL.md). Role play
activities: [communicative-activity-generator](../communicative-activity-generator/SKILL.md).

## Workflow

```
1. SITUATION -> place, speakers, relationship (register), each speaker's goal, a small complication
2. TARGET    -> 3-6 phrases and where they naturally occur
3. DRAFT     -> opening -> purpose -> complication -> resolution -> closing
4. NATURAL   -> contractions, reactions, discourse markers for the level (references/natural-dialogue-features.md)
5. CHECK     -> python scripts/dialogue_check.py dialogue.txt --level A2 --target "Can I have" "How much"
6. READ      -> read aloud; cut anything nobody would say
7. EXPLOIT   -> listening tasks, drills, disappearing dialogue, role cards (references/dialogue-exploitation.md)
```

## Review Codes (dialogue_check.py)

| Code | Severity | Problem |
|------|----------|---------|
| DC001 | high | Target phrase missing |
| DC002 | high | Fewer than two speakers |
| DC003 | medium | One speaker has over 65% of the words |
| DC004 | medium | Turn too long for the level |
| DC005 | low | Full forms with no contractions |
| DC006 | low | No reactions, fillers or discourse markers |
| DC007 | low | Too few or too many turns for the level |

## Output Format

The dialogue in "Speaker: line" format with target phrases in bold, a one-line situation, then the
`dialogue_check.py` result and an exploitation plan (listening tasks, drill lines with stress marked,
practice steps, role cards for the freer stage).

## Scripts

```bash
python scripts/dialogue_check.py dialogue.txt [--level A2] [--target "Can I have" "How much"]
```
One turn per line as `Name: text`. Exit codes: 0 no high findings, 1 high findings, 2 read error.

## Additional Resources

| File | Content |
|------|---------|
| [natural-dialogue-features.md](references/natural-dialogue-features.md) | Spoken features by level, adjacency pairs, length by level, writing process, complications, register, representation |
| [dialogue-exploitation.md](references/dialogue-exploitation.md) | Lesson stages for a dialogue, disappearing and jumbled dialogues, role cards, recording tips |
