# Icon Grid and Keylines

## Canvas and live area

| Canvas | Padding | Live area | Typical stroke | Use |
|--------|---------|-----------|----------------|-----|
| 16 | 1 | 14 | 1 or 1.5 (2x only) | Dense UI, tables, inline with 12-14px text |
| 20 | 2 (or 1.5) | 16-17 | 1.5 or 2 | Compact UI |
| 24 | 2 | 20 | 2 (or 1.5) | Default UI icons (Material Symbols, Lucide, Feather style) |
| 32 / 48 | 2-4 | 28 / 40 | 2-3 | Feature icons, empty states |

Padding protects against clipping and gives optical room; strokes and protruding details may enter the padding sparingly.

## Keyline shapes (24px canvas, 20px live area)

| Shape | Size | Why |
|-------|------|-----|
| Circle | 20 diameter | Circles look smaller than squares of the same width |
| Square | 18 x 18 | |
| Portrait rectangle | 16 wide x 20 tall | |
| Landscape rectangle | 20 wide x 16 tall | |

Start each icon from the keyline that matches its silhouette. Icons that follow them look the same size even though
their boxes differ.

## Stroke system

| Decision | Options | Rule |
|----------|---------|------|
| Width | 1, 1.5, 2 | One width for the whole set at a given size; even widths for 24/20, 1px at 16 for 1x crispness |
| Caps | butt, round, square | One for the set; round is friendlier, butt is crisper on the grid |
| Joins | miter, round, bevel | Match caps (round + round) |
| Corner radius | 0, 1, 2 | One outer radius for the set; inner radius = outer - stroke |
| Gaps | >= stroke width | Narrower gaps fill in at 1x |

Strokes inside a filled set: when an icon set has filled variants (selected states), keep the same silhouette so switching
between outline and filled doesn't shift the icon.

## Optical balance

- Circles and diagonal shapes extend slightly past the square keyline to look the same size.
- Heavy shapes (filled areas) look larger: shrink them a little.
- Pointed shapes (play triangle, arrows) need optical centring: shift toward the point's opposite side.
- Compare icons side by side in a row with text; the row should look even in weight and height.

## Designing per size

Scaling a 24px icon to 16px gives 1.33px strokes and off-grid edges. For icons used at 16px:
- Redraw on the 16 grid with 1px strokes (or accept 2x-only rendering).
- Simplify: remove secondary details, widen gaps.
- Keep the same metaphor and silhouette so the two sizes read as the same icon.

## Metaphors

- One metaphor per concept across the product (trash for delete, not trash and X and minus).
- Prefer established conventions (magnifier = search, gear = settings, bell = notifications).
- Pair ambiguous icons with labels; icon-only buttons always get an accessible name and usually a tooltip.
