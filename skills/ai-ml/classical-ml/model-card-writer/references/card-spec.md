# Model Card Spec (model_card.py)

All keys are optional except `name`. The required sections (written as `**TODO:**` when missing) are
description, owners, intended_use.primary_uses, intended_use.out_of_scope, training_data, evaluation_data,
metrics, limitations, ethical_considerations and monitoring.

| Key | Type | Example |
|-----|------|---------|
| name | string | `"churn-risk-gbm"` |
| version, date | string | `"3.1.0"`, `"2026-10-01"` |
| owners | list of {name, contact} | `[{"name": "Retention Analytics", "contact": "retention-ml@example.com"}]` |
| model_type, task, framework, license | string | `"LightGBM binary classifier"` |
| description | string | one paragraph: what, for whom, how it is used |
| intended_use.primary_uses / primary_users / out_of_scope | list of strings | |
| training_data, evaluation_data | {source, period, rows, label_definition, preprocessing, known_gaps} or a string | |
| metrics | list of {name, value, ci [lo, hi], split} | `{"name": "ROC AUC", "value": 0.795, "ci": [0.765, 0.821], "split": "out-of-time 2026H1"}` |
| baseline | {name, metrics {metric: value}} | `{"name": "rule: support_calls >= 3", "metrics": {"ROC AUC": 0.68}}` |
| threshold | {value, rationale} | `{"value": 0.4, "rationale": "call capacity"}` |
| fairness | {attributes [], assessment} | |
| explainability | string | how the model's decisions are explained |
| limitations, ethical_considerations, caveats | list of strings | |
| risks | list of {risk, mitigation} | |
| monitoring | {metrics [], drift, retraining, owner} | |
| citation | string | BibTeX or a plain reference |

The per-slice table comes from `slice_metrics.py --json` via `--slices`; it is not part of the spec.

## Complete example

See `tests/fixtures/ml/model_card_spec.json` in this repository. Abridged:

```json
{
  "name": "churn-risk-gbm",
  "version": "3.1.0",
  "date": "2026-10-01",
  "owners": [{"name": "Retention Analytics", "contact": "retention-ml@example.com"}],
  "description": "Scores active subscribers each Monday with the probability of cancelling within the next 60 days...",
  "intended_use": {
    "primary_uses": ["Prioritising weekly retention calls for consumer subscribers"],
    "out_of_scope": ["Pricing or credit decisions", "Business customers (not in the training data)"]
  },
  "training_data": {"source": "churn_features_v4", "period": "2024-01 to 2025-12", "rows": "412,000 customer-weeks",
                    "label_definition": "cancelled within 60 days after the snapshot date"},
  "evaluation_data": {"source": "same pipeline, out-of-time", "period": "2026-01 to 2026-06"},
  "metrics": [{"name": "ROC AUC", "value": 0.795, "ci": [0.765, 0.821], "split": "out-of-time 2026H1"}],
  "threshold": {"value": 0.4, "rationale": "the call team handles about 39% of flagged customers per week"},
  "limitations": ["Customers with under 2 months of tenure have few signals"],
  "ethical_considerations": ["Lower recall for group B means fewer retention offers to that group"],
  "risks": [{"risk": "Group B under-served", "mitigation": "group-specific threshold under review"}],
  "monitoring": {"metrics": ["weekly AUC on matured labels", "score PSI"], "retraining": "quarterly, or PSI > 0.2"}
}
```

## Keeping cards current

- Generate the card in the training pipeline: spec facts from config, metrics and slices from the
  evaluation step, so each model version gets its own card.
- Store the card next to the model artefact (registry entry, `README.md` of a Hugging Face repo).
- Diff the cards between versions in review.
