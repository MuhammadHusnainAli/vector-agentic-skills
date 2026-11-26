# Export Pipeline

## Figma setup

- Name the exportable layer or frame with the final asset name; Figma uses the layer name as the file name.
- Use slash naming only if you want folders on export (`icons/ic_close_24` exports into an `icons` folder).
- Export presets per type:

| Type | Preset |
|------|--------|
| Icon | SVG; "Include id attribute" off; outline text; flatten |
| Illustration | SVG (check for embedded images), plus PNG 2x for previews |
| iOS raster | PNG 2x and 3x (suffixes @2x, @3x) |
| Android raster | PNG at 1x, 1.5x, 2x, 3x, 4x into density folders (or export 4x and downscale in the pipeline) |
| Web photo | Export the largest needed size (e.g. 2400 wide) as PNG/JPEG; the build pipeline generates AVIF/WebP widths |

- Frames sized to the asset's real bounds; no stray empty space unless intended padding.
- Hide annotation layers before exporting.

## Optimisation

| Format | Tool / setting |
|--------|----------------|
| SVG | SVGO (keep viewBox, round to 1-2 decimals, remove metadata), `currentColor` for icons |
| JPEG | Quality about 75-82 (mozjpeg) for photos |
| WebP | Quality about 75-80 lossy for photos; lossless for flat graphics |
| AVIF | Quality about 50-65 (visually similar to JPEG ~80 at a fraction of the size) |
| PNG | Only for flat artwork that needs transparency; run through a quantiser (pngquant) |

Size budgets help: in-app photos under about 200 KB at the largest delivered width; icons under 2 KB each as SVG.

## Folder structure

```
assets/
  web/
    icons/        ic_*.svg
    illus/        illus_*.svg
    images/       img_*.(jpg|png)   source, pipeline makes AVIF/WebP widths
  ios/
    Assets.xcassets/...             image sets with @2x/@3x, dark appearance, directions
  android/
    drawable/                       vector drawables (ic_*.xml)
    drawable-night/                 dark variants
    drawable-mdpi/ ... drawable-xxxhdpi/   raster images
  manifest.csv
```

## Manifest

| name | type | web | ios | android | sizes | variants | used in |
|------|------|-----|-----|---------|-------|----------|---------|
| ic_cart_24 | icon | svg | symbol: cart | vector | 24 | outline, filled | header, product |
| illus_empty_inbox | illustration | svg | pdf | vector | 160, 96 | dark | inbox empty state |
| img_hero_home | photo | avif/webp/jpg 400-2400 | jpg @2x @3x | webp 5 densities | - | wide, square | home |

## Versioning

- Assets live in version control (repo or a design-asset package), not chat attachments.
- Changes to an existing asset keep the name; release notes mention visual changes.
- Removed assets go through the same deprecation as code (search usages first).
