---
name: design-system-adoption-tracker
description: "Measure and grow design system adoption with numbers leadership trusts: adoption defined per app or team as the share of UI elements coming from the design system (vs local components, third-party UI libraries and raw HTML the system replaces), token share vs hard-coded colours, design-system version lag, Figma library insertions and detach rate, snapshot history and trend, targets and OKRs, and an adoption plan (blockers interviews, migration support, codemods, lint rules, champions). Ships adoption_scan.mjs (Node, no dependencies) that scans a monorepo or several repos per folder and reports adoption %, change since a baseline snapshot, raw HTML elements the system replaces, token share, version per app, groups below a target and apps on an old major version, as a table, CSV for history, or JSON for the next baseline. Use when reporting design system adoption, setting adoption targets, finding lagging teams, or planning a migration push."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Design System Adoption Tracker

"Is the design system working?" has two parts: are teams using it, and is it getting more used over time? Opinions and
Figma screenshots don't answer either. A repeatable scan, the same definition every quarter, and a trend per team do.
This skill defines the metrics, runs the scan, compares it with the last snapshot, and turns the gaps into an adoption
plan.

## Trigger Conditions

Activate this skill when the user:
- Needs to report design system adoption or coverage to leadership
- Sets adoption targets or OKRs per team
- Wants to know which apps or teams lag and why
- Plans a migration push to a new major version or away from a third-party UI library

One-time inventory of duplicates: `component-library-inventory-auditor`. Process fixes when adoption stalls:
`design-system-governance-process-designer`.

## Workflow

```
1. DEFINE    -> adoption metric, groups (apps/teams), DS packages, what counts as replaceable raw HTML
2. BASELINE  -> node scripts/adoption_scan.mjs . --ds @acme/ui --depth 2 --json > adoption-2026-11.json
3. DESIGN    -> Figma library analytics: insertions, detaches per component and team
4. TARGETS   -> per group targets from the baseline (references/metrics-and-targets.md)
5. DIAGNOSE  -> for low groups: interview teams; raw HTML and third-party lists show what's missing (references/adoption-playbook.md)
6. ACT       -> missing components, codemods, lint rules, migration pairing, champions
7. RE-SCAN   -> monthly/quarterly with --baseline last.json; CSV rows appended to the history sheet
8. REPORT    -> trend per group, wins, blockers, next quarter's focus
```

## Metric Definitions

| Metric | Definition | Caveat |
|--------|------------|--------|
| Adoption | DS elements / (DS + local + third-party + replaceable raw HTML) | Counts instances, not screen area; a page of `<div>`s with one DS button reads high |
| Token share | `var(--...)` references / (tokens + hard-coded colours) | Only colours are counted as raw values |
| Version lag | Major versions behind the latest DS release | Ranges like `^2.4.0` count as major 2 |
| Detach rate (Figma) | Detaches / insertions per component | High detach = component doesn't fit real needs |
| Coverage (manual) | Screens built fully from the DS / screens audited | Sample-based; good for executive reporting |

Use the same definitions every time. Changing the definition resets the trend.

## Scan Findings (adoption_scan.mjs)

| Code | Severity | Meaning |
|------|----------|---------|
| AD001 | warn | Group below the `--min` adoption target |
| AD002 | info | Raw `<button>`, `<input>`, `<select>`, `<textarea>`, `<dialog>`, `<table>` that the DS replaces |
| AD003 | warn | Group on an older major version than `--latest` |

## Scripts

```bash
node scripts/adoption_scan.mjs ROOT --ds @acme/ui [--ds @acme/icons] [--depth 2] [--min 60] [--latest 3.2.0] [--baseline last.json] [--json | --csv]
```
Groups are the folders `--depth` levels under ROOT (`apps/web`, `apps/admin`). Tests, stories and build output are skipped.
Relative and alias imports (`./`, `../`, `@/`, `~/`, `src/`) count as local; other packages count as third-party.
`--json` output is the next run's `--baseline`. Needs Node 18+; no packages.
Exit codes: 0 all groups meet `--min` (or none set), 1 a group is below `--min`, 2 bad arguments or nothing to scan.

## Output

1. Adoption table per group with change since the baseline
2. Overall adoption, token share and version spread
3. Top replaceable raw HTML and third-party components per group (what to migrate first)
4. Targets per group for next quarter
5. Adoption plan: blockers, actions, owners

## Additional Resources

| File | Content |
|------|---------|
| [metrics-and-targets.md](references/metrics-and-targets.md) | Metric choices, Figma analytics, setting targets, reporting templates and pitfalls |
| [adoption-playbook.md](references/adoption-playbook.md) | Why teams don't adopt, diagnosis interviews, interventions, migration campaigns |
