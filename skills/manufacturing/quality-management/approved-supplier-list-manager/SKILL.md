---
name: approved-supplier-list-manager
description: "Manage and audit an approved supplier list (ASL) / external provider register for ISO 9001 8.4.1, IATF 16949 8.4 and AS9100 8.4.1: supplier status (approved, conditional, probation, pending, disqualified), scope of approval by commodity and process, risk class, certification and expiry, re-evaluation intervals by risk, conditions with end dates, single-source contingency, approver and customer-directed sources. Audits the list for expired or expiring certificates, overdue re-evaluations, conditional or probation status past its decision date, high-risk suppliers without the required certification, single-source suppliers without backup and missing approvers, and checks purchase orders for suppliers that are off-list, disqualified or pending, or buying outside the approved scope. Covers ERP blocks, PO requirements, off-list and emergency purchases. Use when maintaining the ASL, preparing for an audit of purchasing, or after an off-list purchase."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Approved Supplier List Manager

The ASL is only a control if it is current and purchasing cannot bypass it. Audit findings usually come from
four places: expired certificates, re-evaluations never done, conditional suppliers left conditional for years,
and purchase orders placed with suppliers or for processes the list does not cover. `scripts/asl_audit.py`
checks all four.

## Trigger Conditions

Activate this skill when the user:
- Maintains an approved supplier list or external provider register
- Is preparing for an ISO 9001, IATF 16949 or AS9100 audit of purchasing
- Found material bought from an unapproved supplier, or outside a supplier's scope
- Asks how often to re-evaluate suppliers or what statuses to use

New supplier approval: [supplier-audit-questionnaire-builder](../supplier-audit-questionnaire-builder/SKILL.md);
performance data for re-evaluation: [supplier-quality-scorecard-builder](../supplier-quality-scorecard-builder/SKILL.md).

## Workflow

```
1. STRUCTURE -> ASL columns and statuses (asl-structure.md)
2. AUDIT     -> python scripts/asl_audit.py asl.csv --today YYYY-MM-DD
3. POs       -> python scripts/asl_audit.py asl.csv --pos last_month_pos.csv --today YYYY-MM-DD
4. FIX       -> off-list or out-of-scope buys: quarantine, NCR on purchasing, close the system gap
5. DECIDE    -> conditional / probation past end date: approve or disqualify
6. PREVENT   -> ERP status block, scope codes, certificate watch (purchasing-controls.md)
```

## Checks (asl_audit.py)

| Code | Severity | Problem |
|------|----------|---------|
| AL001 | high | PO with an off-list, pending or disqualified supplier |
| AL002 | high | PO outside the approved scope |
| AL003 | medium | Certificate expired or expiring |
| AL004 | medium | Re-evaluation overdue (12 / 24 / 36 months by risk) |
| AL005 | medium | Conditional / probation past its decision date or without one |
| AL006 | medium | High-risk supplier without required certification |
| AL007 | low | Single-source high-risk supplier without backup |
| AL008 | low | No approver |

```
AL002 [high] PlastiForm: PO PO-9004: 'anodising' is outside the approved scope (injection moulding)
AL005 [medium] CastCorp: probation ended 2026-09-30: decide approve or disqualify
```

ASL columns, status meanings, standards' requirements and re-evaluation intervals:
[asl-structure.md](references/asl-structure.md). ERP blocks, PO requirements, off-list and emergency purchases:
[purchasing-controls.md](references/purchasing-controls.md).

## Output Format

Deliver the ASL summary (counts by status), the findings ordered by severity with the action and owner for each,
decisions needed (conditional / probation suppliers), and system fixes to prevent recurrence.

## Scripts

```bash
python scripts/asl_audit.py asl.csv --today 2026-10-24
python scripts/asl_audit.py asl.csv --pos pos.csv --today 2026-10-24 --require-cert "IATF 16949" --warn-days 60
```
ASL columns: supplier, status, scope (`;`-separated), risk, certification, cert_expiry, last_evaluation,
approved_by, condition_until, single_source, backup. PO columns: po, supplier, scope, date. Exit codes: 0 no high
findings, 1 high findings, 2 read or usage error.

## Additional Resources

| File | Content |
|------|---------|
| [asl-structure.md](references/asl-structure.md) | Requirements, ASL columns, statuses, re-evaluation intervals |
| [purchasing-controls.md](references/purchasing-controls.md) | ERP blocks, PO requirements, off-list purchases, emergency buys |
