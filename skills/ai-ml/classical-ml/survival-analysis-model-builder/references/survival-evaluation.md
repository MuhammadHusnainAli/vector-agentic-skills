# Survival Evaluation

## Concordance

- **Harrell's C**: among comparable pairs (the shorter time had an event), the share where the subject with
  the shorter time had the higher risk score. Ties in risk count half. 0.5 is random and 1 is perfect.
  It depends on the censoring distribution and becomes optimistic under heavy censoring.
- **Uno's C**: inverse-probability-of-censoring weighted and truncated at tau. Use it to compare models
  (`sksurv.metrics.concordance_index_ipcw`).

Concordance only measures ranking. A model can rank perfectly and still be badly calibrated.

## Time-dependent AUC

The cumulative/dynamic AUC at time t separates subjects with an event by t from those still event-free at t
(`sksurv.metrics.cumulative_dynamic_auc`). Report it at the decision horizons: 30/90/365 days for churn
campaigns, the warranty period for failures.

## Brier score and integrated Brier score

`BS(t) = mean over subjects of (1{T_i > t} - S_hat(t | x_i))^2`, IPCW-weighted for censoring. The integrated
Brier score (IBS) averages it over a time range. Benchmarks: the Kaplan-Meier curve (no covariates) gives
the "null" IBS. A useful model is clearly below it, and values around 0.25 mean no information when S is
near 0.5.

## Calibration

At a decision time t, group the test subjects by predicted S(t) (quintiles or deciles) and compare the mean
prediction with the Kaplan-Meier estimate in each group. The generated script reports the largest gap.
Penalised Cox and AFT models are often calibrated better than forests.

## RMST

Restricted mean survival time up to tau is the area under S(t) on [0, tau]: the average event-free time
within the horizon. The RMST difference between groups ("premium customers stay 155 days longer on
average within the first 700 days") is valid without proportional hazards, which makes it the preferred
summary when curves cross.

## Protocol

- Hold out a test set stratified on the event, or out-of-time (later cohorts) to mimic deployment.
- Evaluation times must lie inside the test follow-up (IPCW metrics need it). The generated script restricts
  them automatically.
- Compare against the Kaplan-Meier null model and a simple Cox model before trusting complex ones.
- Report uncertainty: bootstrap the test set for C and IBS when models are close.

## Reporting template

| Model | Harrell's C | Uno's C | AUC@90 | AUC@365 | IBS | Max calibration gap @180 |
|-------|-------------|---------|--------|---------|-----|--------------------------|
