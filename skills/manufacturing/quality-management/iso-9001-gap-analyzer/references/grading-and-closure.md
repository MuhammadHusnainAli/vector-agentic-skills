# Grading Gaps and Planning Closure

## Grades used by certification bodies

| Grade | Definition (ISO/IEC 17021-1 terms) | Typical example | Effect on certification |
|-------|-----------------------------------|-----------------|------------------------|
| Major nonconformity | Affects the capability of the QMS to achieve intended results: a requirement not addressed at all, or a systemic breakdown | No internal audits done; no management review; nonconforming product shipped routinely | Certification cannot be recommended until corrected and verified (often a follow-up visit) |
| Minor nonconformity | A single lapse that does not affect the system's capability | One overdue calibration; one training record missing | Corrective action plan accepted; verified at the next audit |
| Opportunity for improvement | No requirement broken; a risk or weakness | KPI trend not analysed | Optional |

`gap_score.py` grades not-met core clauses as major because their absence is exactly what auditors call a
systemic breakdown. Treat the grade as a forecast, not a certainty: the auditor decides on the evidence seen.

## Readiness thresholds

| Score | No majors | Meaning |
|-------|-----------|---------|
| >= 90% | yes | Book stage 1. Remaining minors can close before stage 2 |
| 75-90% | yes | 1-3 months of focused work; confirm records exist for 3 months |
| < 75% or any major | - | Build the system first; certification date is not credible yet |

Records need time: most bodies want to see the QMS operating for about 3 months, with at least one full internal
audit cycle and one management review, before stage 2.

## Turning gaps into a closure plan

1. **Order by dependency, not clause number.** Context (4.1, 4.2) -> scope (4.3) -> processes (4.4) -> policy and
   objectives (5.2, 6.2) -> risks (6.1) -> operational controls (8) -> monitoring (9.1) -> audit (9.2) ->
   management review (9.3). An audit cannot run before the processes it audits exist.
2. **One owner and one date per gap.** Owners are process owners, not the quality manager by default.
3. **Define the evidence of closure** in the same row: "risk register QF-06 approved, reviewed at MR 2026-12".
4. **Re-score monthly** with the same worksheet; report the readiness trend to top management.

| Gap | Owner | Action | Evidence of closure | Due |
|-----|-------|--------|---------------------|-----|
| 6.1 not met | Ops director | Build risk/opportunity register from 4.1/4.2 issues, assign actions | QF-06 approved, actions in progress | 2026-12-15 |
| 9.2 not met | QM | Train 2 internal auditors, audit all processes once | Audit programme + 6 reports | 2027-02-28 |

## Interviewing during a gap assessment

- Ask people to **show**, not tell: "show me the last NCR you raised", "show me where this drawing revision is controlled".
- Sample across shifts and roles; one good answer from the quality manager is not evidence for the shop floor.
- Record the exact evidence (document number, record date, person's role) so a "met" can be defended.
