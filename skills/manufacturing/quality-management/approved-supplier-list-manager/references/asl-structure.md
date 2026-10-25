# Approved Supplier List Structure

ISO 9001 8.4.1 requires criteria for evaluation, selection, monitoring and re-evaluation of external providers,
with records. AS9100 8.4.1 requires a register of external providers with approval status (approved, conditional,
disapproved) and scope of approval (product type, process family). IATF 16949 8.4.1.2 requires a documented
selection process with risk assessment; 8.4.2.3 requires suppliers to be certified to ISO 9001 at minimum
(developing toward IATF 16949) unless the customer authorises otherwise.

## Columns

| Column | Content |
|--------|---------|
| Supplier, ID, site | Legal name and the manufacturing site actually approved |
| Status | approved / conditional / probation / disqualified / pending |
| Scope | Commodities and processes approved (machining; anodising; heat treat to AMS 2770) |
| Risk class | high / medium / low (product impact, process complexity, supply risk) |
| Certification and expiry | ISO 9001, IATF 16949, AS9100, NADCAP (with scope) |
| Approval basis | Audit, questionnaire, first article, customer direction |
| Last evaluation and next due | From scorecard history; interval by risk |
| Conditions | For conditional / probation: what must improve, by when (condition_until) |
| Single source / backup | Contingency for critical parts (IATF 6.1.2.3) |
| Approved by | Role with authority (purchasing + quality) |
| Customer-directed | Supplier mandated by the customer (still monitored; responsibility stays with you) |

## Status meanings

| Status | Orders allowed | Typical controls |
|--------|----------------|------------------|
| Approved | Yes, within scope | Normal monitoring |
| Conditional | Yes, within scope, with conditions | Tightened inspection, improvement plan, end date |
| Probation | Existing parts only, no new business | SCAR, development plan, escalation |
| Pending | No (or prototype only with approval) | Assessment in progress |
| Disqualified | No | Phase-out plan for any remaining parts |

## Re-evaluation intervals

High risk every 12 months, medium every 24, low every 36, or immediately after a major quality event, a
certification change, a site or ownership change, or a scorecard grade D.
