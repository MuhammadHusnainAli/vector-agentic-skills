# Documented Processes and Customer-Specific Requirements

## Documented processes

Where IATF 16949 says "documented process", auditors expect a written, controlled description (procedure,
flowchart or equivalent) **and** evidence it is followed. `iatf_gap.py --list-processes` lists the 26 tracked here:

4.4.1.2 product safety; 6.1.2.2 preventive action; 6.1.2.3 contingency plans; 7.1.5.2.1 calibration records;
7.2.1 training needs; 7.2.3 internal auditor competency; 7.3.2 employee motivation; 7.5.3.2.2 engineering
specifications; 8.3.1.1 design; 8.3.3.3 special characteristics; 8.3.4.4 product approval; 8.4.1.2 supplier
selection; 8.4.2.1 type and extent of control; 8.4.2.2 statutory and regulatory requirements; 8.4.2.4 supplier
monitoring; 8.5.1.5 TPM; 8.5.6.1 change control; 8.5.6.1.1 temporary change of process controls; 8.7.1.4 rework;
8.7.1.5 repair; 8.7.1.7 disposition; 9.2.2.1 internal audit programme; 10.2.3 problem solving; 10.2.4 error-proofing;
10.2.5 warranty management; 10.3.1 continual improvement.

Published counts vary (some lists include contingency plans as documents, others count sub-clauses separately);
compare against the standard and current Sanctioned Interpretations.

Processes can be combined: one "Change management" procedure can cover 8.5.6.1 and 8.5.6.1.1; one "Problem
solving" procedure can cover 10.2.3 and 6.1.2.2.

## Customer-specific requirements

| Step | Practice |
|------|----------|
| Collect | Download each customer's CSR document (OEM supplier portals; IATF website lists OEM CSRs) |
| Review | Within the 10-working-day engineering specification window (7.5.3.2.2); record the review |
| Map | CSR matrix: CSR clause -> IATF clause -> where met (procedure, form, KPI) -> owner |
| Implement | Update procedures, control plans, PPAP practice, problem-solving format (e.g. customer 8D portal) |
| Audit | Include CSRs in internal audits; the certification body samples them |
| Monitor | Check for new CSR revisions at least quarterly |

Typical CSR topics: PPAP level and submission method, problem-solving format and deadlines, special
characteristic symbols, safe-launch / early-production containment, annual layout requirements, supplier
quality manual, packaging and labelling, warranty, escalation (new business hold, controlled shipping levels).
