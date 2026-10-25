# Optuna Search for GBMs

A compact, CV-based objective with pruning. For a full study script with storage, resumption and reporting,
use optuna-study-writer.

```python
import lightgbm as lgb
import numpy as np
import optuna
from sklearn.metrics import average_precision_score
from sklearn.model_selection import StratifiedKFold

FOLDS = list(StratifiedKFold(5, shuffle=True, random_state=0).split(X, y))   # same folds for every trial


def objective(trial):
    params = {
        "objective": "binary", "learning_rate": 0.05, "n_estimators": 5000, "verbose": -1, "random_state": 0,
        "num_leaves": trial.suggest_int("num_leaves", 7, 127, log=True),
        "min_child_samples": trial.suggest_int("min_child_samples", 5, 300, log=True),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0), "subsample_freq": 1,
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.3, 1.0),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 30.0, log=True),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
    }
    scores, iters = [], []
    for k, (tr, va) in enumerate(FOLDS):
        m = lgb.LGBMClassifier(**params)
        m.fit(X.iloc[tr], y.iloc[tr], eval_set=[(X.iloc[va], y.iloc[va])], eval_metric="average_precision",
              callbacks=[lgb.early_stopping(100, verbose=False)])
        scores.append(average_precision_score(y.iloc[va], m.predict_proba(X.iloc[va])[:, 1]))
        iters.append(m.best_iteration_)
        trial.report(float(np.mean(scores)), step=k)          # pruning after each fold
        if trial.should_prune():
            raise optuna.TrialPruned()
    trial.set_user_attr("best_iteration_mean", float(np.mean(iters)))
    return float(np.mean(scores))


study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=0),
                            pruner=optuna.pruners.MedianPruner(n_startup_trials=10, n_warmup_steps=1))
study.optimize(objective, n_trials=80, show_progress_bar=False)
print(study.best_value, study.best_params, study.best_trial.user_attrs)
print(optuna.importance.get_param_importances(study))     # which knobs mattered
```

Final model:
```python
best = {**study.best_params, "objective": "binary", "subsample_freq": 1, "verbose": -1, "random_state": 0}
n_trees = int(study.best_trial.user_attrs["best_iteration_mean"] * 2 * 1.1)    # learning rate halved below
final = lgb.LGBMClassifier(**best, learning_rate=0.025, n_estimators=n_trees).fit(X, y)
```

Notes:
- Fixed folds across trials make trials comparable and pruning meaningful.
- The study's best value is optimistic (max over trials); confirm on a holdout.
- `optuna.integration.LightGBMTunerCV` (optuna-integration package) is a stepwise tuner for LightGBM.
