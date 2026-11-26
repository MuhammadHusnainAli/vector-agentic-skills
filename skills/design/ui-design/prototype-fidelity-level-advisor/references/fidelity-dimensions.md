# Fidelity Dimensions

McCurdy, Connors, Pyrzak, Kanefsky and Vera (CHI 2006) described prototype fidelity as five independent dimensions.
Setting them separately ("mixed fidelity") is how you get useful answers fast.

| Dimension | Low | Medium | High |
|-----------|-----|--------|------|
| Visual refinement | Sketches, greyscale boxes | Wireframes with real type and spacing, limited colour | Production visuals, final assets |
| Breadth of functionality | One task or screen | The tasks under test | Most of the product |
| Depth of functionality | Click-through of one path | Main path plus key alternates and errors | All states, edge cases, validation |
| Richness of interactivity | Page-to-page clicks | Overlays, component states, simple transitions | Real input, gestures, timing, motion, sensors |
| Richness of data model | Placeholder text | Realistic, consistent sample data | Real or personalised data, live back end |

## Mixed-fidelity strategies

| Strategy | Profile | When |
|----------|---------|------|
| Vertical slice | Narrow breadth, high depth and interactivity on one flow | Usability of a critical flow; feasibility |
| Horizontal sweep | Broad breadth, shallow depth | Information architecture, navigation, concept overview |
| Grey-box realistic data | Low visual, high data | Comprehension of dashboards, tables, reports; avoids visual feedback noise |
| Visual comp with shallow click-through | High visual, low depth | Brand and aesthetic response; stakeholder story |
| Wizard of Oz | Medium visual, faked intelligence by a human | AI features, recommendations, chat before the model exists |

## What research suggests

- Studies comparing paper and computer prototypes (e.g. Walker, Takayama and Landay, 2002) found that low- and
  high-fidelity prototypes surfaced similar numbers and kinds of usability problems. Polish isn't needed to find flow
  problems.
- Participants and stakeholders comment on what they see: polished visuals draw visual feedback and make people reluctant
  to suggest bigger changes. Rough visuals invite structural critique.
- Interaction qualities (timing, gesture feel, latency, typing) can't be judged from media that don't reproduce them.
- Realistic data matters for comprehension: unrealistic numbers or names make people evaluate the content, not the
  design.

## Fidelity creep

Teams raise fidelity because it feels like progress. Signs: weeks spent on a prototype for a one-hour test; visual
polish before the flow is validated; building screens no task uses. Counter it by writing the question first and
timeboxing the build.
