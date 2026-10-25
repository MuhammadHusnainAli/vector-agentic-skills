---
name: capa-plan-writer
description: "Write and review corrective and preventive action (CAPA) plans that meet ISO 9001 10.2 (also IATF 16949 10.2, AS9100, ISO 13485 8.5.2): correction and containment, verified root causes for occurrence and escape, corrective actions linked to each cause and ranked by strength (eliminate > error-proof > automate/detect > standardise > train > remind), owners and dates, measurable effectiveness checks, extension to similar products and sites, and updates to PFMEA, control plans, procedures and risks. Reviews a CAPA for 'operator error' or symptom root causes, correction-only actions, training-only actions, unverified causes, unlinked actions and missing effectiveness criteria; reports a CAPA log by stage, age, owner, overdue and stuck actions, and closed-too-fast CAPAs. Use when opening or reviewing a CAPA, answering an audit finding or complaint, preparing CAPA metrics for management review, or when CAPAs keep recurring."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# CAPA Plan Writer

A CAPA succeeds when the problem does not come back. That needs a verified root cause, actions that remove it
(not just fix the parts), and a measured effectiveness check. `scripts/capa_check.py` reviews a CAPA plan and ranks
its actions by strength; `scripts/capa_aging.py` reports the CAPA log for follow-up and management review.

## Trigger Conditions

Activate this skill when the user:
- Opens a corrective action for an NCR, complaint, audit finding or escape
- Wants a CAPA reviewed before submission to a customer or auditor
- Has CAPAs that keep recurring, or root causes like "operator error"
- Needs CAPA status metrics (overdue, aging, cycle time) for management review

Root cause tools: [five-whys-analysis-facilitator](../five-whys-analysis-facilitator/SKILL.md),
[quality-fishbone-diagram-builder](../quality-fishbone-diagram-builder/SKILL.md); customer format:
[8d-problem-solving-report-writer](../8d-problem-solving-report-writer/SKILL.md).

## Workflow

```
1. REACT     -> correction and containment (what was done to the parts and suspect stock)
2. CAUSE     -> root causes for occurrence AND escape; verify each (reproduce, on/off, data)
3. ACT       -> at least one strong action (rank >= 3) per verified cause; owner and date
4. EXTEND    -> similar products, machines, sites (10.2.1 b 3)
5. CHECK     -> python scripts/capa_check.py capa.json
6. VERIFY    -> effectiveness: measurable criterion, window, method, owner, date
7. UPDATE    -> PFMEA, control plan, procedures, risk register; close only after effectiveness
8. MONITOR   -> python scripts/capa_aging.py capa_log.csv --today YYYY-MM-DD   (weekly / monthly)
```

## Review Codes (capa_check.py)

| Code | Severity | Problem |
|------|----------|---------|
| CP001 | high | No root cause, or it blames a person / restates the symptom |
| CP002 | high | Only corrections (sort, rework, scrap, replace) |
| CP003 | high | No measurable effectiveness criterion, method and date |
| CP004 | medium | Strongest action is training or a reminder |
| CP005 | medium | Action without owner or due date |
| CP006 | medium | Cause without action, or action without cause |
| CP007 | medium | Root cause not verified |
| CP008 | low | No check for similar nonconformities |
| CP009 | low | No FMEA / control plan / document / risk update |

```
Action strength:
  [4] error-proof       Set tool life counter to 220 parts with machine interlock that stops t
CP001 [high] RC1 'Operator error - not careful when packing' blames a person: ask why the process allowed it
```

The 10.2 steps, correction vs corrective vs preventive, CAPA triggers, root-cause quality, effectiveness checks and
stage limits: [capa-structure.md](references/capa-structure.md). The strength hierarchy and how to turn weak
actions into strong ones: [action-strength.md](references/action-strength.md).

## CAPA Log (capa_aging.py)

| Code | Severity | Finding |
|------|----------|---------|
| CA001 | high | Overdue |
| CA002 | medium | Stuck in a stage beyond its limit (containment 7, root cause 30, action 60, verification 120 days) |
| CA003 | low | Closed within 14 days: effectiveness probably not verified |

## Output Format

Deliver the CAPA as: problem statement, correction/containment, root causes (occurrence and escape, with
verification evidence), action table (action, cause, strength, owner, due), extension to similar items,
effectiveness plan, documents updated. Then the `capa_check.py` result with every high issue resolved.

## Scripts

```bash
python scripts/capa_check.py capa.json
```
Keys: capa_id, problem, correction, root_causes (id, cause, verified, evidence), actions (action, type, cause_id,
owner, due), effectiveness (criteria, method, due), similar_check, updates. Exit codes: 0 no high issues, 1 high
issues, 2 read or JSON error.

```bash
python scripts/capa_aging.py capa_log.csv --today 2026-10-24
```
Columns: capa_id, source, owner, opened, stage, stage_since, due, closed. Exit codes: 0 none overdue,
1 overdue CAPAs, 2 read error.

## Additional Resources

| File | Content |
|------|---------|
| [capa-structure.md](references/capa-structure.md) | ISO 9001 10.2 steps, correction vs corrective vs preventive, triggers, root-cause quality, effectiveness, stage limits |
| [action-strength.md](references/action-strength.md) | Action hierarchy with examples, weak -> strong rewrites, linking actions to causes |
