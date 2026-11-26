# Craft Checklist

What separates a senior designer's finish from a competent first draft. Run it after the slop scan is clean.

## Typography
- [ ] Two families at most (or one with clear weight contrast); every style comes from the scale
- [ ] Display sizes have tighter leading and slight negative tracking; body 1.5-1.6 leading
- [ ] Measure 60-75 characters for reading text
- [ ] No widows in headlines on key breakpoints (`text-wrap: balance` for headings, `pretty` for paragraphs)
- [ ] Numbers in tables use tabular figures; real quotes and apostrophes (“ ” ’), en dashes for ranges
- [ ] Hierarchy readable in greyscale: size and weight carry it, not colour

## Spacing and alignment
- [ ] All spacing from the scale; related items closer than unrelated ones
- [ ] Shared left edges; text aligned to the grid, not to boxes
- [ ] Optical alignment: icons and play symbols nudged, quotes hung, cap heights aligned in buttons
- [ ] Consistent component padding across the product

## Colour and surfaces
- [ ] Tinted neutrals; one accent used for actions and emphasis only
- [ ] Text pairs pass WCAG AA (and ideally APCA); focus ring 3:1
- [ ] Surfaces separated by tone or rules; shadows only where things float
- [ ] Dark mode designed (if offered), not inverted

## Imagery and icons
- [ ] Real product screenshots or photography; no stock "team pointing at laptop"
- [ ] One icon set, one stroke weight, icons only where they help recognition
- [ ] Images have fixed aspect ratios and meaningful alt text

## Copy
- [ ] Headline says who it's for and the outcome; no hype words
- [ ] Buttons name the action ("Book a demo", not "Get started" everywhere)
- [ ] Proof is specific, named and true
- [ ] Microcopy for errors, empty states and confirmations written, not defaulted

## Interaction and states
- [ ] Hover, focus-visible, active, disabled, loading for every control
- [ ] Empty, loading, error states designed
- [ ] Motion purposeful, 150-250 ms, respects reduced motion
- [ ] No layout shift on hover or load

## Responsive and accessibility
- [ ] Designed at 375 / 768 / 1440 px, checked at range edges
- [ ] 200% zoom and 320 px reflow work
- [ ] Headings in order, landmarks, labelled controls, keyboard path through the page
- [ ] Targets at least 24 x 24 CSS px (44 for touch-first)

## Consistency
- [ ] Components reused, not restyled per section
- [ ] Same thing, same look, same name everywhere
