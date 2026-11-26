---
name: design-token-architecture-builder
description: "Design and audit a design token architecture that scales across themes, brands and platforms: three tiers (primitive -> semantic -> component) and when the component tier is worth it, naming taxonomy (namespace, category, concept, property, variant, state, scale), W3C Design Tokens Format (DTCG 2025.10) structure with $type, $value, aliases and groups, modes for light/dark/high-contrast/density, multi-brand setups, Figma variable collections and modes that mirror the code tokens, and a build pipeline with Style Dictionary v4 that keeps aliases as CSS var() references. Ships token_lint.mjs (Node, no dependencies) that lints DTCG JSON for broken aliases, alias cycles, invalid colour/dimension/duration values, type mismatches, component tokens that skip the semantic tier, hard-coded values in semantic tokens, and tokens missing from one mode file. Use when creating tokens for a design system, restructuring a messy token set, adding dark mode or a second brand, or connecting Figma variables to code."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Design Token Architecture Builder

Tokens are the API between design decisions and code. A good architecture lets you change a brand colour in one place,
ship dark mode without touching components, and have Figma and code agree on names. A bad one is 2,000 colour tokens
named after hex values, with components reaching into the raw palette. This skill designs the tiers, names and modes, and
lints the JSON so broken aliases and tier leaks show up before they ship.

## Trigger Conditions

Activate this skill when the user:
- Creates design tokens or Figma variables for a design system
- Restructures a token set (too many tokens, inconsistent names, components using raw palette values)
- Adds dark mode, high contrast, density modes or a second brand
- Connects Figma variables / Tokens Studio to code via Style Dictionary or a similar build
- Has token JSON to review

Finding hard-coded values in code that should be tokens: `design-to-code-gap-auditor`. Dark palette values:
`dark-mode-palette-designer`. Spacing scale: `ui-spacing-scale-consistency-checker`.

## Workflow

```
1. INVENTORY  -> collect the values in use (colours, spacing, radii, type, shadows, motion); cluster near-duplicates
2. PRIMITIVES -> a ramp per colour (50-950), a spacing scale, type scale, radii, durations: raw values only
3. SEMANTICS  -> name by purpose: color.text.default, color.surface.raised, color.action.primary.bg, space.inset.md
4. MODES      -> semantic tokens get a value per mode (light/dark/HC); primitives never change per mode
5. COMPONENTS -> only where a component needs to diverge from semantics or be themed independently
6. NAMING     -> apply the taxonomy in references/tiers-and-naming.md; same names in Figma and code
7. LINT       -> node scripts/token_lint.mjs core.json semantic-light.json components.json --modes light.json dark.json
8. BUILD      -> Style Dictionary with outputReferences so var(--component) -> var(--semantic) -> value
9. GOVERN     -> change process: adding, renaming and deprecating tokens (references/build-and-figma.md)
```

## Architecture Rules

| Rule | Why |
|------|-----|
| Components use semantic (or component) tokens, never primitives | Themes and dark mode work by remapping semantics; a component on `blue.600` can't be themed |
| Primitives hold raw values; semantics alias primitives | One source of truth per value; renaming a brand colour touches one token |
| Name by purpose, not by appearance | `color.text.danger`, not `color.red-text`; the value can change, the purpose doesn't |
| Modes change semantic values only | The same semantic token name in every mode file; missing keys break themes |
| Component tier is optional | Add it for components with independent theming needs (buttons, inputs) or for multi-brand. Not for every component by default |
| No values in token names | `space.16` breaks when the value becomes 18; `space.4` (step) or `space.inset.md` (purpose) survive |
| One scale per concern | Two spacing scales or three grey ramps is the most common source of inconsistency |

## Lint Codes (token_lint.mjs)

| Code | Severity | Problem |
|------|----------|---------|
| TK001 | error | Alias points to a token that doesn't exist |
| TK002 | error | Alias cycle |
| TK003 | error | Node with both $value and children, or a leaf without $value |
| TK004 | error | Invalid value for its $type (colour, dimension, duration, fontWeight, number, cubicBezier) |
| TK005 | warn | Alias resolves to a different $type |
| TK006 | warn | Component token references a primitive directly (skips the semantic tier) |
| TK007 | warn | Hard-coded value in the semantic or component tier |
| TK008 | warn | Primitive aliases a semantic or component token |
| TK009 | warn | Invalid name (starts with $, contains { } or .) |
| TK010 | warn | Token missing from one mode file |
| TK011 | info | Primitive never referenced |

## Scripts

```bash
node scripts/token_lint.mjs core.json light.json components.json [--modes light.json dark.json] [--tiers "primitive=ref;semantic=sys;component=cmp"] [--json] [--strict]
```
Files are merged in order (later override earlier). Tiers come from the first path segment; defaults recognise
`core/base/primitive/ref/palette`, `semantic/sys/system/alias/theme`, `component/comp`. Needs Node 18+; no packages.
Exit codes: 0 no errors, 1 errors (or warnings with `--strict`), 2 bad arguments or unreadable JSON.

## Output

1. Tier diagram and the rule for what goes in each tier
2. Naming taxonomy with examples for colour, space, type, radius, elevation, motion
3. Token JSON skeleton (DTCG) for primitives, semantics per mode, and components
4. Figma variable collections and modes that mirror it
5. Build config and the change/deprecation process
6. Lint findings, if auditing

## Additional Resources

| File | Content |
|------|---------|
| [tiers-and-naming.md](references/tiers-and-naming.md) | The three tiers, naming taxonomy, semantic colour roles, examples per category, anti-patterns |
| [dtcg-format.md](references/dtcg-format.md) | DTCG 2025.10 essentials: $type/$value, groups, aliases, composite types, modes and multi-brand file layouts |
| [build-and-figma.md](references/build-and-figma.md) | Style Dictionary v4 config, CSS output with references, Figma variable collections, governance |
