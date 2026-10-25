---
name: survival-analysis-model-builder
description: "Build time-to-event (survival) models that handle censoring correctly: Kaplan-Meier curves with Greenwood log-log confidence intervals, median survival with CIs, survival at chosen times, restricted mean survival time and the log-rank test; Cox proportional hazards with Efron ties, hazard ratios, concordance and the Grambsch-Therneau proportional-hazards test; and a generated comparison of penalised Cox, Weibull AFT, random survival forest and gradient-boosted survival models with Harrell's and Uno's C, time-dependent AUC, integrated Brier score and calibration. Covers churn, customer lifetime, equipment failure, credit default timing and clinical endpoints, censoring pitfalls, crossing curves, competing risks and time-varying covariates. Use when someone asks how long until an event happens, wants survival curves, hazard ratios or a churn-timing model, or has data where many subjects have not yet had the event."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Survival Analysis Model Builder

When the question is **when** an event happens (churn, failure, default, death, conversion) and some
subjects have not had it yet, ordinary classification and regression are wrong. Dropping the censored
subjects biases toward short times, treating them as "no event" biases toward long ones, and regressing
on observed durations ignores who is still at risk. Survival analysis uses everyone for as long as they
were observed.
- `scripts/km_report.py` describes the curves and compares groups
- `scripts/cox_fit.py` fits and checks a Cox model with no dependencies
- `scripts/gen_survival_script.py` compares Cox, Weibull AFT, random survival forest and gradient boosting
  with survival metrics

## Trigger Conditions

Activate this skill when the user:
- Asks how long until customers churn, machines fail, loans default or patients have an event
- Has durations where some subjects are still active / alive / working (censored)
- Wants survival curves, median time-to-event, hazard ratios, or a comparison of groups over time
- Builds a churn or lifetime model and is unsure how to handle customers who have not churned

If the question is only "will it happen within 30 days?" and everyone has been observed for 30 days, a
classifier with a clear label window works too. See [ml-problem-framing-advisor](../ml-problem-framing-advisor/SKILL.md).

## Workflow

```
1. DATA      -> one row per subject: duration (start -> event or censoring), event (1/0), covariates at start
2. DESCRIBE  -> python scripts/km_report.py data.csv --duration-col t --event-col e --group plan --at 90 180 365
3. COX       -> python scripts/cox_fit.py data.csv --duration-col t --event-col e --covariates plan age
4. CHECK     -> PH test per covariate; crossing curves; events per covariate; censoring pattern
5. COMPARE   -> python scripts/gen_survival_script.py --data data.csv --duration-col t --event-col e --covariates plan age -o surv.py
6. REPORT    -> curves, medians/RMST, hazard ratios with CIs, model comparison, assumptions
```

## Getting the Data Right

| Item | Rule |
|------|------|
| Time origin | the same meaningful start for everyone: signup, installation, diagnosis, loan origination |
| Duration | from origin to the event, or to the last time the subject was observed event-free (censoring) |
| Event | 1 if the event was observed, 0 if censored; one event type per model (see competing risks) |
| Covariates | known at the origin (baseline). Time-varying values need a counting-process (start, stop] format |
| Administrative censoring | everyone still active at the data cut-off is censored at the cut-off date |
| Left truncation | subjects who enter observation late (e.g. customers acquired before the data start) need entry times |

Censoring must be **non-informative**: being censored must not depend on the risk of the event. Customers who
cancel by switching to another plan, or patients withdrawn because they got worse, violate it. Details,
pitfalls and the long format: [survival-data.md](references/survival-data.md).

## Choosing the Model

| Need | Model |
|------|-------|
| Describe and compare groups | Kaplan-Meier + log-rank; RMST difference |
| Interpretable effects (hazard ratios) | Cox PH (`cox_fit.py`); penalised when covariates are many |
| Predict survival time directly, extrapolate | parametric AFT (Weibull, log-normal, log-logistic) |
| Non-linear effects and interactions, non-PH | random survival forest, gradient-boosted survival |
| Several event types (churn vs downgrade) | competing risks: cause-specific Cox, Fine-Gray, Aalen-Johansen |
| Covariates that change over time | time-varying Cox (lifelines `CoxTimeVaryingFitter`) |
| Discrete time (monthly) and many rows | discrete-time hazard: logistic regression on person-period data |

On the fixture with a proportional effect, penalised Cox had the best integrated Brier score (0.172). On the
fixture with crossing hazards (surgery: early risk, later benefit), the random survival forest won and the
script flagged the PH violation. Model guide with code: [survival-models.md](references/survival-models.md).

## Assumptions and Diagnostics

| Check | Tool | If it fails |
|-------|------|-------------|
| Proportional hazards | `cox_fit.py` PH p per covariate (Grambsch-Therneau, rank time) | stratify, add covariate x time, or use RMST / time-specific effects |
| Crossing survival curves | `km_report.py` warning | a single hazard ratio misleads; report RMST and S(t) at key times |
| Enough events | >= 10 events per covariate | penalise (`--penalizer`), fewer covariates |
| Heavy censoring | `km_report.py` (> 70%) | the late curve is uncertain; report earlier time points |
| Linear covariate effects | martingale residual plots, splines | transform or bin the covariate |
| Influential subjects | dfbeta | check for data errors |

`cox_fit.py` and `km_report.py` reproduce lifelines exactly on the fixtures (coefficients, standard errors,
log-likelihood, concordance, PH p-values, Kaplan-Meier CIs, medians, RMST and the log-rank statistic).

## Evaluation

| Metric | Measures | Note |
|--------|----------|------|
| Harrell's C | ranking of risk vs observed order | depends on the censoring distribution |
| Uno's C (IPCW, truncated at tau) | ranking, censoring-adjusted | preferred for comparing models |
| Time-dependent AUC at t | who has the event by t vs who survives past t | report at decision-relevant times |
| Integrated Brier score | calibration + discrimination of S(t) over time | 0 is perfect; around 0.25 is uninformative |
| Calibration at t | predicted S(t) vs Kaplan-Meier observed by risk group | needed when probabilities drive decisions |

Never evaluate with accuracy or RMSE on observed durations. Metric details: [survival-evaluation.md](references/survival-evaluation.md).

## Output Format

When delivering a survival analysis, provide:
1. **Data definition** - origin, event, censoring rule, follow-up, number of events.
2. **Descriptive curves** - KM by group with CIs, median survival or "not reached", S(t) at key times, RMST.
3. **Model** - hazard ratios with 95% CIs (or AFT time ratios), concordance, PH diagnostics.
4. **Prediction comparison** - Uno's C, time-dependent AUC, integrated Brier score and calibration per model.
5. **Caveats** - censoring assumptions, PH violations, extrapolation beyond follow-up.

## Scripts

```bash
python scripts/km_report.py survival.csv --duration-col duration_days --event-col event --group plan --at 90 180 365
python scripts/km_report.py data.csv --duration-col t --event-col died --group arm --tau 365 --json
```
Exit codes: 0 reported, 2 usage or read error.

```bash
python scripts/cox_fit.py survival.csv --duration-col duration_days --event-col event --covariates plan age
python scripts/cox_fit.py data.csv --duration-col t --event-col died --covariates age stage --penalizer 0.1 --json
```
Categorical covariates are one-hot encoded against the first sorted level. Exit codes: 0 fitted and PH holds,
1 PH violated, 2 usage error or no convergence.

```bash
python scripts/gen_survival_script.py --data survival.csv --duration-col duration_days --event-col event --covariates plan age -o surv.py
python scripts/gen_survival_script.py --data data.csv --duration-col t --event-col churn --covariates plan --time-col signup_date --times 90 180
```
Exit codes: 0 written, 2 usage error. `scripts/_surv_io.py` holds the shared loading and chi-square /
normal tail functions.

## Additional Resources

| File | Content |
|------|---------|
| [survival-data.md](references/survival-data.md) | origins, censoring types, informative censoring, truncation, long format, data checks |
| [survival-models.md](references/survival-models.md) | Kaplan-Meier, Cox, AFT, RSF, boosting, competing risks, time-varying covariates, discrete time |
| [survival-evaluation.md](references/survival-evaluation.md) | concordance, time-dependent AUC, Brier score, calibration, RMST, reporting |
