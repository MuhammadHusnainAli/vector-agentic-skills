# Reach and Hardware

## Reach ranges (2010 ADA Standards for Accessible Design, 308)

| Situation | Low limit | High limit |
|-----------|-----------|------------|
| Unobstructed forward reach | 15 in (380 mm) | 48 in (1220 mm) |
| Forward reach over an obstruction 20-25 in deep | - | 44 in (1120 mm) |
| Unobstructed side reach | 15 in (380 mm) | 48 in (1220 mm) |
| Side reach over an obstruction up to 24 in deep, 34 in high max | - | 46 in (1170 mm) |

Also: clear floor space of 30 x 48 in (760 x 1220 mm) in front of the kiosk, and operable parts usable with one hand,
without tight grasping or twisting, with no more than 5 lbf (22.2 N) of force.

ADA 707 (ATMs and fare machines) adds: display screens visible from a point 40 in (1015 mm) above the centre of the clear
floor space, speech output, tactilely discernible input controls, privacy for speech output.

## Mapping reach onto the screen (worked example)

32" portrait screen (16:9), bottom edge mounted at 30 in above the floor:
```
screen height = 32 x 16 / sqrt(16^2 + 9^2) = 27.9 in        screen width = 15.7 in
top edge      = 30 + 27.9 = 57.9 in
above 48 in   = 9.9 in = top 35% of the screen is out of reach for wheelchair users
```
So: put only non-interactive content (branding, headings, imagery) in the top 35%, all controls below. Or lower the
screen; then check the bottom edge stays at 15 in or above.

## Tilt, glare and viewing

- Tilt screens back from vertical (often about 15-30 degrees) for standing users: easier reach and viewing; check
  visibility from 40 in eye height for seated users.
- Avoid glare: positioning relative to windows and lights; anti-glare glass; outdoor kiosks need high brightness
  (often 1000+ nits) and high-contrast designs.
- Privacy: viewing angle or privacy filters for payment and personal data screens.

## Target size maths

```
ppi           = sqrt(width_px^2 + height_px^2) / diagonal_in
target_px     = target_mm / 25.4 x ppi
```
32" 1080 x 1920 screen: about 69 ppi, so a 20 mm target is about 54 px. Large public screens have low ppi; check the
design at actual size.

| Target | Size |
|--------|------|
| Primary choices | 25-40 mm tall; full-width rows or large tiles |
| Minimum | About 20 mm (never under about 15 mm) |
| Spacing | At least 3-5 mm between targets |

## Hardware placement

- Card reader, contactless pad, scanner, printer, keypad and headphone jack within the reach range and near the related
  screen area.
- The screen shows where to tap, insert or scan with an animation pointing to the hardware's real position.
- Tactile keypad with a raised dot on 5 and distinct Enter/Cancel keys (consistent across devices).
