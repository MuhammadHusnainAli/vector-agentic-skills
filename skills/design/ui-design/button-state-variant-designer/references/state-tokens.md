# State Tokens

Two ways to define states. Pick one per system and don't mix them.

## Option A: explicit token per state

Every variant x state x part has a semantic token. More tokens, full control, easy to check contrast.

```
button.{variant}.{part}.{state}
  variant: primary | secondary | tertiary | danger
  part:    container | label | border | icon
  state:   default | hover | pressed | disabled | (selected)
focus.ring.color, focus.ring.width, focus.ring.offset      (shared by all components)
```

Worked matrix (light theme, Tailwind-like palette; contrast = label vs container):

| Variant | State | Container | Label | Contrast |
|---------|-------|-----------|-------|----------|
| primary | default | blue-600 #2563EB | white | 5.17:1 |
| primary | hover | blue-700 #1D4ED8 | white | 6.70:1 |
| primary | pressed | blue-800 #1E40AF | white | 8.72:1 |
| primary | disabled | slate-100 #F1F5F9 | slate-500 #64748B | 4.34:1 (exempt, but readable) |
| secondary | default | white, border #2563EB | blue-600 #2563EB | 5.17:1 |
| secondary | hover | blue-50 #EFF6FF | blue-600 #2563EB | 4.75:1 |
| secondary | pressed | blue-100 #DBEAFE | blue-700 #1D4ED8 | 5.49:1 |
| danger | default | red-600 #DC2626 | white | 4.83:1 |
| danger | hover | red-700 #B91C1C | white | 6.47:1 |
| danger | pressed | red-800 #991B1B | white | 8.31:1 |

Note: blue-500 #3B82F6 with white is only 3.68:1. A common bug is choosing the primary from the "brand blue" swatch
without checking the label.

## Option B: base colours + state layers (Material 3)

Each variant defines container and content colours; interaction states add a translucent layer of the content colour on
top of the container.

| State | State-layer opacity (M3) |
|-------|--------------------------|
| Hover | 8% |
| Focus | 10% |
| Pressed | 10% (plus ripple) |
| Dragged | 16% |
| Disabled | Container: on-surface at 12%. Content: on-surface at 38% |

Pros: few tokens, consistent across every component, works in dark mode automatically.
Cons: contrast must be checked on the composited colour, not the base colour.

Compositing: `result = layer x opacity + container x (1 - opacity)` per RGB channel (in sRGB, as browsers do for
`rgba` over an opaque colour).

## CSS

```css
.btn {
  --btn-bg: var(--button-primary-container-default);
  --btn-fg: var(--button-primary-label-default);
  background: var(--btn-bg); color: var(--btn-fg);
  min-block-size: 2.5rem; padding-inline: 1rem;
  border: 1px solid transparent;          /* reserve border width so variants share a box */
}
.btn:hover   { --btn-bg: var(--button-primary-container-hover); }
.btn:active  { --btn-bg: var(--button-primary-container-pressed); }
.btn:focus-visible {
  outline: var(--focus-ring-width, 2px) solid var(--focus-ring-color);
  outline-offset: var(--focus-ring-offset, 2px);
}
.btn[aria-disabled="true"] { --btn-bg: var(--button-primary-container-disabled); --btn-fg: var(--button-primary-label-disabled); cursor: not-allowed; }
@media (forced-colors: active) { .btn { border-color: ButtonText; } .btn:focus-visible { outline-color: Highlight; } }
```

Hover must not change size, border width or font weight: it shifts layout and makes the button jump.

## Dark mode

Don't invert. Lighten the container (e.g. blue-400 #60A5FA) and darken the label (#0F172A, 7.02:1), or keep a mid-tone
container with white text if it reaches 4.5:1. Re-check every cell; hover in dark mode usually goes lighter, not darker.
