# Media and Effort

Effort is a rough guide for one designer, for a prototype covering about 3-5 tasks. Adjust for the team's fluency.

| Medium | Strengths | Limits | Typical effort |
|--------|-----------|--------|----------------|
| Paper / sketches | Fastest; invites big changes; good for co-design | No real interaction; facilitator plays the computer | Hours |
| Wireframe click-through (Figma, Balsamiq) | Quick flow testing; low visual noise | Limited states; fake input | 0.5-2 days |
| High-fidelity Figma prototype | Realistic look; interactive components and variables | No real text input; complex logic gets heavy | 2-5 days |
| ProtoPie | Real input, sensors, conditions, multi-device, hardware (car, TV) | Separate tool; build time | 2-7 days |
| Framer / code prototype | Real scrolling, responsive layout, real data, real performance | Engineering skills; scope creep | 3-10 days |
| Wizard of Oz | Tests AI/automation before it exists; realistic responses | Needs a hidden operator; timing must be convincing | 1-3 days + operator per session |
| Fake door / painted door | Measures real demand in production | Ethics: tell users afterwards; only for low-cost disappointments | Hours + engineering for tracking |
| Video / animated walkthrough | Communicates vision and motion | Not interactive; not a usability test | 1-3 days |

## Cutting scope when time is short

1. Cut breadth first: fewer tasks, each complete.
2. Keep depth on tested paths: alternates and errors participants will hit.
3. Lower visual refinement before data realism.
4. Fake back-end behaviour with pre-set responses.
5. Never cut the pilot session.

## Estimating

```
effort ≈ screens on tested paths x (wiring time per screen)
       + interactive components needed
       + data preparation
       + QA and pilot (about 20-30% of build time)
```
Compare the total against the decision date. If the prototype can't be ready before the decision, test a lower-fidelity
version now.
