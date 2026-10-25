# Persistence and Serving

## joblib bundle

```python
import json, platform
import joblib, sklearn

bundle = {
    "model": fitted_pipe,
    "columns": list(X_train.columns),
    "dtypes": {c: str(t) for c, t in X_train.dtypes.items()},
    "target": "churned",
    "positive_class": 1,
    "threshold": 0.31,
    "versions": {"sklearn": sklearn.__version__, "python": platform.python_version()},
    "trained_on": "2026-10-24", "data_snapshot": "s3://bucket/train/2026-10-24/",
}
joblib.dump(bundle, "churn_model.joblib", compress=3)
```

Loading:
```python
bundle = joblib.load("churn_model.joblib")            # only trusted files: pickle executes code
X = incoming.reindex(columns=bundle["columns"])        # missing columns -> NaN; extra columns dropped
p = bundle["model"].predict_proba(X)[:, 1]
flag = p >= bundle["threshold"]
```

## Version compatibility

- Pickled scikit-learn objects are only guaranteed to load in the **same** scikit-learn version. Pin it in
  the serving image; re-train or re-export on upgrades.
- scikit-learn warns (`InconsistentVersionWarning`) when loading across versions: treat it as an error in CI.

## Safer formats

| Format | Notes |
|--------|-------|
| `skops.io` | `skops.io.dump(model, "m.skops")`; `load(..., trusted=[...])` refuses unknown types; no arbitrary code |
| ONNX (`skl2onnx`) | language-independent runtime (onnxruntime); not every transformer is supported; verify parity |
| PMML (`sklearn2pmml`) | JVM scoring engines; limited coverage |

Always compare predictions of the exported model against the original on a sample (max abs difference).

## Input contract and validation

At the serving boundary validate before predicting:
- required columns present, types coercible, value ranges sane;
- categorical values outside training levels are allowed (encoders handle unknowns) but counted for monitoring;
- reject or flag rows with too many missing features.

pydantic or pandera schemas work well for this; log validation failures.

## Batch vs online

| Mode | Notes |
|------|-------|
| Batch | load once, `predict_proba` on chunks of 10k-100k rows; write scores with model version |
| Online (FastAPI etc.) | load at startup, not per request; one-row DataFrame with the exact columns; consider ONNX for latency |
| Streaming | micro-batches; same feature code as training (feature store) |

## Reproducibility checklist

- [ ] Fixed `random_state` everywhere.
- [ ] Training data snapshot path or hash stored with the model.
- [ ] Code version (git SHA) stored with the model.
- [ ] Library versions pinned and stored.
- [ ] Prediction parity test between training environment and serving environment.
