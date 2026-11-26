# Errors and Confirmation

## Error types

| Type | Cause | Handling |
|------|-------|----------|
| No-input | Silence (timeout about 5-8 s) | Reprompt with more help |
| No-match | Speech not understood | Reprompt with examples |
| Partial match | Some slots understood | Confirm what was understood, ask for the rest |
| Out of scope | Valid request the system can't do | Say so, offer what it can do |
| System error | Back-end failure | Apologise briefly, say what to do, don't blame the user |

## Escalating reprompts

| Attempt | No-input | No-match |
|---------|----------|----------|
| 1 | "What date would you like?" (rapid reprompt, shorter) | "Sorry, what date was that?" |
| 2 | "You can say a date, like 'this Friday' or 'December 12th'." | "I didn't get that. Try a date like 'next Monday'." |
| 3 | Offer an alternative: transfer, send a link, or exit | Same: change strategy, don't loop |

Never repeat the identical prompt; never loop more than about 3 times.

## Confirmation strategy by risk

| Risk | Strategy | Example |
|------|----------|---------|
| Low, easily undone | Implicit (fold the value into the next turn) | "Okay, a 10-minute timer. Starting now." |
| Medium | Implicit with easy correction | "Booking for 4 on Friday at 8:30. Anything else?" (user can say "No, 5 people") |
| High, irreversible or costly | Explicit yes/no confirmation with key values | "That's $250 to Alex Kim from checking. Should I send it?" |
| Recognition uncertain | Confirm the uncertain value | "Did you say Lucca or Luca's?" |

Accept natural yes/no variants: "yeah", "sure", "go ahead", "nope", "wait". On "no", ask what to change, don't restart.

## Universal commands

Always available: help, repeat, go back / start over, cancel / stop, and for IVRs "agent" / "representative" (and 0).
Help is contextual: explain what the user can say in this state.

## IVR specifics

- Lead with the most common reasons for calling; detect intent from natural speech ("Tell me in a few words why you're
  calling").
- Transfer to a human with context (don't make callers repeat themselves).
- Give wait time estimates and callback options.
- DTMF (keypad) fallback for noisy environments and privacy (PINs, account numbers).

## Exits

- End clearly: "Done. Enjoy dinner." Don't ask "Anything else?" after every task unless the context suggests a follow-up.
- On repeated failure, exit gracefully with an alternative ("I'll send you a link to finish this on your phone").
