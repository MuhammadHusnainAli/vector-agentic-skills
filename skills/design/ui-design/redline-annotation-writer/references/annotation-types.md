# Annotation Types

| Category | Annotate | Wording template |
|----------|----------|------------------|
| Spacing | Gaps and padding as tokens, especially where they change | "Card padding: space.6 (space.4 below 600)" |
| Sizing | Fixed, hug, fill, min, max, aspect ratio | "Name column: fill, min 200; Status: hug; Actions: fixed 48" |
| Alignment | Alignment and distribution that aren't obvious | "Prices right-aligned, tabular figures" |
| Typography | Only exceptions to the text styles | "Title uses heading.md; clamps to 2 lines" |
| Colour | Only when a token isn't obvious from the variable | "Row hover: surface.hover (not the selected colour)" |
| Content | Truncation, wrapping, line clamps, max chars, empty values | "Description: 3 lines then ellipsis; full text on detail page" |
| Responsive | Changes per breakpoint and the rule between | "Below 768: filters move into a sheet behind a 'Filters' button with count" |
| Scroll | What scrolls, what's fixed, sticky thresholds | "Table scrolls horizontally inside its card; first column sticky" |
| Layering | z-order, overlap, scrims | "Menu overlaps the sticky header" |
| States | Differences between states that aren't separate frames | "Selected row: 2px left border action.primary + surface.selected" |
| Motion | Pointer to the motion spec | "Panel slides in from right, duration.slow, easing.enter" |
| Platform | Native components or behaviours | "iOS: use system share sheet" |

## Sizing vocabulary

| Term | Meaning |
|------|---------|
| Fixed | Exact size; doesn't change with content or container |
| Hug | Size to content |
| Fill | Take remaining space in the parent (shared with other fill items) |
| Min / max | Limits on hug or fill |
| Aspect ratio | Height follows width (images, video, cards with media) |

## Examples of good annotations

1. "Page content max-width 1200, centred; side margins space.8 (space.4 below 600)."
2. "Sidebar fixed 280; collapses to 72 (icons only) below 1024; overlay drawer below 768."
3. "KPI cards: 4 per row at >= 1200, 2 per row 600-1199, 1 per row below 600. Equal heights per row."
4. "Customer name: single line, ellipsis; tooltip with full name on hover and focus."
5. "Footer actions stick to the bottom of the sheet; content scrolls above them."
