---
name: card-component-designer
description: "Design card components and card grids that scan well and work for everyone: when cards beat lists and tables (heterogeneous content you browse vs uniform data you compare), anatomy and content priority (media, eyebrow, title, meta, description, actions), clickable cards done right (one real link stretched over the card, secondary actions above it, no nested interactive elements, correct heading level, focus ring on the whole card), media aspect ratios and missing-image fallbacks, title and description truncation with line-clamp, equal heights with actions pinned to the bottom, responsive grids with auto-fill minmax and column math, density variants, and states (hover without layout shift, focus-visible, selected, loading skeleton, disabled). Reviews cards for whole-card anchor wrappers, nested links and buttons, redundant links, missing alt text, heading misuse, uneven grids and hover-only actions. Use when designing product, content, pricing, dashboard or e-commerce cards, or a card grid."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Card Component Designer

Cards are used for everything, which is why they're often wrong. A grid of cards is right when items are different
enough that each needs its own small layout and people browse rather than compare. It's wrong for data people compare
attribute by attribute: that's a table or a list. Once cards are the right choice, the hard parts are the clickable-card
problem, real content lengths and keeping the grid even. This skill handles all three.

## Trigger Conditions

Activate this skill when the user:
- Designs a card, tile or card grid (products, articles, projects, plans, dashboard tiles)
- Asks how to make a whole card clickable, or has nested links/buttons inside a clickable card
- Has uneven card heights, overflowing titles or broken grids at some widths
- Decides between cards, a list and a table

Dashboard KPI tiles: `dashboard-layout-designer`. Grid ranges: `responsive-breakpoint-layout-planner`. Elevation:
`elevation-shadow-system-designer`.

## Workflow

```
1. FIT       -> cards vs list vs table (table below)
2. CONTENT   -> list fields per item with real min/max lengths; rank by what people scan first
3. ANATOMY   -> media, eyebrow/meta, title, description, attributes, actions (references/card-anatomy.md)
4. LINK      -> one primary destination? stretched-link pattern; secondary actions separate (references/clickable-cards.md)
5. LIMITS    -> title lines, description lines, badge count, fallback for missing media
6. GRID      -> min card width, gap, columns per breakpoint, equal heights (references/card-grids.md)
7. STATES    -> hover, focus-visible, selected, loading, disabled/unavailable
8. REVIEW    -> run the checklist below with the longest and shortest real items side by side
```

## Cards, List or Table

| Content and task | Use |
|------------------|-----|
| Visual items browsed for appeal (products, recipes, articles, templates) | Cards |
| Items with varied content types in one collection (feed, dashboard) | Cards |
| Items compared on the same 3+ attributes (price, date, status, owner) | Table |
| Text-first items scanned in sequence (messages, files, search results) | List |
| Few items with a decision between them (pricing plans) | Cards side by side, aligned rows of features |

## Review Checklist

Report as `CODE [severity] problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| CD001 | high | Whole card wrapped in `<a>` with buttons or links inside (nested interactive content; invalid HTML, broken for assistive tech) |
| CD002 | high | Clickable card with no keyboard focus or no visible focus indicator |
| CD003 | high | Informative image without alt text, or decorative image with alt text duplicating the title |
| CD004 | medium | Several links to the same destination in one card (image, title, "Read more") |
| CD005 | medium | Title not a heading, or wrong heading level for the page outline |
| CD006 | medium | Actions only visible on hover (no touch or keyboard path) |
| CD007 | medium | No truncation rule: long titles push actions out of alignment, or truncation hides the only full text |
| CD008 | medium | Hover changes size or border width (layout shift) instead of elevation, outline or shadow |
| CD009 | medium | Cards used for data people compare attribute by attribute (should be a table) |
| CD010 | low | No missing-media fallback; varying aspect ratios in one grid |
| CD011 | low | Grid leaves a lone orphan card stretched across a row, or columns too narrow at a range edge |
| CD012 | low | "Read more" / "Learn more" link text without context for screen readers |

## Output

1. Decision: cards / list / table, with the reason
2. Anatomy with content limits per slot and the fallback for each optional slot
3. Interaction model: primary link, secondary actions, keyboard stops, focus style
4. Grid spec: min width, gap, columns per range, aspect ratio
5. States and review findings

## Additional Resources

| File | Content |
|------|---------|
| [card-anatomy.md](references/card-anatomy.md) | Slots, content priority, truncation, media, badges, pricing and product cards |
| [clickable-cards.md](references/clickable-cards.md) | Stretched-link pattern with CSS, secondary actions, focus, selection cards, screen-reader output |
| [card-grids.md](references/card-grids.md) | auto-fill minmax math, equal heights, masonry, horizontal scrollers, skeletons |
