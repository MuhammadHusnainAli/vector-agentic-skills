# Dynamic (Risk-Based) Incoming Inspection

Incoming inspection should shrink as a supplier proves itself and grow as soon as it slips. Inspecting good
suppliers heavily wastes money; inspecting bad ones lightly ships their defects into production.

## Levels

| Level | Entry | Method | Exit |
|-------|-------|--------|------|
| First lots | New part, new supplier, process or site change | First article (all characteristics), 100% of first 1-3 lots | 3 lots accepted |
| Tightened | 2 of 5 lots rejected, grade C/D supplier, open SCAR | Sample at half the LTPD (larger n) or 100% | 5 consecutive lots accepted and SCAR closed |
| Normal | Default | c = 0 sample per class | Switch on results |
| Skip-lot | >= 10 consecutive accepted lots, grade A, not critical | Inspect 1 lot in 4 (others: CoC check only) | Any rejected lot -> normal |
| Dock-to-stock | >= 20 accepted lots, grade A, minor characteristics, CoC supplied | Certificate review; audit 1 lot in 10 | Any reject or score drop -> normal |

## Characteristic classes

| Class | LTPD (normal) | c = 0 sample size (90% confidence) | Notes |
|-------|---------------|-------------------------------------|-------|
| Critical (safety, regulatory) | 0.5% | 460 | Prefer supplier error-proofing + SPC evidence or source inspection; never certificate-only |
| Major (function, fit) | 2% | 114 | |
| Minor (cosmetic) | 5% | 45 | Good candidate for skip-lot / dock-to-stock |

Lot-homogeneous characteristics (material grade, hardness of one heat, coating batch) are verified per lot by
certificate plus periodic independent testing, not by large samples.

## What to check at receiving

- Paperwork: PO, part number and revision, quantity, CoC / CoA content against the specification, traceability (heat, lot).
- Packaging and labelling, damage, shelf life.
- Characteristics from the plan, with calibrated gauges and limit samples.
- Record the lot result; feed accepted/rejected lots into the switching rules and the supplier scorecard.

## Reducing inspection safely

Shift effort upstream: require supplier SPC data for key characteristics, approve their control plan, audit them,
and use source inspection for critical parts. Receiving inspection then verifies the system rather than sorting parts.
