# Funnel and Experiments

## Funnel table

| Step | Sessions | To next step | Drop-off |
|------|----------|--------------|----------|
| Cart viewed | 40,000 | 55% | 45% |
| Checkout started | 22,000 | 82% | 18% |
| Contact completed | 18,040 | 78% | 22% |
| Delivery completed | 14,071 | 90% | 10% |
| Payment submitted | 12,664 | 94% | 6% |
| Order placed | 11,904 | - | - |

Segment by device, new vs returning, traffic source, country and payment method. A step that looks fine overall often
hides a mobile or one-country problem.

## Revenue at stake

```
lost_orders(step)   = sessions_entering_step x (drop_rate - target_drop_rate)
revenue_at_stake    = lost_orders x average_order_value
```
Example: Delivery step drop 22% vs a target of 12% (similar sites, or your best segment):
`18,040 x 0.10 x $68 = $122,672 per period`. Use this to rank fixes, then discount by confidence.

## Diagnose before redesigning

- Session recordings and form analytics: fields with most corrections, time per field, abandonment field.
- Error logs: validation errors per field, payment decline codes.
- Exit survey on checkout ("What stopped you today?") with a few options + other.
- Usability tests with real payment flows in a test environment.

## Prioritising

| Fix | Impact | Confidence | Effort | Priority |
|-----|--------|------------|--------|----------|
| Show shipping cost in cart | High | High (research-backed) | Low | 1 |
| Address lookup | Medium | High | Medium | 2 |
| Wallets on mobile | High (mobile) | Medium | Medium | 3 |

## A/B tests

- One primary metric: completed orders per checkout start (or revenue per visitor). Guardrails: refunds, support contacts,
  average order value.
- Sample size from the baseline rate and the minimum detectable effect; don't stop early on a "significant" peek.
- Run full weeks to cover weekday patterns; avoid sale periods unless that's the context you care about.
- Don't test known best practices that fix clear failures (forced accounts, hidden fees): just fix them.
- Record results, including flat ones, in a shared log.
