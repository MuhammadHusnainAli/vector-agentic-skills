---
name: language-teacher-cv-writer
description: "Write and review CVs, cover letters and interview preparation for language teachers (EFL/ESL/TESOL and other languages): one-to-two-page structure, a profile line, qualifications first (CELTA, CertTESOL, Delta, PGCE, MA TESOL), experience bullets with action verbs, levels, ages, scale and results, professional development and skills, tailoring for young learner schools, exam centres, business English, EAP, online platforms and senior roles, regional CV norms (photo, age, nationality, visa information), cover letter outline, interview questions and demo lessons. Checks a CV for a missing teaching qualification, experience without numbers, no levels or age groups, duty phrases instead of action verbs, no exam or specialist teaching, length, personal details that some markets advise against, and a missing email. Use when a teacher is writing or updating a CV, applying for a TEFL or language teaching job, or preparing for an interview and demo lesson."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Language Teacher CV Writer

ELT recruiters scan for three things: a recognised qualification, the learners you have taught (levels, ages,
contexts) and evidence of results. `scripts/cv_check.py` checks a CV for these and for regional norms.

## Trigger Conditions

Activate this skill when the user:
- Writes or updates a CV for a TEFL, ESL or other language teaching job
- Applies for a specific job and wants the CV or cover letter tailored
- Moves country or sector (online, business English, EAP, young learners)
- Prepares for an interview or a demo lesson

Qualifications: [tefl-celta-prep-tutor](../tefl-celta-prep-tutor/SKILL.md),
[delta-assignment-planner](../delta-assignment-planner/SKILL.md). Demo lesson planning:
[language-lesson-plan-builder](../language-lesson-plan-builder/SKILL.md).

## Workflow

```
1. TARGET   -> job advert, school type, country (references/tefl-cv-guide.md)
2. FACTS    -> qualifications with dates and grades; roles with hours, levels, ages, class sizes, results
3. DRAFT    -> profile, qualifications, experience bullets (action verb + what + who + scale + result)
4. TAILOR   -> emphasise what the advert asks for; regional norms
5. CHECK    -> python scripts/cv_check.py cv.md --region uk
6. LETTER   -> 250-350 words: fit, evidence, why them, availability
7. PREPARE  -> interview questions and a demo lesson plan
```

Never add qualifications, results or experience the user does not have; ask for numbers instead of inventing them.
Leave personal details (age, photo, nationality) to the user's choice and the target market's norms.

## Review Codes (cv_check.py)

| Code | Severity | Problem |
|------|----------|---------|
| CV001 | high | No recognised teaching qualification |
| CV002 | medium | Experience without numbers |
| CV003 | medium | No levels or age groups |
| CV004 | medium | Duty phrases instead of action verbs |
| CV005 | low | No exam or specialist teaching |
| CV006 | low | Length outside about 250-900 words |
| CV007 | low | Personal details some markets advise against (with --region) |
| CV008 | low | No email address |

## Output Format

The CV in Markdown (ready to paste into a document), tailored to the target job, followed by the `cv_check.py`
result. For applications, add the cover letter and a short list of likely interview questions with answer points.

## Scripts

```bash
python scripts/cv_check.py cv.md [--region uk|us|ie|ca|au|asia|middle-east]
```
Exit codes: 0 no high findings, 1 high findings, 2 read error or empty file.

## Additional Resources

| File | Content |
|------|---------|
| [tefl-cv-guide.md](references/tefl-cv-guide.md) | CV structure, bullet formula with rewrites, tailoring by job type, regional norms, cover letter, interview and demo lesson |
