---
name: prototype-fidelity-level-advisor
description: "Choose the right prototype fidelity for the question being asked instead of defaulting to polished Figma: fidelity as five independent dimensions (visual refinement, breadth of functionality, depth of functionality, richness of interactivity, richness of data model, after McCurdy et al.), mapped from the research or decision question (concept value, comprehension, task flow usability, interaction feel, visual and brand response, technical feasibility, stakeholder buy-in, engineering handoff), the stage, the audience and the time available. Recommends a profile per dimension, the medium (paper to coded prototype, Wizard of Oz, fake door), what to fake, the effort and the risks of too much or too little fidelity, and reviews prototype plans for mismatches. Use when planning a prototype, a usability test, a concept test or a stakeholder demo, or when a team debates how polished a prototype needs to be."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Prototype Fidelity Level Advisor

"Low-fi or high-fi?" is the wrong question. Fidelity has several independent dimensions. A prototype can be visually
rough but have deep, realistic data, or pixel-perfect with only one path clickable. The right profile depends on the
question being answered. A team that polishes everything wastes weeks and gets feedback about colours. A team that tests
interaction feel with paper gets answers it can't trust. This skill matches each dimension to the question and plans what
to build and what to fake.

## Trigger Conditions

Activate this skill when the user:
- Plans a prototype for user testing, concept validation or a stakeholder demo
- Debates how polished or how complete a prototype should be
- Has limited time and needs to decide what to build
- Got feedback about the wrong things (visual details in a concept test, or "it's just a sketch" dismissals)

Building the flow: [clickable-prototype-flow-builder](../clickable-prototype-flow-builder/SKILL.md). Tool recipes: [figma-prototype-interaction-setup-guide](../figma-prototype-interaction-setup-guide/SKILL.md),
[protopie-interaction-recipe-writer](../protopie-interaction-recipe-writer/SKILL.md). Demo script: [prototype-demo-script-writer](../prototype-demo-script-writer/SKILL.md).

## Workflow

```
1. QUESTION  -> write the question as a sentence and the decision it informs (references/question-to-fidelity.md)
2. AUDIENCE  -> participants (who), stakeholders, engineers; what they need to believe or judge
3. PROFILE   -> set each of the five dimensions low / medium / high (references/fidelity-dimensions.md)
4. MEDIUM    -> pick the medium that delivers the profile cheapest (references/media-and-effort.md)
5. FAKE      -> list what is real and what is faked (data, logic, AI, back end, payments)
6. BUDGET    -> effort estimate vs the time available; cut breadth before cutting depth on tested paths
7. RISKS     -> what this fidelity could mislead about; how the session or demo will frame it
8. REVIEW    -> checklist below
```

## Quick Mapping

| Question | Visual | Breadth | Depth | Interactivity | Data |
|----------|--------|---------|-------|---------------|------|
| Is the concept valuable? Do people get it? | Low | Narrow | Shallow | Low | Medium (realistic examples) |
| Can people complete the task? Where do they get stuck? | Medium | Narrow (tested tasks) | Deep on task paths | Medium | High (realistic, consistent) |
| Does the interaction feel right (gestures, timing, motion)? | Medium-high | Very narrow | Deep for that interaction | High (real input, real timing) | Medium |
| How do people respond to the visual design / brand? | High | Narrow | Shallow | Low | Medium |
| Can it be built and perform? | Low-medium | Narrow | Deep | High | Real |
| Will leadership fund it? | High | Narrow (story path) | Shallow-medium | Medium | Realistic, curated |
| What exactly should engineering build? | High | Broad | Deep (all states) | Medium | Edge cases |

## Review Checklist

Report as `CODE [severity] problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| PF001 | high | No written question; the prototype has no defined purpose |
| PF002 | high | Interaction-feel question tested with a medium that can't reproduce it (paper or static frames for gestures, latency or typing) |
| PF003 | high | Task usability tested with unrealistic or inconsistent data (lorem ipsum, mismatched totals) |
| PF004 | medium | High visual polish for an early concept test (feedback drifts to visuals; team gets attached) |
| PF005 | medium | Breadth over depth: many screens linked shallowly, tested paths incomplete |
| PF006 | medium | Effort exceeds the decision's value or the time before the decision |
| PF007 | medium | Faked parts not acknowledged to stakeholders (demo implies the back end or AI exists) |
| PF008 | low | No plan for what happens off the built paths |

## Output

1. Question, decision and audience
2. Fidelity profile (five dimensions) with the reason for each
3. Medium and tool
4. Real vs faked list
5. Effort estimate and scope cuts
6. Risks and how to frame the prototype to participants or stakeholders

## Additional Resources

| File | Content |
|------|---------|
| [fidelity-dimensions.md](references/fidelity-dimensions.md) | The five dimensions with low/medium/high examples, mixed-fidelity strategies, evidence on fidelity effects |
| [question-to-fidelity.md](references/question-to-fidelity.md) | Question types with profiles, media, what to fake and pitfalls |
| [media-and-effort.md](references/media-and-effort.md) | Paper, wireframes, Figma, ProtoPie, Framer/code, Wizard of Oz, fake door: strengths, limits, effort |
