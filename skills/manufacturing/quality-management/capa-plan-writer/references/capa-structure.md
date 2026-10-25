# CAPA Structure (ISO 9001 10.2)

## The steps 10.2.1 requires

| Step | Clause | Content |
|------|--------|---------|
| React | 10.2.1 a | Control and correct the nonconformity; deal with consequences (correction, containment) |
| Evaluate need | 10.2.1 b | Review the nonconformity, determine its causes, check whether similar ones exist or could occur |
| Act | 10.2.1 c | Implement the actions needed |
| Review effectiveness | 10.2.1 d | Did the action stop recurrence? |
| Update | 10.2.1 e, f | Update risks and opportunities; change the QMS if needed |
| Record | 10.2.2 | Nature of the nonconformity, actions, results of corrective action |

## Correction vs corrective vs preventive

| Term | Acts on | Example |
|------|---------|---------|
| Correction | The nonconforming item | Scrap 77 parts; 100% sort of stock |
| Containment | Suspect product everywhere | Quarantine stock, check transit and customer |
| Corrective action | The cause of a nonconformity that happened | Tool-life interlock at 220 parts |
| Preventive action (2015: risk-based thinking) | The cause of a potential nonconformity | Apply the interlock to the other three lathes before they fail |

ISO 9001:2015 dropped the separate "preventive action" clause; extending an action to similar products, machines
and sites (10.2.1 b 3) and the risk register (6.1) cover it. Many companies still use the term CAPA.

## When a CAPA is required

Always for: customer complaints and escapes, repeat nonconformities, major audit findings, safety or regulatory
issues, high-cost events. Optional for one-off minor internal NCRs (trend them instead). Define the triggers in the
procedure so the decision is not ad hoc.

## Root cause quality

- Find the cause of **occurrence** (why it was made wrong) and of **escape** (why it was not detected).
- A root cause is verified when you can switch the problem on and off, reproduce it, or show it with data.
- "Human error" is never a root cause: ask why the process made the error possible, likely and undetected.
- Use 5 Why for simple chains, fishbone for many possible causes, 8D for customer or cross-functional problems.

## Effectiveness check

| Element | Example |
|---------|---------|
| Criterion (measurable) | 0 bore NCRs and Cpk >= 1.33 |
| Window | 3 months or 6 lots, enough opportunities for the problem to recur |
| Method | NCR log + SPC review; customer scorecard |
| Owner and date | Quality engineer, 2027-03-01 |
| If not effective | Re-open root cause analysis; do not extend the date silently |

See [capa-effectiveness-checker](../../capa-effectiveness-checker/SKILL.md) for the statistics.

## CAPA stage limits (typical)

| Stage | Limit |
|-------|-------|
| Containment | 24 hours to 7 days |
| Root cause | 30 days |
| Actions implemented | 60-90 days |
| Effectiveness verified | 90-120 days after implementation |
