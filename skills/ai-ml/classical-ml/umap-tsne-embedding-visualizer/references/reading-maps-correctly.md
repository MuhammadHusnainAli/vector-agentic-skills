# Reading Maps Correctly

| # | Misreading | Reality | Check |
|---|-----------|---------|-------|
| 1 | "This cluster is bigger, so the group is more diverse" | t-SNE equalises densities; UMAP partly too | compare within-cluster distances in the original space; densMAP |
| 2 | "Clusters A and B are far apart, so they are very different" | inter-cluster distances are not preserved (t-SNE especially) | distances between cluster centroids in the original space |
| 3 | "There are 7 clusters" | perplexity / n_neighbors change the count | grid over parameters and seeds; clustering in the original space |
| 4 | "These points are outliers" / "there are no outliers" | outliers are pulled into nearby clusters (seen on the blobs fixture) or appear as fake islands | outlier detection in the original space |
| 5 | "The map shows two groups" in pure noise | small perplexity produces clumps even in random data | run on shuffled data; trustworthiness |
| 6 | "Points along this curve form a trajectory" | gradients can be cut or bent arbitrarily | colour by the variable; PCA view |
| 7 | "Model separates classes well, look at the map" | the map can separate classes the model cannot (or hide separation) | label k-NN accuracy original vs map (embedding_trust.py) |
| 8 | "The layout changed, so the data changed" | different seeds give rotated/reflected/rearranged layouts | fix seeds; compare neighbourhoods, not positions |
| 9 | "Supervised UMAP shows the labels are separable" | it used the labels | unsupervised map for evidence; supervised only for display |
| 10 | "Clusters on the t-SNE plot, let's run k-means on its coordinates" | t-SNE coordinates distort density and distance | cluster on original / PCA / 10-20-D UMAP space |

## Sanity checks before presenting a map

1. Same structure in at least two seeds and two parameter values.
2. PCA baseline shown alongside (with explained variance).
3. Trustworthiness / continuity reported (> 0.9 for strong claims).
4. Any "cluster" claim confirmed by clustering in a faithful space and by profiling.
5. Caption: "Positions show neighbourhoods; sizes and distances between groups are not to scale."

## A null check

Shuffle each feature column independently (destroys structure), embed with the same parameters: if the map
of shuffled data shows "clusters" similar to the real one, the real clusters are not evidence.
