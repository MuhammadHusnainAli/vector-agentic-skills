---
name: overfitting-underfitting-diagnoser
description: "Diagnose overfitting and underfitting from the evidence a model leaves behind: training histories (metric per boosting round or epoch from LightGBM, XGBoost, CatBoost, Keras or PyTorch) and validation curves (train and validation score across one hyperparameter such as max_depth, C, min_samples_leaf or alpha). Finds the best iteration on a smoothed curve, the overfitting onset, degradation and noise, and suggests early-stopping patience; flags under-training, plateaus, divergence and models that are not learning. For validation curves it labels underfit, sweet-spot and overfit zones, applies the one-standard-error rule to pick the simplest adequate value, infers complexity direction, and warns when the best value sits at the edge of the sweep. Includes the fix for each diagnosis per model family. Use when someone asks whether a model overfits or underfits, why validation loss rises, how many rounds or epochs to train, or how to read a train/validation gap."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Overfitting / Underfitting Diagnoser

"Is it overfitting?" deserves a measured answer, not a guess from one train/test pair. Two curves answer it:
the **training history** (score per boosting round or epoch) shows *when* the model starts memorising, and the
**validation curve** (score across one hyperparameter) shows *how much* flexibility the data supports.
`scripts/training_history.py` reads the first and `scripts/validation_curve_report.py` the second. Both return
a verdict and the concrete setting to change.

## Trigger Conditions

Activate this skill when the user:
- Asks whether a model overfits or underfits, or why training is much better than validation
- Shows a loss curve where validation rises, flattens or never improves
- Needs the number of boosting rounds / epochs, or an early-stopping patience
- Sweeps a hyperparameter (max_depth, C, alpha, min_samples_leaf, k) and asks which value to use
- Sees a model that was great in development and worse in production (also check leakage and drift)

Curves over training-set size: [learning-curve-diagnoser](../learning-curve-diagnoser/SKILL.md). Multi-parameter
search results: [hyperparameter-search-planner](../hyperparameter-search-planner/SKILL.md). Too-good scores:
[target-leakage-detector](../target-leakage-detector/SKILL.md).

## Workflow

```
1. EVIDENCE   -> export the history (evals_result_, history.history) and/or a validation curve with fold scores
2. HISTORY    -> python scripts/training_history.py history.csv
3. SWEEP      -> python scripts/validation_curve_report.py validation_curve.csv --current <value in use>
4. CROSS-CHECK-> gap size vs fold noise; same splitter as model selection; leakage if validation is too good
5. FIX        -> one change from the tables below; re-run the same curve
6. REPORT     -> verdict, the numbers behind it, the change, the before/after curve
```

## Diagnosis Table

| Evidence | Diagnosis | Typical fix |
|----------|-----------|-------------|
| Validation loss bottoms out, then rises while training keeps falling | **OVERFITTING** (after the best iteration) | early stopping at the best round; regularise if the gap is already large there |
| Best validation at the last round | **STILL IMPROVING** (under-trained) | more rounds / epochs, or a higher learning rate |
| Validation flat for the last third | **PLATEAU** | stop earlier; gains need features or capacity |
| Training loss rises | **TRAINING DIVERGES** | lower learning rate; check custom objectives, exploding values |
| Validation never beats its first value | **NOT LEARNING** | data/label bug, wrong metric, learning rate far off |
| Validation curve: score falls as complexity grows past the best value, gap widens | overfit zone | move to the 1-SE pick |
| Validation curve: both train and validation low at low complexity | underfit zone | more flexible setting |
| Best value at the edge of the sweep | range too narrow | extend the sweep beyond that edge |

Thresholds are relative to the curve's own noise (std of the metric around its moving average), not to fixed
numbers. Detail on reading both curves: [reading-the-curves.md](references/reading-the-curves.md).

## Key Rules

- **A gap alone is not overfitting.** Boosted trees and forests always score higher on training rows. Overfitting
  means validation gets *worse* as flexibility grows, or that a simpler setting validates as well.
- **Decide on validation folds, confirm on a holdout.** The best iteration chosen on the validation set is
  optimistic for that set.
- **Smooth before picking the best round.** A single lucky round should not decide; the script uses a
  centred moving average (`--smooth`) and sets patience to max(10, 3 x window, 5% of the rounds).
- **Prefer the 1-SE pick.** The least complex value within one standard error of the best generalises at
  least as well and is cheaper.
- **Know which direction is "more complex".** Larger max_depth / num_leaves / C means more flexible; larger
  min_samples_leaf / alpha / reg_lambda / n_neighbors means less flexible. XGBoost `gamma` is a regulariser,
  but SVM `gamma` adds flexibility, so the script infers it from the training-score trend.
- **Check the evaluation before the model.** Leakage, duplicates across folds or a non-grouped split make
  validation too good. A distribution shift makes production worse than validation, and no regulariser
  fixes either.

Fixes per model family and how to confirm them: [remedies.md](references/remedies.md). Exporting histories and
validation curves from each library: [exporting-curves.md](references/exporting-curves.md).

## Output Format

When diagnosing over- or underfitting, deliver:
1. **Evidence** - which curves, metric, splitter, folds.
2. **Verdict** - the diagnosis with best iteration/value, onset, gap and noise (history) or zones, best and
   1-SE pick (validation curve).
3. **Change** - the setting to change (rounds, patience, parameter value) and why.
4. **Confirmation** - the curve after the change and the holdout score against the previous model.

## Scripts

```bash
python scripts/training_history.py history.csv
python scripts/training_history.py history.csv --train-col training_auc --val-col valid_1_auc --smooth 9
python scripts/training_history.py history.csv --json
```
Detects train/validation column pairs (`train_*`/`training_*` with `valid_*`/`val_*`/`eval_*`/`test_*`, including
LightGBM's `valid_1_*`) and the metric direction from its name (override with `--lower-better` /
`--higher-better`). Reports best iteration, smoothed best, degradation, onset, gap at start/best/end, noise,
suggested patience and the verdict. Exit codes: 0 diagnosed, 2 usage or read error.

```bash
python scripts/validation_curve_report.py validation_curve.csv
python scripts/validation_curve_report.py vc.csv --param-col param_C --current 100
python scripts/validation_curve_report.py vc.csv --complexity decreasing --lower-better --json
```
Accepts one row per (value, fold) or per value; numeric parameters are sorted, categorical ones keep file
order. Reports zones, best, 1-SE pick, boundary warnings and, with `--current`, which way to move. Exit codes:
0 reported, 2 usage or read error.

## Additional Resources

| File | Content |
|------|---------|
| [reading-the-curves.md](references/reading-the-curves.md) | history shapes, validation-curve zones, noise and smoothing, the 1-SE rule, misreadings |
| [remedies.md](references/remedies.md) | regularisation and capacity levers per model family, early stopping set-ups, confirmation |
| [exporting-curves.md](references/exporting-curves.md) | getting histories from LightGBM, XGBoost, CatBoost, Keras, PyTorch; validation_curve with fold scores |
