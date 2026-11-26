# Contrast for Button States

## Which requirement applies to which part

| Part | WCAG criterion | Minimum |
|------|----------------|---------|
| Label text vs container | 1.4.3 Contrast (Minimum), AA | 4.5:1; 3:1 if text is at least 24px regular or 18.66px (14pt) bold |
| Container vs page background | 1.4.11 Non-text Contrast, AA | 3:1, only when the container edge is needed to identify the button (e.g. an icon button with no label) |
| Outline button border vs background | 1.4.11 | 3:1 when the border is the only visual that shows it's a button |
| State change (hover/pressed/selected) | 1.4.11 when the state is conveyed visually and is needed | Selected/toggled state: 3:1 between states, or a non-colour cue (icon, border, weight) |
| Focus indicator | 2.4.7 Focus Visible (AA), 2.4.11 Focus Not Obscured (AA), 2.4.13 Focus Appearance (AAA) | Visible; not hidden by sticky headers; AAA: at least a 2 CSS px perimeter with 3:1 change |
| Disabled | Exempt (inactive components) | Aim for about 3:1 so people can still read it |

Hover-only colour changes don't have to meet a contrast ratio between hover and default, but each state's label still must
meet 4.5:1.

## The formulas

Relative luminance of an sRGB colour (channels 0-255):
```
c = channel / 255
c_lin = c / 12.92                      if c <= 0.04045
      = ((c + 0.055) / 1.055) ^ 2.4    otherwise
L = 0.2126 R_lin + 0.7152 G_lin + 0.0722 B_lin
```
Contrast ratio = (L_lighter + 0.05) / (L_darker + 0.05), from 1:1 to 21:1. Do not round up: 4.47:1 fails 4.5:1.

For translucent layers, composite first, then measure.

## Worked values

| Foreground | Background | Ratio | Passes |
|------------|------------|-------|--------|
| #FFFFFF | #2563EB | 5.17 | Text AA |
| #FFFFFF | #3B82F6 | 3.68 | Large text / non-text only |
| #FFFFFF | #DC2626 | 4.83 | Text AA |
| #2563EB | #EFF6FF | 4.75 | Text AA |
| #64748B | #FFFFFF | 4.76 | Text AA (lightest slate grey that passes on white) |
| #94A3B8 | #FFFFFF | 2.56 | Fails text and non-text |
| #CBD5E1 border | #FFFFFF | 1.48 | Fails 3:1: an outline button with this border has no visible boundary |
| #2563EB ring | #0F172A | 3.45 | Focus ring passes 3:1 on a dark surface |
| #0F172A | #60A5FA | 7.02 | Dark-mode primary label |

## Focus rings that work everywhere

A single-colour ring fails on some background. Options:
1. **Two-tone ring:** `outline: 2px solid <dark>; box-shadow: 0 0 0 4px <light>;` One of the two passes on any surface.
2. **Offset ring:** `outline-offset: 2px` so the ring sits on the page background, not on the button fill. Then it needs
   3:1 against the page only.
3. **Per-surface token:** `focus.ring.color` redefined on dark and brand surfaces.

Check the focus ring:
- against the page background (offset ring) or the button fill (inset ring)
- on every surface the button appears on (cards, banners, dark headers)
- not clipped by `overflow: hidden` parents, not covered by sticky headers (2.4.11)

## Process for a full matrix

1. List each variant x state x theme (light, dark, high contrast if supported).
2. Compute label vs container, border vs page (if boundary-only), focus ring vs adjacent colour.
3. Record ratios to two decimals; mark FAIL below the threshold.
4. Fix by moving to the next step in the colour ramp, not by tweaking hex values by hand. Keep it on the ramp.
5. Verify in the browser or in Figma with a contrast plugin; anti-aliasing at small sizes reads lighter than the maths.
