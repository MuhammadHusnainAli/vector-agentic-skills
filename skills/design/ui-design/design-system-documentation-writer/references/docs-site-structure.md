# Docs Site Structure

## Information architecture

| Section | Contents | Main readers |
|---------|----------|--------------|
| Get started | What the system is, install for design (Figma libraries) and code (packages), support channels | Everyone new |
| Foundations | Colour, typography, spacing, layout and grid, elevation, motion, iconography, illustration | Designers, engineers |
| Components | One page per component, A-Z and by category | Designers, engineers |
| Patterns | Forms, errors, empty states, navigation, onboarding, search, data tables, notifications | Designers, PMs |
| Content | Voice and tone, grammar, word list, capitalisation, numbers and dates, inclusive language | Writers, designers |
| Accessibility | Standards (WCAG 2.2 AA), testing guide, per-component notes index | Everyone |
| Resources | Figma libraries, icon set, templates, tokens download, code sandbox | Designers, engineers |
| What's new | Release notes, roadmap, deprecations | Everyone |
| Contribute | How to propose, contribution process, office hours | Contributors |

## Navigation

- Left sidebar by section; component list searchable and filterable by category and status.
- On-page table of contents for long pages.
- Search across components, tokens and content guidelines (synonyms: "modal" finds Dialog).
- Each component page links to Figma and code, and Figma component descriptions link back to the page.

## Status labels

| Status | Meaning | Guarantee |
|--------|---------|-----------|
| Draft | Being designed; don't use in production | None |
| Beta | Usable; API may change in minor releases | Feedback wanted |
| Stable | Production-ready | Breaking changes only in majors |
| Deprecated | Being removed; replacement named | Removal version and date stated |

## Versioning and changelog

- Docs versioned with the package; a version switcher for the current and previous major.
- Changelog entries: version, date, type (added / changed / deprecated / removed / fixed), migration notes for anything
  breaking.
- "Last updated" on every page.

## Keeping docs in sync

| Risk | Control |
|------|---------|
| Props table drifts from code | Generate it from the component's types (react-docgen, Storybook ArgTypes) |
| Examples break | Render examples from stories; run them in CI |
| Figma and docs disagree | Component checklist in the release process: Figma updated, docs updated, changelog written |
| Nobody owns a page | Owner field per page; review dates; stale-page report |
| Readers can't give feedback | "Was this helpful?" + link to the issue tracker on every page |
