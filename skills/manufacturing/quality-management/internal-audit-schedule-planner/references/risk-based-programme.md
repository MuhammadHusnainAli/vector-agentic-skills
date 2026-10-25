# Risk-Based Audit Programme (ISO 9001 9.2.2, ISO 19011 clause 5)

## What 9.2.2 requires of the programme

Planned intervals; frequency, methods, responsibilities, planning requirements and reporting that consider
**the importance of the processes, changes affecting the organization, and the results of previous audits**;
criteria and scope for each audit; objective and impartial auditors; results reported to relevant management;
correction and corrective action without undue delay; records retained.

## Frequency factors

| Factor | Raises frequency | Lowers frequency |
|--------|------------------|------------------|
| Process risk | Customer-facing, safety/special characteristics, special processes, high volume | Support processes with little effect on product |
| Previous results | Major findings, repeat minors, open CAPAs | Two clean audits in a row |
| Change | New equipment, new manager, new product, ERP migration, relocation | Stable for over a year |
| Performance | KPIs off target, customer complaints, escapes | KPIs stable and on target |
| External | Customer audit findings, certification body concerns | - |

`audit_schedule.py` uses: high risk twice a year, others yearly, +1 audit after a major result or significant change,
optionally every 2 years for good low-risk processes. Many certification bodies expect every process and clause to
be covered **at least once a year**; use biennial audits only if the CB and customers accept them.

## Coverage matrix

Build a process x clause matrix and confirm every clause family (4-10) is audited each cycle. Clauses often missed:

| Clause | Put it in the scope of |
|--------|------------------------|
| 4.1, 4.2, 6.1, 6.3 | Leadership / planning audit (interview top management) |
| 7.1.6, 7.4 | Every process audit (ask how knowledge and communication work) |
| 9.1.2, 9.1.3 | Leadership or customer-service audit |
| 9.3 | Leadership audit (sample last management review) |
| 10.2, 10.3 | Quality / CAPA audit, and in every process (trace one NCR to closure) |

## Audit types to mix

| Type | Use |
|------|-----|
| Process audit (turtle) | Default: follows inputs to outputs within one process |
| Clause / system audit | Coverage of 4, 5, 6, 9.3 that no process owns |
| Product audit | Re-inspect finished product against the drawing to test the whole chain |
| Trail audit | Follow one order from quote to delivery across processes |
| Layered process audit | Short, frequent shop-floor checks (see layered-process-audit-designer) |

## Programme records

Programme (this table), audit plans, checklists, reports, finding records, CAPA follow-up, auditor competence
evidence. Review the programme at management review: completed vs planned, findings by process, overdue actions.

## Keeping the programme on track

- Publish dates a quarter ahead and agree them with process owners.
- Track completion % monthly; a slipped audit is rescheduled within the same quarter.
- Spread audits across the year so the last months are not a rush before surveillance.
