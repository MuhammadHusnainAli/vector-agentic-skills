# Defining Effectiveness Criteria

ISO 9001 10.2.1 d requires reviewing the effectiveness of corrective action. "No recurrence so far" is only evidence
if the problem had enough opportunities to recur.

## Set the criterion when the CAPA is opened

| Element | Ask | Example |
|---------|-----|---------|
| Metric | What shows the problem? | Bore NCRs per 1,000 parts; customer complaints on HS-110 |
| Baseline | What was the rate before? | 12 defects in 4,000 parts (3,000 ppm) |
| Target | What rate means "fixed"? | < 500 ppm, or zero over the demonstration quantity |
| Window | How long / how many units? | Until 3,000 parts or 3 months, whichever is later |
| Evidence | Where does the data come from? | NCR log, SPC, customer scorecard |
| Owner, date | Who decides and when? | Quality engineer, 2027-03-01 |

## Choosing the window

| Problem frequency before | Window |
|--------------------------|--------|
| Several per week | 4-8 weeks of production |
| A few per month | 3 months, and enough units for `effectiveness.py rate` to reach significance |
| Rare (a few per year) | Zero-defect demonstration (`effectiveness.py zero`) plus a leading indicator |
| Seasonal or product-mix dependent | Cover the same season / product mix as the failure |

## Leading indicators (when failures are rare)

- Capability of the characteristic (Cpk) before vs after.
- Control-chart stability and no out-of-control signals.
- Error-proofing verification records (daily red-rabbit checks).
- LPA question on the new control passes consistently.
- Audit of the changed procedure in use.

## Verdicts and what to do

| Verdict | Action |
|---------|--------|
| Effective | Close the CAPA; remove extra containment; update lessons learned |
| Not yet demonstrated | Keep monitoring to the computed quantity; keep containment |
| Not effective | Re-open root cause; the cause was wrong or incomplete; do not just extend the date |

## Traps

- **Volume changes:** compare rates (per unit), never counts.
- **Detection changes:** if inspection changed, the defect rate may change because detection did.
- **Containment masking:** 100% sorting hides recurrence at the customer; measure at the process, before the sort.
- **Closing on the implementation date:** implementation is not effectiveness.
