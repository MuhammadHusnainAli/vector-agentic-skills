---
name: design-system-documentation-writer
description: "Write design system documentation that designers and engineers actually use: component pages (summary, when to use and when not, anatomy, variants with reasons, behaviour, content guidelines, accessibility with keyboard and screen-reader notes, props table, do and don't pairs with images, related components, status and changelog), foundation pages (colour, type, spacing, elevation, motion, iconography), pattern pages (forms, empty states, errors, navigation), and the docs site structure (foundations, components, patterns, content, accessibility, resources, what's new). Covers status labels, writing style (decisions with reasons, no marketing tone), code examples and keeping docs in sync with releases. Reviews pages for missing usage limits, unpaired do/don't, vague guidance, incomplete props, missing accessibility notes and stale examples. Use when writing or reviewing design system docs, component guidelines or a docs site."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Design System Documentation Writer

People read design system docs to make a decision quickly: which component, which variant, how to word it, whether it's
accessible. Docs that only show the component ("This is a button") get skipped. Docs that state decisions and their
reasons get followed. This skill writes the pages and reviews existing ones against what readers need.

## Trigger Conditions

Activate this skill when the user:
- Writes a component, foundation or pattern page for a design system
- Sets up or restructures a design system documentation site
- Reviews existing docs that people don't use, or that disagree with the code
- Needs do/don't guidance, content guidelines or accessibility notes for a component

Build-ready component spec (states matrix, edge cases): [ui-component-spec-writer](../ui-component-spec-writer/SKILL.md). Contribution and release process:
[design-system-governance-process-designer](../design-system-governance-process-designer/SKILL.md).

## Workflow

```
1. READERS   -> who reads this page and what they decide: designer choosing, engineer building, PM reviewing, content writer
2. SOURCE    -> component spec, Figma component, code props, accessibility audit, known misuse in products
3. DRAFT     -> fill references/page-templates.md (component, foundation or pattern template)
4. DECIDE    -> every "use when" has a "don't use when" naming the alternative; every variant has a reason
5. EXAMPLES  -> real product content, not lorem ipsum; do/don't pairs that show the same situation both ways
6. STYLE     -> apply references/writing-style.md (imperative, specific, short sentences)
7. REVIEW    -> run the checklist below; engineering checks props and code, accessibility checks the a11y section
8. SHIP      -> status label, version, changelog entry, link from Figma component description
```

## What Makes Docs Get Used

| Practice | Example |
|----------|---------|
| Lead with the decision | "Use a switch for settings that take effect immediately. If the change needs saving, use a checkbox." |
| Name alternatives | "For more than 2 actions, use a menu button." |
| Explain why | "Primary buttons are limited to one per view so the next step is obvious." |
| Show, then tell | Example first, explanation after |
| Do / don't pairs of the same scenario | Do: "Delete project". Don't: "OK" in the same confirmation dialog |
| Copy-pasteable code | Minimal working example, then common variations |
| State status | Stable, beta, deprecated (with replacement and removal date) |

## Review Checklist

Report as `CODE [severity] problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| DD001 | high | No "when not to use" or no named alternative |
| DD002 | high | No accessibility section, or it says only "accessible" (needs keyboard, screen-reader, focus, contrast notes) |
| DD003 | high | Code example that doesn't match the current API (props renamed, removed) |
| DD004 | medium | Do without a matching don't (or the reverse), or do/don't showing different scenarios |
| DD005 | medium | Vague guidance: "use appropriately", "when needed", "sparingly" without a rule |
| DD006 | medium | Variants listed with no reason to choose one over another |
| DD007 | medium | Props table without types, defaults or descriptions |
| DD008 | medium | No content guidelines for components with text (labels, errors, empty states) |
| DD009 | medium | Placeholder or lorem ipsum examples |
| DD010 | low | No status label, version or last-updated date |
| DD011 | low | No links to related components, Figma component or source code |
| DD012 | low | Marketing tone ("beautiful", "powerful", "seamless") instead of guidance |

## Output

A complete Markdown (or MDX) page following the template, with placeholders only for screenshots and live examples,
plus a short list of open questions for the component owner. For reviews: findings, then the corrected sections.

## Additional Resources

| File | Content |
|------|---------|
| [page-templates.md](references/page-templates.md) | Component, foundation and pattern page templates with section guidance |
| [writing-style.md](references/writing-style.md) | Voice, sentence rules, do/don't writing, accessibility notes, code examples |
| [docs-site-structure.md](references/docs-site-structure.md) | Site IA, navigation, status labels, versioning, changelog, keeping docs in sync |
