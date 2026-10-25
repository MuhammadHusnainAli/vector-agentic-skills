---
name: collaborative-filtering-implementer
description: "Implement collaborative filtering recommenders that beat popularity: item-based kNN with cosine, Jaccard or asymmetric similarity, shrinkage, neighbourhood size, positive-only or mean-centred rating signals and 'because you liked X' explanations; implicit ALS with confidence weighting, BPR pairwise ranking and the closed-form EASE model in plain NumPy, tuned on a temporal validation split by recall@k and NDCG@k and refit on all data; plus user-kNN, explicit matrix factorisation, the implicit/LightFM libraries, hyperparameter ranges, cold-start fallbacks, scaling with sparse matrices and approximate nearest neighbours. Produces top-k lists in the format of the recommendation evaluator. Use when someone builds 'users who liked this also liked', item-to-item recommendations, matrix factorisation or ALS/BPR models, or asks why their collaborative filter is no better than recommending bestsellers."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Collaborative Filtering Implementer

Collaborative filtering (CF) recommends from the interaction matrix alone: people who liked X also liked
Y. Done well, it is a strong recommender. Done carelessly, it is popularity with extra steps. The details
that decide it are which interactions count as positive, similarity shrinkage, regularisation strong
enough for sparse data, and hyperparameters tuned on a temporal validation split.
- `scripts/itemknn.py` implements item-kNN with explanations
- `scripts/gen_mf_script.py` generates NumPy ALS, BPR and EASE models with tuning

Both write lists that `rec_eval.py` from
[recommendation-system-designer](../recommendation-system-designer/SKILL.md) scores against the popularity
baseline.

## Trigger Conditions

Activate this skill when the user:
- Builds item-to-item ("similar items", "also liked") or personalised CF recommendations
- Implements or tunes ALS, BPR, EASE, SVD/matrix factorisation or kNN recommenders
- Has a CF model that barely beats popularity, or recommends only bestsellers
- Needs explanations for recommendations ("because you watched X")

Design, data profiling, splits and evaluation: [recommendation-system-designer](../recommendation-system-designer/SKILL.md).
Feature-based re-ranking of CF candidates: [learning-to-rank-model-builder](../learning-to-rank-model-builder/SKILL.md).

## Workflow

```
1. SPLIT     -> temporal_split.py (recommendation-system-designer) -> train.csv / test.csv
2. KNN       -> python scripts/itemknn.py train.csv --min-rating 4 --k 10 -o recs_knn.csv
3. MF        -> python scripts/gen_mf_script.py --train train.csv --min-rating 4 --k 10 -o mf.py; python mf.py
4. EVALUATE  -> rec_eval.py --recs recs_all.csv --test test.csv --train train.csv --k 10 --min-rating 4
5. TUNE      -> signal definition first, then shrink/neighbours (kNN) or lambda/alpha/factors (ALS), lambda (EASE)
6. SHIP      -> the best model plus a popularity fallback for cold users; explanations from item-kNN
```

## Signal Definition Matters Most

On the ratings fixture (NDCG@10 on a leave-last-3 split, relevant = rating >= 4):

| Item-kNN signal | NDCG@10 | Coverage |
|-----------------|---------|----------|
| all interactions as positive (low ratings included) | 0.174 | 0.49 |
| positives only (`--min-rating 4`) | 0.302 | 0.80 |
| positives only, no shrinkage (`--shrink 0`) | 0.350 | 0.86 |
| mean-centred ratings (`--weighted`) | 0.364 | 0.96 |
| popularity baseline | 0.164 | 0.46 |

Treating a 1-star rating as "liked" teaches the model the wrong taste. For implicit data (views, plays,
purchases), weight by count with confidence (ALS) and drop accidental signals (bounces, short plays).

## Models

| Model | Strengths | Key hyperparameters | Fixture NDCG@10 |
|-------|-----------|---------------------|-----------------|
| Item-kNN (`itemknn.py`) | explainable, stable, cheap, strong on small and medium data | similarity, shrink (0-100), neighbours (20-200) | 0.364 |
| ALS (implicit, Hu et al. 2008) | scales, implicit confidence | factors 8-256, lambda 0.1-100, alpha 1-40 | 0.354 |
| EASE (Steck 2019) | closed form, often the strongest simple baseline | lambda 10-1000 | 0.331 |
| BPR | optimises ranking directly | factors, learning rate, epochs, negative sampling | 0.300 |

On this small fixture all four beat popularity clearly. The ordering changes with data size, so tune them
all on validation and pick by the test result. The NumPy ALS matches the `implicit` library (exact solver,
same hyperparameters) on precision, recall, hit rate and coverage, and within 0.011 NDCG (initialisation).
Item cosine similarities match `sklearn.metrics.pairwise.cosine_similarity` to 1e-16.

Algorithms, formulas and library code: [neighbourhood-methods.md](references/neighbourhood-methods.md) and
[matrix-factorisation.md](references/matrix-factorisation.md).

## Tuning Rules

- **Tune on a validation split taken from train** (the generated script holds out each user's last positive),
  then refit on all training data. The test split is touched once.
- **Small or sparse data needs strong regularisation.** ALS chose lambda 50 here. With lambda 0.1-1 it scored
  only 0.174. EASE lambda grows with the catalogue size.
- **Shrinkage** stops item pairs with one or two common users from looking identical. Tune 0-100, and
  expect less of it on dense data.
- **Check coverage and popularity bias** alongside NDCG. A model that wins NDCG by recommending the head of
  the catalogue may lose online.
- **Cold users** (fewer than 3-5 positives) get popularity or content fallbacks. `itemknn.py` fills short lists
  with popular unseen items and marks them.

Scaling (sparse matrices, ANN retrieval, incremental updates) and production notes:
[scaling-and-serving.md](references/scaling-and-serving.md).

## Output Format

When implementing CF, deliver:
1. **Signal** - what counts as positive and how it is weighted.
2. **Models and tuning** - validation grid results and the chosen hyperparameters.
3. **Test comparison** - rec_eval.py table: kNN, ALS/EASE/BPR, popularity; coverage and bias included.
4. **Recommendations** - top-k CSV with explanations (kNN) and the cold-start fallback.
5. **Next steps** - re-ranking with features, an A/B test, retraining cadence.

## Scripts

```bash
python scripts/itemknn.py train.csv --k 10 -o recs.csv
python scripts/itemknn.py ratings_train.csv --min-rating 4 --similarity cosine --shrink 10 --neighbors 50 -o recs.csv
python scripts/itemknn.py events.csv --user-col visitor --item-col product --similarity asymmetric --alpha 0.7
```
Output columns: user_id, item_id, rank, score, because. Exit codes: 0 written, 2 usage or read error.

```bash
python scripts/gen_mf_script.py --train ratings_train.csv --min-rating 4 --k 10 -o mf.py
python scripts/gen_mf_script.py --train events.csv --user-col visitor --item-col product --models als ease --k 20
```
The generated script writes `recs_<model>.csv` and `recs_all.csv` (with a model column). Exit codes: 0
written, 2 usage error.

## Additional Resources

| File | Content |
|------|---------|
| [neighbourhood-methods.md](references/neighbourhood-methods.md) | item/user kNN, similarities, shrinkage, normalisation, explanations, co-occurrence |
| [matrix-factorisation.md](references/matrix-factorisation.md) | explicit MF, implicit ALS, BPR, EASE, hyperparameters, `implicit` / LightFM / surprise code |
| [scaling-and-serving.md](references/scaling-and-serving.md) | sparse data structures, ANN retrieval, incremental updates, batch vs online, monitoring |
