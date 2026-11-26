# M3 Type, Shape, Elevation, States and Motion

## Type scale (baseline, Roboto; size / line height in sp)

| Role | Large | Medium | Small | Weight |
|------|-------|--------|-------|--------|
| Display | 57 / 64 | 45 / 52 | 36 / 44 | 400 |
| Headline | 32 / 40 | 28 / 36 | 24 / 32 | 400 |
| Title | 22 / 28 | 16 / 24 | 14 / 20 | 400 (L), 500 (M, S) |
| Body | 16 / 24 | 14 / 20 | 12 / 16 | 400 |
| Label | 14 / 20 | 12 / 16 | 11 / 16 | 500 |

- Use sp so text follows the user's font size (Android 14+ allows up to 200% with non-linear scaling for large text).
- Brand fonts replace Roboto per role (e.g. brand display face for Display/Headline, Roboto or brand text face for Body).
- Emphasised variants (M3 Expressive) add heavier weights per role; use them for emphasis, not as extra sizes.

## Shape scale (corner radius, dp)

| Token | Radius | Typical components |
|-------|--------|-------------------|
| None | 0 | Full-bleed surfaces |
| Extra small | 4 | Snackbars, menus (some), text field tops |
| Small | 8 | Chips |
| Medium | 12 | Cards, small FABs |
| Large | 16 | FABs, navigation drawers (end side), bottom sheets (top) |
| Extra large | 28 | Dialogs, large FABs |
| Full | 50% | Buttons, badges, search bars, sliders |

M3 Expressive adds intermediate steps (e.g. large-increased, extra-large-increased) and shape morphing; keep each
component on one token.

## Elevation levels

| Level | dp | Typical | How it shows |
|-------|----|---------|--------------|
| 0 | 0 | Flat cards, surfaces | - |
| 1 | 1 | Elevated cards, modal bottom sheets, banners | Surface container tone (+ subtle shadow where needed) |
| 2 | 3 | Navigation bar, menus, scrolled top app bar | Tone |
| 3 | 6 | FAB, dialogs, search bar | Tone + shadow on FAB |
| 4 | 8 | Hover/pressed FAB | |
| 5 | 12 | | |

Use tone (surface containers) to separate layers; shadows are reserved for elements that float (FAB, menus) and should
stay soft.

## State layers

| State | Opacity of the content colour over the container |
|-------|-----------------------------------------------|
| Hover | 8% |
| Focus | 10% (plus a focus indicator ring for keyboard) |
| Pressed | 10% (ripple) |
| Dragged | 16% |
| Disabled | Container onSurface 12%, content onSurface 38% |

## Motion

- Easing: standard `cubic-bezier(0.2, 0, 0, 1)` for most transitions; emphasised easing for expressive, larger moves;
  decelerate for entering, accelerate for exiting.
- Durations scale with distance and size: short (50-200ms) for small state changes, medium (250-400ms) for component
  transitions, long (450-600ms) for full-screen transitions.
- M3 Expressive moves to a spring-based motion system (spatial and effects springs) in Compose Material 3 Expressive.
- Transition patterns: container transform, shared axis (x/y/z), fade through, fade.
- Respect "Remove animations" (animator duration scale 0): don't hide meaning in motion.
