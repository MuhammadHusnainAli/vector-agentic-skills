---
name: redline-annotation-writer
description: "Write redlines and design annotations that carry the intent Dev Mode can't infer: spacing and sizes as tokens and rules (not pixel soup), sizing behaviour (fixed, hug, fill, min and max widths) translated to CSS flex and grid, alignment and distribution, type styles, colour tokens, truncation and wrapping, responsive changes per breakpoint, z-order and overlap, scroll and sticky behaviour, state differences, and platform notes. Defines a consistent notation (numbered markers, colour-coded annotation categories, legend) and an annotation kit for Figma. Reviews redlines for raw pixel values where tokens exist, measurements Dev Mode already shows, missing behaviour rules, contradictory values between frames, unannotated responsive changes and cluttered annotations that hide the design. Use when annotating a design for engineering, preparing redlines for a complex layout, or reviewing an annotated file before handoff."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Redline Annotation Writer

Dev Mode already measures every gap. Redlines that repeat those numbers add clutter and nothing else. Good annotations
capture what a measurement can't: this gap is `space.6` and grows to `space.8` above 1024px, this column fills and that one
hugs, the title truncates after two lines, the header sticks. This skill writes those annotations in a consistent notation
and reviews redlines for noise and missing rules.

## Trigger Conditions

Activate this skill when the user:
- Annotates a design for engineering, or asks for redlines
- Has a complex layout (dashboards, tables, responsive pages) where measurements alone are ambiguous
- Sets up an annotation kit or conventions for the team
- Reviews an annotated file before handoff

Full handoff package: `design-handoff-spec-generator`. Accessibility annotations: `accessibility-annotation-writer`. Spacing
scale: `ui-spacing-scale-consistency-checker`.

## Workflow

```
1. SKIP      -> list what Dev Mode shows correctly already (static sizes, colours from variables, text styles)
2. RULES     -> per region: sizing behaviour, alignment, spacing token, min/max (references/annotation-types.md)
3. RESPONSIVE-> what changes at each breakpoint, and what stays
4. CONTENT   -> truncation, wrapping, line clamps, overflow, empty values
5. BEHAVIOUR -> scroll, sticky, z-order, overlap, states
6. NOTATE    -> numbered markers + category colours + legend (references/notation-and-kit.md)
7. CSS       -> auto layout translated to flex/grid where it helps (references/auto-layout-to-css.md)
8. REVIEW    -> checklist below
```

## Principles

| Principle | Example |
|-----------|---------|
| Tokens, not pixels | "gap: space.4" not "16px" |
| Rules, not instances | "Sidebar: 280 fixed, collapses to 72 below 1024" not five measured frames |
| Annotate intent | "Price column hugs content; name column fills remaining width, min 200" |
| One annotation per rule, referenced everywhere | Marker 4 on every card instead of repeating the sentence |
| Behaviour over geometry | "Header sticky after 64px scroll", "Table header sticks within the table" |
| Keep the design visible | Annotations beside the frame, connected with leaders; not on top of content |

## Review Checklist

Report as `CODE [severity] frame/marker: problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| RL001 | high | Behaviour that can't be measured is missing: fill vs hug, min/max, truncation, sticky, scroll |
| RL002 | high | Values that contradict each other between frames or breakpoints |
| RL003 | medium | Raw pixel or hex values where tokens exist |
| RL004 | medium | Responsive changes not annotated (only some breakpoints designed, no rule between) |
| RL005 | medium | Redundant measurements Dev Mode already shows (clutter) |
| RL006 | medium | Annotations covering the design, or no legend for colours and markers |
| RL007 | low | Inconsistent notation (mixed marker styles, categories without colours) |
| RL008 | low | Annotations not updated after design changes (stale) |

## Output

Annotation list per frame: marker number, category, rule text (with tokens), and where it applies. Plus CSS translations
for complex regions and a legend. For a review: findings and the cleaned-up annotation set.

## Additional Resources

| File | Content |
|------|---------|
| [annotation-types.md](references/annotation-types.md) | What to annotate per category with wording templates |
| [auto-layout-to-css.md](references/auto-layout-to-css.md) | Figma auto layout and constraints to CSS flex, grid, min/max, sticky and overflow |
| [notation-and-kit.md](references/notation-and-kit.md) | Marker system, category colours, legend, building an annotation kit in Figma |
