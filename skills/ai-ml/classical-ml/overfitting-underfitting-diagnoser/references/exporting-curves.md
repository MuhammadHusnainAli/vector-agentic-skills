# Exporting Curves

All snippets write CSVs that `training_history.py` and `validation_curve_report.py` read directly.

## Training histories

```python
import pandas as pd

# LightGBM (sklearn API): eval_set=[(X_tr, y_tr), (X_va, y_va)] gives "training" and "valid_1"
r = model.evals_result_
pd.DataFrame({f"{ds}_{m}": v for ds, ms in r.items() for m, v in ms.items()}) \
  .rename_axis("iteration").reset_index().assign(iteration=lambda d: d.iteration + 1) \
  .to_csv("history.csv", index=False)            # training_binary_logloss, valid_1_binary_logloss, ...

# XGBoost: eval_set=[(X_tr, y_tr), (X_va, y_va)] gives "validation_0" (train) and "validation_1"
r = model.evals_result()
pd.DataFrame({"train_" + m: r["validation_0"][m] for m in r["validation_0"]} |
             {"valid_" + m: r["validation_1"][m] for m in r["validation_1"]}).to_csv("history.csv", index_label="iteration")

# CatBoost: "learn" and "validation"
r = model.get_evals_result()
pd.DataFrame({"learn_" + m: v for m, v in r["learn"].items()} |
             {"valid_" + m: v for m, v in r["validation"].items()}).to_csv("history.csv", index_label="iteration")

# Keras
pd.DataFrame(history.history).rename(columns=lambda c: c if c.startswith("val_") else "train_" + c) \
  .to_csv("history.csv", index_label="epoch")

# PyTorch: collect per epoch
rows.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss})
pd.DataFrame(rows).to_csv("history.csv", index=False)
```
Note that XGBoost names the training set `validation_0`: rename it as above, or pass `--train-col`/`--val-col`.
With `index_label`, iterations start at 0, which does not matter for the diagnosis.

## Validation curves with fold scores

```python
import numpy as np, pandas as pd
from sklearn.model_selection import StratifiedKFold, validation_curve

values = [1, 2, 3, 4, 6, 8, 10, 14, 20]
tr, va = validation_curve(model, X, y, param_name="max_depth", param_range=values,
                          cv=StratifiedKFold(5, shuffle=True, random_state=0), scoring="roc_auc", n_jobs=-1)
rows = [(v, k, tr[i, k], va[i, k]) for i, v in enumerate(values) for k in range(tr.shape[1])]
pd.DataFrame(rows, columns=["max_depth", "fold", "train_score", "val_score"]).to_csv("validation_curve.csv", index=False)
```
For a pipeline, use the step-prefixed name (`param_name="model__max_depth"`). Use log-spaced values for C, alpha
and learning rates.

From an existing search: `cv_results_` already has `split{k}_test_score` (and `split{k}_train_score` with
`return_train_score=True`). Melt it to one row per (value, fold), keeping the other parameters fixed at one
value. Otherwise the curve mixes several parameters.

```python
cv = pd.DataFrame(search.cv_results_)
k = search.n_splits_
long = pd.concat([pd.DataFrame({"C": cv["param_C"], "fold": f, "train_score": cv[f"split{f}_train_score"],
                                "val_score": cv[f"split{f}_test_score"]}) for f in range(k)])
```
