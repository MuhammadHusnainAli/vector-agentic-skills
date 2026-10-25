# Deploying CatBoost Models

## Save and load

```python
model.save_model("model.cbm")                                   # native binary (fastest to load)
model.save_model("model.json", format="json")                   # inspectable
model.save_model("model.onnx", format="onnx", export_parameters={"onnx_domain": "ai.catboost"})
model.save_model("model.mlmodel", format="coreml")              # Apple
model.save_model("model.cpp", format="cpp")                     # standalone C++ code
model.save_model("model.py", format="python")                   # standalone Python code

from catboost import CatBoostClassifier
m = CatBoostClassifier().load_model("model.cbm")
```
ONNX export does **not** support categorical features (CatBoost 1.2 raises "ONNX-ML format export does yet
not support categorical features"); models with `cat_features` should be served natively (`.cbm`), through the
C/C++ evaluation library, or exported as `cpp` / `python` / `json`. For any export, verify predictions match the
native model on a sample before switching.

## What to store with the model

- Feature column order and dtypes.
- The categorical and text feature lists, and the casting rules (`astype(str)`, NaN token).
- Training data snapshot / hash, CatBoost version, parameters, best iteration.

## Fast inference

- Symmetric trees evaluate very fast; batch predictions (`predict_proba` on arrays of rows).
- `model.set_scale_and_bias` / `get_scale_and_bias` for calibration-style adjustments.
- For low-latency services keep one loaded model per process; set `thread_count` to the cores per worker.
- `catboost` C/C++ evaluation library (`libcatboostmodel`) for non-Python services.

## Serving checklist

- [ ] Input validation: columns present, cat values strings, NaN handled exactly as in training.
- [ ] Unseen categories are fine (CatBoost uses the prior); monitor their rate.
- [ ] Version pinned; prediction parity test between training and serving environments.
- [ ] Monitoring: score distribution, top-feature drift, unseen-category rate.
