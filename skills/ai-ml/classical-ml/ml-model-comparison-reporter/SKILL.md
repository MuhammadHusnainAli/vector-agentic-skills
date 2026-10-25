---
name: ml-model-comparison-reporter
description: "Compare machine learning models honestly and write the comparison report: per-fold CV scores analysed with the corrected resampled t-test (Nadeau-Bengio), Wilcoxon signed-rank, Bayesian correlated t-test with a region of practical equivalence, and the Friedman test with average ranks for many models; single-test-set comparisons with the DeLong test for ROC-AUC, McNemar's test on decisions (threshold or top-K), and paired stratified bootstrap CIs for PR-AUC, log loss, Brier, MAE and RMSE; plus practical significance, multiple-comparison control, cost/latency trade-offs and a decision rule. Pure-Python implementations validated against scipy and a brute-force DeLong. Use when someone asks which model is better, whether a gain is significant, how to compare CV results, needs a model comparison table or report for stakeholders, or wants to replace a production model with a challenger."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# ML Model Comparison Reporter

"Model B scores 0.861 vs 0.858" is not a result; it is a pair of noisy estimates. A comparison needs
**pairing** (same folds or same test rows), a test that respects how the scores were produced (CV folds
share training data, so ordinary t-tests are overconfident), a **practical** threshold (is +0.003 AUC worth
anything?), and the costs (latency, complexity) next to the gains. `scripts/compare_models.py` analyses
per-fold CV scores for any number of models; `scripts/paired_predictions.py` compares two models on one
test set row by row. Both are standard-library Python and match scipy / reference implementations.

## Trigger Conditions

Activate this skill when the user:
- Asks "which model is better?", "is this improvement significant?", "can we replace the champion?"
- Has CV results from several models (a bake-off, a tuning run, feature-set variants) and wants a verdict
- Has two models' predictions on the same holdout and wants a test (AUC difference, accuracy difference)
- Needs a comparison table, slide or written report for stakeholders
- Compares many models/datasets and needs multiple-comparison control

Producing per-fold results: [classification-model-selector](../classification-model-selector/SKILL.md)
(bake-off script); baselines to include: [ml-baseline-model-builder](../ml-baseline-model-builder/SKILL.md);
metric choice: [ml-success-metric-selector](../ml-success-metric-selector/SKILL.md).

## Workflow

```
1. ALIGN     -> identical folds (or identical test rows) for every model; record per-fold scores
2. SUMMARISE -> python scripts/compare_models.py folds.csv --metric average_precision --rope 0.005
3. HOLDOUT   -> python scripts/paired_predictions.py holdout_preds.csv --a challenger --b champion --k 400
4. PRACTICAL -> define the smallest difference that matters (ROPE) before looking at results
5. COSTS     -> fit time, latency, size, maintenance next to the metric deltas
6. DECIDE    -> simplest model not distinguishable from the best, unless the gain exceeds the ROPE
7. REPORT    -> table + tests + decision + caveats (references/report-template.md)
```

## Which Test for Which Evidence

| Evidence | Test | Why |
|----------|------|-----|
| k-fold CV scores, 2 models | **corrected resampled t-test** | fold scores are correlated (shared training data); the correction inflates the variance by (1/k + n_test/n_train) |
| same, non-parametric | Wilcoxon signed-rank on fold differences | no normality assumption; low power with 5 folds (minimum p = 0.0625) |
| same, decision-oriented | Bayesian correlated t-test with ROPE | P(A better), P(equivalent), P(B better) instead of a p-value |
| CV scores, 3+ models | Friedman test on ranks, then pairwise corrected tests vs the best | omnibus first, then post-hoc |
| One test set, ROC-AUC | **DeLong test** | exact variance of correlated AUCs on the same rows |
| One test set, decisions at a threshold / top-K | **McNemar** on discordant pairs | only rows where the models disagree carry information |
| One test set, any metric (PR-AUC, log loss, MAE) | paired (stratified) bootstrap CI of the difference | resample rows once, score both models on them |
| Online A/B | two-sample test on the business metric | randomised traffic, pre-registered |

Formulas, assumptions and when each fails: [statistical-tests.md](references/statistical-tests.md).

## Reading compare_models.py

```
model                 mean      std   rank
lightgbm            0.8578   0.0110   1.20
random_forest       0.8536   0.0090   1.80
logreg              0.8364   0.0081   3.00

model                diff   wins  p corr-t  p naive-t  p Wilcoxon  P(best>)  P(equiv)
random_forest     +0.0042   8/10     0.154      0.050       0.064      0.39      0.61
logreg            +0.0214  10/10     0.000      0.000       0.002      1.00      0.00
```
- The **naive** paired t-test says LightGBM beats random forest (p = 0.050); the **corrected** test does not
  (p = 0.154). The correction is the honest one for CV.
- With ROPE ±0.005 the Bayesian test puts 61% on "practically equivalent": prefer the simpler/cheaper model.
- LightGBM beats logistic regression in every fold, by 0.021: real and practically large.

## Reading paired_predictions.py

```
DeLong: AUC A 0.9788  B 0.9130  diff +0.0657 (95% CI +0.0355 .. +0.0960), z 4.26, p 0.0000
McNemar (top-50 of each model): A right/B wrong 32, A wrong/B right 8, p 0.0002 (exact binomial)
  pr_auc    +0.2057  95% CI [+0.1114, +0.3091]
```
Use the test that matches the decision: DeLong for ranking quality, McNemar at the operating point (top-K or
threshold), bootstrap CIs for everything else.

## Practical Significance and Multiplicity

- **Fix the ROPE before looking**: e.g. "±0.005 PR-AUC is noise for this business", or derive it from the
  value model (the difference that changes expected profit by less than the cost of switching).
- **Many comparisons** (10 models, 5 feature sets): control the family-wise error (Holm) or false discovery
  rate (Benjamini-Hochberg), or compare everything against one pre-declared baseline.
- **Test-set reuse**: every look at the test set to choose a model makes its score optimistic; choose on CV,
  confirm once on the holdout.
- **Statistical ≠ practical**: with 1M test rows, +0.0005 AUC is "significant" and worthless.

Details, Holm/BH code and the decision rule: [decision-rules-and-pitfalls.md](references/decision-rules-and-pitfalls.md).

## Output Format

A comparison report contains:
1. **Setup** - data, split/folds, metric(s), ROPE, models and their tuning budgets (equal?).
2. **Table** - mean ± sd (or holdout value with CI) per model, mean rank, cost columns (`--markdown` output).
3. **Tests** - corrected t / Wilcoxon / Bayesian vs the best, Friedman for 3+ models; DeLong / McNemar /
   bootstrap on the holdout.
4. **Decision** - the chosen model and the rule that chose it (best, or simplest within ROPE).
5. **Caveats** - fold count, few positives, test-set reuse, distribution shift, online validation still needed.

Template and an example: [report-template.md](references/report-template.md).

## Scripts

```bash
python scripts/compare_models.py bakeoff_folds.csv --metric average_precision
python scripts/compare_models.py cv_scores.csv --metric roc_auc --rope 0.005 --test-train-ratio 0.25
python scripts/compare_models.py folds.csv --metric log_loss --markdown
python scripts/compare_models.py folds.csv --metric rmse --lower-better --json
```
Long CSV (model, fold, metrics). Mean, std, mean rank; for each model vs the best: mean paired difference, wins,
corrected resampled t-test (Nadeau-Bengio; `--test-train-ratio` defaults to 1/(k-1)), naive paired t-test for
contrast, exact Wilcoxon signed-rank (normal approximation above 20 folds), Bayesian correlated t-test
probabilities with `--rope`; Friedman test for >= 3 models. Lower-is-better metrics are detected from the name.
Exit codes: 0 printed, 2 usage error or fewer than 2 models / 3 shared folds.

```bash
python scripts/paired_predictions.py holdout.csv --a challenger --b champion
python scripts/paired_predictions.py holdout.csv --a lgbm --b logreg --k 400 --n-boot 2000
python scripts/paired_predictions.py reg_holdout.csv --regression --a new --b old
```
Binary: DeLong AUC difference with SE, CI and p; McNemar at `--threshold` or each model's top-`--k` (exact below
50 discordant pairs); stratified paired bootstrap CIs for ROC-AUC, PR-AUC, log loss and Brier differences.
Regression: bootstrap CIs for MAE/RMSE differences and a sign test. Exit codes: 0 printed, 2 usage or data error.

## Additional Resources

| File | Content |
|------|---------|
| [statistical-tests.md](references/statistical-tests.md) | Corrected resampled t-test, 5x2cv, Wilcoxon, Friedman/Nemenyi, Bayesian correlated t-test, DeLong, McNemar, bootstrap: formulas, assumptions, scipy/statsmodels code |
| [decision-rules-and-pitfalls.md](references/decision-rules-and-pitfalls.md) | ROPE choice, one-SE and simplest-within-noise rules, Holm/BH corrections, test reuse, unequal tuning, champion/challenger |
| [report-template.md](references/report-template.md) | Report structure, markdown table, wording for significant / equivalent / inconclusive results, worked example |
