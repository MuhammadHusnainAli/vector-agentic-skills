---
name: ecommerce-checkout-ui-designer
description: "Design and audit e-commerce cart and checkout flows for conversion and trust: total cost visible early (shipping, tax, duties), guest checkout as the default path, express wallets (Apple Pay, Google Pay, PayPal, Shop Pay) placed first, the fewest form fields possible with address lookup and correct autocomplete, delivery options shown as dates and prices, payment fields with live formatting and brand detection, strong customer authentication (3-D Secure, PSD2) handled in flow, order summary always reachable on mobile, coupon fields that don't send people hunting, recoverable errors, post-purchase account creation, and dark patterns that are illegal or harmful (pre-ticked add-ons, drip pricing, fake urgency, forced continuity). Includes funnel analysis (step drop-off, revenue at stake) and experiment design. Reviews checkouts for forced accounts, late costs, excess fields and lost input. Use when designing, auditing or optimising a cart or checkout."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# E-commerce Checkout UI Designer

Checkout is where design decisions turn directly into revenue. Large-scale checkout research (Baymard Institute's
long-running benchmarks) keeps finding the same reasons people leave: costs that appear late, forced account creation,
long forms, unclear delivery, and doubts about the site's trustworthiness at the payment step. Most of these are design
decisions. This skill designs checkouts around those findings, audits existing ones, and turns funnel data into a
prioritised fix list.

## Trigger Conditions

Activate this skill when the user:
- Designs a cart, checkout, payment or order confirmation flow
- Has high cart or checkout abandonment, or a drop at a specific step
- Adds express payments, delivery options, subscriptions or international shipping
- Plans checkout experiments or reviews a checkout before launch

Form fields and validation in depth: `form-layout-designer`. Trust in money flows generally: `fintech-app-ui-trust-reviewer`.
Kiosk checkouts: `kiosk-touchscreen-ui-designer`.

## Workflow

```
1. FUNNEL    -> step-by-step drop-off from analytics (references/funnel-and-experiments.md)
2. COSTS     -> when does the user first see the full total? Move it earlier
3. ACCOUNT   -> guest path first; account creation after purchase (password only)
4. EXPRESS   -> wallets at the top of cart and checkout; they skip most fields
5. FIELDS    -> cut, combine, autofill: address lookup, one name field, no confirm-email (references/checkout-patterns.md)
6. DELIVERY  -> options with dates and prices; pickup; free-shipping threshold progress
7. PAYMENT   -> card fields, wallets, BNPL, SCA/3-D Secure, trust placement (references/payment-and-trust.md)
8. REVIEW    -> order summary, edit links, terms, final total with all costs
9. CONFIRM   -> confirmation page, email, account offer, tracking
10. AUDIT    -> checklist below; mobile first; test errors and slow networks
```

## Principles

| Principle | Practice |
|-----------|----------|
| No surprises | Shipping estimate in the cart; taxes and duties stated before payment; total never jumps on the last step |
| Guest by default | "Continue as guest" as prominent as sign-in; offer an account on the confirmation page |
| Ask less | Every optional field is a cost; derive what you can (city from postcode, card brand from number) |
| Keep the summary close | Items, total and delivery date visible or one tap away at every step |
| Errors never lose data | Failed payment keeps address and items; the message says what to do |
| Trust at the moment of doubt | Security cues and familiar payment logos beside card fields, not in the footer |
| Fair by design | No pre-ticked extras, no hidden fees, no fake timers |

## Review Checklist

Report as `CODE [severity] step: problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| CK001 | high | Total cost (shipping, tax, fees) first revealed at the last step |
| CK002 | high | Account creation required to buy |
| CK003 | high | Errors clear entered data, or payment failure sends the user back to the start |
| CK004 | high | Pre-ticked add-ons, insurance or subscriptions; hidden or drip-priced fees |
| CK005 | medium | More fields than needed (separate first/last name for a global audience, confirm email, company, phone without a reason) |
| CK006 | medium | No address lookup / autocomplete tokens; wrong keyboards (card number as type=number, no numeric inputmode) |
| CK007 | medium | Express wallets missing, or placed below the card form |
| CK008 | medium | Delivery shown as "3-5 business days" with no dates, or no cost until a later step |
| CK009 | medium | Order summary hidden on mobile with no way to see it |
| CK010 | medium | Prominent coupon field with no codes available (sends people to search for codes) |
| CK011 | medium | Security and payment trust cues far from the payment fields |
| CK012 | low | Confirmation page without order number, delivery date, what happens next and an account offer |
| CK013 | low | Fake urgency (countdowns that reset, invented low-stock messages) |

## Output

1. Funnel diagnosis: where people drop and the likely causes
2. Redesigned flow: steps, fields per step, express placement, summary behaviour
3. Field table (label, type, autocomplete, validation) and delivery and payment specs
4. Audit findings, prioritised by revenue impact and effort
5. Experiment plan for the uncertain changes

## Additional Resources

| File | Content |
|------|---------|
| [checkout-patterns.md](references/checkout-patterns.md) | Cart, flow structure, guest checkout, fields, address, delivery, review, confirmation, mobile |
| [payment-and-trust.md](references/payment-and-trust.md) | Card fields, wallets, BNPL, SCA and 3-D Secure, failures, trust cues, regulation and dark patterns |
| [funnel-and-experiments.md](references/funnel-and-experiments.md) | Funnel analysis, revenue at stake, prioritising, A/B test design and pitfalls |
