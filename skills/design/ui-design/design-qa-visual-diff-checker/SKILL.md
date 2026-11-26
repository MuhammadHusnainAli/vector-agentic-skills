---
name: design-qa-visual-diff-checker
description: "Run design QA on built UI against the approved design: capture comparable screenshots (same viewport, device pixel ratio, fonts, data and state, animations off), compare them pixel by pixel, then triage differences by severity (broken, wrong, off, nit) with fixes engineers can act on. Covers the checks a screenshot can't show (hover, focus, motion, responsive ranges, long content, keyboard, screen readers, dark mode), computed-style checks in browser DevTools against tokens, and when to accept differences (platform rendering, real data). Ships png_diff.mjs (Node, no dependencies) that decodes 8-bit PNGs (greyscale, RGB, palette, alpha), reports mismatched pixels with a tolerance, groups differences into regions with bounding boxes and the average colour in each image, ignores anti-aliasing noise, flags size mismatches with a device-pixel-ratio hint, and writes a diff image. Use when reviewing an implementation before release, writing design QA bugs, or setting up visual regression checks."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Design QA Visual Diff Checker

Design QA catches the gap between what was designed and what shipped: the 12px gap that became 16, the button colour
from the wrong token, the missing focus ring, the truncation that never got built. Eyeballing two windows side by side
misses small offsets and colour shifts, and it doesn't scale to 30 screens. This skill sets up comparable captures, diffs
them precisely, checks what screenshots can't show, and writes findings engineers can fix without a meeting.

## Trigger Conditions

Activate this skill when the user:
- Reviews a built feature against the design before release
- Writes design QA bugs or a QA report
- Compares a screenshot with a Figma export, or two builds
- Sets up visual regression testing for a design system or key screens

Handoff that prevents most QA issues: [design-handoff-spec-generator](../design-handoff-spec-generator/SKILL.md). Token drift in code: [design-to-code-gap-auditor](../design-to-code-gap-auditor/SKILL.md).

## Workflow

```
1. SCOPE     -> screens, states, breakpoints and themes to check (from the handoff's state matrix)
2. CAPTURE   -> matching viewport, DPR, fonts, data, state; animations off (references/capture-setup.md)
3. DIFF      -> node scripts/png_diff.mjs design.png build.png --out diff.png
4. INSPECT   -> for each region: measure in DevTools, compare computed styles with tokens
5. BEYOND    -> interactive states, responsive ranges, content edge cases, a11y (references/qa-checklist.md)
6. TRIAGE    -> severity per finding (table below); group by component, not by screen
7. REPORT    -> one ticket per root cause with screenshot pair, diff, expected token, actual value (references/qa-reporting.md)
8. VERIFY    -> re-capture after fixes; add stable screens to visual regression tests
```

## Severity

| Severity | Meaning | Example |
|----------|---------|---------|
| Broken | Blocks a task or accessibility | Missing focus state, overlapping text, button off-screen at 360px |
| Wrong | Clear deviation users notice; wrong component or token | Primary button uses secondary style, wrong error colour |
| Off | Small deviation from spec | 12 vs 16px gap, line height 20 vs 24 |
| Nit | Barely visible; fix if cheap | 1px alignment, sub-pixel rendering |
| Accepted | Intentional or platform difference | Font rendering differences between OSes, real data longer than the mock |

## Diff Codes (png_diff.mjs)

| Code | Severity | Meaning |
|------|----------|---------|
| VD001 | warn | Image sizes differ; only the overlap is compared (often a 2x export vs 1x screenshot) |
| VD002 | warn | Difference region: box, pixel count, average colour in design and build |
| VD003 | info | Tiny regions ignored as anti-aliasing noise |

## Scripts

```bash
node scripts/png_diff.mjs design.png build.png [--tolerance 16] [--min-region 4] [--max 0.5] [--out diff.png] [--json]
```
`--tolerance` is the largest per-channel difference (0-255) treated as equal. Raise it for screenshots with different font
rendering. `--max` is the mismatch percentage that still passes. Transparent pixels are composited over white. Supports
8-bit non-interlaced PNGs (what Figma and browsers export). Needs Node 18+; no packages.
Exit codes: 0 within `--max` and same size, 1 otherwise, 2 bad arguments or unreadable PNG.

## Output

1. QA summary per screen and state: pass / findings count by severity
2. Findings: severity, component, expected (token/spec), actual (computed value), screenshot pair and diff, fix
3. Things verified beyond screenshots (states, responsive, a11y)
4. Recommendation: ship / ship with known issues / fix first

## Additional Resources

| File | Content |
|------|---------|
| [capture-setup.md](references/capture-setup.md) | Matching captures: Figma export settings, browser and Playwright capture, DPR, fonts, data, animations |
| [qa-checklist.md](references/qa-checklist.md) | What to check beyond the diff: states, responsive, content, motion, accessibility, DevTools style checks |
| [qa-reporting.md](references/qa-reporting.md) | Writing QA tickets, grouping by root cause, triage with engineering, visual regression setup |
