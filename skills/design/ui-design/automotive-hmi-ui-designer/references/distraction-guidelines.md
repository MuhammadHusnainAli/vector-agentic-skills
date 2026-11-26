# Driver Distraction Guidelines

## NHTSA Visual-Manual Driver Distraction Guidelines (Phase 1, 2013, in-vehicle devices)

Voluntary US guidelines widely used as a test standard.

- Tasks a driver performs while driving should meet the eye-glance criteria when tested with 24 participants in a
  driving simulator:
  - mean single glance duration 2.0 s or less;
  - at least 85% of glances 2.0 s or less;
  - total eyes-off-road time 12.0 s or less (for at least 21 of 24 participants).
- Alternative occlusion test: total shutter open time 12 s or less.
- Recommended lockouts while driving ("per se" unsuitable tasks) include: manual text entry for messaging or internet,
  displaying video, displaying images not related to driving, automatically scrolling text, displaying text for
  reading (books, web pages, social media, text messages), and manual text entry beyond limited lengths.
- Guidelines assume the device is operated with one hand and support short, interruptible interactions.

## Other frameworks

| Framework | Key points |
|-----------|-----------|
| Alliance of Automobile Manufacturers (AAM) principles | Single glances generally 2 s or less; total glance time for a task about 20 s or less |
| European Statement of Principles on HMI (ESoP, 2006) | Design principles for in-vehicle information: placement, minimal distraction, interruptibility, no time-critical responses |
| JAMA guidelines (Japan) | Restrictions on displayed content and operation while driving |
| Euro NCAP (from 2026 protocols) | Assessment expected to reward physical controls for key functions (e.g. indicators, hazard lights, horn, wipers, emergency call) |

## Estimating glances during design

1. Break the task into steps (each tap, selection, or reading).
2. For each step estimate glances: one glance per decision or target acquisition; reading a list of N items adds
   glances; finding a small target adds time.
3. Assume about 1.2-1.5 s per glance for simple steps; more for searching or reading.
4. Sum the glances: total eyes-off-road time.

| Task: change radio station to a preset | Glances | Time |
|----------------------------------------|---------|------|
| Find the media tile on home screen | 1 | 1.2 s |
| Tap "Radio" | 1 | 1.2 s |
| Find and tap preset 3 | 1 | 1.5 s |
| Total | 3 | 3.9 s (well within 12 s) |

| Task: enter a new destination by typing (blocked while driving) | Glances | Time |
|--------------------------------------------------------------|---------|------|
| Open nav, search, type 12 characters, pick a result, start | 15-25 | 20-35 s: exceeds budget, lock out and offer voice |

Estimates guide design; only testing settles it.

## Testing

- **Occlusion:** shutter glasses alternate 1.5 s vision / 1.5 s occlusion; the task must complete within 12 s total
  vision time. Cheap and repeatable in the lab.
- **Simulator with eye tracking:** measures glance durations and total eyes-off-road time while driving a scenario.
- **Lane keeping and headway variance:** secondary measures of distraction.
- Test with a range of ages; older drivers take longer to read and target.
