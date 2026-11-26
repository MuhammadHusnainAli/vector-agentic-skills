---
name: android-adaptive-icon-designer
description: "Design and deliver Android app icons that survive every launcher: adaptive icon structure (108dp foreground and background layers, 72dp visible area, 66dp safe zone for key content, 18dp edge reserved for motion effects), OEM mask shapes (circle, squircle, rounded square, teardrop), monochrome layer for Android 13+ themed icons, legacy mipmap sizes per density, the Google Play 512x512 store icon, splash screen icon sizes (Android 12 SplashScreen API), notification small icons, and delivery as vector drawables or PNGs with the adaptive-icon XML. Covers concept and silhouette, background choices, contrast in themed and dark contexts, parallax-safe composition, and testing across masks and launchers. Reviews icons for content outside the safe zone, detail lost at 48dp, baked-in shapes, missing monochrome layers and wrong export sizes. Use when designing, reviewing or exporting an Android launcher icon, themed icon, Play Store icon or splash icon."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Android Adaptive Icon Designer

On Android the launcher decides the icon's shape. The same artwork is masked into a circle on one phone and a squircle on
another, moved for parallax, and recoloured by the user's theme on Android 13+. Icons designed as one finished
square-with-rounded-corners look wrong everywhere. This skill designs icons as layers with a safe zone, a monochrome
version and correct exports, and reviews icons before they ship.

## Trigger Conditions

Activate this skill when the user:
- Designs or refreshes an Android launcher icon
- Gets an icon that looks cropped, tiny or boxed-in on some phones
- Needs a themed (monochrome) icon, a Play Store icon, a splash screen icon or notification icon
- Exports icon assets for Android developers

iOS app icons: `ios-human-interface-guidelines-checker`. Pixel-aligned small icons: `icon-pixel-grid-aligner`. Asset
naming: `asset-export-naming-planner`.

## Workflow

```
1. CONCEPT   -> one recognisable symbol; test silhouette at 48dp and 24dp (references/icon-design-guidance.md)
2. GRID      -> 108x108dp artboard; mark 72dp visible area and 66dp safe-zone circle (references/adaptive-icon-specs.md)
3. LAYERS    -> background (full 108dp, no transparency) + foreground (symbol inside the safe zone)
4. MASKS     -> preview under circle, squircle, rounded square and teardrop; check parallax movement
5. MONOCHROME-> single-colour silhouette layer for themed icons
6. VARIANTS  -> Play Store 512px, splash icon, notification icon
7. EXPORT    -> vector drawables (preferred) or PNG per density + adaptive-icon XML (references/export-and-delivery.md)
8. REVIEW    -> run the checklist; test on devices or emulators with different launchers and themes
```

## Review Checklist

Report as `CODE [severity] problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| AI001 | high | Key content outside the 66dp safe-zone circle (gets cropped by circular masks) |
| AI002 | high | Shape, shadow or rounded corners baked into the artwork (double masking, box-in-a-circle look) |
| AI003 | high | Background layer with transparency (undefined colour behind it on some launchers) |
| AI004 | high | Play Store icon not 512x512 PNG, or with transparency or baked-in rounded corners |
| AI005 | medium | No monochrome layer (themed icons fall back to the full-colour icon on Android 13+) |
| AI006 | medium | Text, wordmarks or fine detail that are illegible at 48dp |
| AI007 | medium | Foreground too small (looks lost) or symbol optically off-centre |
| AI008 | medium | Low contrast between foreground and background, or the icon vanishes on dark wallpapers |
| AI009 | medium | Notification icon in colour or with opaque background (must be white silhouette on transparent) |
| AI010 | low | Legacy icon densities missing for apps supporting Android 7.1 or earlier |
| AI011 | low | Splash icon not fitting the splash safe circle |

## Output

1. Icon spec: layers, colours, safe-zone overlay, mask previews
2. Monochrome layer design notes
3. Export list with file names and sizes per density, plus the XML
4. Review findings, if reviewing

## Additional Resources

| File | Content |
|------|---------|
| [adaptive-icon-specs.md](references/adaptive-icon-specs.md) | Dimensions, safe zones, densities, Play Store, splash and notification icon specs |
| [icon-design-guidance.md](references/icon-design-guidance.md) | Concept, silhouette, layers, backgrounds, colour, monochrome design, common mistakes |
| [export-and-delivery.md](references/export-and-delivery.md) | Vector drawables, PNG exports, adaptive-icon XML, file layout, testing |
