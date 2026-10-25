---
name: process-fmea-builder
description: "Build and review process FMEAs with the AIAG-VDA FMEA Handbook (2019) method used under IATF 16949: seven steps, structure from the process flow diagram, failure chains (effect, failure mode, cause at the 4M work-element level), prevention and detection controls, severity / occurrence / detection ratings, Action Priority (H/M/L) instead of RPN, and actions with owners and re-rating. Rates a PFMEA CSV with the full AP table plus legacy RPN, sorts by priority, and flags AP-H rows without action, severity 9-10 without controls, invalid ratings, detection 1-3 claimed for visual inspection, occurrence 1-2 without prevention, unmarked special characteristics and actions without owners. Covers the link to the control plan, review triggers and common audit findings. Use when creating a PFMEA for a new process, converting from RPN to Action Priority, reviewing a PFMEA before PPAP or after a customer complaint."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Process FMEA Builder

A PFMEA is only as good as its ratings. Most PFMEAs fail audits for the same reasons: optimistic detection for
visual checks, occurrence lowered without changing prevention, and high-priority rows with no action.
`scripts/pfmea_ap.py` applies the AIAG-VDA Action Priority table, keeps RPN for legacy customers, and flags
the rating errors.

## Trigger Conditions

Activate this skill when the user:
- Is building a PFMEA for a new part or process, or a process change
- Wants to move from RPN to AIAG-VDA Action Priority
- Needs a PFMEA reviewed before PPAP, a customer audit, or after a complaint
- Asks how to rate severity, occurrence or detection

The control plan built from the PFMEA: [control-plan-writer](../control-plan-writer/SKILL.md).

## Workflow

```
1. PLAN      -> scope, team (process, quality, production, maintenance, design), timing
2. STRUCTURE -> steps from the process flow diagram, work elements (4M)
3. FUNCTION  -> requirements per step (product and process characteristics)
4. FAILURE   -> effect - failure mode - cause chains; one row per cause
5. RISK      -> controls, S/O/D ratings -> python scripts/pfmea_ap.py pfmea.csv
6. OPTIMISE  -> actions for AP H (required) and M (should); owners, dates; re-rate after implementation
7. LINK      -> controls and special characteristics into the control plan
```

## Action Priority

AP ranks severity first, then occurrence, then detection: S10 O2 D3 is never outranked by S4 O5 D5 as it is under
RPN. H means action required (or documented, approved justification); M means action should be taken; L could.
The full table, seven steps and rating guidance: [aiag-vda-method.md](references/aiag-vda-method.md).

```
AP   S  O  D  RPN  Step          Failure mode                Cause
H    9  5  6  270  OP45 Crimp    Low pull-out force          Crimp height drift
FM001 [high] row 5 OP45 Crimp / Low pull-out force / Crimp height drift: AP H (S9 O5 D6) needs an action or a documented justification
```

## Checks (pfmea_ap.py)

| Code | Severity | Problem |
|------|----------|---------|
| FM001 | high | AP H without action |
| FM002 | high | Severity 9-10 with no controls |
| FM003 | high | Missing or out-of-range rating |
| FM004 | medium | D 1-3 without error-proofing or automatic detection |
| FM005 | medium | O 1-2 without prevention control |
| FM006 | medium | Severity 9-10 not marked as a special characteristic |
| FM007 | low | Action without owner or due date |

Failure-chain wording, control-plan link, review triggers and common findings:
[pfmea-practice.md](references/pfmea-practice.md).

## Output Format

Deliver the PFMEA table (step, function, failure mode, effect, S, cause, prevention, O, detection, D, AP, special
characteristic, action, owner, due), sorted by AP, then the `pfmea_ap.py` findings resolved, then the list of
controls and special characteristics to carry into the control plan.

## Scripts

```bash
python scripts/pfmea_ap.py pfmea.csv
python scripts/pfmea_ap.py pfmea.csv --sort rpn
python scripts/pfmea_ap.py pfmea.csv --csv > pfmea_rated.csv     # adds AP and RPN columns; findings to stderr
```
Columns: step, function, failure_mode, effect, S, cause, prevention, O, detection, D, special, action, owner, due.
Exit codes: 0 no high findings, 1 high findings, 2 read error or missing columns.

## Additional Resources

| File | Content |
|------|---------|
| [aiag-vda-method.md](references/aiag-vda-method.md) | Seven steps, rating guidance, full Action Priority table, AP vs RPN |
| [pfmea-practice.md](references/pfmea-practice.md) | Inputs, failure chain wording, control-plan link, review triggers, audit findings |
