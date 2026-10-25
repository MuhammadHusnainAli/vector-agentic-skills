---
name: umap-tsne-embedding-visualizer
description: "Make and read 2-D maps of high-dimensional data (tabular features, embeddings from text/image models, single-cell style data) with UMAP, t-SNE and PCA without being misled: scaling or L2 normalisation, PCA pre-reduction to ~50 dimensions, UMAP n_neighbors/min_dist/metric and t-SNE perplexity/early exaggeration/learning rate/init choices, multiple seeds and parameter grids, colouring by labels or numeric values, transforming new points, and quantitative faithfulness checks: trustworthiness, continuity, k-NN preservation, pairwise-distance correlation and label k-NN accuracy in the original space vs the map. Explains what maps can and cannot show (cluster sizes, inter-cluster distances, density and outliers are unreliable). Use when someone wants to visualise embeddings or clusters, asks UMAP vs t-SNE, how to set perplexity or n_neighbors, why their t-SNE plot shows clusters that are not real, or needs a reproducible plotting script."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# UMAP / t-SNE Embedding Visualizer

A 2-D map of high-dimensional data is a picture of **neighbourhoods**, not of distances. t-SNE and UMAP
preserve who is near whom; they distort cluster sizes, the gaps between clusters, density and the position
of outliers. PCA preserves global variance but squashes non-linear structure. Use all three, several
parameter values and seeds, and measure faithfulness instead of trusting the prettiest plot.
`scripts/gen_embedding_plot.py` writes a reproducible plotting script (PCA pre-reduction, sized parameters,
optional grid of parameters x seeds, saved coordinates); `scripts/embedding_trust.py` scores any map against
the original data (trustworthiness matches scikit-learn).

## Trigger Conditions

Activate this skill when the user:
- Wants to visualise embeddings (sentence/image/user embeddings), clusters or high-dimensional features in 2-D
- Asks UMAP vs t-SNE vs PCA, or how to choose perplexity, n_neighbors, min_dist or the metric
- Sees clusters in a t-SNE/UMAP plot and wants to know whether they are real
- Gets different-looking maps with different seeds or parameters
- Needs to place new points on an existing map, or to use the embedding as input to clustering

Clustering on reduced data: [clustering-algorithm-selector](../clustering-algorithm-selector/SKILL.md);
linear reduction and component counts: [pca-dimensionality-reducer](../pca-dimensionality-reducer/SKILL.md).

## Workflow

```
1. PREPARE   -> numeric features standardised (or embeddings L2-normalised); drop IDs/labels from features
2. GENERATE  -> python scripts/gen_embedding_plot.py data.csv --label segment --drop id --grid -o plot.py
3. RUN       -> python plot.py   -> embedding_{pca,umap,tsne}.png + .csv
4. COMPARE   -> do structures persist across seeds and parameters? across methods?
5. MEASURE   -> python scripts/embedding_trust.py --high data.csv --low embedding_umap.csv --label segment --drop id
6. INTERPRET -> neighbourhoods and separations only; confirm any "cluster" in the original space
7. REPORT    -> method, parameters, seeds, metrics; caption that sizes and distances are not meaningful
```

## Choosing the Method

| Goal | Method | Why |
|------|--------|-----|
| Honest global picture, linear structure, variance explained | PCA | distances and directions preserved (up to projection) |
| Local neighbourhoods, separated groups, fast, can embed new points | UMAP | good local structure, more global structure than t-SNE, `transform()` |
| Fine local structure on small/medium data | t-SNE | excellent local detail; slow on big data; no transform in scikit-learn |
| Input to clustering (HDBSCAN) | UMAP to 5-20 dims, `min_dist=0.0` | keeps density contrast; never cluster on t-SNE coordinates |
| Supervised map (show how labels separate) | UMAP with `y=` | uses labels; for display, not validation |

## Parameters That Matter

| Method | Parameter | Effect | Start |
|--------|-----------|--------|-------|
| UMAP | `n_neighbors` | small = local detail, fragmented; large = global shape, merged | 15 (5-50) |
| UMAP | `min_dist` | how tightly points pack; 0.0 for clustering, 0.1-0.5 for display | 0.1 |
| UMAP | `metric` | cosine for embeddings, euclidean for scaled features, haversine for coordinates | euclidean |
| t-SNE | `perplexity` | effective neighbourhood size; must be < n/3 | 30 (5-50) |
| t-SNE | `init="pca"` | stable, more faithful global layout than random | pca |
| t-SNE | `learning_rate="auto"`, `max_iter>=1000` | convergence | auto |
| both | `random_state` | different seeds give different layouts; check several | fix + vary |
| both | PCA to 50 dims first | denoises, speeds up neighbour search | when > 50 features |

The generator uses perplexity ≈ min(30, max(5, sqrt(n)/2)) and n_neighbors 15 (10 for small data), and `--grid`
renders 3 values x 2 seeds. More detail and other methods (PaCMAP, TriMap, openTSNE, densMAP):
[method-guide.md](references/method-guide.md).

## Measuring Faithfulness

```
120 rows: 8-D original vs 2-D embedding (UMAP), k = 10
trustworthiness  0.954   continuity 0.956   kNN preservation 0.580   distance Spearman 0.725
same data, PCA:  trustworthiness 0.931  distance Spearman 0.967
```
| Metric | Question | Rule of thumb |
|--------|----------|---------------|
| Trustworthiness | are map neighbours real neighbours? | > 0.9 good; < 0.8 the map invents closeness |
| Continuity | are real neighbours kept together? | > 0.9 good |
| kNN preservation | share of exact k-NN kept | 0.3-0.6 typical for 2-D |
| Distance Spearman | is global geometry kept? | high for PCA, lower for t-SNE/UMAP by design |
| Label k-NN accuracy, map vs original | does the map exaggerate or hide separation? | gap > 0.1 is a warning |

## Reading Maps Without Being Fooled

- **Cluster size** in t-SNE/UMAP says little about spread or count in the original space.
- **Distances between clusters** are not interpretable (especially t-SNE).
- **Apparent clusters** can appear in noise (small perplexity / n_neighbors): confirm with clustering in
  the original or a 10-20-D UMAP space, and with stability across seeds.
- **Outliers get absorbed**: on the blobs fixture UMAP places the planted noise points inside the nearest
  cluster. Detect outliers in the original space.
- **Continuous gradients** (e.g. tenure) can be cut into islands; colour by numeric variables to see them.
- **Colour encodes the story**: colour by label, by predicted score, by a key feature; one map, several
  colourings.

Ten common misreadings with examples: [reading-maps-correctly.md](references/reading-maps-correctly.md).

## Output Format

When producing or reviewing a map, deliver:
1. **Preprocessing** - features, scaling or normalisation, PCA pre-reduction.
2. **Method(s) and parameters** - including seeds; grid if used.
3. **Figures** - PCA baseline plus UMAP/t-SNE, coloured meaningfully.
4. **Faithfulness** - `embedding_trust.py` metrics per map.
5. **Interpretation** - what the map supports (neighbourhoods, separations) and what it does not
   (sizes, distances), with any cluster claim confirmed in the original space.
6. **Code** - the generated script (reproducible: fixed seeds, saved coordinates).

## Scripts

```bash
python scripts/gen_embedding_plot.py data.csv --label segment --drop id -o plot_embedding.py
python scripts/gen_embedding_plot.py emb.csv --methods umap tsne pca --grid --metric cosine
python scripts/gen_embedding_plot.py data.csv --methods tsne --label y --perplexity 50
```
Writes a script that standardises (or L2-normalises for cosine), PCA-reduces to 50 dims when wider, runs PCA /
UMAP / t-SNE with data-sized defaults (or a 3-parameter x 2-seed grid), colours by a categorical or numeric
column, and saves `embedding_<method>.png` and `.csv`. Verified with scikit-learn 1.9, umap-learn 0.5 and
matplotlib 3.11. Exit codes: 0 written, 2 usage or read error.

```bash
python scripts/embedding_trust.py --high data.csv --low embedding_umap.csv --drop id --label segment
python scripts/embedding_trust.py --high X.csv --low tsne.csv --k 15 --max-rows 1000 --json
```
Trustworthiness and continuity (Venna & Kaski), k-NN preservation, Spearman correlation of sampled pairwise
distances and leave-one-out k-NN label accuracy in both spaces; the original features are standardised. Exit
codes: 0 computed, 2 usage error (row counts differ, no numeric columns).

## Additional Resources

| File | Content |
|------|---------|
| [method-guide.md](references/method-guide.md) | How UMAP and t-SNE work, parameters in depth, PCA pre-reduction, metrics, PaCMAP/TriMap/openTSNE/densMAP, scaling to large data |
| [reading-maps-correctly.md](references/reading-maps-correctly.md) | What maps show and hide: sizes, distances, densities, outliers, fake clusters, gradients, seeds; checks for each |
| [embedding-recipes.md](references/embedding-recipes.md) | Code: UMAP/t-SNE/PCA, supervised UMAP, transforming new points, UMAP for clustering, cosine embeddings, plotting and interactive views |
