# APQP Phases, Deliverables and Gates

Advanced Product Quality Planning (AIAG APQP, 3rd edition 2024, with the Control Plan now in its own AIAG CP
manual) is the structured path from customer requirement to stable production. IATF 16949 8.1, 8.3 and 8.5.1.1
require it in substance; customers state the format (AIAG, VDA MLA, OEM-specific) in their CSRs.

| Phase | Purpose | Key deliverables | Gate (typical) |
|-------|---------|------------------|----------------|
| 1 Plan and define | Understand the customer and set goals | Voice of customer, business plan, design / reliability / quality goals, preliminary BOM, process flow and special characteristics, product assurance plan | Program approval, team and resources committed |
| 2 Product design and development | Design a product that meets requirements | DFMEA, DFM/A, DVP&R, design reviews, prototype control plan, drawings and specifications, material specs, team feasibility commitment, equipment/tooling/gauge requirements | Design freeze |
| 3 Process design and development | Design a process that makes it consistently | Packaging standards, process flow chart, floor plan, characteristics matrix, PFMEA, pre-launch control plan, work instructions, MSA plan, capability study plan | Process sign-off (tooling and equipment ready) |
| 4 Product and process validation | Prove it with a production run | Significant production run (run at rate), MSA results, preliminary capability (Ppk >= 1.67), production validation testing, packaging evaluation, production control plan, PPAP, quality planning sign-off | PPAP approved |
| 5 Feedback, assessment, corrective action | Launch and stabilise | Safe-launch containment, reduced variation (Cpk >= 1.33), customer satisfaction, delivery, lessons learned | Safe-launch exit |

Phases overlap: process design starts once the design is stable enough; validation needs production tooling.

## Build-to-print suppliers

Without design responsibility, phase 2 becomes: review customer drawings and specifications, feasibility
commitment, special characteristics agreement, equipment and gauge requirements. Process design, validation and
PPAP are unchanged.

## Gate reviews

At each gate the cross-functional team and management review a status table: deliverable, owner, status
(green / yellow / red), risk and recovery plan. Many customers want a red/yellow/green APQP status report
monthly. Do not pass a gate with red items unless there is a dated recovery plan approved by management.

## Typical lead times

| Complexity | Example | P1 | P2 | P3 | P4 | SOP lead time |
|------------|---------|----|----|----|----|---------------|
| Low | Carry-over part with minor change | 4 wk | 8 | 8 | 6 | ~6 months |
| Medium | New part, known process | 6 | 16 | 14 | 10 | ~11 months |
| High | New technology, new line | 8 | 26 | 20 | 14 | ~1.5 years |

Tooling and equipment lead times (injection moulds 12-20 weeks, presses and special machines 20-40 weeks) often
set the critical path in phase 3: order them at design freeze or earlier at risk.
