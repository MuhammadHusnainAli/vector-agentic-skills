# PFMEA in Practice

## Inputs

Process flow diagram (every step incl. receiving, storage, rework, inspection, packing, shipping), drawing and
special characteristics, DFMEA effects (if available), lessons learned, complaint and NCR history, similar-part
PFMEAs (foundation / family FMEAs).

## Failure chain wording

| Element | Write it as | Example |
|---------|-------------|---------|
| Effect | What the next operation, customer or end user experiences | Valve leaks at customer pressure test |
| Failure mode | How the step fails to meet its requirement | Bore oversize (> 12.018 mm) |
| Cause | Why, at the work-element level (4M) | Boring insert worn beyond limit |
| Prevention control | What stops the cause happening | Tool-life interlock at 220 parts |
| Detection control | What finds the failure mode or cause before it leaves | In-process air gauge every 10th part with SPC |

One failure mode can have several causes: one row per cause, each with its own O and controls.

## Link to the control plan

Every prevention and detection control in the PFMEA appears in the control plan with its method, sample size,
frequency and reaction plan; every special characteristic in the control plan has a PFMEA row. Change one, change
the other (see control-plan-writer).

## Review triggers

New part or process; engineering or process change; customer complaint or field failure; internal NCR trend;
new lessons learned; at least annually for active high-severity processes (customer-specific).

## Common audit findings

- Detection rated 2-3 for visual inspection.
- Occurrence lowered without any change to prevention.
- AP H rows with no action and no justification.
- Effects written as failure modes ("out of tolerance").
- PFMEA not updated after a complaint on the same failure mode.
- Rework and inspection steps missing from the analysis.
