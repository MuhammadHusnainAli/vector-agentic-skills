# Writing LPA Questions

## Good questions are observable, binary and tied to a control

| Weak | Strong | Source |
|------|--------|--------|
| Is the area clean? | Are there loose parts or fasteners on the floor within 1 m of station 20? | FOD / mixed-part complaint |
| Is quality OK? | Is the first-off approval for this run signed before the counter passed 1? | Control plan |
| Do operators follow instructions? | Is the work instruction at the station the same revision as the portal (check the revision letter)? | Document control |
| Is the poka-yoke working? | Was the error-proofing verified with the red rabbit part at shift start, and is it logged? | PFMEA control |
| Do operators know what to do? | Ask the operator: what do you do if the torque gun shows NOK? Answer matches the reaction plan? | Control plan reaction |
| Is nonconforming material controlled? | Is every part in the red bin tagged with an NCR number? | 8.7 |

## Question sources (in priority order)

1. Recent customer complaints and escapes (keep for 3 months after closure).
2. Special / key characteristics and their controls.
3. PFMEA lines with action priority H or severity 9-10.
4. Control plan reaction plans.
5. Recent internal NCR Pareto top items.
6. Core set: instructions current, first-off done, error-proofing verified, gauges in calibration, red bin controlled.

## Format for the card

```
Q5  Operator can state the reaction plan for a NOK torque result        [Y] [N] [N/A]
    Look for: answer matches CP-114 step 6 (stop, red tag, call team leader)
    If N: correct on the spot? [Y] [N]  Action / owner / date: ____________
```

Add a "look for" line or photo for every question so all layers judge the same way.
