# Window Feature Catalog

Notation: entity e, anchor a (cutoff − latency), events with time t < a.

## Recency, frequency, monetary

| Feature | Definition |
|---------|------------|
| `days_since_last` | (a − max t) in days; missing if no prior events |
| `days_since_first` (tenure) | (a − min t) |
| `n_<w>` | count of events with a − w <= t < a |
| `active_days_<w>` | distinct calendar days with >= 1 event in the window |
| `sum_<w>`, `mean_<w>`, `max_<w>` | aggregates of the value |

```python
# pandas, snapshot spine (small/medium data)
def window_aggs(events, spine, w_days):
    m = spine.merge(events, on="customer_id", how="left")
    m = m[(m.ts < m.anchor) & (m.ts >= m.anchor - pd.Timedelta(days=w_days))]
    agg = m.groupby(["customer_id", "anchor"]).agg(**{f"n_{w_days}d": ("ts", "size"),
                                                       f"sum_{w_days}d": ("amount", "sum")})
    return spine.merge(agg.reset_index(), on=["customer_id", "anchor"], how="left").fillna(
        {f"n_{w_days}d": 0, f"sum_{w_days}d": 0})
```
The merge is O(spine x events per entity): fine for millions of rows, use SQL/polars beyond that.

## Velocity and burst

| Feature | Definition |
|---------|------------|
| `n_1h`, `n_24h` | short-window counts |
| `burst_1h_7d` | n_1h / (n_7d / 168) | events this hour vs the average hour of the past week |
| `amount_vs_mean_30d` | current amount / mean_30d (event-level) |
| `secs_since_prev` | time since the previous event of the entity |

## Trend

```python
df["spend_trend"] = df["sum_30d"] / (df["sum_30_60d"] + 1)        # sum_30_60d: window [a-60d, a-30d)
df["logins_trend"] = df["n_7d"] / (df["n_30d"] / 30 * 7 + 1e-3)
```
For a slope, aggregate weekly counts over the last 8 weeks and fit a line per entity (numpy polyfit on the
week index), or use (last 4 weeks − previous 4 weeks).

## Diversity

`nuniq_<col>_<w>` (merchants, devices, IPs, products). Also entropy of category shares for "spread" of
behaviour.

## Exponentially weighted features

```python
df = df.sort_values(["customer_id", "ts"])
df["amount_ewm_prior"] = (df.groupby("customer_id")["amount"]
                            .transform(lambda s: s.shift().ewm(halflife=5, min_periods=1).mean()))
# time-aware decay: s.shift().ewm(halflife="7D", times=ts_shifted).mean() needs the times per group
```

## Relative to own history

```python
g = df.groupby("card_id")["amount"]
mean_prior = g.transform(lambda s: s.shift().expanding().mean())
std_prior = g.transform(lambda s: s.shift().expanding().std())
df["amount_z_own"] = (df["amount"] - mean_prior) / (std_prior + 1e-6)
```

## polars (fast, large data)

```python
import polars as pl
ev = pl.read_csv("txns.csv", try_parse_dates=True).sort("timestamp")
feats = ev.rolling(index_column="timestamp", period="24h", group_by="card_id", closed="left").agg(
    pl.len().alias("n_24h"), pl.col("amount").sum().alias("sum_24h"),
    pl.col("merchant_category").n_unique().alias("nuniq_merchant_24h"))
```
`closed="left"` excludes the current row's timestamp (and any events at exactly that instant); with duplicate
timestamps per entity this differs from excluding by event id.

## SQL window functions (event-level, row-based)

```sql
SELECT txn_id, card_id, ts, amount,
       COUNT(*) OVER w24 AS n_24h,
       SUM(amount) OVER w24 AS sum_24h
FROM txns
WINDOW w24 AS (PARTITION BY card_id ORDER BY ts
               RANGE BETWEEN INTERVAL '24 hours' PRECEDING AND INTERVAL '1 microsecond' PRECEDING);
```
`RANGE ... PRECEDING AND <epsilon> PRECEDING` excludes the current row (PostgreSQL 11+, DuckDB). BigQuery
needs `RANGE BETWEEN 86400 PRECEDING AND 1 PRECEDING` over `UNIX_SECONDS(ts)`. `gen_window_sql.py` uses a
join instead, which works for spines too.

## Forecasting lags and rolling statistics

| Feature | Code (horizon h) |
|---------|------------------|
| Lag k (k >= h) | `g.shift(k)` |
| Rolling mean over w ending h steps ago | `g.transform(lambda s: s.shift(h).rolling(w).mean())` |
| Same weekday mean | `g.transform(lambda s: s.shift(h).rolling(7*4).apply(lambda x: x[::-7].mean()))` |
| Year-ago | `g.shift(364)` (keeps weekday alignment) |

## Calendar features

```python
d = df["date"]
df["dow"], df["month"], df["weekofyear"] = d.dt.day_of_week, d.dt.month, d.dt.isocalendar().week.astype(int)
import holidays
hol = holidays.country_holidays("US", years=range(2020, 2027))
df["is_holiday"] = d.dt.date.map(lambda x: x in hol).astype(int)
```
Add `days_to_next_holiday` / `days_since_last_holiday`, paydays (1st/15th, last Friday), school holidays and
promotions known in advance.
