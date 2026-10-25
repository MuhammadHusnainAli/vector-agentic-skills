---
name: manufacturing-dmaic-charter-writer
description: "Write and review Six Sigma DMAIC project charters for manufacturing improvement: business case with money and strategic link, problem statement with what, where, when and how much but no cause or solution, SMART goal statement from baseline to target by a date, customer CTQ, primary metric with operational definition and a counter-balance metric, scope in and out, champion, process owner, belt and team, phase dates with tollgates. Checks charters for causes or solutions in the problem statement, missing magnitude or time frame, unmeasurable goals, targets no better than the baseline, missing scope, sponsor or owner, phase dates out of order or projects too long; estimates cost of poor quality (scrap, rework, escapes, appraisal), savings at the goal and payback. Covers SIPOC, DMAIC tollgate questions, scoping and why projects fail. Use when launching a green or black belt project, preparing a charter for champion sign-off, or building the business case."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Manufacturing DMAIC Charter Writer

Most failed Six Sigma projects fail in Define: a problem statement that already contains the solution, a scope that
is a whole plant, no baseline, no champion. `scripts/charter_check.py` reviews a charter against those failure
modes; `scripts/copq.py` puts a number on the business case.

## Trigger Conditions

Activate this skill when the user:
- Is starting a DMAIC (green belt or black belt) project and needs a charter
- Wants a charter reviewed before the Define tollgate
- Needs the cost of poor quality or savings estimate for the business case
- Asks how to write a problem or goal statement, or how to scope a project

Choosing the problem: [pareto-defect-analyzer](../pareto-defect-analyzer/SKILL.md); measuring the baseline in sigma:
[six-sigma-dpmo-calculator](../six-sigma-dpmo-calculator/SKILL.md).

## Workflow

```
1. SELECT   -> top Pareto bar with money and customer impact
2. COST     -> python scripts/copq.py --units ... --defect-rate ... --target-rate ... --project-cost ...
3. DRAFT    -> charter.json (charter-template.md)
4. CHECK    -> python scripts/charter_check.py charter.json
5. SIPOC    -> confirm process boundaries match scope in / out
6. SIGN     -> champion approves at the Define tollgate; finance agrees the savings method
```

## Problem and Goal Statements

```
Problem: From January to September 2026, 3.1% of VB-2210 valve bodies machined on lathes 1-4 were scrapped or
         reworked for bore diameter outside 12.000-12.018 mm, versus 0.8% on similar parts.
Goal:    Reduce VB-2210 bore scrap and rework from 3.1% to 0.8% by 2027-04-30 without increasing cycle time.
```

## Checks (charter_check.py)

| Code | Severity | Problem |
|------|----------|---------|
| CH001 | high | Cause or solution in the problem statement |
| CH002 | high | No magnitude or time frame |
| CH003 | high | Goal without target number or date |
| CH004 | high | Metric baseline/target missing or target not better |
| CH005 | medium | Scope in/out incomplete |
| CH006 | medium | No champion or process owner |
| CH007 | medium | Phase dates missing, out of order, or project too long |
| CH008 | medium | Business case without money or strategy |
| CH009 | low | No counter-balance metric |
| CH010 | low | No customer CTQ |

Template, statement checklists, goal setting and scoping: [charter-template.md](references/charter-template.md).
Phase tools and tollgate questions, SIPOC, COPQ categories and why projects fail:
[dmaic-tollgates.md](references/dmaic-tollgates.md).

## Output Format

Deliver the charter (all template fields), the COPQ / savings estimate with assumptions, and the
`charter_check.py` result with every high issue fixed.

## Scripts

```bash
python scripts/charter_check.py charter.json [--max-months 6]
```
Exit codes: 0 no high issues, 1 high issues, 2 read or JSON error.

```bash
python scripts/copq.py --units 240000 --defect-rate 3.1% --scrap-share 0.6 --scrap-cost 9.50 --rework-cost 3.20 \
  --escape-share 0.02 --external-cost 85 --appraisal 12000 --target-rate 0.8% --project-cost 15000 --currency GBP
```
Rates accept fractions, percent or ppm. Exit codes: 0 computed, 2 usage error.

## Additional Resources

| File | Content |
|------|---------|
| [charter-template.md](references/charter-template.md) | Charter fields with examples, problem/goal checklists, scoping |
| [dmaic-tollgates.md](references/dmaic-tollgates.md) | DMAIC tools and tollgate questions, SIPOC, COPQ categories, failure reasons |
