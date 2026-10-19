---
name: sql-query-explainer
description: Explain what an existing SQL query does in plain language — logical execution order, step-by-step breakdown of joins, filters, grouping and window logic, and the shape of the result. Use when the user asks what a query does, how it works, or wants complex/legacy SQL documented.
metadata:
  category: programming
  version: "1.0.0"
---

# SQL Query Explainer

Break down and explain complex SQL queries in plain language for understanding and learning.

## Trigger Conditions

Activate this skill when the user:
- Says "explain this query", "what does this SQL do"
- Asks "how does this query work"
- Needs help understanding inherited or legacy SQL
- Wants to learn from an existing query
- Asks for a step-by-step breakdown

## Explanation Workflow

```
1. PARSE      -> Identify query type and structure
2. DECOMPOSE  -> Break into logical components
3. ORDER      -> Explain in execution order
4. TRANSLATE  -> Convert each part to plain language
5. SUMMARIZE  -> Provide overall purpose
```

## Query Execution Order

Understanding execution order is key to explaining queries:

```
Logical Execution Order (not written order):

1. FROM / JOIN    -> Identify source tables
2. WHERE          -> Filter rows
3. GROUP BY       -> Create groups
4. HAVING         -> Filter groups
5. SELECT         -> Choose columns, compute expressions
6. DISTINCT       -> Remove duplicates
7. ORDER BY       -> Sort results
8. LIMIT/OFFSET   -> Restrict output rows
```

## Explanation Components

### For Every Query, Identify:

| Component | Description | Questions to Answer |
|-----------|-------------|---------------------|
| Purpose | What the query accomplishes | What data is being retrieved? |
| Source | Tables involved | Where does the data come from? |
| Joins | Table relationships | How are tables connected? |
| Filters | WHERE conditions | What rows are included/excluded? |
| Grouping | GROUP BY + aggregates | How is data summarized? |
| Output | SELECT columns | What columns are returned? |
| Ordering | ORDER BY | How are results sorted? |
| Limits | LIMIT/OFFSET | How many rows returned? |

## Explanation Templates

### Basic SELECT Explanation

```
This query retrieves [columns] from [table(s)]
where [conditions].
Results are [sorted by X / limited to N rows].

In plain terms: [business-level description]
```

### JOIN Explanation

```
This query combines data from [table A] and [table B]
by matching rows where [join condition].

- INNER JOIN: Only rows that match in both tables
- LEFT JOIN: All rows from [left table], matched rows from [right table]
- RIGHT JOIN: All rows from [right table], matched rows from [left table]
- FULL JOIN: All rows from both tables, matched where possible
```

### Aggregation Explanation

```
This query groups [table] by [grouping columns]
and calculates [aggregate functions] for each group.

The HAVING clause further filters groups where [condition].
```

### Subquery Explanation

```
The outer query [does X].
It uses an inner query that [does Y] to [provide values / filter / etc.].

Execution: The inner query runs [first / for each row], 
then the outer query uses those results.
```

### CTE Explanation

```
This query uses Common Table Expressions (CTEs) to break complex logic into steps:

Step 1 (cte_name1): [what it does]
Step 2 (cte_name2): [what it does, using step 1 results]
Final query: [combines/uses the CTEs to produce final result]

Think of CTEs as temporary named result sets that exist for one query.
```

### Window Function Explanation

```
This query calculates [function] for each row based on [partition/order].

- PARTITION BY: Groups rows for the calculation (like GROUP BY, but keeps all rows)
- ORDER BY: Determines the order for ranking/running calculations
- Frame: Defines which rows to include in the calculation

The result adds [calculated column] to each row without collapsing groups.
```

## Execution Plan Concepts

When explaining performance, reference:

| Term | Meaning |
|------|---------|
| Seq Scan | Reads entire table row by row |
| Index Scan | Uses index to find specific rows |
| Index Only Scan | Gets all data from index, no table access |
| Nested Loop | For each row in A, scan B |
| Hash Join | Build hash table from smaller table, probe with larger |
| Merge Join | Sort both tables, merge sorted results |
| Sort | Orders rows (may spill to disk) |
| Aggregate | Computes SUM, COUNT, etc. |
| Limit | Stops after N rows |

## Explanation Depth Levels

### Level 1: Summary (One Sentence)

```
"Gets all active customers who placed orders in the last month."
```

### Level 2: Overview (One Paragraph)

```
"This query retrieves customer information for active customers 
who have placed at least one order in the last 30 days. It joins 
the customers and orders tables, filters by status and date, 
and returns customer details along with their order count."
```

### Level 3: Detailed Breakdown

```
1. FROM customers c
   - Start with the customers table, alias 'c'

2. JOIN orders o ON c.id = o.customer_id
   - Connect to orders table where customer IDs match

3. WHERE c.status = 'active'
   - Keep only active customers

4. AND o.order_date >= CURRENT_DATE - INTERVAL '30 days'
   - Keep only recent orders (last 30 days)

5. GROUP BY c.id, c.name, c.email
   - Group results by customer

6. SELECT c.id, c.name, c.email, COUNT(o.id) as order_count
   - Return customer info and count of orders

7. ORDER BY order_count DESC
   - Sort by most orders first
```

### Level 4: Educational (With Concepts)

Full explanation including:
- Why each clause is used
- Alternative approaches
- Performance implications
- Common patterns demonstrated
- Related concepts to learn

## Visual Representation Patterns

### Query Flow Diagram (ASCII)

```
┌─────────────┐    ┌─────────────┐
│  customers  │    │   orders    │
└──────┬──────┘    └──────┬──────┘
       │                  │
       └────────┬─────────┘
                │ JOIN on customer_id
                ▼
       ┌────────────────┐
       │     WHERE      │
       │ status='active'│
       │ date >= 30 days│
       └───────┬────────┘
               │
               ▼
       ┌────────────────┐
       │   GROUP BY     │
       │ customer fields│
       └───────┬────────┘
               │
               ▼
       ┌────────────────┐
       │    SELECT      │
       │ id, name,      │
       │ COUNT(orders)  │
       └───────┬────────┘
               │
               ▼
       ┌────────────────┐
       │   ORDER BY     │
       │ order_count    │
       └───────┬────────┘
               │
               ▼
         Final Result
```

### Data Transformation Example

```
Raw Data:
customers: [{id:1, name:'Alice'}, {id:2, name:'Bob'}]
orders: [{id:1, customer_id:1, amount:100}, {id:2, customer_id:1, amount:50}]

After JOIN:
[{customer_id:1, name:'Alice', order_id:1, amount:100},
 {customer_id:1, name:'Alice', order_id:2, amount:50}]

After GROUP BY + COUNT:
[{customer_id:1, name:'Alice', order_count:2, total:150}]
```

## Output Format

When explaining a query, structure the response as:

```
## Query Purpose
[One sentence summary]

## Step-by-Step Breakdown
[Numbered list of each clause with explanation]

## Data Flow
[How data transforms through the query]

## Key Concepts Used
[List of SQL concepts demonstrated]

## Notes
[Any caveats, assumptions, or performance considerations]
```

## Additional Resources

| File | Content |
|------|---------|
| [examples.md](references/examples.md) | Complex queries with detailed explanations |
