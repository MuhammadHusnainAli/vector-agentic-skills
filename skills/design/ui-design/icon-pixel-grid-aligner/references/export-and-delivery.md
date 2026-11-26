# Export and Delivery

## Before export (Figma / Illustrator)

- Frame exactly the canvas size (24 x 24) at 0,0; nothing outside the frame.
- Pixel grid and snap-to-pixel on; nudge by whole or half pixels per the snapping rules.
- Flatten or outline as the delivery needs:
  - **Keep strokes** if code should be able to change the stroke width (Lucide-style sets). All icons must then be pure
    strokes with consistent settings on the root `<svg>`.
  - **Outline strokes** (convert to fills) for fixed-weight sets, icon fonts and anything with mixed strokes and fills.
- Union and flatten boolean operations; remove hidden layers and empty groups.
- No transforms: rotated or scaled layers export as `transform` attributes; flatten them.

## SVG cleanup

| Issue | Fix |
|-------|-----|
| `width`/`height` hard-coded | Keep `viewBox="0 0 24 24"`; set size in CSS or props |
| Hex fills/strokes | `currentColor` so icons inherit text colour |
| Editor metadata, ids, classes | Strip (SVGO with a config that keeps viewBox) |
| 5-6 decimal coordinates | Round to 2 decimals or less (SVGO `floatPrecision: 2`); re-check alignment afterwards |
| `<title>` from layer names | Remove; accessibility names are set where the icon is used |
| Clip paths and masks from frames | Remove unless needed |

SVGO config essentials:
```js
export default {
  multipass: true,
  floatPrecision: 2,
  plugins: [
    { name: "preset-default", params: { overrides: { removeViewBox: false } } },
    "removeDimensions",
    { name: "convertColors", params: { currentColor: true } },
  ],
};
```

## Delivery formats

| Format | Pros | Cons |
|--------|------|------|
| Inline SVG components (React/Vue) | Styleable, tree-shakeable, accessible | Bundle size if many icons per page |
| SVG sprite (`<symbol>` + `<use>`) | One request, cacheable | Cross-origin and styling limits |
| Icon font | Easy in legacy stacks | Blurry hinting, accessibility issues (screen readers read glyphs), FOUT; avoid for new work |
| PNG | Only for platforms that need raster | No scaling; multiple densities |

## Accessibility

- Decorative icons next to text: `aria-hidden="true"`, `focusable="false"`.
- Meaningful standalone icons: name on the control (`<button aria-label="Delete">`), not on the SVG.
- Icons that convey status (error, success) need a text equivalent.
- Non-text contrast: icons needed to understand the UI need 3:1 against the background (WCAG 1.4.11).
- Forced colors: `currentColor` icons follow system colours automatically.
