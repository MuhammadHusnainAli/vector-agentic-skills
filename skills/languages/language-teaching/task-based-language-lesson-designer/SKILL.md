---
name: task-based-language-lesson-designer
description: "Design task-based language teaching (TBLT) lessons that pass Ellis's task criteria (focus on meaning, an information, opinion or reasoning gap, learners' own resources, a non-linguistic outcome) and follow the Willis framework: pre-task, task, planning, report and language focus with analysis and practice. Covers the six task types (listing, ordering, comparing, problem solving, sharing experiences, creative) with examples from A1 to C1, real-world vs pedagogic tasks, task complexity, focus on form, and turning coursebook exercises into tasks. Checks a lesson for disguised grammar exercises, missing gap or outcome, pre-teaching the structure, missing or misordered stages and no planning time. Use when planning a TBL lesson, converting an exercise into a task, or checking whether an activity is really a task."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Task-Based Language Lesson Designer

In task-based lessons learners first use whatever language they have to reach an outcome, then study the
language they needed. `scripts/task_check.py` tests the task against Ellis's four criteria and the lesson against
the Willis cycle.

## Trigger Conditions

Activate this skill when the user:
- Wants a task-based or TBL lesson, or a real-world task for adults or ESP learners
- Asks "is this a task or an exercise?"
- Wants to turn a coursebook exercise into a communicative task
- Has a fluent but inaccurate class, or a class that does not speak in "discussions"

Other shapes: [ppp-lesson-structure-planner](../ppp-lesson-structure-planner/SKILL.md). Full plan:
[language-lesson-plan-builder](../language-lesson-plan-builder/SKILL.md). Task ideas:
[communicative-activity-generator](../communicative-activity-generator/SKILL.md).

## Workflow

```
1. GOAL      -> what learners will produce: decision, list, plan, solution, product
2. TYPE      -> listing / ordering / comparing / problem solving / sharing / creative (references/task-types.md)
3. GAP       -> information, opinion or reasoning; who holds what
4. PRE-TASK  -> topic, topic vocabulary, model recording, outcome stated (no grammar pre-teaching)
5. CYCLE     -> task (time limit) -> planning -> report
6. FOCUS     -> analysis of a model/transcript + practice + errors from the task
7. CHECK     -> python scripts/task_check.py tbl.json
8. REPEAT    -> optional task repetition with new partners
```

## Task or exercise?

| Criterion | Task | Exercise |
|-----------|------|----------|
| Meaning focus | Agree on a class trip | Make five sentences with *going to* |
| Gap | Each has half the timetable | Everyone has the same text |
| Own resources | Any language | The structure on the board |
| Outcome | A plan, a ranking, a decision | A completed worksheet |

Framework detail, timings, focus-on-form techniques, complexity factors and common faults:
[willis-framework.md](references/willis-framework.md).

## Review Codes (task_check.py)

| Code | Severity | Problem |
|------|----------|---------|
| TB001 | high | Instructions prescribe a structure: an exercise, not a task |
| TB002 | high | No information, opinion or reasoning gap |
| TB003 | high | No non-linguistic outcome |
| TB004 | medium | Pre-task teaches the target structure |
| TB005 | medium | Willis stage missing |
| TB006 | medium | Language focus before the task |
| TB007 | low | No planning time or task repetition |
| TB008 | low | Stage without a time limit |

## Output Format

Deliver: task goal and outcome, task type and gap, materials (role cards, split information), instructions with
ICQs, staged plan (pre-task, task, planning, report, language focus) with times and teacher roles, likely
language for the language focus, and a complexity adjustment for stronger and weaker groups. Then the
`task_check.py` result.

## Scripts

```bash
python scripts/task_check.py tbl.json
```
Keys: title, instructions, gap, outcome, stages (name, minutes, procedure). Prints the Ellis criteria and the
stage sequence. Exit codes: 0 no high findings, 1 high findings, 2 read or JSON error.

## Additional Resources

| File | Content |
|------|---------|
| [willis-framework.md](references/willis-framework.md) | Ellis criteria, Willis cycle stage by stage, focus on form, task complexity, common faults |
| [task-types.md](references/task-types.md) | Six task types with A1-C1 examples, outcomes and likely language; real-world vs pedagogic; instructions; converting exercises |
