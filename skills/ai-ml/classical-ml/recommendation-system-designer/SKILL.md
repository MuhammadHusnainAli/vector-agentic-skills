---
name: recommendation-system-designer
description: "Design recommendation systems from the interaction data up: profile users, items, density, cold start, popularity concentration (Gini, long-tail shares), explicit versus implicit feedback and repeats; choose between popularity, item-item kNN, matrix factorisation (ALS, BPR, EASE), content-based, hybrid, two-tower retrieval and learning-to-rank re-ranking; split by time (leave-last-n or global cut-off) instead of randomly; and evaluate top-k lists with precision, recall, hit rate, MRR, MAP and NDCG plus coverage, novelty, popularity bias, personalisation and diversity against a popularity baseline that is always computed. Covers candidate-generation and ranking architecture, cold-start strategies, business rules, online A/B metrics and feedback loops. Use when someone plans a recommender, 'customers also bought' or 'you may like' features, chooses a recommendation algorithm, or needs to evaluate recommendations offline."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Recommendation System Designer

Recommenders often fail for design reasons rather than algorithm reasons:
- a random split that leaks the future
- no popularity baseline, so a "good" model may only recommend bestsellers
- RMSE optimised when the product shows a ranked list
- no plan for new users and items
- offline metrics that never meet the business metric

This skill sets up the design, the protocol and the evaluation:
- `scripts/interaction_profile.py` reads the log and recommends an approach
- `scripts/temporal_split.py` splits the log the way the system will be used
- `scripts/rec_eval.py` scores any recommendation lists against held-out interactions, with
  beyond-accuracy metrics and a popularity baseline

## Trigger Conditions

Activate this skill when the user:
- Plans a recommender ("you may also like", "customers also bought", next item, personalised feed or email)
- Must choose an approach (popularity, item-kNN, ALS, BPR, content-based, two-tower, LTR)
- Needs an offline evaluation protocol or metrics for recommendations
- Sees a recommender that only shows popular items, or offline gains that do not show up in A/B tests

Building item-kNN and matrix factorisation models: [collaborative-filtering-implementer](../collaborative-filtering-implementer/SKILL.md).
Re-ranking with features: [learning-to-rank-model-builder](../learning-to-rank-model-builder/SKILL.md).

## Workflow

```
1. PROFILE   -> python scripts/interaction_profile.py interactions.csv
2. DEFINE    -> the surface, what counts as relevant (purchase, rating >= 4, watch > 50%), k, constraints
3. SPLIT     -> python scripts/temporal_split.py interactions.csv --mode leave-last --n 2 --prefix data
4. BASELINE  -> popularity is computed automatically by rec_eval.py; add recent-popularity / item-kNN
5. MODEL     -> candidates (CF, content) -> optional re-ranker; write recs.csv (user_id,item_id,rank[,model])
6. EVALUATE  -> python scripts/rec_eval.py --recs recs.csv --test data_test.csv --train data_train.csv --k 10 --min-rating 4
7. ONLINE    -> A/B test on the business metric; monitor coverage and feedback loops
```

## Choosing an Approach

| Situation | Start with | Add |
|-----------|-----------|-----|
| Little data, strong bestsellers | popularity (overall, per segment, recent) | item-kNN |
| Thousands of users and items, implicit feedback | item-kNN, ALS / EASE | BPR, a re-ranker |
| Explicit ratings | item-kNN / MF on ratings, evaluated as a ranking | treat low ratings as negative |
| Many new items (news, marketplace) | content-based (text / attribute embeddings) | hybrid with CF when interactions arrive |
| Many new users | popularity / contextual (location, device, referrer) | session-based models |
| Session data without user ids | item-to-item co-occurrence, session kNN, GRU4Rec / SASRec | |
| Large scale with rich features | two-tower retrieval + LTR re-ranking (GBDT LambdaMART) | |
| Repeat consumption (grocery, music) | personal frequency/recency baseline | CF for discovery |

Approach details, trade-offs and cold start: [approaches.md](references/approaches.md).

## Evaluation Protocol

- **Split by time.** Use leave-last-n per user (common in research) or a global cut-off (closest to
  deployment). Random splits put the future in train.
- **Filter seen items** unless re-recommendation is allowed. `rec_eval.py` does this by default.
- **Relevance definition**: explicit `rating >= 4` (`--min-rating 4`), implicit purchases or long views.
  Write it down.
- **Always compare with popularity.** On the fixture, popularity reached NDCG@10 0.164, a genre-aware list
  0.440 and random 0.054. The exit code is 1 when no model beats popularity.
- **Beyond accuracy**:

| Metric | Measures | Watch for |
|--------|----------|-----------|
| coverage | share of the catalogue recommended | below 20%: long tail ignored |
| novelty | mean self-information of recommended items | very low: only bestsellers |
| popularity bias | popularity of recommended items vs the catalogue average | well above 1: popularity amplification |
| personalisation | 1 - mean Jaccard between users' lists | near 0: everyone gets the same list |
| diversity | distinct categories per list (with `--item-features`) | single-category lists |

- **Segment the results**: cold vs warm users, head vs tail items, and new vs returning users.

Metric definitions, sampled-metric pitfalls and offline-online gaps:
[evaluating-recommenders.md](references/evaluating-recommenders.md). Verified: precision, recall, MAP and
NDCG match an independent computation (NDCG via `sklearn.metrics.ndcg_score`).

## Architecture

```
candidate generation (CF, content, popularity, rules)  ->  ~500 candidates per user
ranking (GBDT / neural re-ranker with user, item, context features)  ->  scored list
business logic (availability, diversity, dedup, fairness to sellers, exploration)  ->  final k
logging (impressions, clicks, position) -> training data and evaluation
```
Serving patterns, feedback loops, exploration and A/B testing:
[production-recommenders.md](references/production-recommenders.md).

## Output Format

When designing a recommender, deliver:
1. **Data profile** - size, density, cold start, popularity concentration, feedback type.
2. **Problem definition** - surface, relevance, k, constraints, business metric.
3. **Approach** - baselines, candidate sources, ranker, cold-start fallback.
4. **Offline evaluation** - split, the metric table against popularity, segment results.
5. **Online plan** - A/B design, guardrails (coverage, diversity), monitoring.

## Scripts

```bash
python scripts/interaction_profile.py ratings.csv
python scripts/interaction_profile.py events.csv --user-col visitor --item-col product --time-col ts --cold 5 --json
```
Exit codes: 0 profiled, 2 usage or read error.

```bash
python scripts/temporal_split.py ratings.csv --mode leave-last --n 2 --prefix ratings
python scripts/temporal_split.py events.csv --mode global --test-frac 0.2 --time-col ts --prefix events
```
Writes `<prefix>_train.csv` and `<prefix>_test.csv`, and reports cold test users and unseen test items.
Exit codes: 0 written, 2 usage or read error.

```bash
python scripts/rec_eval.py --recs recs.csv --test test.csv --train train.csv --k 10 --min-rating 4 --item-features items.csv
python scripts/rec_eval.py --recs all_models.csv --test test.csv --train train.csv --k 5 20 --json
```
Exit codes: 0 the best model beats popularity, 1 no model beats popularity, 2 usage or read error.

## Additional Resources

| File | Content |
|------|---------|
| [approaches.md](references/approaches.md) | popularity, neighbourhood, MF, EASE, content, hybrid, sequential, two-tower, LTR; cold start |
| [evaluating-recommenders.md](references/evaluating-recommenders.md) | splits, metric definitions, sampled metrics, segment analysis, offline vs online |
| [production-recommenders.md](references/production-recommenders.md) | multi-stage architecture, serving, business rules, exploration, feedback loops, A/B tests |
