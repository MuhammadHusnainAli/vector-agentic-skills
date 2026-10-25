# Running SPC on the Shop Floor

## Phase I (establish limits) vs Phase II (monitor)

| | Phase I | Phase II |
|---|---------|----------|
| Goal | Bring the process into control and estimate its natural variation | Detect changes quickly |
| Data | 20-25 subgroups (100+ values) from normal production | Each new subgroup as it is made |
| Out-of-control points | Investigate; if a special cause is found and removed, exclude the point and recompute (`--exclude-ooc`) | React per the control plan reaction plan |
| Limits | Calculated, reviewed, frozen | Fixed; recalculate only after a deliberate process change |

Never set control limits from specifications, and never recalculate limits every day: rolling limits hide drift.

## Prerequisites

- Measurement system acceptable (Gage R&R < 10-30% of tolerance and ndc >= 5).
- Rational subgroups and a sampling frequency that catches shifts before many bad parts are made.
- A reaction plan the operator can follow (who, what, contain, record).

## Reading the chart

1. Range / S / MR chart first: if variation is unstable, X-bar limits are not meaningful.
2. Points beyond limits, then run rules (Western Electric / Nelson) for shifts and trends.
3. Mark every signal with what was found and done; an annotated chart is the best evidence of control.

## Control vs capability

A process can be in control and incapable (stable but too wide), or capable and out of control (shifting inside
the tolerance). Control first, then capability: Cp/Cpk use the within-subgroup sigma printed by
`control_limits.py` (see manufacturing-cpk-capability-calculator).

## Common mistakes

| Mistake | Effect |
|---------|--------|
| Using spec limits as control limits | No signal until parts are already bad |
| Subgroups of parts from different cavities or spindles | Inflated within variation, limits too wide |
| Adjusting the process after every point (tampering) | Increases variation |
| Charting a characteristic nobody reacts to | Paperwork with no control |
| Attribute charts with tiny samples (n p-bar < 5) | Limits meaningless; increase n |
