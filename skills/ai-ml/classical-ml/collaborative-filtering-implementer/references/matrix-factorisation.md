# Matrix Factorisation

## Explicit ratings (biased MF / "Funk SVD")

```
r_hat(u, i) = mu + b_u + b_i + p_u . q_i
minimise sum over observed (r - r_hat)^2 + lambda (|p_u|^2 + |q_i|^2 + b_u^2 + b_i^2)
```
SGD or ALS on observed ratings only. It optimises RMSE, which rarely matches a ranked list, so evaluate the
ranking anyway. Libraries: `surprise.SVD`, `surprise.SVDpp`.

## Implicit ALS (Hu, Koren & Volinsky 2008)

```
p(u, i) = 1 if the user interacted, else 0         (preference)
c(u, i) = 1 + alpha * r(u, i)                       (confidence; r = count / plays / weight)
minimise sum over ALL (u, i) of c(u, i) (p(u, i) - x_u . y_i)^2 + lambda (|x_u|^2 + |y_i|^2)
x_u = (Y'Y + Y'(C_u - I)Y + lambda I)^-1 Y' C_u p(u)       (closed form per user; same for items)
```
- The `Y'Y` trick makes each update cost O(f^2 * n_u + f^3).
- Hyperparameters: factors 8-256 (more with more data), lambda 0.1-100 (strong for sparse data), alpha 1-40
  (or log scaling: c = 1 + alpha log(1 + r / eps)), iterations 10-20.

```python
import scipy.sparse as sp
from implicit.als import AlternatingLeastSquares
model = AlternatingLeastSquares(factors=64, regularization=10.0, alpha=20.0, iterations=15, random_state=0)
model.fit(user_items)                                  # users x items CSR (implicit >= 0.5)
ids, scores = model.recommend(uid, user_items[uid], N=10, filter_already_liked_items=True)
similar_ids, sims = model.similar_items(item_id, N=10)
```

## BPR (Rendle et al. 2009)

Maximises `sum log sigmoid(x_ui - x_uj)` over (user, positive item, sampled negative item) triples. It
optimises AUC-like ranking directly. Negative sampling matters: uniform sampling is the default, and
popularity-based sampling gives harder negatives. Libraries: `implicit.bpr.BayesianPersonalizedRanking`,
LightFM (`loss="bpr"` or `"warp"`, where WARP is often better for top-k).

## EASE (Steck 2019)

```
G = X'X + lambda I ;  P = G^-1 ;  B = -P / diag(P) (column-wise) ; diag(B) = 0 ;  scores = X B
```
EASE is a closed-form item-item linear model with no latent factors, and is often the strongest simple
model on benchmark datasets. Cost: an items x items inverse (fine below ~20-50k items). lambda: 10-1000+,
larger for bigger catalogues.

## Hybrid MF with features (LightFM)

```python
from lightfm import LightFM
model = LightFM(no_components=32, loss="warp")
model.fit(interactions, user_features=uf, item_features=itf, epochs=30)
```
Item features (category, brand, text tags) give new items a representation, which helps cold start.

## Practical checks

| Symptom | Likely cause |
|---------|--------------|
| barely beats popularity | lambda too small, factors too many, low ratings treated as positives |
| lists identical across users | over-regularised or too few factors; check personalisation |
| good offline, odd items online | stale factors, id mapping bugs between training and serving |
| NaN or exploding values (BPR) | learning rate too high; clip or lower it |
| results vary run to run | random initialisation: fix seeds, average several runs when comparing |
