---
name: green-belt-exam-tutor
description: "Tutor candidates for Six Sigma Green Belt certification exams (ASQ CSSGB, IASSC and company programmes) across fundamentals and the DMAIC domains: practice quizzes drawn from an original question bank with worked explanations (sigma and DPMO, lean wastes, takt, RTY, Kano, charters, SIPOC, CTQs, COPQ, MSA and ndc, Cp and Cpk, data types, d2 estimates, test selection, p-values, error types, correlation and regression, fractional factorials, resolution, effects, poka-yoke, control chart limits, run rules, reaction plans, handover), reproducible quizzes by seed with shuffled options, grading with per-domain scores and weak areas, an answer-key mode, a study plan and a formula sheet. Use when someone is preparing for a Green Belt exam, wants practice questions or explanations of Six Sigma concepts and calculations, or a trainer needs a quiz for a class."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Green Belt Exam Tutor

Passing a Green Belt exam takes three things: knowing which tool answers which question, doing the core
calculations quickly, and avoiding the classic traps ("accept H0", control limits from specifications, average
yield instead of RTY). `scripts/quiz.py` runs practice quizzes from `references/question-bank.md`, grades them
and points to the weak domains.

## Trigger Conditions

Activate this skill when the user:
- Is preparing for a Six Sigma Green Belt exam or course test
- Wants practice questions, a mock exam or an explanation of a wrong answer
- Asks how to calculate Cpk, DPMO, RTY, takt, control limits or DOE effects for an exam
- Is a trainer who needs a quiz with an answer key

## Workflow

```
1. ASSESS  -> python scripts/quiz.py --n 12 --seed 1      (baseline mock, no answers shown)
2. GRADE   -> python scripts/quiz.py --n 12 --seed 1 --answers <letters>
3. TEACH   -> for each wrong answer: concept, formula, worked example, the trap
4. FOCUS   -> python scripts/quiz.py --domain Measure --n 6 --seed 2
5. PLAN    -> follow the eight-week plan; formula sheet drills
6. MOCK    -> full mixed quizzes with new seeds until >= 80% consistently
```

## Tutoring a Wrong Answer

1. Restate what the question is really asking (the qualifier: first, best, most likely).
2. Explain the concept in two sentences, then the formula from [formula-sheet.md](references/formula-sheet.md).
3. Work the numbers step by step.
4. Name the trap that made the wrong option attractive.
5. Give one similar question to try.

```
3. M04 you answered C, correct A: Cpk = min((10.6 - 10.2) / 0.3, (10.2 - 9.4) / 0.3) = min(1.33, 2.67) = 1.33.
Score: 7/10 = 70%  (PASS at 70%)
By domain: Measure 1/3, Control 2/2, Analyze 2/2 ...
Study next: Measure (see references/study-guide.md)
```

Domains, topics, traps, the eight-week plan and exam technique: [study-guide.md](references/study-guide.md).

## Output Format

For a quiz: numbered questions with options (no answers until graded). For grading: score, per-domain results,
explanations of each wrong answer, the domains to study next. For explanations: concept, formula, worked example,
trap, follow-up question.

## Scripts

```bash
python scripts/quiz.py --list
python scripts/quiz.py --n 10 --seed 3
python scripts/quiz.py --n 10 --seed 3 --answers DCACBADBCA
python scripts/quiz.py --domain Analyze --n 6 --seed 1 --answers-file answers.txt
python scripts/quiz.py --n 10 --seed 3 --key
```
The same seed, size and domain reproduce the same quiz and option letters. Exit codes: 0 printed or passed,
1 graded below --pass-mark (default 0.7), 2 usage error.

## Additional Resources

| File | Content |
|------|---------|
| [question-bank.md](references/question-bank.md) | 36 original questions across six domains with explanations (read by the script) |
| [study-guide.md](references/study-guide.md) | Domains, topics and traps, eight-week plan, exam technique |
| [formula-sheet.md](references/formula-sheet.md) | Formulas for defects, lean, statistics, capability, MSA, SPC, tests, regression, DOE |
