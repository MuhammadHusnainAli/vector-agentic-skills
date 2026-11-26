---
name: dashboard-layout-designer
description: "Design dashboards that answer questions instead of displaying data: dashboard type (operational monitoring, analytical, strategic/executive) decides density, refresh and interaction; start from the questions and decisions each viewer has, then KPIs with comparison (target, previous period, benchmark), status thresholds and sparklines, layout in reading order on a 12-column grid with a density budget, global vs local filters and one consistent time range, freshness stamps, drill-down paths, chart choice per question (and when not to use pie, gauge, donut, 3D), per-widget loading, empty, partial and error states, responsive priority stacking, and accessibility (non-colour status, 3:1 graphical contrast, data-table alternatives). Reviews dashboards for KPIs with no comparison, mixed date ranges, no freshness, too many widgets, colour-only status, vanity metrics, misleading axes and unanswerable questions. Use when designing, restructuring or reviewing a product, admin, analytics or executive dashboard."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Dashboard Layout Designer

A dashboard is a set of answers arranged by importance. Most bad dashboards come from a list of available metrics and a
grid to fill. Good ones start with who looks at it, how often, and what they decide afterwards. Then every widget earns
its place by answering one of those questions with a comparison, so the number means something. This skill designs from
the questions out and reviews existing dashboards for the usual failures.

## Trigger Conditions

Activate this skill when the user:
- Designs a dashboard, admin overview, analytics page, KPI screen or home screen with metrics
- Has a dashboard nobody uses, that is "too busy", or where people still export to Excel
- Chooses charts and KPI cards, or arranges widgets on a grid
- Reviews a dashboard before build

Visual chart design in depth (colours, marks, axes) belongs to a data-visualisation skill. Grid and breakpoints:
`responsive-breakpoint-layout-planner`. Card containers: `card-component-designer`.

## Workflow

```
1. VIEWERS    -> who, how often (glance every hour / weekly review / monthly board), on what screen
2. TYPE       -> operational, analytical or strategic (references/dashboard-types.md)
3. QUESTIONS  -> 3-7 questions per viewer, each with the decision it informs; drop metrics that inform none
4. WIDGETS    -> per question: KPI, chart or table + its comparison + threshold (references/widget-guide.md)
5. PRIORITY   -> rank widgets; top-left = most important; group by question, not by data source
6. LAYOUT     -> 12-col grid, density budget, filter bar, time range, freshness (references/layout-and-grid.md)
7. STATES     -> loading, empty, partial, stale, error, no permission: per widget, not whole page
8. REVIEW     -> run the checklist below; test with a real viewer: "what would you do after looking at this?"
```

## Principles

| Principle | Practice |
|-----------|----------|
| Every number has a comparison | vs target, vs previous period, vs benchmark. "1,204 orders" alone means nothing |
| Status is not colour only | Icon + text label ("Below target") + colour; arrows show direction, colour shows good/bad |
| One time range rules the page | Global time filter; widgets with a different range say so in the title |
| Freshness is visible | "Updated 5 min ago" / "Data through 25 Nov"; stale data flagged |
| Top-left is prime space | The most important KPI there; secondary detail lower and to the right |
| Fewer, bigger widgets | About 5-9 widgets above the fold for a glance dashboard; more means a second page or tabs |
| Same metric, same look everywhere | Revenue always the same colour, format and decimals |
| Drill-down, not drill-everywhere | Each KPI links to the analytical view that explains it |

## Review Checklist

Report as `CODE [severity] problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| DB001 | high | KPI with no comparison (target, previous period or benchmark) |
| DB002 | high | Status conveyed by colour only (WCAG 1.4.1); red/green as the only distinction |
| DB003 | high | Widgets use different date ranges without saying so; no global time control |
| DB004 | high | No data freshness indicator on data that can be stale |
| DB005 | medium | More than about 9 widgets competing above the fold of a glance dashboard |
| DB006 | medium | Widgets that answer no stated question (vanity metrics: total sign-ups ever, page views without outcome) |
| DB007 | medium | Chart type mismatched to the question (pie over 5 slices, gauges, 3D, dual axes that imply correlation) |
| DB008 | medium | Truncated bar-chart baseline, or inconsistent scales between comparable charts |
| DB009 | medium | Whole-page spinner instead of per-widget loading; no empty, partial or error state per widget |
| DB010 | medium | Numbers formatted inconsistently (decimals, units, abbreviations like 1.2k vs 1,200) |
| DB011 | low | No drill-down from KPIs to the explaining view |
| DB012 | low | Charts with no accessible alternative (data table or summary text); graphical elements below 3:1 (WCAG 1.4.11) |

## Output

1. Viewer and question table: viewer, frequency, question, decision, widget
2. Widget spec: title (as the question or the metric), metric definition, comparison, threshold, chart type, drill-down
3. Layout: grid placement per breakpoint, filter bar, time range, freshness
4. States per widget
5. Review findings, if reviewing

## Additional Resources

| File | Content |
|------|---------|
| [dashboard-types.md](references/dashboard-types.md) | Operational, analytical, strategic: density, refresh, interaction, examples; question-first method |
| [layout-and-grid.md](references/layout-and-grid.md) | Grid placement, reading order, density budget, filters, responsive stacking, states |
| [widget-guide.md](references/widget-guide.md) | KPI card anatomy, chart choice by question, number formatting, thresholds, accessibility |
