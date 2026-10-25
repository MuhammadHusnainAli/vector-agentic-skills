---
name: can-do-statement-writer
description: "Write and review can-do statements for language courses, units, lessons and learner self-assessment, CEFR or NCSSFL-ACTFL style: action (observable verb) + text or situation + level-specific conditions, learner ('I can') and descriptor ('Can') versions, progressions of one activity from A1 to C1, and coverage of reception, production, interaction and mediation. Includes a verb bank by mode and level and condition and text-type banks. Lints statements for teacher-centred phrasing, knowledge instead of use (learn, know, understand the passive), missing context, two skills in one statement, vague quality words, grammar items as outcomes, overlong statements and missing modes in a set. Use when writing unit outcomes, self-assessment checklists, portfolio descriptors or course objectives for a language programme."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Can-Do Statement Writer

A good can-do statement names something a learner can be seen doing with the language, in a context, with the
conditions that make it belong to one level. `scripts/cando_lint.py` checks statements and the mode balance of a
set.

## Trigger Conditions

Activate this skill when the user:
- Writes outcomes or objectives for a language course, unit or lesson
- Builds a self-assessment checklist or portfolio for learners
- Has objectives like "learn the present perfect" and wants them action-oriented
- Needs the same outcome written at several levels

Course mapping: [cefr-aligned-syllabus-builder](../cefr-aligned-syllabus-builder/SKILL.md),
[actfl-proficiency-curriculum-mapper](../actfl-proficiency-curriculum-mapper/SKILL.md). Lesson aims:
[language-lesson-plan-builder](../language-lesson-plan-builder/SKILL.md).

## Workflow

```
1. SCOPE    -> course, unit or lesson; level; framework (CEFR or ACTFL)
2. MODES    -> plan statements across reception, production, interaction, mediation
3. BUILD    -> verb (references/verb-bank.md) + text/situation + condition for the level
4. VERSIONS -> learner "I can" (simple wording) and descriptor "Can" (teacher/syllabus)
5. CHECK    -> python scripts/cando_lint.py statements.txt
6. LINK     -> each statement to an activity and an assessment task with criteria
```

## Review Codes (cando_lint.py)

| Code | Severity | Problem |
|------|----------|---------|
| CD001 | high | Not phrased as learner ability |
| CD002 | high | Knowledge (learn, know, understand + grammar) instead of use |
| CD003 | medium | No context |
| CD004 | medium | Two activities in one statement |
| CD005 | low | Vague quality word with no condition |
| CD006 | low | Over 30 words |
| CD007 | low | Grammar item as the outcome |
| CD008 | low | Set misses a mode |

Anatomy, level progressions, examples by mode, common faults with rewrites and classroom use:
[can-do-writing-guide.md](references/can-do-writing-guide.md).

## Output Format

A table: mode, learner statement, descriptor version, level, linked activity or assessment. For self-assessment
checklists add the scale "easily / with help / not yet". Then the `cando_lint.py` result.

## Scripts

```bash
python scripts/cando_lint.py statements.txt
```
One statement per line; numbering and bullets are stripped; lines starting with `#` are ignored. Exit codes:
0 no high findings, 1 high findings, 2 read error or no statements.

## Additional Resources

| File | Content |
|------|---------|
| [can-do-writing-guide.md](references/can-do-writing-guide.md) | Anatomy, learner vs descriptor versions, A1-C1 progressions, examples by mode, faults and fixes, using statements |
| [verb-bank.md](references/verb-bank.md) | Verbs by mode and level band, conditions by level, text types and situations, statement builder |
