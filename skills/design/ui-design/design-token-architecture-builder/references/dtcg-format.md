# W3C Design Tokens Format (DTCG) Essentials

The Design Tokens Community Group format (stable 2025.10) is a JSON format supported by Style Dictionary v4,
Tokens Studio, Figma variable import/export tooling and others.

## Tokens and groups

```json
{
  "color": {
    "$type": "color",
    "blue": {
      "600": { "$value": { "colorSpace": "srgb", "components": [0.145, 0.388, 0.922], "hex": "#2563eb" },
               "$description": "Primary action base" }
    }
  }
}
```
- A token is an object with `$value`. A group is an object without `$value`.
- `$type` on a group applies to all tokens inside unless they set their own.
- `$description`, `$extensions` (tool-specific data, namespaced by reverse domain), `$deprecated` (true or a message).
- Names must not start with `$` and must not contain `{`, `}` or `.`.

## Aliases

```json
{ "color": { "action": { "primary": { "bg": { "$type": "color", "$value": "{color.blue.600}" } } } } }
```
- `{path.to.token}` references another token; the type must match.
- Chains are allowed (component -> semantic -> primitive). Cycles are invalid.

## Types

| $type | Value (2025.10) | Older/string form many tools still accept |
|-------|-----------------|-------------------------------------------|
| color | `{ "colorSpace": "srgb", "components": [r, g, b], "alpha": 1, "hex": "#rrggbb" }` (also oklch, display-p3 ...) | "#2563EB", "oklch(...)" |
| dimension | `{ "value": 16, "unit": "px" }` (px or rem) | "16px", "1rem" |
| fontFamily | "Inter" or ["Inter", "system-ui", "sans-serif"] | |
| fontWeight | 100-1000 or names (regular, bold ...) | |
| duration | `{ "value": 200, "unit": "ms" }` | "200ms" |
| cubicBezier | [0.2, 0, 0, 1] (x values 0-1) | |
| number | 1.5 | |
| strokeStyle | "solid" / "dashed" or object | |
| Composite | border, transition, shadow, gradient, typography | |

Composite example:
```json
{
  "elevation": { "2": { "$type": "shadow", "$value": [
    { "color": "{color.shadow.key}", "offsetX": { "value": 0, "unit": "px" }, "offsetY": { "value": 2, "unit": "px" },
      "blur": { "value": 4, "unit": "px" }, "spread": { "value": 0, "unit": "px" } },
    { "color": "{color.shadow.ambient}", "offsetX": { "value": 0, "unit": "px" }, "offsetY": { "value": 4, "unit": "px" },
      "blur": { "value": 12, "unit": "px" }, "spread": { "value": 0, "unit": "px" } } ] } },
  "typography": { "body": { "md": { "$type": "typography", "$value": {
    "fontFamily": "{font.family.sans}", "fontSize": "{font.size.300}", "fontWeight": 400,
    "letterSpacing": { "value": 0, "unit": "px" }, "lineHeight": 1.5 } } } }
}
```

## Modes and themes: file layout

The format has no built-in modes. The common, tool-friendly layout:

```
tokens/
  core/                 primitives (one set, never mode-specific)
    color.json  space.json  type.json  motion.json
  semantic/
    light.json          every semantic token, light values
    dark.json           the same token names, dark values
    high-contrast.json
  component/
    button.json  input.json        aliases to semantic tokens only
  brand/                (multi-brand)
    acme/core-overrides.json       brand primitives that replace core ramps
```

Build one output per mode by combining `core + semantic/<mode> + component`. Every mode file must have the same set of
semantic keys (`token_lint.mjs --modes`).

## Multi-brand

| Approach | How | Use when |
|----------|-----|----------|
| Brand swaps primitives | Brands provide their own ramps under the same primitive names; semantics unchanged | Brands differ in colour and type only |
| Brand swaps semantics | Each brand has its own semantic files | Brands differ in decisions (which colour is the action colour) |
| Brand component overrides | Component-tier files per brand | Brands restyle specific components |

Brands x modes multiply: 3 brands x 2 modes = 6 builds. Keep the semantic key set identical across all of them.
