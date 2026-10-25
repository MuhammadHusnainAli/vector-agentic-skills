---
name: language-placement-test-builder
description: "Build, analyse and calibrate language placement tests: a blueprint (levels to separate, sections, length, items per level, item types, delivery, parallel forms), level-targeted grammar, vocabulary, reading and listening items, a short speaking interview with probes and a level-up push, cut-score setting (contrasting groups, borderline group, modified Angoff, empirical adjustment), SEM-based borderline bands and placement validation. Runs classical item analysis from response data (facility, upper-lower discrimination, distractor analysis, KR-20 reliability, items easier than lower-level items) and places learners from scores and cut scores, flagging borderline learners for an interview. Use when creating a placement test for a language school or programme, checking whether test items work, or setting and reviewing cut scores."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Language Placement Test Builder

A placement test should separate the levels a school actually runs, quickly and reliably, and send unclear cases
to a short interview. `scripts/item_analysis.py` shows which items work; `scripts/placement_cutoffs.py` places
learners and flags borderline scores.

## Trigger Conditions

Activate this skill when the user:
- Needs a placement test for a language school, university or company programme
- Has trial data and wants to know which items to keep
- Sets or reviews cut scores between levels
- Has too many learners changing class after the first week

Speaking interview rubric: [speaking-rubric-builder](../speaking-rubric-builder/SKILL.md). Classroom quizzes:
[language-quiz-generator](../language-quiz-generator/SKILL.md). Level descriptions:
[cefr-aligned-syllabus-builder](../cefr-aligned-syllabus-builder/SKILL.md).

## Workflow

```
1. BLUEPRINT -> levels, sections, items per level, interview (references/placement-test-design.md)
2. WRITE     -> 8-12 items per level, easy to hard; parallel forms; answer key; level tags
3. PILOT     -> 30+ learners across levels
4. ANALYSE   -> python scripts/item_analysis.py responses.csv     (KEY and LEVEL rows)
5. REVISE    -> fix negative / weak discrimination, dead distractors, mis-levelled items
6. CUTS      -> contrasting groups or borderline group; SEM band
7. PLACE     -> python scripts/placement_cutoffs.py scores.csv --cuts A1:0 A2:15 B1:28 B2:40 --sem 2.5
8. VALIDATE  -> class changes in week 2, teacher feedback, end-of-course results
```

## Review Codes (item_analysis.py)

| Code | Severity | Problem |
|------|----------|---------|
| IA001 | high | Negative discrimination (miskeyed or ambiguous) |
| IA002 | medium | Discrimination below 0.20 |
| IA003 | medium | Facility above 0.90 or below 0.20 |
| IA004 | low | Distractor not working or attracting the top group |
| IA005 | low | Item easier than the average item one level below |

How to read the statistics and fix items: [item-analysis-guide.md](references/item-analysis-guide.md).

## Output Format

The blueprint table, the items by level with key and level tags, the interview guide with level probes and a
rating rubric, and the cut-score method. For analyses, the item table, reliability and a list of items to keep,
revise or drop with reasons.

## Scripts

```bash
python scripts/item_analysis.py responses.csv
```
First column student id; one column per item; a KEY row (required) and a LEVEL row (optional). Exit codes:
0 no high findings, 1 high findings, 2 read error or no KEY row.

```bash
python scripts/placement_cutoffs.py scores.csv --cuts A1:0 A2:15 B1:28 B2:40 C1:50 [--sem 2]
```
Columns: student, score. Exit codes: 0 placed, 2 read error or bad cut scores.

## Additional Resources

| File | Content |
|------|---------|
| [placement-test-design.md](references/placement-test-design.md) | Blueprint, content by level, item types, speaking interview, cut-score methods, SEM, validation |
| [item-analysis-guide.md](references/item-analysis-guide.md) | Statistics and good ranges, diagnosing problem items, improving reliability, analysis workflow |
