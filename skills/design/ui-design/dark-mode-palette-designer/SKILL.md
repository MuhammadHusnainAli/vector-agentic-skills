---
name: dark-mode-palette-designer
description: "Design dark themes that are comfortable and accessible rather than inverted: semantic roles remapped per mode (not inverted hex values), dark grey base surfaces instead of pure black, elevation shown by lighter surfaces instead of shadows, text at softened white with a clear hierarchy, accents lightened and desaturated in OKLCH so they don't vibrate, state colours and borders re-tuned, images, illustrations, charts and brand colours adapted, and both WCAG 2 contrast and APCA checked per pair in every mode. Covers OKLCH ramps, the CSS color-scheme property, prefers-color-scheme, light-dark(), token modes and testing. Ships contrast_matrix.mjs (Node, no dependencies) that computes WCAG ratios, APCA Lc and OKLCH for every text/surface pair in each mode, with per-kind thresholds, alpha compositing, missing-token checks and dark-mode warnings. Use when creating or reviewing a dark theme, fixing dark-mode contrast or building light/dark colour tokens."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Dark Mode Palette Designer

Dark mode is a second palette designed for different conditions: low ambient light, OLED screens, and eyes adapted to
dark surroundings. Inverting the light palette gives the usual problems: pure black with pure white text that glows
(halation), saturated brand colours that vibrate, shadows nobody can see, and grey text that passed in light mode but
fails in dark. This skill remaps the semantic roles for dark, tunes them in OKLCH, and checks every pair with WCAG and
APCA.

## Trigger Conditions

Activate this skill when the user:
- Adds dark mode to a product or design system
- Has a dark theme that feels harsh, muddy, or fails contrast
- Defines light/dark colour tokens, or Figma variable modes
- Wants text/surface pairs checked with WCAG and APCA

Token structure and modes: `design-token-architecture-builder`. Button state colours: `button-state-variant-designer`.
Elevation in dark mode: `elevation-shadow-system-designer`.

## Workflow

```
1. ROLES     -> list semantic roles and the pairs that are actually used (text on surface, icon on action, border on surface)
2. SURFACES  -> dark base (about 12-20% OKLCH lightness), raised surfaces lighter per level (references/dark-palette-method.md)
3. TEXT      -> primary about 90-95% lightness, secondary and disabled steps; never pure white on near-black for long text
4. ACCENTS   -> lighten and desaturate actions, links and status colours; check on-colours (text on accent)
5. BORDERS   -> re-tune for visibility (non-text 3:1 where they identify components)
6. MEDIA     -> images, illustrations, logos, charts, shadows, maps
7. CHECK     -> node scripts/contrast_matrix.mjs palette.json --apca   (references/contrast-wcag-and-apca.md)
8. SHIP      -> tokens per mode, color-scheme, prefers-color-scheme + manual toggle (references/implementation.md)
```

## Principles

| Principle | Why |
|-----------|-----|
| Remap roles, don't invert values | The surface hierarchy reverses (raised = lighter); accents need new values |
| No pure black base for UI | Smearing on OLED during scrolling, harsh contrast; use dark grey with a slight brand tint |
| Elevation = lighter surface | Shadows don't show on dark; lighter surfaces (and subtle borders) separate layers |
| Soften white text | Pure white on near-black causes halation for many readers (especially with astigmatism) |
| Desaturate accents | Saturated colours vibrate on dark; lower chroma and raise lightness |
| Check both polarities | Passing in light doesn't mean passing in dark; APCA treats light-on-dark more strictly |
| Same meaning, both modes | Success, warning and danger stay recognisable in both |

## Check Codes (contrast_matrix.mjs)

| Code | Severity | Problem |
|------|----------|---------|
| DM001 | error | Pair below the WCAG 2 threshold for its kind |
| DM002 | warn | Pair below the APCA threshold (fails the run with `--apca`) |
| DM003 | error | Token missing in a mode |
| DM004 | info | Pure black surface in dark mode |
| DM005 | info | Pure white text on a very dark surface |
| DM006 | info | Highly saturated text colour in dark mode |

## Scripts

```bash
node scripts/contrast_matrix.mjs palette.json [--apca] [--json]
```
`palette.json` holds `modes` (mode -> token -> colour) and `pairs` (`[foreground, background, kind]`, kind = body, large,
non-text or incidental). Thresholds: body 4.5:1 / Lc 75, large 3:1 / Lc 60, non-text 3:1 / Lc 45. Ratios are truncated,
never rounded up. Colours with alpha are composited over their background. Modes whose names contain dark, night or dim
get the dark-mode checks. Needs Node 18+; no packages.
Exit codes: 0 all pass, 1 failures (WCAG; APCA too with `--apca`), 2 bad input.

## Output

1. Dark palette: role -> value for light and dark, with OKLCH
2. Surface elevation steps and text hierarchy
3. Contrast matrix for both modes with fixes for failures
4. Media and data-viz adjustments
5. Implementation notes (tokens, CSS, platform settings)

## Additional Resources

| File | Content |
|------|---------|
| [dark-palette-method.md](references/dark-palette-method.md) | Surface, text, accent, border and status recipes in OKLCH; elevation; images; charts; brand |
| [contrast-wcag-and-apca.md](references/contrast-wcag-and-apca.md) | WCAG 2 vs APCA, thresholds, polarity, what passes where, reporting both |
| [implementation.md](references/implementation.md) | Token modes, CSS color-scheme, prefers-color-scheme, light-dark(), toggles, platform settings, testing |
