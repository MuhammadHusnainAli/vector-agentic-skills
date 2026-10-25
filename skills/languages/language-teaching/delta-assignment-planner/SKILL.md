---
name: delta-assignment-planner
description: "Plan and check Cambridge Delta assignments: the three modules (exam, Module 2 professional practice with PDA and LSAs, Module 3 specialism or management), LSA components (background essay, lesson plan and commentary, observed lesson, post-lesson evaluation), a Module 3 structure, a five-week LSA timeline, background essay structure with matched problem-cause-solution-rationale tables, using sources, core reading by area and common reasons assignments fall short. Counts words per section of a Markdown draft against limits (excluding references and appendices, optionally tables and block quotes) and cross-checks author-date citations with the reference list (cited but not listed, listed but not cited, year mismatches, quotations without page numbers). Use when a teacher is preparing a Delta LSA, PDA or Module 3 assignment, structuring a background essay, or checking word counts and references before submission."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Delta Assignment Planner

Delta assignments succeed when the analysis is precise, the learner problems come from real learners, every
approach is justified from reading, and the lesson follows from the essay. `scripts/word_count.py` checks section
lengths; `scripts/citation_check.py` checks citations against the reference list.

## Trigger Conditions

Activate this skill when the user:
- Is preparing a Delta Module 2 LSA, PDA or a Module 3 assignment
- Needs an outline for a background essay on a language system or skill
- Wants to check word counts per section or the reference list before submission
- Asks what Delta modules involve or how to plan their time

Initial training: [tefl-celta-prep-tutor](../tefl-celta-prep-tutor/SKILL.md). Course design for Module 3:
[esp-english-course-designer](../esp-english-course-designer/SKILL.md),
[academic-english-eap-course-planner](../academic-english-eap-course-planner/SKILL.md).

## Workflow

```
1. FOCUS     -> area, level, learners; agree it with the tutor
2. DATA      -> learner errors and samples for the problems section
3. OUTLINE   -> introduction, analysis, problems, approaches, conclusion (references/lsa-essay-structure.md)
4. DRAFT     -> problems and solutions as matched pairs with rationale and sources
5. COUNT     -> python scripts/word_count.py essay.md --limit "Analysis=600-800" --total 2000-2500
6. CITE      -> python scripts/citation_check.py essay.md
7. LESSON    -> plan and commentary that follow from the essay; post-lesson evaluation
```

Do not write the assignment for the candidate: Delta work must be the candidate's own. Help with structure,
feedback on drafts, analysis checks, reading suggestions and checking tools, and say so if asked to produce
submission text.

## Script Codes (citation_check.py)

| Code | Severity | Problem |
|------|----------|---------|
| CI001 | high | Cited but not in the reference list |
| CI002 | medium | In the reference list but never cited |
| CI003 | medium | Citation year differs from the reference list |
| CI004 | low | Direct quotation without a page number |

## Scripts

```bash
python scripts/word_count.py draft.md [--limit "Title=min-max" ...] [--total min-max] [--no-tables] [--no-quotes]
```
Exit codes: 0 within limits, 1 a section or the total is outside its limit, 2 read error or bad limit.

```bash
python scripts/citation_check.py draft.md
```
Needs a `# References` or `# Bibliography` heading. Exit codes: 0 no high findings, 1 high findings, 2 read error
or no reference list.

## Additional Resources

| File | Content |
|------|---------|
| [delta-modules.md](references/delta-modules.md) | Modules, LSA components and typical lengths, Module 3 structure, LSA timeline, common shortfalls |
| [lsa-essay-structure.md](references/lsa-essay-structure.md) | Essay outline with shares, problem-solution tables, using sources, core reading by area, style |
