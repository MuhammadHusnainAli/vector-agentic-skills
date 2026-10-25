# Decision Rules and Pitfalls

## Choosing the ROPE (region of practical equivalence)

Decide before running the comparison:
- From the value model: the metric change that moves expected profit by less than the cost of switching
  (engineering, retraining, risk).
- From noise: the fold-to-fold standard deviation of a single model is a floor; differences below it are rarely
  meaningful.
- Typical tabular defaults: ±0.005 AUC/PR-AUC, ±1% relative MAE.

## Decision rules

| Rule | Statement |
|------|-----------|
| Best mean | pick the highest mean (only when differences exceed the ROPE) |
| Simplest within noise | among models not distinguishable from the best (corrected test p > 0.05 or P(equiv) high), pick the simplest / cheapest / most interpretable |
| One-SE rule | smallest/simplest model whose mean is within one standard error of the best |
| Champion/challenger | replace the champion only if the challenger is better by more than the ROPE with P(better) >= 0.95, and no guardrail metric degrades |

## Multiple comparisons

With 10 models vs the best, about one comparison is "significant" at 0.05 by chance.

```python
import numpy as np
def holm(pvals, alpha=0.05):
    order = np.argsort(pvals); m = len(pvals); reject = np.zeros(m, bool)
    for i, idx in enumerate(order):
        if pvals[idx] <= alpha / (m - i):
            reject[idx] = True
        else:
            break
    return reject

def benjamini_hochberg(pvals, q=0.05):
    p = np.asarray(pvals); m = len(p); order = np.argsort(p)
    thresh = q * (np.arange(1, m + 1) / m)
    passed = p[order] <= thresh
    k = np.max(np.where(passed)[0]) + 1 if passed.any() else 0
    reject = np.zeros(m, bool); reject[order[:k]] = True
    return reject
```
`statsmodels.stats.multitest.multipletests(p, method="holm" | "fdr_bh")` does the same.

## Pitfalls

| Pitfall | Consequence | Fix |
|---------|-------------|-----|
| Different folds per model | differences reflect folds | precompute folds once |
| Naive paired t-test on CV folds | false "significant" wins | corrected resampled t-test |
| Wilcoxon with 5 folds | can never be significant | 10 folds or repeated CV |
| Choosing on the test set, reporting the test score | optimistic, winner's curse | choose on CV, confirm on holdout once |
| Unequal tuning budgets | favourite looks better | same budget and search for finalists |
| Comparing tuned best_score_ values | each is an optimistic maximum | nested CV or fresh holdout |
| Ignoring variance across seeds | lucky seed | repeat with several seeds |
| Averaging metrics over folds of different size/prevalence | biased means | pooled out-of-fold predictions as a check |
| Many metrics, picking the one that wins | p-hacking | pre-declare the primary metric |
| Offline win treated as final | action effects, drift ignored | shadow mode / A/B test |

## Champion/challenger in production

1. Offline: challenger better by > ROPE on the latest time window, not only on random CV.
2. Shadow: both score live traffic; compare distributions and agreement.
3. Online: randomised split; primary business metric and guardrails; pre-registered duration and sample size.
4. Promote, keep the champion as fallback for a while, monitor.
