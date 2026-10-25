---
name: l2-error-correction-strategy-advisor
description: "Advise language teachers on correcting learner errors: mistakes vs errors vs fossilised errors, what to correct first (global, target, frequent, offensive), immediate vs delayed correction by lesson stage, the six oral corrective feedback types (explicit correction, recast, clarification request, metalinguistic feedback, elicitation, repetition) with examples and research-based guidance on uptake and repair, making recasts noticeable, non-verbal techniques, delayed correction activities, learner preferences, and written correction. Analyses a class error log by category and student, groups errors by pattern, finds persistent (possibly fossilised) errors repeated across dates, and suggests the correction strategy for each category. Use when a teacher asks how or when to correct errors, keeps an error log, or has learners who repeat the same mistakes."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# L2 Error Correction Strategy Advisor

Good correction is selective and matched to the error, the learner and the moment. The skill advises on what,
when and how to correct; `scripts/error_log.py` turns a class error log into priorities and persistent-error
alerts.

## Trigger Conditions

Activate this skill when the user:
- Asks how, when or how much to correct learners
- Has learners who repeat the same errors (fossilisation)
- Keeps an error log and wants patterns and priorities
- Plans delayed error correction after a speaking activity

Classroom feedback moves in detail: [recast-and-prompt-technique-coach](../recast-and-prompt-technique-coach/SKILL.md).
Written feedback: [student-writing-feedback-generator](../student-writing-feedback-generator/SKILL.md).
Pronunciation: [pronunciation-feedback-for-teachers-tool](../pronunciation-feedback-for-teachers-tool/SKILL.md).

## Workflow

```
1. DIAGNOSE -> slip, error, attempt or fossilised? global or local? (references/when-to-correct.md)
2. PRIORITY -> blocks meaning > lesson target > frequent/persistent > register
3. TIMING   -> immediate (accuracy, clarification, pronunciation) or delayed (fluency)
4. TYPE     -> prompt or reformulation (references/corrective-feedback-types.md)
5. LOG      -> student, date, error, correction, category, pattern
6. ANALYSE  -> python scripts/error_log.py errors.csv     (weekly)
7. PLAN     -> delayed-correction slot, targeted mini-lessons for persistent patterns
```

## Quick guide

| Situation | Do |
|-----------|----|
| Drill or controlled practice | Correct immediately; prompt self-correction first |
| Discussion, role play | Note errors; 5-10 min delayed correction afterwards |
| Learner knows the rule | Repetition with rising intonation, or a gesture |
| New, complex form | Explicit correction + brief explanation |
| Same error 3+ times on different days | Explicit focus: rule, examples, personal error log, targeted practice |

## Output Format

For advice: the recommended approach for the situation, with example teacher language for each step. For an error
log: the `error_log.py` summary, priorities for the class, a delayed-correction board for next lesson (4-6
sentences, anonymous) and a plan for each persistent pattern.

## Scripts

```bash
python scripts/error_log.py errors.csv [--student Ana] [--top 5]
```
Columns: student, date, error, correction, category, pattern (optional). Exit codes: 0 printed, 2 read error or
missing columns.

## Additional Resources

| File | Content |
|------|---------|
| [corrective-feedback-types.md](references/corrective-feedback-types.md) | Six feedback types with examples, research summary, noticeable recasts, choosing a type, uptake and repair, non-verbal techniques |
| [when-to-correct.md](references/when-to-correct.md) | Mistakes vs errors vs fossilisation, priorities, immediate vs delayed by stage, delayed techniques, learner factors, written errors, tracking |
