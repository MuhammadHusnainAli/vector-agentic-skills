---
name: ui-spacing-scale-consistency-checker
description: "Define a spacing scale and enforce it across design and code: base unit (4 or 8px), linear vs geometric steps, step names and tokens (space.1-12, inset/stack/inline roles), component padding vs layout spacing, proximity and grouping (related items closer than unrelated), density modes, the relation to type line heights and icon sizes, Figma auto layout and variables, and migrating off-scale values. Ships spacing_audit.mjs (Node, no dependencies) that extracts margin, padding, gap and inset values from CSS/SCSS/LESS, JSX/JS style objects (unitless numbers as px), inline styles and Tailwind arbitrary classes like p-[18px], converts rem, and reports every value against the scale with use counts, off-scale values with the nearest steps and file:line locations, on-scale share, and token usage. Use when spacing looks uneven, when defining or tightening a spacing system, before a design-system migration, or when reviewing a design or codebase for spacing consistency."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# UI Spacing Scale Consistency Checker

Uneven spacing is the main reason a UI looks "slightly off" even when nobody can say why. Usually the cause is many
almost-equal values (10, 12, 14, 15, 16px) chosen one screen at a time. A spacing scale replaces those per-screen choices
with a small set of steps, and the way space is grouped makes the structure readable: related things closer, unrelated
things further apart. This skill defines the scale and finds the values that break it, in design files and in code.

## Trigger Conditions

Activate this skill when the user:
- Says a UI looks inconsistent, cramped or "off", or that spacing differs between screens
- Defines a spacing scale or spacing tokens
- Audits a codebase or design file for spacing values before a design-system migration
- Designs density modes (comfortable / compact)

Tokens in general: `design-token-architecture-builder`. Redlines for handoff: `redline-annotation-writer`. Grid and
breakpoints: `responsive-breakpoint-layout-planner`.

## Workflow

```
1. MEASURE   -> node scripts/spacing_audit.mjs src/ --scale 0,4,8,12,16,24,32,48,64   (what's used today)
2. SCALE     -> choose base and steps from the histogram and the product's density (references/spacing-scales.md)
3. ROLES     -> inset (padding), stack (vertical gaps), inline (horizontal gaps), layout (sections)
4. TOKENS    -> space.* steps + role aliases; Figma number variables with the same names
5. RULES     -> proximity: within-group < between-group < between-section; one step jump at least between levels
6. MAP       -> each off-scale value to a step (nearest, or by role); codemod/replace (references/audit-and-migration.md)
7. ENFORCE   -> lint rules (stylelint), Tailwind config locked to the scale, Figma variables scoped to gap/padding
8. RE-AUDIT  -> run the scan again with --min 95 in CI
```

## Principles

| Principle | Practice |
|-----------|----------|
| Small set of steps | 8-12 steps cover nearly every need; more means steps too close to tell apart |
| Steps must be distinguishable | Adjacent steps differ by at least 4px at small sizes and grow at larger sizes |
| Proximity shows structure | Label-to-field 4-8, field-to-field 16-24, group-to-group 32-48 |
| Inside <= outside | A container's padding is no larger than the space between it and its neighbours |
| Same relationship, same step | All card paddings use one step; all form field gaps use one step |
| Optical, then scale | Adjust for optical balance (icon with text) inside components, not by inventing new layout steps |

## Audit Codes (spacing_audit.mjs)

| Code | Severity | Meaning |
|------|----------|---------|
| SP001 | warn | Off-scale value with the nearest step(s) and file:line locations |
| SP002 | info | Raw on-scale values that could be tokens, and the count of `var(--...)` references |

## Scripts

```bash
node scripts/spacing_audit.mjs PATH [PATH...] [--scale 0,4,8,12,16,24,32,48,64 | --base 4] [--rem 16] [--min 90] [--json]
```
Default scale: 0 2 4 8 12 16 20 24 32 40 48 64 80 96 128. `--base 4` accepts any multiple of 4 instead of a fixed list.
Reads CSS/SCSS/LESS, `<style>` blocks and `style="..."` in markup, JSX/JS style objects (unitless numbers are px) and
Tailwind arbitrary values (`p-[18px]`). Standard Tailwind classes (`p-4`) are on Tailwind's own scale and not counted.
Ignores `0`, `auto`, `%`, `em`, `calc()`. Needs Node 18+; no packages.
Exit codes: 0 all on scale (or share >= `--min`), 1 otherwise, 2 bad arguments or nothing found.

## Output

1. Current state: histogram of values, on-scale share, worst off-scale values with locations
2. The scale: steps, names, tokens, role aliases, density variants
3. Mapping table: off-scale value -> step, with the reason where it's not simply the nearest
4. Enforcement: lint config, Tailwind theme, Figma variables
5. Review findings for design files (spacing between groups, inside vs outside, inconsistent component padding)

## Additional Resources

| File | Content |
|------|---------|
| [spacing-scales.md](references/spacing-scales.md) | Base units, linear vs geometric scales, example scales, roles, density, relation to type and icons |
| [audit-and-migration.md](references/audit-and-migration.md) | Running audits in code and Figma, mapping decisions, codemods, stylelint and Tailwind enforcement |
