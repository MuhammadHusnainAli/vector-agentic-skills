# Scoring, Risk and Approval

## Supplier risk class -> assessment depth

| Risk | Typical supplier | Assessment | Re-assessment |
|------|------------------|------------|---------------|
| High | Safety/critical parts, special processes, sole source, new technology | On-site audit by a trained auditor plus questionnaire | Every 1-2 years, or on performance trigger |
| Medium | Custom parts to drawing, standard processes | Self-assessment questionnaire + evidence, on-site if score < 85% | Every 2-3 years |
| Low | Catalogue items, distributors of standard parts, indirect services | Certificate check + short questionnaire | On certificate expiry or performance trigger |

Classify by product impact (safety, function, appearance), process complexity, spend, supply risk (single
source, geography) and history. Record the classification on the approved supplier list.

## Scale

| Score | Meaning | Evidence expected |
|-------|---------|-------------------|
| 3 fully | In place, effective, records available | Sample records seen |
| 2 mostly | In place with minor gaps | Records with a few gaps |
| 1 partly | Exists informally or only for some products | Little evidence |
| 0 not in place | Not done | - |
| na | Not applicable (state why) | - |

Self-assessments overstate: on average, on-site scores are 10-20 points lower. Ask for evidence (photos,
records, certificates) with every answer scored 3.

## Decision rules (defaults in score_questionnaire.py)

| Result | Rule | Action |
|--------|------|--------|
| Not approved (knockout) | Any KO question 0 or 1 | No orders until fixed and re-assessed |
| Approved | >= 85% and no section < 60% | Add to ASL; normal monitoring |
| Conditional | >= 70% | Orders allowed with improvement plan, extra incoming inspection, re-check in 3-6 months |
| Not approved | < 70% | Find an alternative or run supplier development |

Typical knockouts: no accredited certification where required, uncontrolled work instructions, uncalibrated
gauges, nonconforming product not segregated, distributors buying outside authorized channels, service staff
without required competence.

## Improvement plan for a conditional approval

| Section | Gap | Action by supplier | Evidence | Due | Verified by |
|---------|-----|--------------------|----------|-----|-------------|
| Inspection and measurement | 3 gauges uncalibrated, no MSA | Calibrate, add to register; Gage R&R on 2 key gauges | Certificates, studies | +60 days | SQE desk review |

Link to [supplier-development-plan-writer](../../supplier-development-plan-writer/SKILL.md) for larger gaps and to the
supplier scorecard for ongoing monitoring.

## Weighting

Default section weights favour process control, inspection and nonconformance control, which predict delivered
quality best. Adjust weights to the commodity: service suppliers weight competence highest; distributors weight
traceability and authorized sourcing.
