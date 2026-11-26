# Figma Dev Mode, the Handoff Meeting and Design QA

## File organisation

| Page | Contains |
|------|----------|
| Cover | Feature name, status, links, owners |
| Ready for dev | Final screens grouped in sections by flow, each section marked ready for dev |
| Flows | Flow diagrams and prototypes |
| States and edge cases | State matrix frames, edge-case frames |
| Components (new) | New or modified components with variants and specs |
| Archive / explorations | Everything else, clearly separated |

Frame names use screen IDs ("S03 Refund review - 360"). Sections named after flows.

## Dev Mode

- Mark sections "Ready for dev" so engineers see what's final and get notified of changes after marking.
- Use variables and styles everywhere; Dev Mode then shows token names instead of raw values.
- Set variable code syntax (Web/iOS/Android) to the real token names.
- Annotations: add measurement and note annotations for behaviour the canvas can't show (truncation rule, scroll
  behaviour, max widths). Use annotation categories (behaviour, accessibility, content) consistently.
- Code Connect maps design-system components to real code snippets, so engineers see `<Button variant="primary">`
  instead of generated CSS.
- Compare changes: Dev Mode shows what changed in a frame since it was marked ready.

## The handoff meeting (45-60 minutes)

1. Goal and scope (5 min)
2. Walk the flow end to end with the prototype (10 min)
3. Components table: new and modified (10 min)
4. States, edge cases, data rules (15 min)
5. Open questions and decisions; who owns what (10 min)
Record decisions in the handoff doc during the meeting. Invite QA.

## During the build

- Designer availability: an agreed channel and response time.
- Review builds early (first working screen), not only at the end.
- Design QA pass per story before it's marked done (design-qa-visual-diff-checker).
- Changes after handoff: update the frame, add a changelog note in the doc, notify the channel. Never change a
  ready-for-dev frame silently.
