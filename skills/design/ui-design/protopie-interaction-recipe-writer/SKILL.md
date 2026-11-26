---
name: protopie-interaction-recipe-writer
description: "Write step-by-step ProtoPie recipes for interactions that Figma can't prototype convincingly: real text input and validation, OTP fields, sliders and dials tied to values, swipe-to-delete, drag and drop with snapping, pull to refresh, carousels with paging, conditional flows, counters and carts with variables, timers, sensors (tilt, sound, voice), keyboard and gamepad input, and multi-device or hardware prototypes (phone + TV, car HMI) with Send/Receive and ProtoPie Connect. Each recipe lists layers and containers, the trigger, responses with values, conditions, variables (local or global), formulas, and how to test in ProtoPie Player. Covers ProtoPie building blocks (scenes, layers, components, interactions, triggers, responses, conditions, variables, formulas, Chain, Range, Detect), naming and structure for maintainable pies, and debugging (Debug panel, variables that don't update, conflicting triggers). Use when building or fixing a ProtoPie prototype, or deciding how to prototype an advanced interaction."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# ProtoPie Interaction Recipe Writer

ProtoPie can prototype what Figma can't: real keyboard input, values that follow a finger, logic, sensors, sound and
several devices talking to each other. In ProtoPie every interaction is a trigger, its responses and, optionally,
conditions. Writing those down precisely before building is what keeps a pie maintainable. This skill writes recipes the
way an experienced prototyper would set them up, and debugs ones that misbehave.

## Trigger Conditions

Activate this skill when the user:
- Prototypes an interaction that needs real input, live values, logic, sensors, sound or multiple devices
- Builds or fixes a ProtoPie prototype
- Asks how to do something in ProtoPie (slider, OTP, swipe-to-delete, drag and drop, multi-screen)
- Needs a prototype for a car, TV, kiosk or wearable with real inputs

Simpler click-through flows: `figma-prototype-interaction-setup-guide`. Choosing fidelity: `prototype-fidelity-level-advisor`.
Car interfaces: `automotive-hmi-ui-designer`.

## Workflow

```
1. INTERACTION -> describe it as: when <trigger> on <layer>, if <condition>, then <responses>
2. STRUCTURE   -> layers and containers needed (scroll, paging), components for repeated parts (references/protopie-building-blocks.md)
3. STATE       -> variables (number/text/colour; this scene or all scenes) and their initial values
4. RECIPE      -> trigger, responses (property, value or formula, duration, easing), conditions (references/protopie-recipes.md)
5. BUILD       -> in ProtoPie Studio; name every layer and interaction
6. TEST        -> preview + Debug panel for variables; ProtoPie Player on the real device
7. HARDEN      -> edge cases: rapid repeats, conflicting triggers, reset to start (references/formulas-and-debugging.md)
```

## Recipe Format

Write every recipe in this structure so it can be built exactly:

```
Name:        Swipe row to delete
Layers:      Row (container), Row content, Delete button (behind content)
Variables:   none
Interaction 1
  Trigger:   Drag on "Row content", axis X, range -96 to 0
  Responses: (built into Drag: content follows finger)
Interaction 2
  Trigger:   Touch Up on "Row content"
  Condition: `Row content`.x < -48
  Responses: Move "Row content" x = -96, 200 ms, Ease Out
  Else:      Move "Row content" x = 0, 200 ms, Ease Out
Interaction 3
  Trigger:   Tap on "Delete button"
  Responses: Opacity "Row" 0, 150 ms; Scale "Row" height to 0 (or Move rows below up), 200 ms
Test:        Drag slowly past and before the threshold; tap delete; drag a second row
```

## Review Checklist

Report as `CODE [severity] interaction: problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| PP001 | high | Interaction can't be triggered on the target device (hover on touch, keyboard on phone without input layer) |
| PP002 | high | Conflicting triggers on the same layer (Tap and Drag both moving it) without conditions |
| PP003 | medium | State duplicated in layer properties instead of a variable; values drift out of sync |
| PP004 | medium | Global variables used where scene variables suffice (or the reverse: value lost on scene change) |
| PP005 | medium | Unnamed layers and interactions ("Rectangle 4", "Tap 2"): unmaintainable |
| PP006 | medium | No reset: prototype can't return to its start state between test sessions |
| PP007 | low | Responses without easing or with long durations that make the prototype feel slower than the product |
| PP008 | low | Repeated UI built by copy-paste instead of components with Send/Receive |

## Output

Recipes in the format above, a list of variables with scope and initial values, layer structure, and a test script for
the device. For debugging: likely cause and the fix.

## Additional Resources

| File | Content |
|------|---------|
| [protopie-building-blocks.md](references/protopie-building-blocks.md) | Scenes, layers, containers, components, triggers, responses, conditions, variables, Connect and Player |
| [protopie-recipes.md](references/protopie-recipes.md) | Recipes: text input validation, OTP, slider, drag and drop, pull to refresh, paging carousel, cart counter, timer, multi-device, sensors |
| [formulas-and-debugging.md](references/formulas-and-debugging.md) | Formula syntax and common functions, property references, debugging approach and common failures |
