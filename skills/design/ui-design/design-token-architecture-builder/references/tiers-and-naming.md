# Tiers and Naming

## The three tiers

```
primitive (options)     core.color.blue.600 = #2563EB          core.space.4 = 16px
        |
semantic (decisions)    color.action.primary.bg = {core.color.blue.600}     space.inset.md = {core.space.4}
        |
component (scoped)      button.primary.bg = {color.action.primary.bg}       button.padding.inline = {space.inset.md}
```

| Tier | Contains | Changes per mode/brand? | Who uses it |
|------|----------|-------------------------|-------------|
| Primitive | Every available raw value: colour ramps, scales | No | Only semantic tokens |
| Semantic | Purpose-based decisions | Yes (light/dark, brand A/B) | Components, layouts, product code |
| Component | Overrides scoped to one component | Sometimes | That component only |

When to add component tokens:
- The component must be themeable on its own (white-label button colours).
- The component's value deliberately differs from the general semantic token.
- Multi-brand systems where brands restyle components differently.
Otherwise, components reference semantic tokens directly. A component tier for every property of every component triples
the token count for no benefit.

## Naming taxonomy

```
[namespace].[category].[concept].[property].[variant].[state].[scale]
  ds         color      action    bg         primary   hover
```
Use only the levels you need. Keep the order fixed.

| Category | Good names | Avoid |
|----------|-----------|-------|
| Colour (semantic) | color.text.default / subtle / disabled / inverse / danger; color.surface.default / raised / sunken / overlay; color.border.default / strong / focus; color.action.primary.bg / fg / bg-hover | color.grey-text, color.blue2, color.primaryDark |
| Space | space.1 ... space.12 (scale steps); space.inset.sm/md/lg; space.stack.md; space.inline.sm | space.16px, margin-small-ish |
| Size | size.icon.sm/md/lg; size.target.min | |
| Radius | radius.sm / md / lg / full; radius.control; radius.container | radius.button (unless component tier) |
| Type | font.family.sans; font.size.300; typography.body.md (composite) | font.size.14 |
| Elevation | elevation.1 ... elevation.5 (composite shadow); elevation.overlay | shadow.big |
| Motion | duration.fast / moderate / slow; easing.standard / enter / exit | anim.speed1 |
| Z-index | z.dropdown / sticky / overlay / modal / toast | z.9999 |

## Semantic colour roles (starter set)

| Group | Roles |
|-------|-------|
| Text | default, subtle, disabled, inverse, link, danger, success, warning |
| Surface | default (page), raised (card), sunken (well), overlay (menu, dialog), inverse |
| Border | default, subtle, strong, focus, danger |
| Action | primary bg / fg / bg-hover / bg-pressed; secondary ...; danger ... |
| Feedback | info / success / warning / danger, each with bg (subtle), fg, border, icon |
| Data viz | categorical.1-8, sequential.*, diverging.* (separate from UI feedback colours) |

Each foreground role is designed against specific background roles; document the valid pairs and check contrast for each
(see button-state-variant-designer / dark-mode-palette-designer).

## Anti-patterns

| Anti-pattern | Fix |
|--------------|-----|
| Token per hex value found in the codebase | Cluster first; map to the nearest ramp step |
| Semantic names that describe looks (color.blue-button) | Rename by purpose; keep the old name as deprecated alias |
| Components referencing primitives | Introduce the missing semantic role |
| Different names in Figma and code | One naming source; Figma variable code syntax set to the CSS name |
| Modes as separate token names (color.text.dark-mode) | One name, value per mode |
| Opacity baked into dozens of colours | Primitive with alpha, or a state-layer approach for interaction states |
