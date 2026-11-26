---
name: design-handoff-spec-generator
description: "Produce design handoff packages engineers can build from without guessing: scope and links, user flows, screens per breakpoint, component map (existing design-system components vs new or modified ones), every state and edge case (empty, loading, error, long content, permissions), interaction and motion specs, responsive behaviour, content and copy with limits, accessibility annotations, data and API needs (fields, formats, validation, sorting, pagination), analytics events, assets, open questions and acceptance criteria written as testable statements. Covers Figma Dev Mode setup (ready-for-dev sections, annotations, variables and tokens visible, Code Connect), the handoff meeting, and design QA during the build. Reviews handoffs for happy-path-only screens, unlabelled new components, raw values, unspecified responsive behaviour and data rules, and untestable criteria. Use when preparing a design for engineering, writing a feature spec from designs, or auditing a handoff before sprint planning."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Design Handoff Spec Generator

Handoff isn't a link to a Figma file. It's the set of answers an engineer would otherwise need a meeting for: what
happens when the list is empty, when the name is 80 characters, when the API fails, at 390px wide, and with a keyboard.
Most rework after launch traces back to a state nobody designed. This skill builds the complete package from the designs
and reviews handoffs before they enter a sprint.

## Trigger Conditions

Activate this skill when the user:
- Prepares a design for engineering, or a sprint planning session
- Writes a feature spec or acceptance criteria from designs
- Sets up a Figma file for Dev Mode or a handoff meeting
- Gets repeated questions from engineers, or bugs from undesigned states

Component-level specs: [ui-component-spec-writer](../ui-component-spec-writer/SKILL.md). Measurements: [redline-annotation-writer](../redline-annotation-writer/SKILL.md). Accessibility notes:
[accessibility-annotation-writer](../accessibility-annotation-writer/SKILL.md). Asset delivery: [asset-export-naming-planner](../asset-export-naming-planner/SKILL.md). Checking the build: [design-qa-visual-diff-checker](../design-qa-visual-diff-checker/SKILL.md).

## Workflow

```
1. SCOPE     -> feature goal, in/out of scope, platforms, links (PRD, research, tickets)
2. FLOWS     -> flow diagram with screen IDs; entry points and exits
3. SCREENS   -> each screen at each breakpoint, ready-for-dev sections in Figma
4. COMPONENTS-> map: existing DS component (with props) / modified / new (with spec) (references/handoff-package-template.md)
5. STATES    -> every screen and component state + edge cases (references/states-and-acceptance-criteria.md)
6. BEHAVIOUR -> interactions, motion, responsive rules, focus management, keyboard
7. DATA      -> fields, formats, validation, sorting, pagination, limits, error codes and messages
8. CONTENT   -> final copy with limits and localisation notes; analytics events
9. CRITERIA  -> acceptance criteria per story, testable
10. MEET     -> walkthrough with engineering + QA; record decisions; keep open questions owned and dated
```

## Review Checklist

Report as `CODE [severity] screen/area: problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| HO001 | high | Happy path only: no empty, loading, error or permission states |
| HO002 | high | New or modified components not labelled as such (engineers will rebuild or misuse existing ones) |
| HO003 | high | Responsive behaviour unspecified between the designed widths |
| HO004 | high | Data rules missing: formats, validation, limits, sorting, pagination, error messages |
| HO005 | medium | Raw values instead of tokens or styles (hex, px) in new designs |
| HO006 | medium | Long content, localisation and extreme values not shown |
| HO007 | medium | Interactions and motion undescribed (what opens what, transitions, focus movement) |
| HO008 | medium | No accessibility annotations (headings, focus order, names, announcements) |
| HO009 | medium | Acceptance criteria missing or untestable ("works well", "looks good") |
| HO010 | medium | Open questions without an owner or due date |
| HO011 | low | Exploration frames mixed with final designs; no ready-for-dev markers |
| HO012 | low | Analytics events not defined |

## Output

A handoff document (Markdown) following references/handoff-package-template.md, with links to Figma frames by screen ID,
plus the acceptance criteria and open questions. For a review: findings with the missing items listed per screen.

## Additional Resources

| File | Content |
|------|---------|
| [handoff-package-template.md](references/handoff-package-template.md) | The full handoff document template, section by section, with examples |
| [states-and-acceptance-criteria.md](references/states-and-acceptance-criteria.md) | State matrix per screen, edge cases, data rules, writing testable acceptance criteria |
| [figma-dev-mode-and-meeting.md](references/figma-dev-mode-and-meeting.md) | File organisation, Dev Mode, annotations, Code Connect, the handoff meeting, design QA during build |
