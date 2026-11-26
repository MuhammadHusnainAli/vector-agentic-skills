# QA Reporting

## Ticket template

```
Title: [Off] Order card padding is 12px instead of space.4 (16px)
Component: OrderCard (used on S01, S05)
Severity: Off
Environment: staging build 2026-11-26, Chrome 131, 390 x 844, DPR 1
Expected: padding var(--space-4) = 16px (Figma: <link to frame>)
Actual: padding 12px (computed), hard-coded in OrderCard.module.css line 14
Evidence: design.png | build.png | diff.png (region 1: x=16 y=88 343x112)
Fix: use var(--space-4)
```

## Grouping by root cause

One wrong token used in a shared component causes the same difference on many screens. File one ticket per root cause,
list affected screens, and fix it once. A QA report with 40 screen-level bugs that are really 6 component issues wastes
engineering time and credibility.

## Triage with engineering

- Walk through Broken and Wrong items together; agree fix or accept.
- Off and Nit items: batch into one polish ticket per component, or accept with a note.
- Record accepted differences (and why) so the next QA pass doesn't re-raise them.

## Release recommendation

| Situation | Recommendation |
|-----------|----------------|
| Any Broken | Fix before release |
| Wrong items on primary paths | Fix before release unless agreed otherwise |
| Off / Nit only | Ship; schedule polish |

## Visual regression testing

For stable screens and design-system components:
- Capture baselines with Playwright (or Storybook + a visual testing service) at fixed viewports and themes.
- Compare on every pull request; differences need approval (intended change) or a fix.
- Keep tolerance low for components and higher for pages with text.
- Freeze data and time; disable animations; wait for fonts.
- Review new baselines like code: a careless "accept all" defeats the purpose.
