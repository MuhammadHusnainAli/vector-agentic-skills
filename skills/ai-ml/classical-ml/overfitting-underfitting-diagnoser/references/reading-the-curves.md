# Reading the Curves

## Training history shapes (validation loss, lower is better)

```
OVERFITTING              STILL IMPROVING          PLATEAU                  NOT LEARNING
loss                     loss                     loss                     loss
|\                       |\                       |\                       |~~~~~~~~~~~~~~ val
| \       ___/ val       | \                      | \___________ val       |
|  \_____/               |  \___                  |                        |\
|   \_____               |   \____ val            |  \__________ train     | \_________ train
|         \______ train  |     \____ train        |                        |
+------------------ it   +------------------ it   +------------------ it   +------------------ it
```

| Quantity | Definition in training_history.py | Use |
|----------|-----------------------------------|-----|
| smoothed curve | centred moving average, window `--smooth` (default 5, at most n/5) | pick the best round robustly |
| noise | std of the raw values around the smoothed curve | the tolerance for "worse" and "flat" (2 x noise) |
| best iteration | argmin of the smoothed validation curve | number of rounds / epochs to keep |
| onset | first iteration after the best from which the smoothed curve stays worse than best + 2 x noise | when overfitting starts |
| degradation | final - best (raw) | cost of not stopping early |
| gap at best | validation - training at the best iteration | variance remaining at the chosen point |
| suggested patience | max(10, 3 x window, 5% of the iterations) | early-stopping rounds |

Rules of thumb:
- With **AUC or accuracy** as the validation metric, overfitting often shows as a plateau while log loss
  already rises: probabilities get overconfident before rankings degrade. Look at log loss if calibration matters.
- A **gap that widens while validation is flat** means wasted rounds, not yet harm. Stop for cost reasons.
- **Noisy validation** (small validation set) makes early stopping fire early by chance: larger patience,
  or early-stop on a bigger fold.
- **Learning-rate schedules and warm restarts** create bumps; smooth with a larger window.

## Validation-curve zones

```
score
|            ___ train ____________________
|        ___/
|     __/   .-''-.  val
|   _/  .-''      ''-.
|  / .-'               '-._
| /.'                       '-.
+----------------------------------------- complexity
  underfit | sweet spot |     overfit
```

| Zone | Rule in validation_curve_report.py |
|------|------------------------------------|
| sweet spot | mean validation >= best - 1 SE (SE = fold std / sqrt(folds) at the best value) |
| underfit | less complex than the best and outside 1 SE |
| overfit | more complex than the best, outside 1 SE, gap larger than at the best |
| worse | more complex and outside 1 SE but with no larger gap (noise or instability) |

**The 1-SE rule** (Breiman et al., CART): among values within one standard error of the best, choose the least
complex. The score difference is not distinguishable from noise, and the simpler model is cheaper and usually
more stable on new data.

## Misreadings

| Misreading | Correct reading |
|------------|-----------------|
| "Train 0.99, test 0.85: overfitting" | maybe; only a curve shows whether a simpler setting validates better |
| "Validation rises at the end: overfitting" (for AUC) | higher is better for AUC: that is still improving |
| "Best at round 5000 of 5000: perfect" | under-trained: the optimum lies beyond the budget |
| "One bad round after the best: stop" | noise; judge the smoothed curve |
| "Regularise until the gap closes" | a closed gap with a low score is underfitting; aim for the best validation, not the smallest gap |
| "Validation curve flat: parameter tuned" | flat means the parameter barely matters in this range; spend effort elsewhere |
| Using the test set to pick the round | the test score is then biased; pick on validation, report on test |
