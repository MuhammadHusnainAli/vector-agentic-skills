# Scaling and Serving CF

## Data structures

- Store interactions as a sparse CSR matrix (users x items) with contiguous integer ids. Keep the id mapping
  tables versioned with the model.
- Item-item similarities: keep only the top-k neighbours per item (a sparse matrix). The full item x item
  matrix does not fit for large catalogues.
- Counting co-occurrences scales as the sum over users of (items per user)^2. Cap very heavy users (bots,
  resellers) or sample their history.

## Retrieval at scale

| Model | Serving |
|-------|---------|
| Item-kNN | precomputed neighbour lists; score = sum over the user's recent items |
| ALS / BPR | user vector . item vectors; ANN index (FAISS, ScaNN, HNSW) for millions of items |
| EASE | X_u B for the user's history row; B can be sparsified (keep the top weights) |

Filter seen and unavailable items after retrieval (retrieve more, e.g. k + 100, then filter).

## Freshness

- Retrain nightly or weekly, depending on catalogue churn.
- Fold in new users without retraining. With ALS, solve the user equation against the fixed item factors
  (`model.recommend(..., recalculate_user=True)` in `implicit`). With kNN, use their latest items directly.
- New items have no CF signal until they get interactions. Use content similarity or exploration slots.

## Batch vs online

| Pattern | When |
|---------|------|
| Batch top-N per user stored in a KV store | email, daily feeds, large user bases with slow-changing tastes |
| Online scoring with precomputed factors / neighbours | on-site widgets reacting to the current session |
| Session-based item-to-item | anonymous users |

## Monitoring

- Recommendation coverage, personalisation and popularity bias per day: sudden drops signal id-mapping or
  pipeline bugs.
- The share of fallback (popularity) recommendations: rising means more cold users or broken history joins.
- Online CTR and conversion per model version, and offline metrics for each retrain against the previous
  model on the same split.
