# Breakpoint Systems

Use an existing system when the product lives inside it (Android -> Material, a Tailwind codebase -> Tailwind), and adjust
only where content demands it.

## Material 3 window size classes (dp)

| Class | Width | Typical layout | Navigation |
|-------|-------|----------------|------------|
| Compact | < 600 | 1 pane | Navigation bar (bottom) |
| Medium | 600-839 | 1 pane (2 for list-detail with care) | Navigation rail |
| Expanded | 840-1199 | 1-2 panes | Navigation rail (or drawer) |
| Large | 1200-1599 | 2 panes | Rail or standard drawer |
| Extra-large | >= 1600 | 2-3 panes | Standard drawer |

Height classes also exist (compact < 480dp): a phone in landscape is wide but short, so avoid tall fixed headers.

## Apple size classes

Horizontal and vertical: compact or regular. iPhone portrait = compact width, regular height; most iPhones in landscape =
compact width, compact height; large iPhones in landscape = regular width; iPad full screen = regular x regular, but iPad
Split View and Slide Over can be compact width. Design for the class, not the device.

## Web frameworks (min-width, px)

| Framework | sm | md | lg | xl | 2xl |
|-----------|----|----|----|----|-----|
| Tailwind CSS | 640 | 768 | 1024 | 1280 | 1536 |
| Bootstrap 5 | 576 | 768 | 992 | 1200 | 1400 (xxl) |

These are defaults, not research findings. A design system with its own grid should map its ranges onto the framework's
config, not the other way round.

## Choosing your own

1. Start at 320px with the real content. Widen slowly.
2. Mark the widths where something stops working: line length, an aside that could fit, cards that could go 2-up, a
   table that now fits.
3. Merge marks closer than about 100px apart; keep 3-5 ranges.
4. Name them by size: compact / medium / expanded / large.
5. Check common viewports land mid-range, not right at an edge: 360-430 (phones), 768-834 (tablet portrait),
   1024-1180 (tablet landscape, small laptops), 1280-1536 (laptops), 1920 (desktop).

## Tokens

```json
{
  "breakpoint": {
    "medium":   { "$type": "dimension", "$value": "600px" },
    "expanded": { "$type": "dimension", "$value": "840px" },
    "large":    { "$type": "dimension", "$value": "1200px" }
  }
}
```
CSS custom properties cannot be used inside media queries, so the build step writes these values into the queries
(or into `@custom-media` with a PostCSS plugin).
