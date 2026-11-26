# States and Acceptance Criteria

## State matrix (per screen)

| State | Trigger | Designed? | Frame |
|-------|---------|-----------|-------|
| Default (typical data) | Normal load | | |
| Loading (first load) | Data pending | | |
| Loading (refresh / pagination) | Subsequent loads | | |
| Empty (first use) | No data ever | | |
| Empty (filtered / search) | No results | | |
| Partial | Some data failed or still loading | | |
| Error | Request failed | | |
| No permission | User lacks access | | |
| Offline | No connection | | |
| Success / confirmation | After an action | | |
| Destructive confirmation | Before irreversible action | | |

## Edge cases

| Category | Cases |
|----------|-------|
| Content length | Shortest, typical, longest (names, titles, descriptions), translated (+40%) |
| Counts | 0, 1, 2, many, maximum (pagination or truncation kicks in) |
| Numbers | Zero, negative, very large, decimals, currency and units per locale |
| Dates | Today, yesterday, future, far past, time zones, date formats |
| Media | Missing image, wrong aspect ratio, slow loading |
| Users | No avatar, long name, deleted user, external user |
| Permissions | Viewer vs editor vs admin views |
| Concurrency | Item changed or deleted by someone else while viewing |
| Input | Paste, autofill, emoji, very long input, invalid formats |

## Acceptance criteria

Write per user story, in Given / When / Then, testable without asking the designer.

```
Story: As a shop owner, I can refund part of an order.

AC1 Given an order with 3 items, when I select 2 items and choose Refund,
    then the review screen shows those 2 items, their total, and the shipping refund toggle (off by default).
AC2 Given the refund total exceeds the remaining refundable amount,
    when I try to continue, then I see "You can refund up to $42.10" and Continue is not submitted.
AC3 Given the refund succeeds, then I see the confirmation with the refund ID,
    focus moves to the confirmation heading, and the order status shows "Partially refunded".
AC4 Given the payment provider returns an error, then I see "Couldn't process the refund. No money was moved.
    Try again" and my selection is kept.
AC5 At 360 px wide, the item list stacks and the total stays visible above the Continue button.
```

Bad criteria: "Refund flow works", "Looks like the design", "Is accessible". Replace with observable outcomes.

## Data rules checklist

- Formats: dates, numbers, currency, phone, addresses per locale
- Validation: required, min/max, patterns, cross-field rules; message per rule
- Limits: max characters per field, max items, file sizes and types
- Sorting and filtering defaults; persistence of filters
- Pagination: page size, infinite scroll vs pages, "load more" behaviour
- Error codes mapped to user messages
- Empty values: how null or missing fields display ("-", "Not set", hidden)
