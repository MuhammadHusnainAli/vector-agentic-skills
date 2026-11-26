# Layout, Safe Areas and Scaling

## Placement zones

```
+-----------------------------------------------+
| ambient (score, minimap)       ambient (feed) |
|                                               |
|            centre: action + reticle           |
|            keep clear                         |
|                                               |
| critical (health)      situational (ammo)     |
+-----------------------------------------------+
```
Peripheral vision catches change and colour but not detail: use motion and colour change at the edges to draw attention,
then readable numbers for when the player looks.

## Safe areas

- TVs may crop edges (overscan). Keep HUD inside a safe area: commonly 90% (5% inset each side) as a baseline, with a
  player-adjustable safe-area setting on consoles (calibration screen with corner markers).
- Platform requirements (Xbox, PlayStation, Nintendo) include safe-area handling; check the current certification
  requirements for each platform.
- PC: no overscan, but keep margins so elements aren't flush with bezels.

## Aspect ratios

| Ratio | Approach |
|-------|----------|
| 16:9 (baseline) | Design here |
| 21:9 / 32:9 ultrawide | Anchor HUD to a centred 16:9 (or adjustable width) area by default; option to stretch to the edges. Far edges are outside comfortable vision on ultrawide |
| 16:10 (Steam Deck, many laptops) | Extra vertical space; anchor top and bottom elements to edges |
| 4:3 / portrait (mobile) | Rearrange; thumb zones on mobile; avoid placing UI under thumbs |

Anchor each element to a corner or edge with offsets in percentages of the safe area, not absolute pixels.

## Resolution scaling

- Author UI at a reference resolution (e.g. 1920x1080) and scale by height (or min of width/height) so UI keeps its
  proportion; provide crisp assets for 4K (vector or high-resolution textures).
- HUD scale option (e.g. 75-150%) independent of resolution.

## Text size per platform

| Platform | Guidance |
|----------|----------|
| TV / console at about 2.5-3 m | Compute from visual angle (see tv-10-foot-ui-designer): body text in the high 20s to 30s of px at 1080p for a 55" screen; Xbox Accessibility Guidelines also call for a sufficient minimum size and scalable text |
| PC monitor at about 60 cm | Smaller is fine; around 16-18 px body at 1080p, with scaling |
| Steam Deck (7", 1280 x 800, handheld) | Valve's Deck Verified guidance asks for the smallest text to stay legible at 1280 x 800 (about 9 px minimum character height); larger is better |
| Nintendo Switch handheld | Test in handheld mode at 720p; text that works docked can be too small |
| Mobile | 14-16 pt minimum for body; account for thumbs covering parts of the screen |

## Legibility over the game

- Outline or drop shadow on HUD text; or semi-transparent backing plates.
- Avoid thin fonts and long text; numbers in tabular figures.
- Test over the brightest and busiest scenes (snow, explosions, sky).
