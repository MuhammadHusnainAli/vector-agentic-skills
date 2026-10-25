# Model Comparison Report Template

```markdown
# Model comparison: <task> (<date>)

## Setup
- Data: <rows>, <positives / target summary>, period <dates>
- Evaluation: <splitter> (<k> folds, <repeats>), primary metric <metric>, ROPE ±<r> (set before analysis)
- Holdout: <period / size>, used once for confirmation
- Models and tuning: <model: budget, search method>; all on identical folds

## Results (CV)
<compare_models.py --markdown output>

Cost columns:
| model | fit time | latency (ms / 1k rows) | model size | notes |

## Statistical comparison
- Friedman across <K> models: chi2 = <x>, p = <p>
- <best> vs <runner-up>: Δ = <d> (<wins>/<k> folds), corrected t p = <p>, P(equivalent within ROPE) = <x>

## Holdout confirmation
<paired_predictions.py output: DeLong, McNemar at the operating point, bootstrap CIs>

## Decision
<chosen model> because <rule>. <What was rejected and why.>

## Caveats
- <few positives, fold count, distribution shift, online validation pending>
```

## Wording

| Result | Write |
|--------|-------|
| Significant and above ROPE | "B outperforms A by 0.021 PR-AUC (corrected t-test p < 0.001; 10/10 folds), well above the 0.005 equivalence margin." |
| Equivalent | "A and B are practically equivalent: the difference is 0.004 ± 0.003 and the posterior probability of equivalence within ±0.005 is 0.61. We choose A (2x faster, no extra dependency)." |
| Inconclusive | "The data cannot separate A and B: Δ = 0.012 with a 95% interval from −0.008 to +0.032. More folds or a larger holdout would be needed to resolve it." |
| Holdout disagrees with CV | "B led in CV but not on the latest-quarter holdout (Δ −0.006, CI −0.02..+0.01); possible drift. We keep A and investigate." |

Avoid: "B is better (0.861 vs 0.858)" without uncertainty; "significant" without the test; "no difference" when
the interval is wide (absence of evidence is not evidence of equivalence).

## Worked example (churn bake-off fixture, 5 folds, primary PR-AUC)

| model | PR-AUC mean ± sd | rank | Δ vs logreg | corrected-t p |
|---|---|---|---|---|
| **logreg** | 0.621 ± 0.095 | 1.6 | - | - |
| ebm | 0.605 ± 0.114 | 3.0 | −0.016 | 0.40 |
| et | 0.576 ± 0.084 | 3.2 | −0.045 | 0.14 |
| catboost | 0.557 ± 0.070 | 4.4 | −0.064 | 0.12 |
| lgbm | 0.496 ± 0.057 | 6.6 | −0.125 | 0.09 |

Decision: logistic regression. With 400 rows and 5 folds no model is significantly better, the logistic model
has the best mean, is fastest and is best calibrated. Revisit GBMs when the dataset grows.
