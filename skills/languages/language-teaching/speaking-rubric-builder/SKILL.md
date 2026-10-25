---
name: speaking-rubric-builder
description: "Build and validate speaking assessment rubrics for language learners: holistic vs analytic vs checklist, criteria (fluency and coherence, lexical resource, grammatical range and accuracy, pronunciation and intelligibility, interactive communication, task achievement), band descriptors written from the middle band out with observable features and consistent frequency words, a sample 4-band B1 rubric, task types that elicit each level, rater standardisation with benchmarks, double rating and rater effects. Checks a rubric for missing bands, near-identical adjacent bands, purely evaluative descriptors, native-speaker benchmarks and too many bands or criteria, and measures two-rater agreement (exact, adjacent, quadratic weighted kappa, severity) listing performances that need a third rating. Use when designing a speaking test or rubric, training raters, or checking marking consistency."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Speaking Rubric Builder

A speaking rubric works when its criteria match the task, each band describes observable features that change
from one band to the next, and trained raters agree. `scripts/rubric_check.py` checks the rubric;
`scripts/rater_agreement.py` checks the raters.

## Trigger Conditions

Activate this skill when the user:
- Needs a rubric or band descriptors for a speaking test or classroom speaking task
- Wants a speaking task that elicits a level (interview, long turn, discussion, role play)
- Is training or standardising raters
- Has two teachers' scores and wants to know if they agree

Writing rubrics: [writing-rubric-for-l2-builder](../writing-rubric-for-l2-builder/SKILL.md). Placement
interviews: [language-placement-test-builder](../language-placement-test-builder/SKILL.md).

## Workflow

```
1. PURPOSE   -> placement, progress, achievement, certification; level(s); stakes
2. TASKS     -> at least two task types that elicit the level (references/speaking-criteria.md)
3. TYPE      -> holistic / analytic / checklist
4. CRITERIA  -> 3-5 that match the construct
5. BANDS     -> 4-6 bands; write the middle band first; observable features; consistent frequency words
6. CHECK     -> python scripts/rubric_check.py rubric.csv
7. STANDARD  -> benchmarks, practice, qualification (references/rater-standardisation.md)
8. AGREEMENT -> python scripts/rater_agreement.py double_ratings.csv
```

## Review Codes

| Code | Severity | Problem |
|------|----------|---------|
| SR001 | high | Criterion missing a band |
| SR002 | medium | Adjacent bands nearly identical |
| SR003 | medium | Purely evaluative descriptor |
| SR004 | medium | Native-speaker benchmark |
| SR005 / SR006 | low | Too few or too many bands or criteria |
| RA001 | high | Under 90% of ratings within one band |
| RA002 | medium | Weighted kappa under 0.60 |
| RA003 | low | One rater harsher by over 0.5 band |
| RA004 | low | Ratings two or more bands apart |

## Output Format

The task(s) with instructions and timing, the rubric as a criteria x bands table, scoring and level conversion
rules, and the `rubric_check.py` result. For rater checks, the agreement summary with actions (re-standardise,
third ratings, feedback on severity).

## Scripts

```bash
python scripts/rubric_check.py rubric.csv
```
Columns: criterion, band, descriptor. Exit codes: 0 no high findings, 1 high findings, 2 read error.

```bash
python scripts/rater_agreement.py scores.csv
```
Columns: student, rater_a, rater_b (optional criterion). Exit codes: 0 no high findings, 1 high findings, 2 read
error or fewer than two rows.

## Additional Resources

| File | Content |
|------|---------|
| [speaking-criteria.md](references/speaking-criteria.md) | Holistic vs analytic, core criteria with band features, writing descriptors, sample B1 rubric, task types by level |
| [rater-standardisation.md](references/rater-standardisation.md) | Standardisation session, rating practice, double rating targets, rater effects, converting bands to scores |
