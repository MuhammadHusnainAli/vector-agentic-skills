# Kiosk Accessibility

Confirm the applicable law for each deployment with counsel; requirements differ by sector and country.

## Requirements that shape kiosk design

| Source | Applies to | Key requirements |
|--------|------------|------------------|
| 2010 ADA Standards 308, 707 (US) | ATMs and fare machines (707); reach ranges for operable parts generally | Reach 15-48 in; speech output; tactile input; privacy; display visible from 40 in |
| US DOT 14 CFR Part 382 (airlines) | Airline-owned kiosks at US airports | Accessible kiosks (with speech, tactile input) phased in; accessible kiosks must offer the same functions |
| EN 301 549 (EU) | ICT with closed functionality, including self-service terminals | Speech output, operation without vision, personal headsets, tactile controls, accessible PIN entry, adjustable time |
| European Accessibility Act (Directive (EU) 2019/882) | Self-service terminals: payment terminals, ATMs, ticketing and check-in machines, interactive information terminals (applies from 28 June 2025) | Accessibility of the product and service; EN 301 549 is the harmonised route |

## Accessibility mode

| Feature | Spec |
|---------|------|
| Speech output | Through a headphone jack (privacy); everything on screen spoken; volume control; repeat |
| Tactile navigation | Keypad (arrows, Enter, Back, Help) or the EZ-Access style key layout; focus moves through items in order |
| Lowered layout | All content moves into the lower part of the screen within reach and the 40 in visibility range |
| Visual | Large text option, high contrast mode, no information by colour alone |
| Time | Extended or adjustable timeouts |
| Discovery | Inserting headphones starts audio mode with instructions; tactile sign telling where the jack is |
| PIN entry | Tactile keypad; audio doesn't speak the digits |

## Speech design

- Orientation first: "This is the ticket machine. Use the arrow keys to move, Enter to select, Help at any time."
- Speak screen title, then the focused item and its position ("Destination, 2 of 8: London").
- Confirm actions and totals; spell out reference numbers in groups.

## Testing

- Test with blind users using headphones and keypad only.
- Test with wheelchair users at the real installation (approach, reach, visibility).
- Test with older users and people with tremor (target sizes, timeouts).
- Test in the actual lighting and noise conditions.
