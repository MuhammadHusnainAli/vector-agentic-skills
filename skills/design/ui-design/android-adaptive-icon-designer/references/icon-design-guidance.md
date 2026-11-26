# Icon Design Guidance

## Concept

- One symbol, one idea. The launcher shows it at about 48dp, often next to dozens of others.
- Silhouette test: fill the symbol black on white at 24dp. If it's unrecognisable, simplify.
- Avoid text and wordmarks. A single letterform can work if it's distinctive and bold.
- Don't use photos or screenshots of the UI.

## Composition

- Centre optically, not mathematically: triangles and play icons usually need a nudge.
- Size: the symbol should fill most of the safe zone. Too small looks lost in circular masks; too big gets cropped by
  teardrop and squircle masks.
- Keep the 18dp outer band empty or background-only, because parallax moves the foreground.
- Depth via layers: the foreground can have subtle shading, but avoid drop shadows that fall into the masked edge.

## Background layer

| Option | Works when |
|--------|-----------|
| Solid brand colour | Most icons; strongest recognition |
| Subtle gradient | Adds depth; keep it simple so masks don't reveal awkward edges |
| White | The symbol is colourful; check on light wallpapers and in launcher folders |
| Pattern | Only if very subtle; patterns compete with the symbol at small size |

## Colour and contrast

- Foreground and background need enough contrast to read at small size (aim for at least 3:1 between the symbol and its
  background).
- Check on light and dark wallpapers, in app drawers, folders, and in dark theme.
- Avoid pure black backgrounds: they disappear in dark launchers.

## Monochrome (themed icon) layer

- Android 13+ themed icons take the monochrome layer's alpha and tint it with the user's wallpaper colours.
- Draw a single-colour version of the symbol, not the full icon: no background, no colour, no gradients.
- Same safe zone and size as the foreground. Fine internal detail that relied on colour must be expressed with cut-outs
  (negative space).
- Without it, themed-icon launchers show the full-colour icon among tinted ones, and it looks out of place.

## Common mistakes

| Mistake | Result | Fix |
|---------|--------|-----|
| Exporting the iOS icon (rounded square) as the foreground | A rounded square inside a circle | Separate symbol and background layers |
| Symbol to the edge of the 72dp area | Cropped by circle and teardrop masks | Fit inside the 66dp circle |
| Shadow baked under the symbol to the edge | Shadow cut off by the mask | Keep shadows inside the safe zone or remove them |
| Transparent background layer | Black or random backgrounds on some launchers | Opaque background |
| Thin strokes | Disappear at 48dp | Bold shapes; preview at 48dp actual size; strokes under about 2dp on the 108dp artboard tend to vanish |
| Brand wordmark | Illegible | Symbol or single letter |
