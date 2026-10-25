# Actionability and Constraints

## Classify every feature

| Class | Examples | Spec |
|-------|----------|------|
| Immutable | age, birthplace, past events, tenure so far, protected attributes and their proxies | `"mutable": false` |
| Mutable, one direction | education (up), account age (up), number of late payments in the future window (down) | `"direction": "increase"` / `"decrease"` |
| Mutable, bounded | utilisation 0-100%, price >= floor | `"min"`, `"max"` |
| Discrete | counts, ratings | `"integer": true` |
| Binary choice | autopay, plan upgrade | `"binary": true` |
| Costly | income, relocation | `"cost_multiplier": 3` |
| Derived | totals, ratios, aggregates | recompute from inputs, or validate with `--relation` |

Rule of thumb: if the person cannot change it within the decision horizon, it is immutable for recourse.
It can still be a legitimate model input.

## Cost scale

- **MAD** (median absolute deviation) is robust to outliers and makes a unit change "typical" (Wachter et al.
  2017).
- Use `std` when the MAD is 0 (binary or very skewed features). `cf_validate.py` falls back the same way.
- Domain costs override statistics: changing income by 10% is much harder than closing one card.
- The percentile shift (cost = change in the feature's CDF; Ustun et al. 2019) is a good alternative: moving
  from the 50th to the 60th percentile costs the same on every feature.

## Derived features and causal structure

Counterfactual search treats features as independent knobs. In reality:
- `total_charges = tenure x monthly_charges`: changing the total alone is meaningless (`--relation`).
- Increasing education raises age (time passes) and can change income.
- Paying down debt changes utilisation and the debt-to-income ratio together.

Options:
1. Model only root causes as mutable and recompute derived features before predicting (custom search).
2. Mark derived features immutable and let the search change their inputs.
3. Validate with relations and reject inconsistent counterfactuals.
4. Use causal recourse methods (Karimi et al. 2021) when a structural causal model exists.

## Constraint file (shared by all three scripts)

```json
{"features": {
  "tenure_months":   {"mutable": false, "scale": 14.5},
  "support_calls":   {"direction": "decrease", "min": 0, "integer": true, "scale": 1.0},
  "last_login_days": {"direction": "decrease", "min": 0, "integer": true, "scale": 6.0},
  "monthly_charges": {"direction": "decrease", "min": 20, "max": 120, "scale": 14.0, "cost_multiplier": 2.0},
  "plan_basic":      {"binary": true, "scale": 1.0}
}}
```
`linear_counterfactual.py` needs `intercept` and `coefficients` in the same file. `gen_dice_script.py` and
`cf_validate.py` read only the `features` block.

## Common mistakes

| Mistake | Consequence |
|---------|-------------|
| No immutability | "become younger", "change your region" |
| No direction | "increase your past late payments to lower churn" (a sign quirk of the model) |
| No bounds | negative counts, utilisation above 100% |
| Continuous treatment of counts | "2.37 support calls" |
| Ignoring derived features | flips achieved by inconsistent values (seen with DiCE on the churn fixture) |
| One counterfactual only | the single option may be impossible for this person |
