# Hybrid Patterns

## 1. Guardrail rules around the model

```python
def decide(txn, model):
    # Hard policy first: never delegated to a model.
    if txn.card_id in BLOCKLIST or txn.country in SANCTIONED:
        return "decline", "policy:blocklist"
    if txn.amount > HARD_LIMIT[txn.card_tier]:
        return "review", "policy:limit"
    p = model.predict_proba(features(txn))[0, 1]
    if p >= T_DECLINE:
        return "decline", f"model:{p:.3f}"
    if p >= T_REVIEW:
        return "review", f"model:{p:.3f}"
    return "approve", f"model:{p:.3f}"
```
Log the reason string for every decision: it becomes the audit trail and tells you which layer acted.

## 2. Eligibility filter before scoring

Score only rows the model was trained for. Rules route the rest:
```python
if customer.tenure_days < 30:
    return cold_start_rule(customer)          # model has no history features yet
return model_score(customer)
```

## 3. Model score inside a business rule

Stakeholders keep the rule shape they trust; the model supplies a better signal:
```sql
CASE WHEN churn_score >= 0.6 AND monthly_value >= 50 THEN 'call'
     WHEN churn_score >= 0.6 THEN 'email'
     ELSE 'none' END AS retention_action
```

## 4. Rules for cold start, ML when data exists

New users, products or merchants lack the history a model needs. Use popularity or segment rules until a
volume threshold, then switch to the model, ideally with a blended score during the transition:
```python
w = min(1.0, n_interactions / 20)
score = w * model_score + (1 - w) * rule_score
```

## 5. ML proposes rules, humans approve

1. Fit a shallow tree (`rule_learner.py`) or mine high-lift segments from SHAP interaction values.
2. Analysts review candidate rules for sense, fairness and stability.
3. Approved rules enter the rule engine with an owner and an expiry date.

Good for regulated domains, and for adversarial attacks where analysts need a rule within hours.

## 6. Human overrides as labels

Let analysts override decisions with a reason code. Overrides:
- fix individual errors now;
- become high-value labels (disagreements with the model);
- reveal rules the model has not learned.

Monitor override rates per analyst and per segment; a rising rate is an early drift signal.

## 7. Champion/challenger

```
traffic -> hash(entity_id) % 100
    0..89   -> champion (current rules)      -> act
    90..99  -> challenger (model + guardrails) -> act
    all     -> both scored and logged (shadow) -> compare offline
```
Hash on a stable entity ID so each entity always sees one policy. Compare outcomes per arm with a
pre-registered metric and duration.

## 8. Score bands with human review in the middle

```
p < 0.05        auto-approve
0.05 <= p < 0.6 human review (capacity-bound: top-K by p)
p >= 0.6        auto-decline (with reason codes)
```
Tune the band edges from capacity and error costs; measure precision in each band.

## Choosing a pattern

| Need | Pattern |
|------|---------|
| Legal or safety constraint | 1 |
| Population the model does not cover | 2, 4 |
| Stakeholders need rule-shaped decisions | 3, 8 |
| Fast response to new attack patterns | 5 |
| Build trust and collect labels | 6, 7 |
