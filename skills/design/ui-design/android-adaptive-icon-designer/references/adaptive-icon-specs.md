# Adaptive Icon Specs

## Geometry (dp)

```
108 x 108   full layer (foreground and background are both this size)
 72 x 72    visible area after masking (centred; 18dp on each side is outside the mask)
 66         diameter of the safe-zone circle: key content must stay inside
 18         outer band reserved for launcher effects (parallax, pulsing); may be cropped or shown
```

| Element | Size | Notes |
|---------|------|-------|
| Background layer | 108 x 108dp | Fully opaque; colour, gradient or subtle pattern |
| Foreground layer | 108 x 108dp | Transparent around the symbol |
| Symbol bounding box | Fits the 66dp circle | A square symbol fits in about 46 x 46dp (66 / sqrt 2); a wide one may be about 66 x 40dp |
| Monochrome layer | 108 x 108dp | Alpha-only silhouette; same safe zone; Android 13+ themed icons |

Launchers apply a mask (circle, squircle, rounded square, teardrop, or user-chosen) to the 72dp area and may move the
foreground up to about 18dp for parallax. Design so the symbol looks right in all masks.

## Layer pixel sizes per density

| Density | Scale | Adaptive layer (108dp) | Legacy launcher icon (48dp) |
|---------|-------|------------------------|-----------------------------|
| mdpi | 1x | 108 px | 48 px |
| hdpi | 1.5x | 162 px | 72 px |
| xhdpi | 2x | 216 px | 96 px |
| xxhdpi | 3x | 324 px | 144 px |
| xxxhdpi | 4x | 432 px | 192 px |

Adaptive icons need API 26+. Legacy (`ic_launcher.png`, `ic_launcher_round.png`) PNGs are only needed if minSdk < 26.

## Google Play store icon

- 512 x 512 px, 32-bit PNG (sRGB), up to 1024 KB.
- Full square, no transparency. Google Play applies rounded corners (radius 20% of the icon size) and shadows itself:
  don't bake them in.
- Same artwork as the launcher icon; can use the full square, but keep it consistent with the adaptive icon.

## Splash screen icon (Android 12+ SplashScreen API)

| Variant | Artboard | Content must fit in |
|---------|----------|---------------------|
| App icon without icon background | 288 x 288dp | 192dp diameter circle |
| App icon with icon background | 240 x 240dp | 160dp diameter circle |

Optional branding image at the bottom: 200 x 80dp. The splash background is a single colour.

## Notification small icon

- 24 x 24dp, white silhouette on transparent; the system tints it. Coloured or opaque icons render as white squares.
- Live area about 20 x 20dp; simple shapes, no gradients.
- Densities: 24 / 36 / 48 / 72 / 96 px (mdpi to xxxhdpi).

## Other surfaces

| Surface | Spec |
|---------|------|
| Android TV banner | 320 x 180dp, with app name text, in `drawable-xhdpi` (640 x 360 px) |
| Wear OS | Adaptive icon works; check legibility at small round sizes |
| Shortcuts (app shortcuts) | Adaptive icons, 108dp layers, same safe zone |
