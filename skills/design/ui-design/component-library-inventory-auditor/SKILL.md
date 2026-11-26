---
name: component-library-inventory-auditor
description: "Audit a product's UI components to find what exists, what is duplicated and what to consolidate: interface inventory of live screens by category (buttons, inputs, cards, modals, navigation, typography, colours, icons), code inventory of component definitions and usage counts, near-duplicate detection (Button, Btn, PrimaryButton, CustomButton), local components that shadow design-system ones, unused and one-off components, hard-coded colours, Figma library vs code parity, and a consolidation plan with canonical choices, variant mapping, codemods, deprecation and metrics. Ships inventory_scan.mjs (Node, no dependencies) that scans .jsx/.tsx/.js/.ts/.vue/.svelte sources and reports definitions, usages, duplicate groups, design-system shadows, unused components and colour hard-coding as a table, CSV or JSON. Use when starting or rescuing a design system, estimating UI debt, planning a component consolidation, or preparing a migration to a shared library."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Component Library Inventory Auditor

You can't consolidate what you haven't counted. Products that grew without a design system typically have several
buttons, modals and date pickers, each with its own bugs. The inventory makes that visible in two ways: a screenshot wall
that shows leadership the inconsistency, and usage data from code that shows where consolidation pays off first. This
skill runs both and turns them into a plan.

## Trigger Conditions

Activate this skill when the user:
- Starts a design system and needs to know what exists today
- Suspects duplicated or inconsistent components ("we have five modals")
- Plans a migration to a shared component library or a new major version
- Needs evidence of UI debt for a roadmap or business case

Name hygiene: `component-naming-convention-checker`. Tracking migration progress over time: `design-system-adoption-tracker`.
Token drift between design and code: `design-to-code-gap-auditor`.

## Workflow

```
1. SCOPE     -> products, platforms, repos, Figma libraries in scope; who owns each
2. VISUAL    -> screenshot inventory by category (references/inventory-method.md); group look-alikes on one board
3. CODE      -> node scripts/inventory_scan.mjs src/ --ds @acme/ui --csv > inventory.csv   (each repo)
4. FIGMA     -> list library components and detached instances; match names to code components
5. GROUP     -> merge visual and code results into component families with variants and usage counts
6. DECIDE    -> per family: canonical component, variants to keep, ones to drop (references/consolidation-playbook.md)
7. PRIORITISE-> usage x inconsistency x defect count; quick wins first (high usage, low variance)
8. REPORT    -> inventory summary, debt metrics, consolidation roadmap, success measures
```

## Reading the Scan

| Finding | Meaning | Typical action |
|---------|---------|----------------|
| IN001 near-duplicates | Same concept implemented several times | Pick a canonical one; map others to its variants |
| IN002 shadows design system | Local copy of a DS component | Migrate usages to the DS import; delete the local one |
| IN003 never used | Dead code | Delete (check dynamic imports and route files first) |
| IN004 hard-coded colours | Styles bypass tokens | Replace with tokens; feeds the token work |
| IN005 used once | One-off | Inline it, or fold it into a shared component's variant if the need recurs |

The scan uses static patterns: it finds JSX/TSX/Vue/Svelte components and `<Component>` usages, not components created
dynamically or rendered via config. Spot-check high-impact results before deleting anything.

## Scripts

```bash
node scripts/inventory_scan.mjs DIR [--ds @acme/ui] [--max-raw 5] [--include-tests] [--csv | --json]
```
`--ds` (repeatable) names the design-system package(s), so local copies and DS usage share are reported. Test and story
files are excluded from usage counts unless `--include-tests`. Route folders (`pages/`, `app/`, `routes/`, `views/`,
`screens/`) are treated as entry points, not unused components. Needs Node 18+; no packages.
Exit codes: 0 no warnings, 1 warnings (IN001, IN002, IN004), 2 bad arguments or no source files.

## Output

1. Inventory table per family: component, variants found, usages, repos, owner, canonical? (CSV for the spreadsheet)
2. Visual board summary: counts per category ("14 button styles, 6 modal implementations")
3. Debt metrics: duplicate families, DS usage share, hard-coded colour hotspots, unused components
4. Consolidation roadmap: ordered families with effort, impact and owner
5. Measures of success, tracked with design-system-adoption-tracker

## Additional Resources

| File | Content |
|------|---------|
| [inventory-method.md](references/inventory-method.md) | Interface inventory steps, categories, capture template, Figma library audit |
| [consolidation-playbook.md](references/consolidation-playbook.md) | Choosing the canonical component, variant mapping, prioritisation scoring, codemods, deprecation, reporting |
