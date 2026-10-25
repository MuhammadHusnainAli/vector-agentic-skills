---
name: language-quiz-generator
description: "Generate language quizzes for grammar, vocabulary and comprehension from a tagged question bank: multiple choice with distractors drawn from real learner errors, gap-fills with base forms and all acceptable answers, true/false, balanced sampling across topics, shuffled questions and options by seed for parallel versions, and an answer key with teaching explanations. Checks a bank for MCQs with no or several keys, missing gap or true/false answers, too few or duplicate options, all/none of the above, correct options that stand out by length, gaps with no blank, unmarked negative stems and missing explanations. Covers matching item type to purpose, item-writing rules with flawed and improved examples, quiz length and composition, and using results. Use when a teacher needs a class quiz, exit ticket, test section or parallel versions of a quiz, or wants a question bank reviewed."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Language Quiz Generator

A quiz is useful when each item tests one point clearly, distractors reflect real errors, and the key teaches.
`scripts/quiz_build.py` builds shuffled quizzes from a tagged bank; `scripts/quiz_check.py` reviews the bank for
item-writing flaws.

## Trigger Conditions

Activate this skill when the user:
- Wants a quiz or test section on grammar, vocabulary or a text
- Needs parallel versions of a quiz (A/B versions, retakes)
- Has a question bank to review or extend
- Needs an exit ticket or quick check (see also formative assessment)

Placement tests and item statistics: [language-placement-test-builder](../language-placement-test-builder/SKILL.md).
Quick checks: [formative-assessment-for-language-planner](../formative-assessment-for-language-planner/SKILL.md).
Worksheets: [esl-worksheet-generator](../esl-worksheet-generator/SKILL.md).

## Workflow

```
1. SCOPE   -> points taught, level, length, item types (references/item-writing-guide.md)
2. WRITE   -> items in the bank format (references/bank-format.md), several per point, with explanations
3. CHECK   -> python scripts/quiz_check.py bank.txt     (fix every high finding)
4. BUILD   -> python scripts/quiz_build.py bank.txt --n 10 --level A2 --seed 1
5. VERSION -> same command with --seed 2 for version B
6. USE     -> analyse wrong answers; re-teach; tag weak items
```

When writing new items, write distractors from typical learner errors for the point, list every acceptable
answer for gaps, and keep option lengths similar.

## Review Codes (quiz_check.py)

| Code | Severity | Problem |
|------|----------|---------|
| QC001 | high | MCQ with no key or several keys |
| QC002 | high | Gap or T/F item without a valid answer |
| QC003 | medium | Fewer than 3 options or duplicates |
| QC004 | medium | All/none of the above |
| QC005 | medium | Key much longer than distractors |
| QC006 | low | Gap item with no ___ |
| QC007 | low | Negative stem not in capitals |
| QC008 | low | No explanation |

## Output Format

The quiz with section instructions and numbered items, then the answer key with explanations. When building the
bank, give it in the bank format so it can be reused, followed by the `quiz_check.py` result.

## Scripts

```bash
python scripts/quiz_build.py bank.txt [--n 10] [--level A2] [--topic past] [--seed 1] [--no-key]
```
Exit codes: 0 quiz printed, 1 fewer matching items than requested, 2 bank unreadable or empty.

```bash
python scripts/quiz_check.py bank.txt
```
Exit codes: 0 no high findings, 1 high findings, 2 read error or no items.

## Additional Resources

| File | Content |
|------|---------|
| [bank-format.md](references/bank-format.md) | Bank block format for MCQ, gap and T/F items, with an example bank |
| [item-writing-guide.md](references/item-writing-guide.md) | Item type by purpose, MCQ, gap and T/F rules with flawed and better examples, quiz composition, using results |
