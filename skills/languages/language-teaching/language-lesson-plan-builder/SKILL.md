---
name: language-lesson-plan-builder
description: "Build and review staged language lesson plans for ESL/EFL and other languages: class profile, a main aim written as a learner outcome, subsidiary aims, target language analysis, stages with stage aims, timings, interaction patterns and procedure, materials, anticipated problems with solutions and a board plan. Picks a lesson shape (PPP, TTT, guided discovery, receptive or productive skills, TBL, ESA) from the aim, turns an outline into a timed Markdown plan, and checks plans for teacher-centred or vague aims, timings that do not add up, missing stage aims, too much teacher-fronted time, tasks with no feedback, language lessons with no freer practice and over-long stages. Use when planning a language lesson, preparing a CELTA/TESOL teaching practice plan, or reviewing a colleague's plan."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Language Lesson Plan Builder

A good plan answers three questions: what will learners be able to do at the end, how does each stage get them
there, and what could go wrong. `scripts/plan_scaffold.py` turns an outline into a timed plan;
`scripts/plan_check.py` reviews a plan for the faults trainers flag most often.

## Trigger Conditions

Activate this skill when the user:
- Wants a lesson plan for a language class (any language, any level)
- Is writing a CELTA, Trinity CertTESOL or in-service teaching practice plan
- Has a plan whose timing, aims or staging feels wrong
- Asks which lesson shape to use for a grammar, vocabulary, skills or task-based lesson

Detailed lesson shapes: [ppp-lesson-structure-planner](../ppp-lesson-structure-planner/SKILL.md),
[task-based-language-lesson-designer](../task-based-language-lesson-designer/SKILL.md). Activities:
[communicative-activity-generator](../communicative-activity-generator/SKILL.md),
[warm-up-icebreaker-generator](../warm-up-icebreaker-generator/SKILL.md). Mixed-level classes:
[language-lesson-differentiation-planner](../language-lesson-differentiation-planner/SKILL.md).

## Workflow

```
1. PROFILE  -> level (CEFR), number, ages, L1s, previous lesson, needs
2. AIM      -> one main aim as a learner outcome; 1-2 subsidiary aims
3. SHAPE    -> choose PPP / TTT / skills / TBL from the aim (references/lesson-shapes.md)
4. STAGES   -> name, stage aim, minutes, interaction, procedure, materials
5. LANGUAGE -> meaning, form, pronunciation, CCQs for each target item
6. BUILD    -> python scripts/plan_scaffold.py lesson.json > plan.md
7. CHECK    -> python scripts/plan_check.py lesson.json   (fix every high finding)
8. PROBLEMS -> anticipated problems with concrete solutions; flexi stage; board plan
```

Ask for anything missing from step 1 before writing; a plan for "intermediate adults" with no other detail is
generic. When the user gives only a topic and level, propose an aim and a shape and say so.

## Writing the main aim

| Weak | Better |
|------|--------|
| To teach the present perfect | By the end, learners will be able to ask and answer about life experiences using present perfect + ever/never |
| Ss will understand phrasal verbs | Learners will be able to use six travel phrasal verbs in a hotel check-in role play |
| Reading | Learners will have practised reading for gist and detail in a news article about plastic waste |

Full guidance on aims, stage aims, interaction codes, timing and anticipated problems:
[lesson-plan-anatomy.md](references/lesson-plan-anatomy.md).

## Review Codes (plan_check.py)

| Code | Severity | Problem |
|------|----------|---------|
| LP001 | high | Main aim missing or describes the teacher |
| LP002 | high | Stage minutes do not add up to the lesson length |
| LP003 | medium | Main aim uses understand / know / learn |
| LP004 | medium | Stage with no stage aim |
| LP005 | medium | Teacher-fronted time above 40% |
| LP006 | medium | Pair or group task with no feedback after it |
| LP007 | medium | Language lesson with no freer practice |
| LP008 | low | Stage over 20 minutes |
| LP009 | low | No anticipated problems |

## Output Format

Deliver: class profile, aims, target language analysis (for language lessons), the stage table from
`plan_scaffold.py` (time, stage, stage aim, interaction, procedure, materials), anticipated problems and
solutions, board plan. Include instructions and ICQs for the main tasks. Then the `plan_check.py` result.

## Scripts

```bash
python scripts/plan_scaffold.py lesson.json > plan.md
```
Keys: title, level, minutes, learners, main_aim, subsidiary_aims, stages (name, aim, minutes, interaction,
procedure, materials), problems (problem, solution). Stages without minutes share the remaining time. Exit codes:
0 written, 1 stages exceed the lesson length, 2 read or JSON error.

```bash
python scripts/plan_check.py lesson.json
```
Same JSON. Exit codes: 0 no high findings, 1 high findings, 2 read or JSON error.

## Additional Resources

| File | Content |
|------|---------|
| [lesson-plan-anatomy.md](references/lesson-plan-anatomy.md) | Plan components, writing main and stage aims, interaction codes, timing, anticipated problems |
| [lesson-shapes.md](references/lesson-shapes.md) | PPP, TTT, guided discovery, receptive and productive skills, TBL and ESA shapes with timings; choosing a shape |
