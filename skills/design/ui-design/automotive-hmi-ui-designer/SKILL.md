---
name: automotive-hmi-ui-designer
description: "Design in-vehicle infotainment and cluster interfaces that keep eyes on the road: driver-distraction budgets from the NHTSA visual-manual guidelines (single glances of 2 seconds or less, 12 seconds total eyes-off-road per task) and the AAM and European principles, task decomposition into glances, lockouts while driving (text entry, video, long text, deep lists), character height from viewing distance (ISO 15008 visual-angle guidance), touch targets in millimetres for a moving car (Android Automotive's 76dp minimum), physical and steering-wheel controls, voice for complex input, day/night modes, alert priority, interruptibility, cluster and HUD content, and Android Automotive and CarPlay constraints. Reviews HMI designs for over-budget tasks, small type and targets, typing while driving, buried safety controls and colour-only warnings. Use when designing or reviewing a car infotainment system, cluster, HUD or in-car app."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Automotive HMI UI Designer

In a car, the interface competes with the road. Every second the driver looks at the screen is a second they don't see
the car braking ahead. So the design unit is the glance: a task is acceptable if it can be done in short glances adding up
to a small total, with the hands mostly on the wheel. Designs that are fine on a phone (small text, long lists, typing,
nested menus) are dangerous here. This skill budgets tasks in glances, sizes type and targets for distance and vibration,
and reviews HMI designs against the distraction guidelines the industry tests to.

## Trigger Conditions

Activate this skill when the user:
- Designs an infotainment system, instrument cluster, head-up display or in-car app (Android Automotive, CarPlay, Android Auto)
- Needs to know what can be shown or done while driving
- Sizes text and touch targets for a vehicle display
- Reviews an HMI for driver distraction, or prepares for distraction testing

TV and other at-a-distance interfaces: `tv-10-foot-ui-designer`. Prototyping with real hardware: `protopie-interaction-recipe-writer`.
Voice interaction: `voice-ui-conversation-designer`.

## Workflow

```
1. TASKS     -> list driver tasks (navigation, media, calls, climate, settings) with frequency and while-driving need
2. BUDGET    -> decompose each task into glances; estimate and later measure (references/distraction-guidelines.md)
3. LOCKOUTS  -> what is disabled or simplified while driving; parked-only features
4. CHANNEL   -> best input per task: physical control, steering wheel, voice, touch (references/input-and-layout.md)
5. SIZE      -> character height and touch targets from eye distance, display ppi and vibration
6. MODES     -> day/night, alert priority, interruptions and resumption
7. SURFACES  -> centre display, cluster, HUD: what goes where
8. VALIDATE  -> occlusion or eye-tracking tests in a simulator; check against the budget
9. REVIEW    -> checklist below
```

## Glance Budget

| Criterion (NHTSA visual-manual guidelines, 2013) | Limit |
|---------------------------------------------------|-------|
| Single glance away from the road | Mean 2.0 s or less; 85% of glances 2.0 s or less |
| Total eyes-off-road time per task | 12.0 s or less (for 85% of test drivers) |
| Occlusion alternative | Total shutter-open time 12 s or less |
| Per-se lockouts while driving | Manual text entry, video, automatically scrolling text, displaying text to read (messages, web, social media), and more |

Design target: each step readable in one glance of about 1.5 s or less, tasks in 3-5 glances.

## Review Checklist

Report as `CODE [severity] task/screen: problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| HM001 | high | Task likely exceeds 12 s total eyes-off-road, or needs glances over 2 s |
| HM002 | high | Text entry, video, scrolling or long text available while driving |
| HM003 | high | Safety-relevant or frequent controls (defrost, hazard, climate, volume) only in touch menus |
| HM004 | high | Warnings by colour or visual only (no sound or haptic for urgent alerts), or alerts that hide critical driving info |
| HM005 | medium | Text below about 16 arcminutes at the driver's eye distance; low contrast; thin fonts |
| HM006 | medium | Touch targets under about 10-12 mm, or targets too close together for use while moving |
| HM007 | medium | Deep menus (more than 2-3 levels) or long lists while driving |
| HM008 | medium | Bright night mode (white backgrounds) or day mode unreadable in sunlight |
| HM009 | medium | Task not interruptible: state lost when the driver looks away or the screen times out |
| HM010 | medium | Information on the centre display that belongs in the cluster or HUD (turn-by-turn next manoeuvre) |
| HM011 | low | Animations or auto-playing content drawing attention while driving |
| HM012 | low | Voice not available for complex input (destinations, contacts, messages) |

## Output

1. Task inventory with while-driving decision (allowed, simplified, locked out)
2. Glance budget per task with step-by-step estimates
3. Sizing table: text and target sizes for the display and eye distance
4. Input channel per task and layout zones (driver reach, glance zones)
5. Mode and alert specs; validation plan; review findings

## Additional Resources

| File | Content |
|------|---------|
| [distraction-guidelines.md](references/distraction-guidelines.md) | NHTSA, AAM and European principles, lockouts, glance estimation, occlusion and eye-tracking tests |
| [input-and-layout.md](references/input-and-layout.md) | Physical, steering wheel, voice and touch; sizing maths; layout zones; cluster and HUD; day/night |
| [platforms-and-alerts.md](references/platforms-and-alerts.md) | Android Automotive OS and CarPlay constraints, alert prioritisation and multimodal warnings, interruptions |
