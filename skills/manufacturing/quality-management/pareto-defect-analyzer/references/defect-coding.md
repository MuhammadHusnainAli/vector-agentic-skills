# Defect Coding for Useful Paretos

A Pareto is only as good as the defect codes behind it. Build a short, controlled code list.

## Rules

- 10-25 codes per product family; each code describes **what is wrong and where** ("scratch face A").
- Codes describe the defect (effect), not the cause; causes come from investigation.
- Every code has a definition and a photo or limit sample.
- "Other" requires a free-text description, reviewed weekly; recurring texts become new codes.
- Record quantity, part number, line, shift, operation found, and cost category with each record.

## Example code list (machined housing)

| Code | Defect | Location / note |
|------|--------|-----------------|
| D01 | Burr | Bore edge, cross-holes |
| D02 | Scratch | Face A (sealing face) |
| D03 | Bore oversize | Bore 12.000 +0.018 |
| D04 | Porosity | Casting, machined faces |
| D05 | Thread damage | M8 threads |
| D06 | Missing component | Clip, O-ring |
| D07 | Wrong label | Label content or position |
| D08 | Dent | Any surface |
| D99 | Other | Free text required |

## Cost of a defect

cost = scrap value (material + added value to that operation) + rework labour + re-inspection + downstream
costs (sorting, premium freight, customer charge-backs, warranty). Use the same cost model every month so
Paretos are comparable.
