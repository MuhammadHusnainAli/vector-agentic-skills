---
name: voice-ui-conversation-designer
description: "Design voice and conversational interfaces that people can use without a screen: when voice is the right channel, sample dialogs before flows, turn-taking and the cooperative principle, prompts that are short, end with the question and offer no more than three options, intents, slots and entity design with real utterance variety, confirmation strategy by risk (implicit, explicit, none), error handling with escalating no-input and no-match reprompts, help, barge-in and graceful exits, persona, latency and earcons, multimodal devices, LLM voice agents (grounding, interruptions, confirmation), SSML and spoken duration, privacy and speech accessibility. Reviews scripts for long prompts, buried questions, missing error handling, dead ends and unconfirmed risky actions. Use when designing or reviewing a voice assistant, phone IVR, smart speaker skill, in-car voice or voice agent."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Voice UI Conversation Designer

Voice has no screen to scan, no back button and no visible state. Everything has to fit in short-term memory, in time,
in the order it's spoken. People don't read voice prompts, they hear them once. They answer in ways no designer predicted,
interrupt, go quiet, or ask for something the system can't do. This skill designs conversations from sample dialogs,
writes prompts that work when heard, plans every error path, and reviews scripts and flows the way an experienced
conversation designer would.

## Trigger Conditions

Activate this skill when the user:
- Designs a voice assistant, smart speaker skill/action, phone IVR, in-car voice or voice agent (including LLM-based)
- Writes prompts, reprompts or error messages for voice
- Decides intents, slots and confirmations for a voice task
- Reviews a voice flow or script for usability

Car contexts: [automotive-hmi-ui-designer](../automotive-hmi-ui-designer/SKILL.md). Kiosk audio mode: [kiosk-touchscreen-ui-designer](../kiosk-touchscreen-ui-designer/SKILL.md).

## Workflow

```
1. FIT       -> is voice right for this task? (hands/eyes busy, simple input, short output) (references/dialog-design.md)
2. PERSONA   -> voice, tone, vocabulary; how it handles errors and jokes
3. SAMPLES   -> write sample dialogs for happy path and three messy paths; read them aloud with a partner
4. MODEL     -> intents, slots, required vs optional, entity values and synonyms, utterance variety
5. FLOW      -> states, prompts, reprompts, confirmations, exits
6. ERRORS    -> no-input, no-match, partial match, out of scope, system failure (references/errors-and-confirmation.md)
7. RENDER    -> SSML, pacing, earcons, screen content for multimodal devices (references/ssml-and-voice-tech.md)
8. TEST      -> Wizard-of-Oz before building; then real users, real noise, real accents
9. REVIEW    -> checklist below
```

## Prompt Rules

| Rule | Example |
|------|---------|
| End with the question | "Your table for 4 is at 7:30. Want me to add it to your calendar?" |
| Three options at most per prompt | "You can check a balance, pay a bill, or talk to someone." |
| Short: about 1-2 sentences per turn | Long turns get interrupted or forgotten |
| Implicit confirmation for low risk | "Okay, setting a timer for 10 minutes." |
| Explicit confirmation for high risk | "That's $250 to Alex Kim from checking. Should I send it?" |
| Say what the user can say, when unclear | "You can say a date, like 'next Friday'." |
| Vary common responses | Rotate acknowledgements so it doesn't sound robotic |
| No visual words in voice-only | "Click", "see below", "the button" |

## Review Checklist

Report as `CODE [severity] state/prompt: problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| VU001 | high | No no-input or no-match handling for a state (silence or misrecognition dead-ends) |
| VU002 | high | Risky action (payment, deletion, sending, booking) without explicit confirmation |
| VU003 | high | No way out: no help, cancel, repeat or transfer to a human (IVR) |
| VU004 | medium | Question not at the end of the prompt, or several questions in one turn |
| VU005 | medium | More than three options read in a list, or long lists without chunking |
| VU006 | medium | Prompts over about 30 words or 10-12 seconds spoken |
| VU007 | medium | Reprompts that repeat the same words (no escalation of help) |
| VU008 | medium | Slots that accept only one phrasing; missing synonyms and formats (dates, numbers, names) |
| VU009 | medium | Sensitive information read aloud without consent (balances, health, messages) |
| VU010 | medium | Visual language in a voice-only context |
| VU011 | low | Robotic or inconsistent persona; identical acknowledgements every time |
| VU012 | low | No latency handling (silence over about 1-2 seconds without a filler or earcon) |

## Output

1. Sample dialogs (happy and messy paths)
2. Intent and slot model with example utterances and synonyms
3. Flow with states, prompts, reprompts, confirmations and exits
4. SSML-ready prompt list with estimated durations
5. Test plan and review findings

## Additional Resources

| File | Content |
|------|---------|
| [dialog-design.md](references/dialog-design.md) | When voice fits, cooperative principle, sample dialogs, intents and slots, persona, multimodal and LLM voice agents |
| [errors-and-confirmation.md](references/errors-and-confirmation.md) | No-input/no-match escalation, confirmation strategies by risk, help, exits, IVR transfers |
| [ssml-and-voice-tech.md](references/ssml-and-voice-tech.md) | SSML tags, timing and pacing, earcons, latency, testing and privacy |
