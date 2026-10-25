# Choosing a Control Chart and Its Constants

## Selection

| Data | Subgroup / sample | Chart | Notes |
|------|-------------------|-------|-------|
| Continuous measurement | n = 1 (slow processes, batch, destructive tests) | I-MR | Sensitive to non-normality; consider transforming |
| Continuous | n = 2-9 (typically 3-5 consecutive parts) | X-bar / R | Most common in machining and moulding |
| Continuous | n >= 10, or variable n | X-bar / S | S uses all data in the subgroup |
| Defective units (pass/fail) | Constant n | np | Count of defectives |
| Defective units | Varying n | p | Fraction defective; limits vary per sample |
| Defects (several per unit possible) | Constant inspection area / units | c | Count of defects |
| Defects | Varying units | u | Defects per unit; limits vary |

Rational subgrouping: parts in a subgroup are made under the same conditions (consecutive parts, same cavity,
same tool), so within-subgroup variation is common cause and between-subgroup variation shows shifts.

## Formulas

| Chart | Centre | Limits |
|-------|--------|--------|
| I | x-bar | x-bar +/- 2.66 MR-bar (= 3 MR-bar / 1.128) |
| MR | MR-bar | UCL 3.267 MR-bar, LCL 0 |
| X-bar (R) | X-double-bar | X-double-bar +/- A2 R-bar |
| R | R-bar | D4 R-bar, D3 R-bar |
| X-bar (S) | X-double-bar | X-double-bar +/- A3 S-bar |
| S | S-bar | B4 S-bar, B3 S-bar |
| p | p-bar | p-bar +/- 3 sqrt(p-bar (1 - p-bar) / n_i) |
| np | n p-bar | n p-bar +/- 3 sqrt(n p-bar (1 - p-bar)) |
| c | c-bar | c-bar +/- 3 sqrt(c-bar) |
| u | u-bar | u-bar +/- 3 sqrt(u-bar / n_i) |

Negative lower limits are set to 0.

## Constants

| n | A2 | D3 | D4 | d2 | A3 | B3 | B4 | c4 |
|---|----|----|----|----|----|----|----|----|
| 2 | 1.880 | 0 | 3.267 | 1.128 | 2.659 | 0 | 3.267 | 0.7979 |
| 3 | 1.023 | 0 | 2.574 | 1.693 | 1.954 | 0 | 2.568 | 0.8862 |
| 4 | 0.729 | 0 | 2.282 | 2.059 | 1.628 | 0 | 2.266 | 0.9213 |
| 5 | 0.577 | 0 | 2.114 | 2.326 | 1.427 | 0 | 2.089 | 0.9400 |
| 6 | 0.483 | 0 | 2.004 | 2.534 | 1.287 | 0.030 | 1.970 | 0.9515 |
| 7 | 0.419 | 0.076 | 1.924 | 2.704 | 1.182 | 0.118 | 1.882 | 0.9594 |
| 8 | 0.373 | 0.136 | 1.864 | 2.847 | 1.099 | 0.185 | 1.815 | 0.9650 |
| 9 | 0.337 | 0.184 | 1.816 | 2.970 | 1.032 | 0.239 | 1.761 | 0.9693 |
| 10 | 0.308 | 0.223 | 1.777 | 3.078 | 0.975 | 0.284 | 1.716 | 0.9727 |

`_spc.py` stores d2 and d3 and derives A2, D3, D4; it computes c4 exactly, so S charts work for any n.
