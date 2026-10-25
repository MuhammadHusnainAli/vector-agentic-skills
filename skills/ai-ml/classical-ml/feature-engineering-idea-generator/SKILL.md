---
name: feature-engineering-idea-generator
description: "Generate concrete, leakage-aware feature ideas for tabular ML and the pandas code to build them: infer column roles (IDs, entity keys, datetimes incl. unix epochs, years, amounts, counts, proportions, low- and high-cardinality categoricals, codes like zip, lat/lon, free text), then propose date parts and cyclical encodings, elapsed time to the prediction date, age from year, log1p and clipping for skewed values, missing indicators, rare-level grouping, frequency encoding, code prefixes, text length and TF-IDF, per-unit rates (total / tenure), date differences, geo distances, and point-in-time per-entity aggregates (prior counts, means, time since previous event, velocity). Ranks ideas P1-P3, flags columns that look written after the outcome, and includes domain playbooks (churn, fraud, credit, demand, marketing, real estate, IoT). Use when someone asks for feature ideas, how to improve a model with better features, what features to build from a dataset, or how to encode dates, amounts, IDs or text."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Feature Engineering Idea Generator

On tabular data, better features beat better algorithms. Good features express what a domain expert would
look at, in a form the model can use: rates instead of totals, recency instead of raw dates, behaviour
relative to the entity's own history, and missingness as information. All of it computed only from data
available at prediction time. `scripts/profile_columns.py` infers each column's semantic role;
`scripts/suggest_features.py` turns the roles into ranked ideas, flags probable leaks, and prints an
`add_features(df, train)` pandas function you can drop into a pipeline.

## Trigger Conditions

Activate this skill when the user:
- Asks for feature ideas for a dataset, or "how can I improve this model?" when the model is already tuned
- Has raw tables (transactions, events, customers, sensors) and needs a feature table for ML
- Asks how to use dates, timestamps, IDs, zip codes, free text, coordinates or amounts as features
- Wants per-customer / per-card / per-device aggregates or velocity features
- Is stuck at a plateau and wants domain-driven features (churn, fraud, credit, demand, pricing)

Related: encoding choice in [categorical-encoding-selector](../categorical-encoding-selector/SKILL.md);
scaling in [feature-scaling-advisor](../feature-scaling-advisor/SKILL.md); point-in-time window features in
[time-based-feature-builder](../time-based-feature-builder/SKILL.md); checking that new features do not leak
in [target-leakage-detector](../target-leakage-detector/SKILL.md); pruning in
[feature-selection-analyzer](../feature-selection-analyzer/SKILL.md).

## Workflow

```
1. ROLES     -> python scripts/profile_columns.py data.csv --target y
2. LEAKS     -> anything written after prediction time? (suggest_features flags names; confirm with owners)
3. IDEAS     -> python scripts/suggest_features.py data.csv --target y [--entity customer_id --time-col ts]
4. DOMAIN    -> add the domain playbook features (references/domain-playbooks.md)
5. BUILD     -> python scripts/suggest_features.py ... --code > features.py; statistics learned on train only
6. VALIDATE  -> add features in groups; keep a group only if the CV metric improves beyond noise
7. GUARD     -> re-run leakage checks; document every kept feature (definition, source, availability)
```

## Feature Recipes by Column Role

| Role | Recipes | Watch out |
|------|---------|-----------|
| Datetime | month, day of week, hour, is_weekend, holiday flags; cyclical sin/cos for linear models; **days since** the event at prediction time | raw timestamps let trees memorise periods; never use a date after prediction time |
| Year | age = reference year − year | reference = scoring date, not "today" at training |
| Amount (skewed) | log1p, clipping at train quantiles, ratios to the entity's own average | log of negatives; clip bounds learned on all data |
| Count | log1p / bins, zero indicator, per-unit rate (count / exposure) | counts grow with tenure: normalise |
| Low-card categorical | one-hot (linear) or native categorical (GBMs); group rare levels | unseen levels at serving time |
| High-card categorical | frequency encoding, out-of-fold target encoding, hashing, embeddings | in-sample target encoding leaks |
| Code (zip, NAICS, ICD) | categorical, plus hierarchical prefixes (zip3, NAICS 2-digit) | never as a number |
| Entity key | group-by key for aggregates; never a raw feature | IDs memorise rows |
| Lat/lon | distance to points of interest, grid cell / geohash, density | raw lat/lon is fine for trees, poor for linear |
| Text | length, word count, keyword flags, TF-IDF, sentence embeddings | fit vectorisers in the pipeline |
| Proportion | logit for linear models; keep raw for trees | exact 0/1 need clipping |
| Missingness | `is_missing` indicator per column with > 1% missing | missingness can itself be a leak (filled after the event) |

Detailed formulas and pandas/sklearn code for each: [feature-recipes-by-type.md](references/feature-recipes-by-type.md).

## Cross-Column and Entity Features

These usually carry the most signal and are what the model cannot invent on its own:

| Family | Example | Why it helps |
|--------|---------|--------------|
| Rates | `total_charges / tenure_months`, `claims / exposure_years` | removes the size/exposure effect |
| Ratios to self | `amount / card_mean_amount_prior_30d` | "unusual for this customer" |
| Differences | `days_between(signup, first_purchase)` | captures process speed |
| Recency / frequency / monetary | days since last order, orders in 90 d, spend in 90 d | classic RFM; strong for churn and CLV |
| Velocity | transactions per card in the last 1 h / 24 h | fraud, abuse |
| Trend | spend last 30 d / spend previous 30 d | declining engagement predicts churn |
| Group context | price / median price in the neighbourhood | relative position matters more than level |
| Interactions | plan x region, hour x merchant category | linear models need them explicitly; GBMs often find them |

Per-entity aggregates must use only rows **strictly before** each row's prediction time:

```python
df = df.sort_values(["card_id", "timestamp"])
g = df.groupby("card_id")
df["card_n_prior"] = g.cumcount()
df["card_amount_mean_prior"] = g["amount"].transform(lambda s: s.shift().expanding().mean())
df["amount_vs_card_mean"] = df["amount"] / df["card_amount_mean_prior"]
df["secs_since_prev_txn"] = pd.to_datetime(df["timestamp"]).groupby(df["card_id"]).diff().dt.total_seconds()
```

Window aggregates (last 1 h / 7 d / 30 d) and snapshot tables are covered in
[aggregation-and-interaction-features.md](references/aggregation-and-interaction-features.md).

## Leakage Rules for Every New Feature

1. **Available at prediction time?** If the value is written or updated after the moment you score, it leaks.
2. **Statistics learned on train only.** Quantiles for clipping, frequency tables, kept levels, target
   encodings and scalers are fitted on the training fold and applied elsewhere: `add_features(df, train)`
   takes `train` explicitly for this reason.
3. **Aggregates exclude the current row and the future.** `shift()` before `expanding()`/`rolling()`.
4. **Names are hints, not proof.** `suggest_features.py` excludes columns named like outcomes (status,
   reason, refund, cancel, chargeback, resolution); confirm write times with the data owner.
5. A feature that alone gives AUC > 0.9 is a leak until proven otherwise.

## Validate Ideas, Do Not Just Add Them

| Step | How |
|------|-----|
| Group the ideas | date features, rates, entity aggregates, text, interactions |
| Add one group at a time | same CV folds, same model, same seed |
| Keep if it helps beyond noise | improvement > ~2 x the fold-to-fold standard deviation, or a paired test |
| Check importance and direction | plausible sign/shape (SHAP); surprising strength -> leak check |
| Check stability | importance and effect by time period; drop features whose meaning drifts |
| Cost | compute cost and latency at serving time; online availability |

Ablation code and stability checks: [feature-validation.md](references/feature-validation.md).

## Model Family Matters

| Model | Needs from feature engineering |
|-------|-------------------------------|
| Linear / logistic | scaling, log transforms, one-hot, explicit interactions and splines, cyclical dates |
| Gradient boosting / random forest | rates, aggregates, recency; no scaling; native categoricals; fewer explicit interactions |
| k-NN, SVM, clustering | scaling is mandatory; low-dimensional, meaningful distances |
| Neural nets on tabular | scaling, embeddings for categoricals; still benefit from aggregates |

## Output Format

When proposing features, answer with:
1. **Column roles** - the `profile_columns.py` table, corrected where domain knowledge says otherwise.
2. **Possible leaks** - columns to exclude or rebuild as-of prediction time, with the reason.
3. **Ranked ideas** - P1 (cheap, usually useful), P2 (worth testing), P3 (situational), each with the column(s),
   the transformation and why it should help in this domain.
4. **Code** - an `add_features(df, train)` function (from `--code` or written by hand) where every statistic
   is learned on `train`.
5. **Validation plan** - feature groups, CV setup, keep/drop rule.

## Scripts

```bash
python scripts/profile_columns.py data.csv --target churned
python scripts/profile_columns.py data.csv --sample 20000 --json
```
Roles: id, entity_key, datetime (ISO strings and unix epochs in s/ms), year, binary, count, amount,
continuous, percentage (proportions), categorical, high_card, code (zip/postcode/NAICS/ICD), geo_lat,
geo_lon, text, constant, target; with distinct count, missing share, min/max, skew, rare levels and
singletons. Exit codes: 0 profiled, 2 read error.

```bash
python scripts/suggest_features.py data.csv --target churned
python scripts/suggest_features.py txns.csv --target is_fraud --entity card_id --time-col timestamp
python scripts/suggest_features.py data.csv --target price --code > features.py
python scripts/suggest_features.py data.csv --target churned --json
```
Imports `profile_columns.py` from the same folder. Prints column roles, possible leaks (outcome-like column
names, excluded from ideas), and P1/P2/P3 ideas: calendar parts (hour only when timestamps have a time),
cyclical encodings, elapsed days to the prediction time, age from year, log1p for skewed amounts and counts,
train-quantile clipping, zero indicators, rare-level grouping, frequency and target encoding, code prefixes,
text length and TF-IDF, logit of proportions, missing indicators, cumulative-total-per-exposure rates, date
differences, haversine distance, and point-in-time per-entity aggregates with `--entity` + `--time-col`.
`--code` prints a runnable `add_features(df, train)` pandas function with the P1/P2 ideas. Exit codes: 0
printed, 2 usage or read error.

## Additional Resources

| File | Content |
|------|---------|
| [feature-recipes-by-type.md](references/feature-recipes-by-type.md) | Code for every column role: dates, cyclical, holidays, amounts, counts, categoricals, codes, geo, text, missingness |
| [aggregation-and-interaction-features.md](references/aggregation-and-interaction-features.md) | Point-in-time aggregates, rolling windows, RFM, velocity, trends, ratios to self and group, interactions, splines |
| [domain-playbooks.md](references/domain-playbooks.md) | Feature lists that work in churn, fraud, credit risk, demand, marketing response, real estate, IoT/maintenance, healthcare |
| [feature-validation.md](references/feature-validation.md) | Group ablation, noise thresholds, stability over time, leakage checks for new features, documentation template |
