# Framing Pitfalls

Each pitfall: how it shows up, how to detect it early, and what to change.

## 1. Unactionable predictions
**Shows up as:** a model with strong offline metrics that no one consumes, or that is consumed and the KPI does
not move.
**Detect:** ask "what will you do differently on Monday with this score?" If the answer is a dashboard, the
framing is analytics.
**Fix:** start from the decision and capacity; predict the input to that decision.

## 2. Horizon shorter than the reaction time
**Shows up as:** high recall offline, but flagged customers have already left when the call happens.
**Detect:** compare horizon to the median time between scoring and action.
**Fix:** add a gap window, lengthen the horizon, or act faster.

## 3. Leakage by framing
**Shows up as:** AUC 0.95+ offline, collapse in production.
**Detect:** single-feature AUC near 1.0, features with names like status/reason/result, features computed from
tables overwritten after the event, a model that is much better on old rows than recent ones.
**Fix:** rebuild every feature as-of the prediction time; see target-leakage-detector.

## 4. Training population differs from the scoring population
**Shows up as:** offline metrics do not reproduce on live traffic.
**Examples:** trained on all customers but scored only on new ones; trained on customers who were already
contacted; trained after a dedupe step that production does not run.
**Fix:** generate training rows with the exact eligibility logic used at scoring time.

## 5. Feedback loops
**Shows up as:** a model that keeps getting "worse" each retraining; outcomes shaped by past model actions.
**Mechanism:** you call the high-risk customers, some are saved, so next time they look like non-churners and
the model learns that high-risk signals mean "stays".
**Fix:** keep a random untreated holdout; log score, action and outcome per row; train on holdout labels or
correct with inverse propensity weights; reframe as uplift when the action is the decision.

## 6. Selection bias in labels
**Shows up as:** labels exist only for cases someone chose to look at.
**Examples:** credit outcomes only for approved loans; fraud labels only for reviewed transactions; ticket
resolution labels only for escalated tickets.
**Fix:** randomised exploration (approve a small random sample), reject inference, or restrict the claim to
the labelled population and say so.

## 7. Proxy labels that drift from the goal
**Shows up as:** the proxy metric improves while the business metric does not.
**Fix:** document the gap, pair the proxy metric with a guardrail on the real goal, revisit the proxy after
launch.

## 8. Goodhart's law
**Shows up as:** when a metric becomes a target people game it: tickets closed early to hit resolution time,
leads marked qualified to hit quotas, and labels shift with them.
**Fix:** use labels produced by processes not graded on the model; audit samples; multiple metrics.

## 9. One model for many decisions
**Shows up as:** a single "risk score" used for calls, emails, discounts and credit limits, each wanting a
different horizon and population.
**Fix:** one framing per decision; shared features are fine, shared labels usually are not.

## 10. Ignoring the cost asymmetry
**Shows up as:** threshold 0.5, F1 optimised, and an operating point nobody chose.
**Fix:** write the cost of a false positive and a false negative (or the capacity) into the framing; pick the
threshold from it (see ml-success-metric-selector and imbalanced-class-handler).

## 11. Fairness and regulation found late
**Shows up as:** a launch blocked by legal, or harm to a group discovered after deployment.
**Fix:** list protected attributes and regulated decisions (credit, hiring, housing, insurance) at framing
time; plan sliced metrics, explanation requirements and adverse-action reasons.

## 12. Predicting what is already known
**Shows up as:** a model that "predicts" renewals of customers who already signed, or demand for orders already
placed.
**Fix:** remove the already-decided population; the model should only score genuine uncertainty.

## 13. Static framing of a non-stationary world
**Shows up as:** performance decays month by month.
**Fix:** decide the retraining cadence and drift monitors as part of the framing; prefer features that are
stable in meaning (ratios, recency) over raw counts tied to a growing product.

## Quick detection table

| Check | How | Red flag |
|-------|-----|----------|
| Single-feature predictive power | AUC/R² of each feature alone | > 0.9 AUC from one column |
| Time stability | metric by month of prediction date | steady decline, or much better on old data |
| Population match | compare training eligibility SQL with scoring SQL | any difference |
| Action logging | are actions per row stored? | no -> feedback loop cannot be corrected |
| Label provenance | who/what writes the label, when | written by a process that sees model output |
