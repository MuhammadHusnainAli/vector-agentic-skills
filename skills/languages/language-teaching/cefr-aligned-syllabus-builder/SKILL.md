---
name: cefr-aligned-syllabus-builder
description: "Build language course syllabuses aligned to the CEFR (A1-C2, plus levels, Companion Volume 2020): entry and exit levels, guided learning hours and course length (with an L1-distance adjustment), syllabus type (topic, functional-notional, task-based, skills-based, multi-strand), unit-by-unit can-do outcomes, grammar from a core inventory by level, vocabulary, functions, pronunciation, balance of reception, production, interaction and mediation, recycling and assessment points. Checks a syllabus for units without can-do statements, core grammar for the level not covered, items above the course level, skills missing from most units and units with no vocabulary or functions. Use when designing or reviewing a general English (or other language) course, mapping a coursebook to the CEFR, or estimating hours to reach a level."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# CEFR-Aligned Syllabus Builder

A CEFR-aligned syllabus starts from what learners must be able to do at the exit level, then maps language,
skills and assessment to those outcomes unit by unit. `scripts/cefr_hours.py` estimates the hours needed;
`scripts/syllabus_check.py` checks coverage and alignment against the core inventory.

## Trigger Conditions

Activate this skill when the user:
- Designs a language course or syllabus for a level or a level range
- Wants to align a course or coursebook to the CEFR
- Asks how many hours or weeks learners need to reach B1, B2, etc.
- Reviews a syllabus for gaps or items at the wrong level

Ordering units and term pacing: [language-course-scope-sequence-planner](../language-course-scope-sequence-planner/SKILL.md).
Outcomes: [can-do-statement-writer](../can-do-statement-writer/SKILL.md). US frameworks:
[actfl-proficiency-curriculum-mapper](../actfl-proficiency-curriculum-mapper/SKILL.md).

## Workflow

```
1. LEVELS   -> entry level (placement data) and exit level
2. HOURS    -> python scripts/cefr_hours.py --from A2 --to B1 --hours-per-week 6 [--distance far]
3. TYPE     -> topic / functional / task-based / skills-based / multi-strand
4. OUTCOMES -> can-do statements per unit across reception, production, interaction, mediation
5. LANGUAGE -> grammar (references/core-inventory-by-level.md), lexis, functions, pronunciation
6. SEQUENCE -> needs first, simple to complex, recycle every item later
7. ASSESS   -> formative per unit, progress tests, exit test at the exit level
8. CHECK    -> python scripts/syllabus_check.py syllabus.csv --level A2 --from A1
```

If the hours available are far below the estimate, say so plainly and propose either a lower exit level or a
partial-level outcome (e.g. "A2+ in speaking and listening").

## Review Codes (syllabus_check.py)

| Code | Severity | Problem |
|------|----------|---------|
| SY001 | high | Unit without a can-do statement |
| SY002 | medium | Core grammar item for the course level not covered |
| SY003 | medium | Grammar item above the course level |
| SY004 | medium | A skill in fewer than half the units |
| SY005 | low | Unit with no vocabulary or functions |

## Output Format

Course overview (levels, hours, weeks, syllabus type, materials), then a unit table: unit, topic, can-do
outcomes, grammar, vocabulary, functions, pronunciation, skills/modes, assessment. Include a recycling note and an
assessment calendar. Then the `syllabus_check.py` result with gaps explained (deliberate omissions are fine if
stated).

## Scripts

```bash
python scripts/cefr_hours.py --from A0|A1..C1 --to A1..C2 [--hours-per-week 6] [--weeks 30] [--distance near|medium|far]
```
Exit codes: 0 printed, 2 target not above start.

```bash
python scripts/syllabus_check.py syllabus.csv --level B1 [--from A2] [--inventory file.md]
```
Columns: unit, grammar, vocabulary, functions, can_do, skills. Exit codes: 0 no high findings, 1 high findings,
2 read error or bad CSV.

## Additional Resources

| File | Content |
|------|---------|
| [cefr-levels.md](references/cefr-levels.md) | Levels in brief, modes including mediation, competences, guided hours, building a syllabus, unit template |
| [core-inventory-by-level.md](references/core-inventory-by-level.md) | English grammar items by level with keywords used by `syllabus_check.py` |
