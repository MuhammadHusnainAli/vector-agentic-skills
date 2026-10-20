# Report Formatting

### Currency Formatting

```sql
SELECT 
    TO_CHAR(revenue, 'FM$999,999,999.00') AS revenue_formatted,
    TO_CHAR(growth_rate, 'FM990.0%') AS growth_formatted
FROM metrics;
```

### Date Formatting

```sql
SELECT 
    TO_CHAR(date, 'Mon DD, YYYY') AS date_formatted,
    TO_CHAR(date, 'YYYY-MM') AS month_formatted,
    TO_CHAR(date, 'Day') AS day_of_week
FROM data;
```

### Conditional Formatting Hints

```sql
SELECT 
    metric,
    value,
    CASE 
        WHEN value > 0 THEN 'positive'
        WHEN value < 0 THEN 'negative'
        ELSE 'neutral'
    END AS style_class,
    CASE 
        WHEN value > threshold * 1.1 THEN 'green'
        WHEN value < threshold * 0.9 THEN 'red'
        ELSE 'yellow'
    END AS status_color
FROM metrics;
```
