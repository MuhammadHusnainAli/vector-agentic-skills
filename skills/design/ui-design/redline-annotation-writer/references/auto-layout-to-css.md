# Auto Layout to CSS

## Direction, gap, padding

| Figma | CSS |
|-------|-----|
| Auto layout vertical | `display: flex; flex-direction: column;` |
| Auto layout horizontal | `display: flex; flex-direction: row;` |
| Wrap | `flex-wrap: wrap;` (with row gap = `row-gap`) |
| Gap between items | `gap: var(--space-4);` |
| Gap "Auto" (space between) | `justify-content: space-between;` |
| Padding | `padding: var(--space-4) var(--space-6);` |
| Grid auto layout | `display: grid; grid-template-columns: ...;` |

## Alignment

| Figma (horizontal layout) | CSS |
|---------------------------|-----|
| Align top / centre / bottom | `align-items: flex-start / center / flex-end;` |
| Align left / centre / right | `justify-content: flex-start / center / flex-end;` |
| Text baseline alignment | `align-items: baseline;` |

For vertical layouts, swap: horizontal alignment maps to `align-items`, vertical to `justify-content`.

## Child sizing

| Figma child setting | CSS on the child |
|---------------------|------------------|
| Fixed width 240 | `flex: 0 0 240px;` (or `width: 240px; flex-shrink: 0;`) |
| Hug contents | `flex: 0 0 auto;` |
| Fill container | `flex: 1 1 0; min-width: 0;` (min-width 0 lets text truncate) |
| Min / max width | `min-width: ...; max-width: ...;` |
| Fill in a vertical layout | `flex: 1 1 0; min-height: 0;` or `align-self: stretch` for width |

The `min-width: 0` on fill children is the most common missing rule: without it, long text prevents shrinking and
breaks truncation.

## Constraints and absolute position

| Figma | CSS |
|-------|-----|
| Absolute position inside auto layout | `position: absolute;` in a `position: relative` parent |
| Constraints left & right | `left: Xpx; right: Ypx;` (stretches) |
| Constraint centre | `left: 50%; transform: translateX(-50%);` |
| Scale | Percent-based sizes |

## Scroll and sticky

| Figma prototype setting | CSS |
|-------------------------|-----|
| Overflow vertical scroll | `overflow-y: auto;` on a container with a bounded height |
| Fixed position when scrolling | `position: sticky; top: 0;` (inside its scroll container) or `position: fixed` for viewport-fixed |
| Clip content | `overflow: hidden;` |

## Text

| Figma | CSS |
|-------|-----|
| Truncate text (1 line) | `white-space: nowrap; overflow: hidden; text-overflow: ellipsis;` |
| Max lines N | `display: -webkit-box; -webkit-line-clamp: N; -webkit-box-orient: vertical; overflow: hidden;` |
| Auto height | Default block behaviour |
| Fixed size text box | Usually wrong in production; annotate the real rule |
