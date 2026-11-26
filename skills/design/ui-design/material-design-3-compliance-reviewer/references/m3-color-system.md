# M3 Colour System

## How the scheme is built

1. A source colour (brand colour, or the user's wallpaper with dynamic colour on Android 12+) is converted to HCT
   (hue, chroma, tone).
2. Five key colours are derived: primary, secondary, tertiary, neutral, neutral variant (plus error).
3. Each key colour becomes a tonal palette of tones 0 (black) to 100 (white).
4. Colour roles pick tones from those palettes, differently for light and dark schemes.

Tone in HCT is perceptual lightness (CIE L*). Contrast follows from tone difference: about 40 tones apart gives roughly
3:1, about 50 gives roughly 4.5:1. That's why role pairs are safe when used as intended.

## Accent roles and tones

| Role | Light tone | Dark tone | Use |
|------|-----------|-----------|-----|
| primary | 40 | 80 | Key components: filled buttons, active states, FAB icon on some FABs |
| onPrimary | 100 | 20 | Text/icons on primary |
| primaryContainer | 90 | 30 | Tonal fills that need less emphasis (FAB, tonal buttons, selected chips) |
| onPrimaryContainer | 10 | 90 | Text/icons on primaryContainer |
| secondary / onSecondary / secondaryContainer / onSecondaryContainer | 40 / 100 / 90 / 10 | 80 / 20 / 30 / 90 | Less prominent components (filter chips, tonal buttons) |
| tertiary / onTertiary / tertiaryContainer / onTertiaryContainer | 40 / 100 / 90 / 10 | 80 / 20 / 30 / 90 | Contrasting accents, balance |
| error / onError / errorContainer / onErrorContainer | 40 / 100 / 90 / 10 | 80 / 20 / 30 / 90 | Errors |

Fixed accent roles (primaryFixed, primaryFixedDim, onPrimaryFixed, onPrimaryFixedVariant, and the same for secondary and
tertiary) keep the same tone in light and dark, for elements that must not change with the theme.

## Neutral roles

| Role | Light tone | Dark tone | Use |
|------|-----------|-----------|-----|
| surface | 98 | 6 | Default background |
| surfaceDim / surfaceBright | 87 / 98 | 6 / 24 | Dimmest / brightest surface |
| surfaceContainerLowest | 100 | 4 | |
| surfaceContainerLow | 96 | 10 | e.g. cards on surface |
| surfaceContainer | 94 | 12 | Navigation bar, menus |
| surfaceContainerHigh | 92 | 17 | Dialogs |
| surfaceContainerHighest | 90 | 22 | Filled text fields, input backgrounds |
| onSurface | 10 | 90 | Main text and icons |
| onSurfaceVariant | 30 | 80 | Secondary text and icons |
| outline | 50 | 60 | Important boundaries (text field outlines) |
| outlineVariant | 80 | 30 | Decorative dividers (not for boundaries that must meet 3:1) |
| inverseSurface / inverseOnSurface / inversePrimary | 20 / 95 / 80 | 90 / 20 / 40 | Snackbars and other contrasting elements |
| scrim, shadow | 0 | 0 | Overlays, shadows |

Surface containers replace shadow-based elevation for most components: a dialog is "higher" because it uses
surfaceContainerHigh, not because of a big shadow.

## Rules

- Always pair X with onX (primary with onPrimary, primaryContainer with onPrimaryContainer). Mixing pairs is the main
  source of contrast failures.
- outlineVariant is decorative; borders that identify components use outline.
- Disabled: onSurface at 38% for content, onSurface at 12% for containers (exempt from contrast, still legible).
- Contrast levels: M3 schemes support standard, medium and high contrast variants; Android 14+ exposes a user contrast
  setting. Test the high-contrast scheme.

## Dynamic colour and brand

| Situation | Approach |
|-----------|----------|
| Brand must stay recognisable | Turn off dynamic colour, or keep it but use brand colour in key moments (logo, illustrations) |
| Utility apps | Dynamic colour on; feels integrated with the device |
| Specific brand hues needed (red = sale) | Custom colours added as extra roles, harmonised toward the scheme (hue shifted slightly) with their own on/container roles |
| Semantic colours (success, warning) | Add as custom roles with container variants; M3 only defines error |

Tools: Material Theme Builder (Figma plugin and web) generates schemes, Figma variables and Compose/Views/web code.
