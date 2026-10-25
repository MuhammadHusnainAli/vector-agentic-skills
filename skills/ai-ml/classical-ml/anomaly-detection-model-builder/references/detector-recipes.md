# Detector Recipes

`X_ref` = reference (mostly normal) data, `X_new` = data to score; scale with a scaler fitted on `X_ref`.

## Robust z-score and IQR

```python
import numpy as np
med = np.median(X_ref, axis=0)
mad = np.median(np.abs(X_ref - med), axis=0) * 1.4826
rz = np.abs((X_new - med) / np.where(mad == 0, 1e-9, mad))
score = rz.max(axis=1)                          # flag score > 3.5 (or budget)
q1, q3 = np.percentile(X_ref, [25, 75], axis=0)
iqr_flag = ((X_new < q1 - 1.5 * (q3 - q1)) | (X_new > q3 + 1.5 * (q3 - q1))).any(axis=1)
```

## Mahalanobis with robust covariance

```python
from sklearn.covariance import MinCovDet, EllipticEnvelope
mcd = MinCovDet(random_state=0).fit(X_ref)
score = np.sqrt(mcd.mahalanobis(X_new))
env = EllipticEnvelope(contamination=0.01, random_state=0).fit(X_ref)    # thresholded version
```
Squared Mahalanobis distances of Gaussian data follow χ²(p): `scipy.stats.chi2.ppf(0.999, p)` as a cut.

## k-NN distance

```python
from sklearn.neighbors import NearestNeighbors
nn = NearestNeighbors(n_neighbors=5).fit(Z_ref)
dist, _ = nn.kneighbors(Z_new)                 # when scoring the reference itself use n_neighbors=k+1 and drop self
score = dist[:, -1]
```

## Local Outlier Factor

```python
from sklearn.neighbors import LocalOutlierFactor
lof = LocalOutlierFactor(n_neighbors=20, novelty=True).fit(Z_ref)   # novelty=True to score new data
score = -lof.score_samples(Z_new)                                   # higher = more anomalous
```
With `novelty=False` (default), use `fit_predict` / `negative_outlier_factor_` on the same data only.

## Isolation Forest

```python
from sklearn.ensemble import IsolationForest
iso = IsolationForest(n_estimators=300, max_samples=256, contamination="auto", random_state=0).fit(X_ref)
score = -iso.score_samples(X_new)                                   # higher = more anomalous
flag = iso.predict(X_new) == -1                                     # uses the contamination threshold
```
No scaling needed (splits per feature); `max_features` < 1.0 for many noisy features.

## One-class SVM

```python
from sklearn.svm import OneClassSVM
oc = OneClassSVM(kernel="rbf", nu=0.01, gamma="scale").fit(Z_ref)
score = -oc.decision_function(Z_new)
```
Scale features; tune `nu` (upper bound on the outlier fraction) and `gamma`. `SGDOneClassSVM` for large data.
Sensitivity is real: on the sensor fixture these settings reach PR-AUC 0.36, while MinCovDet Mahalanobis (0.98),
LOF (0.96) and Isolation Forest (0.94-0.98) need no tuning. Start with the tuning-free detectors.

## Reconstruction error

```python
from sklearn.decomposition import PCA
pca = PCA(n_components=0.9).fit(Z_ref)
recon = pca.inverse_transform(pca.transform(Z_new))
score = ((Z_new - recon) ** 2).sum(axis=1)                          # the Q / SPE statistic
```
Autoencoders (PyTorch/Keras) generalise this for non-linear structure; train only on normal data.

## PyOD

PyOD wraps 40+ detectors with a common API (`fit`, `decision_function`, `decision_scores_`), including ECOD
and COPOD (fast, parameter-free), HBOS, and ensembles (`SUOD`).
```python
from pyod.models.ecod import ECOD
clf = ECOD().fit(X_ref); score = clf.decision_function(X_new)
```

## Ensembles

Different detectors find different anomaly types. Combine by rank (average of rank-normalised scores, as in
`anomaly_scores.py`) or by maximum rank; normalising raw scores with z-scores is fragile because detectors'
score distributions differ.
