# Reporting Importance

## Headline chart

Draw a horizontal bar chart of held-out permutation importance with error bars (± std over repeats), sorted,
showing the top 10-15 features or groups, in metric units.

```python
import matplotlib.pyplot as plt
imp = pd.read_csv("importances.csv").sort_values("permutation").tail(15)
fig, ax = plt.subplots(figsize=(6, 0.35 * len(imp) + 1))
ax.barh(imp.feature, imp.permutation, xerr=imp.permutation_std, color="#4C78A8")
ax.axvline(0, color="grey", lw=0.8)
ax.set_xlabel("drop in held-out ROC AUC when shuffled")
ax.set_title("Churn model v3 - permutation importance (test set, Q2 2026, 10 repeats)")
fig.tight_layout(); fig.savefig("importance.png", dpi=150)
```
- Error bars that cross zero mark features without a measurable effect.
- Put groups (e.g. "billing: total + monthly charges") on the same chart as single features.
- Avoid pie charts and stacked percentages: importances are not parts of a whole for permutation measures.

## Cross-check table

Show every method's share and rank next to each other, followed by the Spearman agreement between methods
(compare_importances.py prints both). Explain each disagreement in one line.

## Tiers instead of ranks

When intervals overlap, report tiers:

| Tier | Rule |
|------|------|
| Strong | permutation mean - 2 std > 10% of the top feature |
| Moderate | mean - 2 std > 0 |
| No measurable effect | interval includes 0 |

## Wording

- "Shuffling tenure lowers the model's AUC on held-out customers by 0.08 ± 0.02: it is the strongest driver."
- "Total charges and tenure carry overlapping information. Together they account for 0.11 AUC, but each looks
  small on its own."
- "Customer ID hash was removed: the model was memorising it."
- "These numbers describe this model. They do not mean that changing a customer's tenure would change
  their churn."

## Checklist

- [ ] held-out data, project metric, repeats stated
- [ ] uncertainty shown (std or fold range)
- [ ] one-hot and correlated features grouped
- [ ] IDs and post-outcome fields removed or explained
- [ ] at least two methods compared; disagreements explained
- [ ] stability across folds checked for any feature-selection decision
- [ ] chart title names the model version, the data and the method
