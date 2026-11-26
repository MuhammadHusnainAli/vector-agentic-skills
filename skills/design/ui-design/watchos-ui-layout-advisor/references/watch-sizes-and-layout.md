# Watch Sizes and Layout

## Screen sizes (points)

| Case | Models | Width x height (pt) |
|------|--------|---------------------|
| 38mm | Series 1-3 | 136 x 170 |
| 42mm (older) | Series 1-3 | 156 x 195 |
| 40mm | Series 4-6, SE | 162 x 197 |
| 44mm | Series 4-6, SE | 184 x 224 |
| 41mm | Series 7-9 | 176 x 215 |
| 45mm | Series 7-9 | 198 x 242 |
| 42mm (newer) | Series 10 and later | 187 x 223 |
| 46mm | Series 10 and later | 208 x 248 |
| 49mm | Ultra | 205 x 251 |

Check the deployment target: current watchOS versions drop the oldest hardware, so 38mm and the older 42mm usually only
matter for legacy apps. Design at a mid size (41mm or 42mm newer), verify at 46mm and 49mm, and at the smallest size you
support.

## Layout rules

- Edge to edge: content uses the full width; the black bezel frames it. Rounded corners clip corners on newer models,
  so keep important content away from them.
- One column. Full-width buttons and rows. Two side-by-side buttons at most, for a clear pair (Cancel / Confirm).
- Top of the screen is prime space: the glance goes there. The system time occupies the top-trailing corner.
- Scroll vertically with the Digital Crown; keep each screen short (about 1-2 screens of scrolling at most).
- Spacing: SwiftUI defaults and system list styles handle margins per size; avoid hard-coded widths.

## Typography

- SF Compact (system font on watchOS); use text styles so text follows Dynamic Type: Large Title, Title 1-3, Headline,
  Body, Caption 1-2, Footnote 1-2.
- Large, bold numbers for the glance value; short labels.
- Truncation and wrapping are common at large sizes: design for 2-line labels.

## Colour and backgrounds

- Black backgrounds on OLED save power and make the screen blend into the bezel.
- watchOS 10+ allows full-screen colour backgrounds (gradients tied to content state), used to convey context
  (e.g. a weather condition), not decoration everywhere.
- Accent colour for interactive elements and key data; high contrast between text and background.
- Don't rely on colour alone for status (red/green rings need icons or text too).

## Always-on display

When the wrist is down, the screen dims and updates less often (about once per minute):
- Reduce luminance: dim or remove bright backgrounds; keep the key value visible.
- Hide sensitive information (balances, messages) with redaction.
- Remove animations, seconds-level counters and progress that would look frozen; show a static state that's still true.
- Timers and workouts use system-supported date/timer text so they keep updating correctly.
