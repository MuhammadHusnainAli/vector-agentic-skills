# Green Belt Study Guide

Green Belt exams (ASQ CSSGB, IASSC ICGB and company programmes) follow the DMAIC structure plus fundamentals.
Check the current Body of Knowledge, question count, time limit and allowed references with the certifying
body before you book: they change between editions.

## Domains and what to master

| Domain | Topics | Typical traps |
|--------|--------|---------------|
| Fundamentals | Six Sigma and organisational goals, roles, lean wastes, takt, value stream, RTY, Kano, DPMO and sigma | Average yield vs RTY; 1.5 sigma shift |
| Define | Charter, problem and goal statements, SIPOC, VOC and CTQ trees, scope, COPQ, stakeholders | Cause or solution in the problem statement |
| Measure | Data types, operational definitions, sampling, MSA (Gage R&R, ndc), basic statistics, capability (Cp, Cpk, Pp, Ppk), process maps | %Contribution vs %Study Var; within vs overall sigma |
| Analyze | Hypothesis testing roadmap, p-values, errors, correlation and regression, ANOVA, chi-square, root cause tools | "Accept H0"; correlation is not causation |
| Improve | DOE (full and fractional factorials, resolution, effects), solution selection, pilots, poka-yoke, lean tools | Effect vs coefficient; aliasing |
| Control | SPC charts and constants, run rules, control plans, reaction plans, standard work, handover | Control limits from specifications |

## Eight-week plan

| Week | Focus | Practice |
|------|-------|----------|
| 1 | Fundamentals and lean | `quiz.py --domain Fundamentals` |
| 2 | Define | Write a charter for a real problem |
| 3-4 | Measure: statistics, MSA, capability | Hand-calculate Cp/Cpk, R-bar/d2 |
| 5 | Analyze: tests and regression | Pick the test for 20 scenarios |
| 6 | Improve: DOE | Build a 2^(4-1) and compute effects by hand |
| 7 | Control: SPC | Calculate X-bar/R limits, apply run rules |
| 8 | Mixed mocks | `quiz.py --n 36` with new seeds; review every wrong answer |

## Exam technique

- Do the calculation questions with the formula sheet; mark long ones and return.
- Eliminate options that break definitions ("accept H0", "control limits from specs").
- Read for the qualifier: "first", "best", "most likely".
- Unit check: a Cpk of 8 or a probability above 1 is a wrong turn.
