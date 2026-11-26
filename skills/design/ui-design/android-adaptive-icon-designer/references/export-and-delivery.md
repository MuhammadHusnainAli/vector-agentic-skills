# Export and Delivery

## Preferred: vector drawables

Simple flat icons export best as vector drawables (one XML per layer, no density files):
- Export the 108 x 108 artboard layers as SVG and import with Android Studio's Image Asset Studio (Launcher Icons
  (Adaptive and Legacy)) or Vector Asset Studio.
- Supported SVG subset: paths, groups, solid fills and strokes, linear/radial gradients (API 24+). Not supported: masks
  and filters, embedded raster images, text (convert to outlines), some blend modes.
- Keep path count modest; complex vectors slow launchers and inflate APKs.

Use PNG layers when the artwork has textures or effects that vectors can't express.

## File layout

```
res/
  mipmap-anydpi-v26/
    ic_launcher.xml              adaptive icon definition
    ic_launcher_round.xml        same content (for launchers that request round)
  drawable/                      (vector layers)
    ic_launcher_foreground.xml
    ic_launcher_background.xml
    ic_launcher_monochrome.xml
  mipmap-mdpi/ ... mipmap-xxxhdpi/   (PNG layers or legacy icons if needed)
    ic_launcher.png  ic_launcher_round.png  ic_launcher_foreground.png ...
  drawable-mdpi/ ... drawable-xxxhdpi/
    ic_stat_notify.png           notification icon (white on transparent)
```

## Adaptive icon XML

```xml
<!-- res/mipmap-anydpi-v26/ic_launcher.xml -->
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@drawable/ic_launcher_background" />
    <foreground android:drawable="@drawable/ic_launcher_foreground" />
    <monochrome android:drawable="@drawable/ic_launcher_monochrome" />
</adaptive-icon>
```
Manifest: `android:icon="@mipmap/ic_launcher"` and `android:roundIcon="@mipmap/ic_launcher_round"`.

## Naming

Android resource names: lowercase letters, digits and underscores only, starting with a letter. Conventional prefixes:
`ic_launcher_*`, `ic_stat_*` (notifications), `ic_*` (in-app icons).

## Delivery checklist for developers

- [ ] Foreground, background and monochrome layers (vector XML or PNG per density)
- [ ] `ic_launcher.xml` and `ic_launcher_round.xml`
- [ ] Legacy PNGs only if minSdk < 26
- [ ] Play Store icon 512 x 512 PNG, opaque, no rounded corners
- [ ] Splash icon (and branding image if used) with the splash background colour
- [ ] Notification icon, white on transparent, all densities
- [ ] Mask preview sheet (circle, squircle, rounded square, teardrop) and themed-icon preview

## Testing

- Android Studio's Image Asset Studio preview shows several masks.
- Emulators with different launchers; a Pixel device with themed icons on (Wallpaper & style > Themed icons).
- Long-press the icon for shortcuts; check the splash screen on a cold start; post a test notification.
