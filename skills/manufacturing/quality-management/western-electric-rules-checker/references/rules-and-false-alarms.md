# Run Rules and Their False-Alarm Cost

## Zones

```
 +3 sigma  ---------- UCL
   Zone A   (2 to 3 sigma)
 +2 sigma
   Zone B   (1 to 2 sigma)
 +1 sigma
   Zone C   (0 to 1 sigma)
   centre   ---------- CL
   Zone C, B, A mirrored below
 -3 sigma  ---------- LCL
```
Sigma here is the sigma of the **plotted statistic**: for an X-bar chart, sigma_x / sqrt(n) = (UCL - CL) / 3.

## Rule sets

| Western Electric | Nelson | Pattern |
|------------------|--------|---------|
| WE1: 1 point beyond zone A | 1 | Single point beyond 3 sigma |
| WE2: 2 of 3 in zone A or beyond, same side | 5 | Shift starting |
| WE3: 4 of 5 in zone B or beyond, same side | 6 | Smaller shift |
| WE4: 8 in a row on one side | 2 (9 in a row) | Sustained shift |
| - | 3: 6 in a row increasing or decreasing | Trend |
| - | 4: 14 in a row alternating | Over-adjustment, two streams |
| - | 7: 15 in a row in zone C | Stratification |
| - | 8: 8 in a row outside zone C, both sides | Mixture |

`we_rules.py` reports WE1-WE3 under their WE names in both modes and adds N2, N3, N4, N7, N8 with `--nelson`.

## False alarms

| Rules applied | In-control false-alarm probability per point | Average run length (ARL0) |
|---------------|-----------------------------------------------|---------------------------|
| WE1 only | 0.27% | ~370 |
| WE1-WE4 together | ~1.1% | ~92 |
| All eight Nelson rules | ~1.5-2% | ~50-65 |

More rules detect small shifts sooner but raise false alarms. Practical choice:
- **Phase I** (establishing limits): all rules, to find every special cause.
- **Phase II** on a stable process: WE1-WE4; add the trend rule where wear is expected.
- **Range / S charts:** use WE1 and runs above the centre only; zone rules assume symmetry the R distribution lacks.
- **Attribute charts with small n p-bar:** WE1 and same-side runs; zone rules are unreliable.

## Prerequisites

Rules assume independent, roughly normal plotted values and limits from a stable baseline. Autocorrelated data
(chemical processes, continuous sensors) trigger runs constantly: subgroup less often, chart residuals, or use
EWMA/CUSUM.
