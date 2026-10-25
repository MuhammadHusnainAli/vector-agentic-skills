# Reading PDP and ICE

## Shapes

| Shape | Reading | Follow-up |
|-------|---------|-----------|
| Monotonic, smooth | steady response | candidate for a monotonic constraint |
| Step / threshold | the model splits near a value (trees) | check the threshold against domain knowledge (policy limits, pricing tiers) |
| U or inverted U | optimum in the middle | confirm with data support at both ends |
| Flat PDP, wide ICE fan | opposite effects cancel | find the separator: an interaction |
| Flat PDP, flat ICE | no effect in this range | consistent with low permutation importance |
| Saw-tooth | overfitting to noise in the feature | regularise; smooth with ALE to compare |
| Jump at the tails | extrapolation or rare outliers | ignore outside the rug; cap the feature |

## Heterogeneity

`ice_analysis.py` distinguishes:
- **Opposite effects**: some rows go up while others go down. Classic example: a discount raises conversion
  for price-sensitive customers and has no or a negative effect for loyal ones. The PDP may look flat.
- **Subgroups of different strength**: everyone moves the same way, by clearly different amounts. Fixture
  example: 20 customers lose 0.49 probability over the tenure range, while 10 on monthly contracts lose only
  0.16. The separator `contract_monthly` (AUC 1.00) names the interaction.

After a separator is found, plot ICE coloured by it, or draw a two-way PDP (`--pair`). Confirm with SHAP
interaction values for tree models.

## Support

PDP values at grid points with no nearby data are model extrapolation. Always draw a rug (the generated
plot does). `ice_analysis.py --features` flags grid points outside the 5th-95th percentile. Correlated
features shrink the realistic region further: a PDP over tenure at a fixed monthly-charge combination
may never occur, and ALE avoids that.

## Misreadings

| Misreading | Correct |
|------------|---------|
| "Raising X by 10 lowers churn by 5 points" | the model's prediction changes; it says nothing about intervening on X |
| Reading the PDP where the rug is empty | no data there: extrapolation |
| PDP of a feature correlated with others | averages over impossible rows: prefer ALE |
| Uncentred ICE "all parallel" | level differences hide shape; centre the curves |
| Ignoring the response scale | probability effects are not additive; log-odds are |
| Comparing PDP magnitudes across models | depends on each model's calibration; compare on the same scale |

## Worked fixture example

```
$ python ice_analysis.py ice_tenure.csv --features ice_rows.csv
PDP decreases by 0.3805 over the grid (range 0.3805); 100% of steps go the same way
centred ICE: 0 up, 30 down, 0 flat; end-point spread sd 0.1561 (0.41 x the PDP range)
SUBGROUPS: two groups of curves with different strength: 20 rows change by -0.4885, 10 rows by -0.1645
  separator: contract_monthly (AUC 1.00: the -0.1645 group has higher contract_monthly)
WARNING: 4 grid value(s) outside the 5th-95th percentile [3, 46.65]: the curve there is extrapolation
```
Reading: longer tenure lowers predicted churn for everyone, but much less for monthly-contract customers.
Report the two groups separately, and do not read the curve beyond about 47 months.
