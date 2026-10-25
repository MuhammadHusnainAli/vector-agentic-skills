---
name: model-card-writer
description: "Write model cards that hold up to review: model details, intended and out-of-scope uses, training and evaluation data with periods and label definitions, overall metrics with confidence intervals, the baseline and decision threshold, performance disaggregated by group or segment with bootstrap intervals, fairness gaps (TPR/equal opportunity, FPR, positive rate and the four-fifths ratio), explainability, limitations, ethical considerations, risks with mitigations, and monitoring. Computes slice metrics from a predictions file, generates the card from a JSON spec with visible TODOs for missing sections, and lints existing cards for missing sections, placeholders, metrics without numbers or uncertainty, missing subgroup results and overclaiming language. Follows Mitchell et al. (2019) Model Cards and the Hugging Face card layout. Use when someone documents a model, prepares a model for review or release, or needs a model card, model documentation or a fairness and performance report."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Model Card Writer

A model card is the model's label: what it does, what it was trained and tested on, how well it works
(overall and for each group that matters), where it fails, and who to call. Cards fail review for
predictable reasons: no out-of-scope uses, metrics without uncertainty, no breakdown by group, "unbiased"
claims without evidence, and TODOs left in. `scripts/slice_metrics.py` computes the disaggregated
evaluation, `scripts/model_card.py` writes the card from a JSON spec, and `scripts/card_lint.py` reviews any
card.

## Trigger Conditions

Activate this skill when the user:
- Asks for a model card, model documentation, or a model release/review document
- Needs performance by group, segment or demographic, or a fairness section
- Prepares for model risk review, an audit, or publishing a model (e.g. on Hugging Face)
- Shares a card or README and asks whether it is complete

Inputs often come from other skills: metrics from [ml-success-metric-selector](../ml-success-metric-selector/SKILL.md),
comparisons from [ml-model-comparison-reporter](../ml-model-comparison-reporter/SKILL.md), drivers from
[feature-importance-reporter](../feature-importance-reporter/SKILL.md) and [shap-value-explainer](../shap-value-explainer/SKILL.md).

## Workflow

```
1. PREDICT   -> evaluation predictions: y_true, y_score (or y_pred) and the slice columns
2. SLICES    -> python scripts/slice_metrics.py preds.csv --slices group age_band --threshold 0.4 --json > slices.json
3. SPEC      -> write spec.json (schema: references/card-spec.md), with facts from the owners
4. CARD      -> python scripts/model_card.py spec.json --slices slices.json -o MODEL_CARD.md --strict
5. LINT      -> python scripts/card_lint.py MODEL_CARD.md
6. REVIEW    -> owners confirm intended use, limitations and risks; version the card with the model
```

## What a Card Must Contain

| Section | Content | Common failure |
|---------|---------|----------------|
| Model details | what it predicts, type, version, date, owners | no owner or version |
| Intended use | decisions supported, users | vague ("predict churn") |
| Out-of-scope | uses that are not allowed | missing entirely |
| Data | sources, **periods**, rows, label definition, known gaps | no dates; label not defined |
| Evaluation | metrics on held-out (preferably out-of-time) data with **CIs**, baseline, threshold | test-set point estimates only |
| Performance across groups | the same metrics per slice with CIs; small slices marked | absent, or only overall |
| Fairness | attributes assessed, gaps, the decision on them | "the model is fair" |
| Limitations | where it fails, populations not covered | generic disclaimers |
| Ethical considerations | affected people, sensitive features and proxies, harms | missing |
| Risks and mitigations | concrete risk, concrete mitigation, owner | risks without mitigation |
| Monitoring | metrics, drift checks, retraining trigger, owner | "will be monitored" |

Section-by-section guidance with examples: [writing-model-cards.md](references/writing-model-cards.md).

## Disaggregated Evaluation

`slice_metrics.py` reports, overall and per slice level: n, positives, ROC AUC and TPR with 95% bootstrap
CIs, average precision, FPR, positive rate, Brier score (or MAE/RMSE/bias for regression). Per slice column
it reports:

| Gap | Fairness notion | Flag |
|-----|-----------------|------|
| TPR max - min | equal opportunity difference | > `--max-gap` (0.1) |
| FPR max - min | part of equalised odds | > 0.1 |
| positive rate max - min | demographic parity difference | > 0.1 |
| positive rate min / max | disparate impact ratio | < 0.8 (four-fifths rule) |
| AUC CI below overall AUC | slice underperforms | UNDERPERFORMS |
| n < 50 or < 10 positives / negatives | unreliable estimate | LOW-N (excluded from gaps) |

Metrics match scikit-learn (AUC, average precision, recall, Brier verified). Which notion applies depends on
the decision; they cannot all hold at once when base rates differ. See
[fairness-evaluation.md](references/fairness-evaluation.md).

## Writing Rules

- **Numbers with uncertainty, on the right data**: out-of-time evaluation where the model will face the
  future; CIs or fold ranges.
- **State the threshold** for classifiers. Rates (TPR, FPR, positive rate) depend on it.
- **Compare to a baseline**: the current process, a simple rule, or the previous model.
- **Say who is not covered**: segments missing from training, low-n slices, new markets.
- **No blanket claims**: write "TPR differs by 0.33 between groups A and B (0.84 vs 0.51)", not "the model is
  fair/unbiased".
- **Version the card with the model**: the card describes one model version and one evaluation.

## Output Format

When writing a model card, deliver:
1. **MODEL_CARD.md** - all sections above, generated from the spec, with no TODOs left.
2. **Slice report** - the disaggregated table with CIs and the flagged gaps, plus how they are addressed.
3. **Lint result** - `card_lint.py` with no high findings.
4. **Open questions** - facts only the owners can confirm (intended use, out-of-scope, risks).

## Scripts

```bash
python scripts/slice_metrics.py preds.csv --slices group age_band --threshold 0.4
python scripts/slice_metrics.py preds.csv --slices region --markdown
python scripts/slice_metrics.py preds.csv --regression --pred-col y_pred --slices segment --json > slices.json
```
Exit codes: 0 no flags, 1 a slice underperforms or a gap exceeds the limits, 2 usage or read error.

```bash
python scripts/model_card.py spec.json -o MODEL_CARD.md
python scripts/model_card.py spec.json --slices slices.json -o MODEL_CARD.md --strict
```
Writes YAML metadata and every section. Missing required sections become visible `**TODO:**` lines.
Exit codes: 0 written, 1 TODOs remain with `--strict`, 2 usage or read error.

```bash
python scripts/card_lint.py MODEL_CARD.md
python scripts/card_lint.py README.md --json
```
Rules MC001-MC011: missing core sections, placeholders, metrics without numbers, no uncertainty, no slices,
overclaiming, no data dates, no baseline, no threshold, no owner/version, no monitoring. Exit codes: 0 no
high findings, 1 high findings, 2 read error.

## Additional Resources

| File | Content |
|------|---------|
| [card-spec.md](references/card-spec.md) | the JSON spec schema with a complete example |
| [writing-model-cards.md](references/writing-model-cards.md) | section-by-section guidance, good and bad examples, review checklist |
| [fairness-evaluation.md](references/fairness-evaluation.md) | choosing slices, fairness metrics and their trade-offs, small groups, mitigation options |
