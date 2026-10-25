---
name: actfl-proficiency-curriculum-mapper
description: "Map world language curricula to the ACTFL framework: proficiency levels (Novice, Intermediate, Advanced, Superior, Distinguished with sublevels), functions, contexts, text types and accuracy, proficiency vs performance, the three modes of communication (interpretive, interpersonal, presentational), the 5 Cs World-Readiness Standards, backward-designed thematic units with Integrated Performance Assessments, typical programme targets and FSI time estimates. Looks up approximate ACTFL-CEFR-ILR equivalences with what each level can do, and checks a unit map for missing modes, rehearsed skits mislabelled as interpersonal, translation or word lists as interpretive tasks, and units without an integrated performance assessment. Use when designing or auditing a US K-12 or college language curriculum, writing ACTFL-aligned units, or explaining how ACTFL levels relate to CEFR or ILR."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# ACTFL Proficiency Curriculum Mapper

ACTFL-aligned curricula set performance targets per unit, build every unit around the three modes of
communication, and assess them with an Integrated Performance Assessment. `scripts/mode_coverage.py` checks a
unit map; `scripts/level_map.py` explains levels and their approximate CEFR and ILR equivalents.

## Trigger Conditions

Activate this skill when the user:
- Designs or audits a world language curriculum in the US (K-12, college, immersion, heritage)
- Writes thematic units, IPAs or ACTFL-aligned can-do statements
- Asks what "Intermediate Mid" means, or how ACTFL relates to CEFR or ILR
- Sets programme targets (Seal of Biliteracy, AP, proficiency-based grading)

CEFR courses: [cefr-aligned-syllabus-builder](../cefr-aligned-syllabus-builder/SKILL.md). Outcomes:
[can-do-statement-writer](../can-do-statement-writer/SKILL.md). Programme review:
[language-program-review-writer](../language-program-review-writer/SKILL.md).

## Workflow

```
1. TARGETS  -> programme and course performance targets per year (references/actfl-framework.md)
2. LEVELS   -> python scripts/level_map.py "Intermediate Mid"   (FACT profile, CEFR/ILR equivalents)
3. THEMES   -> thematic units with essential questions; 5 Cs connections
4. MODES    -> interpretive, interpersonal and presentational task per unit at the target level
5. ASSESS   -> IPA per unit: interpretive -> interpersonal -> presentational in one context, with rubrics
6. CHECK    -> python scripts/mode_coverage.py units.csv
7. REPORT   -> targets, unit map, assessment plan; state that framework equivalences are approximate
```

## Review Codes (mode_coverage.py)

| Code | Severity | Problem |
|------|----------|---------|
| AC001 | high | Unit without a performance assessment |
| AC002 | medium | Unit with no task in a mode |
| AC003 | medium | Rehearsed skit or presentation labelled interpersonal |
| AC004 | low | Interpretive task is translation or word lists |
| AC005 | low | Assessment does not cover all three modes |

## Output Format

Programme target table (course/year, target level per mode), unit map (theme, essential question, can-dos per
mode, IPA tasks, authentic resources, culture focus), and the `mode_coverage.py` result. Include FACT-based task
checks for the target level.

## Scripts

```bash
python scripts/level_map.py "Intermediate High" | --cefr B1 | --ilr 2 | --table
```
Exit codes: 0 found, 2 unknown level.

```bash
python scripts/mode_coverage.py units.csv
```
Columns: unit, interpretive, interpersonal, presentational, assessment. Exit codes: 0 no high findings, 1 high
findings, 2 read error or bad CSV.

## Additional Resources

| File | Content |
|------|---------|
| [actfl-framework.md](references/actfl-framework.md) | Levels, FACT task lens, proficiency vs performance, three modes, 5 Cs, backward design and IPA, programme targets, FSI hours |
| [framework-alignment.md](references/framework-alignment.md) | ACTFL, CEFR and ILR compared, approximate alignment table with sources, why scales differ, practical use |
