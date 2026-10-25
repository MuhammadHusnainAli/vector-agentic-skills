# Search Strategies

## Grid search

```python
from sklearn.model_selection import GridSearchCV
grid = GridSearchCV(pipe, {"model__C": [0.01, 0.1, 1, 10], "model__penalty": ["l1", "l2"]},
                    cv=cv, scoring="average_precision", n_jobs=-1)
```
Exhaustive; cost multiplies with every parameter. Good for a handful of discrete choices or a final local
refinement.

## Random search

```python
from scipy.stats import loguniform, randint
from sklearn.model_selection import RandomizedSearchCV
rs = RandomizedSearchCV(pipe, {"model__C": loguniform(1e-4, 1e2)}, n_iter=40, cv=cv, random_state=0, n_jobs=-1)
```
Each trial samples every parameter, so important parameters get many distinct values. 60 trials find a
configuration in the top 5% of the space with 95% probability (if the top 5% region is not tiny).

## Successive halving

```python
from sklearn.experimental import enable_halving_search_cv  # noqa: F401
from sklearn.model_selection import HalvingRandomSearchCV
hs = HalvingRandomSearchCV(pipe, dist, n_candidates=200, factor=3, resource="n_samples",
                           min_resources="exhaust", cv=cv, random_state=0, n_jobs=-1)
```
Starts many candidates on few samples, keeps the best 1/factor each round with factor-times more data.
`resource` can be an estimator parameter (e.g. `model__n_estimators` for forests). Assumes early ranking on small
resources predicts final ranking.

## Hyperband / ASHA

Runs several successive-halving brackets with different starting budgets; ASHA is the asynchronous variant for
many workers. In Optuna: `HyperbandPruner` / `SuccessiveHalvingPruner`; in Ray Tune: `ASHAScheduler`.

## Bayesian optimisation (TPE, Gaussian processes)

```python
import optuna
study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=0, multivariate=True),
                            pruner=optuna.pruners.MedianPruner(n_startup_trials=10, n_warmup_steps=1))
study.optimize(objective, n_trials=100, n_jobs=1)
```
- TPE handles conditional and categorical spaces; `multivariate=True` models parameter interactions.
- GP-based samplers (`GPSampler`) are sample-efficient for small continuous spaces.
- CMA-ES (`CmaEsSampler`) works well for continuous spaces with many trials.
- Startup trials (random) seed the model: 10-20.

## Pruning

Report an intermediate score (after each CV fold, or every N boosting rounds) and let the pruner stop trials
that are below the median of other trials at the same step. Saves 30-70% of compute on GBMs.

## Parallelism

| Approach | Notes |
|----------|-------|
| `n_jobs=-1` on GridSearch/RandomizedSearch | parallel over candidates x folds |
| Optuna with shared storage (RDB) and several processes | each process runs `study.optimize`; TPE sees all trials |
| Ray Tune / Dask | cluster-scale |

Do not parallelise both the search and the estimator (`n_jobs=-1` twice): oversubscription.

## Multi-objective

`optuna.create_study(directions=["maximize", "minimize"])` for accuracy vs latency/size; pick from the Pareto
front (`study.best_trials`).
