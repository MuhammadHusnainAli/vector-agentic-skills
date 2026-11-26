# SSML, Pacing and Voice Tech

## SSML essentials (W3C SSML 1.1; support varies by platform)

```xml
<speak>
  Your table is booked.
  <break time="300ms"/>
  Lucca, <say-as interpret-as="date" format="md">12/5</say-as>, at
  <say-as interpret-as="time" format="hms12">8:30pm</say-as>.
  Your confirmation code is <say-as interpret-as="characters">K7Q2</say-as>.
  <prosody rate="95%">Please arrive ten minutes early.</prosody>
  Want me to add it to your calendar?
</speak>
```

| Tag | Use |
|-----|-----|
| `<break time="300ms"/>` | Pauses between ideas; 200-500 ms usually |
| `<say-as interpret-as="characters">` | Codes and abbreviations spelled out |
| `<say-as interpret-as="date|time|telephone|cardinal|ordinal">` | Correct reading of values |
| `<emphasis level="moderate">` | Stress a key word sparingly |
| `<prosody rate|pitch|volume>` | Slow down important details; don't change pitch for effect |
| `<sub alias="...">` | Pronounce an abbreviation as words |
| `<phoneme>` | Fix brand or name pronunciation |
| `<audio src>` | Earcons and sounds (platform support varies) |

## Timing

- Typical text-to-speech speaking rate: about 150 words per minute (2.5 words per second).
- Estimated duration = words / 2.5 seconds + breaks.
- Keep most turns under about 8-10 seconds; information people need to remember (codes, numbers) at the end and offered
  again ("Want me to repeat that?") or sent to a screen.
- Group digits for phone and account numbers (3-3-4) with short breaks.

## Earcons and latency

- Short sounds signal listening start/stop, success, and errors; keep them brief and consistent.
- Response latency over about 1-2 seconds needs a cue: an earcon, a short acknowledgement ("Let me check"), or a light on
  the device.
- Barge-in: let users interrupt long prompts; stop speaking immediately when they talk.

## Testing

- Wizard of Oz: a person plays the system with the scripted prompts; reveals real phrasing before building.
- Test with diverse accents, ages, speech patterns, and in realistic noise (car, kitchen, street).
- Measure task completion, turns per task, error rates per state, and transfers/abandonment (IVR).
- Review real logs (with consent) for unrecognised utterances; add them to training data and fix prompts that cause them.

## Privacy and accessibility

- Ask before reading sensitive information aloud; offer "send it to your phone" instead.
- Voice authentication isn't sufficient alone for high-risk actions.
- Support people with speech differences: tolerant timeouts, alternatives (touch, text, DTMF), no penalties for
  disfluency; allow adjusting speech rate of the system.
