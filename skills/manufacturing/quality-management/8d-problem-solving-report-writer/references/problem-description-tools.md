# D2 Tools: 5W2H and Is / Is-Not

## 5W2H

| Question | Answer with | Example |
|----------|-------------|---------|
| What? | Part, feature, defect, measured value | Scratches 5-12 mm on face A of HS-110 |
| Where? | Where found, where on the part, which line/machine | Customer receiving, Plant 2; face A |
| When? | Production dates, shift, lot, when found | Lots shipped 2026-08-10 to 08-20 |
| Who? | Who found it (role), which customer | Customer incoming inspection |
| Why is it a problem? | Requirement violated, effect | Cosmetic spec CS-02 zone A; customer line rejects |
| How many? | Quantity, rate, trend | 60 of 400 (15%) in 2 lots |
| How detected? | Method that found it | Visual inspection at 1 m under 1000 lux |

## Is / is-not

| | Is | Is not | Distinction -> clue |
|---|----|--------|--------------------|
| What | Scratches on face A | Face B, edges | Face A faces the next part in the tray |
| Where (line) | Line 2 packed | Line 1 packed | Line 2 uses open trays |
| When | Since 2026-08-10 | Before August | New tray supplier from 08-08 |
| How many | 15% of parts | 0% before packing (50 checked) | Damage happens after packing |

Each distinction narrows the cause. Test candidate causes against the table: a true cause explains every "is" and every "is not".

## Problem statement template

> "[Defect] on [part/feature] found at [where] on [quantity] of [checked] parts from [lots/dates]; requirement is
> [spec]. Not seen on [is-not]."

No "because", "due to" or "caused by": the cause comes in D4.
