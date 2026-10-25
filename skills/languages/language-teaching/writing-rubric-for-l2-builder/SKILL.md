---
name: writing-rubric-for-l2-builder
description: "Build analytic and holistic rubrics for second-language writing and score scripts with them: criteria (task achievement and content, organisation and coherence, lexical range and accuracy, grammatical range and accuracy, register), band descriptors, a sample 0-5 B1 email rubric, genre-specific checks (emails, letters, essays, reports, reviews, stories), word counts by level, a scoring procedure with an off-task gate, and feedback from jagged profiles. Profiles a learner's text (word count against the task, paragraphs, sentence length, linker variety and overuse, lexical variety, repetition, informal language in formal tasks) and combines criterion bands into weighted totals and levels, flagging off-task scripts, jagged profiles and borderline totals. Use when designing a writing test or rubric, marking L2 essays or emails consistently, or preparing feedback on learner writing."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Writing Rubric for L2 Builder

L2 writing is scored fairly when the rubric matches the task and genre, every criterion has observable
descriptors, and scorers follow a fixed procedure. `scripts/essay_profile.py` gives objective data on a text;
`scripts/writing_score.py` turns criterion bands into totals and levels.

## Trigger Conditions

Activate this skill when the user:
- Needs a rubric or marking scheme for a writing task in a language class or test
- Is marking learner essays, emails or reports and wants consistency
- Wants to convert band scores to a total, percentage or level
- Needs data on a script (length, paragraphing, linkers) to support marking

Rubric checks and rater agreement: [speaking-rubric-builder](../speaking-rubric-builder/SKILL.md) (its
`rubric_check.py` and `rater_agreement.py` work for writing rubrics too). Feedback comments:
[student-writing-feedback-generator](../student-writing-feedback-generator/SKILL.md).

## Workflow

```
1. TASK      -> genre, reader, purpose, points to cover, word count for the level
2. CRITERIA  -> 3-5 analytic criteria; genre-specific checks (references/writing-criteria.md)
3. BANDS     -> descriptors per band, from the expected standard outwards
4. PROFILE   -> python scripts/essay_profile.py essay.txt --min 140 --max 190 [--formal]
5. SCORE     -> task first (off-task = 0), then each criterion with evidence
6. TOTAL     -> python scripts/writing_score.py scores.csv --cuts A2:40 B1:60 B2:80 [--weights task:2]
7. FEEDBACK  -> one strength and one target per criterion; focus on the jagged criterion
```

## Profile Codes (essay_profile.py)

| Code | Severity | Finding |
|------|----------|---------|
| WP001 | high | Under the minimum, or more than 10% over the maximum |
| WP002 | medium | One paragraph for over 120 words |
| WP003 | medium | Fewer than 3 different linkers |
| WP004 | low | One linker used 4+ times |
| WP005 | low | Informal language in a formal task |
| WP006 | low | Content word repeated 5+ times |

## Output Format

The task prompt, the rubric (criteria x bands), the scoring procedure, and for marked scripts: bands per criterion
with evidence, total and level from `writing_score.py`, and feedback (strength and target per criterion).

## Scripts

```bash
python scripts/essay_profile.py essay.txt [--min 140] [--max 190] [--formal]
```
Exit codes: 0 no high findings, 1 high findings (length), 2 read error or empty text.

```bash
python scripts/writing_score.py scores.csv [--max-band 5] [--weights task:2 lexis:1] [--cuts B1:60 B2:80] [--gate task]
```
Columns: student, then one column per criterion. Exit codes: 0 scored, 2 read error, bad weights or out-of-range
score.

## Additional Resources

| File | Content |
|------|---------|
| [writing-criteria.md](references/writing-criteria.md) | Analytic criteria, sample B1 rubric, genre checks, word counts by level, scoring procedure, feedback from the rubric |
