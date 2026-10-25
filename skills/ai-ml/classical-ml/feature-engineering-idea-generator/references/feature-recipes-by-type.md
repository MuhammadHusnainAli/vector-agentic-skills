# Feature Recipes by Column Type

All snippets assume `df` (rows to transform) and `train` (the training split, the only place statistics are
learned). Wrap them in a function or a scikit-learn transformer so the same code runs in training and serving.

## Dates and timestamps

```python
d = pd.to_datetime(df["event_ts"], errors="coerce", utc=True)
df["month"] = d.dt.month
df["dow"] = d.dt.day_of_week            # 0 = Monday
df["hour"] = d.dt.hour
df["is_weekend"] = (d.dt.day_of_week >= 5).astype(int)
df["day_of_month"] = d.dt.day
df["is_month_end"] = d.dt.is_month_end.astype(int)

# Elapsed time to the prediction time (scoring date per row, or a fixed cutoff)
df["days_since_signup"] = (pd.to_datetime(df["score_date"]) - pd.to_datetime(df["signup_date"])).dt.days

# Cyclical encodings (linear / distance models): hour 23 is next to hour 0
df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
df["dow_sin"] = np.sin(2 * np.pi * df["dow"] / 7)
df["dow_cos"] = np.cos(2 * np.pi * df["dow"] / 7)
```

Holidays and events: `holidays` package (`holidays.country_holidays("US")`) or a company calendar; add
`days_to_next_holiday` and `days_since_last_holiday` for demand problems.

Unix epochs: `pd.to_datetime(df["ts"], unit="s")` (or `unit="ms"`).

**Do not** feed the raw timestamp or a monotonically increasing date to a tree model trained on a random
split: it learns "period" effects that do not exist in the future.

Time zones: compute hour/day-of-week in the user's local time when behaviour is local (shopping, logins).

## Years

```python
df["building_age"] = df["score_date"].dt.year - df["year_built"]
```

## Amounts and other skewed positives

```python
df["log_amount"] = np.log1p(df["amount"].clip(lower=0))
lo, hi = train["amount"].quantile([0.01, 0.99])
df["amount_clip"] = df["amount"].clip(lo, hi)
df["amount_is_round"] = (df["amount"] % 10 == 0).astype(int)        # fraud: round amounts
df["amount_cents"] = (df["amount"] * 100 % 100).round()             # fraud/testing patterns
```
Trees are invariant to monotone transforms: log1p helps linear, k-NN and neural models, not GBMs (except via
ratios and interactions).

## Counts

```python
df["log_tickets"] = np.log1p(df["tickets_90d"])
df["tickets_per_month"] = df["tickets_total"] / df["tenure_months"].clip(lower=1)
df["has_tickets"] = (df["tickets_90d"] > 0).astype(int)
```

## Low-cardinality categoricals

```python
keep = train["plan"].value_counts()
keep = keep[keep >= 20].index
df["plan"] = df["plan"].where(df["plan"].isin(keep), "other")
```
Then one-hot (`OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=20)`) for linear models, or
native categoricals for LightGBM / CatBoost / HistGradientBoosting. Ordinal categories (small < medium <
large) get an ordinal integer.

## High-cardinality categoricals

```python
freq = train["merchant_id"].value_counts()
df["merchant_freq"] = df["merchant_id"].map(freq).fillna(0)

from sklearn.preprocessing import TargetEncoder          # sklearn >= 1.3; cross-fitted inside fit_transform
te = TargetEncoder(target_type="binary", cv=5, smooth="auto")
```
See categorical-encoding-selector for the full decision table (hashing, CatBoost ordered target statistics,
embeddings).

## Codes with hierarchy

```python
df["zip3"] = df["zip_code"].astype(str).str.zfill(5).str[:3]
df["naics2"] = df["naics"].astype(str).str[:2]
df["icd_chapter"] = df["icd10"].str[0]
```
Join external attributes by code (census income by zip, industry risk by NAICS) when allowed.

## Geography

```python
def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))

df["dist_to_store_km"] = haversine_km(df.lat, df.lon, df.store_lat, df.store_lon)
df["grid_cell"] = (df.lat.round(2).astype(str) + "_" + df.lon.round(2).astype(str))   # ~1 km cells
```
Fraud: distance between billing and shipping address, between consecutive transactions divided by elapsed
time ("impossible travel").

## Text

```python
df["desc_len"] = df["description"].str.len()
df["desc_words"] = df["description"].str.split().str.len()
df["desc_has_urgent"] = df["description"].str.contains(r"\burgent|asap\b", case=False, regex=True).astype(int)

from sklearn.feature_extraction.text import TfidfVectorizer
tfidf = TfidfVectorizer(ngram_range=(1, 2), min_df=5, max_features=20000, sublinear_tf=True)
```
TF-IDF goes inside the ColumnTransformer so it is fitted on training text only. For semantic signal use
sentence embeddings, reduced with PCA/TruncatedSVD if the model is a GBM.

## Missingness

```python
for c in ["monthly_charges", "last_payment_amount"]:
    df[f"{c}_missing"] = df[c].isna().astype(int)
```
`SimpleImputer(add_indicator=True)` does this inside a pipeline. A column missing only for positives (filled
after the event) is a leak, not a feature.

## Booleans and flags

Keep as 0/1. Combine related flags into counts (`n_products_owned`) and ratios.
