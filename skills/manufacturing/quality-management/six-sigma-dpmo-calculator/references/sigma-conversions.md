# Sigma Level Conversions

## Table (short-term sigma with the 1.5 shift, one-sided tail)

| Sigma level | DPMO | Yield |
|-------------|------|-------|
| 2 | 308,538 | 69.1% |
| 2.5 | 158,655 | 84.1% |
| 3 | 66,807 | 93.3% |
| 3.5 | 22,750 | 97.7% |
| 4 | 6,210 | 99.38% |
| 4.5 | 1,350 | 99.865% |
| 5 | 233 | 99.977% |
| 5.5 | 32 | 99.9968% |
| 6 | 3.4 | 99.99966% |

Formulas: sigma = Phi^-1(1 - DPMO / 10^6) + 1.5; DPMO = 10^6 (1 - Phi(sigma - 1.5)).

## The 1.5 shift

Motorola's convention assumes a process mean drifts by about 1.5 sigma over the long term, so a process with
short-term capability Z = 6 delivers 3.4 DPMO long term. It is a reporting convention, not a law: when
comparing with Cpk or long-term data, state whether the shift is included (`--no-shift` gives long-term Z).
Relationship to capability: Z_short-term ~ 3 Cpk (e.g. Cpk 1.33 ~ 4 sigma short term, before the shift).

## Units in use

| Metric | Formula | Use |
|--------|---------|-----|
| DPU | defects / units | Assembly, complex units with several defects each |
| DPO | defects / (units x opportunities) | Comparing processes of different complexity |
| DPMO | DPO x 10^6 | Sigma level |
| ppm defective | defective units / units x 10^6 | Customer quality (one bad unit = one count) |
| FTY | units passing first time / units in | One step |
| RTY | product of step FTYs | Whole process; e^-total DPU for Poisson defects |

ppm and DPMO are not the same: a unit with three defects is 1 defective (ppm) but 3 defects (DPMO).
