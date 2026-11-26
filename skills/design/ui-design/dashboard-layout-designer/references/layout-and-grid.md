# Layout and Grid

## Reading order

Left-to-right readers scan top-left first, then across the top, then down the left (F-pattern on dense pages). Place:
1. Page title, global filters and time range, freshness stamp (one row)
2. KPI row: the 3-5 headline numbers with comparisons
3. The primary chart that explains the top KPI (wide, 8-12 columns)
4. Supporting breakdowns (4-6 columns each)
5. Detail tables and feeds (full width, lowest)

For right-to-left locales, mirror the layout.

## 12-column placement (desktop, about 1280-1440px)

| Row | Widgets | Span |
|-----|---------|------|
| 1 | Filter bar + time range + "Updated 3 min ago" | 12 |
| 2 | 4 KPI cards | 3 + 3 + 3 + 3 |
| 3 | Primary trend chart + target progress | 8 + 4 |
| 4 | Breakdown by segment + by channel + top items | 4 + 4 + 4 |
| 5 | Detail table | 12 |

Widget heights on a row unit (e.g. 8px x n) so rows align; equal heights within a row.

## Density budget

| Dashboard type | Widgets above the fold (1080p) | Notes |
|----------------|-------------------------------|-------|
| Operational wallboard | 4-8 large tiles | Readable from 3 m; status + number |
| Executive | 4-6 KPIs + 1-2 charts | Commentary text beside numbers |
| Product / analytical | 6-9 | Filters and tables carry the detail |

Beyond the budget: tabs by question area, or a second dashboard. Scrolling is fine for analytical pages, but the top must
summarise.

## Filters

- Global filters (time range, region, product) in one bar at the top; they apply to every widget.
- Widget-level filters only when that widget answers a different question; show the override in its title
  ("Revenue by channel, last 90 days").
- Show active filters as removable chips; "Reset" restores defaults.
- Persist filters in the URL so views can be shared.

## Time range

- Presets that match decisions: Today, Last 7 days, Month to date, Quarter to date, Last 12 months, Custom.
- Comparison period selector (previous period / same period last year) beside it.
- Incomplete periods are marked (today is partial: dashed line or lighter bar), so a falling final point is not misread.

## States per widget

| State | Display |
|-------|---------|
| Loading | Skeleton in the widget's shape; other widgets render as they arrive |
| Empty | "No orders in this period" + suggestion (widen range, clear filter) |
| Partial | Data until X; banner in the widget |
| Stale | Freshness turns amber/red with time since update |
| Error | "Couldn't load. Retry" in the widget; rest of page works |
| No permission | Explain who can grant access; don't show a broken tile |

## Responsive stacking

On medium and compact widths, stack widgets in priority order (not left-to-right order). KPI cards go 2-up then 1-up.
Wide charts keep their aspect ratio by reducing height less than width, or switch to a simpler form (sparkline +
number). Tables become scrollable with a sticky first column.
