---
name: internal-audit-schedule-planner
description: "Plan a risk-based ISO 9001 internal audit programme (clause 9.2, ISO 19011): audit frequency per process from risk, previous results and changes; a load-balanced 12-month calendar that schedules overdue and never-audited processes first; auditor assignment that never puts an auditor in their own department; clause coverage check so every clause family 4-10 is audited each cycle; audit types (process, clause, product, trail, layered); auditor competence, independence and pool sizing; programme records and tracking. Use when building or revising the annual internal audit schedule, preparing for certification or surveillance, after a finding that the audit programme is not risk-based or does not cover all clauses, or when a small company needs independent auditors."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Internal Audit Schedule Planner

An internal audit programme must be planned, risk-based (importance, changes, previous results), cover the whole
QMS and use auditors who are not auditing their own work. `scripts/audit_schedule.py` turns a process list into a
12-month programme with frequencies, months, independent auditors and a clause-coverage check.

## Trigger Conditions

Activate this skill when the user:
- Needs the annual internal audit schedule or programme
- Asks how often to audit each process, or whether the programme is "risk-based"
- Has a finding that not all clauses or processes were audited, or auditors audited their own area
- Is a small company without enough independent auditors

For writing the checklist for each audit use [iso-audit-checklist-generator](../iso-audit-checklist-generator/SKILL.md).

## Workflow

```
1. LIST      -> processes with department, clauses in scope, risk, last result, recent change, last audit date
2. AUDITORS  -> trained auditors and their departments
3. PLAN      -> python scripts/audit_schedule.py processes.csv --start 2027-01 --auditors auditors.csv
4. COVERAGE  -> fix AS001: add missing clause families to a process scope (usually 4, 6, 9.3, 10)
5. AGREE     -> confirm dates with process owners; publish a quarter ahead
6. TRACK     -> completion % monthly; review the programme at management review
```

## Frequency Rules

| Situation | Audits per year |
|-----------|-----------------|
| High risk (customer-facing, special characteristics, special processes) | 2 |
| Medium / low risk | 1 |
| Major finding last time, or significant change | +1 |
| Low risk with good results (`--biennial-low`, only if the CB accepts it) | 0.5 |

Overdue or never-audited processes go into the first quarter; other audits land near their due month in the
least-loaded month. Frequency factors, coverage matrix, audit types and programme records:
[risk-based-programme.md](references/risk-based-programme.md).

## Checks (audit_schedule.py)

| Code | Severity | Finding |
|------|----------|---------|
| AS001 | high | A clause family (4-10) is not covered this cycle |
| AS002 | high | No independent auditor for a process |
| AS003 | medium | Process overdue (scheduled in the first quarter) |
| AS004 | low | Process never audited |

```
2027-01  Purchasing                    high    8.4                   A. Khan
2027-05  Purchasing                    high    8.4                   A. Khan
AS003 [medium] Purchasing: last audited 2026-06-01 (7 months ago, interval 4)
AS001 [high] clause 10 is not covered by any audit this cycle; add it to a process scope
```

Independence rules, ISO 19011 competence evidence, pool sizing and small-company options:
[auditor-competence-independence.md](references/auditor-competence-independence.md).

## Output Format

Deliver:
1. **Programme table** - month, process, risk, clauses, auditor (from `audit_schedule.py`).
2. **Rationale** - why each process has its frequency (risk, results, changes).
3. **Coverage** - process x clause confirmation that 4-10 are all covered.
4. **Auditor plan** - who audits what, independence and competence gaps, training needed.
5. **Tracking** - how completion and follow-up will be reported.

## Scripts

```bash
python scripts/audit_schedule.py processes.csv --start 2027-01 --auditors auditors.csv
python scripts/audit_schedule.py processes.csv --start 2027-01 --biennial-low --csv > programme.csv
```
Processes CSV: process, department, clauses (`;`-separated), risk, last_result (none/good/minor/major), changed,
last_audit. Auditors CSV: auditor, department. Exit codes: 0 complete, 1 coverage or independence problems,
2 read or usage error.

## Additional Resources

| File | Content |
|------|---------|
| [risk-based-programme.md](references/risk-based-programme.md) | 9.2.2 requirements, frequency factors, coverage matrix, audit types, records, tracking |
| [auditor-competence-independence.md](references/auditor-competence-independence.md) | Independence, ISO 19011 competence, pool sizing, small-company options |
