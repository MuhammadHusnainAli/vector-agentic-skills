# Uplift Evaluation

Individual effects are unobservable: nobody is both treated and untreated. Evaluation compares treated and
control groups **within score-ranked segments** of a randomised holdout.

## Curves (scikit-uplift conventions, reproduced by uplift_eval.py)

Sort by score, descending. At each cut-off n (distinct scores), with N_t and N_c treated / control counts and
Y_t, Y_c their outcome sums so far:

```
Qini(n)   = Y_t - Y_c * N_t / N_c                        (Y_t when N_c = 0)
Uplift(n) = (Y_t / N_t - Y_c / N_c) * n
```
- Random targeting: the straight line from (0, 0) to the curve's end point.
- Perfect curve (Qini): rank treated responders first and control responders last (allowing negative
  effects).
- Qini coefficient = (area(model) - area(random)) / (area(perfect) - area(random)). AUUC is the same for
  the uplift curve.

These values are comparable only on the same holdout data. A difference of a few hundredths is often noise,
so bootstrap the holdout to compare models.

## Decile table

The treated minus control outcome rate per score decile, with a 95% CI. A useful model shows:
- high, significant uplift at the top
- falling uplift down the deciles
- possibly a negative bottom: sleeping dogs. On the fixture the bottom decile was −10.1 points
  [−19.6, −0.6].

A flat table means the model has not learned heterogeneity, whatever its Qini value.

## Policy value

For a policy pi(x) in {0, 1} (treat the top q%), estimated on randomised data with assignment probability p
(or per-row propensities):

```
V(pi) = mean( Y * 1{T = pi(X)} / P(T = pi(X) | X) )
```
Compare it with treat-all (the treated mean) and treat-none (the control mean). Profit per person =
V x value per outcome - q x cost per treatment. `uplift_eval.py` reports both for each `--target-fracs`.
On the fixture, treating the top 30% earned +2.86 per person, against +2.31 for treating everyone and
+2.16 for no-one.

## From model to rollout

1. Choose the fraction (or a score threshold) from the profit curve on the holdout.
2. Roll out as a test: model-targeted vs random-targeted vs no treatment, randomised.
3. Measure the incremental outcome per treated person and the total profit. This validates the whole policy,
   not just the model.
4. Keep a random holdout permanently for retraining and monitoring.

## Checklist

- [ ] randomised holdout, never used in training
- [ ] Qini/AUUC for every learner on the same holdout, with bootstrap intervals for close calls
- [ ] the decile table with CIs; sleeping dogs identified
- [ ] the targeting fraction chosen by value or profit, not by Qini alone
- [ ] a randomised rollout plan with a control group
