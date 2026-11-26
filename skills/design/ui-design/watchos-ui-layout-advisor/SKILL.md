---
name: watchos-ui-layout-advisor
description: "Design Apple Watch interfaces for seconds-long use: decide what belongs on the wrist at all, design for a 2-second glance, lay out for every case size (41mm to 49mm and older 38-46mm) in points with full-width controls and the Digital Crown, use watchOS 10+ structure (vertical page TabView, NavigationStack and NavigationSplitView, toolbar button placements, full-screen colour backgrounds), SF Compact text styles and Dynamic Type, black OLED backgrounds, always-on display states, double tap, haptics, notifications (short and long look), and complications and Smart Stack widgets (accessoryCircular, Rectangular, Inline, Corner). Reviews watch designs for phone screens shrunk down, text-heavy screens, small targets, deep navigation, horizontal swiping between unrelated pages, missing always-on treatment and complications that don't update. Use when designing or reviewing a watchOS app, companion watch experience, complication, widget or watch notification."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# watchOS UI Layout Advisor

People look at their watch for about two seconds, often while doing something else. A watch app that tries to be a small
phone app fails: too much text, too many steps, targets too small for a moving finger. Good watch design starts by
cutting to the one or two things worth doing on the wrist, then delivers them as a glance, a complication or a
notification. The app itself comes after those. This skill decides what goes on the watch, lays it out for every case
size, and reviews existing designs.

## Trigger Conditions

Activate this skill when the user:
- Designs a watchOS app or a watch companion for an iPhone app
- Designs complications, Smart Stack widgets or watch notifications
- Asks about Apple Watch screen sizes, layout, navigation or the Digital Crown
- Reviews a watch design that feels cramped or slow

iPhone app review: [ios-human-interface-guidelines-checker](../ios-human-interface-guidelines-checker/SKILL.md). Glance-time thinking for other small, at-a-distance
interfaces: [automotive-hmi-ui-designer](../automotive-hmi-ui-designer/SKILL.md), [tv-10-foot-ui-designer](../tv-10-foot-ui-designer/SKILL.md).

## Workflow

```
1. JOBS      -> list wrist moments: check status, act on alert, quick input, track a session; cut everything else
2. SURFACE   -> per job: complication / Smart Stack widget / notification / app screen (decision table below)
3. GLANCE    -> the one thing to see in 2 seconds per screen: big, high contrast, top of the screen
4. STRUCTURE -> vertical pages, list -> detail, or a single scrolling view (references/watch-navigation-and-interaction.md)
5. LAYOUT    -> design at 41mm and 45/46mm; check 49mm and the oldest supported size (references/watch-sizes-and-layout.md)
6. STATES    -> always-on (dimmed), loading, offline/phone-unreachable, empty, error
7. INPUT     -> buttons, Digital Crown, double tap, dictation/Scribble only when unavoidable
8. COMPANION -> complications and widgets (references/complications-and-widgets.md)
9. REVIEW    -> checklist below; test on device, on the wrist, while walking
```

## Which Surface

| Job | Best surface |
|-----|--------------|
| See a value often (next meeting, steps, battery, price) | Complication |
| See timely info when relevant (boarding pass, timer, delivery) | Smart Stack widget (with relevance) |
| React to an event (reply, approve, snooze) | Notification with actions |
| Short task with a few steps (start workout, log water, pay) | App screen, 1-3 taps |
| Long reading, complex forms, settings management | iPhone, not the watch |

## Review Checklist

Report as `CODE [severity] screen: problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| WO001 | high | The main info isn't readable in 2 seconds (too small, low contrast, below the fold) |
| WO002 | high | Tap targets too small or too close (aim for full-width buttons, at least 44pt tall) |
| WO003 | high | Task needs more than about 3 taps or any typing that could be avoided |
| WO004 | high | No always-on state: sensitive info shown when the wrist is down, or a frozen, misleading screen |
| WO005 | medium | Phone patterns: dense lists, tables, hamburger menus, small toolbars full of icons |
| WO006 | medium | Layout designed for one case size; clips or wastes space on others |
| WO007 | medium | Navigation deeper than 2 levels, or horizontal paging between unrelated sections (watchOS 10+ uses vertical pages) |
| WO008 | medium | Text not using text styles / Dynamic Type; truncates at larger sizes |
| WO009 | medium | Light or busy backgrounds that waste battery on OLED and blur with the bezel |
| WO010 | medium | Complication or widget shows stale data with no timestamp, or text overflows its family |
| WO011 | low | Digital Crown unused where it fits (scrolling, adjusting values) |
| WO012 | low | Haptics missing for confirmations, or overused |

## Output

1. Wrist-jobs table: job, surface, the glance (what's seen first), actions
2. Screen layouts at 41mm and 46mm, noting what changes at 49mm and the oldest size
3. Navigation map and input methods
4. Always-on, offline and error states
5. Complication and widget families with content per family
6. Review findings, if reviewing

## Additional Resources

| File | Content |
|------|---------|
| [watch-sizes-and-layout.md](references/watch-sizes-and-layout.md) | Case sizes in points, margins, text styles, layout rules, colour and always-on |
| [watch-navigation-and-interaction.md](references/watch-navigation-and-interaction.md) | watchOS 10+ structure, toolbars, Digital Crown, double tap, haptics, notifications, input |
| [complications-and-widgets.md](references/complications-and-widgets.md) | Widget families, content per family, relevance in the Smart Stack, update budgets, design rules |
