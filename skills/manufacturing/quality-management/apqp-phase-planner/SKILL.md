---
name: apqp-phase-planner
description: "Plan and track Advanced Product Quality Planning (AIAG APQP 3rd edition, IATF 16949) for a new or changed automotive part: back-schedule the five phases (plan and define, product design, process design, product and process validation, launch and feedback) from the start-of-production date by program complexity, with overlap, PPAP lead and safe-launch period; list the deliverables and gate for each phase (DFMEA, DVP&R, feasibility, process flow, PFMEA, control plans, MSA, Ppk, run at rate, PPAP, safe launch, lessons learned); adjust for build-to-print suppliers; flag compressed timelines and late or untracked deliverables against a status list. Covers gate reviews, red/yellow/green status reporting, run at rate and safe-launch exit criteria. Use when kicking off a new automotive program, building an APQP timing plan for a customer, preparing a gate review or recovering a late launch."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# APQP Phase Planner

APQP works backwards from the start of production (SOP): PPAP must be approved before SOP, which needs a
production run, which needs finished process design and tooling, which needs a frozen design. `scripts/apqp_plan.py`
builds that back-schedule, lists each phase's deliverables, and checks a status list for late or missing items.

## Trigger Conditions

Activate this skill when the user:
- Is starting a new automotive part or program and needs an APQP timing plan
- Must report APQP status to a customer or prepare a gate review
- Is a build-to-print supplier asking what APQP means for them
- Has a launch at risk and needs to see what is late

PPAP package: [ppap-submission-package-builder](../ppap-submission-package-builder/SKILL.md); PFMEA:
[process-fmea-builder](../process-fmea-builder/SKILL.md); control plan: [control-plan-writer](../control-plan-writer/SKILL.md).

## Workflow

```
1. INPUTS   -> SOP date, complexity (low/medium/high), design responsibility, customer PPAP lead and safe-launch rules
2. PLAN     -> python scripts/apqp_plan.py --sop 2027-09-06 --complexity medium --today 2026-10-26
3. COMPRESS -> if COMPRESSED: parallel work, carry-over, more resources, or renegotiate SOP / staged PPAP
4. ASSIGN   -> owner and due date for each deliverable; long-lead tooling ordered at design freeze
5. TRACK    -> python scripts/apqp_plan.py --sop ... --status deliverables.csv --today YYYY-MM-DD
6. GATES    -> review red/yellow items with management at each gate
7. LAUNCH   -> safe launch with exit criteria; lessons learned into the next program
```

## Phases and Gates

| Phase | Ends with | Medium-complexity duration |
|-------|-----------|----------------------------|
| 1 Plan and define | Program approval | 6 weeks |
| 2 Product design and development | Design freeze | 16 weeks (about 5 for build-to-print) |
| 3 Process design and development | Process sign-off | 14 weeks, starting halfway through phase 2 |
| 4 Product and process validation | PPAP approved, 4 weeks before SOP | 10 weeks |
| 5 Launch, feedback and corrective action | Safe-launch exit | 13 weeks after SOP |

```
4 Product and process validation            2027-05-31  2027-08-09  PPAP approved
LATE  phase 1 'Preliminary special characteristics' is in-progress; phase ended 2026-12-28
```

Deliverables per phase, build-to-print changes, gates and typical lead times:
[apqp-phases.md](references/apqp-phases.md). Status reporting, run at rate and safe launch:
[launch-and-status-reporting.md](references/launch-and-status-reporting.md).

## Output Format

Deliver:
1. **Timing plan** - phases with start, end and gate (from `apqp_plan.py`).
2. **Deliverable list** with owners and due dates per phase.
3. **Status** - done / in progress / late, untracked deliverables, red/yellow risks with recovery plans.
4. **Critical path** - long-lead tooling and equipment, PPAP date, SOP.

## Scripts

```bash
python scripts/apqp_plan.py --sop 2027-09-06 --complexity medium --today 2026-10-26
python scripts/apqp_plan.py --sop 2027-09-06 --complexity high --no-design --ppap-lead 6 --safe-launch 13
python scripts/apqp_plan.py --sop 2027-09-06 --status deliverables.csv --today 2027-03-01
```
Status CSV: deliverable, phase (1-5), status (done/in-progress/not-started). Exit codes: 0 feasible and nothing late,
1 compressed timeline or late deliverables, 2 usage or read error.

## Additional Resources

| File | Content |
|------|---------|
| [apqp-phases.md](references/apqp-phases.md) | Phase purposes, deliverables, gates, build-to-print, lead times |
| [launch-and-status-reporting.md](references/launch-and-status-reporting.md) | Status report format, run at rate, safe launch, lessons learned |
