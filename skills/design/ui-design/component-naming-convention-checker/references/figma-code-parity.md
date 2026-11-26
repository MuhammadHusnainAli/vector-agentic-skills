# Figma and Code Parity

## Property mapping

| Figma property type | Code equivalent | Naming rule |
|---------------------|-----------------|-------------|
| Variant property (`Size=md`) | Enum prop (`size="md"`) | Property name = prop name in Title case; values identical, lowercase |
| Variant property for state (`State=hover`) | Not a prop: CSS/interaction state | Keep in Figma for documentation; mark as "visual state only" |
| Boolean property (`Show icon`) | Optional slot or boolean (`icon={...}`) | Name for what it controls; map in docs ("Show icon -> pass `icon`") |
| Instance swap (`Icon`) | Slot / icon prop (`icon="trash"`) | Same name as the prop |
| Text property (`Label`) | String prop (`label`) | Same name as the prop |
| Nested instance properties (exposed) | Props of a sub-component | Prefix with the part if ambiguous (`Badge count`) |

Figma Dev Mode and Code Connect can show the real code snippet for an instance. Code Connect mappings only stay right if
property names line up.

## Parity table (build one per component)

| Component | Figma property | Figma values | Code prop | Code values | Status |
|-----------|----------------|--------------|-----------|-------------|--------|
| Button | Variant | Primary, Secondary, Ghost | variant | primary, secondary, tertiary | Mismatch: Ghost vs tertiary; casing |
| Button | Size | Small, Medium, Large | size | sm, md, lg | Mismatch: value names |
| Button | Show icon | true/false | icon | IconName | OK (documented mapping) |
| Button | State | Default, Hover, Pressed, Disabled, Focus | disabled | boolean | OK: only Disabled is a prop |
| Button | - | - | loading | boolean | Missing in Figma |

Statuses: OK, Mismatch (rename one side), Missing in Figma, Missing in code, Intentional difference (documented).

## How to collect the lists

- Figma: the component set's properties panel, or the Figma REST API (`GET /v1/files/:key/component_sets` then the file
  nodes' `componentPropertyDefinitions`).
- Code: TypeScript prop types (react-docgen-typescript, Storybook ArgTypes), or the component's `.d.ts`.

## Common mismatches

| Mismatch | Fix |
|----------|-----|
| Value casing (Primary vs primary) | Lowercase both, or accept Title case in Figma with an exact lowercase mapping documented |
| Size names (Medium vs md) | Use the code scale in Figma too |
| Figma-only variants (Ghost) never built | Build it or remove it from Figma |
| Code-only props (loading) not designable | Add a Figma variant or boolean |
| Different component names (Modal vs Dialog) | Rename one side; keep alias for search |
| States as props in Figma (Hover=true) | Model as a State variant, not a boolean |
