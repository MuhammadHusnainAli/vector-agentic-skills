---
name: ui-microinteraction-designer
description: "Design and specify microinteractions that make a product feel responsive and clear: Dan Saffer's model (trigger, rules, feedback, loops and modes), response-time limits (0.1 s instant, 1 s flow, 10 s attention), feedback for every action (pressed states, optimistic updates, progress, success, undo), motion with purpose (orientation, continuity, attention, feedback), duration by distance and size, easing (ease-out to enter, ease-in to exit, standard for moves), motion tokens, choreography and stagger, haptics and sound, loading patterns (spinner delay and minimum time, skeletons, progress), performance (transform and opacity only), and accessibility (prefers-reduced-motion alternatives, WCAG 2.2.2, 2.3.1, 2.3.3). Writes engineer-ready specs and reviews motion for purposeless decoration, slow or inconsistent timing, layout-property animation, missing reduced-motion handling and silent actions. Use when designing interaction details, writing motion specs, defining motion tokens or reviewing how a UI feels."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# UI Microinteraction Designer

Microinteractions are the small moments around a single action: a like, a toggle, a copy, a save, a pull to refresh. They
decide whether an interface feels responsive or dead. Good ones answer three questions every time: did it register, is it
working, did it succeed? Motion is a tool for those answers, not decoration. This skill designs the moments, writes specs
engineers can build exactly, and reviews motion that's slow, inconsistent or inaccessible.

## Trigger Conditions

Activate this skill when the user:
- Designs feedback for actions (save, like, add to cart, copy, delete, toggle, submit)
- Specifies animations or transitions for handoff, or defines motion tokens
- Says the UI "feels slow", "janky", "flat" or "too animated"
- Needs reduced-motion handling or loading-state behaviour

Button states: `button-state-variant-designer`. Prototyping motion: `protopie-interaction-recipe-writer`,
`figma-prototype-interaction-setup-guide`.

## Workflow

```
1. LIST      -> the interactions on the screen and the question each must answer (registered? working? done?)
2. MODEL     -> trigger, rules, feedback, loops/modes per interaction (references/microinteraction-spec.md)
3. TIMING    -> what happens at 0-100 ms, 100 ms-1 s, 1-10 s, over 10 s
4. MOTION    -> purpose first; then property, duration, easing, distance from tokens (references/motion-tokens.md)
5. REDUCED   -> reduced-motion alternative for every animation (references/motion-accessibility-and-performance.md)
6. SPEC      -> one spec table per interaction; prototype the tricky ones
7. REVIEW    -> checklist below; test on a low-end device and with reduced motion on
```

## Response-Time Rules

| Elapsed | Users perceive | Design response |
|---------|----------------|-----------------|
| 0-100 ms | Instant | Pressed state, toggle flips, text appears; no spinner |
| 100 ms-1 s | Delay, still in flow | Optimistic update, or subtle inline progress after about 300-400 ms |
| 1-10 s | Waiting | Progress indicator with context ("Uploading 3 of 8"); keep the rest usable |
| Over 10 s | Attention lost | Determinate progress, time estimate, background the task, notify on completion |

Show spinners only after a short delay (about 300-500 ms), and once shown keep them for a minimum time (about 500 ms) so
fast responses don't flicker.

## Motion Purpose Test

Keep an animation only if it does at least one of:
- **Orient:** shows where something came from or went (a sheet sliding from the button that opened it)
- **Connect:** keeps continuity between states (shared element from card to detail)
- **Feedback:** confirms an action (checkmark draw, item drops into the cart)
- **Attention:** draws the eye to a change that matters (new item highlight), once

## Review Checklist

Report as `CODE [severity] interaction: problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| MI001 | high | Action with no immediate feedback (nothing changes within 100 ms) |
| MI002 | high | No reduced-motion alternative for large movement, parallax, zoom or auto-playing motion |
| MI003 | high | Flashing more than 3 times per second (WCAG 2.3.1), or auto-moving content over 5 s with no pause (2.2.2) |
| MI004 | medium | Animation with no purpose (decoration that delays the task) |
| MI005 | medium | UI transitions over about 500 ms for common actions, or inconsistent durations for the same kind of change |
| MI006 | medium | Linear easing on movement; ease-in on entering elements |
| MI007 | medium | Animating layout properties (width, height, top, left, margin) instead of transform and opacity |
| MI008 | medium | Spinner flicker for fast responses, or a spinner where optimistic UI fits |
| MI009 | medium | Success or failure not communicated to screen readers (no live region) |
| MI010 | low | `transition: all` (animates unintended properties) |
| MI011 | low | Haptics or sounds that don't match the meaning, or can't be turned off |

## Output

Per interaction, a spec table: trigger, rules, states, feedback (visual, text, haptic, screen reader), motion (property,
from/to, duration token, easing token, delay), reduced-motion alternative, edge cases (failure, double trigger, offline).
Plus motion tokens if the system lacks them, and review findings when auditing.

## Additional Resources

| File | Content |
|------|---------|
| [microinteraction-spec.md](references/microinteraction-spec.md) | Saffer's model, spec template, worked examples (like, copy, toggle, add to cart, delete with undo, pull to refresh) |
| [motion-tokens.md](references/motion-tokens.md) | Duration and easing tokens, CSS values, duration by distance, choreography and stagger, platform equivalents |
| [motion-accessibility-and-performance.md](references/motion-accessibility-and-performance.md) | Reduced motion, WCAG criteria, vestibular triggers, compositor-only properties, loading patterns, haptics |
