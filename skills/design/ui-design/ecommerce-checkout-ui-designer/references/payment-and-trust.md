# Payment and Trust

## Card fields

| Field | Spec |
|-------|------|
| Card number | `inputmode="numeric"`, `autocomplete="cc-number"`, formatted in groups as typed, brand icon detected from the number, Luhn check on blur |
| Expiry | One field "MM / YY", `autocomplete="cc-exp"`, auto-insert the slash |
| Security code | `autocomplete="cc-csc"`, 3-4 digits, hint showing where to find it |
| Name on card | `autocomplete="cc-name"`; pre-fill from the delivery name |

Use the payment provider's hosted fields or elements (PCI scope), styled with your tokens. Accept paste; don't split the
card number into four inputs.

## Wallets and alternatives

- Apple Pay / Google Pay / PayPal / Shop Pay and local methods (iDEAL, Bancontact, UPI, Pix, Klarna...) by market.
- Show wallets that the device supports (Apple Pay on Safari/iOS only).
- Buy now, pay later: show instalment cost honestly near the price; never default to it.

## Strong customer authentication (SCA) and 3-D Secure

- In the EEA and UK, PSD2 requires strong customer authentication for many online card payments; card issuers trigger
  3-D Secure challenges.
- Show the challenge in a modal/iframe from the provider with your context around it ("Your bank may ask you to confirm
  this payment").
- Handle outcomes: success, failed authentication (let them retry or choose another method), timeout.

## Payment failures

| Failure | Message direction |
|---------|-------------------|
| Declined | "Your card was declined. Try another card or payment method." (don't speculate on the reason) |
| Insufficient funds | Provider gives a code: same neutral message, offer alternatives |
| Expired / wrong CVC | Point to the field: "Check the security code" |
| Network error | "Payment didn't go through. You haven't been charged." + retry |

Keep the order and address; never show "Your order failed" when the payment is still pending; show pending state.

## Trust cues

- Place reassurance next to the card fields: lock icon with "Secure payment", accepted card logos, the provider's name.
- The page itself must look consistent and polished; sudden style changes at payment raise doubt.
- Clear returns policy and support contact reachable from checkout.
- Reviews, guarantees and badges help most for unfamiliar brands; don't clutter the payment step with them.

## Regulation and dark patterns

| Pattern | Status (examples) |
|---------|-------------------|
| Pre-ticked add-ons or extra paid services | Prohibited in the EU (Consumer Rights Directive requires express consent for additional payments) and in the UK |
| Drip pricing / hidden mandatory fees revealed late | Targeted by the US FTC rule on unfair or deceptive fees (live-event tickets and short-term lodging, 2025) and the UK DMCC Act 2024; bad practice everywhere |
| Fake urgency or scarcity | Unfair commercial practice under EU and UK law; FTC enforcement in the US |
| Hard-to-cancel subscriptions | Cancellation must be as easy as sign-up under many regimes (EU, UK, US state laws) |
| Confirmshaming ("No thanks, I don't like saving money") | Manipulative; avoid |

Check current rules for each market with legal counsel; the safe design default is honest, opt-in, upfront pricing.
