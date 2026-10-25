# Uplift Learners

Notation: X covariates, T in {0, 1} treatment, Y outcome, tau(x) = E[Y | X=x, T=1] - E[Y | X=x, T=0].

## Meta-learners (Kunzel et al. 2019)

| Learner | Estimate |
|---------|----------|
| S | fit mu(x, t); tau(x) = mu(x, 1) - mu(x, 0) |
| T | fit mu1 on treated and mu0 on control; tau = mu1 - mu0 |
| X | T-learner first; D1 = Y - mu0(X) on treated, D0 = mu1(X) - Y on control; fit g1(D1 ~ X), g0(D0 ~ X); tau = e(x) g0(x) + (1 - e(x)) g1(x) |
| R (Nie & Wager) | residualise Y and T on X (cross-fitted), regress the residual products; robust to confounding |
| DR | doubly robust pseudo-outcome mu1 - mu0 + T(Y - mu1)/e - (1 - T)(Y - mu0)/(1 - e), regressed on X |

The S-learner's flaw is easy to see on the fixture. A logistic S-learner without treatment x covariate
interactions gives the same effect sign for everyone, so 0% are predicted negative and it cannot find
sleeping dogs. Trees can split on t, but often do not when the effect is small.

## Class transformation (Jaszewska & Lambert 2012)

`Z = T Y + (1 - T)(1 - Y)`. With P(T=1) = 0.5, `tau(x) = 2 P(Z=1 | x) - 1`. For other assignment shares,
reweight rows to 50/50 (as the generated script does). Binary outcomes only. Variants: Athey and Imbens'
transformed outcome Y* = Y (T - p) / (p (1 - p)) for continuous outcomes.

## Tree-based

- Uplift trees and random forests with split criteria on the treatment-control difference (KL, Euclidean,
  chi-square, DDP): causalml `UpliftTreeClassifier`, `UpliftRandomForestClassifier`.
- Causal forests (Wager & Athey 2018): honest splitting, valid confidence intervals; `grf` (R), econml
  `CausalForestDML`.

## Libraries

```python
# scikit-uplift
from sklift.models import SoloModel, TwoModels, ClassTransformation
from sklift.metrics import qini_auc_score, uplift_auc_score, uplift_at_k
tm = TwoModels(estimator_trmnt=LGBMClassifier(), estimator_ctrl=LGBMClassifier(), method="vanilla")
tm.fit(X_tr, y_tr, t_tr); uplift = tm.predict(X_te)

# causalml
from causalml.inference.meta import BaseXClassifier
x = BaseXClassifier(outcome_learner=LGBMClassifier(), effect_learner=LGBMRegressor())
tau = x.fit_predict(X, treatment=t, y=y, p=propensity)

# econml
from econml.dr import DRLearner
dr = DRLearner(model_propensity=LogisticRegression(), model_regression=LGBMRegressor(), model_final=LGBMRegressor())
dr.fit(y, t, X=X); tau = dr.effect(X_te)
```

## Practical guidance

- Use small, regularised base models (few leaves, large `min_child_samples`): uplift signals are weak.
- Use the same covariates for every learner and the same holdout for every comparison.
- Ensembles (averaging T, X and class transformation scores) are often more stable than any single learner.
- Multiple treatments (several offers): fit per-treatment uplift against control and pick the best
  treatment per person, minus its cost.
