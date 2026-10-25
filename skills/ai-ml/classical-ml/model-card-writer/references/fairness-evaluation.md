# Fairness Evaluation for Model Cards

## Choosing slices

- **Sensitive attributes** relevant to the domain and jurisdiction (e.g. sex, age, ethnicity, disability).
  Collecting or using them, even for evaluation only, is regulated in some places, so check with legal.
- **Proxies** when the attributes are unavailable: geography, language, device. Use them with care.
- **Business segments**: plan, region, channel, tenure band. Performance often differs most here.
- **Intersections** (group x age band) when sample sizes allow.
- **Data-quality strata**: new vs established customers, complete vs sparse records.

## Metrics and what they mean

| Metric | Definition | Fits when |
|--------|------------|-----------|
| Demographic parity difference | positive rate max - min | the benefit or burden should reach groups equally regardless of the label |
| Disparate impact ratio | positive rate min / max (< 0.8: four-fifths rule, US EEOC guideline) | screening, selection |
| Equal opportunity difference | TPR max - min | missing a true positive is the harm (e.g. not offering help to someone who needs it) |
| FPR difference | FPR max - min | false alarms are the harm (e.g. fraud flags, extra scrutiny) |
| Equalised odds | both TPR and FPR equal | both error types matter |
| Calibration within groups | predicted probability = observed rate in each group | scores are used as probabilities |
| AUC per group | ranking quality per group | the model's usefulness differs across groups |

When base rates differ between groups, calibration and equalised odds cannot both hold, except with a
perfect model (Kleinberg et al. 2016; Chouldechova 2017). Choose the notion from the decision's harms and
document why.

## Small groups

- Report n and positives; `slice_metrics.py` marks LOW-N (< 50 rows or < 10 positives or negatives) and
  leaves those slices out of the gaps.
- Use the bootstrap CIs: a gap whose intervals overlap heavily may be noise.
- Pool periods or use Bayesian shrinkage for rare groups instead of over-reading a point estimate.

## Mitigation options

| Stage | Option | Trade-off |
|-------|--------|-----------|
| Data | collect more data for under-served groups; fix label bias | slow, most durable |
| Features | remove proxies; add features that serve all groups | may cost accuracy |
| Training | reweighting, fairness constraints (Fairlearn `ExponentiatedGradient`) | explicit accuracy-fairness trade-off |
| Post-processing | group-specific thresholds (Fairlearn `ThresholdOptimizer`) | uses the attribute at decision time, which is legally restricted in some domains |
| Process | human review for affected groups; restrict use | operational cost |

Record the option chosen, the measured effect (before and after slice tables) and the residual gap.

## Tools

- `slice_metrics.py` (this skill): stdlib, CIs, gaps, flags.
- Fairlearn (`MetricFrame`, mitigation algorithms), AIF360, the What-If Tool, and Evidently for monitoring
  slices in production.

```python
from fairlearn.metrics import MetricFrame, true_positive_rate, selection_rate
mf = MetricFrame(metrics={"tpr": true_positive_rate, "selection": selection_rate},
                 y_true=y, y_pred=(score >= 0.4), sensitive_features=df["group"])
mf.by_group, mf.difference(), mf.ratio()
```
