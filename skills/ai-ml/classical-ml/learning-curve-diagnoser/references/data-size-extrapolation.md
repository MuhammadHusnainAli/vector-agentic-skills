# Data-Size Extrapolation

## The model

Empirically, generalisation error falls as a power law in the training size, so a score that rises
with data follows

    val(n) = a - b * n^(-c),   b >= 0, c > 0

- `a` is the asymptote: the score this model class reaches with unlimited data from the same distribution.
- `c` is the learning rate of the curve; 0.3-0.7 is typical for tabular models.
- `b` scales how far the current curve is from the asymptote.

`diagnose_curve.py` grid-searches `c` (0.005-1.5) and solves `a` and `b` by least squares on the largest four
sizes. The smallest sizes are often in a different regime and pull the fit around. The asymptote is capped at
the final training score, because training descends towards the same limit. This fit matches
`scipy.optimize.curve_fit` with the same bounds.

## How far to trust it

| Extrapolation | Reliability |
|---------------|-------------|
| within the measured range | interpolation, good |
| 2x the largest size | usually within the fold noise |
| 4x | a guess; the exponent is poorly determined from four points |
| 10x and beyond | a direction only; curves often flatten earlier than the power law says |

Requirements:
- new data from the same distribution, with the same labelling process and quality
- R^2 of the fit >= 0.9 (the script warns otherwise and falls back to the measured slope capped by headroom)
- enough folds that the fold standard error is smaller than the gain being predicted

## Is collecting data worth it?

```
value of doubling = (predicted gain from 2x) x (value per metric point)
cost of doubling  = rows x labelling cost per row + training cost growth (fit_time column)
```
Translate the metric into money with the metric-to-business mapping from
[ml-success-metric-selector](../../ml-success-metric-selector/SKILL.md): e.g. +0.02 recall at fixed
precision x fraud loss per missed case.

## Alternatives when data is the bottleneck

| Option | When |
|--------|------|
| Active learning (label the uncertain rows) | labels are expensive, unlabelled rows are plentiful |
| Weak supervision / labelling rules | experts can write heuristics faster than labels |
| More positives only | imbalanced targets: the curve is driven by the minority class |
| Pretrained embeddings / transfer | text, images, product catalogues |
| Stronger priors: monotonic constraints, simpler model | small data and high variance |
| Data augmentation | images/audio; rarely meaningful for tabular data |
| Longer history | time series, if the old data is still relevant (check with a recency test) |

## Sample size for a target

With `--target`, the script solves `n = (b / (a - target))^(1/c)`. If the target is at or above the
asymptote it reports that more data alone cannot reach it. Present it as an order of magnitude, together
with the 2x prediction you can test cheaply.
