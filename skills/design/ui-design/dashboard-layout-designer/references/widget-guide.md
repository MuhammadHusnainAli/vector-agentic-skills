# Widget Guide

## KPI card anatomy

```
Net revenue                       (i)   <- metric name + definition tooltip
$1.24M                                  <- value, consistent format
▲ 8.2% vs last month   ↗ sparkline      <- delta with direction + comparison label + trend
94% of monthly target  [■■■■■■■■■□]     <- progress to target
Below target                            <- status as text (plus colour and icon)
```

Rules:
- Direction (up/down arrow) and goodness (green/red) are different things: rising costs are up and bad.
- Show the comparison label ("vs last month"); a bare "+8.2%" is ambiguous.
- Round for reading: $1.24M, not $1,238,472.19. Exact values in the tooltip or drill-down.
- Keep units in the value or the label, not both.

## Chart by question

| Question | Chart | Avoid |
|----------|-------|-------|
| How does it change over time? | Line (continuous), column (discrete periods) | Pie, area stacks with many series |
| How do categories compare? | Horizontal bar, sorted | Pie, radar, 3D bars |
| Part of a whole (2-5 parts) | Stacked bar, 100% bar, or donut with labels | Pie with > 5 slices |
| Progress to target | Bullet chart, progress bar | Gauges and speedometers (big for one number) |
| Distribution | Histogram, box plot | Averages alone |
| Relationship | Scatter | Dual-axis lines (imply correlation by scaling) |
| Ranking | Sorted bar or table with inline bars | Unsorted bars |
| Funnel conversion | Horizontal bars with step conversion % | Funnel shapes that distort widths |
| Exact lookup | Table with formatting and inline bars | Charts |

Bar charts start at zero. Line charts may not, but label the axis clearly. Comparable charts side by side share a scale.

## Number formatting

| Rule | Example |
|------|---------|
| Same decimals for the same metric everywhere | 4.2% everywhere, not 4.2% and 4.17% |
| Abbreviate consistently with locale | 1.2K / 3.4M (en-US); 1,2 Tsd. in de-DE contexts |
| Percent change vs percentage points | Conversion 4.0% -> 4.5% is +0.5 pp, or +12.5% |
| Negative numbers | Minus sign or parentheses in finance; never colour alone |
| Tabular figures | `font-variant-numeric: tabular-nums` so digits align in tables and counters |

## Thresholds and status

- Define thresholds with the metric owner; document them in the definition tooltip.
- Three levels at most (on track / at risk / off track). Status labels in text.
- Colour-blind-safe pairs: blue/orange rather than green/red alone; add icons (check, warning, cross).

## Accessibility

- Graphical elements needed to understand a chart: 3:1 against neighbours (WCAG 1.4.11).
- Each chart has a text summary ("Revenue rose 8% in November, driven by EMEA") and a data-table view.
- Patterns or direct labels instead of legend-matching by colour.
- Keyboard: focusable data points or a table; tooltips also on focus.
- Live updates on operational dashboards: don't announce every tick. Announce threshold crossings in a polite live region.
