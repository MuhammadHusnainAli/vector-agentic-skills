# Pareto Analysis Done Right

## Steps

1. **Define the question.** Which defects cost us most? Which cause most customer complaints? Which lines?
2. **Define categories** that are specific and mutually exclusive ("burr on bore edge", not "machining defect").
3. **Pick the measure:** count (frequency), quantity of parts, cost (scrap + rework + warranty), or severity-weighted.
4. **Collect a representative period** (typically 1-3 months; enough for 50+ events).
5. **Sort descending, add cumulative %,** mark the vital few (usually up to 80%).
6. **Stratify** the top bars (by line, shift, supplier, part number) to find where the problem concentrates.
7. **Act on the top one or two**, then repeat the Pareto to confirm the bar shrank.

## Count vs cost

| Measure | Best for |
|---------|----------|
| Count / quantity | Process improvement: where defects happen most |
| Cost | Business case and prioritising projects (COPQ) |
| Severity-weighted | Customer risk: safety and function defects ahead of cosmetic |

When the top category differs between count and cost (PA003), decide with management which drives the
project. A frequent cheap defect (burr) and a rare expensive one (oversize bore) need different responses.

## Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Vague categories | "Other" or "misc" is the biggest bar (PA001) | Split by mechanism; require specific codes at data entry |
| Mixed populations | Flat Pareto (PA002) | Stratify by another factor; the concentration may be in one line or supplier |
| Different denominators | Lines with different volumes compared on counts | Use rates (defects per 1,000 parts) |
| One-off events | A single bad lot dominates | Treat separately (NCR / CAPA); Pareto the chronic losses |
| No follow-up | Same Pareto every month | Assign the top bar to a project with an owner; compare before/after |

## Before / after

Compare the same period length before and after an action (`--compare`); confirm the target bar shrank and no
other bar grew (problem moved downstream). Use rates if volume changed.
