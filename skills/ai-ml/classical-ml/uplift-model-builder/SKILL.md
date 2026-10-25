---
name: uplift-model-builder
description: "Build uplift (incremental response, heterogeneous treatment effect) models that target the people a campaign, offer or intervention actually changes: validate the randomised experiment (sample-ratio mismatch, covariate balance by standardised mean difference, average treatment effect with confidence interval and minimum detectable effect, segment effects with a heterogeneity test), train S-, T- and X-learners and the class-transformation approach, and evaluate on a holdout with Qini coefficient and AUUC (matching scikit-uplift), uplift by decile with confidence intervals, sleeping-dog detection and the inverse-propensity-weighted value and profit of treating the top fraction. Covers persuadables, sure things and sleeping dogs, observational data, causal forests and rollout. Use when someone wants to target a marketing campaign, discount, retention offer or nudge by incremental effect, asks about uplift or CATE models, Qini curves, or who to treat."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Uplift Model Builder

A response model predicts who will convert. An uplift model predicts who will convert **because** they
were treated. The two lists differ:
- **persuadables** respond only when treated; target them
- **sure things** respond anyway; the treatment is wasted on them
- **lost causes** never respond
- **sleeping dogs** respond less when treated; the treatment does harm

Targeting by response probability spends budget on sure things and can wake the sleeping dogs. Uplift
modelling needs randomised data (or known propensities) and its own evaluation:
- `scripts/rct_check.py` validates the experiment
- `scripts/gen_uplift_script.py` trains the meta-learners
- `scripts/uplift_eval.py` measures Qini, AUUC, deciles and the value of targeting

## Trigger Conditions

Activate this skill when the user:
- Wants to target a campaign, discount, retention offer, notification or treatment by incremental effect
- Asks about uplift models, CATE, heterogeneous treatment effects, meta-learners or Qini / AUUC
- Has an A/B test and wants to know who benefited, or who was hurt
- Targets "high propensity" customers and sees little incremental lift

A/B test design and analysis of the average effect: [ml-success-metric-selector](../ml-success-metric-selector/SKILL.md)
for metric choice. Churn timing: [survival-analysis-model-builder](../survival-analysis-model-builder/SKILL.md).

## Workflow

```
1. DATA      -> a randomised test (or logged propensities); treatment, outcome, pre-treatment covariates only
2. CHECK     -> python scripts/rct_check.py data.csv --treatment-col treatment --outcome-col converted --covariates age segment --segments segment
3. MODEL     -> python scripts/gen_uplift_script.py --data data.csv --covariates age segment -o uplift.py; python uplift.py
4. EVALUATE  -> python scripts/uplift_eval.py holdout_scores.csv --scores s_learner t_learner x_learner class_transform --cost-per-treatment 0.5 --value-per-outcome 20
5. DECIDE    -> treat the fraction with the best profit; exclude sleeping dogs; confirm with a new randomised rollout
```

## Before Modelling: Is There Anything to Model?

| Check | rct_check.py | If it fails |
|-------|--------------|-------------|
| Randomisation worked | sample-ratio mismatch test (p < 0.001 = broken) | stop: fix assignment or logging |
| Groups comparable | SMD per covariate (abs value > 0.1 = imbalance) | investigate; adjust or re-randomise |
| Average effect | ATE with CI, relative lift, MDE | a null ATE can still hide opposite segment effects |
| Effects differ | per-segment effects and Cochran's Q | no heterogeneity: treat everyone or no-one, no uplift model needed |

Fixture (randomised, 2,000 people): ATE +3.2 points [+0.3, +6.1]. The segments diverge: A +13.2, B +2.1
and C −4.4 (Q = 21.5, p = 2e-5). These recover the planted effects (A +10, B +2, C −3). The numbers match
scipy (SRM p, SMD). Covariates must be measured **before** treatment. Post-treatment variables (clicks on
the offer) are not covariates. Design and data rules: [uplift-data-and-design.md](references/uplift-data-and-design.md).

## Learners

| Learner | Idea | Strength | Weakness |
|---------|------|----------|----------|
| S-learner | one model with t as a feature | simple, data-efficient | can shrink effects to zero; a linear model without interactions gives one effect for everyone |
| T-learner | separate treated and control models | flexible | noisy when one arm is small; differences of two errors |
| X-learner | impute individual effects, regress them, weight by propensity | good with unbalanced arms | more stages |
| Class transformation | z = 1 for (treated, converted) or (control, not converted) | one classifier | binary outcomes; needs 50/50 or reweighting |
| Causal forest / DR-learner | honest splitting / doubly robust pseudo-outcomes | valid inference, observational data | econml / grf; more tuning |

Fixture holdout (800 people), Qini coefficient: class transformation 0.214, T-learner 0.179, X-learner 0.174
and S-learner 0.070 with logistic bases. With LightGBM bases: S 0.170, X 0.143, T 0.115, class transform 0.104.
No learner wins everywhere, so compare them on the same holdout. Formulas and libraries:
[uplift-learners.md](references/uplift-learners.md).

## Evaluation

| Measure | Meaning |
|---------|---------|
| Qini coefficient | area between the Qini curve and random targeting, normalised by the perfect curve (1 perfect, 0 random) |
| AUUC | the same for the uplift curve |
| Uplift by decile | treated minus control rate per score decile with CI; should fall from top to bottom |
| Sleeping dogs | deciles with a significantly negative uplift: exclude them |
| Targeting value | IPW estimate of the outcome when treating the top q%, against treat-all and treat-none |
| Profit | value x outcomes - cost x treated, per person |

`uplift_eval.py` matches scikit-uplift's `qini_auc_score` and `uplift_auc_score` exactly (fixture: 0.1768 and
0.0785). On the fixture's provided score, the bottom decile is a significant sleeping-dog group (−10.1
points). Treating the top 30% earns +2.86 per person, against +2.31 for treating everyone.

Individual effects are never observed, so uplift can only be evaluated on randomised holdout data through
these group comparisons. Evaluation details: [uplift-evaluation.md](references/uplift-evaluation.md).

## Output Format

When building an uplift model, deliver:
1. **Experiment check** - SRM, balance, ATE with CI, segment effects and heterogeneity.
2. **Models** - learners, base models, covariates (pre-treatment only).
3. **Holdout evaluation** - Qini/AUUC per learner, the decile table with CIs, sleeping dogs.
4. **Targeting decision** - fraction to treat, expected incremental outcomes and profit against treat-all.
5. **Rollout plan** - a randomised validation of the targeting policy with a holdout control.

## Scripts

```bash
python scripts/rct_check.py uplift.csv --treatment-col treatment --outcome-col converted --covariates age segment --segments segment
python scripts/rct_check.py exp.csv --treatment-col variant --outcome-col revenue --expected-share 0.2 --json
```
Exit codes: 0 checks passed, 1 sample-ratio mismatch or imbalance, 2 usage error.

```bash
python scripts/gen_uplift_script.py --data uplift.csv --covariates age segment -o uplift.py
python scripts/gen_uplift_script.py --data exp.csv --covariates age plan region --learners t_learner x_learner --base logreg
```
Writes `holdout_scores.csv` and `uplift_models.joblib`. Exit codes: 0 written, 2 usage error.

```bash
python scripts/uplift_eval.py holdout_scores.csv --scores t_learner x_learner --cost-per-treatment 0.5 --value-per-outcome 20
python scripts/uplift_eval.py preds.csv --scores model --propensity-col p_treat --target-fracs 0.1 0.2 0.5 --json
```
Exit codes: 0 evaluated, 2 usage or read error. `scripts/_uplift_io.py` holds the shared parsing and
chi-square functions.

## Additional Resources

| File | Content |
|------|---------|
| [uplift-data-and-design.md](references/uplift-data-and-design.md) | the four customer types, experiment design for uplift, covariates, observational data, sample size |
| [uplift-learners.md](references/uplift-learners.md) | S/T/X/R/DR learners, class transformation, uplift trees and causal forests, libraries |
| [uplift-evaluation.md](references/uplift-evaluation.md) | Qini and uplift curves, normalisation, deciles, policy value with IPW, profit, rollout |
