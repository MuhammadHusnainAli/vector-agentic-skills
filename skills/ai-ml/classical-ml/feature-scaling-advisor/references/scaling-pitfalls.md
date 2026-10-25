# Scaling Pitfalls

| Pitfall | What goes wrong | Fix |
|---------|-----------------|-----|
| `scaler.fit(X)` on all data before the split | test statistics leak into training; optimistic CV | fit inside a Pipeline; cross-validate the Pipeline |
| Scaling before `train_test_split` in a notebook | same leak, very common | split first, or use a Pipeline |
| Separate scalers for train and test (`fit_transform` on both) | test is scaled by its own statistics: features shift | `fit` on train, `transform` test |
| Time series scaled with future data | look-ahead leakage | fit on the training window; refit at retrain |
| `MinMaxScaler` at serving time sees values outside the training range | outputs < 0 or > 1; NN saturation | `clip=True`, or robust/standard scaling |
| Quantile transform with few rows | jagged mapping; `n_quantiles` > n warning | `n_quantiles=min(1000, n_rows)` |
| Box-Cox on zeros/negatives | ValueError | Yeo-Johnson or log1p |
| Scaling binary / one-hot columns for trees | harmless but pointless | passthrough |
| Interpreting standardised coefficients as raw effects | wrong units in reports | report per-SD effects or back-transform |
| Re-fitting the scaler on each prediction batch | inconsistent features between batches | persist the fitted scaler with the model |
| Different preprocessing in training and serving code | train/serve skew | one serialised Pipeline used in both |
| Scaling the target for a tree model and forgetting to invert | predictions in the wrong units | `TransformedTargetRegressor` |
| Scaling IDs or codes | meaningless distances | drop IDs; encode codes as categories |
| Sentinel values (−999) scaled as numbers | distorts mean/std | convert to NaN + indicator first |

## Leakage size: when it matters

Standard scaling leaks only the mean and variance of the test fold: the effect on CV scores is usually small
for large datasets. It becomes material when:
- datasets are small (hundreds of rows);
- the transform is flexible (quantile, power with fitted λ, target-dependent steps);
- the test distribution differs from training (time drift), so the leak smuggles in shift information.

Because the fix (a Pipeline) costs nothing, always use it.

## Serving checklist

- [ ] The fitted Pipeline (scalers included) is serialised and versioned with the model.
- [ ] Input columns and order are validated at serving time (`feature_names_in_`).
- [ ] Out-of-range behaviour is defined (clip, or robust scaling).
- [ ] Drift monitoring compares serving feature distributions with the training statistics stored in the
      scaler (`mean_`, `scale_`, `quantiles_`).
