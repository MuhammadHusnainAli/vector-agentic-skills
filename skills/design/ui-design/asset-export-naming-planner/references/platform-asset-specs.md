# Platform Asset Specs

## iOS

- Scales: @2x and @3x for current devices (@1x only for very old devices and some Mac/iPad contexts).
- Asset catalogs (`.xcassets`): image sets with scale slots, appearances (Any, Dark, High contrast), and directions
  (left-to-right / right-to-left / both). Vector PDF or SVG with "Preserve Vector Data" scales cleanly.
- Prefer SF Symbols for UI icons; custom symbols can be exported from the SF Symbols app template.
- Names in asset catalogs are free-form, but use the same convention as other platforms (lowercase, underscores or
  hyphens consistently) to keep cross-platform manifests simple.

## Android

- Densities and scale factors:

| Qualifier | Scale | 24dp icon | 48dp image |
|-----------|-------|-----------|------------|
| mdpi | 1x | 24 px | 48 px |
| hdpi | 1.5x | 36 px | 72 px |
| xhdpi | 2x | 48 px | 96 px |
| xxhdpi | 3x | 72 px | 144 px |
| xxxhdpi | 4x | 96 px | 192 px |

- Resource names: lowercase letters, digits and underscores only; must start with a letter; no hyphens or spaces.
  File extension isn't part of the resource name, so `ic_close.xml` and `ic_close.png` collide.
- Vector drawables (`res/drawable/`) for icons and simple illustrations; raster in `drawable-<density>/`.
- Night variants in `drawable-night/` (and `-night-<density>`); RTL with `android:autoMirrored="true"` for directional
  vectors or `drawable-ldrtl/`.
- WebP preferred over PNG for raster (lossless or lossy).

## Web

- SVG for icons, logos, illustrations.
- Responsive images: `srcset` with width descriptors and `sizes` matching the layout:
  ```html
  <img src="hero-800.jpg" srcset="hero-400.avif 400w, hero-800.avif 800w, hero-1600.avif 1600w"
       sizes="(min-width: 64em) 50vw, 100vw" width="1600" height="900" alt="..." loading="lazy">
  ```
  Use `<picture>` for format fallbacks (AVIF -> WebP -> JPEG) and art direction.
- Widths: generate about 3-6 widths covering the displayed sizes x 1-2 DPR (e.g. 400, 800, 1200, 1600, 2400).
- Always set width/height (or aspect-ratio) to prevent layout shift.

## Favicons and app-like web

| File | Size | Notes |
|------|------|-------|
| favicon.ico | 32 x 32 (with 16) | Legacy browsers |
| icon.svg | Scalable | Modern browsers; can include a dark-mode media query |
| apple-touch-icon.png | 180 x 180 | iOS home screen; no transparency |
| icon-192.png, icon-512.png | 192, 512 | Web app manifest; plus a maskable version with safe zone |

## Social images

- Open Graph / link previews: 1200 x 630 PNG or JPEG; key content centred (cropped to squares in some apps).
- Keep text minimal and large; it must survive small previews.
