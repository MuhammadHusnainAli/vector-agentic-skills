# Writing an NCR

An NCR records **what is wrong, how much, where it is now, and what will be done with it**. Root cause and
corrective action belong in the CAPA/8D it may trigger, not in the NCR.

## Fields

| Field | Content | Example |
|-------|---------|---------|
| ID, date | Unique number, date found | NCR-2611, 2026-10-02 |
| Detected by / at | Role and detection point (receiving, in-process, final, customer, supplier) | Final inspector, final |
| Part, revision, lot | Traceability to drawing revision and production lot | VB-2210 rev C, lot L2609-14 |
| Requirement | Exact spec with its source | Bore 12.000 +0.018/-0.000 mm, drawing item 7 |
| Actual | Measured value or observation with method | 12.021-12.030 mm by bore gauge BG-04 |
| Quantity | Affected / checked / total in lot | 40 of 200 checked; lot 560 |
| Containment | Every location checked, quantity, result, who, when | See below |
| Disposition | Use-as-is, rework, repair, scrap, return to supplier, regrade | Scrap |
| Authority | Who decided (MRB role), concession ref if needed | Quality engineer (MRB) |
| Re-inspection | For rework/repair: result against the original requirement | 100% re-check, 0 failures |
| CAPA link | When systemic, repeat or customer-detected | CA-118 |

## Description: requirement vs actual

| Weak | Strong |
|------|--------|
| "Parts are defective" | "Bore 12.021-12.030 mm on 40 of 200 parts; drawing VB-2210 rev C requires 12.000-12.018 mm" |
| "Wrong material" | "Mill certificate shows 6061-T4; PO and drawing require 6061-T6" |
| "Cosmetic damage" | "Scratches 5-12 mm long on face A on 60 parts; spec CS-02 allows none longer than 2 mm in zone A" |

Add a photo with a scale or a measurement record. Use is / is-not thinking: which lots, machines, shifts are affected
and which are not.

## Containment checklist

When the problem is found late (final inspection, shipping, customer), check every place suspect product can be:

| Location | Question |
|----------|----------|
| Machine / WIP | Parts made since the last good check? |
| Inspection queue | Waiting parts from the same lot or machine? |
| Finished stock | All lots since the last known good? |
| In transit | Shipments since the last good check? |
| Customer | Stock at the customer's receiving and line? Notify them |
| Supplier | Same material lot still at the supplier? |

Record quantity found, quantity bad, action and who did it. Mark suspect product clearly (red tag, hold status in ERP).

## Severity (for prioritising)

| Level | Examples | Response |
|-------|----------|----------|
| Critical | Safety, regulatory, customer line stop | Immediate containment, notify customer the same day, CAPA |
| Major | Function, fit, customer-detected, repeat | Containment same shift, CAPA |
| Minor | Cosmetic within limits of usability, internal, one-off | Disposition, trend |
