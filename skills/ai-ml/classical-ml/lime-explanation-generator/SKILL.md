---
name: lime-explanation-generator
description: "Generate LIME (Local Interpretable Model-agnostic Explanations) for tabular predictions that are reproducible and honest: run LimeTabularExplainer with training statistics, categorical encoding decoded inside the prediction function (so Pipelines with one-hot encoders work), quartile rules or continuous slopes, kernel width and sample size chosen deliberately, and repeated runs with different seeds. Then check stability (sign consistency, coefficient of variation, top-k overlap), surrogate fidelity (weighted R^2) and the gap between surrogate and model, and compare signs with SHAP for the same row. Explains when LIME is the right tool, how kernel width and discretisation change the answer, and how to report it. Use when someone asks for LIME explanations, sees LIME give different answers on each run, or needs a model-agnostic local explanation for a black-box model."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# LIME Explanation Generator

LIME explains one prediction by sampling perturbations around the row, querying the model, and fitting a
weighted linear surrogate. It works with any model, but the explanation depends on the random sample, the
kernel width and how continuous features are discretised. A single LIME run is an anecdote.
`scripts/gen_lime_script.py` writes a script that runs LIME correctly and repeatedly, and
`scripts/lime_stability.py` decides whether the result is stable and faithful enough to report.

## Trigger Conditions

Activate this skill when the user:
- Asks for LIME explanations of individual predictions
- Gets a different LIME explanation each time they run it
- Needs a local explanation for a model SHAP cannot explain efficiently (external API, ensemble of mixed models)
- Wants rule-like explanations ("support_calls > 3 raises churn probability")

For tree and linear models, SHAP is usually the better default: exact, additive and deterministic
([shap-value-explainer](../shap-value-explainer/SKILL.md)). Counterfactuals ("what would change the decision"):
[counterfactual-explanation-generator](../counterfactual-explanation-generator/SKILL.md).

## Workflow

```
1. GENERATE  -> python scripts/gen_lime_script.py --model m.joblib --train train.csv --rows test.csv --target y --row 0 5 -o lime_run.py
2. RUN       -> python lime_run.py                 (lime_runs_row<N>.csv, lime_row<N>.html)
3. CHECK     -> python scripts/lime_stability.py lime_runs_row0.csv --compare shap_row0.csv
4. TUNE      -> unstable: more samples / fixed kernel width; low fidelity: --no-discretize, smaller kernel width
5. REPORT    -> stable features only, mean weights, fidelity, the comparison with SHAP
```

## Settings That Change the Answer

| Setting | Effect | Guidance |
|---------|--------|----------|
| `num_samples` (`--samples`) | more samples, lower variance | 5000 by default; raise to 10-20k when unstable |
| `kernel_width` | the size of the "local" neighbourhood | default 0.75 x sqrt(n_features); smaller = more local, noisier |
| `discretize_continuous` | quartile rules vs continuous slopes | rules are readable; slopes fit smooth models better (`--no-discretize`) |
| training data | perturbation statistics and category frequencies | use the training set, not the test rows |
| seed | which perturbations are drawn | repeat with several seeds; never report one run |
| `num_features` (`--top`) | how many features the surrogate keeps | 5-10 |

Measured on the churn fixture (`gen_lime_script.py` + `lime_stability.py`): mean surrogate R^2 for the
same row went from 0.05 to 0.78 (logistic regression) and from 0.05 to 0.42 (LightGBM) when switching to
`--no-discretize`. The default quartile rules can be reproducible yet describe the model poorly. Details
and the algorithm: [lime-method.md](references/lime-method.md).

## Stability and Fidelity

| Check | Rule in lime_stability.py | If it fails |
|-------|---------------------------|-------------|
| sign consistency | >= 90% of runs agree on the sign | do not report that feature's direction |
| size noise | coefficient of variation <= 0.5 | report the direction, not the size |
| top-k membership | in the top-k in >= 80% of runs | the feature is borderline |
| top-k Jaccard | mean pairwise overlap >= 0.7 (negligible features ignored) | raise samples, fix the kernel width |
| fidelity | weighted R^2 of the surrogate >= 0.5 | try `--no-discretize`, a smaller kernel width, or SHAP |
| local gap | surrogate vs model prediction at the row | a large gap means the surrogate misses the model here |
| agreement | sign agreement with SHAP for the same row | investigate disagreeing features |

Verdicts: **STABLE**, **STABLE BUT LOW FIDELITY** and **UNSTABLE**. Interpretation and troubleshooting:
[stability-and-fidelity.md](references/stability-and-fidelity.md).

## Reporting LIME

- Report only features marked **stable**, with their mean weight over runs and the number of runs.
- State the settings: samples, kernel width, discretisation, training data, and fidelity.
- LIME weights are slopes of a local surrogate, in output units per rule (or per unit for continuous
  features). They do not sum to the prediction the way SHAP values do.
- Rules like "0 < support_calls <= 1" describe the bin the row falls into relative to the others, not a
  threshold the model uses.
- A local explanation describes one row. Do not generalise it to the model.

Wording templates and when to prefer other methods: [reporting-lime.md](references/reporting-lime.md).

## Output Format

When explaining a prediction with LIME, deliver:
1. **Setup** - model, row, training data, samples, kernel width, discretisation, repeats.
2. **Explanation** - the stable features with mean weights (and std), as rules or slopes.
3. **Quality** - stability verdict, top-k Jaccard, fidelity (R^2), local gap, agreement with SHAP.
4. **Caveats** - unstable features left out, local scope, non-causal reading.

## Scripts

```bash
python scripts/gen_lime_script.py --model model.joblib --train train.csv --rows test.csv --target churned --row 0 5 -o lime_run.py
python scripts/gen_lime_script.py --model pipe.joblib --train train.csv --rows test.csv --target price --row 3 --samples 10000
python scripts/gen_lime_script.py --model m.joblib --train train.csv --rows test.csv --target y --no-discretize --kernel-width 2.0 --repeats 20
```
Encodes categoricals for LIME and decodes them inside `predict_fn`, keeps integer dtypes, fills missing
numerics with training medians for LIME only, and explains the probability of `--class` (default: the last
class) or the regression output. Each repeat uses a new seed, and each row's runs go to one CSV.
Verified with the `lime` package on logistic-regression and LightGBM Pipelines (classification) and a
random-forest Pipeline (regression). Exit codes: 0 written, 2 usage error.

```bash
python scripts/lime_stability.py lime_runs_row0.csv
python scripts/lime_stability.py lime_runs_row0.csv --top-k 3 --compare shap_row0.csv --json
```
Exit codes: 0 stable, 1 unstable, 2 usage or read error. Low fidelity is reported in the verdict.

## Additional Resources

| File | Content |
|------|---------|
| [lime-method.md](references/lime-method.md) | the algorithm, perturbation of tabular data, kernel, discretisation, settings, library calls |
| [stability-and-fidelity.md](references/stability-and-fidelity.md) | why LIME varies, the checks, troubleshooting, comparing with SHAP |
| [reporting-lime.md](references/reporting-lime.md) | wording, what LIME weights mean, when to choose LIME, SHAP or counterfactuals |
