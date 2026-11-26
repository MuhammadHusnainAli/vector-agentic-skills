---
name: responsive-breakpoint-layout-planner
description: "Plan responsive layouts the way senior product designers do: breakpoints set where the content breaks rather than at device widths, a column grid per range (columns, gutters, margins, max content width) with the column-width math, mobile-first min-width media queries vs container queries for components, fluid type and spacing with clamp() that still respects browser zoom, Material 3 window size classes, Bootstrap/Tailwind/Apple size-class mapping, layout patterns (column drop, layout shifter, off-canvas, list-detail, supporting pane), responsive tables, navigation and images (srcset, sizes, art direction), pointer and hover media features, and WCAG 1.4.10 reflow at 320 CSS px. Reviews breakpoint sets and CSS for overlapping or gapped ranges, device-named breakpoints, horizontal scroll and hover-only interactions. Use when defining breakpoints or a grid, designing a screen across sizes, converting a desktop design to mobile, or reviewing responsive behaviour before handoff."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Responsive Breakpoint & Layout Planner

Devices change every year, but content keeps the same limits: a line of text stops being readable past about 75
characters, a form field stops being usable when it's narrower than its value, and a sidebar stops helping when it squeezes
the main column. Put breakpoints where your content breaks, give each range a grid, and decide how every region changes
between ranges. This skill plans that system and reviews existing ones.

## Trigger Conditions

Activate this skill when the user:
- Defines breakpoints, a layout grid or max content width for a product
- Designs a screen for mobile, tablet and desktop, or converts a desktop design down
- Asks about container queries, fluid typography or clamp()
- Reviews responsive behaviour or a handoff that only shows one width

Dashboards: `dashboard-layout-designer`. Card grids: `card-component-designer`. Navigation changes across sizes:
`navigation-pattern-selector`.

## Workflow

```
1. CONTENT   -> list the regions (nav, main, aside, filters, detail) and each one's useful min / max width
2. RANGES    -> start narrow; widen until something breaks (line too long, empty space, cramped aside) = breakpoint
3. GRID      -> per range: columns, gutter, margin, max width; compute column width (references/grid-math.md)
4. BEHAVIOUR -> per region per range: stack, reflow, column drop, shift, off-canvas, hide (references/responsive-patterns.md)
5. SCOPE     -> page-level changes = media queries; component-level changes = container queries
6. FLUID     -> type and spacing scale with clamp() between the smallest and largest range (rem + vw, never vw alone)
7. CHECK     -> 320 CSS px reflow, 200% zoom, landscape phone, foldables, pointer: coarse; run the review below
8. HANDOFF   -> breakpoint table + grid table + behaviour matrix; frames at the edges of each range, not just the middle
```

## Rules That Hold Up

| Rule | Why |
|------|-----|
| Name ranges by size (compact, medium, expanded), never by device (tablet) | iPads in split view are phones; phones in landscape are tablets |
| Mobile-first `min-width` queries | Ranges never overlap and the small layout needs no overrides |
| Breakpoints in `em` for media queries | They follow the user's font size; px queries break when users enlarge text |
| Max content width (about 1200-1440px) or a measure of 60-75ch for text | Wide monitors make long lines and scattered layouts |
| Design both edges of every range | Most bugs live at 599px, not at 375px |
| Container queries for reusable components | A card in a sidebar and in the main column needs different layouts at the same viewport |
| clamp() with a rem term | `font-size: 4vw` ignores zoom and fails WCAG 1.4.4 |
| No horizontal scroll at 320 CSS px except data tables, maps, diagrams | WCAG 1.4.10 Reflow |
| Hover is an enhancement: `@media (hover: hover)` | Touch laptops and tablets exist |

## Review Checklist

Report as `CODE [severity] problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| RB001 | high | Content needs horizontal scrolling at 320 CSS px (WCAG 1.4.10), other than tables, maps or diagrams |
| RB002 | high | Text size set in vw only, or fixed heights that clip at 200% zoom (WCAG 1.4.4) |
| RB003 | high | Overlapping or gapped ranges (`max-width: 768px` with `min-width: 768px`; 767px to 768px gap at fractional widths) |
| RB004 | medium | Device-named breakpoints, or breakpoints that match no content change |
| RB005 | medium | Only one width designed per range; no frames at range edges |
| RB006 | medium | Line length over about 75 characters at the largest range (no max width or measure) |
| RB007 | medium | Component layout switches on viewport width where a container query is needed |
| RB008 | medium | Hover-only affordances with no `(hover: hover)` guard or touch equivalent |
| RB009 | low | More than 5 breakpoints (usually a sign of per-screen tweaks) |
| RB010 | low | px media queries instead of em |

## Output

1. Breakpoint table: range name, min width, columns, gutter, margin, column width at both edges, max width
2. Behaviour matrix: region x range with the pattern used
3. Fluid scale: clamp() values for type and spacing with the min/max viewport they span
4. CSS skeleton: custom properties, min-width em queries, container query setup
5. Review findings, if reviewing

## Additional Resources

| File | Content |
|------|---------|
| [grid-math.md](references/grid-math.md) | Column width formula, worked grids, clamp() derivation, em conversion |
| [breakpoint-systems.md](references/breakpoint-systems.md) | Material 3 window size classes, Apple size classes, Bootstrap, Tailwind, choosing your own |
| [responsive-patterns.md](references/responsive-patterns.md) | Layout patterns, tables, navigation, images, forms, foldables, container query recipes |
