# Implementation

## Tokens

Semantic tokens get a value per mode; primitives stay the same. Components only use semantic tokens.

```css
:root, [data-theme="light"] {
  color-scheme: light;
  --surface-base: oklch(100% 0 0);
  --text-default: oklch(21% 0.04 266);
}
[data-theme="dark"] {
  color-scheme: dark;
  --surface-base: oklch(18% 0.015 260);
  --text-default: oklch(92% 0.005 260);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface-base: oklch(18% 0.015 260);
    --text-default: oklch(92% 0.005 260);
  }
}
```

- `color-scheme` makes the browser render form controls, scrollbars and the default canvas in the right mode.
- `light-dark(light, dark)` (supported in current browsers) picks a value based on `color-scheme`:
  `--surface-base: light-dark(oklch(100% 0 0), oklch(18% 0.015 260));`
- Add a `<meta name="color-scheme" content="light dark">` to avoid a white flash before CSS loads.
- OKLCH is supported in all current evergreen browsers; provide hex fallbacks only if you must support older ones.

## Mode selection

| Option | Behaviour |
|--------|-----------|
| System (default) | Follows the OS setting via `prefers-color-scheme` |
| Light / Dark (user override) | Stored per user (account setting, local storage); applied before first paint |

Always offer System as the default. Persist the choice and apply it server-side or with an inline script in `<head>` to
avoid flashes.

## Platforms

| Platform | Mechanism |
|----------|-----------|
| iOS / iPadOS | Semantic system colours and asset catalog colours with Any/Dark (and high-contrast) appearances |
| Android | `values-night` resources or Material 3 dark colour scheme; `isSystemInDarkTheme()` in Compose |
| Windows | Light/Dark theme resources plus high-contrast theme dictionaries |
| Figma | Variable collection with Light and Dark modes; preview frames in each mode |

## Testing

- Every screen in both modes; states (hover, focus, error, disabled) in both.
- Contrast matrix (`contrast_matrix.mjs`) for all declared pairs; add pairs when new combinations appear.
- OLED device in a dim room: check smearing, glare and halation.
- Increase Contrast / forced colours settings in both modes.
- Images, illustrations, charts, emails (email clients have their own dark-mode transformations), PDFs and exports.
