---
name: prototype-demo-script-writer
description: "Write demo scripts that make a prototype land with its audience: audience and decision first (executive funding, sprint review, customer showcase, engineering kickoff, conference talk), a story arc (who the user is, the problem today with evidence, the new experience as a task, the outcome, the ask), timed beats at a realistic speaking rate, an exact click path with what to say at each step, honest framing of what is real and what is faked, likely questions and objections with answers, and a rehearsal and fallback plan (backup video, screenshots, reset steps, device setup, notifications off). Reviews existing scripts for feature tours without a story, no clear ask, overruns, jargon, unframed fake data or AI, and fragile live demos with no fallback. Use when preparing a design demo, stakeholder presentation, sprint review or customer showcase of a prototype."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Prototype Demo Script Writer

A demo is a decision meeting with a prototype in it. Most design demos are feature tours: "and here you can..., and here
you can...". The audience is left to work out why any of it matters. Strong demos tell one user's story with one task,
show evidence that the problem is real, make clear what's real and what's mocked, and end with a specific ask. They also
survive a frozen prototype. This skill writes that script and reviews existing ones.

## Trigger Conditions

Activate this skill when the user:
- Prepares to demo a prototype to executives, stakeholders, customers or engineering
- Has a sprint review, design review or showcase slot
- Wants a talk track and click path for a recorded walkthrough
- Got feedback that past demos were confusing, long, or didn't lead to decisions

Building the prototype: [clickable-prototype-flow-builder](../clickable-prototype-flow-builder/SKILL.md). Framing fidelity: [prototype-fidelity-level-advisor](../prototype-fidelity-level-advisor/SKILL.md).

## Workflow

```
1. DECISION  -> what the audience should decide or do afterwards (fund, prioritise, approve, give feedback on X)
2. AUDIENCE  -> who is in the room, what they care about, what they already know (references/storytelling-and-audiences.md)
3. STORY     -> persona + situation + problem today (evidence) + new experience + outcome
4. PATH      -> one task through the prototype; every click with its line (references/demo-script-template.md)
5. TIME      -> beats timed at about 130-150 spoken words per minute; demo no more than half the slot
6. FRAMING   -> what's real, faked or not yet decided; open questions you want input on
7. Q&A       -> likely questions and objections with short answers
8. REHEARSE  -> two full run-throughs on the real setup; fallback ready (references/delivery-and-fallbacks.md)
```

## Rules

| Rule | Why |
|------|-----|
| One persona, one task, one story | Audiences remember stories, not feature lists |
| Show the problem before the solution | The solution means nothing without the pain; use a clip, quote or metric |
| Say what's fake | A demo that implies a working back end or AI causes trouble later |
| Lead with the ask, end with the ask | "We're asking for X by Y" |
| Leave half the slot for discussion | The decision happens in the discussion |
| Talk about the user, not the UI | "Maya can now see..." beats "this component shows..." |
| Rehearse with the real setup | Most demo failures are setup: login, network, screen share, zoom level |

## Review Checklist

Report as `CODE [severity] problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| DS001 | high | No stated decision or ask |
| DS002 | high | Feature tour with no user story or problem statement |
| DS003 | high | Script runs over the slot, or leaves under a third of it for discussion |
| DS004 | medium | No evidence for the problem (research, data, quotes) |
| DS005 | medium | Faked data, flows or AI presented as working without framing |
| DS006 | medium | No fallback for a live demo (video, screenshots) |
| DS007 | medium | Jargon or internal names the audience won't know |
| DS008 | medium | Click path not written down; presenter improvises navigation |
| DS009 | low | No prepared answers for predictable questions (cost, timeline, risks, metrics) |
| DS010 | low | Setup steps missing (reset, notifications off, zoom, test account) |

## Output

1. Decision and audience summary
2. Script table: time, beat, screen/click, talk track
3. Framing statement (real vs faked)
4. Q&A sheet
5. Setup and fallback checklist

## Additional Resources

| File | Content |
|------|---------|
| [demo-script-template.md](references/demo-script-template.md) | Script table template with a worked 10-minute executive demo, timing maths |
| [storytelling-and-audiences.md](references/storytelling-and-audiences.md) | Story arcs, audience-specific emphasis, evidence, framing fidelity, handling objections |
| [delivery-and-fallbacks.md](references/delivery-and-fallbacks.md) | Rehearsal, setup checklist, remote demos, recorded walkthroughs, recovery when things break |
