# Responsive Patterns

## Page-level patterns

| Pattern | What happens | Use for |
|---------|--------------|---------|
| Mostly fluid | Same grid, margins grow, max width caps it | Content sites, simple apps |
| Column drop | Columns stack as width shrinks | Main + aside layouts |
| Layout shifter | Regions move to different positions per range | Complex apps; costs the most to build and test |
| Off-canvas | Secondary regions slide in on demand | Filters, nav, detail panes on compact |
| List-detail | Compact: list -> detail as two screens. Expanded: side by side | Mail, messages, settings, admin |
| Supporting pane | Main content + contextual pane that becomes a sheet on compact | Editors, maps, comments |

Behaviour matrix (write one for every screen):

| Region | Compact | Medium | Expanded |
|--------|---------|--------|----------|
| Navigation | Bottom bar | Rail | Rail + labels / drawer |
| Filters | Sheet from a button with active-count badge | Sheet | Left pane |
| Results | 1 column list | 2-column grid | 3-column grid |
| Detail | New screen | New screen | Right pane |

## Container queries

Use when a component's layout depends on its own width, not the page's.

```css
.card-list { container-type: inline-size; container-name: cards; }
@container cards (min-width: 30em) {
  .card { grid-template-columns: 8rem 1fr; }   /* media beside text */
}
```
Rule: page layout = media queries; reusable components = container queries. Container query units (`cqi`) let type
scale with the container.

## Tables

| Option | When |
|--------|------|
| Horizontal scroll in a focusable, labelled region with a sticky first column | Data comparison where columns matter (allowed by WCAG 1.4.10) |
| Priority columns: hide low-priority columns behind "Columns" control | Admin tables |
| Row -> card (label: value pairs) | Few rows, many columns, reading one record at a time |
| Summary row + expand | Financial and order tables |

## Images

- Resolution switching: `srcset` with width descriptors + `sizes` that matches the layout
  (`sizes="(min-width: 52.5em) 33vw, 100vw"`).
- Art direction: `<picture>` with different crops per range when the subject gets too small.
- Always set `width`/`height` or `aspect-ratio` to prevent layout shift.

## Forms

Single column at every width (multi-column forms get skipped fields and wrong reading order). Widen the form's max width
slightly on large screens; don't spread it across 12 columns. Field width hints expected length (postcode narrow, address
wide).

## Input and capability

```css
@media (hover: hover) and (pointer: fine) { .row-actions { opacity: 0; } .row:hover .row-actions { opacity: 1; } }
@media (pointer: coarse) { :root { --target-min: 44px; } }
```
Never hide functionality behind hover without a touch path.

## Foldables and odd viewports

- Dual-screen / foldables: treat the hinge as a fold; with the Viewport Segments API (`env(viewport-segment-width 0 0)`)
  put list and detail on either side.
- Landscape phones: compact height. Sticky headers and bottom bars eat most of the screen; collapse on scroll.
- Ultra-wide (> 2000px): cap content width; extra space goes to margins or an additional pane, never stretched text.
