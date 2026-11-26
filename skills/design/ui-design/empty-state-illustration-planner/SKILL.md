---
name: empty-state-illustration-planner
description: "Plan empty states that move people forward instead of decorating a blank screen: inventory every place content can be missing and classify each (first use, no data yet, user cleared, no search or filter results, error or failed to load, offline, no permission, feature locked by plan), then write the state with a headline, one-sentence explanation, one primary action and an optional help link, decide whether it earns an illustration and at what size, and keep a consistent illustration system (style, palette, sizes for full-page, panel and inline, dark-mode variants, no embedded text, accessible as decorative). Includes copy formulas per type, starter content and sample data patterns, and an illustration brief template. Reviews empty states for dead ends, blaming or jokey error copy, illustrated errors, no-results confused with no-data, missing filter resets and text baked into images. Use when designing or auditing empty, zero, no-results, error or onboarding states."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Empty State & Illustration Planner

Empty states are where new users decide whether a product is worth their time, and where returning users get stuck after
a search or filter goes wrong. Most products have dozens, designed one at a time or never: a blank table, "No data", a cute
illustration with nothing to click. This skill inventories them all, gives each one the right job and wording, and plans a
small illustration system so they look like they belong together.

## Trigger Conditions

Activate this skill when the user:
- Designs empty, zero-data, first-run, no-results, error or permission states
- Plans illustrations for empty states or wants a consistent illustration style
- Reviews an onboarding flow where new accounts start empty
- Has support tickets or drop-off from users who "don't know what to do next"

Forms and validation errors: [form-layout-designer](../form-layout-designer/SKILL.md). Dashboard widget states: [dashboard-layout-designer](../dashboard-layout-designer/SKILL.md).

## Workflow

```
1. INVENTORY -> every list, table, feed, search, filter, dashboard widget, inbox, folder, chart that can be empty
2. CLASSIFY  -> type per instance (references/empty-state-types.md); one container can have several types
3. JOB       -> what the user should do next in each; if nothing, say so and stay quiet
4. WRITE     -> headline + explanation + primary action (+ help link) (references/copy-patterns.md)
5. VISUAL    -> illustration, icon or nothing, by type and space (references/illustration-system.md)
6. STARTER   -> for first use: templates, sample data, import, invite, guided first action
7. SPEC      -> state per component in the design system (empty slot in table, list, card grid, chart)
8. REVIEW    -> checklist below; test with a fresh account and with filters that return nothing
```

## Which Visual

| Type | Visual |
|------|--------|
| First use (product, feature or space) | Illustration (medium or large) earns its place: sets tone, explains the concept |
| No data yet (waiting for activity) | Small illustration or icon |
| User cleared everything (inbox zero) | Small celebratory illustration, optional |
| No search or filter results | Icon or nothing; the fix (clear filters, check spelling) matters more |
| Error / failed to load | Icon (warning) and plain text; no cute illustration |
| No permission / locked | Icon (lock) and who to ask, or the upgrade path |
| Small containers (widgets, side panels, table cells) | Text only, or a small icon |

## Review Checklist

Report as `CODE [severity] location: problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| ES001 | high | Dead end: no action or next step where one exists |
| ES002 | high | No results and no data look the same (users think their data is gone) |
| ES003 | high | Filtered-to-empty view with no way to clear or adjust filters |
| ES004 | high | Error shown as an empty state (or empty state shown on error): "No projects" when loading failed |
| ES005 | medium | Copy that blames the user, jokes about an error, or uses jargon ("No entities found") |
| ES006 | medium | Illustration on an error or permission state; illustrations so large they push the action below the fold |
| ES007 | medium | Text baked into an illustration (can't translate, not accessible) |
| ES008 | medium | Inconsistent illustration styles across states |
| ES009 | medium | More than one primary action, or the action isn't the most likely next step |
| ES010 | low | Decorative illustration announced by screen readers (missing `alt=""` / `aria-hidden`) |
| ES011 | low | No dark-mode variant for illustrations with light backgrounds |
| ES012 | low | First-use state without starter content (template, sample, import) where it would help |

## Output

1. Inventory table: location, container, type, trigger condition, job, action, visual
2. Copy for each state (headline, body, action label, help link)
3. Illustration plan: which states get which illustration, sizes, brief for the illustrator
4. Component spec additions (empty slots in table, list, grid, chart)
5. Review findings, if auditing

## Additional Resources

| File | Content |
|------|---------|
| [empty-state-types.md](references/empty-state-types.md) | Each type: when it occurs, goal, structure, action, example, pitfalls |
| [copy-patterns.md](references/copy-patterns.md) | Headline and body formulas, action labels, tone per type, before/after examples |
| [illustration-system.md](references/illustration-system.md) | Style rules, sizes, palette, dark mode, production, accessibility, brief template |
