---
name: button-state-variant-designer
description: "Design a button system that holds up across a product: emphasis hierarchy (primary, secondary, tertiary, danger, link-style) with one primary per region, sizes on the spacing scale with 24px / 44pt / 48dp targets, the full state model (default, hover, pressed, focus-visible, disabled, loading, toggled) as semantic tokens or Material-style state layers, contrast per state (text 4.5:1, boundaries and focus indicators 3:1, WCAG 1.4.3, 1.4.11, 2.4.7, 2.4.11, 2.4.13), focus rings that work on any background, disabled vs aria-disabled, loading without layout shift, destructive actions with confirm or undo, button vs link, icon placement, label writing and button-group order per platform. Reviews button sets and CSS for missing focus states, outline:none, opacity-only disabled, hover-only affordances, low-contrast states, small targets and competing primaries. Use when designing or auditing buttons, defining button tokens, or fixing inconsistent buttons across a product."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Button State & Variant Designer

Buttons are the most-used component and the most inconsistent one. Products end up with 30 button styles because nobody
decided the hierarchy, the states or the tokens up front. This skill designs the system once: which variants exist and
why, every state as a token, contrast checked state by state, and the behaviour rules (loading, disabled, destructive)
that screenshots don't show.

## Trigger Conditions

Activate this skill when the user:
- Designs buttons or a button component for a product or design system
- Asks about hover, pressed, focus, disabled or loading states, or state colours for dark mode
- Has too many button styles, competing primary buttons, or inconsistent states
- Needs to check button contrast or focus visibility

Full component spec (API, keyboard): `ui-component-spec-writer`. Tokens for every component: `design-token-architecture-builder`.
Dark palette: `dark-mode-palette-designer`.

## Workflow

```
1. INVENTORY -> list every action type in the product: commit, cancel, destructive, navigate, toggle, inline
2. HIERARCHY -> map them to 3-5 variants (references/variant-hierarchy.md); kill the rest
3. SIZES     -> sm / md / lg on the spacing scale; check targets (24px floor, 44pt / 48dp touch)
4. STATES    -> for each variant: default, hover, pressed, focus-visible, disabled, loading (+ selected for toggles)
5. TOKENS    -> semantic tokens per variant x state, or base colour + state layers (references/state-tokens.md)
6. CONTRAST  -> check every cell in light and dark (references/contrast-for-states.md)
7. BEHAVIOUR -> loading, disabled, destructive, groups, labels (references/variant-hierarchy.md)
8. REVIEW    -> run the checklist below; fix every high
```

## Non-Negotiables

| Rule | Detail |
|------|--------|
| One primary per region | A dialog, form or card has one primary action. Two primaries means nobody knows what's next |
| Focus is always visible | `:focus-visible` ring with 3:1 against the background. Never `outline: none` without a replacement |
| States differ by more than colour hue | Pressed and selected also change shade or show a border or icon. Colour-blind and forced-colors users need it |
| Label states the action | Verb + object ("Save draft"), sentence case, same verb as the result ("Delete" -> "Deleted") |
| Loading keeps the width | Spinner replaces or joins the label inside the same box. Repeat clicks are blocked |
| Disabled is rare | Prefer enabled + validation on click. If disabled, the reason is visible nearby |
| Buttons act, links go | Navigation to a URL is a link even if it looks like a button. Actions are `<button>` |

## Review Checklist

Report as `CODE [severity] problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| BS001 | high | No visible focus state, or `outline: none` / `0` with no replacement (WCAG 2.4.7) |
| BS002 | high | Label text below 4.5:1 against the container in any enabled state (WCAG 1.4.3) |
| BS003 | high | Focus indicator below 3:1 against the adjacent colour (WCAG 1.4.11; 2.4.13 at AAA) |
| BS004 | high | Target under 24x24 CSS px with no spacing exception (WCAG 2.5.8); under 44pt / 48dp in a touch product |
| BS005 | medium | More than one primary button in a region |
| BS006 | medium | Boundary-only variant (outline) whose border is below 3:1 when the border is the only thing that shows it's a button |
| BS007 | medium | Disabled shown by opacity on the whole button (hover still fires, text unreadable) with no reason given |
| BS008 | medium | Hover is the only feedback (no pressed state) or hover changes layout (border width, font weight) |
| BS009 | medium | Loading changes the width, or allows repeat submits |
| BS010 | medium | Destructive action with neither confirmation nor undo |
| BS011 | low | More than 5 variants, or variants named by colour (blue, grey) instead of role |
| BS012 | low | Vague labels: OK, Submit, Click here, Yes/No without the action |

## Output

1. Variant table: variant, role, when to use, when not to use
2. Size table: height, padding, type token, icon size, min target
3. Token matrix: variant x state -> container / label / border / focus tokens, with contrast in light and dark
4. Behaviour rules: loading, disabled, destructive, groups and order, labels
5. Review findings, if auditing

## Additional Resources

| File | Content |
|------|---------|
| [variant-hierarchy.md](references/variant-hierarchy.md) | Variants and their jobs, sizes, groups and order per platform, labels, destructive, loading, disabled, button vs link |
| [state-tokens.md](references/state-tokens.md) | Token naming per variant x state, state layers (Material 3 opacities), worked token matrix, CSS |
| [contrast-for-states.md](references/contrast-for-states.md) | WCAG formulas, which criterion applies to which part, focus ring techniques, worked contrast values |
