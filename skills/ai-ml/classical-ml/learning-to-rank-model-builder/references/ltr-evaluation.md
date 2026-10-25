# LTR Evaluation

## Metric definitions (per query, then averaged over queries)

| Metric | Definition |
|--------|------------|
| DCG@k | sum over i < k of gain(label_i) / log2(i + 2), gain = 2^label - 1 (exp) or label (linear) |
| NDCG@k | DCG@k / DCG@k of the ideal ordering |
| P@k | relevant documents in the top k / k |
| AP@k | sum of P@i at relevant positions i <= k / min(#relevant, k) |
| RR | 1 / position of the first relevant document |
| ERR@k | sum over i of (1 / (i+1)) R_i prod over j < i of (1 - R_j), R = (2^g - 1) / 2^g_max |

## Conventions that change the numbers

| Choice | Options | rank_eval.py |
|--------|---------|--------------|
| Gain | exp (2^l - 1; LightGBM/XGBoost/TREC), linear (sklearn) | `--gain` |
| Queries without relevant documents | exclude, count as 1 (LightGBM), count as 0 | `--empty` |
| Score ties | pessimistic, input order (LightGBM), optimistic | `--ties` |
| Relevance threshold for binary metrics | label >= 1 (or >= 2 for "highly relevant") | `--rel-min` |

Report the conventions with every number. On the fixture, the same coarse model scored NDCG@5 0.832
(pessimistic), 0.902 (input order, = LightGBM's internal metric) and 0.974 (optimistic).

## Significance

- The unit is the query. Compute the per-query metric for both systems and test the paired differences.
- `rank_eval.py --baseline` reports a bootstrap 95% CI of the mean difference and a randomisation (sign-flip)
  test with 10,000 permutations. The paired t-test is a common alternative (TREC practice).
- With few queries (< 50), only large differences are detectable. The fixture's +0.02 NDCG over BM25 was
  not significant with 40 queries.
- Many comparisons: correct (Holm) or pre-register the primary comparison.
- Look at wins and losses: a mean gain built on large wins for a few queries and small losses for many may
  be undesirable.

## Segment analysis

Report by query frequency (head, torso, tail), query type and number of candidates. Rankers often improve
head queries while hurting the tail. Write per-query results (`--per-query`) and inspect the worst losses.

## Online evaluation

| Method | Notes |
|--------|-------|
| Interleaving (team-draft, balanced) | mixes two rankings in one result list; very sensitive, needs fewer users than A/B |
| A/B test | business metrics (CTR@k, conversion, revenue, abandonment, reformulation rate) |
| Counterfactual evaluation | IPS on logged randomised rankings |

Offline NDCG gains often shrink online. Use offline evaluation to shortlist, and interleaving or A/B tests
to decide.
