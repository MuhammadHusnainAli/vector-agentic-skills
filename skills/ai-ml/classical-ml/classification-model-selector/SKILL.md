---
name: classification-model-selector
description: "Choose the right classification algorithm for tabular, text or mixed data and prove the choice with a fair bake-off: logistic regression (L2, L1, elastic net), linear SVM, naive Bayes, k-NN, RBF SVM, decision trees, random forest, extra trees, HistGradientBoosting, LightGBM, XGBoost, CatBoost, explainable boosting machines (EBM/GAM), points scorecards and MLPs, matched to data size, width, categorical and high-cardinality share, missingness, class imbalance, text, and constraints such as interpretability, monotonic constraints, calibrated probabilities, latency budgets and tiny deployable models. Ranks candidates with starting hyperparameters and cautions, then generates a bake-off script running every candidate on identical CV folds with per-fold metrics, fit time and prediction latency. Use when someone asks which classifier to use, logistic regression vs random forest vs XGBoost, whether deep learning is worth it on tabular data, or wants a model comparison set up."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Classification Model Selector

On tabular data the realistic shortlist is short: a regularised **logistic regression** (fast, explainable,
often surprisingly close), a **gradient-boosted tree** model (LightGBM / XGBoost / CatBoost /
HistGradientBoosting: usually the most accurate), and, when explanations are mandatory, a **glass-box**
model (EBM / GAM or a points scorecard). Data shape and constraints move the ranking: small data favours
simpler models, many categoricals favour CatBoost, text favours linear models on TF-IDF, latency and
regulation constrain everything. `scripts/select_classifier.py` ranks candidates from data traits and
needs; `scripts/bakeoff_scaffold.py` writes a script that runs the shortlist on identical folds and records
per-fold metrics, fit time and prediction latency.

## Trigger Conditions

Activate this skill when the user:
- Asks "which classifier should I use?", "XGBoost or random forest?", "is logistic regression enough?"
- Starts a classification project and needs a shortlist and a fair comparison plan
- Has constraints: regulated decisions, monotonicity, calibrated probabilities, < 5 ms latency, SQL/edge
  deployment, tiny data, very wide data, many high-cardinality categoricals, text fields
- Wonders whether neural networks / deep learning help on tabular data

Regression targets go to [regression-model-trainer](../regression-model-trainer/SKILL.md); tuning the
GBM chosen here to [xgboost-lightgbm-tuner](../xgboost-lightgbm-tuner/SKILL.md) or
[catboost-model-builder](../catboost-model-builder/SKILL.md); statistical comparison of bake-off results to
[ml-model-comparison-reporter](../ml-model-comparison-reporter/SKILL.md); rare positives to
[imbalanced-class-handler](../imbalanced-class-handler/SKILL.md).

## Workflow

```
1. TRAITS     -> python scripts/select_classifier.py --csv data.csv --target y --drop id [--interpretable ...]
2. SHORTLIST  -> top 3-4 + logistic regression baseline (+ the current production model if any)
3. BAKE-OFF   -> python scripts/bakeoff_scaffold.py data.csv --target y --models logreg hgb lgbm catboost -o bakeoff.py
4. RUN        -> python bakeoff.py  -> bakeoff_folds.csv (same folds for every model)
5. COMPARE    -> paired tests on per-fold scores (ml-model-comparison-reporter); weigh fit/predict cost
6. DECIDE     -> simplest model within noise of the best that meets constraints; then tune it
```

## Quick Decision Table

| Situation | First choices | Why |
|-----------|---------------|-----|
| Typical tabular, 10k-10M rows, mixed types | LightGBM / XGBoost / HistGBM, + logistic baseline | GBMs dominate tabular benchmarks |
| Many or high-cardinality categoricals | CatBoost | ordered target statistics, little preprocessing |
| < ~2,000 rows | logistic regression (regularised), random forest, CatBoost, EBM | variance dominates; simple models win often |
| Very wide (p > n), sparse | L1 / elastic-net logistic, linear SVM | regularised linear models scale with width |
| Text fields | TF-IDF + logistic regression / linear SVM; embeddings + GBM | sparse linear models are strong text baselines |
| Regulated / must explain exactly | EBM, scorecard, monotone GBM with reason codes, logistic | glass-box or constrained models |
| Monotonic business logic (price up -> risk up) | GBM with monotone constraints, EBM, scorecard | constraint enforced by construction |
| Calibrated probabilities consumed downstream | logistic, GBM + calibration check | forests and SVMs need calibration |
| < 1 ms latency or SQL/edge deployment | logistic, shallow tree, small GBM compiled (treelite/ONNX) | model size and depth matter |
| Images, audio, raw text sequences | not classical ML | deep learning |

The bake-off on the 400-row churn fixture illustrates the small-data row: regularised logistic regression
(ROC-AUC 0.80, PR-AUC 0.62) beat every default GBM (0.73-0.76) on identical folds.

## Algorithm Profiles

| Model | Strengths | Weaknesses | Needs |
|-------|-----------|------------|-------|
| Logistic regression | fast, stable, interpretable, good probabilities | linear in features; needs interactions/splines | scaling, one-hot, regularisation (C) |
| Linear SVM | wide sparse data, text | no probabilities without calibration | scaling |
| Naive Bayes | tiny data, text, instant training | strong independence assumption; overconfident | counts / TF-IDF |
| k-NN | no training; local patterns | slow inference, curse of dimensionality | scaling, small p |
| RBF SVM | small dense data | O(n²) training, tuning C/gamma | scaling |
| Decision tree | readable rules | unstable, weak alone | depth / leaf limits |
| Random forest | robust, little tuning | big, poorly calibrated, slower inference | few params |
| Extra trees | fast, noise-tolerant | same as RF | few params |
| HistGradientBoosting | strong, native NaN/categoricals, in scikit-learn | < 256 categories per feature | early stopping |
| LightGBM | fastest at scale, native categoricals | overfits small data with defaults | `min_child_samples`, early stopping |
| XGBoost | robust, rich regularisation, GPU | categorical support needs category dtype | early stopping |
| CatBoost | best with categoricals, good defaults | slower training | `cat_features` |
| EBM (InterpretML) | glass-box GAM with interactions, near-GBM accuracy | slower training, large data takes time | little tuning |
| MLP / tabular DL | very large data, embeddings, multimodal | rarely beats GBMs on tabular; tuning-heavy | scaling, early stopping |

Detail per algorithm (key hyperparameters, defaults that matter, failure modes):
[algorithm-profiles.md](references/algorithm-profiles.md).

## Running a Fair Bake-Off

Rules the generated script enforces:
1. **Identical folds** for every model (stratified, grouped by entity, or time-ordered).
2. **Each model gets the preprocessing its family needs**, all fitted inside the fold.
3. **Same metrics** (ROC-AUC, PR-AUC, log loss, Brier) and **cost columns** (fit seconds, prediction ms per
   1k rows).
4. **Untuned defaults first**: a heavily tuned favourite against untuned rivals is not a comparison; tune
   the top 2 afterwards with the same budget.
5. **Per-fold results saved** (`bakeoff_folds.csv`) for paired statistical comparison: fold-to-fold variance
   is often larger than the gap between models.

Design details (time-based bake-offs, nested tuning, budgets, reporting): [bakeoff-design.md](references/bakeoff-design.md).

## Choosing Among Close Models

When two models are within noise on the primary metric, prefer, in order:
1. the one that satisfies the hard constraints (explainability, monotonicity, latency, deployment target);
2. the simpler / cheaper one (fewer features, faster, smaller);
3. the better-calibrated one if probabilities are consumed;
4. the more stable one (lower fold-to-fold std, stable over time periods).

Interpretability and constraint options in depth: [interpretable-and-constrained-models.md](references/interpretable-and-constrained-models.md).

## Output Format

When recommending a classifier, answer with:
1. **Data traits** - rows, features, categorical/high-cardinality share, missingness, imbalance, text.
2. **Constraints** - explainability, monotonicity, calibration, latency, deployment.
3. **Ranked shortlist** - 3-4 models with why, starting configuration and cautions (`select_classifier.py`).
4. **Bake-off plan** - folds, metrics, the generated script, budget for tuning the top two.
5. **Decision rule** - "simplest model within one standard error of the best that meets constraints".

## Scripts

```bash
python scripts/select_classifier.py --csv data.csv --target churned --drop customer_id
python scripts/select_classifier.py --rows 2000000 --features 300 --cat-share 0.4 --hc-share 0.1 --minority 0.002 --latency-ms 5
python scripts/select_classifier.py --csv data.csv --target y --interpretable --monotone --calibrated --json
```
Derives rows, features, categorical and high-cardinality share, missing share, minority share and text columns
from a CSV (or takes them as flags), applies needs (`--interpretable`, `--monotone`, `--calibrated`,
`--latency-ms`, `--tiny-model`) and ranks up to 16 algorithms with a reason, a starting configuration and
cautions. Exit codes: 0 printed, 2 usage or read error.

```bash
python scripts/bakeoff_scaffold.py data.csv --target churned --models logreg hgb rf lgbm xgb catboost ebm -o bakeoff.py
python scripts/bakeoff_scaffold.py data.csv --target churned --group-col customer_id
python scripts/bakeoff_scaffold.py data.csv --target churned --time-col signup_date --folds 5
```
Writes a script that runs each chosen model (logreg, hgb, rf, et, lgbm, xgb, catboost, ebm; optional libraries
skipped if missing) on identical StratifiedKFold / StratifiedGroupKFold / TimeSeriesSplit folds with
family-appropriate preprocessing, and saves per-fold ROC-AUC, PR-AUC, log loss, Brier, fit seconds and
prediction ms per 1k rows to `bakeoff_folds.csv`. Verified with scikit-learn 1.9, LightGBM 4.7, XGBoost 3.4,
CatBoost 1.2 and interpret 0.7. Exit codes: 0 written, 2 usage error.

## Additional Resources

| File | Content |
|------|---------|
| [algorithm-profiles.md](references/algorithm-profiles.md) | Each classifier: how it works in two lines, key hyperparameters, good defaults, data needs, failure modes |
| [bakeoff-design.md](references/bakeoff-design.md) | Fair comparison protocol, folds, tuning budgets, time-based bake-offs, cost metrics, reporting template |
| [interpretable-and-constrained-models.md](references/interpretable-and-constrained-models.md) | EBM/GAMs, scorecards, monotone constraints in LightGBM/XGBoost/HistGBM/CatBoost, reason codes, regulation |
| [tabular-deep-learning.md](references/tabular-deep-learning.md) | When neural nets help on tabular data, what to try (MLP, FT-Transformer, TabPFN-style models), and why GBMs usually win |
