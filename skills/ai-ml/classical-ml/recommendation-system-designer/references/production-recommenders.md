# Production Recommenders

## Multi-stage architecture

| Stage | Input -> output | Typical methods | Latency budget |
|-------|-----------------|-----------------|----------------|
| Candidate generation | catalogue -> 100-1000 items | ALS/EASE neighbours, two-tower ANN, co-occurrence, popularity, rules | 10-30 ms |
| Ranking | candidates -> scores | GBDT LambdaMART, DNN with user/item/context features | 20-50 ms |
| Re-ranking / business logic | scores -> final k | diversity (MMR), dedup, availability, price rules, fairness, exploration | < 10 ms |

## Serving patterns

- **Batch**: compute top-N per user nightly and store it in a key-value store. This is simple and cheap,
  but it is not fresh.
- **Real-time**: retrieve candidates from precomputed embeddings or ANN, then rank online with fresh
  context.
- **Hybrid**: batch candidates plus an online re-rank with session features.

## Business rules

Typical rules:
- remove out-of-stock and already-purchased items (when not repeat-friendly)
- cap items per category or brand
- respect age and region restrictions and promoted slots
- keep rules outside the model, versioned and logged

## Exploration and feedback loops

A recommender trains on data it generated, so popular items get more exposure and more clicks. Counter it
with:
- exploration slots (epsilon-greedy, Thompson sampling) for new and tail items
- logging impressions with positions and propensities, so later training can correct for exposure
- monitoring catalogue coverage and the share of impressions on the top 1% of items over time

## A/B testing

| Metric type | Examples |
|-------------|----------|
| Primary | revenue per user, conversion, watch time, retention |
| Engagement | CTR on the widget, add-to-cart |
| Guardrails | coverage, diversity, latency, complaints, returns |
| Long-term | retention after 30/90 days (CTR wins can hurt retention) |

Randomise by user, run full weekly cycles, watch novelty effects, and check sample ratio mismatch.

## Monitoring

- the data pipeline: interaction volumes, new item rate, embedding freshness
- model outputs: coverage, popularity bias and personalisation daily
- online KPIs per surface; alert on drops after deployments
- retrain cadence matched to catalogue churn (daily for news, weekly for retail)
