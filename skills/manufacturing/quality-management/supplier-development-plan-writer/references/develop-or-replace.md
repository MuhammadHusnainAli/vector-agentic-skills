# Develop or Replace?

Supplier development costs engineering time on both sides. Spend it where the return is highest: suppliers that
are strategic, hard to replace, or carry a large share of spend and risk.

## Decision matrix

| | Poor performance, hard to replace (strategic, single source, unique process, large spend) | Poor performance, easy to replace |
|---|---|---|
| **Supplier willing to invest** | DEVELOP: joint plan, on-site support | Develop lightly, or replace if cheaper |
| **Supplier unwilling** | Escalate (executive, controlled shipping), develop a second source in parallel | REPLACE |

`dev_plan.py` scores priority as spend share x risk x performance gap (x 1.5 single source) and marks:
DEVELOP (gap and strategic / single source / >= 10% of spend), REPLACE (gap, small, replaceable), MONITOR (score >= 85).

## Signs development will work

- Supplier management attends the kick-off and assigns a named owner.
- Data are shared openly (their scrap, capability, OTD).
- Early actions are done on time.
- The supplier funds its share (equipment, people, training).

## Signs it will not

- Repeated SCAR rejections for the same issue.
- Commitments missed without warning.
- Ownership or financial instability; key people leaving.
Start a second source when two or more appear.
