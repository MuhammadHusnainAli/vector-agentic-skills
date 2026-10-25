---
name: control-plan-writer
description: "Write and review control plans (AIAG Control Plan, IATF 16949 8.5.1.1 and Annex A) for prototype, pre-launch and production phases: operation, equipment, product and process characteristics, special characteristic class (CC/SC), specification, measurement technique, sample size and frequency, control method (SPC, 100% inspection, error-proofing, check sheet) and reaction plans that stop, contain suspect product since the last good check, correct, verify and record. Drafts control plan rows from a PFMEA (product rows from detection controls, process rows from prevention controls, sampling parsed from the control text), and checks a control plan for missing specs, methods, sampling or reaction plans, weak controls on special characteristics, reaction plans without containment and disagreement with the PFMEA. Use when building a control plan for PPAP, reviewing one before a customer audit, or after an escape caused by a weak reaction plan."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Control Plan Writer

The control plan is the shop-floor contract: for each characteristic, how it is measured, how often, how the
process is controlled and what happens when it goes wrong. It must agree with the PFMEA and give special
characteristics strong controls. `scripts/cp_from_pfmea.py` drafts the plan from the PFMEA;
`scripts/cp_check.py` checks the plan and cross-checks it against the PFMEA.

## Trigger Conditions

Activate this skill when the user:
- Needs a control plan for a new part, PPAP or a process change
- Wants a control plan reviewed before a customer audit or PPAP
- Had an escape where the reaction plan did not contain suspect product
- Asks how to control a special characteristic or write a reaction plan

PFMEA input: [process-fmea-builder](../process-fmea-builder/SKILL.md); SPC for the control method:
[manufacturing-spc-chart-builder](../manufacturing-spc-chart-builder/SKILL.md).

## Workflow

```
1. INPUTS   -> process flow, PFMEA, drawing with special characteristics, CSRs, gauge list with MSA
2. DRAFT    -> python scripts/cp_from_pfmea.py pfmea.csv --part VB-2210 --phase production > cp.csv
3. COMPLETE -> specs, sample size and frequency, control method, specific reaction plans for every row
4. CHECK    -> python scripts/cp_check.py cp.csv --pfmea pfmea.csv
5. ALIGN    -> fix CPL007 by updating the plan or the PFMEA so they say the same thing
6. RELEASE  -> approve; train operators; audit with LPAs; update on every change
```

## Checks (cp_check.py)

| Code | Severity | Problem |
|------|----------|---------|
| CPL001 | high | No specification or process setting |
| CPL002 | high | No measurement technique |
| CPL003 | high | No sample size or frequency |
| CPL004 | high | No reaction plan |
| CPL005 | high | CC/SC without SPC, 100% check or error-proofing |
| CPL006 | medium | Reaction plan without containment of suspect product |
| CPL007 | medium | PFMEA control or special characteristic missing from the plan |
| CPL008 | low | TODOs left, phase missing |

```
CPL005 [high] OP45 #4 Pull-out force: CC needs SPC, 100% inspection or error-proofing (has 'Check sheet')
CPL006 [medium] OP45 #4 Pull-out force: reaction plan must contain suspect product (quarantine since last good check)
```

Phases, columns, the rules auditors check and family plans: [control-plan-columns.md](references/control-plan-columns.md).
Reaction plan template, weak-to-strong rewrites and out-of-control vs out-of-spec reactions:
[reaction-plans.md](references/reaction-plans.md).

## Output Format

Deliver the control plan table (all AIAG columns) with phase and revision, followed by the `cp_check.py` result
with all high findings fixed and every PFMEA/plan mismatch resolved, and a list of gauges needing MSA.

## Scripts

```bash
python scripts/cp_from_pfmea.py pfmea.csv --part VB-2210 --phase production > control_plan.csv
```
Exit codes: 0 written, 2 read error or missing PFMEA columns.

```bash
python scripts/cp_check.py control_plan.csv
python scripts/cp_check.py control_plan.csv --pfmea pfmea.csv
```
Exit codes: 0 no high findings, 1 high findings, 2 read error.

## Additional Resources

| File | Content |
|------|---------|
| [control-plan-columns.md](references/control-plan-columns.md) | Phases, columns with examples, audit rules, family control plans |
| [reaction-plans.md](references/reaction-plans.md) | Reaction plan template, weak -> strong, out-of-control vs out-of-specification |
