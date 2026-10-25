---
name: regression-model-trainer
description: "Train regression models whose loss matches the target: squared error, absolute/Huber for heavy tails, log1p targets with retransformation (smearing) correction, Gamma for positive skewed amounts, Poisson for counts with exposure offsets, Tweedie for zero-inflated losses, two-part hurdle models, logit/cross-entropy for proportions, and quantile (pinball) loss and conformal prediction intervals for percentiles and uncertainty. Covers ridge/lasso/GLMs (PoissonRegressor, GammaRegressor, TweedieRegressor), HistGradientBoosting, LightGBM, XGBoost and CatBoost objectives, monotone constraints, sample weights and exposure, and residual diagnostics: calibration by prediction decile, heteroscedasticity, segment bias, interval coverage and worst errors with CI gates. Use when someone trains a model to predict a quantity (price, demand, revenue, duration, claims, LTV), asks which loss or objective to use, sees under-prediction of large values, needs prediction intervals, or wants to check a regression model's residuals."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Regression Model Trainer

A regression model estimates whatever its loss tells it to: squared error estimates the **mean**, absolute
error the **median**, pinball loss a **quantile**, Poisson/Gamma/Tweedie deviances a mean under a
variance that grows with the level. Picking the loss from the target's shape, and checking residuals for
bias by level and segment, matter more than the algorithm. `scripts/target_diagnostics.py` reads the target
and recommends the loss with the objective names for scikit-learn, LightGBM, XGBoost and CatBoost;
`scripts/residual_report.py` diagnoses predictions (decile calibration, heteroscedasticity, segment bias,
interval coverage) and can gate CI on bias.

## Trigger Conditions

Activate this skill when the user:
- Trains a model to predict a quantity: price, demand, revenue, spend, LTV, duration, claim cost, counts
- Asks which loss/objective to use (MSE vs MAE vs Huber vs Poisson vs Tweedie vs log target)
- Sees large values systematically under-predicted, or errors that grow with the prediction
- Needs prediction intervals or a percentile (P90 demand, upper bound on delivery time)
- Has exposure (policy-years, store-days) or zero-heavy targets
- Wants a residual analysis or a bias gate for a regression model

Choosing the evaluation metric: [ml-success-metric-selector](../ml-success-metric-selector/SKILL.md);
time-ordered targets: [time-series-forecasting-model-builder](../time-series-forecasting-model-builder/SKILL.md);
GBM tuning: [xgboost-lightgbm-tuner](../xgboost-lightgbm-tuner/SKILL.md).

## Workflow

```
1. TARGET     -> python scripts/target_diagnostics.py data.csv --target y [--need-quantile 0.9]
2. BASELINE   -> mean/median and one-feature baselines (ml-baseline-model-builder)
3. LINEAR     -> ridge / GLM with the recommended family (interpretable reference)
4. GBM        -> HistGradientBoosting / LightGBM / XGBoost / CatBoost with the matching objective
5. PREDICT    -> out-of-fold or holdout predictions to a CSV (y_true, y_pred, segment, intervals)
6. DIAGNOSE   -> python scripts/residual_report.py preds.csv --segment region --max-abs-bias-pct 10
7. INTERVALS  -> quantile models or conformal intervals; check coverage on the holdout
8. REPORT     -> metric in business units, bias by decile/segment, coverage
```

## Target Shape -> Loss

| Target | Loss / approach | scikit-learn | LightGBM | XGBoost | CatBoost |
|--------|-----------------|--------------|----------|---------|----------|
| Symmetric, light tails | squared error | `Ridge`, HGB `loss="squared_error"` | `regression` | `reg:squarederror` | `RMSE` |
| Heavy-tailed noise / outliers | Huber or absolute | `HuberRegressor`, HGB `loss="absolute_error"` | `huber`, `regression_l1` | `reg:pseudohubererror`, `reg:absoluteerror` | `Huber:delta=`, `MAE` |
| Positive, right-skewed, ~log-normal | log1p target (+ smearing) | `TransformedTargetRegressor(np.log1p, np.expm1)` | train on log1p | train on log1p | train on log1p |
| Positive, skewed, var ∝ mean² | Gamma deviance | `GammaRegressor`, HGB `loss="gamma"` | `gamma` | `reg:gamma` | `Tweedie:variance_power=1.99` |
| Counts | Poisson deviance (+ exposure) | `PoissonRegressor`, HGB `loss="poisson"` | `poisson` | `count:poisson` | `Poisson` |
| Zeros + positive tail (loss cost, spend) | Tweedie, 1 < p < 2 | `TweedieRegressor(power=1.5)` | `tweedie` + `tweedie_variance_power` | `reg:tweedie` | `Tweedie:variance_power=1.5` |
| Zeros from a separate process | two-part: classifier x positive regressor | two models | two models | two models | two models |
| Proportion in (0, 1) | logit transform or cross-entropy | `TransformedTargetRegressor(logit, expit)` | `cross_entropy` | `reg:logistic` | `CrossEntropy` |
| A percentile is the decision | quantile (pinball) | HGB `loss="quantile", quantile=q` | `quantile`, `alpha=q` | `reg:quantileerror` | `Quantile:alpha=q` |

On the fixtures: house prices -> log1p target (skew 4.6, log-skew 0.39); claim counts -> Poisson
(variance/mean 1.01); claim amounts with 90% zeros -> Tweedie (two-part as the alternative); utilisation in
(0, 1) -> logit. Loss mechanics, smearing and Tweedie power selection: [losses-and-targets.md](references/losses-and-targets.md).

## Model Recipes

```python
import numpy as np
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import PoissonRegressor, TweedieRegressor

# Log target for prices (predicts ~median; multiply by a smearing factor when sums matter)
price_model = TransformedTargetRegressor(
    regressor=make_pipeline(prep, HistGradientBoostingRegressor(max_leaf_nodes=31, learning_rate=0.05)),
    func=np.log1p, inverse_func=np.expm1)

# Claim frequency with exposure: model the rate, weight by exposure
freq = HistGradientBoostingRegressor(loss="poisson")
freq.fit(X, y_counts / exposure, sample_weight=exposure)        # predicts claims per unit exposure

# Pure premium (zeros + amounts)
pp = make_pipeline(prep, TweedieRegressor(power=1.6, link="log", alpha=0.01, max_iter=1000))
```
LightGBM with an exposure **offset** (`init_score=np.log(exposure)`), monotone constraints, sample weights,
and CatBoost/XGBoost equivalents: [model-recipes.md](references/model-recipes.md).

## Reading Residuals

```
Calibration by prediction decile (mean pred / mean true):
  D1:0.95  D2:1.00  D3:1.01  ...  D8:0.84  D9:0.85  D10:0.87
|residual| vs prediction correlation +0.79: errors grow with the level (heteroscedastic)
By segment:  large  n=102  MAE 136.5  bias -134.2 (-14.8%)
Interval coverage 57.3% (nominal 80%)  <- too narrow
```

| Pattern | Cause | Fix |
|---------|-------|-----|
| Top deciles under-predicted, bottom over-predicted | shrinkage / regularisation, squared error on skewed target, missing driver of large values | log target or Gamma/Tweedie; features for large cases; less regularisation |
| |residual| grows with the prediction | multiplicative noise | log target or deviance loss; report WAPE/relative errors |
| One segment biased | missing interaction or segment feature; different population | add the feature/interaction; separate model; sample weights |
| Bias overall after log target | retransformation bias | smearing correction or deviance loss |
| Intervals cover far less than nominal | model too confident; distribution shift | conformal calibration on a holdout; wider quantiles |
| Worst errors are data errors | outliers, unit mistakes | fix data; robust loss |

More diagnostics (partial residual plots, residuals vs time, influence): [residual-diagnostics.md](references/residual-diagnostics.md).

## Prediction Intervals

| Method | How | Notes |
|--------|-----|-------|
| Quantile models | fit q = 0.1 and q = 0.9 models (HGB / LightGBM quantile) | flexible; quantiles can cross; check coverage |
| Split conformal | holdout residuals -> add the (1 − α) quantile of |residual| to point predictions | distribution-free marginal coverage; constant width unless normalised |
| Conformalised quantile regression (CQR) | quantile models + conformal correction | adaptive width with valid coverage |
| GLM / parametric | variance from the family | only if the family is right |

Code for each and coverage checks: [prediction-intervals.md](references/prediction-intervals.md).

## Output Format

When training or reviewing a regression model, deliver:
1. **Target diagnosis** - shape statistics and the chosen loss with the reason (`target_diagnostics.py`).
2. **Models** - baseline, linear/GLM and GBM with the matching objective; exposure/weights if relevant.
3. **Metrics** - MAE/RMSE/WAPE (business units), against baselines, with CV spread.
4. **Residual report** - decile calibration, heteroscedasticity, segment bias, worst rows (`residual_report.py`).
5. **Intervals** - method and holdout coverage, if uncertainty matters.
6. **Fixes** - what the residuals suggest next (features, loss, segmentation).

## Scripts

```bash
python scripts/target_diagnostics.py data.csv --target price
python scripts/target_diagnostics.py data.csv --target claim_amount --json
python scripts/target_diagnostics.py data.csv --target units --need-quantile 0.9
```
Reports quantiles, mean vs median, skew and skew of log, zero and negative shares, integer-ness, tail ratio,
dispersion and outlier share; recommends squared, Huber/absolute, log1p, Gamma, Poisson (zero-inflation check
against the Poisson zero share), Tweedie (two-part alternative when zeros > 50%), logit or quantile, with
scikit-learn / LightGBM / XGBoost / CatBoost objective names, the matching metric and notes (smearing, tails,
negatives). Exit codes: 0 diagnosed, 2 usage error or non-numeric target.

```bash
python scripts/residual_report.py preds.csv
python scripts/residual_report.py preds.csv --segment region --slice-by sqft year_built --top 5
python scripts/residual_report.py preds.csv --lower p10 --upper p90 --nominal 0.8
python scripts/residual_report.py preds.csv --max-abs-bias-pct 10 --json
```
MAE, RMSE, MedAE, bias, R2, WAPE; mean prediction / mean actual per prediction decile; |residual| vs prediction
correlation; MAE and bias per segment and per quartile of slice columns; interval coverage and width; the
largest errors with CSV line numbers; a bias gate. Exit codes: 0 printed (gate passed), 1 gate failed, 2 usage
or read error.

## Additional Resources

| File | Content |
|------|---------|
| [losses-and-targets.md](references/losses-and-targets.md) | What each loss estimates, deviance families, log-target retransformation bias and smearing, Tweedie power choice, hurdle models, proportions |
| [model-recipes.md](references/model-recipes.md) | Ridge/lasso/GLMs, HistGBM, LightGBM, XGBoost, CatBoost code per objective; exposure offsets; weights; monotone constraints; early stopping |
| [residual-diagnostics.md](references/residual-diagnostics.md) | Decile calibration, heteroscedasticity, segment and time slices, partial residuals, influential points, what each pattern means |
| [prediction-intervals.md](references/prediction-intervals.md) | Quantile regression, split conformal, CQR, MAPIE, coverage evaluation, crossing quantiles |
