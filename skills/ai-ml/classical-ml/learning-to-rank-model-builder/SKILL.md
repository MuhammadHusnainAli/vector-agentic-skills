---
name: learning-to-rank-model-builder
description: "Build learning-to-rank models for search, recommendations re-ranking and marketplace sorting: validate query-document data (contiguous query groups, single-label and no-relevant queries, duplicates, query-level features, single-feature baselines and leakage-like features), train LightGBM lambdarank and XGBoost rank:ndcg rankers with grouped cross-validation, early stopping on NDCG@k, label gains and truncation, and evaluate per query with NDCG (exponential or linear gain), MAP, MRR, ERR and precision@k, with tie handling made explicit and paired bootstrap / randomisation tests that tell whether a ranker really beats BM25 or the current system. Covers pointwise, pairwise and listwise losses, judgement and click labels, position bias, feature design and online interleaving. Use when someone builds a ranker, re-ranks search results or recommendation candidates, uses LambdaMART, or compares rankings offline."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Learning-to-Rank Model Builder

A ranker orders the documents of each query, so everything is per query: grouping, splitting, losses and
metrics. The common failures are silent ones:
- unsorted rows that mix queries into the wrong groups
- queries leaking across folds
- NDCG averaged over queries with no relevant documents
- tied scores evaluated optimistically
- a "better" model with no significance test over queries

The scripts check the data, train the rankers and evaluate them per query:
- `scripts/ltr_data_check.py` validates the data
- `scripts/gen_ltr_script.py` trains LightGBM / XGBoost rankers with grouped CV
- `scripts/rank_eval.py` evaluates and compares rankings per query

## Trigger Conditions

Activate this skill when the user:
- Builds or tunes a ranker (LambdaMART, LightGBM `LGBMRanker`, XGBoost `XGBRanker`) for search or re-ranking
- Re-ranks recommendation candidates with features
- Compares rankings offline (BM25 vs a model, model A vs B) or needs NDCG/MAP/MRR computed correctly
- Has relevance judgements or click logs and asks how to turn them into training labels

Candidate generation for recommendations: [recommendation-system-designer](../recommendation-system-designer/SKILL.md).
GBM tuning detail: [xgboost-lightgbm-tuner](../xgboost-lightgbm-tuner/SKILL.md).

## Workflow

```
1. CHECK     -> python scripts/ltr_data_check.py data.csv --qid-col qid --label-col label --exclude doc_id
2. BASELINE  -> single-feature NDCG (bm25, current production score) from the check, or rank_eval.py
3. TRAIN     -> python scripts/gen_ltr_script.py --data data.csv --features f1 f2 f3 --models lgbm xgb --k 10 -o ltr.py
4. EVALUATE  -> python ltr.py; python scripts/rank_eval.py oof_scores.csv --scores lgbm xgb --baseline bm25 --k 10
5. DECIDE    -> significant per-query gain over the baseline? Then plan an online interleaving / A/B test
```

## Data Rules

| Rule | Why | Check |
|------|-----|-------|
| Rows sorted by query id before building groups | LightGBM `group=` and XGBoost `qid=` assume contiguous blocks | BLOCKING in `ltr_data_check.py` |
| Split by query (GroupKFold) | documents of one query in train and test leak | the generated script |
| Single-label queries out of training | no pairs, so no gradient for pairwise/listwise losses | WARNING, excluded |
| Queries with no relevant document reported separately | NDCG is undefined (LightGBM counts them as 1) | `rank_eval.py --empty` |
| Single-feature baselines first | many rankers barely beat BM25 | the check's feature table |
| Features that rank almost perfectly | labels leaking into features (clicks derived from judgements) | BLOCKING at NDCG >= 0.98 |
| Query-level features (constant in a query) | cannot reorder documents on their own | WARNING |

Labels from judgements, clicks or purchases, position bias and feature design:
[ltr-data-and-labels.md](references/ltr-data-and-labels.md).

## Models and Losses

| Approach | Loss | Library |
|----------|------|---------|
| Pointwise | regression / classification of the label | any GBM |
| Pairwise | RankNet / BPR-style pairs | XGBoost `rank:pairwise` |
| Listwise (LambdaMART) | lambdas weighted by the NDCG change | LightGBM `lambdarank`, XGBoost `rank:ndcg` |
| Neural | listwise softmax / ApproxNDCG | TF-Ranking, allRank |

LambdaMART (GBDT with lambdarank) is the strong default for tabular features. Set `label_gain` = 2^label - 1
(LightGBM's default is the same; pass it explicitly when labels exceed 30), truncate the lambdas at the
evaluation depth (`lambdarank_truncation_level` / `lambdarank_num_pair_per_sample`), and early-stop on NDCG@k
of a query-grouped validation split. Parameters and code: [ltr-models.md](references/ltr-models.md).

## Evaluation

| Metric | Use |
|--------|-----|
| NDCG@k | graded relevance, position-discounted; the main metric |
| MAP@k, P@k | binary relevance (label >= threshold) |
| MRR | navigational queries: the first relevant result matters |
| ERR@k | cascade user model: stops at the first satisfying result |

- **Gain convention**: exponential (2^label - 1; LightGBM, XGBoost, TREC) by default. `--gain linear` matches
  `sklearn.metrics.ndcg_score` (verified: 0.9322 on the fixture).
- **Ties**: pessimistic by default (a constant score cannot look good). `--ties input` reproduces LightGBM's
  own NDCG@k exactly (verified 0.9019/0.9263). With coarse scores the two differed by 0.07 on the fixture.
- **Significance**: queries are the unit. `--baseline` reports the mean per-query difference with a bootstrap
  CI and a sign-flip randomisation p-value. On the fixture, LightGBM and XGBoost improved NDCG@10 by about
  0.02 over BM25 but were **not significant** (p 0.25-0.35, 40 queries).

Metric formulas, pitfalls and online evaluation: [ltr-evaluation.md](references/ltr-evaluation.md).

## Output Format

When building a ranker, deliver:
1. **Data check** - queries, group sizes, labels, blocking issues fixed, single-feature baselines.
2. **Model** - loss, features, label gains, CV scheme, best iterations, feature importance.
3. **Evaluation** - NDCG@k/MAP/MRR per model and baseline, the gain and tie conventions, excluded queries.
4. **Significance** - per-query differences with CI and p-value against the baseline.
5. **Next steps** - an online interleaving or A/B test, label improvements, feature ideas.

## Scripts

```bash
python scripts/ltr_data_check.py ltr.csv --qid-col qid --label-col label --exclude doc_id score
python scripts/ltr_data_check.py train.csv --qid-col query --label-col rel --features bm25 pagerank ctr --k 5 --json
```
Exit codes: 0 no blocking issue, 1 blocking issue, 2 usage or read error.

```bash
python scripts/gen_ltr_script.py --data ltr.csv --qid-col qid --label-col label --features bm25 freshness clicks -o ltr.py
python scripts/gen_ltr_script.py --data train.csv --qid-col query --label-col rel --exclude doc_id --models lgbm xgb --k 5
```
Writes `oof_scores.csv` (out-of-fold scores plus raw features for baselines) and `ranker_<model>.joblib`.
Exit codes: 0 written, 2 usage error.

```bash
python scripts/rank_eval.py preds.csv --qid-col qid --label-col label --scores lgbm xgb --baseline bm25 --k 5 10
python scripts/rank_eval.py preds.csv --scores model --k 10 --gain linear --ties input --per-query per_query.csv
```
Exit codes: 0 evaluated, 1 with `--baseline` when no model is significantly better, 2 usage error.
`scripts/_rank_metrics.py` holds the shared metric functions.

## Additional Resources

| File | Content |
|------|---------|
| [ltr-data-and-labels.md](references/ltr-data-and-labels.md) | judgements, click models and position bias, sampling, feature families |
| [ltr-models.md](references/ltr-models.md) | pointwise/pairwise/listwise, LambdaMART, LightGBM and XGBoost parameters, neural rankers |
| [ltr-evaluation.md](references/ltr-evaluation.md) | metric definitions, gain and tie conventions, significance, interleaving and A/B tests |
