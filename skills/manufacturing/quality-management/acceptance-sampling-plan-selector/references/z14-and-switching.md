# ANSI/ASQ Z1.4 (ISO 2859-1) Quick Reference

## Table I: code letters

| Lot size | S-1 | S-2 | S-3 | S-4 | I | II | III |
|----------|-----|-----|-----|-----|---|----|-----|
| 2-8 | A | A | A | A | A | A | B |
| 9-15 | A | A | A | A | A | B | C |
| 16-25 | A | A | B | B | B | C | D |
| 26-50 | A | B | B | C | C | D | E |
| 51-90 | B | B | C | C | C | E | F |
| 91-150 | B | B | C | D | D | F | G |
| 151-280 | B | C | D | E | E | G | H |
| 281-500 | B | C | D | E | F | H | J |
| 501-1,200 | C | C | E | F | G | J | K |
| 1,201-3,200 | C | D | E | G | H | K | L |
| 3,201-10,000 | C | D | F | G | J | L | M |
| 10,001-35,000 | C | D | F | H | K | M | N |
| 35,001-150,000 | D | E | G | J | L | N | P |
| 150,001-500,000 | D | E | G | J | M | P | Q |
| 500,001 and over | D | E | H | K | N | Q | R |

Sample sizes by letter: A 2, B 3, C 5, D 8, E 13, F 20, G 32, H 50, J 80, K 125, L 200, M 315, N 500, P 800,
Q 1250, R 2000.

## Common normal-inspection plans (level II)

| Lot size | Letter | n | AQL 0.65 | AQL 1.0 | AQL 1.5 | AQL 2.5 | AQL 4.0 |
|----------|--------|---|----------|---------|---------|---------|---------|
| 91-150 | F | 20 | 20 / 0 | 13 / 0 | 32 / 1 | 20 / 1 | 20 / 2 |
| 281-500 | H | 50 | 80 / 1 | 50 / 1 | 50 / 2 | 50 / 3 | 50 / 5 |
| 501-1,200 | J | 80 | 80 / 1 | 80 / 2 | 80 / 3 | 80 / 5 | 80 / 7 |
| 1,201-3,200 | K | 125 | 125 / 2 | 125 / 3 | 125 / 5 | 125 / 7 | 125 / 10 |
| 3,201-10,000 | L | 200 | 200 / 3 | 200 / 5 | 200 / 7 | 200 / 10 | 200 / 14 |

Entries are n / Ac (Re = Ac + 1). Where an arrow applies, the sample size changes: always run
`z14_plan.py` rather than reading across a row by eye.

## Inspection levels

| Level | Use |
|-------|-----|
| II | Default |
| I | Less discrimination needed, cheaper inspection |
| III | More discrimination (critical customers, history of problems) |
| S-1 to S-4 | Small samples for expensive or destructive tests, accepting larger risks |

## Switching rules (normal / tightened / reduced)

| From | To | Condition |
|------|----|-----------|
| Normal | Tightened | 2 of 5 or fewer consecutive lots rejected on original inspection |
| Tightened | Normal | 5 consecutive lots accepted on original inspection |
| Normal | Reduced | Switching score >= 30, steady production, and the responsible authority approves (optional) |
| Reduced | Normal | A lot rejected, irregular production, or other conditions warrant |
| Tightened | Discontinue | 5 consecutive lots remain on tightened inspection: stop acceptance under the standard until the supplier improves |

Without the switching rules, Z1.4 plans give much weaker protection than intended. Tightened and reduced plans
are in Tables II-B and II-C of the standard.

## Related standards

ANSI/ASQ Z1.9 / ISO 3951 (variables sampling, smaller samples for measured characteristics); ISO 2859-2 (isolated
lots, LQ-indexed); c = 0 plans (Squeglia) used by many automotive and defence customers who do not accept any
nonconforming units in the sample.
