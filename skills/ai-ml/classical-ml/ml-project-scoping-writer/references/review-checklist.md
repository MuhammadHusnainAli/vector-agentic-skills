# Scope Review Checklist

## Checklist

**Decision and value**
- [ ] The decision, the acting team and its capacity are named.
- [ ] The problem is quantified (volume, cost, rate).
- [ ] Value is estimated against the current process, with a ceiling.

**Success**
- [ ] One primary metric at the operating point, on a deployment-like split.
- [ ] A numeric target and the baseline's value on the same split.
- [ ] Guardrails with limits, including per-segment floors.
- [ ] An online confirmation plan (A/B, holdout) with duration.

**Data**
- [ ] Label defined as a query with its window and population.
- [ ] Each source has an owner, freshness and availability at prediction time.
- [ ] Known leaks and exclusions are listed.

**Plan**
- [ ] Phased approach starting with a baseline.
- [ ] In-scope and out-of-scope lists.
- [ ] Dated milestones with checkable exit criteria.
- [ ] Go/no-go criteria per gate.

**Risk and ownership**
- [ ] ML-specific risks with mitigations.
- [ ] Team, FTE and run cost.
- [ ] Post-launch owner, monitoring and retraining plan.
- [ ] Fairness/regulatory review where decisions affect people.

## Red-flag phrases

| Phrase | Question to ask |
|--------|-----------------|
| "leverage AI/ML" | Which prediction feeds which decision? |
| "high accuracy" | Which metric, at which operating point, versus what? |
| "real-time" | What latency, and is the data real-time too? |
| "we have all the data" | When is each field written relative to the prediction? |
| "the model will learn" | From which label, observed when? |
| "phase 2: productionise" | Who owns serving, monitoring and retraining? |
| "insights" | What will someone do differently with them? |

## Comment templates

- *Missing baseline:* "What does today's process score on recall@400 for the same holdout? Without it we
  cannot tell whether the model adds value."
- *Metric without operating point:* "AUC summarises all thresholds; the team calls 400 a week. Please make
  recall@400 (or precision@400) the primary metric and keep AUC as secondary."
- *No out-of-scope:* "Please list what this project will not do; real-time scoring and offer choice seem
  likely to creep in."
- *Milestone without exit criterion:* "How will we know 'model ready' is done? Suggest: recall@400 >= 0.45 on
  the holdout with the CI above the rule."
- *Leak risk:* "Is `account_status` read as of the scoring date or today? If today, it leaks the outcome."
- *Feedback loop:* "Calling customers changes who churns. Can we keep a random 5% untreated group?"

## Sign-off roles

| Role | Signs off on |
|------|--------------|
| Product/business owner | decision, value, capacity, success criteria |
| ML lead | approach, validation plan, risks |
| Data owner(s) | label definition, source availability |
| Acting team lead | workflow fit, capacity, adoption |
| Model risk / legal (if applicable) | fairness, explainability, regulatory |
| Platform/MLOps | serving, monitoring, on-call |
