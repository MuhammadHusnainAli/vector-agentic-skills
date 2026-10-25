# PCA for Monitoring and Outlier Detection

## Statistics

With standardised observation z, k retained components P (columns), scores t = Pᵀz, eigenvalues λ:
```
T²  = Σ_{i=1..k} t_i² / λ_i           (Hotelling: distance inside the model plane)
Q   = || z − P t ||²                   (squared prediction error, SPE: distance from the plane)
```
- High T², normal Q: an extreme but correlation-consistent state (e.g. high load, everything rises together).
- High Q: the correlation structure is broken (sensor drift, fault, new operating regime).

## Control limits

| Method | Limit |
|--------|-------|
| Empirical (used by pca_outliers.py) | α-quantile of T² and Q on the reference period |
| T², F-distribution | `k (n−1)(n+1) / (n (n−k)) · F_{α}(k, n−k)` (new observations, normality) |
| T², chi-square | χ²_α(k) for large n |
| Q, Jackson-Mudholkar | approximation from the discarded eigenvalues θ_1, θ_2, θ_3 |
| Q, Box | g·χ²_α(h) with g = θ_2/θ_1, h = θ_1²/θ_2 |

Empirical limits need a reasonably large, clean reference period; parametric limits assume approximately
normal data.

## Contributions

- Q contributions: squared residual per feature (z_j − ẑ_j)²; the largest point to the broken sensor or
  variable.
- T² contributions: per feature, Σ_i (t_i / λ_i) · p_ij · z_j; interpret with care (can be negative).

## Reference period design

1. Choose a period of normal operation (no known incidents, representative regimes).
2. Remove known faults; fit scaler and PCA; set limits.
3. Validate on a separate normal period (false-alarm rate ≈ 1 − α) and on known incidents (detection).
4. Refit when the process legitimately changes; version the model.

## Dynamic and adaptive variants

- Dynamic PCA: add lagged copies of variables to capture autocorrelation.
- Recursive / moving-window PCA: refit on a rolling window for slowly drifting processes.
- Multi-mode processes: one PCA per operating mode, or mixture models.

## Practical tips

- Alarm on persistence (e.g. 3 consecutive points over the limit) to reduce false alarms.
- Show operators the contribution chart, not just the flag.
- Combine with univariate limits for safety-critical variables.
