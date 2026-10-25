---
name: iso-9001-certification-roadmap-planner
description: "Plan the route to ISO 9001 certification: phased project timeline from gap analysis through context, processes, documentation, training, a 3-month records period, a full internal audit cycle and management review to stage 1, stage 2, nonconformity closure and certificate, scaled by headcount and starting maturity; estimated audit days from the IAF MD 5 table with surveillance and recertification dates over the 3-year cycle; target-date feasibility check; certification body selection (accreditation, IAF MLA, sector codes, 3-year cost); project governance, budget and timeline risks. Use when a company asks 'how long will ISO 9001 take?', 'when can we be certified?', 'how many audit days?', needs a certification project plan or Gantt for management, or must hit a customer-imposed certification deadline."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# ISO 9001 Certification Roadmap Planner

Certification takes 6-18 months, and the critical path is usually the same: processes in place, about three
months of records, one complete internal audit cycle, one management review, then stage 1 and stage 2.
`scripts/roadmap.py` builds the dated plan, estimates audit days and checks whether a target date is realistic.

## Trigger Conditions

Activate this skill when the user:
- Asks how long ISO 9001 certification will take or when they could be certified
- Has a customer deadline for certification
- Needs a project plan, Gantt or budget for management approval
- Asks how many audit days, how surveillance works, or how to choose a certification body

Start with [iso-9001-gap-analyzer](../iso-9001-gap-analyzer/SKILL.md) to set the maturity input honestly.

## Workflow

```
1. INPUTS   -> start date, effective personnel in scope, sites, maturity (none / basic / partial), target date
2. PLAN     -> python scripts/roadmap.py --start 2026-11-02 --employees 40 --maturity basic --target 2027-09-30
3. ADJUST   -> if the target is not achievable: add resources, reuse existing systems, or move the date
4. CB       -> shortlist accredited certification bodies; request quotes for the 3-year cycle
5. GOVERN   -> sponsor, project lead, process owners, fortnightly steering, milestones
6. TRACK    -> re-run the plan monthly with actual progress; report slippage to the sponsor
```

## Critical Path

| Milestone | Cannot be shortened because |
|-----------|-----------------------------|
| Processes implemented | The audit samples real practice, not documents |
| ~3 months of records | Auditors need evidence the system operates over time |
| Full internal audit cycle | Required (9.2) before stage 1; checks every process and clause |
| Management review | Required (9.3) with all inputs, including audit results |
| Stage 1 -> stage 2 | Concerns must be closed; the CB schedules both |
| Nonconformity closure | Majors must be verified before the certification decision |

```
Stage 2 audit (certification)                   2027-08-09  2027-08-16     1  Stage 2 report: recommendation or nonconformities
Certificate expected: 2027-09-27 (~11 months)
Audit days (IAF MD 5, before CB adjustments): initial 4 (stage 1 + stage 2)
Target 2027-06-30: NOT achievable - 19 days short; raise maturity (consultant, existing system) or move the date
```

Stage-by-stage process, entry criteria for stage 1, CB selection and safe ways to speed up:
[certification-process.md](references/certification-process.md). IAF MD 5 table, complexity adjustments,
typical durations, governance and timeline risks: [audit-time-and-planning.md](references/audit-time-and-planning.md).

## Output Format

Deliver:
1. **Assumptions** - headcount, sites, maturity, design responsibility, resources.
2. **Roadmap** - phases with dates, durations and deliverables (from `roadmap.py`).
3. **Certificate date** and whether the target is achievable, with slack or shortfall.
4. **Audit days and 3-year cycle** - initial, surveillance and recertification estimates.
5. **Governance and budget** - sponsor, lead, steering rhythm, cost items.
6. **Top risks** to the timeline with mitigations.

## Scripts

```bash
python scripts/roadmap.py --start 2026-11-02 --employees 40
python scripts/roadmap.py --start 2026-11-02 --employees 180 --maturity partial --target 2027-06-30
python scripts/roadmap.py --start 2026-11-02 --employees 12 --maturity basic --json
```
Exit codes: 0 plan printed (and target met), 1 target not achievable, 2 usage error.

## Additional Resources

| File | Content |
|------|---------|
| [certification-process.md](references/certification-process.md) | ISO/IEC 17021-1 steps, stage 1 entry criteria, nonconformity closure, CB selection, speeding up safely |
| [audit-time-and-planning.md](references/audit-time-and-planning.md) | IAF MD 5 audit-day table and adjustments, typical durations, governance, timeline risks |
