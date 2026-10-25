---
name: language-course-scope-sequence-planner
description: "Plan the scope and sequence of a language course: what is covered and in which order, using sequencing principles (need first, frequency, simple to complex, prerequisites, contrast after both items, learnability, topic coherence, spiral), a recycling plan for every item, a scope and sequence chart, and pacing across a real term calendar with holidays, review lessons, assessment lessons and weighted units. Checks a sequence for items taught before their prerequisites, circular prerequisites, items never recycled and late recycling, prints a valid teaching order, and turns term dates into unit start and end dates. Use when ordering a syllabus or coursebook, planning a term or year, or fixing a course where items are taught once and forgotten."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Language Course Scope and Sequence Planner

Scope says what the course covers; sequence says when each item is introduced, recycled and assessed.
`scripts/sequence_check.py` finds ordering and recycling problems; `scripts/pacing.py` fits units to the real
term calendar.

## Trigger Conditions

Activate this skill when the user:
- Needs to order units or language items in a course
- Plans a term or year of lessons around holidays and tests
- Has a course where learners forget items because they are never revisited
- Adapts a coursebook's order to their learners

What to include at each level: [cefr-aligned-syllabus-builder](../cefr-aligned-syllabus-builder/SKILL.md).
Outcomes: [can-do-statement-writer](../can-do-statement-writer/SKILL.md).

## Workflow

```
1. SCOPE     -> outcomes, grammar, lexis, functions, skills for the course
2. ORDER     -> sequencing principles (references/scope-and-sequence.md); list prerequisites per item
3. RECYCLE   -> plan 2+ revisits per item in later units
4. CHECK     -> python scripts/sequence_check.py scope.csv --gap 3
5. PACE      -> python scripts/pacing.py --start ... --end ... --days mon wed fri --units 8 --holidays ... \
                    --review-every 3 --assessment 2
6. CHART     -> scope and sequence chart: unit, weeks, outcomes, language, skills, recycles, assessment
7. REVIEW    -> mid-term check against the pacing plan
```

## Review Codes (sequence_check.py)

| Code | Severity | Problem |
|------|----------|---------|
| SQ001 | high | Item taught before an item it requires, or prerequisite missing |
| SQ002 | high | Circular prerequisites |
| SQ003 | medium | Item never recycled |
| SQ004 | low | First recycling too late |

## Output Format

The scope and sequence chart, the pacing table with dates from `pacing.py`, a recycling map, the assessment
calendar, and the `sequence_check.py` result with how each finding was fixed.

## Scripts

```bash
python scripts/sequence_check.py scope.csv [--gap 3]
```
Columns: item, unit, requires (`;`-separated items), recycled_in (`;`-separated units). Exit codes: 0 no high
findings, 1 high findings, 2 read error or bad CSV.

```bash
python scripts/pacing.py --start 2026-09-07 --end 2026-12-18 --days mon wed fri (--units 8 | --weights 2 1 1 2) \
    [--holidays 2026-10-26:2026-10-30 2026-11-26] [--review-every 3] [--assessment 2]
```
Exit codes: 0 printed, 1 not enough lessons, 2 bad dates or arguments.

## Additional Resources

| File | Content |
|------|---------|
| [scope-and-sequence.md](references/scope-and-sequence.md) | Sequencing principles, recycling plan, chart template, pacing rules, multi-level programmes, common problems |
