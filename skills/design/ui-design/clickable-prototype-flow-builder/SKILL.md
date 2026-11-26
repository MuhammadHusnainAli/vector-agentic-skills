---
name: clickable-prototype-flow-builder
description: "Plan and build clickable prototypes that answer a question rather than show every screen: start from the tasks to test or demo, map the flow as a graph (screens as nodes, interactions as edges) in Mermaid, cover the happy path plus the alternates and error states that matter, decide what is clickable and what happens on off-path clicks, keep data and state consistent across screens (same user, same cart, same numbers), set entry points per task, and QA the flow for dead ends, unreachable screens, missing back paths, broken links and inconsistent state before anyone sees it. Covers tool-agnostic build steps (Figma, ProtoPie, Framer, code prototypes), realistic content, device framing and sharing, task-to-screen coverage matrices and press/click counts per task, and readiness for usability testing or stakeholder demos. Use when turning designs into a clickable prototype, planning a prototype for user testing, or reviewing a prototype before a test or demo."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Clickable Prototype Flow Builder

A prototype is a tool for answering a question: can people complete this task, do they understand this concept, will
leadership fund this? Prototypes that try to link every screen take days, break in the middle of a test, and still don't
cover the paths that matter. This skill starts from the tasks, maps the flow as a graph, builds only what's needed with
consistent content, and QAs it like software before a participant or executive touches it.

## Trigger Conditions

Activate this skill when the user:
- Turns static screens into a clickable prototype for a test or demo
- Plans which screens and paths a prototype needs
- Has a prototype that breaks, dead-ends or confuses test participants
- Needs a flow diagram of a prototype or a coverage check against test tasks

How much fidelity: `prototype-fidelity-level-advisor`. Figma wiring: `figma-prototype-interaction-setup-guide`. Advanced
logic: `protopie-interaction-recipe-writer`. Presenting it: `prototype-demo-script-writer`.

## Workflow

```
1. QUESTION  -> what the prototype must answer, for whom (test participants, stakeholders, engineers)
2. TASKS     -> 3-6 tasks written as scenarios; each has a start screen and success screen
3. MAP       -> flow graph in Mermaid: happy path, alternates, errors (references/flow-mapping.md)
4. COVERAGE  -> task x screen matrix; cut screens no task touches
5. CONTENT   -> one consistent persona and data set across screens (names, prices, counts, dates)
6. BUILD     -> hotspots, transitions, overlays, state; off-path click handling (references/build-checklist.md)
7. QA        -> walk every edge; dead ends, unreachable screens, back paths, state consistency (checklist below)
8. READY     -> entry links per task, device, reset between sessions (references/test-and-demo-readiness.md)
```

## Scope Rules

| Rule | Why |
|------|-----|
| Build the paths the tasks need, plus the obvious wrong turns | Testing what people do when they go wrong is half the value |
| Every screen has a way forward and a way back | Dead ends end sessions; participants blame themselves |
| Off-path clicks get a response | A "Not available in this prototype" overlay beats a click that does nothing |
| One data story | Mismatched names or totals between screens make participants doubt the whole thing |
| Realistic content | Lorem ipsum hides comprehension problems, and labels get tested with real words |
| Start each task on its own entry screen | No need to restart the whole prototype between tasks |

## QA Checklist

Report as `CODE [severity] screen/link: problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| CP001 | high | Dead end: a screen on a task path with no way forward or back |
| CP002 | high | Broken link: hotspot pointing to a missing or wrong screen |
| CP003 | high | Task can't be completed by its expected path (missing edge) |
| CP004 | medium | Unreachable screen (built but no path leads to it) |
| CP005 | medium | Inconsistent data across screens (cart total, user name, item counts, dates) |
| CP006 | medium | Obvious alternate path a participant will try is not built and gives no feedback |
| CP007 | medium | State doesn't persist (selected item forgotten after navigating back) |
| CP008 | medium | Hotspots that are smaller than the visible control, or hidden hotspots on non-interactive areas |
| CP009 | low | Placeholder content, lorem ipsum, or dates in the past for "upcoming" items |
| CP010 | low | No reset path between sessions or tasks |

## Output

1. Question and tasks with start and success screens
2. Mermaid flow diagram with node and edge names
3. Coverage matrix and click count per task
4. Build notes: hotspots, overlays, variables or state, off-path handling
5. QA results and the share links per task

## Additional Resources

| File | Content |
|------|---------|
| [flow-mapping.md](references/flow-mapping.md) | Mermaid flow template, naming, coverage matrix, click counts, graph QA by hand |
| [build-checklist.md](references/build-checklist.md) | Tool-agnostic build steps, hotspots, overlays, state, content, device framing, versioning |
| [test-and-demo-readiness.md](references/test-and-demo-readiness.md) | Pilot testing, entry links, resets, device setup, failure fallbacks, sharing and permissions |
