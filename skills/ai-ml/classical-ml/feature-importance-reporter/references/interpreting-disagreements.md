# Interpreting Disagreements

## Split bias (IMPURITY-ONLY on a lone feature)

Tree learners pick the best split among many candidate thresholds. A continuous or high-cardinality feature
offers many more candidates, so by chance alone it finds splits that reduce training impurity. MDI and gain
then rank it highly even when it carries no signal. Strobl et al. (2007) showed this for random forests.

Recognise it:
- high gain share, permutation near zero or negative
- the feature has many distinct values (IDs, hashes, fine-grained timestamps, raw zip codes)
- no strongly correlated partner exists

Action: trust the held-out measure. For IDs, remove the feature. For legitimate continuous features, check
binned versions or monotone constraints.

## Redundancy (IMPURITY-ONLY or SHAP-VS-PERM with a correlated partner)

`total_charges` is roughly `tenure_months x monthly_charges`. The model splits on both, so gain and SHAP
credit both. Permuting `total_charges` alone hardly hurts because `tenure_months` still carries most of the
information.

Recognise it:
- |correlation| >= 0.7 with another feature (`gen_importance_script.py` builds the groups)
- grouped permutation is larger than the sum of single permutations (SHARED-INFO)

Action: report the group's importance. If you must drop one member, drop by domain sense (keep the
interpretable one) and confirm with a drop-column refit.

## Leakage (DOMINANT)

A single feature with more than half the held-out importance, especially one that is recorded after the
outcome (refund issued, cancellation reason, account closed date), points to leakage. Run
[target-leakage-detector](../../target-leakage-detector/SKILL.md). A genuinely decisive feature (e.g. a
credit bureau score) also dominates, so the timing of the data decides.

## Negative permutation importance

Shuffling the feature made the score *better*. Within noise (|mean| < 2 std) it means no effect. Clearly
negative means the model learned a pattern that does not hold out of sample, which is a sign of overfitting
on that feature. Drop it or regularise.

## Methods agree but the order changes between runs

Use `importance_stability.py` from
[feature-selection-analyzer](../../feature-selection-analyzer/SKILL.md). If the top-k set changes across folds,
the ranking is not a finding. Report tiers (clearly important / marginal / no effect) instead of ranks.

## Worked example (fixture importances.csv)

| Feature | gain | permutation | mean\|SHAP\| | Reading |
|---------|------|-------------|------------|---------|
| tenure_months | 24% | 39% | 32% | top on every method: a robust driver |
| total_charges | 22% | 2% | 11% | redundant with tenure x monthly charges: group them |
| monthly_charges | 11% | 1% | 4% | split bias / redundancy: little unique signal |
| customer_id_hash | 9% | -0.5% | 2% | ID-like split bias: remove |
| region_north | 0.7% | 0% | 0.4% | no effect |

## Importance versus usefulness versus causality

| Statement | Supported by |
|-----------|--------------|
| "The model relies on X" | SHAP, gain |
| "Removing X's information hurts held-out performance" | permutation, drop-column |
| "We could drop X without losing accuracy" | drop-column refit (and grouped permutation for correlated sets) |
| "Changing X changes the outcome" | none of these; needs experiments or causal inference |
