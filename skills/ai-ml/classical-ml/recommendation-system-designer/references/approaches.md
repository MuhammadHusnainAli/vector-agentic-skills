# Recommendation Approaches

## Non-personalised

| Method | Notes |
|--------|-------|
| Global popularity | a strong baseline; always report it |
| Recent / trending popularity | time-decayed counts; strong for news and fashion |
| Segment popularity | per country, category, device, new vs returning |
| Association rules / co-occurrence ("bought together") | item-to-item, no user history needed |

## Neighbourhood (memory-based) CF

- **Item-item kNN**: score unseen items by their similarity to items the user interacted with. It is
  stable, explainable ("because you watched X") and strong on small and medium data. Use cosine with
  shrinkage, or adjusted cosine for ratings.
- **User-user kNN**: weaker and less stable when users have few interactions.
- **Session kNN**: neighbours by session rather than user.

## Latent factor models

| Model | Feedback | Objective |
|-------|----------|-----------|
| Funk SVD / biased MF | explicit ratings | squared error on observed ratings |
| ALS for implicit feedback (Hu, Koren, Volinsky 2008) | counts, plays, clicks | weighted squared error with confidence 1 + alpha x count on all user-item pairs |
| BPR (Rendle 2009) | implicit | pairwise ranking: seen items above unseen |
| EASE (Steck 2019) | implicit | closed-form item-item linear model; very strong baseline |
| SLIM | implicit | sparse item-item regression |

Libraries: `implicit` (ALS, BPR, GPU), `LightFM` (hybrid MF with features), `surprise` (explicit), RecBole and
Microsoft Recommenders (benchmarks), TensorFlow Recommenders / TorchRec (two-tower).

## Content-based and hybrid

- Represent items by attributes, text embeddings or image embeddings, and users by aggregates of the items
  they liked.
- Content handles new items immediately. CF captures taste that content misses.
- Hybrids: LightFM (MF with side features), weighted blending, switching (content when an item has few
  interactions), or features in a re-ranker.

## Sequential and session-based

Next-item prediction from the order of interactions: Markov chains, GRU4Rec, SASRec and BERT4Rec. Use them
when order matters (playlists, e-commerce sessions) and data is large.

## Two-tower retrieval + ranking

A user tower and an item tower produce embeddings, and dot-product retrieval (ANN index: FAISS, ScaNN) yields
candidates. A ranking model (GBDT LambdaMART or a neural network) then scores the candidates with rich
features. This is the standard at large scale.

## Cold start

| Case | Strategy |
|------|----------|
| New user, no history | popularity by context (country, device, referrer), onboarding questions, trending items |
| New user, a few interactions | item-kNN from those items, session-based models |
| New item | content similarity, an exploration slot, boosting in the ranker with uncertainty |
| New system | editorial lists, popularity, content-based; collect interactions first |

Evaluate cold users and items separately. Overall metrics are dominated by warm users.
