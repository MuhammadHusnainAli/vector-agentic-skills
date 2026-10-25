---
name: classroom-management-for-esl-coach
description: "Coach ESL/EFL teachers in classroom management: the instruction sequence (attention, group first, graded imperatives, demonstration, ICQs, hand out, start, check), ICQ examples, online instructions, routines for the first weeks (class agreement, L1 use, phones, lateness, homework, seating), strategies for L1 use in tasks, dominant and quiet learners, mixed levels, large classes, fast finishers, low motivation, disruptive young learners and teens, cultural expectations, classroom language to teach early and teacher presence. Checks planned instructions for length, missing ICQs, useless ICQs like 'Do you understand?', no demonstration, long sentences, filler and missing grouping or timing, and builds seating plans that keep named learners apart, seat learners who need the front, mix first languages and alternate stronger and weaker learners. Use when a teacher struggles with instructions, behaviour, L1 use, participation or seating."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Classroom Management for ESL Coach

Most management problems in language classes start with unclear instructions, unplanned routines or poor seating.
`scripts/instruction_check.py` checks planned instructions; `scripts/seating_plan.py` builds a seating plan that
respects constraints and mixes L1s.

## Trigger Conditions

Activate this skill when the user:
- Says learners do not understand instructions or start tasks wrongly
- Has learners who speak L1 in tasks, dominate, stay silent or disrupt
- Starts a new class and wants routines and a classroom agreement
- Needs a seating plan for pairs or groups

Mixed levels: [language-lesson-differentiation-planner](../language-lesson-differentiation-planner/SKILL.md).
Children: [young-learner-esl-activity-generator](../young-learner-esl-activity-generator/SKILL.md). Online:
[online-language-teaching-setup-advisor](../online-language-teaching-setup-advisor/SKILL.md).

## Workflow

```
1. DIAGNOSE -> what happens, when, with whom; class level, size, age
2. INSTRUCT -> script instructions and ICQs (references/giving-instructions.md)
3. CHECK    -> python scripts/instruction_check.py instructions.txt --level A2
4. ROUTINES -> agreement, signals, L1 policy, phones, lateness (references/routines-and-behaviour.md)
5. SEATING  -> python scripts/seating_plan.py class.csv --size 2
6. REVIEW   -> try for two weeks; keep what works; adjust
```

## Coaching approach

Ask what the teacher has tried; give two or three concrete strategies, with the exact words to say; suggest a
small experiment and how to tell if it worked. Rewrite any instructions the teacher shares, at the class level,
with a demonstration and ICQs.

## Review Codes (instruction_check.py)

| Code | Severity | Problem |
|------|----------|---------|
| IC001 | medium | Too long for the level |
| IC002 | medium | No ICQs |
| IC003 | medium | ICQ that checks nothing |
| IC004 | medium | No demonstration or example |
| IC005 | low | Long sentence for the level |
| IC006 | low | Filler words |
| IC007 | low | No grouping or time limit |

## Scripts

```bash
python scripts/instruction_check.py instructions.txt [--level A2]
```
Instructions first, then ICQs as lines ending in "?" (answers in brackets). Exit codes: 0 no medium findings,
1 medium findings, 2 read error or empty input.

```bash
python scripts/seating_plan.py class.csv [--size 2] [--seed 1]
```
Columns: name, level, l1, keep_apart (`;`-separated names), front (y). Exit codes: 0 plan printed, 1 a keep-apart
constraint could not be met, 2 read error.

## Additional Resources

| File | Content |
|------|---------|
| [giving-instructions.md](references/giving-instructions.md) | Instruction sequence, graded language, ICQs by task, demonstrations, online instructions, planning |
| [routines-and-behaviour.md](references/routines-and-behaviour.md) | First-week routines, common challenges and strategies, escalation for young learners, classroom language, teacher presence |
