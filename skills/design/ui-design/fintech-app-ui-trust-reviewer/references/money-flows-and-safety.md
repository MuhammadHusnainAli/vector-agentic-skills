# Money Flows and Safety

## Anatomy of a money movement

```
Enter -> Review -> Authenticate -> Result -> Receipt
```

| Step | Must show |
|------|-----------|
| Enter | Recipient (with verified name), amount with currency, available balance, limits |
| Review | Recipient, amount sent, fees, exchange rate (and margin vs mid-market if applicable), amount received, arrival time, source account; edit links |
| Authenticate | Biometric or PIN; step-up for risky transactions; explain why if extra checks |
| Result | Clear outcome; if pending, what happens next and when |
| Receipt | Reference, details, share/download |

The final button names the action and the amount: "Send $250.00".

## Friction proportional to risk

| Risk signal | Added friction |
|-------------|----------------|
| New payee | Payee name check, warning about scams, confirmation |
| Large or unusual amount | Step-up authentication, a pause with a scam prompt, optional delay |
| Payment purpose commonly used in scams (investment, "safe account") | Specific warning text and questions |
| Changed payee details (invoice redirection) | Strong warning, verify through another channel |
| Low risk, known payee, small amount | Minimal friction (biometric only) |

Avoid uniform friction: warnings on every payment train people to click through.

## Payee verification and scams

- Name-matching services (UK Confirmation of Payee; the EU Verification of Payee under the Instant Payments Regulation)
  show whether the account name matches: match, close match (show the actual name), no match (strong warning).
- Authorised push payment scams: people are tricked into sending money themselves. Effective warnings are specific to
  the stated purpose, interrupt at the right moment, and say exactly what scammers say ("Your bank will never ask you to
  move money to a safe account").
- Offer a "pause and check" option and an easy way to call the bank from the warning.

## Security UX

| Area | Practice |
|------|----------|
| Login | Biometric with PIN/password fallback; passkeys where supported |
| Step-up | Re-authenticate for sensitive changes (new payee, limits, contact details, device added) |
| Session timeout | Warn before expiry with "Stay signed in"; keep entered data after re-authentication (WCAG 2.2.1) |
| Devices | List signed-in devices, sign out remotely, notify on new device |
| Notifications | Real-time alerts for transactions and security events |
| Masking | Card and account numbers masked (last 4); reveal on request after auth; copy button for full number |
| Screenshots | Consider hiding sensitive data in app switcher previews |

## Errors

- Always say whether money moved: "No money has left your account" or "The payment is pending; you'll hear from us by 5 PM".
- Give the reason when known and the next step; avoid codes without explanation.
- Don't let a retry cause a duplicate payment: idempotent submits and a clear pending state.
