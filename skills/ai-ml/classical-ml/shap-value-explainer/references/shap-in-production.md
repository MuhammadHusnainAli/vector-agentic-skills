# SHAP in Production

## Reason codes

Reason codes are the top features pushing a decision in the unfavourable direction, translated into
approved wording.

```python
def reason_codes(sv_row, names, wording, k=4, direction=+1):
    """Top-k features pushing the score towards the adverse outcome (direction=+1: higher score = adverse)."""
    contrib = sorted(((direction * v, n) for v, n in zip(sv_row, names) if direction * v > 0), reverse=True)
    return [wording.get(n, n) for _, n in contrib[:k]]
```
- Map grouped features (all one-hot levels, all aggregates of a source) to a single code.
- Keep a reviewed wording table. Features without approved wording should not be used as reasons, and
  arguably not as features.
- Use a fixed, documented background (e.g. a sample of approved applicants) so that codes mean "relative to
  the typical approved case".
- Adverse-action notices (credit decisions in the US under ECOA/Regulation B; similar duties under GDPR
  Art. 22 and the EU AI Act for high-risk systems) require the principal reasons. Have compliance review the
  method. SHAP is commonly used, but the wording and the background are what get scrutinised.

## Latency and storage

| Pattern | When |
|---------|------|
| Compute SHAP at scoring time (TreeExplainer path-dependent) | per-request explanations, small trees, < ~10 ms budget |
| Compute in batch after scoring | dashboards, monitoring, outreach lists |
| Store top-k only (feature, value, SHAP) | audit trails; full vectors only for sampled rows |
| Precompute for the decision-relevant segment | e.g. only declined or flagged cases |

LightGBM and XGBoost compute SHAP natively and quickly: `model.predict(X, pred_contrib=True)` (LightGBM) and
`booster.predict(DMatrix(X), pred_contribs=True)` (XGBoost) return SHAP values plus a bias column without the
shap package. This is the path-dependent variant.

## Monitoring explanations

- Track mean |SHAP| per feature per week. A feature whose share jumps signals drift or a pipeline bug before
  performance metrics move (labels arrive late).
- Track the base value. It should change only with a model or background change.
- Compare SHAP distributions between training and production with the same population-stability checks used
  for features.
- After a retrain, diff the global ranking and directions against the previous model. Unexplained flips need
  review before release.

## Governance checklist

- [ ] explainer, perturbation mode, background (source, size, date) and output space documented
- [ ] additivity checked in the pipeline
- [ ] correlated features grouped for reporting
- [ ] reason-code wording reviewed; sensitive attributes and their proxies are never reasons
- [ ] explanations stored with the model version
- [ ] the model card ([model-card-writer](../../model-card-writer/SKILL.md)) links the global explanation
