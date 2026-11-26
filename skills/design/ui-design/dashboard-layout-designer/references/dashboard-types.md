# Dashboard Types and the Question-First Method

## Types

| | Operational | Analytical | Strategic / executive |
|---|---|---|---|
| Viewer | Operators, support, on-call, store managers | Analysts, product managers, marketers | Leadership, board, account owners |
| Question | "Is anything wrong right now? What needs action?" | "Why did this change? Which segment?" | "Are we on track against goals?" |
| Cadence | Continuous / hourly | Ad hoc, during investigation | Weekly / monthly |
| Refresh | Real-time to minutes | On query | Daily or period close |
| Density | Low per widget, high contrast, glanceable from distance | High; filters, segmentation, tables | Low; few KPIs with targets and trends |
| Interaction | Alerts, acknowledge, jump to item | Filter, slice, drill, compare, export | Drill to the owner's report |
| Signature widgets | Status tiles, queues, thresholds, event feed | Time series with breakdowns, tables, cohort and funnel views | KPI vs target, trend, forecast, RAG status with commentary |

Mixing types on one page gives you a page that does none of them well. Split into separate views linked by drill-down.

## Question-first method

1. Interview or list viewers. For each: role, cadence, device, what decision they make after looking.
2. Write their questions in their words:
   - "Are we going to hit the monthly revenue target?"
   - "Which support queue is breaching SLA right now?"
   - "Did the onboarding change improve week-1 retention?"
3. For each question define: metric (with exact definition), comparison, threshold, granularity, filter dimensions.
4. Drop any metric that answers no question or drives no decision.
5. Rank questions by frequency x importance; that is the layout order.

## Metric definition (write it down)

| Field | Example |
|-------|---------|
| Name | Net revenue |
| Definition | Gross bookings minus refunds and discounts, excluding tax, in USD at booking-date FX |
| Source | finance.orders (daily close) |
| Grain | Day |
| Comparison | Monthly target (pro-rated), same period last year |
| Threshold | Red below 90% of pro-rated target, amber 90-100%, green >= 100% |
| Owner | Finance ops |

Two widgets that both say "Revenue" but use different definitions destroy trust in the whole dashboard.

## Vanity vs decision metrics

| Vanity | Decision-oriented |
|--------|-------------------|
| Total registered users (ever) | Weekly active users vs last 4 weeks |
| Page views | Conversion rate by step |
| Number of features shipped | Adoption of each feature at day 30 |
| Tickets closed | SLA breach rate, backlog age |
