# The Framing Canvas

A framing is complete when a stranger could build the training table from it without asking you anything.
Fill every field; write `TBD (owner, date)` rather than leaving one blank.

## Field by field

### 1. Decision
The choice that changes because of the prediction. Phrase it as a verb applied to a set:
"choose which 400 customers to call", "decide whether to hold this payment", "set tomorrow's order quantity".
If you cannot name a decision, stop: you have an analytics question, not an ML problem.

### 2. Action and capacity
Who executes the decision, through which system, and how many cases per period. Capacity turns a score into an
operating point: 400 calls a week means you care about precision and recall *in the top 400*, not at 0.5.
Capacity also caps value: a perfect model that flags 5,000 cases for a team that can review 50 adds little over
a decent one.

### 3. Unit of prediction
One row of the scoring table. Always "entity at a moment":
- "an active subscriber on a Monday scoring date"
- "a card transaction at authorisation time"
- "a store-SKU pair on the day the order is placed"
- "a support ticket when it is created"

If the same entity appears many times (weekly snapshots), say so: it drives grouped cross-validation.

### 4. Prediction time
When the model is called. Batch ("daily 02:00"), event-driven ("on ticket creation"), or request-time
("checkout, < 50 ms"). It defines the leakage line and the latency budget.

### 5. Target and horizon
An observable event or quantity in a window that starts at prediction time:
"cancels within 30 days", "units sold in the next 7 days", "chargeback filed within 90 days".
The horizon must exceed the time needed to act.

### 6. Label delay
How long after prediction time the label becomes known. Churn-in-30-days has a 30-day delay; chargebacks can
take 90+ days; ad clicks seconds. Delay sets the earliest you can evaluate a model in production and the
freshest data you can train on.

### 7. Features and availability
For each source: owner, update frequency, and *when the value for a given row is written*. Anything written
after prediction time is unusable unless rebuilt as an as-of snapshot.

### 8. Baseline
The current process measured on the same population and metric: a rule, a heuristic, a human queue order, or
"do nothing". Without it no one can say whether the model helps.

### 9. Metric and guardrails
One primary metric at the operating point, tied to the decision (recall@400, cost per saved customer, WAPE on
the order quantity), plus guardrails that must not degrade (complaints, false-decline rate, fairness gaps).

### 10. Risks
Proxy gap, feedback loop, selection bias, fairness, regulatory constraints, label drift.

## Filled canvases

### Subscription churn
| Field | Value |
|-------|-------|
| Decision | Which customers the retention team calls this week |
| Action + capacity | Agents call with an offer; 400 calls/week |
| Unit | Active subscriber on the Monday scoring date |
| Prediction time | Monday 06:00 UTC batch |
| Target | Voluntary cancellation within 30 days after scoring |
| Label delay | 30 days |
| Features | tenure, plan, usage last 7/30/90 d, support tickets last 90 d, payment failures, price changes |
| Unsafe features | cancellation_reason, refund_issued, account_status read today |
| Baseline | Call customers whose contract ends this month |
| Metric | Saved customers per 400 calls (needs holdout); offline proxy recall@400 |
| Guardrails | Complaint rate, offer cost per save |
| Risks | Calls change outcomes (feedback) -> keep 5% untreated holdout; consider uplift |

### Retail demand
| Field | Value |
|-------|-------|
| Decision | Order quantity per store-SKU for the next replenishment cycle |
| Action + capacity | Auto-replenishment system; all 40k store-SKUs daily |
| Unit | Store-SKU on the order date |
| Prediction time | Daily 22:00 after sales close |
| Target | Units sold over days t+2..t+8 (lead time 2 days, cycle 7 days) |
| Label delay | 8 days |
| Features | lagged sales, price, promotions planned (known in advance), holidays, weather forecast |
| Unsafe features | actual weather, realised promotions not planned at order time, stock-outs after t |
| Baseline | Same week last year x trend, or seasonal naive |
| Metric | WAPE weighted by margin; bias (over/under) |
| Guardrails | Stock-out rate, waste for perishables |
| Risks | Censored demand when out of stock (sales < demand) |

### Card fraud
| Field | Value |
|-------|-------|
| Decision | Approve, decline or step-up (3-D Secure) at authorisation |
| Action + capacity | Real-time rules engine; analysts review 2,000 cases/day |
| Unit | Card transaction at authorisation |
| Prediction time | Request time, < 30 ms |
| Target | Confirmed fraud (chargeback or analyst label) within 90 days |
| Label delay | Up to 90+ days; analyst labels within 2 days for reviewed cases |
| Features | velocity per card/device/merchant, amount vs card history, geo distance, device fingerprint |
| Unsafe features | chargeback flags, case outcomes, merchant risk score recomputed after the fact |
| Baseline | Current rule set |
| Metric | Fraud value caught at a fixed false-decline rate; review precision at 2,000/day |
| Guardrails | Approval rate, customer friction, fairness by region |
| Risks | Declined transactions never get labels (selection bias); adversarial drift |

### B2B lead scoring
| Field | Value |
|-------|-------|
| Decision | Order of leads in each rep's queue |
| Action + capacity | 25 reps x 30 touches/day |
| Unit | Lead on the day it enters the queue |
| Prediction time | On creation, refreshed daily |
| Target | Opportunity created within 21 days |
| Label delay | 21 days |
| Baseline | Order by company size, then recency |
| Metric | Opportunities from the top 750 daily leads |
| Risks | Reps already cherry-pick; labels reflect who was contacted (selection bias) |

### Support ticket routing
| Field | Value |
|-------|-------|
| Decision | Which queue a new ticket goes to |
| Unit | Ticket at creation |
| Target | Final resolving queue (multiclass) |
| Unsafe features | agent notes, reassignments, resolution codes |
| Baseline | Keyword rules |
| Metric | Top-1 accuracy and reassignment rate; macro-F1 so small queues count |
| Risks | Label noise: tickets resolved in the wrong queue |

### Predictive maintenance
| Field | Value |
|-------|-------|
| Decision | Which machines get an inspection in next week's schedule |
| Action + capacity | 12 inspections/week |
| Unit | Machine on the planning date |
| Target | Failure within 14 days (or remaining useful life with survival framing) |
| Label delay | 14 days |
| Baseline | Fixed-interval maintenance |
| Metric | Failures caught by the 12 inspections; downtime avoided |
| Risks | Maintenance prevents failures, hiding labels; rare events -> pool fleets |

### Credit default
| Field | Value |
|-------|-------|
| Decision | Approve/decline and limit at application |
| Unit | Application at submission |
| Target | 90+ days past due within 12 months of origination |
| Label delay | 12 months |
| Risks | Only approved applicants have labels (reject inference); regulation requires explainability and adverse-action reasons |

### Pricing / discount
| Field | Value |
|-------|-------|
| Decision | Discount level shown to each visitor |
| Target | Conversion and margin under each discount (causal) |
| Framing | Uplift / contextual bandit, not plain conversion prediction |
| Risks | Historical discounts were not random: confounded by targeting rules |
