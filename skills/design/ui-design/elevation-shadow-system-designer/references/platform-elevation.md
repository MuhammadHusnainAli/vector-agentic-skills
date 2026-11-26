# Platform Elevation

## Material 3

- Six levels (0, 1, 3, 6, 8, 12 dp). Elevation is shown mainly with surface colour (surface container roles: lowest,
  low, default, high, highest), not shadows.
- Shadows remain for elements that float over content: FABs, menus, elevated cards, modal sheets.
- Mapping: cards -> level 1 / surfaceContainerLow; navigation bar -> level 2 / surfaceContainer; menus and FAB -> level 3;
  dialogs -> level 3 with surfaceContainerHigh.

## Apple (iOS, iPadOS, macOS)

- Depth comes from materials (blur and vibrancy: ultra-thin to thick) and system backgrounds (systemBackground,
  secondarySystemBackground, tertiarySystemBackground), not from shadow scales.
- Since iOS 26 / macOS 26, Liquid Glass gives controls and bars a translucent, layered look with system-managed lighting.
- Custom shadows are subtle; sheets and popovers get system shadows. Avoid heavy drop shadows on cards.

## Fluent 2 (Windows, Microsoft 365)

- Shadow ramp tokens: shadow2, shadow4, shadow8, shadow16, shadow28, shadow64 (number = elevation depth), each made of
  a key and an ambient layer.
- Typical mapping: cards and list items on hover -> 2-4; command bars and tooltips -> 8; flyouts and menus -> 16;
  dialogs -> 64 (with Smoke behind); teaching tips -> 16-28.
- Windows 11 materials (Mica, Acrylic) carry most of the layering in apps.

## Mapping your levels

| Your level | Material 3 | Fluent | Apple |
|------------|-----------|--------|-------|
| 1 card | Level 1, surfaceContainerLow | shadow2-4 | secondarySystemBackground grouping |
| 2 sticky | Level 2, surfaceContainer | shadow8 | Bar material |
| 3 menu | Level 3 | shadow16 | Popover / menu (system) |
| 4 dialog | Level 3, surfaceContainerHigh + scrim | shadow64 + Smoke | Sheet / alert (system) |
| 5 toast/drag | Level 4-5 | shadow28 | System-defined |

In cross-platform products, keep the semantic levels shared and let each platform render them natively.
