# Counting Defect Opportunities

DPMO depends on the opportunity count. Count generously and the sigma level looks great; count consistently and
it becomes a useful comparison.

## Rules

1. An opportunity is a **measurable characteristic that the customer cares about and that can independently fail**.
2. Count only what is **inspected or measured**; unmeasured opportunities cannot generate defects.
3. Do not count trivial items (each solder joint on a board may count; each line of a standard form usually not).
4. Keep the count **fixed** for a product once defined; document it.
5. When in doubt, report DPU and ppm alongside DPMO.

## Examples

| Unit | Opportunities | Count |
|------|---------------|-------|
| Machined housing | 12 drawing characteristics inspected + 2 visual (burr, scratch) | 14 |
| PCB assembly | Components placed (polarity, presence) + solder joints | 120 components, 640 joints -> 760 |
| Invoice | Customer, amount, PO number, due date, tax | 5 |
| Wire harness | Wires routed, terminals crimped, connectors seated | per drawing |

## Hidden factory and RTY

The yield reported at final inspection often looks high because rework in earlier steps is invisible.
RTY multiplies first-pass yields of every step: 98% x 95% x 99.5% x 97% = 89.9%, so one unit in ten is
touched twice. Collect first-pass data at each step (not just final yield) to see it.

## Worked example

38 defects found on 1,200 housings with 14 opportunities each:
DPU = 0.032, DPO = 0.00226, DPMO = 2,262, sigma = 4.34 (short term). With 7 opportunities the same data would
give DPMO 4,524 and sigma 4.11: always quote the opportunity count with a sigma level.
