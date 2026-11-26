# Money Display and States

## Balances

| Term | Meaning | Display |
|------|---------|---------|
| Available | What can be spent or sent now | The headline number for spending decisions |
| Current / ledger | Settled balance, before pending items | Secondary, labelled |
| Pending | Authorised but not settled (card holds, incoming transfers) | Listed separately with expected dates |
| Reserved / on hold | Held for disputes, deposits | Explain why and until when |

Label the headline number explicitly ("Available $1,240.18"). When available and current differ, show both and the reason
("$300.00 pending").

## Amount formatting

| Rule | Example |
|------|---------|
| Format by locale, not by hand | en-US $1,234.56; de-DE 1.234,56 €; en-IN ₹1,23,456.00 |
| Use the currency's minor units | JPY has none (¥1,235); KWD has three (KWD 1.235) |
| Never round money silently | Show exact amounts; if abbreviating ($1.2M) on dashboards, exact on tap |
| Show currency whenever more than one is possible | "1,000.00 EUR -> 1,071.30 USD" |
| Sign and direction | "-$45.00" or "$45.00" in a debit column with label; incoming "+$1,200.00" |
| Colour is not the sign | Green/red plus a sign or label; colour-blind users and printouts lose colour |
| Tabular figures | `font-variant-numeric: tabular-nums` so columns align |
| Inputs | Numeric keypad with decimal; currency fixed outside the input; no float rounding in display |

Use `Intl.NumberFormat` (or platform equivalents) with the currency code; store amounts as integers in minor units.

## Transaction states

| State | Meaning | Show |
|-------|---------|------|
| Scheduled | Will run at a set date | Date, edit and cancel |
| Pending / processing | Submitted, not complete | Expected completion time, what happens next, cancel if possible |
| Requires action | Needs user (authentication, documents) | The action, deadline |
| Completed | Settled | Date and time, reference |
| Failed | Didn't happen | Reason in plain language, whether money moved, retry or alternative |
| Reversed / refunded | Undone after completion | Original and reversal linked, amounts and dates |
| Disputed | Under investigation | Case number, timeline, provisional credit if any |

Timelines ("Sent -> Received by bank -> Credited") help for slow rails (international, ACH, SEPA).

## Transaction list

- Merchant/counterparty name cleaned and recognisable, logo when available, category.
- Amount aligned right, signed; pending items marked and grouped at the top.
- Dates grouped ("Today", "Yesterday", "Mon 24 Nov").
- Search and filters (amount ranges, categories, dates); export.

## Receipts

Reference number, date and time with time zone, amounts including fees and FX rate, sender and recipient details (masked),
status, and share/download options.
