# Contrast: WCAG 2 and APCA

## WCAG 2.x contrast ratio

- `(L1 + 0.05) / (L2 + 0.05)` from relative luminance; 1:1 to 21:1; symmetric (swapping text and background gives the
  same ratio).
- Requirements (AA): text 4.5:1, large text 3:1 (24px regular or 18.66px bold), non-text UI and graphics 3:1 (1.4.11).
  AAA: 7:1 and 4.5:1.
- This is the legal and procurement standard today (WCAG 2.1/2.2 AA, EN 301 549, Section 508).
- Known weakness: it overstates contrast of light text on dark backgrounds and of mid-tone pairs, so some passing
  dark-mode pairs are hard to read.

## APCA (Accessible Perceptual Contrast Algorithm)

- Produces Lc (lightness contrast) from about -108 to 106. Positive = dark text on light; negative = light text on dark.
  Compare absolute values.
- Accounts for polarity and for how contrast perception changes with lightness. It's the candidate method for WCAG 3,
  which is still a draft, so APCA is not a conformance requirement yet.
- Thresholds depend on font size and weight. Simplified guide:

| Use | Minimum Lc |
|-----|-----------|
| Body text (about 16px regular), columns of text | 75 (90 preferred) |
| Content text that isn't body (short labels, about 16px+ medium) | 60 |
| Large text (24px+ regular, 16px+ bold), headlines | 45 |
| Non-text: large icons, input borders, focus indicators | 30-45 |
| Placeholder, disabled (not essential) | 30 |
| Invisible threshold | below 15 |

Smaller or thinner text needs higher Lc; the APCA lookup tables give exact values per size and weight.

## Using both

| Situation | Approach |
|-----------|----------|
| Compliance (legal, procurement) | WCAG 2.x AA must pass |
| Design quality, especially dark mode | Also aim for APCA thresholds; they catch pairs that pass WCAG but read poorly |
| Disagreement (passes WCAG, fails APCA) | Typical in dark mode with mid-grey text: raise text lightness until both pass |
| Disagreement (fails WCAG, passes APCA) | Typical for white text on mid-saturated orange/blue: WCAG governs compliance, so adjust |

## Reporting

For each mode, a table: foreground token, background token, kind, WCAG ratio (truncated to 2 decimals, never rounded up),
APCA Lc, pass/fail. Fix by moving along the token ramp, then re-check every pair that uses the changed token.

## Things contrast maths doesn't catch

- Text over images and gradients: check the worst area, or add a scrim.
- Thin weights and small sizes render lighter than their colour value (anti-aliasing).
- Translucent layers: composite first, then measure (the script does this for `#rrggbbaa` and `rgba()`).
- Colour vision deficiency: contrast can pass while two status colours look identical; add icons or labels.
