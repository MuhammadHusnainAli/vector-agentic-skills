# Motion Tokens

## Durations

| Token | Value | Use |
|-------|-------|-----|
| duration.instant | 0-50 ms | Colour/opacity changes on hover and press |
| duration.fast | 100-150 ms | Small elements: icons, toggles, checkboxes, tooltips |
| duration.moderate | 200-250 ms | Medium elements: dropdowns, popovers, list item changes |
| duration.slow | 300-400 ms | Large elements: sheets, drawers, dialogs, page-level transitions |
| duration.slower | 400-500 ms | Full-screen transitions, shared-element transitions |

Rules:
- Larger distance or area = longer duration, but rarely over 500 ms for UI.
- Exits are faster than entrances (about 70-80% of the entrance), because people already know what's leaving.
- Mobile transitions can be a bit longer than desktop, wearables shorter.
- Same kind of change = same token everywhere.

## Easing

| Token | Curve | Use |
|-------|-------|-----|
| easing.standard | `cubic-bezier(0.2, 0, 0, 1)` | Elements moving on screen from one place to another |
| easing.enter (decelerate) | `cubic-bezier(0.05, 0.7, 0.1, 1)` | Elements entering: start fast, settle gently (M3 emphasized decelerate) |
| easing.exit (accelerate) | `cubic-bezier(0.3, 0, 0.8, 0.15)` | Elements leaving the screen (M3 emphasized accelerate) |
| easing.emphasized | A spring, or `easing.standard` with a longer duration | Expressive, large moves |
| linear | `linear` | Only opacity crossfades, progress bars, spinners' rotation |

Springs (iOS SwiftUI, Compose, Framer Motion) are defined by stiffness and damping (or response and damping fraction);
they handle interruption naturally. Map tokens to springs per platform: "snappy" (fast response, critically damped) for
UI, "bouncy" (some overshoot) only for playful feedback.

## CSS

```css
:root {
  --duration-fast: 150ms; --duration-moderate: 220ms; --duration-slow: 320ms;
  --easing-standard: cubic-bezier(0.2, 0, 0, 1);
  --easing-enter: cubic-bezier(0.05, 0.7, 0.1, 1);
  --easing-exit: cubic-bezier(0.3, 0, 0.8, 0.15);
}
.menu[data-state="open"]   { animation: menu-in var(--duration-moderate) var(--easing-enter); }
.menu[data-state="closed"] { animation: menu-out var(--duration-fast) var(--easing-exit); }
@keyframes menu-in  { from { opacity: 0; transform: translateY(-4px) scale(0.98); } }
@keyframes menu-out { to   { opacity: 0; transform: translateY(-4px) scale(0.98); } }
@media (prefers-reduced-motion: reduce) {
  .menu[data-state] { animation-duration: 1ms; }
}
```

## Choreography

- Related elements move together; one focal motion at a time.
- Stagger lists by 20-40 ms per item, capped (e.g. first 6-8 items), so long lists don't take seconds.
- Parent before children on enter; children before parent on exit.
- Shared element (card -> detail): the element morphs; other content fades.

## Platform equivalents

| Concept | iOS (SwiftUI) | Android (Compose / M3) | Web |
|---------|---------------|------------------------|-----|
| Standard move | `.snappy` / `.smooth` spring | M3 standard easing or spatial spring | `--easing-standard` |
| Enter | spring / `.easeOut` | emphasized decelerate | `--easing-enter` |
| Shared element | `matchedGeometryEffect`, navigation zoom transition | `SharedTransitionLayout` | View Transitions API |
| Reduced motion | `accessibilityReduceMotion` | `ANIMATOR_DURATION_SCALE` = 0 / system setting | `prefers-reduced-motion` |
