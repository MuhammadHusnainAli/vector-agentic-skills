# Window Features at Scale

| Data size | Tool | Approach |
|-----------|------|----------|
| < 1M events | pandas / `pit_features.py` | groupby + rolling(closed="left") or bisect per entity |
| 1M - 500M events | polars, DuckDB | `rolling(..., group_by=, closed="left")`; SQL joins bounded by the longest window |
| > 500M events | Spark, BigQuery, Snowflake | pre-aggregate to daily tables, then window over days |

## Pre-aggregate to daily (or hourly) tables

Window features over days do not need raw events:
```sql
CREATE TABLE daily_card AS
SELECT card_id, DATE(ts) AS d, COUNT(*) AS n, SUM(amount) AS amt
FROM txns GROUP BY 1, 2;

SELECT s.card_id, s.score_date,
       SUM(CASE WHEN dc.d >= s.score_date - 7  THEN dc.n END)   AS n_7d,
       SUM(CASE WHEN dc.d >= s.score_date - 30 THEN dc.amt END) AS amt_30d
FROM spine s
JOIN daily_card dc ON dc.card_id = s.card_id AND dc.d < s.score_date AND dc.d >= s.score_date - 30
GROUP BY 1, 2;
```
Cost drops from events x snapshots to days x snapshots. Distinct counts cannot be summed across days: keep
HyperLogLog sketches (BigQuery `HLL_COUNT`, Snowflake `HLL`) or compute them from raw events.

## DuckDB from Python

```python
import duckdb
con = duckdb.connect()
sql = open("features.sql").read()          # from gen_window_sql.py --dialect duckdb
feats = con.execute(sql).df()               # tables can be CSV/Parquet: FROM read_parquet('events/*.parquet')
```

## Spark

```python
from pyspark.sql import functions as F, Window
w = Window.partitionBy("card_id").orderBy(F.col("ts").cast("long")).rangeBetween(-86400, -1)
df = df.withColumn("n_24h", F.count("*").over(w)).withColumn("sum_24h", F.sum("amount").over(w))
```
`rangeBetween(-86400, -1)` on epoch seconds excludes the current second (and the current row).

## Incremental computation

For daily batch scoring, update yesterday's aggregates with today's new events instead of recomputing
history: maintain per-entity daily partials and roll windows by adding the newest day and dropping the oldest.

## Memory tips for pandas

- Sort once by (entity, time); use `groupby(..., sort=False)`.
- Use categoricals for entity IDs, `float32` for amounts.
- Process entities in chunks (hash partition) and concatenate results.
