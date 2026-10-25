# Study Patterns

## CV objective with per-fold pruning

See the anatomy in SKILL.md. Rule: folds are created once at module level; the objective iterates them and reports
the running mean after each fold.

## Single-split objective with per-round pruning (large data)

```python
def objective(trial):
    params = {...}
    dtrain, dvalid = lgb.Dataset(X_tr, y_tr), lgb.Dataset(X_va, y_va)
    def report(env):                                         # LightGBM callback: report every 50 rounds
        if env.iteration % 50 == 0:
            value = env.evaluation_result_list[0][2]
            trial.report(value, env.iteration)
            if trial.should_prune():
                raise optuna.TrialPruned()
    booster = lgb.train({**params, "metric": "auc", "verbose": -1}, dtrain, 5000, valid_sets=[dvalid],
                        callbacks=[lgb.early_stopping(100, verbose=False), report])
    return booster.best_score["valid_0"]["auc"]
```
The `optuna-integration` package provides `LightGBMPruningCallback`, `XGBoostPruningCallback` and
`CatBoostPruningCallback` doing the same.

## Model selection in one study

```python
def objective(trial):
    family = trial.suggest_categorical("family", ["logreg", "lgbm"])
    if family == "logreg":
        model = make_pipeline(prep, LogisticRegression(C=trial.suggest_float("C", 1e-4, 1e2, log=True), max_iter=5000))
    else:
        model = lgb.LGBMClassifier(num_leaves=trial.suggest_int("num_leaves", 7, 127, log=True), verbose=-1)
    return cv_score(model)
```
Prefer separate studies per family when budgets allow; a shared study lets TPE abandon one family early.

## Multi-objective

```python
def objective(trial):
    model = build(trial)
    pr_auc = cv_score(model)
    latency = measure_latency(model)            # ms per 1k rows
    return pr_auc, latency
study = optuna.create_study(directions=["maximize", "minimize"], sampler=optuna.samplers.NSGAIISampler(seed=0))
for t in study.best_trials:                     # Pareto front
    print(t.values, t.params)
```

## Constraints

```python
def constraints(trial):
    return [trial.user_attrs["model_mb"] - 50]   # <= 0 is feasible
sampler = optuna.samplers.TPESampler(seed=0, constraints_func=constraints)
```
Set `trial.set_user_attr("model_mb", size)` in the objective.

## Warm start with known configurations

```python
study.enqueue_trial({"num_leaves": 31, "min_child_samples": 20, "reg_lambda": 1.0})   # library defaults
study.enqueue_trial(previous_best_params)
```

## Handling failures

- Let unexpected errors fail the trial (`catch=(ValueError,)` to continue the study); failed trials are ignored
  by TPE.
- For known-invalid regions (e.g. a configuration that cannot fit), `raise optuna.TrialPruned()`.
- Never return a constant sentinel score.

## Time budgets

`study.optimize(objective, timeout=4 * 3600)` stops starting new trials after the timeout; combine with a stale
callback and a trial cap.

## Refitting the best trial

```python
best = study.best_trial
params = best.params
n_trees = int(best.user_attrs["best_iteration_mean"] * 2 * 1.1)       # learning rate halved for the final fit
final = lgb.LGBMClassifier(**params, learning_rate=0.025, n_estimators=n_trees, verbose=-1).fit(X, y)
```
For non-boosting models, rebuild with `optuna.trial.FixedTrial(best.params)` passed to the same model-building
function used in the objective, which avoids duplicating the space definition.
