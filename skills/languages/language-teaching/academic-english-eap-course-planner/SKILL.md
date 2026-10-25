---
name: academic-english-eap-course-planner
description: "Plan English for Academic Purposes (EAP) courses: pre-sessional, in-sessional, foundation, IELTS preparation and discipline-specific EAP, with syllabus strands (academic reading, lecture listening and note-taking, essay and report writing, paraphrase, summary and synthesis, referencing and plagiarism, seminars and presentations, academic vocabulary, critical thinking), a 10-week pre-sessional outline, exit assessment, IELTS-CEFR alignment and academic style (formality, hedging, cohesion, reporting verbs). Estimates study hours and weeks to close an IELTS gap from overall or per-skill scores (IELTS rounding, minimum per skill, priority skills, feasibility before a deadline), and checks learner texts for contractions, informal words with academic alternatives, unhedged claims, 'you', And/But/So starts, rhetorical questions and missing citations. Use when designing an EAP or pre-sessional course, advising a student on reaching an IELTS score, or teaching academic writing style."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Academic English (EAP) Course Planner

EAP courses prepare learners to study through English, not just to pass a test. `scripts/ielts_gap.py` estimates
how much study a band gap needs; `scripts/academic_style_check.py` shows learners where their writing is not yet
academic, with alternatives.

## Trigger Conditions

Activate this skill when the user:
- Designs a pre-sessional, in-sessional, foundation or IELTS preparation course
- Advises a student on how long it takes to reach an IELTS score
- Teaches academic writing style, hedging, paraphrasing or referencing
- Wants learner essays checked for academic register

Workplace English: [esp-english-course-designer](../esp-english-course-designer/SKILL.md). Writing rubrics:
[writing-rubric-for-l2-builder](../writing-rubric-for-l2-builder/SKILL.md). Citation checks:
[delta-assignment-planner](../delta-assignment-planner/SKILL.md) (`citation_check.py`).

## Workflow

```
1. LEARNERS -> entry scores (per skill), target, deadline, disciplines
2. GAP      -> python scripts/ielts_gap.py --skills L6 R6.5 W5 S5.5 --target 6.5 --min-skill 6 --weeks 10 --hours-per-week 20
3. TYPE     -> pre-sessional / in-sessional / IELTS / ESAP (references/eap-syllabus.md)
4. STRANDS  -> reading, listening, writing, sources, speaking, language, study skills, critical thinking
5. OUTLINE  -> week-by-week plan with assessment points
6. STYLE    -> teach and check academic style (references/academic-style.md)
7. CHECK    -> python scripts/academic_style_check.py essay.txt
8. ASSESS   -> exit tasks that mirror university work, mapped to the required score
```

The hours estimate is a rule of thumb (about 200 guided hours per band, more above 7.0). State it as an estimate
and recommend checking progress with a mock test at the midpoint.

## Review Codes (academic_style_check.py)

| Code | Severity | Problem |
|------|----------|---------|
| AS001 | medium | Contractions |
| AS002 | medium | Informal word or phrasal verb (alternative given) |
| AS003 | medium | Absolute claims with no hedging |
| AS004 | low | "You" addressing the reader |
| AS005 | low | Sentences starting with And/But/So |
| AS006 | low | Rhetorical questions |
| AS007 | low | No citations in a text over 150 words |

## Scripts

```bash
python scripts/ielts_gap.py (--current 5.5 | --skills L6 R6.5 W5 S5.5) --target 6.5 [--min-skill 6] [--hours-per-week 20] [--weeks 10]
```
Exit codes: 0 feasible (or no time given), 1 not enough time, 2 bad arguments.

```bash
python scripts/academic_style_check.py essay.txt
```
Exit codes: 0 no medium findings, 1 medium findings, 2 read error or empty text.

## Additional Resources

| File | Content |
|------|---------|
| [eap-syllabus.md](references/eap-syllabus.md) | Course types, syllabus strands, 10-week pre-sessional outline, assessment, IELTS-CEFR alignment |
| [academic-style.md](references/academic-style.md) | Formality alternatives, hedging devices, impersonal style, nominalisation, cohesion, reporting verbs |
