---
name: asset-export-naming-planner
description: "Plan how design assets are exported, named and delivered for web, iOS and Android so engineers drop them in without renaming or re-exporting: asset inventory by type (icons, illustrations, photos, logos, app icons, favicons, social images), the right format per type and platform (SVG, PDF, vector drawable, PNG, WebP, AVIF, JPEG), scales and densities (@1x-@3x, mdpi-xxxhdpi, srcset widths), a naming convention with prefixes, descriptors, variants, sizes, states and themes that satisfies every platform's rules (Android resource names lowercase with underscores), folder structure, Figma export presets and slice setup, optimisation (SVGO, compression quality), dark-mode and RTL variants, and versioning. Reviews asset folders and lists for illegal or inconsistent names, missing densities or variants, wrong formats, oversized files, text baked into images and duplicates. Use when preparing assets for handoff, setting up an asset naming convention or auditing an asset folder."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Asset Export & Naming Planner

Assets cause friction out of proportion to their importance. Engineers rename "Group 427@2x.png", re-export icons in the
wrong format, ask for the missing xxxhdpi, and discover the dark-mode version never existed. One naming convention and one
export plan per platform, agreed before handoff, removes all of it. This skill builds that plan and audits asset folders
against it.

## Trigger Conditions

Activate this skill when the user:
- Prepares images, icons, illustrations or logos for engineering
- Sets up an asset naming convention or export presets in Figma
- Ships to several platforms (web, iOS, Android) from one design file
- Audits an asset folder with inconsistent names, missing sizes or heavy files

Icon drawing and SVG hygiene: `icon-pixel-grid-aligner`. Android launcher icons: `android-adaptive-icon-designer`.
Handoff package: `design-handoff-spec-generator`.

## Workflow

```
1. INVENTORY -> every asset in the feature: type, where used, sizes displayed, themes, locales
2. FORMAT    -> per type and platform (references/platform-asset-specs.md)
3. NAME      -> apply the convention (references/naming-convention.md); check platform rules
4. VARIANTS  -> densities, widths, dark mode, RTL, locale-specific images
5. PRESETS   -> Figma export settings per asset type; layer names = file names (references/export-pipeline.md)
6. OPTIMISE  -> SVGO for SVG; quality settings for raster; size budgets
7. DELIVER   -> folder structure per platform, manifest table, where each asset is used
8. REVIEW    -> checklist below
```

## Format Decision

| Asset | Web | iOS | Android |
|-------|-----|-----|---------|
| UI icons | SVG (inline/sprite/component) | SF Symbols, or SVG/PDF vector in asset catalog | Vector drawable (from SVG) |
| Illustrations (flat) | SVG | SVG/PDF in asset catalog, preserve vector data | Vector drawable, or WebP if complex |
| Photos | AVIF/WebP with JPEG fallback, several widths | JPEG/HEIC @2x, @3x in asset catalog | WebP per density |
| Logos | SVG | PDF/SVG vector | Vector drawable |
| Complex artwork with gradients, blur | WebP/AVIF/PNG | PNG @2x @3x | WebP per density |
| Animations | Lottie JSON / video (MP4, WebM) | Lottie / video | Lottie / AnimatedVectorDrawable |

## Review Checklist

Report as `CODE [severity] asset: problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| AE001 | high | Names illegal on a platform (Android: uppercase, hyphens, spaces, leading digits) |
| AE002 | high | Missing densities or scales for raster assets (@3x, xxhdpi/xxxhdpi), or missing srcset widths |
| AE003 | high | Text baked into images (not translatable, not accessible) |
| AE004 | medium | Raster used where vector works (icons and logos as PNG) |
| AE005 | medium | Inconsistent naming (mixed casing, missing prefixes, sizes in some names only) |
| AE006 | medium | Missing dark-mode or RTL variants where the asset needs them |
| AE007 | medium | Oversized files (photos over about 200-300 KB for in-app use, SVGs with embedded rasters) |
| AE008 | low | Duplicates under different names |
| AE009 | low | Editor junk in names ("Group 427", "Frame 12 copy", "final_v2_FINAL") |

## Output

1. Asset manifest: name, type, format per platform, sizes/densities, variants, where used
2. Naming convention summary
3. Figma export presets and layer naming instructions
4. Folder structure per platform
5. Review findings, if auditing

## Additional Resources

| File | Content |
|------|---------|
| [platform-asset-specs.md](references/platform-asset-specs.md) | iOS scales and asset catalogs, Android densities and resource rules, web responsive images, favicons, social images |
| [naming-convention.md](references/naming-convention.md) | Name structure, prefixes, descriptors, variants, platform-safe rules, examples |
| [export-pipeline.md](references/export-pipeline.md) | Figma export setup, optimisation settings, folder structures, manifests, versioning |
