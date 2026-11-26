# Component Parity

## Collect both sides

| Side | Source |
|------|--------|
| Figma | Library component sets and their properties (variant, boolean, instance swap, text); via the file, or the REST API (`GET /v1/files/:key/component_sets` plus node `componentPropertyDefinitions`) or a Figma MCP/plugin |
| Code | Component exports and prop types (TypeScript types, react-docgen, Storybook ArgTypes) |
| Docs | Design system site component list |

## Parity table

| Component | Figma | Code | Property / prop | Figma values | Code values | Status | Action |
|-----------|-------|------|-----------------|--------------|-------------|--------|--------|
| Button | yes | yes | variant | Primary, Secondary, Ghost | primary, secondary, tertiary | Mismatch | Rename Ghost -> tertiary in Figma |
| Button | yes | yes | size | S, M, L | sm, md, lg | Mismatch (naming) | Align values |
| Button | yes | yes | loading | - | boolean | Code-only | Add Figma variant |
| Tooltip | yes | no | - | - | - | Figma-only | Build, or remove from library |
| DataGrid | no | yes | - | - | - | Code-only | Design it into the library or document as engineering-only |

Statuses: OK, Mismatch, Figma-only, Code-only, Intentional (documented).

## States coverage

For each component, list the states from its spec and check:
- Figma: a variant or documented property for the state
- Code: supported by props or CSS
- Storybook: a story per state (makes visual regression possible)

| Component | State | Figma | Code | Story |
|-----------|-------|-------|------|-------|
| TextField | error | yes | yes | yes |
| TextField | read-only | no | yes | no |
| TextField | loading (async validation) | yes | no | no |

## Code Connect

Figma Code Connect maps each Figma component (and its properties) to the real code snippet shown in Dev Mode. Setting it up
forces parity decisions, because every Figma property needs a code mapping. Unmappable properties are parity gaps by
definition.
