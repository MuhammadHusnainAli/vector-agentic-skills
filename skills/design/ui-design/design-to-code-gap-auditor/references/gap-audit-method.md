# Gap Audit Method

## Layers of drift

| Layer | Question | How to measure |
|-------|----------|----------------|
| Tokens | Are values coming from tokens? | `token_drift.mjs` (colours); spacing audit for spacing; CSS stats for font sizes, radii, shadows |
| Components | Do the same components exist on both sides with the same API? | Parity table (component-parity.md) |
| Variants and props | Do variants and values match? | Parity table per component |
| States | Are all specified states built? | Spec/state matrix vs Storybook stories |
| Behaviour | Does it behave as specified (focus, keyboard, motion)? | Spot checks on key components |
| Patterns | Are screens built with the documented patterns (forms, empty states)? | Sample of top screens |
| Content | Do labels and messages follow the content guidelines? | Sample review |

Start with tokens and components: they're measurable and fix many screens at once.

## Sampling screens

For layers that can't be scanned, sample: the top 10-20 screens by traffic plus the newest 5 features. Score each screen
on a short checklist (tokens, components, states, a11y basics) to get a coverage percentage per product area.

## Root causes

| Cause | Signal | Fix the cause |
|-------|--------|---------------|
| Missing token | Same off-palette value used many times (TD003 with high counts) | Add a semantic token |
| Unclear spec | Near-misses and inconsistent spacing in one feature | Better handoff (tokens visible in Dev Mode) |
| Old fork / legacy code | Drift concentrated in older folders | Migration project |
| Hotfix pressure | Scattered single uses | Lint rules + review checklist |
| Design-only variants | Figma variants never built | Build or remove; parity check in the release process |
| Code-only props | Engineers added options design never saw | Contribution process; designers review component PRs |
| Third-party components | Styles from a library theme | Theme the library with tokens, or replace |

## Reporting

```
Design-to-code gap - web app - 2026-11
Token share (colours): 41% via tokens (baseline)
Raw colours: 312 uses; 188 exact token matches, 64 near-misses, 60 off-palette (14 distinct values)
Components: 23 in Figma, 27 in code; 4 code-only, 2 Figma-only; 9 with variant mismatches
States: 31% of specified states missing in Storybook
Top causes: no danger/warning surface tokens (40 off-palette uses), legacy settings module (35% of raw values)
Plan: add 4 tokens; codemod exact matches; migrate settings module in Q1; stylelint rule in CI
```
