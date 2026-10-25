# Value and Cost Models

Always compare the model to the current process (the baseline), at the action's capacity.

## Generic top-K value model

```
K                 = cases acted on per period (capacity)
prec@K            = share of acted cases that are true positives
v_tp              = value of acting on a true positive (net of action effect: saves x value)
c_fp              = cost of acting on a false positive
c_action          = cost of the action itself (call, review)
value(model)      = K * (prec@K * v_tp - (1 - prec@K) * c_fp - c_action)
lift              = value(model) - value(baseline)
ceiling           = value at prec@K = min(1, positives_per_period / K)
break-even prec@K = (c_action + c_fp + run_cost/K) / (v_tp + c_fp)
```

## Churn retention

| Input | Value |
|-------|-------|
| Capacity | 400 calls/week |
| Churners per week | 300 (out of 50,000 active) |
| Save rate when a churner is called | 30% |
| Customer value if saved | $600 |
| Call cost | $8 |
| Baseline prec@400 | 0.25 |
| Model prec@400 | 0.40 |

Saves: baseline 400 x 0.25 x 0.30 = 30/week; model 48/week. Lift 18 x $600 = $10,800/week. Call cost is the
same in both. Ceiling: prec@400 = 300/400 = 0.75 -> 90 saves/week, so a perfect model adds at most $36k/week
over baseline.

Caveat: if calling also annoys non-churners (c_fp > 0) or the save rate differs by segment, use uplift: the
value comes from persuadable customers, not from churners in general.

## Fraud at authorisation

| Input | Value |
|-------|-------|
| Transactions/day | 2,000,000 |
| Fraud rate | 0.1% (2,000/day), average $150 |
| Decline cost (false positive) | lost margin $3 + friction; customer churn risk |
| Review capacity | 2,000 cases/day |

Report fraud dollars caught at a fixed false-decline rate (e.g. 0.2% of good transactions), not AUC.
Value = fraud $ prevented - (false declines x cost per false decline) - review cost. Because fraud amounts
vary, rank by expected loss (`p_fraud x amount`) and measure value-weighted recall.

## Demand forecasting

Value comes from inventory: lower safety stock for the same service level, fewer stock-outs, less waste.

```
safety_stock ~ z_service * sigma_forecast_error * sqrt(lead_time)
holding_saving = (sigma_old - sigma_new) * z * sqrt(L) * unit_cost * holding_rate
```

A 10% reduction in forecast error standard deviation reduces safety stock by ~10%. Measure error at the
decision's aggregation (store-SKU-week), weighted by margin or volume.

## Lead scoring

```
value = (opportunities from top-K leads under model - under baseline order) x win rate x deal value
```
Measure on leads that were actually worked; beware that reps already prioritise (selection bias): run an A/B
on queue order.

## Cost of errors table

Write this table with the business owner; it becomes the threshold choice later.

| Outcome | Business effect | Cost estimate |
|---------|-----------------|---------------|
| True positive | action prevents loss | +$ value saved |
| False positive | action wasted, possible harm | -$ action cost - friction |
| False negative | loss not prevented | -$ loss (relative to perfect) |
| True negative | nothing | 0 |

The optimal threshold for a calibrated probability p is to act when `p * v_tp > (1 - p) * c_fp + c_action`,
i.e. `p > (c_fp + c_action) / (v_tp + c_fp)`; with a capacity, take the top K instead.

## Build and run cost

| Item | Typical size |
|------|--------------|
| Data engineering for features and labels | often 50-70% of the effort |
| Modelling and validation | 10-20% |
| Serving, monitoring, retraining | 20-30%, recurring |
| Human review / action cost | per prediction, recurring |

A project is feasible when the expected lift over its first year exceeds build plus run cost with margin for
the uncertainty in the lift estimate (use the lower end of the metric CI).
