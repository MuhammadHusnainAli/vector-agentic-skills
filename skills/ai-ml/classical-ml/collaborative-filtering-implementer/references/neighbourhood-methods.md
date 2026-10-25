# Neighbourhood Methods

## Item-based kNN

```
sim(i, j)   similarity of item columns over users
N_k(i)      the k most similar items to i
score(u, i) = sum over j in history(u) with i in N_k(j) of sim(j, i) * w(u, j)
```
Item-based kNN is more stable than user-based kNN: items accumulate many interactions, while users often
have few. Similarities can be precomputed offline, and explanations come for free (the history item that
contributed most).

## Similarities

| Similarity | Formula | Notes |
|------------|---------|-------|
| Cosine | dot(i, j) / (\|i\| \|j\|) | default for implicit data |
| Adjusted cosine | cosine after subtracting each user's mean rating | explicit ratings (`itemknn.py --weighted`, mean-centred) |
| Pearson | cosine after subtracting each item's mean | explicit ratings, less common |
| Jaccard | \|U_i and U_j\| / \|U_i or U_j\| | binary data, robust |
| Asymmetric cosine | dot / (\|i\|^(2a) \|j\|^(2(1-a))) | a > 0.5 penalises popular neighbours |
| Conditional probability | P(j \| i) = \|U_i and U_j\| / \|U_i\| | "bought together"; normalise for popularity |
| Lift / PMI | P(i, j) / (P(i) P(j)) | co-occurrence beyond popularity |

## Shrinkage

`sim' = sim * n_ij / (n_ij + lambda)`, where n_ij is the number of common users. Without it, two items
seen together by one user can get similarity 1. Typical lambda is 10-100, tuned on validation. Dense data
needs less (the fixture preferred 0).

## Neighbourhood size

Small k (10-20) gives precise but less diverse lists. Large k (100-500) behaves more like popularity
within taste clusters. Tune k together with shrinkage.

## User-based kNN

`score(u, i) = sum over v in N_k(u) of sim(u, v) * r(v, i)`. Useful for very small catalogues or when
users are stable and rich in history. Otherwise item-based kNN is preferred.

## Explanations

Report the history item with the largest contribution: "Because you liked *Dune*". `itemknn.py` writes it
in the `because` column, or `popular` for fill-ins. Explanations increase trust and help debugging:
nonsensical "because" items reveal noisy signals.

## Libraries

```python
# scikit-learn for similarities on a sparse matrix
from sklearn.metrics.pairwise import cosine_similarity
S = cosine_similarity(X_item_user, dense_output=False)          # X: items x users (csr)
# implicit's kNN
from implicit.nearest_neighbours import CosineRecommender, BM25Recommender
model = BM25Recommender(K=100); model.fit(user_items_csr)
ids, scores = model.recommend(user_id, user_items_csr[user_id], N=10)
```
BM25 weighting of the interaction matrix often beats plain cosine on implicit data.
