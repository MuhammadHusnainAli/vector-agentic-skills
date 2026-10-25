---
name: target-leakage-detector
description: "Find and fix target leakage, the reason models score 0.99 offline and fail in production: features written after the prediction time (status, cancellation reason, refunds, chargebacks, closed dates), missingness patterns filled by the outcome, future timestamps, aggregates over all history, identifiers or row order that encode the label, target-derived columns, in-sample target encoding, and pipeline leaks in code (scaler/imputer/encoder/selector fitted before the split, SMOTE before the split, fitting on test data, early stopping on the test set, groupby target means, shuffled splits on temporal data). Scans a training table with out-of-fold single-feature AUC, is-missing AUC, future-date checks and period-stability checks, and lints Python training code with an AST linter. Use when results look too good to be true, offline and online performance disagree, a feature is suspiciously important, or before trusting any new model or feature table."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Target Leakage Detector

Leakage is information in training that will not exist when the model makes a real prediction. It comes in
two kinds: **data leakage** (a column that knows the answer: written after the event, derived from the
label, or aggregated over the future) and **pipeline leakage** (the evaluation lets test rows influence
training: preprocessing, selection or resampling fitted before the split). Both inflate offline scores
and collapse in production. `scripts/leakage_scan.py` scans a training table for eight leakage signatures;
`scripts/code_leak_lint.py` lints training code for ten pipeline-leakage bugs.

## Trigger Conditions

Activate this skill when the user:
- Gets an implausibly good result (AUC > 0.95, R² > 0.95 on a hard business problem, a first baseline that
  beats the expected ceiling)
- Sees offline metrics far better than shadow/online metrics, or a model that decays immediately after launch
- Has one feature dominating importance or SHAP, especially a status, date, reason, flag or ID
- Is building a new feature table, label query or training script and wants a pre-flight check
- Uses target encoding, SMOTE, feature selection or scalers and is unsure whether CV is honest
- Asks "is this feature leaking?" or "why is my CV score so much higher than my test score?"

Split-level problems (duplicates and entity overlap between train and test, time overlap) are covered in
depth by [train-test-split-auditor](../train-test-split-auditor/SKILL.md); point-in-time feature building by
[time-based-feature-builder](../time-based-feature-builder/SKILL.md).

## Workflow

```
1. PREDICTION TIME -> write down when the model scores (the leakage line) and the label window
2. DATA SCAN       -> python scripts/leakage_scan.py table.csv --target y --time-col score_date --drop id
3. CODE SCAN       -> python scripts/code_leak_lint.py train.py
4. INVESTIGATE     -> for each high finding: when is the field written? by which process? overwritten?
5. FIX             -> drop, rebuild as-of prediction time, or move the step inside the Pipeline
6. CONFIRM         -> time-ordered holdout; the score should drop to a plausible level and stay stable by period
7. GUARD           -> keep both scans in CI for the feature table and the training code
```

## Data Leakage Signatures (leakage_scan.py)

| Code | Signature | Typical cause | Fix |
|------|-----------|---------------|-----|
| LD001 | one feature alone gives AUC > 0.9 (or |Spearman| > 0.95) | outcome-side field, label proxy | drop or rebuild as-of |
| LD002 | is-missing predicts the target | field filled only when the event happens (reason, resolution date) | drop; never impute it |
| LD003 | dates later than the prediction time | `last_login` read today for an old snapshot; event dates after scoring | as-of snapshot tables |
| LD004 | outcome-like column name | status, reason, refund, chargeback, closed, settled, approved | confirm write time with the owner |
| LD005 | row order / ID predicts the target | file sorted by outcome; IDs assigned at labelling | never use IDs; split deliberately |
| LD006 | feature is a deterministic function of the target | label encoded in another column, joins on the label table | drop |
| LD007 | identical features with different labels; duplicates | label noise, bad joins, duplicated events | dedupe; group-aware splits |
| LD008 | much stronger signal in old rows than new rows | backfilled or overwritten history | snapshot history; time-based validation |

```
LD001 [high] account_status: single feature AUC 0.939 > 0.9: almost certainly leakage or a proxy of the label
LD003 [high] last_login_date: 10% of values are later than score_date: information from the future
LD005 [medium] (row order): row position predicts the target (AUC 1.00): the file is sorted by outcome
```

Full taxonomy with real-world cases (healthcare, credit, churn, fraud, competitions):
[leakage-taxonomy.md](references/leakage-taxonomy.md).

## Pipeline Leakage (code_leak_lint.py)

| Code | Bug | Correct pattern |
|------|-----|-----------------|
| LK001 | scaler / imputer / encoder / PCA fitted before the split or CV | all preprocessing inside a `Pipeline` that is cross-validated |
| LK002 | SMOTE / over- / under-sampling before the split | `imblearn.pipeline.Pipeline([... ("smote", SMOTE()), ("model", ...)])` |
| LK003 | feature selection on all data before CV | selector inside the Pipeline; nested CV if tuned |
| LK004 | target column left in X | `X = df.drop(columns=[target, ...])` |
| LK005 | `.fit()` on test / validation data | fit on train only; `transform` elsewhere |
| LK006 | `groupby(...)[target].transform("mean")` on the training table | `TargetEncoder` (cross-fitted) or expanding means over past rows |
| LK007 | random split / shuffled KFold on temporal data | `TimeSeriesSplit`, cutoff dates, gap for label windows |
| LK008 | `fillna(df[c].mean())`, manual standardisation before the split | `SimpleImputer` / scalers in the Pipeline |
| LK009 | early stopping on the test set | separate validation split for `eval_set` |
| LK010 | CV of a bare estimator while preprocessing exists | cross-validate the whole Pipeline |

```python
from imblearn.pipeline import Pipeline            # supports samplers; behaves like sklearn's Pipeline
pipe = Pipeline([
    ("prep", ColumnTransformer([...])),           # fitted per training fold
    ("select", SelectFromModel(LogisticRegression(penalty="l1", solver="liblinear", C=0.1))),
    ("smote", SMOTE(random_state=0)),             # resamples training folds only
    ("model", LogisticRegression(max_iter=2000)),
])
scores = cross_val_score(pipe, X, y, cv=TimeSeriesSplit(n_splits=5, gap=4))
```
Before/after code for every rule: [pipeline-leakage-patterns.md](references/pipeline-leakage-patterns.md).

## Point-in-Time Correctness

For each row, every feature must be computable from data that existed **at that row's prediction time**:
- Join slowly changing tables "as of" the prediction time (`pd.merge_asof`, SQL `valid_from <= t < valid_to`).
- Aggregates use only events strictly before t (`shift()` before rolling; `closed="left"` windows).
- Respect data latency: if yesterday's events land at 06:00, a 02:00 score cannot use them.
- Respect label latency for target-derived features: only labels known by t.

Patterns and SQL: [point-in-time-correctness.md](references/point-in-time-correctness.md).

## Investigating a Suspicious Feature

1. **Who writes it, and when?** Ask the data owner; read the ETL. A field "updated nightly" overwrites history.
2. **Look at its timeline:** value distribution by days before the event. A jump just before the label is
   suspicious; a jump after is leakage.
3. **Rebuild it as-of** and compare single-feature AUC: a leak collapses, a real signal survives weaker.
4. **Ablate:** train without it on a time-ordered holdout. A small loss means it carried little real signal.
5. **Shadow test:** compute it live at prediction time and compare with the training value.

Playbook with queries and decision rules: [investigation-playbook.md](references/investigation-playbook.md).

## Plausibility Check

| Problem | Typical honest ROC-AUC | Treat as suspicious above |
|---------|------------------------|---------------------------|
| Customer churn (30-day) | 0.70-0.85 | 0.92 |
| Card fraud (rich velocity features) | 0.90-0.97 | 0.99 |
| Credit default (12-month) | 0.70-0.80 | 0.88 |
| Lead conversion | 0.70-0.85 | 0.92 |
| Hospital readmission (30-day) | 0.65-0.75 | 0.85 |
| Click-through | 0.70-0.80 | 0.90 |

Ranges are rough; an unusually strong result needs a leakage review before celebration, not after launch.

## Output Format

When checking for leakage, answer with:
1. **Prediction time and label window** used as the leakage line.
2. **Data findings** - `leakage_scan.py` output, each high finding with the likely mechanism.
3. **Code findings** - `code_leak_lint.py` output with the corrected code.
4. **Investigation results** - write times confirmed, as-of rebuilds, ablation deltas.
5. **Fixed evaluation** - score on a time-ordered holdout after fixes, stability by period.
6. **Guardrails** - scans added to CI, data contracts for the risky sources.

## Scripts

```bash
python scripts/leakage_scan.py table.csv --target churned
python scripts/leakage_scan.py table.csv --target churned --time-col score_date --drop customer_id
python scripts/leakage_scan.py table.csv --target price --auc 0.85 --json
```
Checks LD001-LD008: out-of-fold single-feature AUC (binary) or |Spearman| (numeric) above `--auc` (default
0.9), is-missing AUC > 0.85, datetime columns later than `--time-col`, outcome-like names, row order and
numeric IDs that predict the target, deterministic level-to-class mappings, conflicting or duplicated feature
rows, and signal decay from oldest to newest third. Exit codes: 0 no high findings, 1 high findings, 2 usage
or read error.

```bash
python scripts/code_leak_lint.py train.py
python scripts/code_leak_lint.py notebooks/*.py --json
cat train.py | python scripts/code_leak_lint.py -
```
AST rules LK001-LK010: preprocessing, selection and resampling fitted before the split; target column left
in X; fitting on test/validation data; in-sample groupby target means; shuffled splits in code that handles
dates; full-data fillna/standardisation; early stopping on the test set; CV of bare estimators while
preprocessing exists. Heuristic by design: export notebooks with `jupyter nbconvert --to script` first.
Exit codes: 0 no high findings, 1 high findings, 2 read or syntax error.

## Additional Resources

| File | Content |
|------|---------|
| [leakage-taxonomy.md](references/leakage-taxonomy.md) | Every leakage type with real cases: outcome fields, future data, proxies, IDs, duplicates, target encoding, temporal and group leakage, competition leaks |
| [point-in-time-correctness.md](references/point-in-time-correctness.md) | As-of joins (pandas merge_asof, SQL), snapshot tables, event-time vs processing-time, data and label latency |
| [pipeline-leakage-patterns.md](references/pipeline-leakage-patterns.md) | Before/after code for LK001-LK010, imblearn pipelines, nested CV, early stopping splits |
| [investigation-playbook.md](references/investigation-playbook.md) | Step-by-step investigation, timeline queries, as-of rebuild comparison, ablation, CI guards |
