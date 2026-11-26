# Releases, Deprecation and Health Metrics

## Semantic versioning for a design system

| Change | Version |
|--------|---------|
| Bug fix, a11y fix with no API change, docs | Patch (2.3.1) |
| New component, new prop or variant, new token, deprecation notice | Minor (2.4.0) |
| Removed or renamed component/prop/token, changed default behaviour, visual change that breaks layouts | Major (3.0.0) |

Visual changes need judgement: a colour tweak inside the same role is minor; changing component dimensions that can
break product layouts is major (or minor behind an opt-in flag until the next major).

Figma libraries follow the same versioning in their release notes, so designers know which code version matches.

## Cadence

| Release type | Cadence |
|--------------|---------|
| Patch | As needed (weekly batch is common) |
| Minor | Every 2-4 weeks |
| Major | At most 1-2 per year, announced at least a quarter ahead |

## Deprecation timeline

1. **Announce** (minor release): mark deprecated in code (console warning in development, `@deprecated` JSDoc, lint
   rule), docs banner with replacement and removal version, Figma component moved to a "Deprecated" page.
2. **Support migration**: migration guide, codemod where mechanical, office hours, usage report per team
   (component-library-inventory-auditor / design-system-adoption-tracker).
3. **Remove** in the next major, not earlier than the announced date, once usage is near zero or teams have committed
   dates.

Deprecation notice template:
```
Deprecated in 2.4.0, removed in 3.0.0 (planned for 2027-Q2).
Use <Dialog> instead. Migration: <link>. Codemod: npx @acme/ui-codemods modal-to-dialog
```

## Release notes

- Grouped by Added / Changed / Deprecated / Removed / Fixed.
- Lead with what product teams must do ("Action needed: ...").
- Screenshots for visual changes; before/after for anything that moves layouts.
- Link to the PR/issue and the docs page.

## Health metrics

| Area | Metric | Source |
|------|--------|--------|
| Adoption | Share of UI built from DS components per product; DS version lag | Code scans, package manifests |
| Design adoption | Library insertions vs detaches in Figma | Figma library analytics |
| Speed | Median time from request to release, by tier | Issue tracker |
| Contribution | Contributions from outside the core team per quarter | Repo |
| Quality | Open bugs and accessibility defects in DS components | Tracker |
| Satisfaction | Quarterly survey (ease of use, trust, docs quality); support questions per week | Survey, support channel |

Review quarterly; when one metric degrades (e.g. request time), change the process step that causes it.
