# Fluent Foundations (Windows 11)

## Type ramp (Segoe UI Variable, epx)

| Style | Size / line height | Weight | XAML style resource |
|-------|-------------------|--------|---------------------|
| Caption | 12 / 16 | Regular | `CaptionTextBlockStyle` |
| Body | 14 / 20 | Regular | `BodyTextBlockStyle` |
| Body Strong | 14 / 20 | Semibold | `BodyStrongTextBlockStyle` |
| Body Large | 18 / 24 | Regular | `BodyLargeTextBlockStyle` |
| Subtitle | 20 / 28 | Semibold | `SubtitleTextBlockStyle` |
| Title | 28 / 36 | Semibold | `TitleTextBlockStyle` |
| Title Large | 40 / 52 | Semibold | `TitleLargeTextBlockStyle` |
| Display | 68 / 92 | Semibold | `DisplayTextBlockStyle` |

Segoe UI Variable adjusts its optical size automatically (Small, Text, Display). Body 14 is the default for UI text;
don't go below Caption 12.

## Spacing and sizing

- 4 epx base grid; common spacing: 4, 8, 12, 16, 24, 32, 48.
- Effective pixels (epx) scale with display scaling (100%, 125%, 150%, 200%); design at 100%.
- Control heights: standard controls about 32 epx (compact density 24); touch target minimum 40 x 40 epx.

## Corner radius

| Element | Radius |
|---------|--------|
| Top-level containers: windows, flyouts, dialogs, context menus | 8 epx (`OverlayCornerRadius`) |
| In-page controls: buttons, text boxes, list item backplates | 4 epx (`ControlCornerRadius`) |
| Maximised or snapped windows | 0 (system handles it) |
| Elements touching each other or the window edge | Don't round the touching edges |

## Materials

| Material | Use | Don't |
|----------|-----|-------|
| Mica | Base layer of long-lived windows (app background, title bar); picks up the desktop wallpaper tint | Use on transient surfaces |
| Mica Alt | Title bar area with tabs (stronger tint to separate tabs from content) | |
| Acrylic | Transient, light-dismiss surfaces: flyouts, context menus, some panes | Use as the whole app background |
| Smoke | Dims the app behind a modal ContentDialog | |
| Layering | Content sits on a "layer" surface (card-like, slightly lighter) above Mica | Paint opaque custom backgrounds over the whole window |

Materials fall back to solid colours when transparency effects are off, on battery saver, or in contrast themes. Designs
must work with the fallback.

## Colour and themes

- Light and Dark themes follow the system setting by default; the accent colour follows the user's Windows accent.
- Use theme resources (`TextFillColorPrimaryBrush`, `CardBackgroundFillColorDefaultBrush`, `AccentFillColorDefaultBrush`,
  `ControlStrokeColorDefaultBrush`) instead of hex values.
- Contrast themes (Aquatic, Desert, Dusk, Night sky, or user-defined) replace colours with a small system palette. Provide
  `HighContrast` theme dictionaries using system colour resources; never convey meaning by colour alone.
- Text contrast at least 4.5:1 in Light and Dark.

## Iconography

- Segoe Fluent Icons font for system-style icons (16 epx default in controls); outline style by default, filled for
  selected states.
- App icons: Windows 11 style is a layered, slightly rounded, front-facing perspective; provide target sizes from 16 to
  256 px (taskbar, Start, file explorer) and light/dark/contrast variants as needed.

## Motion

- Use built-in control animations and connected animations; keep transitions short and purposeful.
- Respect "Animation effects" off (Settings > Accessibility > Visual effects): no essential information in animation.
