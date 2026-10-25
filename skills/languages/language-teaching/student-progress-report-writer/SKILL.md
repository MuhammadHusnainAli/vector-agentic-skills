---
name: student-progress-report-writer
description: "Write language learners' progress reports and report-card comments that are specific, balanced and useful to learners and parents: strength with evidence, measured progress, one or two areas to develop and a concrete next step, a phrase bank by skill, plain-language CEFR level descriptions, tone guidance and what to avoid. Summarises scores by learner, skill and term (latest score, change, strongest and weakest skill, an evidence sentence, and drops that need checking), and checks drafted comments for another learner's name pasted in, missing next steps, vague praise without evidence, no strengths, teacher jargon and length. Use when a language teacher writes end-of-term reports, parent reports, progress comments or learner feedback summaries."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Student Progress Report Writer

A good report comment is true only of this learner: it names a strength with evidence, shows progress, sets one
or two targets and gives a next step. `scripts/progress_summary.py` gathers the evidence from scores;
`scripts/comment_check.py` checks the drafted comments before they go home.

## Trigger Conditions

Activate this skill when the user:
- Writes end-of-term or end-of-course reports for language learners
- Needs comments for a class from a mark sheet
- Wants comments rewritten to be more specific or parent-friendly
- Wants to check a batch of comments for copy-paste errors

Writing feedback on a single piece: [student-writing-feedback-generator](../student-writing-feedback-generator/SKILL.md).
Programme-level data: [language-program-review-writer](../language-program-review-writer/SKILL.md).

## Workflow

```
1. EVIDENCE -> python scripts/progress_summary.py scores.csv    (per learner, per skill, per term)
2. NOTES    -> teacher's observations: a task, a moment, attitude to learning
3. DRAFT    -> strength + evidence, progress, area to develop, next step (references/report-comment-bank.md)
4. LEVEL    -> plain-language level description if levels are reported
5. CHECK    -> python scripts/comment_check.py comments.md
6. READ     -> would this comment make sense for any other learner? If yes, add a detail
```

Do not invent evidence: if the teacher gives only scores, base the comment on scores and ask for one observation
per learner to make it personal. Use the learner's pronouns as the teacher gives them; otherwise write with the
learner's name.

## Review Codes (comment_check.py)

| Code | Severity | Problem |
|------|----------|---------|
| RC001 | high | Another learner's name in the comment |
| RC002 | medium | No next step |
| RC003 | medium | Vague praise with no skill or example |
| RC004 | medium | No strength mentioned |
| RC005 | low | Teacher jargon |
| RC006 | low | Under 40 or over 150 words |

## Output Format

One comment per learner under a `## Name` heading (60-120 words), ready to paste, then the `comment_check.py`
result. With scores, include the evidence line from `progress_summary.py` for each learner above the comment.

## Scripts

```bash
python scripts/progress_summary.py scores.csv [--student Ana] [--drop 5]
```
Columns: student, term, skill, score. Exit codes: 0 printed, 2 read error, bad scores or unknown student.

```bash
python scripts/comment_check.py comments.md
```
Exit codes: 0 no high findings, 1 high findings, 2 read error or no `## Name` sections.

## Additional Resources

| File | Content |
|------|---------|
| [report-comment-bank.md](references/report-comment-bank.md) | Comment structure with example, phrase bank (strengths, progress, areas, next steps), plain-language levels, tone, what to avoid |
