---
name: language-teacher-observation-form-builder
description: "Build lesson observation forms for language teachers and track observation results: a criteria bank across planning and aims, classroom management, language clarification, skills development, learner engagement, error correction, assessment for learning, inclusion and differentiation, materials and technology, and rapport, each with observable look-fors; evaluative forms with a 1-4 scale and n/o, developmental (peer and coaching) forms with no ratings and reflection questions, pre- and post-observation practice and action points. Tracks ratings per teacher and area over time, flagging areas that need support, areas that improved and strengths to share. Use when a director of studies, mentor or peer observer needs an observation form, wants to run developmental observations, or wants to follow teachers' development across observations."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Language Teacher Observation Form Builder

Observations help teachers improve when the criteria are observable, evidence replaces impressions, and action
points are followed up. `scripts/observation_form.py` builds a form from the criteria bank;
`scripts/observation_trends.py` follows ratings across observations.

## Trigger Conditions

Activate this skill when the user:
- Needs an observation form for language lessons (appraisal, peer observation, mentoring, accreditation)
- Wants a developmental (non-judgemental) observation process
- Has observation results and wants to see each teacher's trends
- Plans CPD from observation findings

Feedback moves in detail: [recast-and-prompt-technique-coach](../recast-and-prompt-technique-coach/SKILL.md).
Programme evidence: [language-program-review-writer](../language-program-review-writer/SKILL.md).

## Workflow

```
1. PURPOSE -> developmental, evaluative or training (references/observation-criteria.md)
2. FOCUS   -> areas agreed with the teacher in a pre-observation meeting
3. FORM    -> python scripts/observation_form.py --areas classroom engagement [--developmental]
4. OBSERVE -> timed evidence notes against look-fors; n/o for areas not seen
5. DEBRIEF -> teacher reflects first; questions; 1-2 action points with a review date
6. TRACK   -> python scripts/observation_trends.py observations.csv
7. CPD     -> support for areas flagged twice; invite teachers with strengths to share
```

## Output Format

The form (header, areas with criteria, look-fors, evidence and rating columns, strengths, action points), and for
written feedback: strengths with evidence, development points with evidence, agreed actions. For trends: the
per-teacher table and the CPD actions.

## Scripts

```bash
python scripts/observation_form.py --areas all|<area words...> [--developmental] [--teacher "J. Doe"] [--date 2026-11-02]
```
Exit codes: 0 printed, 2 bank unreadable or an area matches nothing.

```bash
python scripts/observation_trends.py observations.csv [--teacher "J. Doe"]
```
Columns: teacher, date, area, rating (1-4 or n/o). Exit codes: 0 printed, 2 read error, bad rating or unknown
teacher.

## Additional Resources

| File | Content |
|------|---------|
| [observation-criteria.md](references/observation-criteria.md) | 23 criteria in 10 areas with look-fors, rating scale, developmental vs evaluative vs training observations, good practice |
