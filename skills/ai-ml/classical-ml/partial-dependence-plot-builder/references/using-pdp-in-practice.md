# Using PDP in Practice

## Monotonic constraints

When domain knowledge says a response must be monotonic (more income never raises credit risk, a higher price
never raises demand), enforce it in the model instead of hoping:

| Library | Setting |
|---------|---------|
| LightGBM | `monotone_constraints=[1, -1, 0, ...]` (1 increasing, -1 decreasing), `monotone_constraints_method="advanced"` |
| XGBoost | `monotone_constraints="(1,-1,0)"` or a dict by feature name |
| CatBoost | `monotone_constraints={"tenure": -1}` (dict by name, or a list of ints by position) |
| HistGradientBoosting | `monotonic_cst={"tenure_months": -1}` |

Verify afterwards: the share of ICE curves moving the wrong way should be 0 (`ice_analysis.py`: up/down counts).
Compare the held-out score with and without constraints. A small loss is often worth the plausibility.

## Plausibility review

For each top feature, ask a domain expert to state the expected shape before showing the plot. Then compare:

| Outcome | Action |
|---------|--------|
| Shape matches | document it |
| Shape differs but data supports it | investigate the data. It may be a real finding, a proxy effect or leakage |
| Shape differs in low-support regions only | cap the feature or constrain it |
| Saw-tooth or implausible thresholds | regularise, increase min_child_samples, or constrain |

## Regulated models (credit, insurance, healthcare)

- Regulators and model-risk teams expect documented, plausible, usually monotonic responses for key drivers.
- Keep PDP/ALE plots with the model documentation ([model-card-writer](../../model-card-writer/SKILL.md)).
- Check fairness proxies: plot predictions against features correlated with protected attributes, such as
  zip code against race.
- Re-run the plots at each retrain and diff the shapes.

## Stakeholder charts

- One feature per chart. Use ALE or PDP with a band (the 10th-90th percentile of centred ICE) rather than
  hundreds of lines.
- Label the y-axis in business units ("predicted churn probability, percentage points").
- Shade or cut regions without data.
- Use one sentence: "Customers with longer tenure are scored as much less likely to churn, mostly in the
  first two years."

```python
band_lo, band_hi = np.percentile(centred, [10, 90], axis=0)
ax.fill_between(grid, band_lo, band_hi, alpha=0.25, label="10-90% of customers")
ax.plot(grid, centred.mean(axis=0), lw=2.5, label="average")
```

## Monitoring

Partial dependence shapes are a model fingerprint. After a retrain, compare the PDP/ALE curves of the top
features with the previous version. A changed shape without a known data change is a red flag.
