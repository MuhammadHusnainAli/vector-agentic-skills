# Migrating From Rules to ML

## Step by step

1. **Inventory and measure the rules.** For a labelled period, compute each rule's hit rate, precision and
   incremental recall, and the whole rule set's precision/recall at its current volume. This is the bar.
2. **Check label provenance.** If outcomes were observed only for cases rules flagged (reviews, blocks), the
   labels are biased toward what rules already catch. Plan a random review sample (e.g. 1-2% of unflagged
   cases) to observe outcomes elsewhere.
3. **Split policy from prediction.** Separate rules that encode policy (must stay) from rules that are
   heuristics for risk (candidates for replacement).
4. **Build features the rules use, and more.** Rule conditions are good features; keep them so the model can
   at least match the rules.
5. **Offline comparison.** Same holdout, same capacity: rule precision@K vs model precision@K. Include
   learned rules (`rule_learner.py`) as an intermediate option.
6. **Shadow mode.** Score live traffic with the model; log decisions both ways; review a sample of
   disagreements with domain experts. Expect the model to find some cases rules miss and vice versa.
7. **Champion/challenger.** Route a small, randomised share of traffic to model + policy guardrails. Compare
   business outcomes with a pre-registered analysis.
8. **Ramp up and retire.** Increase traffic in steps; retire heuristic rules whose incremental recall drops
   to ~0 under the model. Keep a rules-only fallback path for outages.
9. **Keep learning signals.** Keep the random review sample and analyst overrides; they feed retraining and
   detect drift.

## Selection bias from rule-generated labels

```
Rules flag 5% of traffic -> analysts review flagged cases -> labels exist mostly for flagged cases
Model trained on these labels learns "what analysts confirmed among rule hits"
```
Consequences: the model can look excellent offline and still miss fraud types the rules never flagged.

Mitigations:
- Random exploration sample with outcomes observed (review or delayed chargeback).
- Train on outcomes that do not depend on review (e.g. chargebacks for approved transactions).
- Weight explored samples by inverse selection probability.
- Report metrics separately on the exploration sample.

## Rollback plan

| Trigger | Action |
|---------|--------|
| Precision on the challenger falls below rules for 2 consecutive days | route traffic back to rules |
| Feature pipeline outage | automatic fallback to rules |
| Score distribution shift (PSI > 0.25) | alert; pause ramp-up |
| Complaint or false-decline spike | revert and investigate |

## Pitfalls

| Pitfall | Effect | Fix |
|---------|--------|-----|
| Dropping policy rules into the model | policy violations when the model disagrees | keep policy rules as hard guardrails |
| Training only on rule-flagged outcomes | model inherits blind spots | exploration sample |
| Big-bang switch | no comparison, no rollback | shadow, then small traffic share |
| Retiring rules without measuring incremental recall | losing coverage of rare patterns | measure under the model before deleting |
| No logging of which layer decided | audits impossible | log rule ID / model version per decision |
| Analysts lose the ability to react to new attacks | slow response | keep an emergency-rule path |
