---
name: elevation-shadow-system-designer
description: "Design an elevation system where depth means something: a small set of levels tied to roles (base, raised card, sticky header, dropdown and popover, dialog, toast), layered shadows (tight key shadow plus soft ambient shadow) from one consistent light source, tinted low-alpha shadow colours instead of grey or black, elevation through lighter surfaces and borders in dark mode, z-index scale tokens that match the levels, shadows vs borders vs surface tone, interaction elevation (hover lift, dragging), performance-safe shadow animation, forced-colors fallbacks, and platform equivalents (Material 3 tonal elevation, Apple materials, Fluent shadow ramp). Reviews designs and CSS for too many shadows, conflicting light directions, harsh shadows, wrong stacking order, z-index sprawl and invisible dark-mode elevation. Use when defining shadow and elevation tokens, cleaning up inconsistent shadows, or designing layering for menus, dialogs and sticky elements."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Elevation & Shadow System Designer

Elevation tells people what's on top of what and what they can interact with. A dropdown above the page, a dialog above
everything, a dragged card lifted from its list. When every designer picks their own box-shadow, that message gets lost.
Codebases end up with dozens of unique shadows, light coming from different directions, and z-index values like 99999.
This skill defines a few levels with a meaning each, builds the shadows from one light source, and makes elevation work in
dark mode and high-contrast modes.

## Trigger Conditions

Activate this skill when the user:
- Defines shadow or elevation tokens for a design system
- Has inconsistent, harsh or muddy shadows, or many one-off box-shadows
- Designs layering for cards, sticky headers, menus, dialogs, toasts or drag and drop
- Has z-index bugs (menus under headers, toasts under dialogs)
- Needs elevation to work in dark mode

Dark surfaces: [dark-mode-palette-designer](../dark-mode-palette-designer/SKILL.md). Tokens: [design-token-architecture-builder](../design-token-architecture-builder/SKILL.md). Cards: [card-component-designer](../card-component-designer/SKILL.md).

## Workflow

```
1. ROLES     -> list layers in the product: page, cards, sticky bars, popovers, drawers, dialogs, toasts, drag
2. LEVELS    -> 4-6 levels; assign each role a level (table below)
3. LIGHT     -> one light source (above, slightly in front): positive y offsets only, x = 0
4. SHADOWS   -> layered key + ambient per level, tinted colour, low alpha (references/shadow-recipes.md)
5. DARK      -> lighter surfaces per level + subtle border; shadows only for floating layers
6. Z-INDEX   -> tokens aligned with levels (references/layering-and-z-index.md)
7. STATES    -> hover lift (one level), pressed (back down), dragging (top level)
8. REVIEW    -> checklist below; check in light, dark and forced colors
```

## Levels and Roles

| Level | Roles | Light theme | Dark theme |
|-------|-------|-------------|------------|
| 0 | Page, flat sections | No shadow | Base surface |
| 1 | Cards, tiles, raised panels | Subtle shadow or border | Surface +1 step, border |
| 2 | Sticky header/footer, hovered cards, small popovers | Small shadow | Surface +2, border |
| 3 | Dropdowns, menus, popovers, date pickers | Medium shadow | Surface +3, soft shadow |
| 4 | Drawers, sheets, dialogs | Large shadow + scrim | Surface +4, shadow + scrim |
| 5 | Toasts, dragged items | Largest shadow | Surface +5, shadow |

Higher level = closer to the user = above lower levels in stacking order. A dropdown inside a dialog belongs to the
dialog's layer stack and still renders above it.

## Review Checklist

Report as `CODE [severity] problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| EL001 | high | Stacking order contradicts elevation (menu under a sticky header, toast under a dialog scrim) |
| EL002 | high | Elevation is the only cue separating interactive layers, and it disappears in dark mode or forced colors |
| EL003 | medium | More distinct shadows than levels (usually 10+ unique box-shadows in the CSS) |
| EL004 | medium | Conflicting light directions (some shadows offset left, some right, or upward) |
| EL005 | medium | Harsh or muddy shadows: pure black at high alpha, one big blur with no key shadow, large spread |
| EL006 | medium | Z-index values outside a token scale (999, 9999, 2147483647) |
| EL007 | medium | Hover changes size or margins instead of shadow/transform (layout shift) |
| EL008 | low | Animating box-shadow directly on many elements (jank); animate a pseudo-element's opacity instead |
| EL009 | low | Shadows on flat elements that aren't interactive or above anything (decoration noise) |
| EL010 | low | Shadow colour ignores the surface (grey shadows on tinted backgrounds look dirty) |

## Output

1. Level table: level, roles, shadow token, dark-mode surface token, z-index token
2. Shadow values (CSS and design tool) for light and dark
3. Interaction rules: hover, pressed, dragging, focus (focus is not elevation)
4. Z-index scale and stacking-context rules
5. Review findings, if auditing

## Additional Resources

| File | Content |
|------|---------|
| [shadow-recipes.md](references/shadow-recipes.md) | Layered shadow formula, ready-to-use 5-level CSS for light and dark, tinted colours, animation, forced colors |
| [layering-and-z-index.md](references/layering-and-z-index.md) | Z-index token scale, stacking contexts, portals, scrims, sticky elements, common bugs |
| [platform-elevation.md](references/platform-elevation.md) | Material 3 tonal elevation, Apple materials and shadows, Fluent shadow ramp, mapping your levels |
