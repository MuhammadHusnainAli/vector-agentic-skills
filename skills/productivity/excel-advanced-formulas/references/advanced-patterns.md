# Advanced Formula Patterns

Production-ready advanced formula examples, optimization patterns, GROUPBY/PIVOTBY usage, and complex data transformations.

## GROUPBY Function (Preview)

Group data and aggregate with a single formula.

### Syntax

```
=GROUPBY(row_fields, values, function, [field_headers], [total_depth], [sort_order], [filter_array], [field_relationship])
```

### Parameters

- row_fields: Columns to group by
- values: Column(s) to aggregate
- function: Aggregation function (SUM, AVERAGE, COUNT, MAX, MIN, etc.)
- field_headers: 0 = no headers, 1 = yes but no filter, 2 = yes with filter, 3 = yes with filter (default)
- total_depth: 0 = no totals, 1 = grand total, 2 = grand + subtotals, etc.
- sort_order: 0 = ascending, 1 = descending, array for multiple
- filter_array: Filter the results

### Basic Examples

Sum by category:
```
=GROUPBY(A2:A100, C2:C100, SUM)
```

Average by region:
```
=GROUPBY(B2:B100, D2:D100, AVERAGE)
```

Count by status:
```
=GROUPBY(E2:E100, E2:E100, COUNT)
```

Max by product:
```
=GROUPBY(A2:A100, C2:C100, MAX)
```

### Multiple Grouping Fields

Group by region and product:
```
=GROUPBY(HSTACK(A2:A100, B2:B100), C2:C100, SUM)
```

Group by year and month:
```
=GROUPBY(
  HSTACK(YEAR(D2:D100), MONTH(D2:D100)),
  E2:E100,
  SUM
)
```

### Multiple Value Columns

Sum and count:
```
=GROUPBY(A2:A100, HSTACK(C2:C100, C2:C100), HSTACK(SUM, COUNT))
```

### With Totals

Add grand total:
```
=GROUPBY(A2:A100, C2:C100, SUM, 3, 1)
```

Grand total + subtotals:
```
=GROUPBY(HSTACK(A2:A100, B2:B100), C2:C100, SUM, 3, 2)
```

### Sorted Results

Descending by sum:
```
=GROUPBY(A2:A100, C2:C100, SUM, 3, 0, 1)
```

### Custom Aggregation

Using LAMBDA:
```
=GROUPBY(A2:A100, C2:C100, LAMBDA(x, PERCENTILE.INC(x, 0.5)))
```

Weighted average:
```
=GROUPBY(A2:A100, HSTACK(B2:B100, C2:C100), LAMBDA(v,
  SUMPRODUCT(INDEX(v,,1), INDEX(v,,2)) / SUM(INDEX(v,,2))
))
```

## PIVOTBY Function (Preview)

Create pivot table style summaries.

### Syntax

```
=PIVOTBY(row_fields, col_fields, values, function, [field_headers], [row_total_depth], [row_sort_order], [col_total_depth], [col_sort_order], [filter_array])
```

### Basic Examples

Sales by region (rows) and product (columns):
```
=PIVOTBY(A2:A100, B2:B100, C2:C100, SUM)
```

Count by status (rows) and month (columns):
```
=PIVOTBY(D2:D100, MONTH(E2:E100), D2:D100, COUNT)
```

### With Totals

Row and column totals:
```
=PIVOTBY(A2:A100, B2:B100, C2:C100, SUM, 3, 1, 0, 1)
```

### Practical Examples

Monthly sales by region:
```
=PIVOTBY(
  Region,
  TEXT(Date, "YYYY-MM"),
  Amount,
  SUM,
  3, 1, 0, 1
)
```

Quarterly performance by department:
```
=PIVOTBY(
  Department,
  "Q" & ROUNDUP(MONTH(Date)/3, 0),
  Revenue,
  SUM
)
```

## LET Optimization Patterns

### Cache Expensive Calculations

Before:
```
=IF(
  XLOOKUP(A1, B:B, C:C) > 100,
  XLOOKUP(A1, B:B, C:C) * 0.1,
  XLOOKUP(A1, B:B, C:C) * 0.05
)
```

After:
```
=LET(
  price, XLOOKUP(A1, B:B, C:C),
  rate, IF(price > 100, 0.1, 0.05),
  price * rate
)
```

### Multi-Step Transformation

```
=LET(
  raw_data, A2:D100,
  filtered, FILTER(raw_data, INDEX(raw_data,,2) > 0),
  sorted, SORT(filtered, 3, -1),
  top_10, TAKE(sorted, 10),
  top_10
)
```

### Named Intermediate Results

```
=LET(
  sales, B2:B100,
  costs, C2:C100,
  
  total_sales, SUM(sales),
  total_costs, SUM(costs),
  gross_profit, total_sales - total_costs,
  margin, gross_profit / total_sales,
  
  HSTACK(
    total_sales,
    total_costs,
    gross_profit,
    TEXT(margin, "0.0%")
  )
)
```

### Conditional Logic with LET

```
=LET(
  value, A1,
  category, B1,
  
  base_rate, SWITCH(category,
    "A", 0.15,
    "B", 0.12,
    "C", 0.10,
    0.08
  ),
  
  volume_bonus, IF(value > 10000, 0.02, 0),
  final_rate, base_rate + volume_bonus,
  
  value * final_rate
)
```

## Data Transformation Pipelines

### Filter, Transform, Aggregate

```
=LET(
  data, A2:E1000,
  
  filtered, FILTER(data,
    (INDEX(data,,2) = "Active") *
    (INDEX(data,,4) > DATE(2024,1,1))
  ),
  
  with_calc, HSTACK(
    filtered,
    INDEX(filtered,,3) * INDEX(filtered,,5)
  ),
  
  sorted, SORT(with_calc, COLUMNS(with_calc), -1),
  
  TAKE(sorted, 20)
)
```

### Unpivot Data (Wide to Long)

```
=LET(
  headers, B1:E1,
  row_labels, A2:A10,
  values, B2:E10,
  
  n_rows, ROWS(row_labels),
  n_cols, COLUMNS(headers),
  
  expanded_labels, WRAPROWS(
    TOCOL(MAKEARRAY(n_rows, n_cols, LAMBDA(r, c, INDEX(row_labels, r)))),
    1
  ),
  
  expanded_headers, WRAPROWS(
    TOCOL(MAKEARRAY(n_rows, n_cols, LAMBDA(r, c, INDEX(headers, 1, c)))),
    1
  ),
  
  flat_values, TOCOL(values),
  
  HSTACK(expanded_labels, expanded_headers, flat_values)
)
```

### Pivot Data (Long to Wide)

Use PIVOTBY or:
```
=LET(
  data, A2:C100,
  row_keys, UNIQUE(INDEX(data,,1)),
  col_keys, UNIQUE(INDEX(data,,2)),
  
  pivot, MAKEARRAY(
    ROWS(row_keys),
    COLUMNS(col_keys),
    LAMBDA(r, c,
      SUMIFS(
        INDEX(data,,3),
        INDEX(data,,1), INDEX(row_keys, r),
        INDEX(data,,2), INDEX(col_keys, c)
      )
    )
  ),
  
  VSTACK(
    HSTACK("", TRANSPOSE(col_keys)),
    HSTACK(row_keys, pivot)
  )
)
```

## Recursive Patterns

### Factorial (Named LAMBDA: FACT)

```
=LAMBDA(n,
  IF(n <= 1, 1, n * FACT(n - 1))
)
```

### Fibonacci Sequence

Generate first n Fibonacci numbers:
```
=LET(
  n, 10,
  SCAN(
    HSTACK(0, 1),
    SEQUENCE(n - 2),
    LAMBDA(prev, _,
      HSTACK(INDEX(prev, 2), SUM(prev))
    )
  )
)
```

### Cumulative Growth

```
=LET(
  initial, 1000,
  rates, A1:A12,
  SCAN(initial, rates, LAMBDA(bal, rate, bal * (1 + rate)))
)
```

## Dynamic Reports

### Top N by Category

```
=LET(
  data, A2:C100,
  categories, UNIQUE(INDEX(data,,1)),
  n, 3,
  
  REDUCE(
    "",
    categories,
    LAMBDA(acc, cat,
      LET(
        cat_data, FILTER(data, INDEX(data,,1) = cat),
        top_n, TAKE(SORT(cat_data, 3, -1), n),
        IF(acc = "", top_n, VSTACK(acc, top_n))
      )
    )
  )
)
```

### Running Rank

```
=LET(
  values, A2:A100,
  MAP(SEQUENCE(ROWS(values)), LAMBDA(i,
    RANK(INDEX(values, i), TAKE(values, i))
  ))
)
```

### Moving Average

```
=LET(
  data, A2:A100,
  window, 7,
  n, ROWS(data),
  
  MAP(SEQUENCE(n), LAMBDA(i,
    IF(i < window,
      AVERAGE(TAKE(data, i)),
      AVERAGE(CHOOSEROWS(data, SEQUENCE(window, 1, i - window + 1)))
    )
  ))
)
```

### Year-over-Year Comparison

```
=LET(
  dates, A2:A100,
  values, B2:B100,
  
  current_year, YEAR(TODAY()),
  
  cy_data, SUMIFS(values, YEAR(dates), current_year),
  py_data, SUMIFS(values, YEAR(dates), current_year - 1),
  
  growth, (cy_data - py_data) / py_data,
  
  HSTACK(py_data, cy_data, TEXT(growth, "+0.0%;-0.0%"))
)
```

## Error Handling Patterns

### Graceful Degradation

```
=LET(
  lookup_result, XLOOKUP(A1, B:B, C:C),
  fallback_result, XLOOKUP(A1, D:D, E:E),
  default_value, 0,
  
  IFERROR(lookup_result,
    IFERROR(fallback_result, default_value)
  )
)
```

### Validate Before Process

```
=LET(
  input, A1,
  is_valid, AND(
    ISNUMBER(input),
    input > 0,
    input <= 1000000
  ),
  
  IF(is_valid,
    LET(
      processed, input * 1.1,
      ROUND(processed, 2)
    ),
    "Invalid input"
  )
)
```

### Safe Division

```
=LET(
  numerator, A1,
  denominator, B1,
  
  IF(OR(denominator = 0, ISBLANK(denominator)),
    0,
    numerator / denominator
  )
)
```

### Array with Error Cleanup

```
=LET(
  raw_calc, A1:A100 / B1:B100,
  IFERROR(raw_calc, 0)
)
```

## Performance Optimization

### Avoid Volatile Functions in Large Ranges

Instead of:
```
=SUMIF(INDIRECT("A:A"), ">0", INDIRECT("B:B"))
```

Use:
```
=SUMIF(A:A, ">0", B:B)
```

### Cache Filter Results

```
=LET(
  filtered, FILTER(A1:D1000, B1:B1000 > 100),
  
  VSTACK(
    HSTACK("Count", ROWS(filtered)),
    HSTACK("Sum", SUM(INDEX(filtered,,3))),
    HSTACK("Avg", AVERAGE(INDEX(filtered,,3)))
  )
)
```

### Limit Array Size

```
=LET(
  full_data, A:D,
  last_row, MATCH(9E307, A:A, 1),
  actual_data, TAKE(full_data, last_row),
  
  FILTER(actual_data, INDEX(actual_data,,2) = "Active")
)
```

### Use SUMIFS Over SUMPRODUCT

Faster:
```
=SUMIFS(C2:C1000, A2:A1000, "East", B2:B1000, ">100")
```

Slower:
```
=SUMPRODUCT((A2:A1000="East")*(B2:B1000>100)*C2:C1000)
```

## Complex Business Scenarios

### Tiered Pricing

```
=LET(
  quantity, A1,
  tiers, {0, 100, 500, 1000},
  prices, {10, 8, 6, 4},
  
  tier_index, SUMPRODUCT((quantity >= tiers) * 1),
  unit_price, INDEX(prices, tier_index),
  
  quantity * unit_price
)
```

### Commission with Accelerators

```
=LET(
  sales, A1,
  quota, B1,
  
  attainment, sales / quota,
  
  base_rate, 0.05,
  accelerator, IFS(
    attainment >= 1.5, 0.03,
    attainment >= 1.2, 0.02,
    attainment >= 1.0, 0.01,
    TRUE, 0
  ),
  
  sales * (base_rate + accelerator)
)
```

### Inventory Reorder Point

```
=LET(
  daily_sales, A2:A31,
  lead_time_days, 7,
  safety_stock_days, 3,
  
  avg_daily, AVERAGE(daily_sales),
  std_daily, STDEV.S(daily_sales),
  
  reorder_point, (avg_daily * lead_time_days) +
                 (1.65 * std_daily * SQRT(lead_time_days)),
  safety_stock, avg_daily * safety_stock_days,
  
  HSTACK(
    ROUND(reorder_point, 0),
    ROUND(safety_stock, 0),
    ROUND(reorder_point + safety_stock, 0)
  )
)
```

### Aging Analysis

```
=LET(
  invoices, A2:D100,
  today, TODAY(),
  
  days_old, today - INDEX(invoices,,3),
  
  HSTACK(
    invoices,
    days_old,
    IFS(
      days_old <= 30, "Current",
      days_old <= 60, "31-60 Days",
      days_old <= 90, "61-90 Days",
      TRUE, "Over 90 Days"
    )
  )
)
```

### Cohort Analysis

```
=LET(
  customers, A2:A1000,
  signup_dates, B2:B1000,
  order_dates, C2:C1000,
  
  cohort_month, TEXT(signup_dates, "YYYY-MM"),
  order_month, TEXT(order_dates, "YYYY-MM"),
  
  cohorts, UNIQUE(cohort_month),
  
  PIVOTBY(
    cohort_month,
    DATEDIF(signup_dates, order_dates, "M"),
    customers,
    LAMBDA(x, COUNTA(UNIQUE(x)))
  )
)
```

## Combining Multiple Advanced Functions

### Complete Data Pipeline

```
=LET(
  raw, RawData,
  
  cleaned, FILTER(raw,
    (INDEX(raw,,1) <> "") *
    ISNUMBER(INDEX(raw,,3)) *
    (INDEX(raw,,4) >= DATE(2024,1,1))
  ),
  
  enriched, HSTACK(
    cleaned,
    XLOOKUP(INDEX(cleaned,,2), Categories[ID], Categories[Name], "Unknown"),
    INDEX(cleaned,,3) * INDEX(cleaned,,5)
  ),
  
  aggregated, GROUPBY(
    CHOOSECOLS(enriched, 6),
    CHOOSECOLS(enriched, 7),
    SUM
  ),
  
  final, SORT(aggregated, 2, -1),
  
  TAKE(final, 10)
)
```

### Dynamic Dashboard Metric

```
=LET(
  data, SalesData,
  period, $A$1,
  metric, $B$1,
  
  period_filter, SWITCH(period,
    "MTD", MONTH(INDEX(data,,1)) = MONTH(TODAY()),
    "QTD", ROUNDUP(MONTH(INDEX(data,,1))/3,0) = ROUNDUP(MONTH(TODAY())/3,0),
    "YTD", YEAR(INDEX(data,,1)) = YEAR(TODAY()),
    TRUE
  ),
  
  filtered, FILTER(data, period_filter),
  values, INDEX(filtered,,3),
  
  result, SWITCH(metric,
    "Sum", SUM(values),
    "Avg", AVERAGE(values),
    "Count", COUNT(values),
    "Max", MAX(values),
    "Min", MIN(values),
    SUM(values)
  ),
  
  result
)
```

## Best Practices Summary

1. **Use LET liberally** - Cache any calculation used more than once
2. **Name variables meaningfully** - Makes formulas self-documenting
3. **Build incrementally** - Test each step of complex formulas
4. **Limit array sizes** - Don't process entire columns when possible
5. **Handle errors explicitly** - Use IFERROR, IFNA at appropriate points
6. **Consider version compatibility** - Check function availability
7. **Document complex logic** - Use cell comments for business rules
8. **Test edge cases** - Empty inputs, zeros, negative numbers
9. **Optimize for readability** - Future you will thank present you
10. **Use structured references** - Table references over A1 notation
