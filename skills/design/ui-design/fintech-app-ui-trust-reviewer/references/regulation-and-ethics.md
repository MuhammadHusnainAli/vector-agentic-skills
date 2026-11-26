# Regulation and Ethics in Fintech UI

This is design guidance, not legal advice. Confirm requirements for each market and product with compliance.

## Regimes that shape interfaces (examples)

| Regime | What it means for UI |
|--------|----------------------|
| UK FCA Consumer Duty (2023) | Firms must show consumers understand products and that communications support good outcomes: test comprehension, avoid sludge and exploiting biases |
| EU/UK PSD2 strong customer authentication | Two-factor authentication for many payments and account access; exemptions (low value, trusted beneficiaries) shape where friction appears |
| EU Instant Payments Regulation | Verification of Payee before instant credit transfers |
| US Regulation E (EFTA) | Error-resolution rights and disclosures for electronic transfers; receipts and periodic statements |
| US Truth in Lending (Reg Z) | APR and finance charge disclosures for credit, prominent and before commitment |
| Securities and investing rules (e.g. FINRA, SEC, FCA) | Risk warnings; scrutiny of gamified "digital engagement practices" |

## Disclosure design

- Put key facts at the decision point in plain language: cost, APR, fees, risk, cancellation rights.
- Use a short summary box (key facts) with links to full terms, not the reverse.
- Show worked examples ("Borrow $1,000 over 12 months: total to repay $1,108.40").
- Test comprehension with real users ("What will this cost you if you pay late?").

## Dark patterns in finance

| Pattern | Example | Fix |
|---------|---------|-----|
| Costly default | Faster transfer with a fee pre-selected | Default to the free option, or ask neutrally |
| Hidden FX margin | "No fees" with a poor exchange rate | Show the rate vs mid-market and total cost |
| Drip fees | Fees appear after entering card details | All costs on the review screen |
| Gamified trading | Confetti after trades, streaks, push notifications nudging trades | Neutral confirmations; risk information; no rewards for frequency |
| Roach motel | Easy sign-up, cancellation by phone only | Cancel in app, same number of steps as sign-up |
| Nagging upsell | Repeated credit offers after declining | Respect the decision for a defined period |
| Confirmshaming | "No, I don't want to protect my money" | Neutral decline wording |
| Pre-approved framing | "You're approved!" before a hard check | Accurate status ("Check your rate; this won't affect your credit score") |

## Inclusive money design

- Plain language at a reading age around 9-11 for core flows; explain jargon in place.
- Support for vulnerable customers: easy access to help, extra time, ways to add a trusted person, gambling blocks.
- Accessibility: screen readers announce amounts correctly (currency and sign), no colour-only meaning, captions on video.
