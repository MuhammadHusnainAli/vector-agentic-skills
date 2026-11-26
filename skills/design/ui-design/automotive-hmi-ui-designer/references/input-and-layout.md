# Input and Layout

## Input channel by task

| Task type | Best channel | Why |
|-----------|--------------|-----|
| Frequent, safety-related (hazard, defrost, volume, climate temperature) | Physical controls with tactile feedback | Operable without looking; muscle memory |
| Frequent, simple (next track, accept call, cruise) | Steering wheel controls | Hands stay on the wheel |
| Complex input (destinations, contacts, messages) | Voice | No visual demand for entry; confirm briefly on screen |
| Browsing and selection while parked | Touch | Rich interaction is fine when stationary |
| Quick selection while driving | Touch with large targets, shallow menus | Short glances |

Touch has no tactile feedback: the driver must look. Haptic feedback on touch helps confirm the input, but doesn't remove
the glance needed to find the target.

## Character height

Visual angle formula (cap height h at eye distance d):
```
h = 2 x d x tan(arcmin / 60 / 2 degrees)
```
ISO 15008 guidance for in-vehicle displays recommends character heights of about 20 arcminutes, with about 16 as a
minimum (check the current edition for exact values by use case).

| Eye distance | 16 arcmin cap height | 20 arcmin cap height |
|--------------|----------------------|----------------------|
| 650 mm | 3.0 mm | 3.8 mm |
| 750 mm (typical centre display) | 3.5 mm | 4.4 mm |
| 900 mm | 4.2 mm | 5.2 mm |

Example: 10.25" 1920 x 720 display, about 200 ppi (7.88 px/mm). 20 arcmin at 750 mm = 4.36 mm = 34 px cap height, about a
49 px font (cap height about 0.7 of font size). 16 arcmin = about 39 px font. Use bold or medium weights, high contrast,
and avoid condensed fonts.

## Touch targets

- Physical size matters, not pixels: `mm = px / ppi x 25.4`.
- Android Automotive OS requires touch targets of at least 76 x 76 dp. At 200 ppi that's 95 px, about 12 mm.
- Many OEM guidelines aim for about 10-15 mm targets with spacing, larger for targets used while moving. 15 mm at 200 ppi is
  about 118 px.
- Place frequent targets near the driver and the display edge (the edge acts as a physical anchor for the hand).

## Layout zones

| Zone | Content |
|------|---------|
| Instrument cluster (behind the wheel) | Speed, warnings, turn-by-turn next manoeuvre, driver assistance status |
| Head-up display | Speed, next manoeuvre, critical alerts; minimal and high contrast |
| Centre display, driver side | Frequent controls and the active task |
| Centre display, passenger side | Less frequent, passenger-oriented content |
| Physical controls | Safety and climate basics, volume |

Keep the most important information as close to the driver's line of sight as possible; lower and further screen areas
take longer glances.

## Day and night

- Night: dark backgrounds, dimmed overall luminance, no large white areas, reduced saturation; follow the vehicle's
  headlight/ambient sensor.
- Day: high contrast for sunlight; anti-glare; check legibility under direct sun.
- Transition smoothly; never flash bright screens at night.
