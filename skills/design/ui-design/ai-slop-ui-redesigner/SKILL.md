---
name: ai-slop-ui-redesigner
description: "Find and remove the generic look of AI-generated interfaces (AI slop) and redesign an existing UI to the standard of a top product designer: detect the fingerprints (purple-indigo gradients, gradient headline text, emoji icons, glassmorphism, glow blobs, hype copy, template social proof, icon-in-square feature grids, oversized radii and shadows, hover lift everywhere, Inter-only type, default Tailwind accents, lorem ipsum), diagnose the cause (defaults instead of decisions, no real content), then rebuild from a brief and one art direction: type pairing and scale, restrained colour, spacing, radius and elevation systems, content-led layout, specific copy, honest proof, real imagery, finished states and accessibility, keeping the product's content and function. Ships slop_scan.mjs (Node, no dependencies) that scores HTML, CSS, JSX/TSX, Vue, Svelte and Astro code 0-100 with file:line evidence, before and after. Use when a UI looks AI-generated, generic or template-like."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# AI Slop UI Redesigner

AI tools produce interfaces that are competent and interchangeable: purple-to-blue gradients, a gradient headline,
"Unlock the power of...", three glass cards with emoji icons, "Trusted by 10,000+ teams", everything rounded and lifting on
hover. None of it is wrong on its own. Together it signals that nobody made a decision, and users read that as a product
that didn't care. Removing the gradients doesn't fix it. A top designer starts from what this product is and who it's for,
picks a point of view, and rebuilds the system and the content around it. This skill detects the template patterns,
diagnoses why they're there, and redesigns the UI properly while keeping what works.

## Trigger Conditions

Activate this skill when the user:
- Says a UI, landing page or app "looks AI-generated", generic, template-like or "like every other SaaS site"
- Built screens with an AI tool (v0, Lovable, Bolt, Cursor, Claude, ChatGPT) and wants them to look professionally designed
- Asks to refine, polish, elevate or de-template an existing design or front-end
- Wants a review of AI-built UI before launch

Foundations used during the rebuild: [design-token-architecture-builder](../design-token-architecture-builder/SKILL.md), [ui-spacing-scale-consistency-checker](../ui-spacing-scale-consistency-checker/SKILL.md),
[dark-mode-palette-designer](../dark-mode-palette-designer/SKILL.md) (contrast), [elevation-shadow-system-designer](../elevation-shadow-system-designer/SKILL.md), [button-state-variant-designer](../button-state-variant-designer/SKILL.md),
[empty-state-illustration-planner](../empty-state-illustration-planner/SKILL.md), [ui-microinteraction-designer](../ui-microinteraction-designer/SKILL.md).

## Workflow

```
1. SCAN       -> node scripts/slop_scan.mjs src/   (score + patterns with file:line)
2. INVENTORY  -> what the page/app must do: content, actions, data, states; what to keep (references/redesign-method.md)
3. BRIEF      -> product, audience, the one thing users must understand, brand attributes, real proof available
4. DIRECTION  -> choose one art direction and write it in one sentence; pick references (not other AI sites)
5. SYSTEM     -> type pairing and scale, colour (neutrals + one accent), spacing, radius, elevation, motion tokens
6. LAYOUT     -> content-led hierarchy, a real grid, varied section rhythm, product imagery instead of decoration
7. COPY       -> rewrite with specifics: who, what, numbers, outcomes; honest proof (references/slop-catalogue.md)
8. CRAFT      -> states, focus, alignment, optical details, responsive, a11y (references/craft-checklist.md)
9. VERIFY     -> re-scan (target under 15), contrast matrix, spacing audit, side-by-side review at 3 widths
```

Keep the user's content, structure that works, brand assets and functionality. Change the decisions, not the product.
If there's an existing design system or brand, the redesign uses it; the slop usually comes from ignoring it.

## What Top Designers Do Instead

| Template default | Senior decision |
|------------------|-----------------|
| Purple-blue gradient background | A neutral base with a considered tint and one accent chosen for the brand |
| Gradient headline text | Typographic contrast: a display face, size and weight carry the headline |
| Emoji icons in tinted squares | A real icon set at one stroke weight, or no icons; product screenshots show features |
| Three equal feature cards | Content-led layout: the most important point gets the most space |
| Glass cards, glow blobs, floating animation | Flat surfaces with clear hierarchy; motion only where it explains |
| "Unlock the power of AI" | "Close the month in three days, with every number traced to its source" |
| "Trusted by 10,000+ teams", John Doe, 5 stars | Named customers, specific results, or nothing until you have them |
| rounded-2xl + shadow-xl everywhere | A radius and elevation scale where each step means something |
| Inter at every size | A pairing with character, a type scale with clear steps, tuned line lengths |
| Centered everything | Alignment chosen per section; left-aligned reading text |

## Score Bands (slop_scan.mjs)

| Score | Verdict | Action |
|-------|---------|--------|
| 0-14 | Clean | Polish with the craft checklist |
| 15-34 | Noticeable | Replace the flagged defaults; tighten the system |
| 35-59 | Heavy | Redesign foundations (type, colour, layout, copy) |
| 60-100 | Severe | Full redesign from a brief and art direction |

## Scripts

```bash
node scripts/slop_scan.mjs PATH [PATH...] [--max 30] [--json]
```
15 rules (AS001-AS015) with weights; repeated use raises a rule's weight up to 2x. Precision guards: a blurred sticky header
isn't glassmorphism (needs a translucent white/black fill), loading spinners and skeletons aren't decorative motion, and
large radii and heavy shadows only count when they're the majority. The score detects template patterns, not taste: a clean
score means "no template fingerprints", and the craft checklist still applies. Needs Node 18+; no packages.
Exit codes: 0 score at or below `--max` (default 30), 1 above, 2 bad arguments or nothing to scan.

## Output

1. Scan result before (score, patterns, locations) and the diagnosis
2. Brief and art direction (one paragraph plus references)
3. The new system: tokens for type, colour, spacing, radius, elevation, motion
4. Redesigned screens or code, with rewritten copy
5. Verification: scan after (target under 15), contrast results, craft checklist, what was kept and why

## Additional Resources

| File | Content |
|------|---------|
| [slop-catalogue.md](references/slop-catalogue.md) | Every pattern: how to spot it, why it reads as AI, what to do instead; copy rewrites |
| [redesign-method.md](references/redesign-method.md) | Brief, art directions, type pairings, colour recipe, layout moves, worked before/after |
| [craft-checklist.md](references/craft-checklist.md) | The finishing standard senior designers hold: typography, spacing, alignment, colour, imagery, states, a11y |
