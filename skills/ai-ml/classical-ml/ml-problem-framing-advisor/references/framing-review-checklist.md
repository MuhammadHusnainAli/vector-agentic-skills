# Framing Review Checklist

## Stakeholder interview (30 minutes)

Ask in this order; write answers into the spec for `scripts/frame_check.py`.

1. What decision do you make today that this should improve? Who makes it, how often?
2. How do you make it now? (This is the baseline.) How well does it work, and how do you know?
3. If you had a perfect prediction, what would you do differently? How many cases could you handle per
   day/week?
4. What exactly counts as the outcome? Where is it recorded? How long after the decision is it known?
5. How far ahead do you need to know? How long does acting take?
6. Which data do you look at when deciding? When is each piece of it updated?
7. What happens when the prediction is wrong in each direction? Which mistake is worse, and by how much?
8. Does acting change the outcome? (If yes: holdout, uplift.)
9. Who else is affected? Any regulated or sensitive groups?
10. What would make you stop using the model?

## Spec fields read by frame_check.py

| Field | Type | Used by rules |
|-------|------|---------------|
| `problem` | string | context only |
| `decision`, `action` | string | FR001 |
| `action_capacity` | string | FR010 |
| `owner` | string | FR013 |
| `unit_of_prediction` | string | FR003 |
| `prediction_time` | string | FR004 |
| `target` | string | FR002, FR005, FR014 |
| `task_type` | one of binary_classification, multiclass_classification, regression, forecasting, ranking, survival, uplift, anomaly, clustering | FR005, FR010, FR014 |
| `horizon_days`, `time_to_act_days`, `label_delay_days` | number | FR005, FR006 |
| `label_is_proxy`, `proxy_risk` | bool, string | FR011 |
| `features` | list of `{"name", "available_at"}`; `available_at` in prediction_time, before_prediction_time, static, or a later moment | FR007 |
| `baseline` | string | FR008 |
| `success_metric`, `guardrail_metrics` | string, list | FR009 |
| `prediction_affects_label`, `holdout_plan` | bool, string | FR012 |

## Review checklist

**Decision**
- [ ] A named decision, owner and action
- [ ] Capacity per period
- [ ] Today's process is described and can be measured (baseline)

**Prediction**
- [ ] Unit of prediction = entity at a moment
- [ ] Prediction time and latency budget
- [ ] Horizon longer than the time to act
- [ ] Training population built with the scoring eligibility logic

**Label**
- [ ] Written as a query
- [ ] Outcome window fully observed for every training row
- [ ] Label delay known; monitoring plan accounts for it
- [ ] Proxy gap documented
- [ ] Noise estimated on a double-labelled sample if humans label

**Features**
- [ ] Every source has an "available at" time
- [ ] No outcome-side, final-state or all-time aggregate columns
- [ ] As-of logic for slowly changing data

**Evaluation**
- [ ] Primary metric at the operating point
- [ ] Guardrails
- [ ] Validation split mirrors deployment (time-based / grouped)
- [ ] Sliced metrics for key segments and protected groups

**Risks**
- [ ] Feedback loop: holdout and action logging
- [ ] Selection bias in labels
- [ ] Regulatory and explanation requirements
- [ ] Retraining cadence and drift monitoring

## Red-flag phrases

| Phrase | Ask |
|--------|-----|
| "Use AI to..." | Which decision changes? |
| "Predict churn" | Within what window, for whom, scored when? |
| "We'll figure out how to use it later" | Then stop until you do |
| "We have all the data" | When is each field written? |
| "Accuracy of 95%" | What is the base rate? What does the current rule get? |
| "Real-time" | What latency, and is the data real-time too? |
| "The model will learn what matters" | From which label, measured how? |
