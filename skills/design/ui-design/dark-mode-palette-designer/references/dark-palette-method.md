# Dark Palette Method

Work in OKLCH (lightness L 0-100%, chroma C, hue h). Lightness is perceptual, so equal L steps look like equal steps,
which HSL doesn't give you.

## Surfaces

| Role | Light | Dark (starting point) |
|------|-------|-----------------------|
| surface.base (page) | oklch(100% 0 0) | oklch(16-20% 0.01-0.02 h_brand) |
| surface.raised (cards) | oklch(100% 0 0) + shadow | base + 3-5% L |
| surface.overlay (menus, dialogs) | oklch(100% 0 0) + larger shadow | base + 6-10% L |
| surface.sunken (wells, inputs) | oklch(97% 0.005 h) | base - 2-3% L, or base with a border |
| surface.inverse | oklch(20% 0.02 h) | oklch(92% 0.01 h) |

- A slight hue tint (chroma 0.01-0.02 toward the brand hue) keeps dark greys from looking dead.
- Each elevation step must be visible: about 3-5% L apart at minimum.
- Material's dark baseline uses #121212 (about oklch(18% 0 0)) for the same reasons.

## Text hierarchy (on dark base)

| Role | Dark value | Notes |
|------|-----------|-------|
| text.default | oklch(90-94% 0.005 h) | Softened white; still well above 4.5:1 |
| text.subtle | oklch(70-75% 0.01 h) | Check against raised surfaces too, not only base |
| text.disabled | oklch(50-55% 0.01 h) | Exempt from contrast but should be readable |
| text.placeholder | Same as subtle if it carries meaning | Placeholders that fail 4.5:1 shouldn't hold information |

## Accents and status colours

Starting from the light-mode accent (often around L 50-55%, high chroma):
- Raise lightness to about L 65-75% so it reads on dark.
- Reduce chroma by 10-30% to stop vibration (very saturated blue, red and magenta glow on dark).
- Keep hue, adjusting by a few degrees if the colour shifts perceptually (blues can turn purple when lightened; correct the
  hue back).
- Text on accent fills: in dark mode accent fills are lighter, so their on-colour usually becomes dark (oklch(20% ...)).
  Check both options and pick the one with better contrast.

| Role | Light | Dark |
|------|-------|------|
| action.primary.bg | oklch(55% 0.21 263) | oklch(70% 0.15 258) |
| action.primary.fg | white | oklch(20% 0.03 265) |
| text.link | oklch(50% 0.2 263) | oklch(75% 0.12 255) |
| status.danger.fg | oklch(55% 0.21 27) | oklch(72% 0.16 25) |
| status.danger.bg (subtle) | oklch(96% 0.03 20) | oklch(28% 0.06 25) |

## Borders and dividers

- Borders that identify a component (input outlines, outline buttons) need 3:1 against adjacent colours in both modes.
- Decorative dividers can be subtle, about base + 8-12% L.
- In dark mode borders do more work, because shadows don't separate surfaces.

## Shadows and elevation

Shadows barely show on dark. Use lighter surfaces per level, optionally with a 1px top highlight or subtle border. Keep
a soft dark shadow for floating elements (menus) to separate them from content behind them.

## Images, illustrations, logos

- Full-colour photos: usually unchanged; reduce brightness slightly (filter: brightness(0.9)) if they glare.
- Illustrations with white backgrounds: provide dark variants or transparent backgrounds.
- Logos: dark-mode version (light wordmark), never a logo on a white box.
- Screenshots of the product: show the matching theme.

## Data visualisation

- Re-tune categorical palettes for dark: higher lightness, lower chroma, re-check that series stay distinguishable.
- Gridlines and axes: subtle but visible (non-text 3:1 where needed to read values).
- Sequential scales usually reverse direction of lightness (more = lighter on dark).

## Brand colours

Brand guidelines often specify one hex for the primary colour. In dark mode, keep the brand hue but adjust lightness and
chroma for legibility. Agree this with the brand team as a "dark-mode brand variant" rather than breaking contrast.
