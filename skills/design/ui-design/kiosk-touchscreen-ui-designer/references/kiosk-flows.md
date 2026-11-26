# Kiosk Flows

## Attract and start

- Attract loop shows what the kiosk does ("Order here", "Check in for your flight") and invites touch anywhere.
- First touch starts; the first screen asks the most important question (language, or dine-in vs takeaway).
- Accessibility entry visible from the start screen (headphone icon, "Accessibility" button in the reach zone).

## Language

- First screen or a persistent control on every screen; language names in their own language ("Español", "Français"),
  optionally with flags; remember nothing between users.

## Flow patterns

| Kiosk | Flow |
|-------|------|
| Food ordering | Start -> dine in/takeaway -> categories -> item -> customise -> cart -> pay -> number/receipt |
| Ticketing | Start -> destination (popular list + search) -> date/time -> tickets/passengers -> review -> pay -> print/QR |
| Check-in | Start -> identify (scan booking/ID/QR) -> confirm details -> options (bags, seats) -> boarding pass/bag tags |
| Wayfinding | Start -> search or category -> map with route -> send to phone (QR) |

- 3-6 steps, linear, with a visible progress indicator.
- Cart or summary always visible on ordering kiosks.
- Upsells limited to one, easy to skip, never pre-selected.

## Input alternatives

| Instead of typing | Use |
|-------------------|-----|
| Booking reference | Scan QR/barcode, NFC, ID card |
| Destination | Popular destinations list + alphabetical list + search with large keyboard and suggestions |
| Name, email | Skip; or QR to phone to enter details there |
| Payment | Contactless and wallets first, then card insert, then cash if supported |

## Timeouts and reset

| Moment | Behaviour |
|--------|-----------|
| No input for about 30-60 s (depending on task) | "Are you still there?" with a countdown (about 20-30 s) and a large "Continue" button; sound cue |
| Countdown ends | Full reset: clear all data, return to attract loop |
| After completion | Thank-you screen with receipt option, then automatic reset after a short delay |
| During payment | Pause the idle timer; payment terminals have their own timeouts |

Longer timeouts in accessibility mode (and adjustable), as WCAG 2.2.1 requires a way to extend time limits.

## Errors and help

- Plain messages with the fix ("Card not read. Try tapping again or insert your card").
- "Help" calls staff (light, sound or staff notification) and shows "Help is on the way".
- Hardware failures (printer out of paper) handled with alternatives (QR receipt, email).
- Never trap: Back and Start over on every screen; Start over asks for confirmation if a cart has items.

## Receipts and confirmation

- Show the order number large on screen; print or QR/email option.
- Next steps: where to wait, where to collect, gate and time.
