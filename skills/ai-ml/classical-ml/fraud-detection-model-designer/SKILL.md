---
name: fraud-detection-model-designer
description: "Design fraud detection models that survive production: point-in-time velocity and behaviour features per card, account or device (counts and amounts over sliding windows that exclude the current event, time since previous, amount relative to history, first-time merchant category or country), out-of-time splits with a label-maturity gap for chargeback delay, LightGBM with an Isolation Forest anomaly score, and evaluation the way fraud operations work: average precision against the fraud-rate baseline, precision/recall and value detection rate at alert budgets, recall at fixed false-positive rates, cost-optimal thresholds from fraud losses, review cost and customer friction, alert-capacity constraints and week-by-week stability. Covers rules versus models, label delay and noise, adversarial drift, graph and device signals, real-time scoring and feedback loops. Use when someone builds or reviews a fraud, scam, abuse, chargeback or anti-money-laundering model, sets fraud thresholds, or evaluates a fraud score."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Fraud Detection Model Designer

Fraud is an adversarial, extremely imbalanced problem with delayed and noisy labels and asymmetric costs.
The patterns that make fraud models look great offline and fail live are well known:
- features computed with future information
- random splits
- accuracy or ROC AUC as the headline
- thresholds picked without the alert budget or the money involved

This skill builds the features, the protocol and the evaluation around those realities:
- `scripts/fraud_velocity_features.py` computes leak-free velocity features
- `scripts/gen_fraud_model_script.py` writes an out-of-time LightGBM + anomaly-score model
- `scripts/fraud_eval.py` evaluates a score in alerts, money and cost

## Trigger Conditions

Activate this skill when the user:
- Builds or reviews a fraud, scam, account-takeover, promo-abuse, chargeback or AML model
- Needs velocity / behavioural features for transactions or events
- Must set a fraud threshold, size an alert queue, or estimate money saved
- Sees a fraud model that degrades after launch or looks too good offline

General imbalance techniques and threshold tuning: [imbalanced-class-handler](../imbalanced-class-handler/SKILL.md).
Unsupervised detectors: [anomaly-detection-model-builder](../anomaly-detection-model-builder/SKILL.md). Leakage:
[target-leakage-detector](../target-leakage-detector/SKILL.md).

## Workflow

```
1. LABELS    -> define fraud (confirmed chargeback, analyst decision, customer report), label delay, exclusions
2. FEATURES  -> python scripts/fraud_velocity_features.py tx.csv --entity card_id --categorical merchant_category country -o feats.csv
3. MODEL     -> python scripts/gen_fraud_model_script.py --data tx.csv --entity card_id --categorical merchant_category country -o model.py
4. EVALUATE  -> python model.py; python scripts/fraud_eval.py test_scored.csv --alerts-per-day 50
5. OPERATE   -> threshold from cost and capacity; rules + model; monitoring of AP by week and fraud mix
```

## Labels and Splits

| Issue | Rule |
|-------|------|
| Label delay | chargebacks arrive weeks to months later. Leave a **gap** between train end and test start (`--gap-days`), and do not train on immature recent labels |
| Label noise | friendly fraud, unconfirmed alerts and "no label = legit" bias. Document the label source |
| Selection bias | blocked transactions never get labels. Keep a small random hold-out that is not blocked, or use rejected-inference caveats |
| Splits | **out of time** only. Random splits let the model learn fraud rings it would not have seen yet |
| Entity leakage | features or splits that let the same card or ring appear in train and test with future knowledge |

## Features That Work

| Family | Examples | Leak-free rule |
|--------|----------|----------------|
| Velocity | transactions and amount per card in 1h / 24h / 7d | windows end before the current event (`closed="left"`) |
| Behaviour deviation | amount / card's past mean, z-score, unusual hour | statistics from past events only |
| Novelty | first time this merchant category / country / device / IP for the entity | the "seen" set is updated after scoring |
| Network | shared devices, emails, IPs, cards per device; graph features | as of the event time |
| Merchant / context | merchant risk tier, MCC, channel, card-not-present | known at authorisation |
| Unsupervised | Isolation Forest / autoencoder score fitted on the training period | fit on train only |

`fraud_velocity_features.py` (stdlib, streaming) and the generated script's pandas features produce
identical values, and both match pandas `rolling(closed="left")`. The same definitions can therefore be
served online. Feature catalogue and real-time computation: [fraud-features.md](references/fraud-features.md).

## Evaluating a Fraud Score

| Question | Metric | fraud_eval.py |
|----------|--------|---------------|
| Does it rank fraud first? | average precision (baseline = fraud rate); ROC AUC only as secondary | ranking |
| What does the alert queue look like? | precision, recall and alerts/day at the top 0.5-5% | alert rates |
| How much money is stopped? | **value detection rate** (fraud amount caught / total) | every table |
| How many good customers are hit? | FPR, recall at FPR 0.1% / 1% | at FPR |
| Where should the threshold be? | minimal expected cost: missed amount x loss rate + review cost + friction | cost |
| Can the team handle it? | best threshold within the alerts-per-day capacity | `--alerts-per-day` |
| Is it stable? | AP and fraud rate by week | by week |

On the fixture: AP 0.83 against a random 0.023. The cost-optimal threshold reviews 121 alerts, catches 98.6%
of the fraud value and costs 705 against 11,807 without a model. A capacity of one alert per day lowers value
detection to 73%. Metrics match scikit-learn (ROC AUC, AP). Details and the cost model:
[fraud-evaluation.md](references/fraud-evaluation.md).

## Production Design

- **Rules + model**: hard rules for known patterns and regulatory blocks, the model for ranking, and
  analyst review for the uncertain band.
- **Decisions**: approve / step-up authentication / review / decline. Each has its own threshold and cost.
- **Real time**: sub-100 ms scoring with online feature stores (velocity counters in Redis or Flink).
- **Feedback loop**: blocked fraud gets no chargeback label. Record analyst outcomes and keep a random
  control.
- **Adversarial drift**: retrain frequently, monitor AP by week, the feature distributions and new
  fraud-pattern clusters.

Operations, monitoring and governance: [fraud-operations.md](references/fraud-operations.md).

## Output Format

When designing or reviewing a fraud model, deliver:
1. **Label definition** - source, delay, exclusions, the gap used.
2. **Features** - families, point-in-time guarantees, online computation plan.
3. **Model and split** - out-of-time design, model, importance, the anomaly component.
4. **Operating point** - the alert-rate table, value detection, the cost-optimal and capacity thresholds.
5. **Operations** - decisions per band, monitoring (AP by week, drift), the retraining cadence.

## Scripts

```bash
python scripts/fraud_velocity_features.py transactions.csv --entity card_id --time-col timestamp --amount-col amount \
    --categorical merchant_category country -o features.csv
```
Exit codes: 0 written, 2 usage or read error.

```bash
python scripts/gen_fraud_model_script.py --data transactions.csv --entity card_id --label-col is_fraud -o fraud_model.py
python scripts/gen_fraud_model_script.py --data tx.csv --entity account_id --categorical merchant_category country --gap-days 14
```
Exit codes: 0 written, 2 usage error.

```bash
python scripts/fraud_eval.py transactions.csv --label-col is_fraud --score-col score --amount-col amount
python scripts/fraud_eval.py scored.csv --alerts-per-day 20 --review-cost 5 --friction-cost 10 --loss-rate 0.8
```
Exit codes: 0 evaluated, 2 usage or read error.

## Additional Resources

| File | Content |
|------|---------|
| [fraud-features.md](references/fraud-features.md) | feature families, point-in-time computation, online counters, graph signals |
| [fraud-evaluation.md](references/fraud-evaluation.md) | metrics under imbalance, value detection, cost model, capacity, label delay in evaluation |
| [fraud-operations.md](references/fraud-operations.md) | rules + model, decision bands, feedback loops, drift and adversaries, monitoring, governance |
