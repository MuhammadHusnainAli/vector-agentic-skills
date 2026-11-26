---
name: kiosk-touchscreen-ui-designer
description: "Design self-service kiosks and public touchscreens (ordering, ticketing, check-in, wayfinding, payment, information) for first-time, standing, hurried users of every height and ability: reach ranges from the 2010 ADA Standards (15-48 inches) mapped onto the physical screen, mounting height, tilt and glare, physical touch-target sizes in millimetres, attract loop and start, language choice up front, short linear flows with big choices, no typing where possible, idle timeout with warning and full session reset for privacy, hardware placement, staff help, and accessible modes required for self-service terminals (speech output with headphones, tactile keypad, lowered reach-zone layout, high contrast) under ADA 707, EN 301 549 and the European Accessibility Act. Reviews kiosks for out-of-reach controls, small targets, typing, missing timeouts and resets, no audio path and dead ends. Use when designing or auditing a kiosk, self-checkout, ticket machine, check-in terminal or public touchscreen."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Kiosk Touchscreen UI Designer

A kiosk user has never seen your interface. They're standing, often in a queue, maybe holding a bag or a child, and leave
the moment it gets confusing. The next user might be in a wheelchair, blind, or not speak the default language. Kiosks also
have physical facts screens don't: the top of a tall portrait display can be out of reach, sunlight washes out contrast,
and the previous customer's order is still on screen when the next person walks up. This skill designs for all of it and
audits existing kiosks.

## Trigger Conditions

Activate this skill when the user:
- Designs a self-service kiosk, self-checkout, ticket or fare machine, check-in or registration terminal, or public display
- Decides screen size, mounting height and where controls go on screen
- Needs accessibility for self-service terminals (ADA, EN 301 549, European Accessibility Act)
- Has kiosks with long queues, abandoned sessions or staff constantly helping

Checkout logic: `ecommerce-checkout-ui-designer`. Large touch targets and glance design in vehicles: `automotive-hmi-ui-designer`.

## Workflow

```
1. CONTEXT   -> location, light, queue pressure, users (first-time? languages? disabilities?), session length
2. HARDWARE  -> screen size, orientation, mounting height, tilt; payment, printer, scanner, keypad positions (references/reach-and-hardware.md)
3. ZONES     -> map the 15-48 in reach range onto the screen; interactive controls only inside it
4. FLOW      -> start -> language -> 3-6 linear steps -> pay -> done; no dead ends (references/kiosk-flows.md)
5. INPUT     -> big choices instead of typing; scanning; phone handoff (QR) for complex input
6. TIMEOUTS  -> idle warning, reset, privacy clearing
7. ACCESS    -> speech output, tactile keypad navigation, lowered layout, contrast and text size (references/kiosk-accessibility.md)
8. TEST      -> on the real hardware, in place, with first-time users, including a wheelchair user and a screen-reader user
9. REVIEW    -> checklist below
```

## Rules

| Rule | Why |
|------|-----|
| All controls within 15-48 in (380-1220 mm) above the floor | ADA 308 reach range; also comfortable for short and tall users |
| Targets about 20 mm or larger, with space between | Standing users tap fast and imprecisely; dirty screens; gloves |
| One decision per screen, big choices | First-time users; queue pressure |
| Language first, flags plus language names | Users can't read the default language |
| No typing where it can be avoided | On-screen keyboards are slow and error-prone in public |
| Every screen has Back, Start over and Help | No dead ends; staff help is part of the design |
| Idle warning then full reset | Privacy and readiness for the next user |
| Tap only; no hover, long-press or multi-finger gestures | Not discoverable and not accessible |

## Review Checklist

Report as `CODE [severity] screen/element: problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| KS001 | high | Interactive controls above 48 in or below 15 in from the floor |
| KS002 | high | No audio or tactile path for blind users (ADA 707, EN 301 549, EAA) |
| KS003 | high | No idle timeout, or no warning before it; previous user's data visible to the next person |
| KS004 | high | Dead ends: screens without back, start over or help |
| KS005 | medium | Targets smaller than about 15-20 mm, or spaced too tightly |
| KS006 | medium | Text entry required where scanning, choices or phone handoff would work |
| KS007 | medium | Language selection missing or hidden after the first screen |
| KS008 | medium | Hover, long-press, swipe-only or multi-touch interactions |
| KS009 | medium | Low contrast or small text for the viewing distance and lighting (sunlight, glare) |
| KS010 | medium | Payment/printer/scanner location not shown on screen when needed |
| KS011 | low | Attract loop that's unclear about how to start, or starts only from one small button |
| KS012 | low | No confirmation of what was ordered/paid; no receipt option |

## Output

1. Hardware and reach plan: screen position, reach zone overlay, hardware positions
2. Flow with screens, choices and timeouts
3. Layout grid with target sizes in mm and px for the screen's ppi
4. Accessibility mode spec
5. Review findings, if auditing

## Additional Resources

| File | Content |
|------|---------|
| [reach-and-hardware.md](references/reach-and-hardware.md) | ADA reach ranges, mapping reach onto screens (worked example), tilt, glare, target size maths, hardware placement |
| [kiosk-flows.md](references/kiosk-flows.md) | Attract, start, language, flow patterns, input alternatives, timeouts and reset, errors, help, receipts |
| [kiosk-accessibility.md](references/kiosk-accessibility.md) | ADA 707, EN 301 549 and EAA requirements, speech and keypad modes, lowered layout, testing |
