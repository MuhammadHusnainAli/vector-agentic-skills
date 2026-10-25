# Data Requirements and Non-Normal Data

## Before calculating

1. **Measurement system:** Gage R&R acceptable; resolution at least 1/10 of the tolerance.
2. **Stability:** the control chart shows no special causes. Capability of an unstable process predicts nothing.
3. **Amount of data:** at least 100 values (25 subgroups of 4-5) for an initial study; 30-50 gives only a rough
   estimate with a wide confidence interval.
4. **Representative:** covers normal sources of variation (shifts, operators, material lots, tool changes).

## Checking normality

Anderson-Darling p < 0.05 means the normal model does not fit. First ask **why**:

| Cause | Sign | Fix |
|-------|------|-----|
| Mixture of streams (cavities, spindles, machines) | Bimodal histogram | Analyse each stream separately |
| Special causes / drift | Out-of-control chart | Stabilise first |
| Natural boundary (flatness, runout, roughness >= 0) | Right-skewed, bounded at 0 | Non-normal method |
| Rounding / poor resolution | Few distinct values | Better gauge |
| Sorting / truncation | Missing tail at a spec limit | Measure before inspection |

## Non-normal methods

| Method | How | Notes |
|--------|-----|-------|
| Percentile (ISO 22514-2) | Pp = (USL - LSL) / (P99.865 - P0.135); Ppk from the median to each spec over the half-spread | Needs several hundred values for stable tail percentiles; `--method percentile` |
| Fit a distribution | Lognormal, Weibull, gamma; compute percentiles from the fitted distribution | Check fit with a probability plot |
| Box-Cox transform | Transform data and specs, compute indices on transformed data | Report the lambda used |

Report which method was used. Do not switch methods to "get a better number".
