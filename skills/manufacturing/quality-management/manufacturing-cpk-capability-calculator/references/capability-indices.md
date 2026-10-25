# Capability Indices

## Definitions

| Index | Formula | Sigma | Answers |
|-------|---------|-------|---------|
| Cp | (USL - LSL) / 6 sigma_within | Within subgroup (R-bar/d2, S-bar/c4, MR-bar/1.128) | Could the process fit if centred? |
| Cpk | min(USL - mean, mean - LSL) / 3 sigma_within | Within | Does it fit where it runs now (short term)? |
| Pp | (USL - LSL) / 6 sigma_overall | Overall sample standard deviation | Long-term spread vs tolerance |
| Ppk | min(USL - mean, mean - LSL) / 3 sigma_overall | Overall | What the customer actually receives |
| Cpm | (USL - LSL) / 6 sqrt(sigma^2 + (mean - target)^2) | Overall + off-target | Penalises distance from nominal (Taguchi) |

One-sided specs (flatness, runout, minimum strength): only Cpu or Cpl exists; Cp/Pp are undefined.

## Index -> expected defect rate (centred, normal)

| Cpk | Sigma level (short term) | ppm out of spec (two-sided, centred) |
|-----|--------------------------|--------------------------------------|
| 0.67 | 2 | 45,500 |
| 1.00 | 3 | 2,700 |
| 1.33 | 4 | 63 |
| 1.50 | 4.5 | 6.8 |
| 1.67 | 5 | 0.57 |
| 2.00 | 6 | 0.002 |

## Typical requirements

| Context | Requirement |
|---------|-------------|
| Automotive PPAP initial study (special characteristics) | Ppk > 1.67 accepted; 1.33-1.67 customer review |
| Ongoing production (IATF / most customers) | Cpk >= 1.33 |
| Safety / critical characteristics | Often Cpk >= 1.67 or 2.00 per CSR |
| Aerospace key characteristics (AS9103) | Cpk >= 1.33 typical, with variation management |

## Reading the results

| Pattern | Meaning | Action |
|---------|---------|--------|
| Cp high, Cpk low | Off centre | Re-centre (offset, nominal setting) |
| Cpk high, Ppk much lower | Shifts or drift between subgroups | Stabilise (SPC, tool wear, warm-up) |
| Cp < 1 | Process spread wider than tolerance | Reduce variation (DOE, equipment) or negotiate tolerance |
| Wide confidence interval | Too little data | Collect more: the CI halves with 4x the data |
| Observed ppm >> expected | Non-normal tails or special causes | Check distribution and control chart |

Confidence interval for Cpk (Bissell): Cpk +/- z sqrt(1/(9n) + Cpk^2 / (2(n - 1))). With n = 125 and Cpk 1.35 the
95% interval is about 1.17 to 1.53, so "1.35" does not prove ">= 1.33".
