# LTR Data and Labels

## Data layout

One row per (query, document) with a query id, a graded label and features. Queries can be search queries,
users (for re-ranking recommendations), or (user, context) sessions.

```
qid,doc_id,label,bm25,title_match,price_rank,ctr_30d,doc_age_days
q17,d903,3,12.4,1,0.2,0.08,12
```

## Label sources

| Source | Pros | Cons |
|--------|------|------|
| Human judgements (0-4 scale) | clean, graded | expensive; judges disagree; drift from real intent |
| Clicks | plentiful, real intent | position bias, presentation bias, noise |
| Purchases / conversions | close to value | sparse |
| Dwell time, add-to-cart | intermediate strength | thresholds needed |

A typical graded mapping for e-commerce: 0 = impression only, 1 = click, 2 = add to cart, 3 = purchase.

## Position bias

Users click higher positions more, regardless of relevance. Training on raw clicks teaches the model to
reproduce the old ranking.
- **Estimate propensities** by position (randomisation experiments, or intervention harvesting from
  different rankers), then weight clicks by 1 / propensity (inverse propensity scoring). LightGBM supports
  unbiased lambdarank: `lambdarank_position_bias_regularization` with `position` in the Dataset.
- **Click models** (cascade, DBN) infer attractiveness and satisfaction from click sequences.
- Add a little randomisation (top-k shuffles) in production to collect less biased data.

## Sampling

- Keep all judged documents per query, and sample unjudged ones as label-0 negatives only if they were
  actually shown (or are clearly irrelevant).
- Very long candidate lists: keep the top N from the candidate generator plus the positives. Train on what
  the ranker will see at serving time.
- Balance queries: a few head queries with thousands of documents dominate training. Cap documents per query
  or weight queries.

## Feature families

| Family | Examples |
|--------|----------|
| Query-document match | BM25 per field, title match, embedding cosine similarity, exact phrase |
| Document quality | popularity, CTR (time-windowed and smoothed), rating, freshness, price |
| Query features | length, type (navigational / brand), category intent (query-level: only useful in interactions) |
| User / context | user-category affinity, device, location, time |
| Behavioural | historical CTR of the (query, doc) pair, with smoothing and a time cut-off |

Leakage traps: CTR or "was clicked" features computed over the same period as the labels; features derived
from the judgement process. Compute behavioural features strictly before the label window.
