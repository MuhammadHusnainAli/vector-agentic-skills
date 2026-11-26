# Illustration System for Empty States

## Style rules (write these down once)

| Rule | Decide |
|------|--------|
| Style | Flat, line, isometric, 2.5D, hand-drawn: one style |
| Palette | 2-4 colours from the brand palette + neutrals; works in light and dark |
| Line weight | One weight at each size (if line-based) |
| Perspective | Front or one consistent angle |
| People | Whether to show people; if yes, diverse and not tied to one culture's gestures |
| Metaphor | Objects that relate to the feature (folder, inbox, chart), not generic mascots |
| Detail | Low; reads at the smallest size |

## Sizes

| Context | Size (CSS px) | Notes |
|---------|---------------|-------|
| Full page | 160-240 | Action must stay above the fold on a 1366 x 768 laptop and on phones |
| Panel / modal | 96-128 | |
| Card / small container | 48-64 | Often an icon is better |
| Inline / widget | Icon 24-32, or none | |

Provide each illustration as SVG (or optimised PNG/WebP at 1x/2x). Keep SVGs small: simplified paths, no embedded
rasters.

## Dark mode

- Transparent backgrounds; no white blobs.
- Colours that hold contrast on dark surfaces; outline colours from tokens if lines must adapt.
- Either one illustration that works on both, or light/dark variants switched with `<picture>` and
  `prefers-color-scheme`, or SVGs using `currentColor` and CSS variables.

## Accessibility

- Illustrations in empty states are usually decorative: `alt=""` or `aria-hidden="true"`. The headline carries meaning.
- If the illustration conveys information not in the text, describe it in alt text (rare; better to put it in the text).
- No flashing or looping animations; respect reduced motion for animated illustrations (Lottie).

## Production

- Build a set, not one-offs: list all states that get illustrations (from the inventory) and commission them together.
- Naming: `empty-<feature>-<type>.svg` (e.g. `empty-invoices-first-use.svg`).
- Store in the design system with usage notes; Figma components with size variants.

## Illustration brief template

```
Feature / state: Invoices, first use
Purpose: Show that invoices are created from orders automatically; encourage connecting a store
Context and size: Full page, 200 px, light and dark
Content ideas: Paper invoice sliding out of a shop window; envelope; checkmark
Must avoid: Text in the image, money symbols tied to one currency, mascots
Style references: (links to existing set)
Deliverables: SVG light + dark, Figma component, PNG preview
```
