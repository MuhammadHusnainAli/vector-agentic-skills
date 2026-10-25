# Deep Learning on Tabular Data

## The default answer

Gradient-boosted trees remain the strongest general choice for medium-sized tabular data (thousands to
millions of rows, heterogeneous features). Several benchmark studies (Grinsztajn et al. 2022, "Why do
tree-based models still outperform deep learning on tabular data?"; Shwartz-Ziv & Armon 2021) found GBMs
ahead on most datasets at a fraction of the tuning cost. Reasons: tabular features are heterogeneous and
non-smooth, many are uninformative, and trees are invariant to monotone transforms.

## When neural networks are worth trying

| Situation | Why NN can help |
|-----------|-----------------|
| Very large data (10M+ rows) with complex interactions | capacity, minibatch training |
| Mixed modalities (tabular + text/images) | one model with embeddings for each |
| Very high-cardinality IDs with lots of data (users, items) | learned embeddings |
| Online / continual learning | incremental updates |
| Ensembling with GBMs | diversity often gives small gains |
| Small data with strong priors (in-context foundation models) | TabPFN-style models trained on synthetic tasks can be strong on small tables |

## What to try (in order of effort)

1. **MLP with good preprocessing**: quantile-transformed numerics, embeddings for categoricals, dropout,
   weight decay, early stopping. A well-tuned MLP is a reasonable NN baseline.
2. **Residual MLP / FT-Transformer** (feature tokenisation + transformer) from libraries such as
   `rtdl` / PyTorch Tabular.
3. **Pretrained tabular foundation models** (TabPFN family) for small datasets: check size limits and licence.

## Practical rules

- Compare against a tuned GBM with the same folds and tuning budget.
- Scale inputs (QuantileTransformer works well); handle missing values explicitly.
- Expect more tuning and compute; budget it before starting.
- If a NN wins by a small margin, consider whether the operational cost (GPU, serving, monitoring) is worth it.
