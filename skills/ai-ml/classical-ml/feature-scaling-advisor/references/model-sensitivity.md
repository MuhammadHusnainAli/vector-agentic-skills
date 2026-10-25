# Why Models Are (or Are Not) Scale-Sensitive

## Distances (k-NN, k-means, DBSCAN, SVM-RBF, hierarchical clustering)

Euclidean distance sums squared differences across features:
```
d(a, b)² = Σ_j (a_j − b_j)²
```
A feature with standard deviation 1,000 contributes ~10⁶ times more than a feature with standard deviation 1.
The model effectively ignores everything but the widest columns. On the churn fixture `total_charges` holds
99.9% of the raw distance variance; scaling lifts 15-NN ROC-AUC from 0.58 to ~0.78 (`scale_impact.py`).

For DBSCAN, `eps` is in the scaled units: rescaling changes which points are neighbours, so tune eps after
scaling.

## Penalties (ridge, lasso, elastic net, regularised logistic regression, SVM)

The penalty λ Σ β_j² (or Σ |β_j|) is unit-dependent: a feature measured in cents needs a coefficient 100x
smaller than the same feature in dollars and is penalised 10,000x less under L2. Without scaling, the
penalty decides importance by units. Standardise numeric features; for one-hot columns scaling is a choice
(it changes how rare levels are regularised).

## Gradients (neural networks, SGD, logistic regression solvers)

Badly scaled inputs give elongated loss surfaces: gradient descent zig-zags and needs tiny learning rates.
Standardised inputs make optimisation faster and more stable. `lbfgs` in LogisticRegression may emit
convergence warnings on unscaled data.

## Variance (PCA)

PCA finds directions of maximum variance. Unscaled, the first component is simply the widest column.
Standardise (= PCA on the correlation matrix) unless all features share units and their variances are
meaningful (e.g. pixel intensities).

## Trees and gradient boosting: invariant

A split `x <= t` partitions rows the same way as `log(x) <= log(t)` or `(x − μ)/σ <= (t − μ)/σ`. Histogram-
based GBMs bin by quantiles, also invariant. Scaling changes nothing except, occasionally, tie-breaking and
floating-point details. Monotone transforms of the **target** do change tree models (different loss).

## Linear regression without penalties

Ordinary least squares predictions are invariant to scaling features; coefficients rescale inversely.
Scaling helps interpretation (coefficients per standard deviation) and numerical conditioning.

## Naive Bayes, LDA/QDA

Gaussian NB models each feature separately: scale-invariant. LDA is invariant to linear rescaling of features
(the classifier adapts); regularised variants are not.

## Quick demonstration (ridge)

```python
import numpy as np
from sklearn.linear_model import Ridge
rng = np.random.default_rng(0)
x1 = rng.normal(0, 1, 500)                # same importance...
x2 = rng.normal(0, 1, 500)
y = x1 + x2 + rng.normal(0, 0.5, 500)
X = np.column_stack([x1, x2 * 1000])      # ...but x2 recorded in different units
print(Ridge(alpha=100).fit(X, y).coef_ * [1, 1000])   # ~[0.85, 0.99]: x1 shrunk, x2 untouched - units drive the penalty
```
