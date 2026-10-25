---
name: counterfactual-explanation-generator
description: "Generate counterfactual explanations and algorithmic recourse: the smallest realistic change to a row's features that changes the model's decision. Solves exact minimal-cost recourse for linear and logistic models (MAD-scaled L1 cost, immutable features, increase/decrease directions, bounds, integer and binary features, diverse alternatives, features every counterfactual must change, and a no-recourse finding when immutable features decide), generates DiCE counterfactuals for any scikit-learn model with constraints turned into permitted ranges and every result re-predicted, and validates counterfactuals from any method for constraint violations, implausible values, off-manifold rows, broken derived-feature relations and failure to flip the prediction. Use when someone asks what a customer or applicant would need to change to get a different outcome, wants counterfactual or what-if explanations, recourse for adverse decisions, or DiCE."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Counterfactual Explanation Generator

A counterfactual explanation answers "what would have to be different for the model to decide
otherwise?". For example: "with 3 fewer support calls and one more recent login, the churn risk would drop
below 75%". Useful counterfactuals are **valid** (the prediction really changes), **actionable** (only
features the person can change, in directions they can change them), **sparse** (few changes),
**plausible** (they look like real data) and **diverse** (several options).
`scripts/linear_counterfactual.py` solves the problem exactly for linear and logistic models.
`scripts/gen_dice_script.py` runs DiCE for any model. `scripts/cf_validate.py` checks counterfactuals from
any method before anyone sees them.

## Trigger Conditions

Activate this skill when the user:
- Asks what an applicant, customer or patient would need to change to get a different decision
- Needs recourse for adverse decisions (credit, insurance, hiring, fraud holds) or "what-if" explanations
- Uses or evaluates DiCE, Alibi counterfactuals or a custom search
- Wants to know whether some people have no recourse (fairness review)

Attribution ("why this score?"): [shap-value-explainer](../shap-value-explainer/SKILL.md). Local surrogates:
[lime-explanation-generator](../lime-explanation-generator/SKILL.md). Model documentation:
[model-card-writer](../model-card-writer/SKILL.md).

## Workflow

```
1. CONSTRAINTS -> per feature: mutable?, direction (increase/decrease), min/max, integer/binary, cost scale
2. GENERATE    -> linear/logistic: python scripts/linear_counterfactual.py model.json row.json --target-prob 0.3
                  any model:       python scripts/gen_dice_script.py --model m.joblib --train train.csv --rows rows.csv --target y --constraints c.json -o dice.py
3. VALIDATE    -> python scripts/cf_validate.py --original row.json --cfs cfs.csv --train train.csv --constraints c.json \
                      --pred-col pred_prob --target-prob 0.5 --side below --relation "total=tenure*monthly"
4. SELECT      -> 1-3 valid, plausible, diverse options; cheapest first
5. COMMUNICATE -> plain-language options, with the caveat that model inputs are not guaranteed causes
```

## Constraints Make or Break Recourse

| Feature kind | Constraint | Example |
|--------------|------------|---------|
| Immutable | `"mutable": false` | age, tenure so far, past defaults, region of birth |
| Monotone in time | `"direction": "increase"` | age, education level, account age |
| Behaviour that can improve | `"direction": "decrease"` + `"min"` | missed payments going forward, support calls, utilisation |
| Integer counts | `"integer": true` | number of accounts, calls |
| Binary choices | `"binary": true` | plan upgrade, autopay on/off |
| Hard to change | `"cost_multiplier": 2-5` | income, monthly price |
| Derived features | `--relation "total=a*b"` in validation | total charges = tenure x monthly charges |

The cost unit is the feature's MAD (median absolute deviation), so "1" means a typical difference between
people. Without constraints, counterfactuals happily suggest "be 10 years younger" or "have negative
support calls". Constraint design and examples: [actionability-and-constraints.md](references/actionability-and-constraints.md).

## Methods

| Method | Models | Guarantees | Use |
|--------|--------|------------|-----|
| `linear_counterfactual.py` | linear, logistic (any GLM score) | exact minimal MAD-L1 cost under the constraints | scorecards, logistic credit models, linear baselines |
| DiCE random (`gen_dice_script.py`) | any classifier | diverse; not minimal | black-box models, quick options |
| DiCE genetic / kdtree | any classifier | better proximity; kdtree returns real training rows | plausibility matters |
| Alibi CFProto / Wachter | differentiable or any | gradient or prototype guided | images, neural networks |
| MILP (Ustun et al. "actionable recourse") | linear, tree ensembles | exact, with complex constraints | audits of recourse |

Verified on the fixtures:
- The linear solver matches a brute-force search exactly for four targets. Integer features are branched
  on floor and ceiling.
- DiCE random produced valid flips that cost 7.6-10.2 MAD units where the exact optimum was 5.5.
- For a LightGBM churn model, DiCE "flipped" a low-risk customer only by changing `total_charges` without
  changing tenure or monthly charges. `cf_validate.py --relation` rejects all three results.

Method details: [counterfactual-methods.md](references/counterfactual-methods.md).

## Validation Before Showing Anyone

| Check | cf_validate.py | Why |
|-------|----------------|-----|
| prediction really changes | `--pred-col` + `--target-prob` + `--side` | some generators return near-misses |
| immutable / direction / bounds / integer | violations | the advice must be possible |
| unseen categories | UNSEEN | a level the model never saw |
| implausible values | outside the 1-99% training range and further out than the original | no fantasy values |
| off-manifold | nearest training row farther than max(p95 of training NN distances, the original's own) | a combination no real person has |
| derived features | RELATION | consistency between features |
| diversity | mean pairwise distance, distinct change sets | several genuinely different options |

## Communicating Recourse

- Offer options, not orders: "Any one of these would change the outcome: ...".
- Use real units and directions: "3 fewer support calls in the next quarter", not "support_calls -3".
- Say what is not guaranteed: the model can change, and other factors may matter.
- A NO RECOURSE result (immutable features decide the outcome) is a fairness finding. Report it to model
  owners, not to the customer as advice.
- Never suggest gaming the model, and never suggest changing protected attributes or their proxies.

Wording, regulation (adverse-action notices, GDPR Art. 22, the EU AI Act) and fairness of recourse:
[communicating-recourse.md](references/communicating-recourse.md).

## Output Format

When producing counterfactual explanations, deliver:
1. **Constraints** - mutable features, directions, bounds, cost scales, relations.
2. **Counterfactuals** - 1-3 validated options with the changes, cost, sparsity and new prediction.
3. **Validation** - cf_validate.py results (violations, plausibility, validity).
4. **Recourse findings** - essential features, no-recourse cases, groups with costlier recourse.
5. **Plain-language text** - what the person could change, with caveats.

## Scripts

```bash
python scripts/linear_counterfactual.py cf_logreg.json cf_row.json --target-prob 0.3
python scripts/linear_counterfactual.py model.json row.json --threshold 0.5 --json
python scripts/linear_counterfactual.py linear.json row.json --target-value 250000 --side above
```
The model spec holds the intercept, coefficients and a per-feature constraint block. The script prints the
optimal counterfactual, diverse alternatives (the best without each used feature), single-feature options,
essential features, or NO RECOURSE with the best reachable probability. Exit codes: 0 found, 1 no feasible
recourse, 2 usage or read error.

```bash
python scripts/gen_dice_script.py --model model.joblib --train train.csv --rows test.csv --target churned --row 0 -o dice_run.py
python scripts/gen_dice_script.py --model m.joblib --train train.csv --rows test.csv --target churned --constraints c.json --method genetic --total 6
```
Immutable features are excluded from `features_to_vary` and directions become per-row `permitted_range`.
Integer features are rounded, every counterfactual is re-predicted, and the script prints the
`cf_validate.py` command with the right `--side`. Verified with dice-ml on logistic and LightGBM Pipelines
(random, genetic, kdtree). Exit codes: 0 written, 2 usage error.

```bash
python scripts/cf_validate.py --original row.json --cfs cfs.csv --train train.csv --constraints c.json --pred-col pred_prob --target-prob 0.5 --side below
```
Exit codes: 0 all usable, 1 any violation, invalid or off-manifold counterfactual, 2 usage or read error.

## Additional Resources

| File | Content |
|------|---------|
| [actionability-and-constraints.md](references/actionability-and-constraints.md) | designing constraints, cost scales, derived features, causal dependencies |
| [counterfactual-methods.md](references/counterfactual-methods.md) | the exact linear solution, DiCE, Wachter, prototypes, MILP, trade-offs |
| [communicating-recourse.md](references/communicating-recourse.md) | wording, regulation, fairness of recourse, audits |
