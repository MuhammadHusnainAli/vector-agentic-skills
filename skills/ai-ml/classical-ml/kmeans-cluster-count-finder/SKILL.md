---
name: kmeans-cluster-count-finder
description: "Choose the number of clusters k for k-means (and k-means-like methods) with evidence instead of a single elbow plot: inertia elbow via the kneedle method, silhouette, Calinski-Harabasz, Davies-Bouldin, the gap statistic against uniform reference data (which also detects that there is no structure at all), bootstrap stability (adjusted Rand index on overlapping subsamples), BIC for Gaussian mixtures, cluster-size floors and business usefulness, then profile the chosen clusters (sizes, standardised feature differences, over-represented categories, outcome by cluster) so they can be named and acted on. Pure-Python k-means++ sweep validated against scikit-learn. Use when someone asks how many clusters to use, gets an ambiguous elbow plot, wants silhouette or gap statistic analysis, or needs to name and sanity-check k-means segments."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# k-Means Cluster Count Finder

There is no true k; there is a k that the data supports and a k the business can use. Look at several
criteria, because each fails differently: the elbow is often vague, silhouette favours few well-separated
groups, Calinski-Harabasz grows with k on large data, and the **gap statistic** is the one that notices when
the data is no more clustered than noise. Then check **stability** (does the same partition come back?) and
**profiles** (can each cluster be named and acted on?). `scripts/k_sweep.py` runs the sweep and votes;
`scripts/cluster_profile.py` profiles the clusters you keep.

## Trigger Conditions

Activate this skill when the user:
- Asks "how many clusters should I use?" or shows an elbow plot without a clear elbow
- Wants silhouette, gap statistic, Calinski-Harabasz, Davies-Bouldin or BIC analysis
- Must pick between, say, 4 and 6 customer segments
- Has k-means clusters and needs to describe, name or validate them
- Suspects the clusters are arbitrary

Choosing the algorithm itself: [clustering-algorithm-selector](../clustering-algorithm-selector/SKILL.md);
density-based alternatives without k: [dbscan-parameter-tuner](../dbscan-parameter-tuner/SKILL.md).

## Workflow

```
1. PREPARE  -> same features and scaling you will use in production (see clustering-algorithm-selector)
2. SWEEP    -> python scripts/k_sweep.py data.csv --drop id --k-min 2 --k-max 10 --b 5
3. READ     -> votes + table; stability >= 0.8 at the chosen k; no tiny clusters; gap > 0.25
4. BUSINESS -> which k gives segments that need different actions? capacity for k strategies?
5. FIT      -> KMeans(n_clusters=k, n_init="auto", random_state=0) on all data
6. PROFILE  -> python scripts/cluster_profile.py segments.csv --label cluster --outcome churned
7. NAME     -> one plain-language name per cluster from its top distinguishing features
```

## The Criteria and How They Fail

| Criterion | Choose k where | Fails when |
|-----------|----------------|------------|
| Inertia elbow (kneedle) | curvature is largest | curve is smooth (no elbow); always decreases |
| Silhouette | mean silhouette is highest | prefers k = 2 for elongated or nested structure; expensive (O(n²)) |
| Calinski-Harabasz | ratio is highest | grows with k on large datasets |
| Davies-Bouldin | index is lowest | favours compact spherical clusters |
| Gap statistic | first k with gap(k) >= gap(k+1) − s(k+1) | slower; uniform reference in the bounding box is crude for correlated data |
| Stability (ARI across subsamples) | partitions reproduce (ARI > 0.8) | stable is necessary, not sufficient (uniform data splits stably) |
| BIC (Gaussian mixtures) | BIC minimum / elbow | spends components on outliers |
| Business | segments map to distinct actions | k chosen before looking at data |

## Reading k_sweep.py

```
  k     inertia silhouette        CH     DB stability     gap  sizes
  3       188.9      0.676     559.2  0.461      0.98   1.923  [102, 100, 98]
  4       155.6      0.689     471.9  0.789      0.99   1.884  [100, 98, 98, 4]
  6       111.1      0.703     417.4  0.528      0.80   1.908  [98, 98, 96, 3, 3, 2]
votes: elbow=3, silhouette=6, calinski_harabasz=3, davies_bouldin=3, gap=3
RECOMMENDED k = 3 (4 of 5 criteria; stability ARI 0.98)
```
Silhouette prefers k = 6 only by splitting off 2-3-point noise clusters (see `sizes`): always read cluster
sizes next to the indices. On the uniform fixture every index votes k = 4, yet the gap statistic is <= 0.05
for every k: the script reports **NO CLEAR k**, because k-means cuts uniform data into stable but
meaningless quadrants.

Formulas, computational cost and scikit-learn / yellowbrick equivalents:
[choosing-k-methods.md](references/choosing-k-methods.md). The script's inertia, silhouette, CH and DB values
match scikit-learn on the blobs fixture.

## Business Rules for k

- **Actionability:** k <= the number of distinct treatments the team can run.
- **Minimum size:** each cluster >= 2-5% of rows (or a minimum count) unless tiny clusters are the point
  (anomalies).
- **Interpretability:** every cluster has a name from 1-3 distinguishing features.
- **Stability over time:** re-fit next month; segments persist and membership changes are explainable.
- When two k values are close on the criteria, choose the one with the clearer profiles.

## Profiling and Naming

```
cluster 3: 58 rows (14.5%), churned mean 0.379
  last_login_days   mean 35.26 vs 8.041 elsewhere  (d +3.45, higher)      -> "dormant"
cluster 0: 45 rows (11.2%), churned mean 0.467
  support_calls     mean 4.756 vs 0.707 elsewhere  (d +3.85, higher)      -> "support-heavy"
cluster 1: 103 rows (25.8%), churned mean 0.136
  plan=premium      97% vs 32% overall (lift 3.0x)                         -> "premium"
```
`cluster_profile.py` ranks features by the standardised difference (Cohen's d) between a cluster and the rest,
lists over-represented categories, compares a business outcome across clusters, and warns about tiny or
featureless clusters. Naming and reporting guidance: [interpreting-segments.md](references/interpreting-segments.md).

## k-Means Practicalities

| Issue | Practice |
|-------|----------|
| Initialisation | k-means++ with `n_init="auto"` (or 10+); fix `random_state` |
| Scaling | standardise; log1p skewed features first |
| Outliers | cap or remove; they become singleton clusters or drag centroids |
| Large data | `MiniBatchKMeans`; choose k on a sample |
| Non-spherical clusters | GMM, HDBSCAN or spectral instead |
| Categorical features | k-prototypes / k-modes, not one-hot k-means |
| Medoids needed (actual rows as centres, robust) | k-medoids (`sklearn_extra` / `kmedoids`) |
| Hierarchy of segments | bisecting k-means (`BisectingKMeans`) or Ward |

More in [kmeans-practice.md](references/kmeans-practice.md).

## Output Format

When choosing k, deliver:
1. **Sweep table** - inertia, silhouette, CH, DB, stability, gap and sizes per k (`k_sweep.py`).
2. **Votes and recommendation** - or "no clear k" with the reason.
3. **Business check** - actionability, size floor, interpretability for the candidate k values.
4. **Profiles** - per cluster: size, top distinguishing features, categories, outcome (`cluster_profile.py`).
5. **Names and actions** - a name and the intended action per cluster.
6. **Stability plan** - refit cadence and how membership changes will be monitored.

## Scripts

```bash
python scripts/k_sweep.py data.csv --drop customer_id --k-max 10
python scripts/k_sweep.py data.csv --columns x1 x2 x3 --k-min 2 --k-max 8 --b 10 --json
python scripts/k_sweep.py data.csv --no-scale --n-init 10 --max-rows 3000
```
Pure-Python k-means++ (best of `--n-init`) on standardised numeric columns for each k: inertia, sampled silhouette,
Calinski-Harabasz, Davies-Bouldin, stability ARI on overlapping 80% subsamples, gap statistic with `--b` uniform
references (0 = skip), cluster sizes; votes from elbow (kneedle), silhouette, CH, DB and gap; recommendation or
"no clear k" (criteria spread, weak silhouette, unstable winner, gap < 0.25). Exit codes: 0 clear
recommendation, 1 no clear k, 2 usage error.

```bash
python scripts/cluster_profile.py segments.csv --label cluster
python scripts/cluster_profile.py segments.csv --label cluster --outcome churned --drop customer_id --top 4 --json
```
Per cluster (noise label -1 shown last): size and share, numeric features ranked by Cohen's d vs the rest,
categorical levels with the highest lift, outcome mean; warnings for clusters below `--min-share` or without a
distinguishing feature, and for outcomes that barely differ. Exit codes: 0 profiled, 2 usage error.

## Additional Resources

| File | Content |
|------|---------|
| [choosing-k-methods.md](references/choosing-k-methods.md) | Elbow/kneedle, silhouette, CH, DB, gap statistic, stability, BIC/AIC, information criteria for k-means, scikit-learn and yellowbrick code |
| [kmeans-practice.md](references/kmeans-practice.md) | Initialisation, scaling, outliers, MiniBatch, empty clusters, k-medoids, bisecting k-means, assigning new rows, refreshing segments |
| [interpreting-segments.md](references/interpreting-segments.md) | Profiling, Cohen's d and lift, naming, segment cards, outcome validation, communicating segments |
