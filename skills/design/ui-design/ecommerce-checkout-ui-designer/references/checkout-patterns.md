# Checkout Patterns

## Cart

- Line items with image, name, variant (size, colour), quantity stepper, price, remove (with undo).
- Shipping estimate (by detected location or postcode entry) and the total; free-shipping threshold progress
  ("Add $12 for free delivery").
- Express wallet buttons above the main "Checkout" button.
- Save for later instead of delete-only; stock and delivery warnings per item.

## Flow structure

| Structure | Fits |
|-----------|------|
| One page (sections stacked) | Few fields, returning users, digital goods |
| Accordion steps on one page | Most retail; shows progress and allows editing earlier steps |
| Multi-page steps (Contact -> Delivery -> Payment -> Review) | Complex delivery, international, high-value orders |

Common order: Contact (email) -> Delivery (address, method) -> Payment -> Review/Place order. Ask for email first: it
enables abandoned-checkout recovery and order updates.

## Guest checkout

- Equal prominence: "Continue as guest" next to "Sign in". Detect returning customers by email and offer sign-in inline
  without blocking.
- After purchase: "Save your details for next time: create a password" on the confirmation page.

## Fields (typical minimum for physical goods)

| Field | Notes |
|-------|-------|
| Email | type=email, autocomplete=email |
| Full name | One field globally (`name`), or given/family if the carrier requires |
| Address | Lookup/autocomplete, then editable fields; `address-line1`, `address-line2` (collapsed "Add apartment, suite"), `postal-code`, `address-level2`, `address-level1`, `country` |
| Phone | Only if the carrier needs it; say why ("For delivery updates") |
| Billing address | "Same as delivery" checked by default |

Remove: confirm email, title/salutation, company (unless B2B), fax, date of birth (unless legally required).

## Delivery options

- Show each option with price and an estimated date range ("Arrives Tue 2 Dec - Thu 4 Dec").
- Default to the most chosen option, not the most expensive.
- Pickup points and store pickup with map/list and opening hours.
- Cut-off times ("Order in the next 3 h for delivery tomorrow") only when true.

## Review step

- All items, delivery address, method and date, payment method (last 4 digits), costs broken down, total.
- "Change" links per section that return to the review after editing.
- Terms and consent near the button; marketing consent unticked by default.
- The button states the action and amount: "Pay $84.20" / "Place order".

## Confirmation

- Order number, items, total, delivery date, where updates will be sent, how to change or cancel.
- Account creation offer, app download only if relevant.
- Confirmation email sent immediately with the same information.

## Mobile

- Sticky bottom bar with total and the primary action; collapsible order summary at the top showing the total.
- Correct keyboards and autofill; large targets; no hover-dependent info.
- Wallet buttons visible without scrolling at the start of checkout.
- Test on a slow network: show progress on "Pay" and prevent double submission.
