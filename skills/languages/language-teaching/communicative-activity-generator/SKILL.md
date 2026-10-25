---
name: communicative-activity-generator
description: "Generate communicative language-class activities matched to level, skill, class size, time, preparation, online or face-to-face delivery and target language: information gaps, find someone who, role plays with goal-and-conflict role cards, jigsaw reading, ranking and pyramid discussions, dictogloss, running dictation, taboo, mysteries, surveys, debates and more from a 38-activity bank. Adapts frames to the target grammar or vocabulary, writes A/B cards and role cards, and covers setup, ICQs, monitoring, content-then-language feedback, large classes, fixed seating and breakout rooms. Use when a teacher needs a speaking or practice activity, wants freer practice for a grammar point, or needs ideas for a specific class size or online lesson."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Communicative Activity Generator

A communicative activity gives learners a reason to talk: a gap to close and an outcome to reach.
`scripts/activity_picker.py` filters the bank in [activity-bank.md](references/activity-bank.md) by level,
skill, class size, time, preparation, online use and language focus; the skill then adapts the chosen frame and
writes the materials.

## Trigger Conditions

Activate this skill when the user:
- Needs a speaking activity, freer practice or fluency task for a language class
- Asks for an activity for a specific grammar point, vocabulary set, level or class size
- Teaches online and needs activities that work in breakout rooms
- Has learners who "don't talk" in discussions

Warmers: [warm-up-icebreaker-generator](../warm-up-icebreaker-generator/SKILL.md). Full task cycle:
[task-based-language-lesson-designer](../task-based-language-lesson-designer/SKILL.md). Games for word lists:
[vocabulary-game-generator](../vocabulary-game-generator/SKILL.md).

## Workflow

```
1. CLASS     -> level, class size, time, room or online, target language
2. PICK      -> python scripts/activity_picker.py --level B1 --skill speaking --minutes 15 --students 12
3. ADAPT     -> fit the frame to the target language (references/running-activities.md)
4. MATERIALS -> A/B cards, role cards (goal, conflict, constraint), prompt cards, answer key
5. SETUP     -> grouping, instructions, demo, ICQs, materials, timer
6. FEEDBACK  -> content first, then 4-6 language points, then one pronunciation point
```

Offer two or three options from the picker with a one-line reason each, then build the one the teacher picks
(or the best fit if they asked for one).

## Activity output

For the chosen activity give:

| Part | Content |
|------|---------|
| Aim | Fluency / accuracy practice of the target language in a context |
| Time and grouping | Minutes; pairs, groups, mingle |
| Materials | Cards or prompts written in full, ready to copy |
| Instructions | 3-5 short sentences the teacher says, plus a demo |
| ICQs | 2-3 questions with answers |
| Monitoring focus | What language to listen for |
| Feedback | Content question, language points, extension for fast finishers |
| Variations | Easier, harder, online |

Setup, monitoring, information-gap and role-card design, and class-size adjustments:
[running-activities.md](references/running-activities.md).

## Scripts

```bash
python scripts/activity_picker.py --level B1 --skill speaking --minutes 15 --students 12 [--online] \
    [--prep none|low|medium|high] [--grouping pairs] [--focus conditionals] [--show 5] [--bank file.md]
```
Teachers can add their own activities as rows in the bank (same columns) or pass `--bank`. Exit codes:
0 matches, 1 nothing matches, 2 bank unreadable or bad level.

## Additional Resources

| File | Content |
|------|---------|
| [activity-bank.md](references/activity-bank.md) | 38 activities with skills, levels, grouping, minimum class size, time, prep, online use, language focus and procedure |
| [running-activities.md](references/running-activities.md) | What makes an activity communicative, adapting frames, information gaps, role cards, setup, monitoring, feedback, class-size adjustments |
