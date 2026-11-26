# Motion Accessibility and Performance

## Who is affected

- People with vestibular disorders: large movement, parallax, zooming and spinning can cause dizziness and nausea.
- People with attention and cognitive disabilities: auto-moving content distracts.
- People with photosensitive epilepsy: flashing can trigger seizures.

## WCAG criteria

| Criterion | Level | Requirement |
|-----------|-------|-------------|
| 2.2.2 Pause, Stop, Hide | A | Moving, blinking or scrolling content that starts automatically, lasts over 5 s and is shown with other content can be paused, stopped or hidden |
| 2.3.1 Three Flashes or Below Threshold | A | Nothing flashes more than three times in any one second (unless below flash thresholds) |
| 2.3.3 Animation from Interactions | AAA | Motion animation triggered by interaction can be disabled, unless essential |

Treat 2.3.3 as a baseline anyway: respect the OS reduced-motion setting.

## Reduced-motion alternatives

| Animation | Reduced alternative |
|-----------|---------------------|
| Slide-in sheet / page transition | Crossfade or instant |
| Zoom / scale transitions | Fade |
| Parallax scrolling | Static |
| Auto-playing carousel or video background | Paused by default with play control |
| Animated illustrations (Lottie) | Static first frame or end frame |
| Scroll-triggered reveal animations | Content visible immediately |
| Spinner | Keep (it's a status indicator), or a pulsing opacity |

Reduced motion means less movement, not no feedback: keep colour and opacity changes, state changes and text.

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 1ms !important; animation-iteration-count: 1 !important;
                           transition-duration: 1ms !important; scroll-behavior: auto !important; }
}
```
A blanket rule like this is a safety net; still design specific alternatives for important transitions.

## Performance

- Animate `transform` and `opacity`: the compositor handles them without layout or paint.
- Avoid animating `width`, `height`, `top`, `left`, `margin`, `padding`, `box-shadow`, `filter` on large areas.
  For size changes use FLIP (measure, invert with transform, play) or `grid-template-rows: 0fr -> 1fr` for accordions.
- `will-change` only on elements about to animate; remove it after.
- Target 60 fps (16.7 ms per frame); test on a low-end Android phone with CPU throttling.
- Prefer CSS or the Web Animations API over JavaScript per-frame updates; use View Transitions for page/state transitions.

## Loading patterns

| Situation | Pattern |
|-----------|---------|
| Under about 300 ms expected | Nothing; or optimistic update |
| Layout known, content loading | Skeleton matching the final layout |
| Indeterminate, short | Spinner after about 300-500 ms delay, minimum about 500 ms on screen |
| Determinate (upload, export) | Progress bar with percentage and item counts |
| Long (over 10 s) | Progress + estimate + allow leaving; notify when done |

Skeleton shimmer is motion: reduce it under reduced motion (static skeleton).

## Haptics and sound

- Haptics confirm physical-feeling actions (toggle, success, error, threshold reached in a drag); one per event.
- Match platform semantics: selection change, light/medium impact, success/warning/error notification haptics.
- Sounds only where expected (messages sent, payments, alarms), off by default in productivity tools, always
  controllable.
- Never use haptics or sound as the only feedback.
