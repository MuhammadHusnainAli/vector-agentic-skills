---
name: component-naming-convention-checker
description: "Define and check naming conventions across a design system so Figma, code and docs use the same words: component names (purpose not appearance, one term per concept: Dialog vs Modal, Select vs Dropdown, Toast vs Snackbar, Tag vs Chip vs Badge), casing per platform (PascalCase components, camelCase props, kebab-case files and CSS, prefixed custom elements), prop and variant naming (variant enums with semantic values, boolean prop style, on-prefixed events, shared size scale), Figma component sets with Property=Value variants, boolean, instance-swap and text properties that map one-to-one to code props, layer names, token names and CSS class prefixes. Reviews name lists for visual names (BlueButton), abbreviations, wrong casing, mixed size scales, synonyms, negative booleans, Figma-code mismatches and version suffixes. Use when setting naming rules for a design system, auditing names before a release, or aligning a Figma library with the code library."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Component Naming Convention Checker

Names are the interface people search with. When Figma calls it "Modal", code calls it `<Dialog>` and the docs say
"Overlay", every handoff needs a translation and search finds nothing. This skill sets one vocabulary and one set of
casing and structure rules for components, props, variants, Figma properties and tokens, then reviews name lists against
them.

## Trigger Conditions

Activate this skill when the user:
- Sets up naming rules for a new design system or library
- Shares a list of components, props, variants or Figma properties to review
- Aligns a Figma library with a code library (property names, variant values)
- Is renaming components and needs a migration-safe plan

Token names: `design-token-architecture-builder`. Finding duplicated components: `component-library-inventory-auditor`.
Figma-vs-code variant gaps: `design-to-code-gap-auditor`.

## Workflow

```
1. COLLECT   -> names from code (components, props, values), Figma (components, properties, values), docs
2. VOCAB     -> pick one term per concept (references/vocabulary.md); record synonyms as search aliases
3. RULES     -> casing and structure per artefact (references/naming-rules.md)
4. CHECK     -> run the review checklist over every name; group findings by rule
5. PARITY    -> line up Figma properties and code props side by side (references/figma-code-parity.md)
6. PLAN      -> renames with deprecated aliases, codemods and Figma library migration notes
```

## Core Rules

| Artefact | Rule | Example |
|----------|------|---------|
| Component | Purpose noun, PascalCase in code, Title case in Figma | `Dialog`, `TextField`, Figma "Text field" |
| Variant prop | `variant` with semantic values | `variant="primary" / "danger"` |
| Size prop | One scale for the whole system | `size="sm" / "md" / "lg"` everywhere |
| Boolean prop | Positive, adjective or is/has, default false; one style across the system | `disabled`, `loading`, `fullWidth` (not `notVisible`, `noBorder`) |
| Event prop | `on` + past/present verb or noun+verb | `onChange`, `onOpenChange`, `onDismiss` |
| Figma variant property | `Property=Value`, property Title case, values match code values | `Variant=primary, Size=md, State=hover` |
| Files | One convention (PascalCase.tsx or kebab-case.tsx) | `TextField.tsx` |
| CSS classes | System prefix + BEM or similar | `.ds-button`, `.ds-button--primary`, `.ds-button__icon` |
| Custom elements | Prefix, must contain a hyphen | `<acme-button>` |

## Review Checklist

Report as `CODE [severity] name: problem -> suggested name`.

| Code | Severity | Check |
|------|----------|-------|
| NC001 | high | Two names for the same concept across the system (Modal and Dialog both exist) |
| NC002 | high | Figma property or value with no matching code prop/value (or the reverse) |
| NC003 | medium | Appearance in the name (BlueButton, RoundedCard, BigTitle) |
| NC004 | medium | Abbreviations or internal jargon (Btn, Dlg, Txt, NavThing) |
| NC005 | medium | Casing breaks the rule for that artefact (textField component, OnChange prop, Primary value) |
| NC006 | medium | Mixed size scales (sm/md/lg next to small/medium/large or S/M/L or 1/2/3) |
| NC007 | medium | Negative or double-negative booleans (hideLabel=false, noPadding, notDisabled) |
| NC008 | medium | Version or status in the name (ButtonV2, NewCard, OldModal, LegacyTable) |
| NC009 | low | Overly generic names (Item, Wrapper, Container, Box) for public components |
| NC010 | low | Plural/singular inconsistency (Tabs and Tab vs TabList; RadioGroup vs Radios) |
| NC011 | low | Same prop with different names across components (onClose / onDismiss / onHide) |

## Output

1. Naming rules table for the system
2. Vocabulary: chosen term, rejected synonyms (as search aliases), definition
3. Findings list
4. Rename plan: old -> new, deprecation alias, codemod, Figma migration note, docs redirect

## Additional Resources

| File | Content |
|------|---------|
| [naming-rules.md](references/naming-rules.md) | Casing and structure per platform and artefact, props and events, Figma layers, renaming safely |
| [vocabulary.md](references/vocabulary.md) | Preferred terms for commonly confused components with definitions |
| [figma-code-parity.md](references/figma-code-parity.md) | Mapping Figma properties to code props, parity table, common mismatches |
