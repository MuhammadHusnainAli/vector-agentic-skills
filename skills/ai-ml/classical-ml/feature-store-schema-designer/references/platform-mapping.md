# Platform Mapping

The design (entities, sources, views, TTLs, services) transfers across platforms; the vocabulary differs.

| Concept | Feast | Tecton | Databricks (Feature Engineering in Unity Catalog) | SageMaker Feature Store | Vertex AI Feature Store | Hopsworks |
|---------|-------|--------|-----------------------------------------------------|-------------------------|-------------------------|-----------|
| Entity / key | `Entity(join_keys=...)` | `Entity(join_keys=...)` | primary key columns of a feature table | record identifier | entity ID column | primary key |
| Group of features | `FeatureView` | `BatchFeatureView`, `StreamFeatureView` | feature table (Delta) | feature group | feature view over BigQuery | feature group |
| Event time | `timestamp_field` | `timestamp_field` | `timestamp_keys` (time series feature table) | event time feature name | timestamp column | `event_time` |
| TTL | `ttl` | `ttl` / `serving_ttl` | lookback window in `FeatureLookup` | online TTL | — (latest value) | TTL on online store |
| Online store | Redis, DynamoDB, SQLite... | built-in (DynamoDB/Redis) | online tables / Lakebase | online store | Bigtable / optimized online serving | RonDB |
| Request-time features | `on_demand_feature_view` | `RealtimeFeatureView` | feature functions (UC functions) | — (compute in the app) | — | on-demand transformation functions |
| Model's feature list | `FeatureService` | `FeatureService` | `FeatureLookup` list in a training set | — | feature view selection | feature view |
| Historical retrieval | `get_historical_features` | `get_features_for_events` | `create_training_set(... timestamp_lookup_key=...)` | Athena/Spark query over offline store | BigQuery point-in-time query | `feature_view.training_data()` |

## Databricks example

```python
from databricks.feature_engineering import FeatureEngineeringClient, FeatureLookup
fe = FeatureEngineeringClient()
fe.create_table(name="ml.churn.customer_activity", primary_keys=["customer_id"], timestamp_keys=["event_ts"],
                df=activity_df, description="Rolling engagement aggregates")
training_set = fe.create_training_set(
    df=spine_df,                                    # customer_id, score_ts, label
    feature_lookups=[FeatureLookup(table_name="ml.churn.customer_activity", lookup_key="customer_id",
                                   timestamp_lookup_key="score_ts", lookback_window=timedelta(days=2))],
    label="churned")
```

## SageMaker example

```python
from sagemaker.feature_store.feature_group import FeatureGroup
fg = FeatureGroup(name="customer-activity", sagemaker_session=session)
fg.load_feature_definitions(data_frame=activity_df)       # infers types
fg.create(s3_uri=f"s3://{bucket}/offline", record_identifier_name="customer_id",
          event_time_feature_name="event_ts", role_arn=role, enable_online_store=True)
```
Point-in-time training sets are built by querying the offline store (Athena/Spark) with "latest row with
event_ts <= spine time" logic, or with the SDK's dataset builder (`as_of`, `point_in_time_accurate_join`).

## Choosing a platform

| Situation | Typical choice |
|-----------|----------------|
| Open source, bring your own infra | Feast |
| Heavy real-time/streaming features, managed | Tecton |
| Already on Databricks / Unity Catalog | Databricks Feature Engineering |
| AWS-native ML stack | SageMaker Feature Store |
| GCP / BigQuery-centric | Vertex AI Feature Store |
| Full ML platform with feature store | Hopsworks |

APIs change across versions; check the platform's current docs for exact signatures before generating code
for anything other than Feast.
