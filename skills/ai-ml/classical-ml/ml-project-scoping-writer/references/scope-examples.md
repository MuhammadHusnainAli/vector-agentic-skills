# Scope Examples

## Example 1: churn retention targeting (abridged)

```markdown
# Churn retention targeting

| Owner | Date | Status |
|-------|------|--------|
| Data Science - Retention | 2026-11-01 | in review |

## Summary
Rank active subscribers each Monday by risk of voluntary cancellation in the next 30 days so the retention
team calls the 400 most at-risk customers instead of those whose contract ends this month.

## Problem and decision
Voluntary churn is 2.1% per month (~1,050 customers, ~$630k monthly revenue). The current rule finds 30% of
next-month churners in its 400 calls. Decision: which 400 customers are called each week.

## Success criteria
| Item | Value |
|------|-------|
| Primary metric | recall@400 of 30-day voluntary churners |
| Target | >= 0.45 on the latest 3-month time holdout, 95% CI above the rule |
| Baseline | 0.30 (contract-end rule, same holdout) |
| Guardrails | complaint rate <= 1.5%; recall@400 per region >= 0.35; score PSI < 0.2 |
| Online metric | saves per 400 calls vs a 5% untreated holdout, 6 weeks |

## Data and labels
Label: voluntary cancellation in (score_date, score_date + 30 days], active customers only.
History: 24 months of weekly snapshots (~50k customers/week).
| Source | Owner | Freshness | Available at prediction time |
|--------|-------|-----------|------------------|
| billing.subscriptions | finance | hourly | yes |
| support.tickets | support | daily (24 h lag) | yes, up to previous day |
| churn_survey | marketing | after cancellation | NO (excluded) |

## Approach
1. Baseline: rule, dummy, logistic regression on a time holdout.
2. Model: LightGBM on point-in-time features; calibrated; top-400 cut.
3. Shadow: 4 weeks scoring without acting.
4. Test: randomised model vs rule, 6 weeks.

## Scope
| In scope | Out of scope |
|----------|--------------|
| weekly batch scoring | real-time scoring |
| voluntary churn, consumer plans | involuntary churn (payment failures), business plans |
| ranking who to call | choosing the offer (separate uplift project) |

## Milestones
| Milestone | Date | Exit criterion |
|-----------|------|----------------|
| Label + feature table | 2026-11-08 | leakage scan clean, label query reviewed by finance |
| Baseline table | 2026-11-15 | rule, dummy, LR measured with CIs |
| Model ready | 2026-12-13 | recall@400 >= 0.45 offline |
| Shadow complete | 2027-01-17 | features present for >= 98% of rows; PSI < 0.2 |
| Test readout | 2027-03-07 | go/no-go |

## Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Calls change labels (feedback loop) | high | medium | 5% untreated holdout; log calls |
| Ticket data lags 24 h | medium | low | features up to previous day only |
| Team ignores list | medium | high | co-design list format with team leads; weekly review |

## Go / no-go criteria
- Stop after the model milestone if recall@400 < 0.40 or the CI overlaps the rule.
- Launch if the test shows >= +5 saves/week with the 95% CI excluding 0.
```

## Example 2: store-SKU demand forecasting (key sections)

**Summary.** Forecast daily unit sales per store-SKU for days t+2..t+8 to set replenishment orders, replacing
"same week last year x trend".

**Success criteria.**
| Item | Value |
|------|-------|
| Primary metric | WAPE at store-SKU-week, weighted by margin |
| Target | <= 0.28 (baseline 0.34) on a 13-week rolling-origin backtest |
| Guardrails | bias within ±3%; stock-out rate not higher than control stores |
| Online metric | waste and stock-out rate in 20 pilot stores vs 20 matched control stores, 8 weeks |

**Scope.**
| In scope | Out of scope |
|----------|--------------|
| 40k store-SKUs with >= 1 year history | new products (cold start) |
| point forecast + 80% interval | price optimisation |
| daily batch | intraday re-forecasting |

**Risks.** Censored demand during stock-outs (mitigation: flag stock-out days, impute demand); promotions
known late (mitigation: only planned promotions as features); holiday calendar changes (mitigation: explicit
holiday features, review each year).

## Before/after rewrites

| Before | After |
|--------|-------|
| "Leverage AI to optimise retention." | "Rank customers weekly by 30-day churn risk so retention calls the top 400." |
| "Achieve high accuracy." | "Recall@400 >= 0.45 on the latest 3-month holdout (rule: 0.30)." |
| "Real-time fraud detection." | "Score each authorisation within 30 ms p99 at 2,000 TPS." |
| "Deliver insights on churn drivers." | "Report the top 10 drivers with SHAP and a retention-team review by Dec 1." |
| "Use state-of-the-art deep learning." | "Start with logistic regression and LightGBM; consider sequence models only if they beat both by 0.03 AUC." |
| "Deliver ASAP." | "Baseline table by Nov 15; test readout by Mar 7." |
| "Risk: data quality." | "Risk: support tickets lag 24 h (medium). Mitigation: features up to the previous day only." |
