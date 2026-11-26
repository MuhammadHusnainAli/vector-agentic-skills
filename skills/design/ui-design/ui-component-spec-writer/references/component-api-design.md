# Component API Design

Most of a component's API is decided in the design file. A component whose Figma properties contradict each other
becomes a component whose props contradict each other.

## Enums over booleans

```
Bad:   <Button primary danger small />          (what is primary + danger?)
Good:  <Button variant="danger" size="sm" />
```
Use a boolean only for an independent on/off attribute: `loading`, `fullWidth`, `disabled`. If two booleans can't both
be true, they should be one enum.

## Naming

| Concern | Convention | Example |
|---------|------------|---------|
| Emphasis | `variant`, semantic values | primary, secondary, tertiary, danger. Never `blue`, `outlined-grey` |
| Size | One scale shared across components | sm, md, lg (not small/M/large mixes) |
| Booleans | Adjective or is/has prefix, default false | `loading`, `fullWidth`, `hasIcon` |
| Events | `on` + verb | `onChange`, `onOpenChange`, `onDismiss` |
| Content | Noun for the slot | `label`, `description`, `icon`, `action` |

## Props vs slots vs composition

| Content | Use | Why |
|---------|-----|-----|
| A short string | Prop (`label`) | Can be length-checked and translated |
| One icon from the set | Prop (`icon="trash"`) | Keeps sizing and colour consistent |
| Rich, varied content | Slot / children | Spec what is allowed (no nested interactive elements in a clickable card) |
| Repeating structured parts | Compound components (`<Tabs><Tabs.List><Tabs.Tab>`) | Keeps the parts' ARIA wiring inside the component |

## Controlled and uncontrolled

Form-like components (text field, select, switch, tabs, accordion, dialog `open`) support both:
- Uncontrolled: `defaultValue` / `defaultOpen`. The component owns the state.
- Controlled: `value` + `onChange` / `open` + `onOpenChange`. The parent owns the state.
The spec says which events fire and when (on every keystroke, on commit, on blur).

## Things that should not be props

- Colours, spacing, radii: these come from tokens and variants. A `color` prop ends consistency.
- `className`/`style` overrides as the documented way to customise: keep them as an escape hatch and measure how often
  they're used (see design-system-adoption-tracker).
- Accessibility opt-outs (`noFocusRing`).

## Deprecation

Never rename or remove a prop in a minor version. Mark it deprecated, log a development warning that names the replacement,
document the migration, and remove it in the next major. See design-system-governance-process-designer.
