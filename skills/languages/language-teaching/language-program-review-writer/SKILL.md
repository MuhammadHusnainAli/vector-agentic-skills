---
name: language-program-review-writer
description: "Write evidence-based reviews of language programmes and schools: review areas used by quality schemes (aims and design, curriculum and materials, teaching and learning, assessment, learner outcomes, support and welfare, staffing and CPD, resources, management, published information), evidence sources and triangulation, key indicators, findings, prioritised and owned recommendations, an action plan and a report template. Calculates by-course retention, pass rate, median CEFR level gain, attendance and satisfaction from learner records and flags low retention, low pass rates, zero level gain, poor attendance and low satisfaction, with a caution for small groups. Use when preparing a programme or course review, an accreditation self-evaluation, an annual quality report, or a data-based report on a language department."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Language Programme Review Writer

A useful programme review links each judgement to evidence and ends in specific, owned recommendations.
`scripts/program_metrics.py` turns learner records into the outcome indicators most reviews need.

## Trigger Conditions

Activate this skill when the user:
- Reviews a language programme, department or course for quality or accreditation
- Writes an annual report or self-evaluation for a language school
- Has learner data (enrolments, results, attendance, surveys) to interpret
- Needs recommendations and an action plan after a review

Curriculum checks: [cefr-aligned-syllabus-builder](../cefr-aligned-syllabus-builder/SKILL.md),
[actfl-proficiency-curriculum-mapper](../actfl-proficiency-curriculum-mapper/SKILL.md). Observation evidence:
[language-teacher-observation-form-builder](../language-teacher-observation-form-builder/SKILL.md).

## Workflow

```
1. SCOPE    -> purpose, courses, period, audience (management, accreditor, funder)
2. EVIDENCE -> learner data, surveys, observations, documents, interviews (references/review-framework.md)
3. DATA     -> python scripts/program_metrics.py students.csv
4. FINDINGS -> strengths and areas for development per area, each with two sources
5. RECOMMEND-> specific, prioritised, owned, dated, measurable
6. WRITE    -> references/report-template.md; executive summary last
7. CHECK    -> every recommendation traces to a finding; small groups flagged; data anonymised
```

Ask for missing evidence rather than inventing it; where evidence is thin, say so in the limitations section.

## Indicators (program_metrics.py)

| Code | Severity | Finding |
|------|----------|---------|
| PM001 | high | Retention below threshold (default 75%) |
| PM002 | medium | Pass rate below threshold (default 75%) |
| PM003 | medium | Median level gain of completers is zero |
| PM004 | low | Mean attendance below threshold (default 80%) |
| PM005 | low | Mean satisfaction below 3.5/5 |
| PM006 | info | Fewer than 10 students |

## Output Format

A report following [report-template.md](references/report-template.md): executive summary, context, method and
limitations, findings by area with evidence, outcomes data table, recommendations table (priority, owner,
deadline, success measure), action plan.

## Scripts

```bash
python scripts/program_metrics.py students.csv [--retention 75] [--pass 75] [--attendance 80]
```
Columns: student, course, status (completed/withdrawn/continuing), start_level, end_level, passed, attendance,
satisfaction (only the first three are required). Exit codes: 0 no high findings, 1 high findings, 2 read
error or bad CSV.

## Additional Resources

| File | Content |
|------|---------|
| [review-framework.md](references/review-framework.md) | Review areas and questions, evidence sources, key indicators, findings to recommendations, ethics and data |
| [report-template.md](references/report-template.md) | Section-by-section report template and writing style |
