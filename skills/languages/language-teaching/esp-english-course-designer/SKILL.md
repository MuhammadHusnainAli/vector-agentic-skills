---
name: esp-english-course-designer
description: "Design English for Specific Purposes (ESP) courses for professions and workplaces (medical and nursing, aviation, legal, hospitality, engineering, business): needs analysis (target situation, present situation, learning needs, means analysis) with practitioner interviews, task-list surveys rating frequency, importance and difficulty, triangulation with managers, can-do outcomes for core tasks, task- or genre-based syllabuses, authentic workplace materials, genre analysis of key interactions (e.g. SBAR nursing handover), performance assessment agreed with subject experts and course evaluation. Ranks surveyed tasks by frequency x importance x difficulty into core, secondary and low bands, flags tasks respondents disagree on, and compares priorities by role. Use when a teacher or training manager plans an English course for a specific job, sector or company, or needs a needs-analysis survey."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# ESP English Course Designer

An ESP course is only as good as its needs analysis: it teaches the tasks learners actually do, in the language
those tasks need. `scripts/needs_analysis.py` turns a task-list survey into course priorities.

## Trigger Conditions

Activate this skill when the user:
- Plans English training for a profession, sector or company
- Needs a needs-analysis survey or interview guide
- Has survey results and wants course priorities
- Wants a syllabus built around workplace tasks and genres

Academic purposes: [academic-english-eap-course-planner](../academic-english-eap-course-planner/SKILL.md).
Task design: [task-based-language-lesson-designer](../task-based-language-lesson-designer/SKILL.md). Outcomes:
[can-do-statement-writer](../can-do-statement-writer/SKILL.md).

## Workflow

```
1. CONTEXT  -> sector, roles, sponsor goals, hours, group, current level (references/esp-course-design.md)
2. TASKS    -> interview practitioners; draft 10-25 target tasks
3. SURVEY   -> frequency, importance, difficulty (1-5) per task; learners and managers
4. RANK     -> python scripts/needs_analysis.py survey.csv --by-role
5. ANALYSE  -> genres and interactions for core tasks; collect authentic materials
6. DESIGN   -> can-do outcomes, task/genre syllabus, sequence, materials
7. ASSESS   -> workplace-like performance tasks with criteria agreed with experts
8. EVALUATE -> learner and sponsor feedback; real-task performance
```

## Output Format

Needs analysis summary (sources, methods, ranked task table, disagreements), course outline (outcomes, units by
core task, language and genre focus, materials, hours), a sample unit, and the assessment plan.

## Scripts

```bash
python scripts/needs_analysis.py survey.csv [--by-role]
```
Columns: respondent, task, frequency, importance, difficulty (1-5), role (optional). Exit codes: 0 printed,
2 read error or values outside 1-5.

## Additional Resources

| File | Content |
|------|---------|
| [esp-course-design.md](references/esp-course-design.md) | Needs analysis components and methods, survey design, course design steps, genre analysis example, ESP fields, teacher's role |
