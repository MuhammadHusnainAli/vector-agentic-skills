# Evaluating Recommenders

## Splits

| Split | Use | Risk |
|-------|-----|------|
| Global temporal cut-off | closest to deployment; preferred | test users may be new (evaluate them separately) |
| Leave-last-n per user | common in papers; every user is evaluated | different users' test periods overlap with others' training |
| Random per-user holdout | only without timestamps | leaks future popularity and trends |
| Random over all interactions | never | the worst leakage |

Tune hyperparameters on a validation split cut before the test period, then refit on train + validation.

## Accuracy metrics @k

| Metric | Definition (per user, averaged) |
|--------|---------------------------------|
| Precision@k | relevant items in the top k / k |
| Recall@k | relevant items in the top k / all relevant items of the user |
| Hit rate@k | 1 if any relevant item is in the top k |
| MRR | 1 / rank of the first relevant item |
| MAP@k | mean of precision at each relevant position, divided by min(\|relevant\|, k) |
| NDCG@k | DCG / ideal DCG with gains 2^rel - 1 and log2(rank + 1) discounts |

For a single held-out item per user (leave-last-1), hit rate@k equals recall@k and MRR is common.

## Beyond accuracy

| Metric | Definition in rec_eval.py |
|--------|---------------------------|
| Coverage | distinct recommended items / catalogue (items in train) |
| Novelty | mean of -log2(item train popularity / number of train users) |
| Popularity bias | mean train count of recommended items / mean train count of the catalogue |
| Personalisation | 1 - mean pairwise Jaccard of users' top-k sets |
| Diversity | mean share of distinct categories within a list |

There is a trade-off: popularity scores high on accuracy and low on coverage and novelty. Report both, and
decide with the business which matters.

## Pitfalls

| Pitfall | Effect |
|---------|--------|
| Sampled metrics (rank the true item among 100 random negatives) | inconsistent with full ranking; can reverse model order (Krichene and Rendle 2020). Rank against the full catalogue |
| Not filtering seen items | inflated scores for repeat-heavy data, or penalised good models |
| Evaluating only warm users | hides cold-start failure |
| Popularity bias in the test set | models that push bestsellers look better; check item-segment results |
| Tuning on the test set | optimistic results |
| Comparing models at different k | choose k from the product (slots on screen) |

## Offline vs online

Offline metrics estimate how well the model predicts what users did under the old system. Online, the new
recommendations change what users see and do. Expect gaps. Use offline evaluation to shortlist, A/B tests to
decide, and counterfactual estimators (inverse propensity scoring on logged impressions) when logs include
the propensities.
