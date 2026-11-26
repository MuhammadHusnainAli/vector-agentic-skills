# Naming Rules

## Casing by platform

| Platform | Components | Props / parameters | Values | Files |
|----------|-----------|--------------------|--------|-------|
| React / TS | PascalCase | camelCase | string unions, lowercase (`"primary"`) | PascalCase.tsx or kebab-case.tsx (pick one) |
| Vue | PascalCase in SFC names; kebab-case in DOM templates | camelCase in script, kebab-case in templates | lowercase | PascalCase.vue |
| Web components | Prefixed kebab-case tag (`acme-text-field`) | kebab-case attributes, camelCase properties | lowercase | kebab-case |
| SwiftUI | PascalCase types | camelCase | enum cases camelCase (`.primary`) | PascalCase.swift |
| Jetpack Compose | PascalCase composables | camelCase | enum PascalCase or sealed classes | PascalCase.kt |
| Figma | Title case or sentence case component names | Title case property names | values matching code | Pages and sections by category |
| CSS | prefix + kebab-case classes | - | modifiers | - |

## Components

- Name the job: `Dialog`, `Toast`, `Tooltip`, `TextField`, `DatePicker`.
- Compound parts share the root: `Tabs`, `Tabs.List`, `Tabs.Tab`, `Tabs.Panel` (or `TabList`, `Tab`, `TabPanel`).
- No appearance (`RoundedCard`), no product names (`CheckoutButton` belongs in product code), no versions (`CardV2`).
- Product-level components that wrap system ones get product prefixes or live in product folders, never in the system
  namespace.

## Props

| Kind | Rule | Good | Avoid |
|------|------|------|-------|
| Variant | `variant` enum | `variant="danger"` | `danger`, `isDanger`, `type="red"` |
| Size | `size` enum, shared scale | `size="sm"` | `small`, `isSmall`, `size={2}` |
| Booleans | Positive; default false; one style system-wide | `disabled`, `required`, `fullWidth` | `notRequired`, `enabled` (default true), mixing `isOpen` and `open` |
| Controlled value | `value`/`defaultValue`, `checked`/`defaultChecked`, `open`/`defaultOpen` | | `selectedValue`, `initialValue` |
| Events | `on` + Change/verb; payload documented | `onValueChange(value)`, `onOpenChange(open)` | `handleClick` as a prop name, `onClicked` |
| Content | Noun for the slot | `label`, `description`, `icon`, `startAdornment` | `text1`, `leftThing` |
| Accessibility | Standard names | `aria-label` passthrough, `labelledBy` | `a11yText` |

Same concept, same name across components: if `Dialog` uses `onOpenChange`, so do `Popover`, `Drawer` and `Menu`.

## Figma layers

- Component layers named after anatomy parts used in the spec and code: `container`, `label`, `icon-start`.
- No "Frame 123" or "Rectangle 4" in published components; descriptions link to docs.
- Hidden helper layers prefixed `_` (also hides components from publishing when used on component names).

## Renaming safely

1. Add the new name; keep the old one as a deprecated alias (re-export, Figma: keep the old component on a deprecated page
   pointing to the new one).
2. Development warning on old usage; codemod for code; search-and-replace guide for Figma.
3. Docs: redirect the old page; add the old name as a search alias.
4. Remove in the next major.
