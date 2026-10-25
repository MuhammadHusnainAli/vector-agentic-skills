# Audit Time and Project Planning

## IAF MD 5 audit days (QMS, initial = stage 1 + stage 2)

| Effective personnel | Days | Effective personnel | Days |
|---------------------|------|---------------------|------|
| 1-5 | 1.5 | 426-625 | 11 |
| 6-10 | 2 | 626-875 | 12 |
| 11-15 | 2.5 | 876-1175 | 13 |
| 16-25 | 3 | 1176-1550 | 14 |
| 26-45 | 4 | 1551-2025 | 15 |
| 46-65 | 5 | 2026-2675 | 16 |
| 66-85 | 6 | 2676-3450 | 17 |
| 86-125 | 7 | 3451-4350 | 18 |
| 126-175 | 8 | 4351-5450 | 19 |
| 176-275 | 9 | 5451-6800 | 20 |
| 276-425 | 10 | 6801-8500 | 21 |
| | | 8501-10700 | 22 |

Surveillance is about one third and recertification about two thirds of the initial time. CBs adjust for
complexity: up for design responsibility, many processes, multiple shifts or high risk; down for low-risk
processes, repetitive work or a mature integrated system (reductions usually capped at 30%). Part-time staff and
repetitive work can reduce the effective personnel count. Multi-site organizations may qualify for site sampling
(IAF MD 1). Verify the current MD 5 edition with the CB.

## Typical durations

| Organization | From scratch to certificate |
|--------------|-----------------------------|
| < 25 people, simple processes | 6-9 months |
| 25-100 people | 9-12 months |
| 100-500 people, several sites | 12-18 months |
| Existing ISO 14001/45001 or customer-approved system | 4-8 months |

`roadmap.py` models this: build phases scale with headcount (x1 up to 25, x1.25 to 100, x1.5 to 500, x2 above)
and maturity (none x1, basic x0.75, partial x0.5); the 12-week records period and audit stages do not scale.

## Project governance

| Element | Recommendation |
|---------|----------------|
| Sponsor | Managing director (5.1 needs top-management ownership) |
| Project lead | Quality manager or trained coordinator, 30-60% of time for a 50-person company |
| Steering meeting | Every 2 weeks: progress vs roadmap, blocked items, decisions |
| Process owners | Write and run their own processes; QM coaches |
| Budget | Training, CB fees (3-year cycle), possible consultant, software (eQMS), staff time |
| Milestones to report | Gap report, process map approved, documents released, first audit cycle complete, MR held, stage 1, stage 2 |

## Risks to the timeline

- Process owners not released from daily work -> documents late.
- Internal auditors not trained in time -> audit cycle slips -> stage 1 slips.
- CB booked late -> 6-10 week wait.
- Design responsibility discovered late -> 8.3 must be implemented and the scope changed.
