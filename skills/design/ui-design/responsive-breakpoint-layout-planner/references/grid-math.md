# Grid Math

## Column width

```
content  = min(viewport, max_width) - 2 x margin
column   = (content - (columns - 1) x gutter) / columns
span(n)  = n x column + (n - 1) x gutter
```

Always compute at both edges of a range. A column that is 60px at 1024 and 30px at 768 within one range means the range is
too wide.

### Worked grid (8px base)

| Range | Viewport | Cols | Gutter | Margin | Max width | Column width |
|-------|----------|------|--------|--------|-----------|--------------|
| compact | 360 | 4 | 16 | 16 | - | (360-32-48)/4 = 70 |
| compact | 599 | 4 | 16 | 16 | - | (599-32-48)/4 = 129.75 |
| medium | 600 | 8 | 24 | 24 | - | (600-48-168)/8 = 48 |
| medium | 839 | 8 | 24 | 24 | - | (839-48-168)/8 = 77.9 |
| expanded | 840 | 12 | 24 | 32 | - | (840-64-264)/12 = 42.7 |
| expanded | 1439 | 12 | 24 | 32 | - | (1439-64-264)/12 = 92.6 |
| large | 1440+ | 12 | 32 | auto | 1280 | (1280-352)/12 = 77.3 |

Rules of thumb:
- Gutter at least equal to the base spacing unit; margins at least the gutter.
- Fractional column widths are fine in CSS grid (`1fr`); don't round each column, the remainder accumulates.
- Use 4 columns on compact (halves and quarters), 8 on medium, 12 on expanded (halves, thirds, quarters).

## Measure

Body text reads best at about 45-75 characters per line. In CSS: `max-inline-size: 66ch` on text containers. At 16px with
an average font, 66ch is about 520-560px: a 12-column layout at 1440 puts body text in 6-7 columns, not 12.

## Fluid values with clamp()

To scale a value from `min` at viewport `vmin` to `max` at `vmax` (all in px, converted to rem with 16px = 1rem):

```
slope      = (max - min) / (vmax - vmin)
intercept  = min - slope x vmin
value      = clamp(min_rem, intercept_rem + (slope x 100)vw, max_rem)
```

Example: heading 28px at 360 -> 48px at 1440.
```
slope     = 20 / 1080            = 0.018519
intercept = 28 - 0.018519 x 360  = 21.333px = 1.3333rem
value     = clamp(1.75rem, 1.3333rem + 1.8519vw, 3rem)
```

Zoom safety: because part of the value is rem, it grows with the user's font size. Check that at 200% zoom the maximum
size is at least 2x the minimum (here 48 / 28 = 1.71, fine because the rem part also doubles). If `max / min > 2.5`, the
vw term dominates and zoom barely changes the size: lower the max or widen the range.

Fluid spacing uses the same formula (e.g. section padding 24px -> 64px). Keep small values (borders, icon gaps) fixed.

## px to em for media queries

`em in media queries = px / 16` (always the browser default font size, not your root font size).
600px = 37.5em, 840px = 52.5em, 1200px = 75em.

## Avoiding range gaps

```css
/* mobile-first: no overlap, no gap */
@media (min-width: 37.5em) { ... }   /* medium   */
@media (min-width: 52.5em) { ... }   /* expanded */

/* if max-width is unavoidable, use range syntax */
@media (37.5em <= width < 52.5em) { ... }
```
`max-width: 767px` + `min-width: 768px` leaves 767.5px (zoomed or high-DPI windows) matched by neither.
