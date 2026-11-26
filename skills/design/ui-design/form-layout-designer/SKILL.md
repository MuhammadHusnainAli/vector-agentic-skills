---
name: form-layout-designer
description: "Design forms people finish: question protocol (why each field exists), single-column layout with labels above fields, field widths that signal expected length, grouping with fieldset and legend, required vs optional marking, the right input type, inputmode and autocomplete token for every field (names, email, phone, address, dates, passwords, one-time codes, payment), validation timing (on blur after first input, on submit with an error summary), error messages that say how to fix it, multi-step and one-thing-per-page flows, progress indicators, conditional questions, save and resume, and the WCAG 2.2 form criteria (1.3.5, 3.3.1-3.3.4, 3.3.7 redundant entry, 3.3.8 accessible authentication). Reviews forms for placeholder-as-label, multi-column layouts, missing or wrong autocomplete, split fields, paste blocking, hidden password rules, vague errors and disabled submit buttons. Use when designing or reviewing a sign-up, checkout, onboarding, settings or data-entry form."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Form Layout Designer

Every field costs the user time, and some users leave because of it. A senior form designer starts by deleting questions,
then makes the rest unambiguous: one column, labels above, correct keyboard and autofill, errors that say how to fix them.
Visual styling comes last. This skill designs forms from the question list up and reviews existing ones.

## Trigger Conditions

Activate this skill when the user:
- Designs a sign-up, login, checkout, onboarding, application, settings or data-entry form
- Asks about form layout, labels, validation, error messages or multi-step flows
- Reviews a form for usability, conversion or accessibility
- Has a form with high abandonment or many support tickets about input errors

Checkout specifically: [ecommerce-checkout-ui-designer](../ecommerce-checkout-ui-designer/SKILL.md). Text field component spec: [ui-component-spec-writer](../ui-component-spec-writer/SKILL.md).

## Workflow

```
1. QUESTIONS -> for each field: who uses the answer, what for, what if we don't ask (references/form-structure.md)
2. CUT       -> remove, defer to later, or derive (city from postcode, card type from number)
3. ORDER     -> conversation order; group related fields; easy questions first
4. FLOW      -> one page, multi-step or one-thing-per-page (decision table in form-structure.md)
5. FIELDS    -> type, inputmode, autocomplete, width, format hints (references/field-patterns.md)
6. ERRORS    -> timing, message wording, error summary (references/validation-and-errors.md)
7. LAYOUT    -> single column, labels above, buttons aligned to the fields' left edge, primary action last
8. REVIEW    -> run the checklist below
```

## Layout Rules

| Rule | Why |
|------|-----|
| One column | Multi-column forms get fields skipped and are read in the wrong order. Exception: short related pairs (city + postcode, expiry + CVC) |
| Labels above fields | Fastest to scan, survive translation and zoom, work on narrow screens |
| Width matches expected input | A postcode field 4 characters wide says "short answer"; a full-width postcode field invites the full address |
| Hints between label and field | Placed where they are read before typing; linked with `aria-describedby` |
| Mark the minority | If most fields are required, mark optional ones with "(optional)"; asterisks need a legend and are often missed |
| Group with fieldset + legend | Radio groups, checkbox groups, addresses and date parts need a group label for screen readers |
| Primary action after the last field | Aligned with the fields; secondary actions visually weaker; no Reset button |
| Submit stays enabled | A disabled submit doesn't say what's wrong. Validate on submit and show the summary |

## Review Checklist

Report as `CODE [severity] problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| FL001 | high | Placeholder used as the label, or no programmatic label (WCAG 1.3.1, 3.3.2) |
| FL002 | high | Errors shown only by colour, not linked to the field (`aria-describedby`), or not announced (WCAG 1.4.1, 3.3.1) |
| FL003 | high | Paste blocked in password or code fields, or a cognitive test with no alternative (WCAG 3.3.8) |
| FL004 | high | Personal-data fields without the right `autocomplete` token (WCAG 1.3.5) |
| FL005 | medium | Multi-column layout of unrelated fields |
| FL006 | medium | Wrong keyboard: no `type=email` / `type=tel` / `inputmode=numeric` where it applies; `type=number` for codes, card numbers or postcodes |
| FL007 | medium | Error messages that don't say how to fix it ("Invalid input") |
| FL008 | medium | Validation on every keystroke before the user finishes, or errors on fields not yet touched |
| FL009 | medium | Password rules hidden until failure; no show-password option |
| FL010 | medium | Asking again for information already given in the same process (WCAG 3.3.7) |
| FL011 | medium | Disabled submit button as the only validation feedback |
| FL012 | medium | Split fields where one works (phone in 3 boxes, name in title/first/middle/last for a global audience) |
| FL013 | low | Questions with no clear owner or use (question protocol fails) |
| FL014 | low | Required/optional not indicated, or asterisks with no legend |

## Output

1. Question protocol table: field, why we ask, who uses it, required/optional/remove
2. Field table: label, hint, type, inputmode, autocomplete, width, validation rule, error message
3. Layout: page/step breakdown, grouping, button placement, progress indicator if multi-step
4. Review findings, if reviewing

## Additional Resources

| File | Content |
|------|---------|
| [field-patterns.md](references/field-patterns.md) | Names, email, phone, address, dates, passwords, codes, payment, choice fields; autocomplete token list |
| [validation-and-errors.md](references/validation-and-errors.md) | When to validate, message formulas, error summary, success states, accessibility markup |
| [form-structure.md](references/form-structure.md) | Question protocol, single page vs steps, one thing per page, progress, conditional reveal, save and resume |
