# Counterfactual Methods

## Exact solution for linear scores

For a score `z = b + sum_j w_j x_j` (logistic: probability = sigmoid(z)), reaching a target `z*` from `z0`
needs a score change `need = |z* - z0|` in one direction. With cost `sum_j |delta_j| / s_j x c_j`:

```
minimise   sum_j |delta_j| x c_j / s_j
subject to sum_j w_j delta_j moves z by `need` in the wanted direction
           delta_j within [lo_j, hi_j] (immutability, direction, bounds)
```
This is a fractional knapsack. Use features in decreasing order of efficiency `|w_j| x s_j / c_j` (score
change per unit cost) until the need is covered. This is optimal for continuous features.
`linear_counterfactual.py` adds:
- exhaustive search over binary features (2^b subsets, small b)
- floor/ceil branching for integer features (exact; checked against brute force)
- alternatives: the best solution with each used feature excluded, and single-feature solutions
- essential features: excluding them leaves no feasible solution
- NO RECOURSE: the best reachable score when even every allowed move is not enough

L1 cost gives sparse answers that change few features. L2 cost spreads small changes over many features,
which is harder to act on.

## Wachter et al. (2017)

```
argmin_x'  lambda x (f(x') - y*)^2 + d(x, x')     (d = MAD-weighted L1)
```
Gradient-based. It needs a differentiable model, and constraints come through projection.
`alibi.explainers.Counterfactual` implements it.

## DiCE (Mothilal et al. 2020)

Generates several counterfactuals that trade off proximity, diversity (a determinantal point process term)
and sparsity.

```python
import dice_ml
data = dice_ml.Data(dataframe=train, continuous_features=cont, outcome_name="churned")
model = dice_ml.Model(model=pipe, backend="sklearn", model_type="classifier")
exp = dice_ml.Dice(data, model, method="random")          # "genetic", "kdtree"
cf = exp.generate_counterfactuals(query, total_CFs=4, desired_class="opposite",
                                  features_to_vary=[...], permitted_range={"monthly_charges": [20, 84.15]},
                                  random_seed=0)          # random_seed: method="random" only (verified on dice-ml 0.12)
cf.cf_examples_list[0].final_cfs_df
```
| method | Behaviour |
|--------|-----------|
| random | random sampling over the features to vary: fast and diverse, not minimal |
| genetic | evolutionary search with proximity/sparsity terms: closer, slower |
| kdtree | nearest training rows of the desired class: plausible by construction, may change many features |

DiCE has no direction constraints. Express them as per-row `permitted_range` (`gen_dice_script.py` does).
Categoricals are strings inside DiCE, so wrap the model to restore dtypes. Re-predict every result.

## Prototype-guided (Van Looveren and Klaise 2021)

`alibi.explainers.CounterfactualProto` pulls the counterfactual towards a class prototype (autoencoder or
k-d tree), which improves plausibility and is faster for complex models.

## MILP / actionable recourse (Ustun, Spangher and Liu 2019)

Exact recourse for linear models (and, with encodings, tree ensembles) with rich constraints. It can
**audit** a population: the share of rejected people with no recourse, per group. Package: `recourse`
(actionable-recourse).

## Choosing

| Need | Method |
|------|--------|
| Logistic scorecard, exact and explainable | linear solver / MILP |
| Any sklearn model, several options quickly | DiCE random, then validate |
| Plausibility over minimality | DiCE kdtree or prototypes |
| Audit recourse fairness across many rows | linear solver / MILP in a loop, per-group statistics |
| Tree ensembles, exact | MILP encodings (e.g. FOCUS, FACE, or `recourse` with tree support) |
