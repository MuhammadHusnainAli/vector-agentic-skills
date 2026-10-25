# Interpreting and Naming Segments

## Distinguishing features

For each numeric feature, Cohen's d between the cluster and the rest:
```
d = (mean_in − mean_out) / pooled_sd
```
|d| >= 0.8 large, 0.5 medium, 0.2 small. Rank features by |d|; the top 1-3 usually name the segment. For
categoricals, lift = share in cluster / share overall; > 1.5 is notable.

## Naming

- Use the top distinguishing features in plain language: "dormant" (days since login d = +3.5), "support-heavy"
  (support calls d = +3.9), "premium loyal" (premium plan lift 3.0x, high charges).
- Avoid names that imply causes the data does not show.
- Keep a short definition next to each name (the 2-3 rules that describe it).

## Segment card template

| Field | Content |
|-------|---------|
| Name | Dormant |
| Size | 58 customers (14.5%) |
| Defining traits | last login 35 days ago (vs 8); slightly shorter tenure |
| Outcome | churn 38% (vs 21% overall) |
| Action | re-engagement campaign within 7 days of 21+ days inactivity |
| Owner | lifecycle marketing |
| Watch | share of customers entering the segment per week |

## Validating against outcomes

Segments that do not differ on the outcomes the business cares about (churn, spend, response) rarely deserve
different treatment. `cluster_profile.py --outcome` reports the outcome per cluster and warns when the spread
is small. Differences are associations, not effects of membership; for "who should get the campaign" use
uplift modelling.

## Communicating

- Show sizes and 3-4 traits per segment, not centroids in z-scores.
- Present centroids in original units (`inverse_transform`).
- A 2-D scatter (PCA/UMAP) coloured by segment helps intuition, but the profiles are the evidence.
- State the refresh cadence and that segments are descriptive groupings, not fixed customer types.
