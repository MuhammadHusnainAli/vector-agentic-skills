---
name: ui-component-spec-writer
description: "Write UI component specifications that engineering can build and QA can test without a follow-up meeting: purpose and when not to use, anatomy, props API (variants vs booleans vs slots, controlled vs uncontrolled), variant x state matrix with token references, sizes and touch targets (WCAG 2.5.8, 44pt, 48dp), keyboard model and ARIA from the WAI-ARIA Authoring Practices pattern (button, tabs, dialog, combobox, menu, switch, checkbox, radio group, accordion, tooltip, disclosure, listbox, slider, text field, toast, card), focus movement, content limits and overflow, tokens, motion and edge cases (long text, translation growth, 200% zoom, RTL, forced colors, reduced motion). Reviews existing specs against a 14-point checklist (no focus state or keyboard model, wrong pattern, hover-only behaviour, raw values, small targets). Use when designing a new component, writing or reviewing a component spec, preparing a component for handoff or adding one to a design system."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# UI Component Spec Writer

A component spec is a contract. Design decides behaviour once, engineering builds it once, and QA tests against it. It has
three readers: an engineer who needs to know what to build, QA who needs to know when it's done, and an accessibility
reviewer who needs to know it works without a mouse. Specs fail when they document only the happy-path screenshot. This
skill writes the whole contract, and reviews specs other people wrote, using the template, pattern tables and checklist
in `references/`.

## Trigger Conditions

Activate this skill when the user:
- Designs a new component or a new variant of an existing one
- Writes, reviews or "finishes" a component spec before handoff
- Asks what states, props, keyboard behaviour or ARIA a component needs
- Adds a component to a design system, or engineering keeps asking the same questions

Design-system docs page for a component: `design-system-documentation-writer`.
Per-state button colours: `button-state-variant-designer`. Annotating a whole
screen: `accessibility-annotation-writer`.

## Workflow

```
1. JOB       -> one sentence: the job it does, and which component to use instead when it is the wrong choice
2. PATTERN   -> map it to an APG pattern (references/apg-patterns.md); the job decides, not the look
3. DRAFT     -> fill references/spec-template.md: anatomy, API, matrix, sizes, keyboard, ARIA, content, tokens, motion
4. DECIDE    -> resolve the decisions below explicitly; write each one into the spec with its reason
5. EDGES     -> walk references/edge-case-catalogue.md with real worst-case content
6. REVIEW    -> run references/spec-review-checklist.md; no high findings before handoff
7. SIGN-OFF  -> engineering (API), accessibility (keyboard/ARIA), content design (limits), QA (matrix = test cases)
```

Ask for what you can't infer: platforms (web, iOS, Android), the existing token names, and the real content. Don't invent
token names. Propose new ones and mark them as proposals.

## Decisions a Senior Designer Makes Explicitly

| Decision | Rule |
|----------|------|
| New component or variant? | Variant when anatomy and behaviour match. New component when the keyboard model or semantics differ (a toggle button is not a switch) |
| Variant enum vs booleans | One `variant` enum beats `primary`/`danger`/`ghost` booleans that can contradict each other |
| Prop vs slot | Strings and icons are props. Arbitrary content is a slot, and the spec says what is allowed in it |
| Controlled vs uncontrolled | Form-like components support both (`value` + `onChange`, `defaultValue`) |
| Disabled | Last resort. Prefer enabled + validation. If disabled, say how users learn why (aria-disabled + helper text) |
| Matrix size | Variant x state cells over about 60 means the component does two jobs: split it |
| Target size | 24x24 CSS px is the WCAG 2.2 AA floor (2.5.8). Design to 44pt (iOS) / 48dp (Android) for touch |
| Focus movement | Every open, close and delete says where focus lands; never on `<body>` |

## Output

A spec: the filled template in Markdown, plus an Open questions list with owners. For a review: findings as
`CODE [severity] problem -> fix`, high first, ending with `N findings: H high, M medium, L low. Ready for handoff: yes/no.`

## Additional Resources

| File | Content |
|------|---------|
| [spec-template.md](references/spec-template.md) | The spec skeleton to fill in, section by section |
| [apg-patterns.md](references/apg-patterns.md) | Anatomy, states, keyboard table and ARIA for 16 APG patterns |
| [spec-review-checklist.md](references/spec-review-checklist.md) | 14 review checks (CS001-CS014) with how to spot and fix each |
| [spec-anatomy.md](references/spec-anatomy.md) | What each section must answer, weak vs strong, focus management, sign-off |
| [component-api-design.md](references/component-api-design.md) | Props, variants, slots, composition, naming, controlled state, deprecation |
| [edge-case-catalogue.md](references/edge-case-catalogue.md) | Content, layout, state, input and platform edge cases |
