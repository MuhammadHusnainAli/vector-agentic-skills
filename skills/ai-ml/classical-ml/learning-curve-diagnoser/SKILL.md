---
name: learning-curve-diagnoser
description: "Build and read learning curves (training and validation score versus training-set size) to decide whether a model is data-limited, variance-limited or bias-limited, and therefore whether to collect more data, regularise, add capacity or engineer features. Generates scikit-learn learning_curve scripts with geometric size spacing, seeded shuffling, stratified/grouped/time-ordered splitters, fit times and a plot with std bands, then diagnoses the result: the gap at the largest size, validation gain per doubling, an inverse power-law fit capped at the training score with 2x/4x/10x predictions and the rows needed for a target score, plus warnings for noisy curves, memorisation, and validation that drops as data grows. Use when someone asks whether more data will help, how much data is needed, why validation lags training, or how to read a learning curve plot."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Learning Curve Diagnoser

"Should we label more data?" and "should we use a bigger model?" are both answered by the same plot: training
and validation score as the training set grows. The **gap** between the curves measures variance, the
**slope** of the validation curve says whether rows still help, and the **training curve** is the ceiling the
validation curve converges towards. `scripts/gen_learning_curve.py` writes a correct scikit-learn
`learning_curve` script; `scripts/diagnose_curve.py` turns its CSV into a verdict, a data-size extrapolation
and the right next step.

## Trigger Conditions

Activate this skill when the user:
- Asks whether more data, more labels or a longer history will improve the model, or how much data is needed
- Sees a large train/validation gap, or training and validation scores that are both mediocre
- Shares a learning-curve plot or `learning_curve` output and asks what it means
- Must choose between collecting data, regularising, adding capacity or engineering features

Curves over a hyperparameter or over boosting iterations (validation curves, training history):
[overfitting-underfitting-diagnoser](../overfitting-underfitting-diagnoser/SKILL.md). Splitter choice:
[cross-validation-strategy-designer](../cross-validation-strategy-designer/SKILL.md).

## Workflow

```
1. GENERATE  -> python scripts/gen_learning_curve.py data.csv --target y --model hgb --scoring roc_auc -o lc.py
2. RUN       -> python lc.py             (learning_curve.csv + learning_curve.png)
3. DIAGNOSE  -> python scripts/diagnose_curve.py learning_curve.csv --target 0.90
4. ACT       -> the verdict table below; re-run the curve after the change
5. REPORT    -> plot, verdict, extrapolation with its caveats, chosen action
```

## Reading the Curve

| Pattern | Verdict | Action |
|---------|---------|--------|
| Large gap, validation still rising | **HIGH VARIANCE - DATA-LIMITED** | more data pays; regularise meanwhile |
| Large gap, validation flat | **HIGH VARIANCE** | regularise, simplify, remove noisy features; more data of the same kind adds little |
| Gap closed, score too low | **HIGH BIAS** | more capacity, better features, less regularisation; more data will not help |
| Gap closed, score meets the target | **CONVERGED** | stop; spend effort elsewhere |
| Validation drops as size grows | data problem | subsets not random (sorted data, `shuffle=False`), drift, or label noise in later rows |
| Validation above training | regulariser artefact | heavy dropout/augmentation, tiny folds, or a bug (swapped columns) |
| Training score 1.0 everywhere | memorisation | the gap is real, but the training curve cannot show the ceiling |

The key fact: as rows are added the training score falls and the validation score rises towards the **same
asymptote**. Once the gap has closed, the training score is the best the model can reach, so the only way up
is a better model or better features. Worked readings and shapes: [reading-learning-curves.md](references/reading-learning-curves.md).

## Building a Trustworthy Curve

- **Geometric sizes** (e.g. 10%, 16%, 25%, 40%, 63%, 100% of the training fold): the curve bends at small n.
- **Shuffle with a seed**: `learning_curve` takes the first rows of each training fold; on sorted data the small
  sizes are a biased slice. Time-ordered data is the exception: keep the order and use `TimeSeriesSplit`.
- **Same splitter as model selection**: grouped data needs `GroupKFold`, otherwise the curve is optimistic.
- **Enough folds**: compare the standard error of the validation mean with the gain from doubling; if the
  noise is larger, use more folds or `RepeatedStratifiedKFold`.
- **Fixed model settings**: early stopping or tuning at each size changes two things at once. Keep the model
  fixed, or tune at each size deliberately and say so.
- **Fit time** comes for free (`return_times=True`): it shows what doubling the data costs.

## Extrapolating "How Much Data?"

`diagnose_curve.py` fits `val(n) = a - b * n^-c` to the largest four sizes, with the asymptote `a` capped at
the final training score, and reports predictions at 2x, 4x and 10x plus the rows needed for `--target`.

| Rule | Why |
|------|-----|
| Trust 2x, treat 4x as a guess, 10x as a direction | power laws flatten in ways four points cannot show |
| Cap the asymptote at the training score | validation cannot overtake training on the same distribution |
| Target above the cap means "not with this model" | more data alone cannot get there |
| New data must match the old | extrapolation assumes the same distribution and label quality |
| Check R^2 >= 0.9 of the fit | otherwise the gain from doubling falls back to the measured slope, capped by the headroom |

Method, cost-benefit of labelling and alternatives (active learning, augmentation, transfer):
[data-size-extrapolation.md](references/data-size-extrapolation.md). Concrete fixes per verdict and
model family: [acting-on-the-diagnosis.md](references/acting-on-the-diagnosis.md).

## Output Format

When diagnosing a learning curve, deliver:
1. **Setup** - model, metric, splitter, sizes, folds.
2. **Curve table and plot** - mean train/validation, fold std and gap at each size.
3. **Verdict** - variance, data-limited, bias or converged, with the numbers that decide it.
4. **Extrapolation** - predicted score at 2x/4x data, rows for the target, ceiling, and the fit quality.
5. **Action** - the next experiment, and what curve would confirm it worked.

## Scripts

```bash
python scripts/gen_learning_curve.py data.csv --target churned --model hgb --scoring roc_auc -o lc.py
python scripts/gen_learning_curve.py data.csv --target price --model rf --scoring neg_root_mean_squared_error
python scripts/gen_learning_curve.py data.csv --target churned --group-col customer_id --sizes 8 --min-frac 0.05
```
Models: logreg (Ridge for regression), rf, hgb, lgbm. Detects classification vs regression (override with
`--task`), switches binary scorers to their multiclass forms, drops `--group-col`/`--time-col` from the features,
and keeps time order (`shuffle=False`, `TimeSeriesSplit`) with `--time-col`. The generated script writes
`learning_curve.csv` (train_size, fold, train_score, val_score, fit_time) in scorer sign convention and
`learning_curve.png`. Exit codes: 0 written, 2 usage error.

```bash
python scripts/diagnose_curve.py learning_curve.csv
python scripts/diagnose_curve.py lc.csv --target 0.95
python scripts/diagnose_curve.py lc.csv --lower-better --gap-threshold 500 --json
```
Reads any CSV with size, train and validation columns (`--size-col`, `--train-col`, `--val-col`), one row per
fold or per size. The gap threshold defaults to 2% of max(1, |score|). Exit codes: 0 diagnosed, 2 usage or
read error.

## Additional Resources

| File | Content |
|------|---------|
| [reading-learning-curves.md](references/reading-learning-curves.md) | the bias-variance reading, canonical shapes, metric conventions, common misreadings |
| [data-size-extrapolation.md](references/data-size-extrapolation.md) | power-law fitting, how far to trust it, labelling cost-benefit, alternatives to more data |
| [acting-on-the-diagnosis.md](references/acting-on-the-diagnosis.md) | fixes for variance and bias per model family, and the curve that confirms each fix |
