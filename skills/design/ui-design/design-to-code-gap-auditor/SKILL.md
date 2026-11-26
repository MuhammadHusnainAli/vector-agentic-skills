---
name: design-to-code-gap-auditor
description: "Audit how far the built product has drifted from the design system and design files, then plan how to close the gap: token drift (raw colours in code that equal a token, nearly match one or are off-palette; unused tokens; var() references to undeclared tokens), component parity (Figma variants and properties vs code props and values, components that exist on one side only), state coverage, behaviour, content and responsive gaps, and the root causes behind them (missing tokens, unclear specs, old forks, no lint rules). Ships token_drift.mjs (Node, no dependencies) that reads DTCG JSON, flat JSON or CSS-variable token files with aliases and scans CSS, SCSS, JSX/TSX, Vue, Svelte and HTML for hex, rgb() and hsl() colours, matching them to tokens with perceptual OKLab deltaE and preferring semantic aliases in its fixes. Use when the product no longer matches the design system, before a redesign or token migration, or when setting up guardrails against drift."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Design-to-Code Gap Auditor

Every product drifts from its design system. A hex value pasted during a hotfix, a component variant that only exists in
Figma, a prop with a different name in code, a state nobody built. Each gap is small, but together they're why the
product doesn't look like the design system docs, and why every redesign costs more than it should. This skill measures
the gap across tokens, components and states, finds the root causes, and plans the fixes and guardrails.

## Trigger Conditions

Activate this skill when the user:
- Says the product no longer matches the design system or the Figma files
- Plans a token migration, theme change, dark mode or redesign
- Wants to know which hard-coded values to replace and with which tokens
- Needs guardrails (lint rules, CI checks) to stop drift

One-feature QA against its design: `design-qa-visual-diff-checker`. Duplicate components: `component-library-inventory-auditor`.
Naming parity: `component-naming-convention-checker`. Token architecture: `design-token-architecture-builder`.

## Workflow

```
1. TOKENS    -> node scripts/token_drift.mjs tokens.json src/ --ignore tokens.css
2. TRIAGE    -> exact matches = mechanical replace; near-misses = confirm intent; off-palette = new token or design fix
3. COMPONENTS-> parity table: Figma component/properties vs code props/values (references/component-parity.md)
4. STATES    -> states in the spec vs states in code and stories
5. CAUSES    -> why each cluster of drift happened (references/gap-audit-method.md)
6. PLAN      -> fix order by visibility and effort; codemods; owners (references/closing-and-preventing-drift.md)
7. GUARD     -> lint rules, CI checks, Code Connect, review checklist
8. TRACK     -> re-run the scan monthly; report token share and parity gaps closed
```

## Drift Codes (token_drift.mjs)

| Code | Severity | Meaning | Usual fix |
|------|----------|---------|-----------|
| TD001 | warn | Raw colour equals a token | Replace with the semantic token (listed first) |
| TD002 | warn | Raw colour within `--delta` of a token | Almost always meant the token; confirm, then replace |
| TD003 | warn | Off-palette colour | Add a token if the need is real; otherwise map to the nearest role |
| TD004 | info | Token never used in code | Remove, or it's used only by design (check Figma) |
| TD005 | info | `var(--x)` that matches no token | Typo, a local variable, or a token missing from the source of truth |

## Scripts

```bash
node scripts/token_drift.mjs TOKENS CODE_DIR [more dirs] [--prefix ds] [--delta 3] [--ignore tokens.css] [--json]
```
TOKENS is DTCG JSON (aliases resolved), flat JSON (`{"color.blue.600": "#2563eb"}`) or a CSS file of custom properties.
CSS variable names are token paths joined with `-` (add `--prefix ds` for `--ds-color-...`). `--delta` is the OKLab
deltaE x100 below which a colour counts as a near-miss (about 2 is the just-noticeable difference; default 3).
`--ignore` skips files whose path contains the text (e.g. the generated tokens file). Needs Node 18+; no packages.
Exit codes: 0 no warnings, 1 warnings, 2 bad arguments or unreadable tokens.

## Output

1. Gap summary: token share (token references vs raw colours), counts per drift code, parity gaps, missing states
2. Replacement table: raw value -> token, with locations (from the script)
3. Parity table per component with status
4. Root causes and the plan (fix order, owners, codemods)
5. Guardrails to add

## Additional Resources

| File | Content |
|------|---------|
| [gap-audit-method.md](references/gap-audit-method.md) | Layers of drift, how to measure each, root-cause categories, reporting |
| [component-parity.md](references/component-parity.md) | Building the Figma-vs-code parity table, states coverage, Code Connect |
| [closing-and-preventing-drift.md](references/closing-and-preventing-drift.md) | Fix order, codemods, lint and CI guardrails, review checklist, tracking |
