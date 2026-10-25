---
name: tefl-celta-prep-tutor
description: "Tutor trainees preparing for CELTA, Trinity CertTESOL and other initial TEFL/TESOL courses: course structure and assessment (teaching practice, assignments, grades, the five CELTA syllabus topics), what trainers assess in teaching practice, a pre-course study plan, grammar and phonology essentials, ELT terminology, and practice quizzes from an original question bank across language analysis, phonology, methodology, planning, classroom management and skills, with seeded reproducible quizzes, shuffled options, grading with explanations and weak-domain reports. Explains concepts like CCQs, ICQs, PPP, TTT, TBL, guided discovery, recasts, gist and scanning, schwa and minimal pairs, and helps with pre-interview tasks, lesson plans and assignment structure. Use when someone is applying for or taking a CELTA or TESOL course, wants practice questions on ELT knowledge, or a trainer needs a quiz."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# TEFL / CELTA Prep Tutor

Trainees succeed on initial courses when they can analyse language accurately, plan learner-centred lessons
and act on feedback. `scripts/quiz.py` runs practice quizzes from
[question-bank.md](references/question-bank.md); the references cover the course and the terminology.

## Trigger Conditions

Activate this skill when the user:
- Is applying for or taking CELTA, Trinity CertTESOL or a similar TEFL course
- Wants practice on grammar terminology, phonology or methodology for a pre-interview task
- Asks what trainers look for in teaching practice or how assignments work
- Is a trainer who wants a quiz with an answer key

Planning help: [language-lesson-plan-builder](../language-lesson-plan-builder/SKILL.md),
[ppp-lesson-structure-planner](../ppp-lesson-structure-planner/SKILL.md). Next step after CELTA:
[delta-assignment-planner](../delta-assignment-planner/SKILL.md).

## Workflow

```
1. BASELINE -> python scripts/quiz.py --n 12 --seed 1
2. GRADE    -> python scripts/quiz.py --n 12 --seed 1 --answers <letters>
3. TEACH    -> for each wrong answer: concept, example, classroom application
4. FOCUS    -> python scripts/quiz.py --domain Phonology --n 6 --seed 2
5. PREPARE  -> four-week plan (references/course-guide.md); terminology (references/terminology.md)
6. APPLY    -> practise a lesson plan, CCQs, instructions and ICQs with the planning skills
```

## Tutoring a wrong answer

1. Say what the question tests (meaning, form, pronunciation, method).
2. Explain the concept in two sentences with an example sentence or classroom moment.
3. Show the trap (why the chosen option looked right).
4. Give a quick follow-up: "Write a CCQ for *should have*."

## Output Format

For quizzes: the questions, then (after answers) score by domain, explanations for wrong answers and what to study
next. For course questions: a direct answer with what trainers expect, and a practical example (a plan extract,
CCQs, instructions).

## Scripts

```bash
python scripts/quiz.py --list
python scripts/quiz.py [--domain Language] [--n 10] [--seed 1] [--answers BCAD...] [--key] [--pass-mark 0.7]
```
Exit codes: 0 printed or passed, 1 graded below the pass mark, 2 usage error.

## Additional Resources

| File | Content |
|------|---------|
| [question-bank.md](references/question-bank.md) | 36 original questions in six domains with explanations |
| [course-guide.md](references/course-guide.md) | CELTA and CertTESOL structure, what trainers assess, before and during the course, four-week plan |
| [terminology.md](references/terminology.md) | Glossary of ELT terms used on initial courses |
