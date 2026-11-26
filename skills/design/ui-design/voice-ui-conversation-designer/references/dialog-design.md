# Dialog Design

## When voice fits

| Good fit | Poor fit |
|----------|----------|
| Hands or eyes busy (driving, cooking) | Comparing many options (products, flights) |
| Short commands and quick answers (timers, weather, calls) | Browsing, reading long content |
| Simple input that's long to type (addresses, messages) | Privacy-sensitive output in shared spaces |
| Accessibility (vision or motor impairments) | Precise input (codes, spellings) without fallback |

## Cooperative principle (Grice's maxims) in voice

| Maxim | In practice |
|-------|-------------|
| Quantity | Say enough, not more: answer first, details on request |
| Quality | Don't guess; say what you don't know |
| Relation | Stay on the user's goal; no unrelated promotions |
| Manner | Clear, brief, ordered: put the new information last, the question at the very end |

## Sample dialogs first

Write scripts like a play before drawing flows:

```
User:   Book a table at Lucca for Friday.
System: For how many people?
User:   Four, around 8.
System: I can do 7:45 or 8:30 on Friday for 4. Which works?
User:   8:30.
System: Done: Lucca, Friday at 8:30 for 4. I've sent the confirmation to your phone.
```
Then write messy versions: the user gives everything at once, changes their mind, goes silent, asks something unrelated,
says a restaurant that doesn't exist. Read them aloud with someone; awkwardness shows up immediately.

## Intents and slots

| Concept | Example |
|---------|---------|
| Intent | BookTable |
| Slots | restaurant (required), date (required), time (required), party_size (required), seating (optional) |
| Utterances | "Book Lucca for Friday", "Table for four tomorrow at 8", "Can I get a reservation", "I need dinner for 2 tonight" |
| Entities and synonyms | party_size: "two", "a couple of us", "me and my wife" (2); date: "tonight", "this Friday", "the 12th" |

- Collect only missing slots; accept over-answering (fill several slots from one utterance).
- Confirm ambiguous values ("Friday the 5th or Friday the 12th?").
- Use 20-50 realistic utterances per intent from research or logs, not variations of one sentence.

## Persona

Define: name (or none), personality traits (helpful, calm, concise), vocabulary level, how it apologises, whether it
uses humour (never in errors or sensitive moments), and words it never uses. Consistency matters more than charm.

## Multimodal devices

On devices with screens (smart displays, cars, TVs, phones), voice carries the conversation and the screen carries detail:
lists, images, comparisons. Speak the summary ("I found 3 restaurants nearby; the closest is Lucca") and show the list.
Don't read everything on the screen.

## LLM-powered voice agents

- Ground answers in approved sources; say when information isn't available rather than improvising.
- Keep turns short even when the model can say more; offer "Want details?"
- Confirm before any action with consequences; read back key values.
- Handle interruptions (barge-in) mid-response and resume or stop cleanly.
- Latency: start speaking quickly (stream a short acknowledgement) instead of silence while generating.
- Guardrails for out-of-scope requests and sensitive topics, with a handoff to humans where it matters.
