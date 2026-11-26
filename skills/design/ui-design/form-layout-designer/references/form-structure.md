# Form Structure

## Question protocol

Before designing, list every field with:

| Field | Who uses the answer | What for | Required? | What if we didn't ask? | Decision |
|-------|---------------------|----------|-----------|------------------------|----------|
| Phone | Delivery courier | Contact on failed delivery | Optional | Courier emails instead | Keep, optional |
| Company size | Sales | Lead scoring | No | Enrich from domain later | Remove |
| Title (Mr/Ms) | Nobody | - | - | - | Remove |

Fields without an owner and a use get removed. Fields needed later (profile details, preferences) move to after sign-up.

## Single page, multi-step or one thing per page

| Situation | Pattern |
|-----------|---------|
| Up to about 6-8 short fields, one topic | Single page |
| Distinct topics (account, shipping, payment) | Multi-step, one topic per step |
| Complex, branching, high-stakes (government, insurance, loans) | One thing per page (one question or tightly related group per screen) |
| Long forms people fill in over days | Multi-step + save and resume + check-your-answers |

One-thing-per-page (GOV.UK pattern) makes branching simple, errors local, and mobile easy, at the cost of more page loads.

## Multi-step rules

- Show progress as "Step 2 of 4: Delivery" text; a numbered stepper only when steps are few and fixed.
- Don't number steps in branching flows (the total changes); use section names.
- Back must keep entered data. Browser back must work.
- End with a check-your-answers page with Change links for anything consequential.
- Save on every step; for long forms offer "Save and come back later" with a clear way to return.

## Conditional questions

- Reveal follow-up questions directly under the answer that triggers them (radio with conditional reveal), at most one
  level deep.
- Deeper branching belongs on separate pages.
- Hidden fields are not submitted and not validated.

## Layout grid

- Max form width about 500-640px even on wide screens; centring a narrow form is fine.
- Vertical rhythm: label-to-field 4-8px, field-to-next-label 24-32px, group-to-group 40-48px.
- Button row: primary first (left-aligned with fields) or per the product convention; never full-width on desktop forms
  that sit in a narrow column next to whitespace, full-width on mobile is fine.

## Accessibility structure

- `<form>` with a heading; each group in `fieldset` + `legend`.
- Labels associated with `for`/`id`; hints and errors with `aria-describedby`.
- `required` (or `aria-required="true"`) on required fields; visible "(optional)" text too.
- Focus order follows the visual order. No positive `tabindex`.
- Time limits: warn before session timeout and allow extending (WCAG 2.2.1); keep entered data.
