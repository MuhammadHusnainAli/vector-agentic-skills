---
name: icon-pixel-grid-aligner
description: "Draw and fix UI icons so they render crisply and read as one family: icon grids and keylines (16, 20, 24, 32 with 1-2px padding and live area, keyline shapes for circles, squares and rectangles), pixel snapping rules (fills on whole pixels, odd strokes on half pixels, even strokes on whole pixels), stroke width, caps, joins and corner radius consistency, optical size and weight balance, sizes that scale cleanly (designing per size vs scaling), SVG export settings (flatten transforms, outline or keep strokes, no stray groups, rounded coordinates, currentColor), and icon font vs SVG sprite delivery. Ships svg_grid_check.mjs (Node, no dependencies) that checks SVG icons or folders for off-grid edges (with snapped values), wrong stroke widths, viewBox and transform problems, geometry outside the live area and mixed caps and joins across a set. Use when designing an icon set, reviewing icons that look blurry or inconsistent, or preparing icons for export."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Icon Pixel Grid Aligner

An icon at 16-24px is only a few hundred pixels. A horizontal edge that sits half a pixel off turns a crisp line into two
grey rows, and a set that mixes 1.5px and 2px strokes reads as two families. High-density screens hide some of this, but
1x screens, small sizes and Windows ClearType-era displays show it at once. This skill sets up the grid and the drawing
rules, and checks SVGs for edges that will blur.

## Trigger Conditions

Activate this skill when the user:
- Designs or extends an icon set
- Says icons look blurry, uneven or inconsistent
- Exports icons from Figma, Illustrator or another tool for code
- Reviews icon SVGs before adding them to a library

Android launcher icons: `android-adaptive-icon-designer`. Asset names and formats: `asset-export-naming-planner`.

## Workflow

```
1. GRID      -> pick the canvas (24 most common; 16/20 for dense UI) and padding (references/icon-grid-and-keylines.md)
2. STYLE     -> stroke width, caps, joins, corner radius, fill vs outline, perspective: write them down
3. DRAW      -> start from keyline shapes; snap edges (fills whole px, odd strokes half px, even strokes whole px)
4. OPTICAL   -> balance visual weight and size across the set (circles slightly larger than squares)
5. SIZES     -> design a separate 16px version for complex icons instead of scaling 24 down
6. EXPORT    -> flatten transforms, consistent strokes, currentColor, viewBox 0 0 N N (references/export-and-delivery.md)
7. CHECK     -> node scripts/svg_grid_check.mjs icons/ --grid 24 --stroke 2 --padding 2
8. REVIEW    -> view the set at 1x and 2x side by side, in light and dark, next to text
```

## Snapping Rules

| Geometry | Edge position | Example (24px grid) |
|----------|---------------|---------------------|
| Filled shape | Whole pixel | Rect from x=4 to x=20 |
| 1px stroke (odd) | Stroke centre on .5 | Horizontal line at y=11.5 |
| 2px stroke (even) | Stroke centre on whole pixel | Horizontal line at y=12 |
| 1.5px stroke | Can't be crisp at 1x | Use only if the set is only shown at 2x or larger |
| Curves and diagonals | Not snappable; keep anchor points on the grid where the curve meets straight segments | |

Only these rules make edges crisp at 1x. At 2x, half-pixel errors are less visible but still soften stroke ends.

## Check Codes (svg_grid_check.mjs)

| Code | Severity | Problem |
|------|----------|---------|
| IG001 | warn | viewBox missing, offset, or not the grid size |
| IG002 | warn | Horizontal or vertical edge off the pixel grid (with the snapped value) |
| IG003 | warn | Stroke width differs from the set, or fractional |
| IG004 | warn | transform attribute (flatten it) |
| IG005 | warn | Geometry outside the live area or the viewBox |
| IG006 | info | Coordinates with 3+ decimals |
| IG007 | warn | Set mixes stroke caps or joins |

## Scripts

```bash
node scripts/svg_grid_check.mjs icons/ [more.svg] [--grid 24] [--stroke 2] [--padding 2] [--json]
```
Handles `path` (all commands, absolute and relative), `rect`, `line`, `polyline`, `polygon`, `circle` and `ellipse`, with
stroke settings inherited from the `<svg>` element. Only axis-aligned edges are checked; review curves visually. The script
reports but doesn't rewrite. Snap in the design tool, then re-export. Needs Node 18+; no packages.
Exit codes: 0 no warnings, 1 warnings, 2 bad arguments, no SVGs or invalid path data.

## Output

1. Grid spec: canvas, padding, live area, keyline shapes, stroke, caps, joins, radius
2. Per-icon findings with the fixes (snap values), plus set-level consistency notes
3. Export settings for the design tool and the delivery format

## Additional Resources

| File | Content |
|------|---------|
| [icon-grid-and-keylines.md](references/icon-grid-and-keylines.md) | Canvases, padding, keylines, stroke systems, optical balance, sizes, metaphors |
| [export-and-delivery.md](references/export-and-delivery.md) | Figma/Illustrator export settings, SVG cleanup, currentColor, sprites vs components vs icon fonts, accessibility |
