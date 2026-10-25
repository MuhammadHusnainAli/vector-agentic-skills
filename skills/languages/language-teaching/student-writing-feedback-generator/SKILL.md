---
name: student-writing-feedback-generator
description: "Generate written feedback on language learners' writing: content and task first, then two or three language focus areas, strength-target-action comments, level-appropriate wording, a comment bank for task, organisation, language, register and next steps, learner self- and peer-check checklists, and redraft routines. Uses a correction code key (spelling, tense, verb form, agreement, wrong word, word form, article, preposition, word order, missing and extra words, punctuation, capitals, register, unclear meaning) so learners correct their own errors; summarises a coded text by error type and density, writes a learner-facing summary of the main areas to work on, flags over-marking and unknown codes, and produces a clean copy for redrafting. Use when a teacher needs feedback comments on student writing, a correction code system, or help marking a stack of learner texts efficiently."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Student Writing Feedback Generator

Feedback improves writing when it is selective, specific and acted on. The skill writes strength-target-action
comments; `scripts/correction_codes.py` summarises a correction-coded text and writes the learner summary.

## Trigger Conditions

Activate this skill when the user:
- Wants feedback comments on a learner's essay, email, story or report
- Sets up a correction code system for a class
- Has many texts to mark and wants consistent, faster feedback
- Wants learners to redraft or keep an error log

Scores and rubrics: [writing-rubric-for-l2-builder](../writing-rubric-for-l2-builder/SKILL.md). Oral correction:
[l2-error-correction-strategy-advisor](../l2-error-correction-strategy-advisor/SKILL.md). Reports:
[student-progress-report-writer](../student-progress-report-writer/SKILL.md).

## Workflow

```
1. READ     -> whole text for task completion and message
2. CONTENT  -> one comment on task/content, one on organisation
3. CODE     -> mark errors in studied language with codes (references/correction-code-key.md);
               reformulate language above the learner's level
4. SUMMARY  -> python scripts/correction_codes.py coded.txt --name Ana --clean
5. COMMENT  -> strength - target - action (references/feedback-framing.md), 2-3 focus areas
6. ACTION   -> redraft or correct; error log entries; checklist for next time
```

When given an uncoded learner text, code it first (only errors the learner can fix), then run the script on the
coded version so the summary and focus areas reflect the marking.

## Output Format

1. The coded text (or the reformulated version for errors above level).
2. Feedback: content/task comment, organisation comment, language focus areas with examples from the text, next
   steps.
3. The learner summary from `correction_codes.py` and the clean text for redrafting.

Keep the comment language at the learner's level; offer an L1 version if the teacher asks.

## Scripts

```bash
python scripts/correction_codes.py coded.txt [--name Ana] [--clean]
```
Codes go in square brackets after the word: `goed[T]`. Exit codes: 0 printed, 1 unknown codes found, 2 read error
or no codes.

## Additional Resources

| File | Content |
|------|---------|
| [correction-code-key.md](references/correction-code-key.md) | Code key with examples, marking rules, classroom routine, electronic marking |
| [feedback-framing.md](references/feedback-framing.md) | Principles, strength-target-action structure, comment bank, learner checklist, what to avoid |
