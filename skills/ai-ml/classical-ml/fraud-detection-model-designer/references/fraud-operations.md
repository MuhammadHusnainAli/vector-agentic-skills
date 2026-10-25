# Fraud Operations

## Rules and models together

| Component | Role |
|-----------|------|
| Hard rules | regulatory blocks, sanctions, known compromised cards, impossible values |
| Model score | ranks the remaining risk |
| Score bands | approve (low), step-up authentication (medium), analyst review (high), decline (very high) |
| Analysts | label the uncertain band and feed decisions back |
| Rule engine for new attacks | fast, temporary response until the model is retrained |

Rules are explainable and fast to deploy, but they decay and overlap. Review the rule hit rates monthly and
retire rules that the model already covers.

## Feedback loops and selection bias

- Declined transactions never produce chargebacks, so the model never learns whether they were fraud.
  Keep a small random sample of high-score transactions that are reviewed instead of blocked, or use analyst
  outcomes as labels.
- Analyst decisions are labels with their own bias and delay. Record the decision, the reason and the time.
- When comparing a new model with the incumbent, both must be evaluated on traffic the incumbent did not
  filter, or the comparison favours the incumbent.

## Adversarial drift

Fraudsters adapt within days or weeks:
- retrain frequently (weekly or monthly) with an out-of-time validation for each release
- monitor AP by week, the alert volume, the share of fraud caught by rules vs the model, and feature PSI
- run anomaly detectors next to the supervised model to catch new patterns without labels
- prefer features that are costly for fraudsters to fake (device, network, behaviour) over easily changed ones

## Real-time architecture

```
event -> feature service (online counters, profile store) -> model (< 50 ms) -> decision engine (rules + bands)
      -> response (approve / challenge / decline) -> logging (features, score, decision, latency)
      -> label pipeline (chargebacks, analyst outcomes) -> training data (point-in-time joins)
```
Log the exact features used at decision time. Training on recomputed features introduces skew.

## Monitoring checklist

- [ ] average precision and value detection by week (with label maturity)
- [ ] alert volume per day vs capacity; analyst hit rate
- [ ] false-positive complaints and step-up abandonment rate
- [ ] feature PSI and missing rates; online/offline feature parity checks
- [ ] latency and timeouts (a timeout must fall back to a safe default)
- [ ] fairness: decline and challenge rates by customer segment and region

## Governance

Document the label definition, features, thresholds and their cost rationale, the expected performance and
known blind spots in a model card ([model-card-writer](../../model-card-writer/SKILL.md)). Credit and payment
fraud decisions can trigger adverse-action or explanation obligations. Keep the reason codes and the
review trail.
