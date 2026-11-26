# TV Sizing

## From visual angle to pixels

Readable character size depends on the angle it subtends at the eye. Ergonomics standards (ISO 9241-303) recommend a
capital-letter height of about 20-22 arcminutes, with 16 arcminutes as a minimum for reading.

```
screen_height_m = diagonal_in x 9 / sqrt(16^2 + 9^2) x 0.0254      (16:9 screens)
pixel_pitch_m   = screen_height_m / vertical_resolution
cap_height_m    = 2 x distance_m x tan(arcmin / 60 / 2 degrees)
cap_height_px   = cap_height_m / pixel_pitch_m
font_size_px    = cap_height_px / cap_ratio        (cap ratio about 0.7 for most UI fonts; check yours)
```

Compute in 1080p design pixels even for 4K TVs: platforms scale 1080p layouts up, so the physical size stays the same.

## Worked table (1080p, cap ratio 0.7)

| Screen | Distance | Pixel pitch | Font px for 16 arcmin (minimum) | Font px for 20 arcmin (comfortable) |
|--------|----------|-------------|-------------------------------|-------------------------------------|
| 43" | 2.5 m | 0.496 mm | 34 | 42 |
| 43" | 3.0 m | 0.496 mm | 40 | 50 |
| 55" | 2.5 m | 0.634 mm | 26 | 33 |
| 55" | 3.0 m | 0.634 mm | 31 | 39 |
| 65" | 2.5 m | 0.749 mm | 22 | 28 |
| 65" | 3.0 m | 0.749 mm | 27 | 33 |
| 75" | 2.5 m | 0.865 mm | 19 | 24 |
| 75" | 3.0 m | 0.865 mm | 23 | 29 |

Smaller TVs at the same distance need bigger pixel sizes. Design for the small end of your audience's screens (often
43-50"). Platform defaults (tvOS body text about 29pt at 1920x1080) sit near the 55"/3m minimum: don't go smaller.

## Targets and spacing

- Focusable items are selected by focus, not by touch, so there's no touch target size. But items must be big enough to
  read and to show a clear focus state. Posters and cards are typically 200-400px wide at 1080p.
- Leave room around items for the focus scale-up (often 1.05-1.15x) without overlapping neighbours.
- Thin lines (1-2px) and small text flicker or blur on TVs; use at least 2px strokes and solid shapes.

## Safe areas

| Platform | Safe area (1080p / design units) |
|----------|----------------------------------|
| tvOS | Insets of 60pt top and bottom, 80pt left and right on 1920 x 1080 |
| Android TV / Google TV | Overscan margin of 5%: 48dp left/right, 27dp top/bottom on the 960 x 540dp canvas |
| Broadcast convention | Action-safe 5% inset (93% area); title-safe 10% inset (90% area) |
| Fire TV, Roku, smart TV platforms | Follow the platform guide; assume at least a 5% margin when unsure |

Backgrounds and artwork can bleed to the edges; text, focusable items and logos stay inside.

## Colour on TVs

- TVs vary widely in calibration and are often in vivid modes: avoid relying on subtle colour differences.
- Avoid large pure white areas (glare, blooming); use dark themes or off-white.
- Highly saturated reds and oranges bleed on some panels; test.
- Contrast: aim for at least 4.5:1 for text even though screens are bright: distance and glare reduce effective contrast.
