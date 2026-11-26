---
name: figma-prototype-interaction-setup-guide
description: "Set up Figma prototypes that behave like the real product with the least wiring: choose the right mechanism (frame navigation, overlays, interactive components with variants, variables and conditionals, scroll and sticky positioning) for each interaction; triggers (on click, on drag, while hovering, while pressing, key/gamepad, after delay, mouse enter/leave) and actions (navigate, change to, back, scroll to, open/swap/close overlay, set variable, conditional, set variable mode); Smart Animate layer-matching rules, transitions, easing and spring presets; flows and starting points; and step-by-step recipes for tabs, accordions, toggles, dropdowns, bottom sheets, carousels, toasts, hover states, cart counters, form validation and fake text input. Diagnoses broken prototypes: Smart Animate jumps, stuck overlays and hover states, broken scroll and duplicated-screen bloat. Use when building or fixing a Figma prototype or deciding how to prototype an interaction in Figma."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Figma Prototype Interaction Setup Guide

Most Figma prototypes are built the slow way. Every state becomes a duplicated frame, and a tab bar ends up with 40
connections. Then one copy change means editing 30 screens. Figma has better tools for most of this: interactive
components carry their own states everywhere they're used, variables hold state across screens, and overlays avoid
duplicate screens. This skill picks the right mechanism for each interaction, gives step-by-step recipes, and diagnoses
prototypes that misbehave.

## Trigger Conditions

Activate this skill when the user:
- Builds a prototype in Figma and asks how to make an interaction work
- Has a prototype with too many duplicated frames or connections
- Has broken behaviour: Smart Animate jumps, overlays stuck open, hover states that stick, scroll not working
- Needs variables, conditionals or interactive components explained for prototyping

Planning which flows to build: [clickable-prototype-flow-builder](../clickable-prototype-flow-builder/SKILL.md). Interactions Figma can't do well (real text input,
sensors, complex logic): [protopie-interaction-recipe-writer](../protopie-interaction-recipe-writer/SKILL.md). Fidelity choice: [prototype-fidelity-level-advisor](../prototype-fidelity-level-advisor/SKILL.md).

## Choosing the Mechanism

| Interaction | Use | Not |
|-------------|-----|-----|
| Component states (hover, pressed, toggle, checkbox, tabs, accordion) | Interactive components (variants + Change to) | Duplicate frames per state |
| Moving between screens | Navigate to + transition | Overlays for full screens |
| Menus, sheets, dialogs, toasts | Overlays (open, swap, close) | Navigate to a copy of the screen with the menu drawn in |
| Values that persist (cart count, selected plan, logged-in) | Variables + Set variable | One frame per value |
| Logic (if empty show error, else continue) | Conditional actions on variables | Separate flows per outcome |
| Themes, languages, device sizes | Variable modes (Set variable mode) | Duplicated pages |
| Long pages, carousels, sticky headers | Overflow scrolling + fixed/sticky position | Many frames per scroll position |
| Timed changes (splash, toast dismiss, auto-advance) | After delay trigger | Manual clicks |

## Workflow

```
1. FLOWS     -> from the flow map: starting points per task (references/figma-recipes.md)
2. COMPONENTS-> make interactive components for every stateful control used in the flows
3. VARIABLES -> create variables for state that crosses screens; bind text and visibility to them
4. SCREENS   -> one frame per distinct screen, not per state
5. WIRE      -> navigation, overlays, scroll, conditionals; transitions matched to the product
6. ANIMATE   -> Smart Animate only where layer names match (references/smart-animate-and-transitions.md)
7. TEST      -> present every flow; fix with references/troubleshooting.md
8. SHARE     -> flow links, hotspot hints off for tests, device frame set
```

## Review Checklist

Report as `CODE [severity] element: problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| FP001 | high | Broken or missing connections on task paths (dead ends, wrong destinations) |
| FP002 | high | Overlays that can't be closed (no close action, no outside click) |
| FP003 | medium | Duplicated frames per component state where an interactive component would work |
| FP004 | medium | State that should persist resets between screens (no variable) |
| FP005 | medium | Smart Animate between frames whose layer names or hierarchy differ (jumps instead of animating) |
| FP006 | medium | Scrolling content not set to overflow scroll; headers that scroll away when they should be fixed/sticky |
| FP007 | medium | Hover interactions (While hovering) used on touch prototypes |
| FP008 | low | No flow starting points, so testers start from the wrong screen |
| FP009 | low | Transitions that don't match the product (dissolve everywhere, slow 800 ms animations) |
| FP010 | low | Unused frames and connections bloating the file and slowing load |

## Output

For "how do I...": the mechanism, then numbered steps in Figma's UI terms, then gotchas. For a review: findings and fixes.
For a full prototype plan: components to make interactive, variables, frames, overlays and flows.

## Additional Resources

| File | Content |
|------|---------|
| [figma-recipes.md](references/figma-recipes.md) | Step-by-step recipes: tabs, accordion, toggle, dropdown, sheet, toast, carousel, hover, cart counter, validation, fake typing, flows |
| [smart-animate-and-transitions.md](references/smart-animate-and-transitions.md) | Triggers and actions reference, Smart Animate matching rules, transitions, easing and springs |
| [troubleshooting.md](references/troubleshooting.md) | Symptoms, causes and fixes for common prototype breakages; performance |
