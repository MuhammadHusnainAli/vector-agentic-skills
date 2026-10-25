# Optuna API Guide (Optuna 3.x-5.x)

## Studies

```python
study = optuna.create_study(
    study_name="lgbm_churn", storage="sqlite:///lgbm_churn.db", load_if_exists=True,
    direction="maximize",                     # or directions=[...] for multi-objective
    sampler=optuna.samplers.TPESampler(seed=0, multivariate=True, n_startup_trials=10),
    pruner=optuna.pruners.MedianPruner(n_startup_trials=10, n_warmup_steps=1))
study.optimize(objective, n_trials=200, timeout=None, n_jobs=1, callbacks=[...], gc_after_trial=True,
               catch=())                      # exceptions listed in catch mark the trial FAIL and continue
study.best_value, study.best_params, study.best_trial.user_attrs
df = study.trials_dataframe()                 # columns: number, value, params_*, user_attrs_*, state, duration
```
`optuna.load_study(study_name=..., storage=...)` reopens a stored study.

## Suggest API

| Call | Use |
|------|-----|
| `trial.suggest_float(name, low, high, log=False, step=None)` | continuous; `log=True` for multiplicative effects |
| `trial.suggest_int(name, low, high, step=1, log=False)` | integers; `log=True` for sizes |
| `trial.suggest_categorical(name, choices)` | choices must be None/bool/int/float/str |
| deprecated | `suggest_uniform`, `suggest_loguniform`, `suggest_discrete_uniform` -> `suggest_float` |

Suggesting the same name twice with a different distribution in one trial raises `ValueError`.

## Samplers

| Sampler | When |
|---------|------|
| `TPESampler(multivariate=True, group=True)` | default; conditional/categorical spaces |
| `GPSampler` | few continuous parameters, expensive trials |
| `CmaEsSampler` | continuous spaces, many trials |
| `RandomSampler` | baselines, very cheap trials |
| `GridSampler(search_space)` | exhaustive small grids |
| `NSGAIISampler` / `NSGAIIISampler` | multi-objective |
| `QMCSampler` | quasi-random space-filling |

## Pruners

| Pruner | Behaviour |
|--------|-----------|
| `MedianPruner(n_startup_trials, n_warmup_steps)` | prune if below the median of previous trials at the same step |
| `PercentilePruner(percentile=25)` | stricter/looser variants |
| `SuccessiveHalvingPruner`, `HyperbandPruner(min_resource, max_resource)` | budget-based brackets |
| `ThresholdPruner(lower=...)` | prune when a value crosses a bound (e.g. diverging loss) |
| `PatientPruner(wrapped, patience)` | tolerate temporary dips |
| `NopPruner()` | none |

Pruning needs `trial.report(value, step)`, `trial.should_prune()` and `raise optuna.TrialPruned()`.
Steps are folds (CV objectives) or boosting rounds / epochs (single-split objectives).

## Storage and parallelism

- SQLite is fine for one machine; use PostgreSQL/MySQL (`storage="postgresql://..."`) for many workers.
- Run the same script in several processes against one storage: they share trials.
- `n_jobs>1` in `optimize` uses threads: helpful only when the objective releases the GIL (most ML libraries do
  in their fit loops), but beware of nested parallelism (`n_jobs=-1` inside models).
- `JournalStorage` (file-based journal) suits NFS/multi-process setups without a database.

## Callbacks

```python
def stop_when_stale(patience):
    def cb(study, trial):
        done = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
        if len(done) > patience and study.best_trial.number < done[-patience].number:
            study.stop()
    return cb
```
Other uses: logging to MLflow/W&B, checkpointing artefacts of the best trial.

## Ask-and-tell

```python
trial = study.ask({"C": optuna.distributions.FloatDistribution(1e-4, 1e2, log=True)})
value = evaluate(trial.params)
study.tell(trial, value)
```
For external evaluation loops or batch evaluation on a cluster.

## Analysis

```python
optuna.importance.get_param_importances(study)                       # fANOVA by default
optuna.visualization.plot_optimization_history(study)                # plotly figures
optuna.visualization.plot_slice(study, params=["num_leaves", "min_child_samples"])
optuna.visualization.plot_contour(study, params=["num_leaves", "min_child_samples"])
```
