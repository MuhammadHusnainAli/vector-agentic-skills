# Signal and Label Checks

## Single-feature screens

Before any model, score each column alone against the target:

| Target | Numeric feature | Categorical feature |
|--------|-----------------|---------------------|
| Binary | ROC-AUC of the raw value (direction-free: max(AUC, 1-AUC)) | AUC of out-of-fold smoothed target mean per level |
| Numeric | |Spearman| | |Spearman| of out-of-fold level means |
| Multiclass | one-vs-rest AUC for each class, take the max | same |

### Why out-of-fold for categoricals
A high-cardinality column (zip code, user ID) gets a "target mean per level" that memorises the label in-sample,
producing a fake AUC near 1.0. Computing each row's level mean from the *other* fold, with smoothing toward
the global mean (`(sum + m*prior) / (count + m)`), removes that optimism. The same logic is why target
encoding must be done inside CV folds (see categorical-encoding-selector).

### Missingness as a signal
Fields filled only when the outcome happens (`cancellation_reason`, `chargeback_date`, `resolution_code`) are
empty for negatives and filled for positives. Even if their values are never used, an "is missing" flag
created implicitly by imputation leaks the label. Score `is_missing(col)` as its own feature.

### Reading the screen
- **Best signal tiny:** univariate signal is absent. Interactions can exist (XOR-like), but in tabular business
  data that is rare; get new data sources before building.
- **Several moderate signals:** the usual healthy case.
- **One near-perfect feature:** a leak until proven otherwise. Ask when the field is written.
- **IDs or row numbers with signal:** data is sorted by outcome or time; the split or the data pipeline leaks.

## Leak signatures to look for

| Signature | Example | Check |
|-----------|---------|-------|
| Outcome-side fields | refund_issued, cancellation_reason | when is it written? |
| Post-event timestamps | last_activity_date read today | compare with the snapshot date |
| Aggregates over all history | lifetime_orders computed at extraction | recompute as-of |
| Missingness pattern | field null unless the event happened | is-missing AUC |
| ID or sequence | autoincrement IDs assigned at labelling | AUC of the ID |
| Duplicates across train/test | the same customer in both | grouped split |
| Target encoded on full data | category mean includes the row's own label | OOF encoding |

## Label noise

Estimate before modelling when labels come from people or heuristics:
1. Sample 200-500 rows stratified by label.
2. Have two people label them independently with the written guideline.
3. Compute agreement and Cohen's kappa:
   ```
   kappa = (p_observed - p_expected) / (1 - p_expected)
   ```
| Kappa | Agreement |
|-------|-----------|
| < 0.4 | poor: guideline or concept is unclear |
| 0.4 - 0.6 | moderate |
| 0.6 - 0.8 | substantial |
| > 0.8 | almost perfect |

With noise rate e on a binary label, the best achievable accuracy against those labels is about 1 - e; a model
"stuck" at 85% may be at the noise ceiling.

## Label drift by period

Compute the label rate per month of prediction date. Compare each month with the overall rate using a z-score
`(p_month - p) / sqrt(p (1 - p) / n_month)`; flag |z| > 3. Common causes: a change in the label definition
(new cancellation flow), a pipeline bug, a product change, seasonality. Decide which period is representative
of the future and validate there.

## Selection bias

Labels exist only where someone looked:
- Credit: repayment observed only for approved loans.
- Fraud: confirmed only for reviewed or charged-back transactions.
- Marketing: conversion observed only for contacted leads.

Consequences: the model learns the reviewer's policy, and performance on the unreviewed population is
unknown. Mitigations: a random exploration sample (approve/review a small random share), reject inference,
or limit the model's scope to the population with labels and state it.

## Feature availability audit

For each candidate source fill this table:

| Source | Owner | Update cadence | Written when | Available at prediction time? | Latency to fetch |
|--------|-------|----------------|--------------|-------------------------------|------------------|
| billing.invoices | finance | hourly | at invoice creation | yes | 50 ms (cache) |
| crm.cases | support | real-time | at case open; status overwritten | only as-of snapshot | warehouse only |
| churn_survey | marketing | weekly | after cancellation | **no** | - |

Any "no" that carries most of the signal is a NO-GO for the current framing.
