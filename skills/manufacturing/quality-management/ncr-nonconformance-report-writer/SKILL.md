---
name: ncr-nonconformance-report-writer
description: "Write and check nonconformance reports (NCRs) for ISO 9001 8.7, IATF 16949 8.7 and AS9100: requirement vs actual description with drawing revision and measured values, part, lot and quantities, detection point, containment across machine, WIP, stock, transit, customer and supplier, disposition (rework, repair, use-as-is, scrap, return to supplier, regrade) with MRB authority, concessions and deviation permits, re-inspection after rework, and when to escalate to CAPA or 8D. Checks NCRs for missing requirement or extent, incomplete containment for late detection, use-as-is or repair without concession, rework without re-inspection and vague descriptions; trends an NCR log with Pareto by defect, part, supplier or cost, repeat part/defect combinations, aging open NCRs, escape rate and unrecorded cost. Use when raising or reviewing an NCR, running an MRB, preparing monthly quality reports or deciding whether an NCR needs a corrective action."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# NCR Nonconformance Report Writer

An NCR answers four questions: what does not meet which requirement, how much and where is it, what was done
to contain it, and what will happen to it (with whose authority). `scripts/ncr_check.py` checks individual NCRs;
`scripts/ncr_trend.py` turns the NCR log into Paretos, repeats and escalations.

## Trigger Conditions

Activate this skill when the user:
- Found a nonconforming part, batch or service and needs to raise an NCR
- Is running a material review board or choosing a disposition
- Wants to know whether use-as-is or repair needs customer approval
- Needs a monthly NCR Pareto or to decide which NCRs need a CAPA

Root cause and corrective action: [capa-plan-writer](../capa-plan-writer/SKILL.md) or
[8d-problem-solving-report-writer](../8d-problem-solving-report-writer/SKILL.md).

## Workflow

```
1. DESCRIBE   -> requirement (spec, revision) vs actual (measured, method), part, lot, quantities, photo
2. CONTAIN    -> every location suspect product can be: machine, WIP, stock, transit, customer, supplier
3. CHECK      -> python scripts/ncr_check.py ncr.json
4. DISPOSE    -> MRB decides; concession for use-as-is/repair; re-inspect rework
5. ESCALATE   -> CAPA/8D when customer-detected, repeat, safety-related or high cost
6. TREND      -> python scripts/ncr_trend.py ncr_log.csv --today YYYY-MM-DD   (monthly)
```

## NCR Checks (ncr_check.py)

| Code | Severity | Problem |
|------|----------|---------|
| NR001 | high | No requirement vs actual |
| NR002 | high | Part, lot or quantity missing |
| NR003 | high | No containment, or late detection without stock/WIP/transit/customer checked |
| NR004 | high | Use-as-is or repair without concession |
| NR005 | medium | Rework/repair without re-inspection |
| NR006 | medium | Customer-detected or repeat without CAPA |
| NR007 | medium | Invalid disposition or no authority |
| NR008 | low | Vague description, no measured value |
| NR009 | low | Detection point or detector missing |

Field-by-field guide, strong vs weak descriptions, containment checklist and severity levels:
[ncr-writing-guide.md](references/ncr-writing-guide.md).

## Dispositions

| Disposition | Needs |
|-------------|-------|
| Rework | Rework instruction + re-inspection to the original requirement |
| Repair / use-as-is | Concession from customer or design authority (mandatory under IATF 16949 and AS9100 when they own the design) |
| Scrap | Controlled scrap, quantity recorded |
| Return to supplier | Supplier notified; SCAR if systemic |
| Regrade | Engineering approval, re-identification |

MRB roles, concessions vs deviation permits and scrap control: [disposition-and-mrb.md](references/disposition-and-mrb.md).

## Trend Findings (ncr_trend.py)

| Code | Severity | Finding |
|------|----------|---------|
| NT001 | high | Same part + defect repeated: one systemic CAPA |
| NT002 | medium | NCR open too long |
| NT003 | medium | Escape (customer-detected) rate above limit |
| NT004 | low | NCRs without cost |

```
NT001 [high] VB-2210 / bore oversize: 3 NCRs - systemic; one CAPA for all, not 3 corrections
NT003 [medium] escape rate 20.0% > 10%: review detection controls (PFMEA detection, final inspection)
```

## Output Format

For an NCR: the completed fields (ID, detection, part/rev/lot, requirement, actual, quantities, containment by
location, disposition, authority, concession, re-inspection, CAPA link) and the `ncr_check.py` result.
For a log review: Pareto table, monthly trend, escapes, cost, and the escalation list.

## Scripts

```bash
python scripts/ncr_check.py ncr.json          # one NCR object or a list
```
Exit codes: 0 no high findings, 1 high findings, 2 read or JSON error.

```bash
python scripts/ncr_trend.py ncr_log.csv --today 2026-10-24
python scripts/ncr_trend.py ncr_log.csv --by supplier --weight cost --repeat 3 --max-open 30 --escape-limit 10
```
Log columns: ncr_id, date, part, defect, supplier, detection_point, qty, cost, status, closed_date. Exit codes:
0 no repeats, 1 repeats found, 2 read error.

## Additional Resources

| File | Content |
|------|---------|
| [ncr-writing-guide.md](references/ncr-writing-guide.md) | NCR fields, requirement vs actual, containment checklist, severity |
| [disposition-and-mrb.md](references/disposition-and-mrb.md) | Dispositions and approvals (ISO 9001, IATF, AS9100), MRB, concessions vs deviations, scrap control |
