---
name: fintech-app-ui-trust-reviewer
description: "Review banking, payments, wallet, lending and investing interfaces for the trust signals and safety that money products need: unambiguous balances (available vs current vs pending), money formatting per locale and currency with exact amounts, transaction states and timelines (pending, processing, completed, failed, reversed), confirmation of irreversible actions with recipient, amount, fees, exchange rate and arrival time, fees and FX spreads shown before commit, payee verification and scam warnings, friction proportional to risk, security UX (biometrics, step-up authentication, session timeouts with warning, device management, masked identifiers), error and dispute paths, and disclosures written for comprehension (APR, fees, risks) under regimes such as the UK Consumer Duty, PSD2 and US Regulation E. Flags dark patterns: hidden fees, costly defaults, gamified risky trading, hard cancellation. Use when designing or auditing a fintech, banking, payments, crypto, lending or investing product."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Fintech App UI Trust Reviewer

In money products every ambiguity costs trust, and often money too. "Balance: $1,240" when $300 is pending. A transfer
button that sends immediately with no review. A fee that appears on the statement but never on screen. A "processing"
state that lasts three days with no explanation. People can't undo these mistakes, and they remember them. This skill
reviews money interfaces the way an experienced fintech design lead and a compliance partner would together.

## Trigger Conditions

Activate this skill when the user:
- Designs or reviews a banking, payments, wallet, card, lending, investing or crypto product
- Designs transfers, payments, top-ups, withdrawals, trades, loan applications or subscriptions
- Needs balance displays, transaction lists, statuses or receipts
- Wants a trust, safety or dark-pattern review before launch

Checkout and card payment fields: [ecommerce-checkout-ui-designer](../ecommerce-checkout-ui-designer/SKILL.md). Forms: [form-layout-designer](../form-layout-designer/SKILL.md). Dashboards:
[dashboard-layout-designer](../dashboard-layout-designer/SKILL.md).

## Workflow

```
1. MONEY     -> every place money is shown: balances, amounts, fees, rates, limits (references/money-display-and-states.md)
2. STATES    -> transaction lifecycle per product, with timelines and what the user can do in each state
3. FLOWS     -> each money movement: entry -> review -> authenticate -> result (references/money-flows-and-safety.md)
4. RISK      -> friction proportional to risk: new payees, large amounts, unusual patterns, scam warnings
5. SECURITY  -> login, step-up, session, devices, notifications, masking
6. ERRORS    -> failures, reversals, disputes, support access
7. DISCLOSE  -> fees, APR, risks, terms: comprehension, not fine print (references/regulation-and-ethics.md)
8. REVIEW    -> checklist below; test with people who are anxious about money, not just power users
```

## Review Checklist

Report as `CODE [severity] screen: problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| FT001 | high | Irreversible money movement without a review step showing recipient, amount, fees, rate and arrival time |
| FT002 | high | Fees, FX margins or total cost revealed only after commit (or only on statements) |
| FT003 | high | Ambiguous balance: available vs current vs pending not distinguished where they differ |
| FT004 | high | Transaction status unclear or missing (no pending state, no failure reason, no timeline) |
| FT005 | high | No payee verification or scam warning for new payees and high-risk payments |
| FT006 | high | Dark patterns: costly defaults, hidden fees, gamified trading rewards, cancellation harder than sign-up |
| FT007 | medium | Amount formatting errors: rounding, missing currency, ambiguous sign, wrong locale separators |
| FT008 | medium | Session timeout without warning and extension; data lost on re-authentication |
| FT009 | medium | Full account or card numbers shown by default (mask to last 4; reveal on request with auth) |
| FT010 | medium | Errors that blame or don't say whether money moved ("Something went wrong") |
| FT011 | medium | Disclosures (APR, fees, risk) in fine print or behind links at the moment of decision |
| FT012 | low | No receipt or reference number after a transaction; no way to share or download it |
| FT013 | low | Support and dispute paths hard to find from a transaction |

## Output

Findings by severity with fixes; corrected copy for amounts, statuses and errors; a recommended review-screen layout for
money movements; and items that need compliance or legal confirmation, marked as such.

## Additional Resources

| File | Content |
|------|---------|
| [money-display-and-states.md](references/money-display-and-states.md) | Balances, amount formatting, signs and colour, transaction states, lists and receipts |
| [money-flows-and-safety.md](references/money-flows-and-safety.md) | Transfer flow anatomy, review screens, friction by risk, scam prevention, security UX, errors |
| [regulation-and-ethics.md](references/regulation-and-ethics.md) | Disclosure design, regimes that shape UI (Consumer Duty, PSD2, Reg E, TILA), dark patterns in finance |
