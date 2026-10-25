---
name: layered-process-audit-designer
description: "Design and run layered process audits (LPA, AIAG CQI-8, IATF 16949 and OEM requirements such as GM BIQS): layer structure (supervisors daily, managers weekly, plant leadership monthly), short risk-based yes/no question cards drawn from PFMEA, control plan reaction plans, special characteristics and recent complaints, rotation so higher layers see every area, workload per person, on-the-spot correction and escalation. Builds a rotating multi-week LPA calendar with workload from a people list, and analyses LPA results for compliance by area, layer and question, repeat failures that need corrective action, failures not corrected, layer gaps that show weak layer-1 audits, and stale always-pass questions to rotate. Use when setting up an LPA program, writing LPA questions, preparing for an automotive customer audit, or reviewing monthly LPA results."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Layered Process Audit Designer

LPAs put several layers of management on the floor, checking the same handful of critical controls at
different frequencies. They work when questions are short, observable and risk-based, audits actually happen,
and failures turn into action. `scripts/lpa_plan.py` builds the rotation calendar and workload;
`scripts/lpa_results.py` turns results into compliance trends and escalations.

## Trigger Conditions

Activate this skill when the user:
- Is setting up an LPA program or a customer (automotive OEM) requires one
- Needs LPA questions or a question card for a line
- Wants an LPA schedule with rotation across areas and layers
- Has LPA results and needs to know what to act on

## Workflow

```
1. LAYERS    -> who audits at layer 1 (daily), 2 (weekly), 3 (monthly); areas in scope
2. QUESTIONS -> 5-15 observable yes/no questions from complaints, special characteristics, PFMEA, reaction plans
3. CARD      -> each question with a "look for" line or photo of the correct state
4. PLAN      -> python scripts/lpa_plan.py --people people.csv --weeks 4 --questions 10
5. RUN       -> fix on the spot when possible; record action, owner, date when not
6. ANALYSE   -> python scripts/lpa_results.py results.csv   (monthly)
7. IMPROVE   -> CAPA for repeats, coach layer 1 on gaps, rotate stale questions
```

## Layers

| Layer | Who | Frequency |
|-------|-----|-----------|
| 1 | Supervisors / team leaders, own area | Every shift or day |
| 2 | Managers and engineers, rotating | Weekly |
| 3 | Plant leadership, rotating | Monthly |

All layers use the same card. Design rules, metrics (completion >= 95%, open actions, layer gap) and rollout:
[lpa-system-design.md](references/lpa-system-design.md). Weak vs strong questions, sources and card format:
[question-writing.md](references/question-writing.md).

## Results Analysis (lpa_results.py)

| Code | Severity | Meaning | Action |
|------|----------|---------|--------|
| LR001 | high | Same question fails repeatedly in one area | Open a corrective action (5 Why / 8D) |
| LR002 | medium | Failure not corrected on the spot, no follow-up | Record action, owner, date |
| LR003 | medium | Layer 1 compliance >= 15 points above higher layers | Coach layer 1; review "look for" lines |
| LR004 | low | Question passed every time | Rotate in a question on a current risk |

```
LR001 [high] Q2 failed 5 times in Weld - systemic: open a corrective action
LR003 [medium] Press: layer 1 finds 100% compliance, higher layers 80% - coach layer 1 on what to check
```

## Output Format

Deliver:
1. **Program design** - layers, people, areas, frequency, audit length.
2. **Question card** - numbered questions with "look for" and source (complaint, PFMEA line, control plan step).
3. **Calendar** - rotation table and workload per person (from `lpa_plan.py`).
4. **Results review** - compliance by area/layer/question, escalations and question changes (from `lpa_results.py`).

## Scripts

```bash
python scripts/lpa_plan.py --people people.csv --weeks 4
python scripts/lpa_plan.py --people people.csv --weeks 8 --questions 12 --minutes-per-question 1.5 --days 6
```
People CSV: name, layer (1/2/3), area (home area; required for layer 1). Layer 2/3 auditors get the least-visited
area each week, without doubling up, home area last. Exit codes: 0 plan, 1 an area has no layer-1 auditor,
2 read error.

```bash
python scripts/lpa_results.py results.csv
python scripts/lpa_results.py results.csv --repeat 3 --stale 20
```
Results CSV: date, layer, area, auditor, question_id, question, result (pass/fail/na), corrected. Exit codes:
0 no high findings, 1 repeat failures found, 2 read error.

## Additional Resources

| File | Content |
|------|---------|
| [lpa-system-design.md](references/lpa-system-design.md) | Layers and frequency, design rules, metrics, rollout |
| [question-writing.md](references/question-writing.md) | Weak vs strong questions, question sources, card format |
