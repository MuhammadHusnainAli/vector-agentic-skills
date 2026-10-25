---
name: pca-dimensionality-reducer
description: "Apply PCA correctly for dimensionality reduction, visualisation, decorrelation, compression and monitoring: standardise first (or justify covariance PCA), choose the number of components with cumulative explained variance, scree/elbow, Kaiser's rule and parallel analysis, interpret components through signed loadings, use PCA inside scikit-learn pipelines without leakage (PCA, IncrementalPCA, TruncatedSVD for sparse/text data, KernelPCA, whitening, randomized solver), and detect multivariate outliers and process faults with Hotelling's T² and Q (SPE) residuals and per-feature contributions. Pure-Python PCA report and T²/Q outlier scripts validated against scikit-learn. Use when someone asks how many principal components to keep, whether to scale before PCA, what a component means, wants to reduce features before modelling or clustering, or monitor sensors/processes with PCA."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# PCA Dimensionality Reducer

PCA rotates the data onto orthogonal directions of maximum variance. It is the right tool for correlated
numeric features: compressing them, decorrelating them for linear models, plotting high-dimensional data,
and spotting rows that break the usual correlation pattern. It is the wrong tool when variance is not what
matters (rare but important signals), for non-linear structure (UMAP/t-SNE for visualisation), or when
features are on different scales and nobody standardised them. `scripts/pca_report.py` reports explained
variance, four component-count rules and interpretable loadings, and warns about scaling;
`scripts/pca_outliers.py` scores rows with Hotelling's T² and Q residuals.

## Trigger Conditions

Activate this skill when the user:
- Asks how many principal components to keep, or reads a scree plot
- Asks whether to standardise before PCA, or why PC1 is "just one feature"
- Wants to reduce many correlated features before regression, clustering or k-NN
- Needs to interpret components (what does PC2 mean?)
- Wants PCA on text/TF-IDF or other sparse data (TruncatedSVD) or on data that does not fit in memory
- Monitors sensors, processes or KPIs for multivariate anomalies (T², SPE/Q charts)

Non-linear 2-D visualisation: [umap-tsne-embedding-visualizer](../umap-tsne-embedding-visualizer/SKILL.md);
choosing features by relevance to a target: [feature-selection-analyzer](../feature-selection-analyzer/SKILL.md);
general anomaly detection: [anomaly-detection-model-builder](../anomaly-detection-model-builder/SKILL.md).

## Workflow

```
1. SCALE     -> standardise (correlation PCA) unless all features share units and their variance matters
2. REPORT    -> python scripts/pca_report.py data.csv --drop id label
3. CHOOSE k  -> parallel analysis for "real" structure; cumulative variance (90-95%) for model inputs
4. INTERPRET -> top signed loadings per component; name components only when loadings are clear
5. USE       -> Pipeline([("scale", StandardScaler()), ("pca", PCA(k)), ("model", ...)]) fitted on train only
6. MONITOR   -> python scripts/pca_outliers.py --train reference.csv --score new.csv --k K   (T², Q)
```

## Scale First (Usually)

| Data | PCA on |
|------|--------|
| Features in different units (money, counts, days) | correlation matrix: standardise first |
| Same units and variance is meaningful (pixel intensities, spectra, returns of similar assets) | covariance matrix (no scaling) |
| Sparse counts / TF-IDF | TruncatedSVD (no centring) |

`pca_report.py --no-scale` on the wide fixture: `revenue_usd` (std ~1000) holds 100% of the variance, so PC1
*is* revenue. Standardised, the same data shows two real factors (PC1 46%, PC2 28%).

## Choosing the Number of Components

| Rule | Keep components | Use for |
|------|-----------------|---------|
| Cumulative variance | until 80/90/95% | compression, model inputs (pick by downstream CV score if possible) |
| Scree / elbow | before the curve flattens | quick visual |
| Kaiser | eigenvalue > 1 (correlation PCA) | rough; tends to over-keep with many features |
| Parallel analysis (Horn) | eigenvalue above that of column-shuffled data | "how many real dimensions?"; the most reliable rule |
| Downstream CV | the k that maximises the model's CV score | when PCA feeds a model |

Wide fixture: 2 by parallel analysis (the two planted factors), 3 by Kaiser, 4 for 90%, 5 for 95%: different
questions, different answers. Details and formulas: [choosing-components.md](references/choosing-components.md).

## Interpreting Components

```
PC1 (46.0%): f4 +0.45, f2 +0.45, f1 +0.45     -> a common "factor A" across f1-f5
PC2 (27.8%): f8 +0.58, f6 +0.58, f7 +0.57     -> "factor B" across f6-f8
PC3 (10.2%): f9 +0.83, revenue_usd -0.56      -> noise columns, no shared meaning
```
- Loadings are the weights of original (standardised) features; signs are arbitrary per component (the
  script makes the largest loading positive).
- Name a component only when a few features dominate with a coherent story; later components are often noise.
- Varimax rotation (factor analysis) gives more interpretable axes when interpretation is the goal.

## PCA in Pipelines

```python
from sklearn.decomposition import PCA
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

model = make_pipeline(StandardScaler(), PCA(n_components=0.95, svd_solver="full"), LogisticRegression(max_iter=2000))
```
- Fit inside the pipeline (CV refits PCA per fold): PCA on all data before splitting leaks test structure.
- `n_components=0.95` keeps enough components for 95% variance; tune k with CV when PCA feeds a model.
- PCA rarely helps tree ensembles (they handle correlated features) and hurts interpretability; it helps
  linear models with collinearity, k-NN/k-means (distance concentration), and speed.
- Sparse / text: `TruncatedSVD(n_components=100)` (LSA); out-of-core: `IncrementalPCA(batch_size=...)`;
  non-linear: `KernelPCA(kernel="rbf")`; large dense data: `svd_solver="randomized"`.

Variants, whitening and inverse transforms: [pca-in-practice.md](references/pca-in-practice.md).

## Multivariate Outliers and Monitoring

```
PCA with 2 components (70.7% variance) fitted on 300 rows; limits at the 0.99 training quantile: T2 14.2, Q 4.44
  line 42: Q    T2 14.2  Q 39.6  top Q contributors: temperature +4.04, vibration +3.73, pressure -3.06
  line 43: T2   T2 68.3  Q 1.31
against is_anomaly: precision 0.83, recall 0.83
```
- **T²**: unusually far along normal directions (a big but consistent excursion).
- **Q / SPE**: the row breaks the correlation structure (sensor fault, new regime); contributions show which
  features.
- Fit on a clean reference period; set limits from it; score new data. Theory and control-limit options:
  [pca-monitoring.md](references/pca-monitoring.md).

## Output Format

When applying PCA, deliver:
1. **Scaling decision** and why.
2. **Variance table** - explained and cumulative per component (`pca_report.py`).
3. **k** - the rules' answers and the chosen k for the purpose (structure vs compression vs model input).
4. **Interpretation** - top loadings for the kept components, names where justified.
5. **Pipeline code** - scaler + PCA + model, fitted on training folds.
6. **Monitoring** (if relevant) - T²/Q limits, flagged rows, contributing features (`pca_outliers.py`).

## Scripts

```bash
python scripts/pca_report.py data.csv --drop id label
python scripts/pca_report.py data.csv --columns f1 f2 f3 f4 --top 4 --targets 0.9 0.99
python scripts/pca_report.py data.csv --no-scale --json
```
Pure-Python PCA (Jacobi eigendecomposition) on the correlation or covariance matrix: explained and cumulative
variance, components needed for each target share, Kaiser count, parallel analysis with column-shuffled data
(`--pa-runs`, `--pa-quantile`), top signed loadings per component, and an unscaled-dominance warning. Matches
scikit-learn's explained variance ratios and loadings. Exit codes: 0 printed, 2 usage error.

```bash
python scripts/pca_outliers.py --train reference.csv --score new.csv --drop id --k 2
python scripts/pca_outliers.py --train sensors.csv --drop reading_id --label is_anomaly --var 0.9 --alpha 0.995
```
Fits standardised PCA on `--train` (k from `--k` or `--var`), computes Hotelling's T² and Q residuals for the
scored rows, empirical control limits at `--alpha`, flagged rows with the top Q-contributing features, and
precision/recall against a `--label` column. Imports `pca_report.py` from the same folder. Exit codes: 0 scored,
2 usage error.

## Additional Resources

| File | Content |
|------|---------|
| [choosing-components.md](references/choosing-components.md) | Explained variance, scree, Kaiser, parallel analysis, Velicer MAP, CV-based choice, broken-stick |
| [pca-in-practice.md](references/pca-in-practice.md) | scikit-learn PCA options, whitening, inverse_transform, IncrementalPCA, TruncatedSVD, KernelPCA, sparse PCA, factor analysis, pitfalls |
| [pca-monitoring.md](references/pca-monitoring.md) | Hotelling T², Q/SPE, control limits (empirical, F, Jackson-Mudholkar), contribution plots, reference-period design |
