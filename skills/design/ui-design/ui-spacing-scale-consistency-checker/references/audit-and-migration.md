# Audit and Migration

## Code audit

```bash
node scripts/spacing_audit.mjs src/ --scale 0,2,4,8,12,16,24,32,40,48,64,80,96 --json > spacing.json
```
Read the histogram first: the most-used values usually reveal the implicit scale the team already follows. Values used once
or twice are noise to remove.

## Figma audit

- Select frames and check auto layout gap and padding values; non-auto-layout frames hide spacing in absolute positions.
- Use number variables for spacing (scoped to gap and padding) so designers pick steps instead of typing values.
- Plugins that list unique spacing values across a page help on big files.
- Check the same component in several screens: card padding 16 in one, 20 in another is the usual drift.

## Mapping decisions

| Off-scale value | Typical mapping | Check |
|-----------------|-----------------|-------|
| 2-3px off a step (10, 14, 18) | Nearest step by role: inset favours the smaller step, layout the larger | Does the proximity hierarchy still hold? |
| Exactly between two steps (20 on an 8/16/24 scale) | Decide by role and context; or add the step if it's used a lot | Frequent in-between values may mean the scale lacks a step |
| Odd values from borders (padding 15 = 16 - 1px border) | Use 16 and `box-sizing: border-box`, or an inset outline | Visual size, not the arithmetic, should land on the scale |
| Optical tweaks (padding-left 14 next to an icon) | Keep inside the component; document | Not a layout value |
| rem values that convert to fractions (1.1rem = 17.6px) | Nearest step in rem (1rem or 1.25rem) | |

Record the mapping table and apply it consistently. Same value + same role = same decision everywhere.

## Applying changes

- Mechanical: find-and-replace per value and role with review; for CSS-in-JS and Tailwind arbitrary values, a codemod.
- Tokens: replace raw values with `var(--space-*)` / Tailwind theme keys as you go, so the next audit counts them as
  tokens.
- Visual regression tests on key screens; spacing changes move layouts by a few pixels everywhere.

## Enforcement

Stylelint (CSS/SCSS):
```json
{
  "plugins": ["stylelint-declaration-strict-value"],
  "rules": {
    "scale-unlimited/declaration-strict-value": [["/^(margin|padding|gap)/"], { "ignoreValues": ["0", "auto", "inherit"] }]
  }
}
```
(or a custom rule that only allows `var(--space-*)` and listed values).

Tailwind: replace the default spacing in `theme.spacing` (not `extend`) with the scale, and disallow arbitrary values in
review or with a lint plugin.

CI: `node spacing_audit.mjs src/ --min 95` to fail builds that add off-scale values.
