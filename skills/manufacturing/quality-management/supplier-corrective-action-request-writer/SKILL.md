---
name: supplier-corrective-action-request-writer
description: "Write supplier corrective action requests (SCARs) and evaluate the supplier's response: when to issue a SCAR, a problem statement with requirement, actual result, quantity and evidence, impact and cost recovery, response deadlines (containment 24-48 hours including stock at the supplier, in transit and at the customer with a clean point; root cause in about 10 working days; closure with effectiveness in 30-60 days). Checks the request for missing facts and loose deadlines, and checks the response for incomplete containment, missing or blame-based occurrence and escape causes, correction- or training-only actions, missing verification, effectiveness, PFMEA and control plan updates or read-across, and late steps; returns accept, accept with comments or reject. Use when a supplier ships nonconforming product, when issuing or reviewing a SCAR or supplier 8D, or when deciding whether to close a supplier corrective action."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Supplier Corrective Action Request Writer

A SCAR works when the supplier receives facts it can investigate and deadlines it must meet, and when the
response is judged against clear criteria rather than accepted because it arrived. `scripts/scar_check.py` checks
both sides: the request before it is sent, and the supplier's response before it is accepted.

## Trigger Conditions

Activate this skill when the user:
- Needs to issue a SCAR for a supplier nonconformity, repeat defect or audit finding
- Received a supplier's SCAR or 8D response and must accept or reject it
- Asks what to require from a supplier and by when
- Wants to know whether a supplier corrective action can be closed

The 8D format the supplier may use: [8d-problem-solving-report-writer](../8d-problem-solving-report-writer/SKILL.md);
long-term improvement: [supplier-development-plan-writer](../supplier-development-plan-writer/SKILL.md).

## Workflow

```
1. DECIDE   -> SCAR needed? (production or customer impact, repeat, safety, scorecard trigger)
2. WRITE    -> requirement vs actual, quantity, evidence, impact, deadlines (writing-the-scar.md)
3. CHECK    -> python scripts/scar_check.py scar.json   (request only: "ready to send")
4. RESPONSE -> add the supplier's response to the JSON
5. EVALUATE -> python scripts/scar_check.py scar.json   (ACCEPT / ACCEPT WITH COMMENTS / REJECT)
6. CLOSE    -> only after effectiveness evidence; record on the scorecard
```

## Checks (scar_check.py)

| Code | Severity | Problem |
|------|----------|---------|
| SR001 | high | Problem lacks requirement, actual, quantity or evidence |
| SR002 | medium | Due dates missing or loose |
| SR101 | high | Containment incomplete or no clean point |
| SR102 | high | Occurrence or escape cause missing or human error |
| SR103 | high | Corrections or training only; a cause without action |
| SR104 | medium | No verification or effectiveness plan |
| SR105 | medium | No PFMEA / control plan update or read-across |
| SR106 | medium | Late response steps |

```
SR102 [high] occurrence cause 'Operator error during pouring' blames a person: why did the process allow it?
SR102 [high] no escape root cause (why was it not detected before shipping?)
Supplier response: REJECT
```

When to issue, request content, an example problem statement and cost recovery:
[writing-the-scar.md](references/writing-the-scar.md). Accept / reject criteria per element, responding and
escalation: [evaluating-responses.md](references/evaluating-responses.md).

## Output Format

For a request: the SCAR text (identification, problem, impact, required response and dates) and the check result.
For a response: the verdict, the reasons per element, the new due dates for rejected items, and the closure criteria.

## Scripts

```bash
python scripts/scar_check.py scar.json
```
Keys: scar_id, supplier, part, issued, ncr_ref, problem (requirement, actual, quantity, evidence), due
(containment, root_cause, closure), response (containment, containment_date, clean_point, occurrence_cause,
escape_cause, cause_verification, actions with addresses occurrence/escape, effectiveness, fmea_control_plan,
read_across, root_cause_date, closure_date). Exit codes: 0 request ready / response accepted, 1 incomplete request
or rejected response, 2 read or JSON error.

## Additional Resources

| File | Content |
|------|---------|
| [writing-the-scar.md](references/writing-the-scar.md) | When to issue, request content, example, cost recovery |
| [evaluating-responses.md](references/evaluating-responses.md) | Accept / reject criteria, responding to the supplier, escalation |
