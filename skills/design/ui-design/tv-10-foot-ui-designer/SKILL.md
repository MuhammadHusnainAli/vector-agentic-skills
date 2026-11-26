---
name: tv-10-foot-ui-designer
description: "Design TV and living-room interfaces viewed from about 3 metres and driven by a remote: text and target sizes from visual angle (screen size, resolution and viewing distance to minimum font px), overscan and safe areas (tvOS, Android TV / Google TV, title-safe and action-safe), the focus model (one focused element, unmistakable focus state with scale, glow or outline, predictable D-pad movement, no traps, focus memory per row), press-count budgets, rows and side navigation, back behaviour, text entry alternatives (QR code sign-in, voice), playback controls, colour on TVs and accessibility. Reviews TV designs for small text, hover-dependent UI, weak focus states, focus traps, long press paths, unsafe-area content and keyboard-heavy flows. Use when designing or reviewing apps for Apple TV, Android TV / Google TV, Fire TV, Roku, smart TVs or game consoles."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# TV 10-Foot UI Designer

A TV interface is a big screen seen from far away, driven by five buttons. Everything that matters follows from that.
Text sizes come from visual angle, not pixels. There's no pointer, so focus is the only way the user knows where they are.
Every extra press is felt, and typing with a remote is miserable. This skill sizes TV interfaces from viewing geometry,
designs the focus model and reviews designs ported from web or mobile.

## Trigger Conditions

Activate this skill when the user:
- Designs an app for Apple TV, Android TV / Google TV, Fire TV, Roku, a smart TV platform or a console
- Ports a web or mobile design to TV
- Asks about TV text sizes, safe areas, focus states or D-pad navigation
- Has users getting lost, or flows with lots of remote presses or typing

Navigation patterns in general: [navigation-pattern-selector](../navigation-pattern-selector/SKILL.md). Game interfaces: [game-hud-ui-designer](../game-hud-ui-designer/SKILL.md).

## Workflow

```
1. CONTEXT   -> platforms, remotes (D-pad, touch surface, pointer remotes, game controllers), screen sizes, distance
2. SIZES     -> minimum text and target sizes from visual angle (references/tv-sizing.md)
3. SAFE AREA -> keep text and controls inside the platform safe area
4. STRUCTURE -> side or top navigation, rows/shelves, hero, details, player (references/tv-layout-and-focus.md)
5. FOCUS     -> focus state design, movement rules, initial focus, focus memory, back behaviour
6. PRESSES   -> count presses for top tasks; restructure paths that exceed the budget
7. INPUT     -> replace typing with phone sign-in, QR codes, voice, recent searches
8. REVIEW    -> run the checklist below on a real TV at real distance
```

## Rules That Hold Up

| Rule | Why |
|------|-----|
| Body text about 28-32px at 1080p for 55" at 2.5-3m; never under about 24px | Below about 16 arcminutes, reading slows sharply |
| One focused element, always visible | Without a pointer, focus is the user's position |
| Focus moves to the nearest item in the pressed direction | Surprising jumps make users lose their place |
| Rows remember their focused item | Returning to a row lands where the user left it |
| Back always goes back one level; from the top level, the platform decides (often exit) | Users press Back to escape anything |
| Fewer, larger items per screen than on web | Each item costs presses to reach |
| No hover states, tooltips or small close buttons | Remotes don't hover |
| Avoid pure white full-screen backgrounds | Glare in a dark room; some TVs bloom and band |

## Review Checklist

Report as `CODE [severity] screen/element: problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| TV001 | high | Text smaller than the minimum for the target screen and distance |
| TV002 | high | Focus state hard to see (colour-only change, thin outline, low contrast) |
| TV003 | high | Focus trap, unreachable element, or no initial focus on screen load |
| TV004 | high | Text or controls outside the platform safe area |
| TV005 | high | Flow that needs typing with the on-screen keyboard where an alternative exists (sign-in, search with suggestions) |
| TV006 | medium | Top task needs more than about 8-10 presses from home |
| TV007 | medium | Back button behaviour inconsistent, or exits the app from a deep screen |
| TV008 | medium | Focus jumps unpredictably (non-spatial order, skipping rows) or rows don't remember position |
| TV009 | medium | Web/mobile patterns: hover reveals, tooltips, dropdowns, small icons, scrollbars |
| TV010 | medium | Autoplaying previews with sound or with no way to stop; motion ignoring reduce-motion settings |
| TV011 | low | Pure white large backgrounds, saturated reds that bloom, thin lines that flicker (interlace/ringing) |
| TV012 | low | Missing captions settings, screen-reader labels or high-contrast support |

## Output

1. Sizing table for the target screens: minimum text, target size, safe area
2. Screen structure and navigation model
3. Focus specification: visual treatment, movement rules, initial focus, memory, back
4. Press-count table for top tasks
5. Input alternatives for text entry
6. Review findings, if reviewing

## Additional Resources

| File | Content |
|------|---------|
| [tv-sizing.md](references/tv-sizing.md) | Visual-angle formula, worked font-size table, safe areas per platform, platform type scales |
| [tv-layout-and-focus.md](references/tv-layout-and-focus.md) | Screen structures, focus design, D-pad movement rules, press budgets, back/home, input, player, accessibility |
