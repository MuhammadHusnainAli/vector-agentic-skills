# Spacing Scales

## Base unit

| Base | Pros | Cons | Typical products |
|------|------|------|------------------|
| 8px | Few, clearly different steps; matches many platform grids | Too coarse for dense UI (8 vs 16 is a big jump) | Consumer apps, marketing |
| 4px | Finer control for dense UIs; aligns with 4px baseline type grids | Tempts people to use every multiple | Productivity, data-heavy, enterprise |

Common answer: a 4px base with a curated scale that skips most multiples above 16.

## Scale shapes

| Shape | Steps (px) | Notes |
|-------|-----------|-------|
| Linear 8 | 8, 16, 24, 32, 40, 48 | Simple; large steps feel samey (40 vs 48) |
| Curated 4/8 (recommended) | 0, 2, 4, 8, 12, 16, 24, 32, 40, 48, 64, 80, 96 | Fine at the small end, growing gaps at the large end |
| Geometric (ratio about 1.5) | 4, 6, 9, 14, 21, 32, 48, 72 | Good for editorial; odd values awkward in components |
| Tailwind default | 0, 1, 2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 28, 32, 36, 40, 44, 48, 56, 64, 80, 96, 112, 128 ... | Very permissive; lock it down in the theme if consistency matters |

Steps should be easy to tell apart: humans barely notice 14 vs 16, so having both invites inconsistency.

## Naming

| Style | Example | Notes |
|-------|---------|-------|
| Numeric step | space.1 = 4, space.2 = 8, space.3 = 12, space.4 = 16, space.6 = 24, space.8 = 32 | Step = value / 4; leaves room to add steps |
| T-shirt | space.xs, sm, md, lg, xl, 2xl | Readable; hard to insert a step later |
| Role aliases (semantic) | space.inset.sm/md/lg, space.stack.sm/md/lg, space.inline.xs/sm, space.layout.section | Components use roles; roles map to steps |

## Roles

| Role | Meaning | Typical values |
|------|---------|----------------|
| Inset | Padding inside a container | Squish (vertical < horizontal) for buttons and chips: 8 x 16; square for cards: 16 or 24 |
| Stack | Vertical gap between stacked elements | Label to field 4-8; between fields 16-24; between groups 32 |
| Inline | Horizontal gap between items in a row | Icon to text 4-8; between buttons 8-12; between chips 8 |
| Layout | Between page sections and regions | 32-96, often fluid (clamp) |

## Proximity hierarchy

Spacing tells people what belongs together. Each level up should use a clearly larger step:

```
heading <- 8 -> its text
field label <- 4 -> field  <- 16 -> next label
group <- 32 -> next group
section <- 64 -> next section
```

If a heading sits the same distance from the text above and below, it no longer belongs to either.

## Density modes

| Density | Rule |
|---------|------|
| Comfortable (default) | Base role values |
| Compact | Insets and stacks one step smaller (16 -> 12, 12 -> 8); control heights 40 -> 32 |
| Touch | Larger targets, same visual spacing; hit areas extended |

Implement density as alternate values for the role tokens (a mode), not as new component variants.

## Relation to type and icons

- Line heights on a 4px grid (16/20/24/28/32) keep text boxes aligned with spacing steps.
- Icons 16/20/24 with 4/8 gaps keep icon-plus-text rows on the grid.
- Optical adjustments (an icon's visual weight, cap height vs box) happen inside components with 1-2px tweaks; document
  them, don't add them to the global scale.
