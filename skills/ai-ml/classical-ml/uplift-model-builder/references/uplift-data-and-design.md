# Uplift Data and Design

## The four types

| Type | Without treatment | With treatment | Action |
|------|-------------------|----------------|--------|
| Persuadable | no | yes | treat |
| Sure thing | yes | yes | do not spend on them |
| Lost cause | no | no | do not spend on them |
| Sleeping dog | yes | no | never treat (retention calls that remind people to cancel) |

A response model ranks sure things and persuadables together at the top. An uplift model separates them.

## Data requirements

- **Randomised assignment** of the treatment (an A/B test or a holdout control in a campaign). Without it,
  treated and untreated people differ systematically and the "uplift" is confounded.
- **Pre-treatment covariates only**: everything known before the assignment. Variables affected by the
  treatment (opened the email, used the coupon) bias the estimates.
- **The outcome window** fixed in advance (conversion within 14 days of the send).
- **Enough data**: heterogeneous effects are smaller and noisier than average effects. A common rule is
  several thousand per arm for binary outcomes with a few percentage points of lift. `rct_check.py`
  prints the minimum detectable effect for the overall comparison. Segment effects need about
  (number of segments) x that sample.

## Designing experiments for uplift

- Use a control share of 10-50%: a larger control gives better uplift models, a smaller one costs less.
  Use the X-learner or reweighting for unbalanced arms.
- Randomise at the unit of decision (customer, not session).
- Keep a permanent random holdout in recurring campaigns to keep collecting unbiased data for retraining.
- Pre-register the outcome, the window and the segments to report.

## Observational data

Without randomisation, you need the propensity e(x) = P(treated | x) and the assumption of no unmeasured
confounding:
- estimate e(x), check overlap (no e near 0 or 1), and use doubly robust learners (DR-learner, causal
  forests with orthogonalisation: econml `DRLearner`, `CausalForestDML`)
- evaluate with IPW using the estimated propensities (`uplift_eval.py --propensity-col`) and treat the
  results as weaker evidence
- validate the final targeting policy with a randomised test before full rollout

## Common traps

| Trap | Effect |
|------|--------|
| Training on the treated group only (response model) | targets sure things |
| Post-treatment covariates | biased and leaky effects |
| Sample-ratio mismatch ignored | assignment or logging bug, so the results are invalid |
| Many segments tested without correction | false "persuadable" segments |
| Evaluating on the training data | optimistic Qini |
| Treating "negative uplift" scores as certain | noise near zero: act on significant deciles only |
