# LTR Models

## Loss families

| Family | Idea | Notes |
|--------|------|-------|
| Pointwise | predict each label independently (regression / ordinal) | simple; ignores the ranking structure |
| Pairwise | penalise mis-ordered pairs (RankNet, RankSVM) | optimises AUC-like objectives |
| Listwise | optimise a list metric (LambdaRank / LambdaMART, ListNet, ApproxNDCG) | best for NDCG@k |

**LambdaMART**: gradient-boosted trees whose gradients ("lambdas") for each document pair are scaled by the
change in NDCG from swapping them. It is the standard strong baseline.

## LightGBM

```python
from lightgbm import LGBMRanker, early_stopping
df = df.sort_values("qid", kind="stable")                    # contiguous groups
group = df.groupby("qid", sort=False).size().to_numpy()
ranker = LGBMRanker(objective="lambdarank", n_estimators=2000, learning_rate=0.05, num_leaves=31,
                    min_child_samples=20, label_gain=[2 ** i - 1 for i in range(5)],
                    lambdarank_truncation_level=10)
ranker.fit(X_tr, y_tr, group=group_tr, eval_set=[(X_va, y_va)], eval_group=[group_va], eval_at=[5, 10],
           callbacks=[early_stopping(100)])
scores = ranker.predict(X_te)                                  # compare within a query only
```
| Parameter | Effect |
|-----------|--------|
| `label_gain` | gain per label (default 2^i - 1 for i up to 30) |
| `lambdarank_truncation_level` | only pairs involving the top positions get lambdas; set near k |
| `lambdarank_norm` | normalise lambdas per query (default true) |
| `objective="rank_xendcg"` | XE-NDCG: faster, often similar quality |
| `lambdarank_position_bias_regularization` + `position` | unbiased LambdaMART for click data |

## XGBoost

```python
from xgboost import XGBRanker
ranker = XGBRanker(objective="rank:ndcg", lambdarank_pair_method="topk", lambdarank_num_pair_per_sample=10,
                   n_estimators=2000, learning_rate=0.05, max_depth=6, eval_metric="ndcg@10",
                   early_stopping_rounds=100)
ranker.fit(X_tr, y_tr, qid=qid_tr, eval_set=[(X_va, y_va)], eval_qid=[qid_va], verbose=False)
```
`qid` must be sorted (contiguous). Other objectives: `rank:pairwise` and `rank:map` (binary labels only: XGBoost rejects graded labels for it).
`lambdarank_unbiased=True` estimates position bias from the data (XGBoost 2.0+).

## Cross-validation

- GroupKFold by query, with early stopping on a query-grouped inner validation split, never on the test fold.
- Tune `num_leaves` / `max_depth`, `min_child_samples`, the learning rate and the truncation level.
  Rankers overfit small query sets quickly (best iterations of 1-85 on the 40-query fixture).
- Refit on all queries with about the mean best iteration x 1.1.

## Neural rankers

TF-Ranking, allRank and PyTorch implementations of listwise losses (softmax cross-entropy, ApproxNDCG,
NeuralNDCG) pay off with text or embedding inputs and large data. Cross-encoders (BERT re-rankers) dominate
text relevance, but cost much more at serving time. Use them on the top candidates only.

## Serving

- Score only the candidates of the query (tens to hundreds). Rankers compare documents within a query, and
  scores are not comparable across queries.
- Keep feature computation identical between training and serving (a feature store, or the same code path).
- Log the features at serving time to build the next training set without leakage.
