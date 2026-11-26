# Design QA Checklist (beyond the diff)

## Visual (with DevTools)

- [ ] Spacing: gaps and padding match tokens (inspect the box model; compare with `--space-*`)
- [ ] Colours: computed colours match token values (Styles panel shows `var(--...)`; raw hex means a bypassed token)
- [ ] Typography: font family, size, weight, line height, letter spacing per text style
- [ ] Radii, borders, shadows match tokens
- [ ] Icons: correct icon, size and colour; aligned with text
- [ ] Images: aspect ratio, cropping, no stretching or blur

## States

- [ ] Hover, pressed, focus-visible, disabled, selected, loading, error per interactive component
- [ ] Empty, loading, error, partial, no-permission states of each screen
- [ ] Success and confirmation states

## Responsive

- [ ] Each breakpoint and the edges of each range (e.g. 599 and 600)
- [ ] 320 CSS px reflow without horizontal scroll (except tables, maps)
- [ ] Landscape phone, tablet, very wide screens (max width honoured)
- [ ] Browser zoom 200%

## Content

- [ ] Longest real strings, translations, numbers with many digits
- [ ] Truncation and wrapping rules as specified; full text reachable
- [ ] Date, number and currency formats per locale

## Behaviour and motion

- [ ] Interactions as specified (what opens, closes, navigates)
- [ ] Transition durations and easing feel right; reduced-motion mode respected
- [ ] Focus moves correctly on open, close, delete, submit, route change
- [ ] Keyboard: every control reachable and operable; Escape closes overlays

## Accessibility

- [ ] Names for icon buttons and images; headings and landmarks as annotated
- [ ] Contrast of text and UI in light and dark
- [ ] Screen reader spot check of the main flow (VoiceOver/NVDA/TalkBack)
- [ ] Target sizes at least 24 x 24 CSS px (44pt / 48dp on touch)

## Themes and platforms

- [ ] Dark mode, high contrast / forced colors
- [ ] Browsers in scope (Chrome, Safari, Firefox, Edge); iOS Safari quirks (safe areas, 100vh)
