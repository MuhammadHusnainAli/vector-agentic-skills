# Regression Model Recipes

`prep` is a ColumnTransformer (scaled numerics + one-hot for linear models; ordinal/native categoricals for
trees). See scikit-learn-pipeline-builder.

## Linear and GLMs (scikit-learn)

```python
from sklearn.linear_model import RidgeCV, LassoCV, ElasticNetCV, HuberRegressor, PoissonRegressor, GammaRegressor, TweedieRegressor
from sklearn.pipeline import make_pipeline
import numpy as np

ridge = make_pipeline(prep, RidgeCV(alphas=np.logspace(-3, 3, 25)))
huber = make_pipeline(prep, HuberRegressor(epsilon=1.35, alpha=1e-4, max_iter=1000))
poisson = make_pipeline(prep, PoissonRegressor(alpha=1e-3, max_iter=1000))
gamma = make_pipeline(prep, GammaRegressor(alpha=1e-3, max_iter=1000))
tweedie = make_pipeline(prep, TweedieRegressor(power=1.6, link="log", alpha=1e-3, max_iter=1000))
```
GLM coefficients with a log link are multiplicative effects: `exp(coef)` per unit (per SD when scaled).

## HistGradientBoosting

```python
from sklearn.ensemble import HistGradientBoostingRegressor
hgb = HistGradientBoostingRegressor(loss="squared_error",   # "absolute_error", "gamma", "poisson", "quantile"
                                    learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=40,
                                    l2_regularization=1.0, early_stopping=True, validation_fraction=0.15,
                                    monotonic_cst=None, random_state=0)
```
No Tweedie loss in HistGradientBoosting: use LightGBM/XGBoost/CatBoost, or `TweedieRegressor`.

## LightGBM

```python
import lightgbm as lgb
reg = lgb.LGBMRegressor(objective="tweedie", tweedie_variance_power=1.5, n_estimators=5000, learning_rate=0.03,
                        num_leaves=31, min_child_samples=50, subsample=0.8, subsample_freq=1,
                        colsample_bytree=0.8, reg_lambda=1.0, random_state=0, verbose=-1)
reg.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], eval_metric="tweedie",
        callbacks=[lgb.early_stopping(200), lgb.log_evaluation(0)])

# Exposure offset for Poisson/Tweedie: the model learns the rate.
# With init_score LightGBM does not boost from the average (it starts at raw score 0 = rate 1), so put the
# base rate into the offset too; otherwise early stopping can halt while predictions are still biased.
base = y_tr.sum() / exposure_tr.sum()
reg_off = lgb.LGBMRegressor(objective="poisson", n_estimators=3000, learning_rate=0.03, verbose=-1)
reg_off.fit(X_tr, y_tr, init_score=np.log(exposure_tr) + np.log(base),
            eval_set=[(X_va, y_va)], eval_init_score=[np.log(exposure_va) + np.log(base)],
            callbacks=[lgb.early_stopping(200)])
rate = reg_off.predict(X_new) * base               # predict() excludes init_score: add the base rate back
expected = rate * exposure_new                     # counts for the new rows' exposure
```
Measured on the claims fixture: offset with the base rate -> mean predicted rate 0.164 vs actual 0.166;
offset without it -> 0.226 after early stopping. LightGBM >= 4.7 deprecates `eval_set` in the scikit-learn
API in favour of `eval_X=` / `eval_y=`; `eval_set` still works with a warning.
Other objectives: `regression`, `regression_l1`, `huber` (`alpha` = δ), `fair`, `quantile` (`alpha` = q),
`mape`, `gamma`, `poisson`, `cross_entropy`.

## XGBoost

```python
import xgboost as xgb
reg = xgb.XGBRegressor(objective="reg:gamma", n_estimators=5000, learning_rate=0.03, max_depth=6,
                       min_child_weight=5, subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0,
                       tree_method="hist", early_stopping_rounds=200, random_state=0)
reg.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)
# offsets: reg.fit(X, y, base_margin=np.log(exposure)); prediction needs base_margin too
```
Quantile: `objective="reg:quantileerror", quantile_alpha=[0.1, 0.5, 0.9]` (multi-quantile in one model).

## CatBoost

```python
from catboost import CatBoostRegressor
reg = CatBoostRegressor(loss_function="Tweedie:variance_power=1.5", iterations=5000, learning_rate=0.05,
                        depth=6, l2_leaf_reg=3, od_type="Iter", od_wait=200, random_seed=0, verbose=0,
                        cat_features=cat_cols)
reg.fit(X_tr, y_tr, eval_set=(X_va, y_va), use_best_model=True)
```
`baseline=` in `Pool` carries an offset.

## Monotone constraints

```python
HistGradientBoostingRegressor(monotonic_cst={"sqft": 1, "age": -1})            # dict by name (sklearn >= 1.2)
lgb.LGBMRegressor(monotone_constraints=[1, -1, 0, ...])                        # one per feature, in column order
xgb.XGBRegressor(monotone_constraints={"sqft": 1, "age": -1})
```

## Sample weights

Use weights for exposure (rates), for reflecting the population when rows were sampled unevenly, or for
business importance (revenue-weighted error). Pass them to `fit` and to the evaluation metric.

## Ensembles

Averaging a GLM and a GBM, or GBMs with different objectives, often improves calibration across deciles.
Stack with out-of-fold predictions (`StackingRegressor(cv=5)`) when the gain justifies the complexity.
