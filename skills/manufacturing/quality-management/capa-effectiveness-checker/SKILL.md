---
name: capa-effectiveness-checker
description: "Verify whether a corrective action actually worked (ISO 9001 10.2.1 d, IATF 16949, 8D D6) with statistics instead of 'no complaints so far': before/after defect-rate comparison with an exact conditional binomial test for Poisson counts and a minimum practical reduction, zero-defect demonstration size (n = ln(1-C)/ln(1-p), rule of three) with progress so far, and exact Clopper-Pearson upper bounds on the post-action defect rate. Returns effective, not yet demonstrated (with the units still needed) or not effective. Covers setting effectiveness criteria when the CAPA is opened, choosing the window by problem frequency, leading indicators for rare failures (Cpk, SPC stability, error-proofing checks, LPA), and traps such as volume changes, detection changes and containment masking. Use when closing a CAPA or 8D, deciding how long to monitor, or challenging a CAPA closed on its implementation date."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# CAPA Effectiveness Checker

Implementation is not effectiveness. A corrective action is effective when the defect rate has dropped by a
meaningful amount and the data is strong enough to rule out luck. `scripts/effectiveness.py` answers the three
questions this needs: did the rate drop significantly, how many defect-free units prove a target, and what is
the worst rate still consistent with the data?

## Trigger Conditions

Activate this skill when the user:
- Wants to close a CAPA or 8D and needs to show it worked
- Asks how long to monitor, or how many parts without defects are enough
- Has before/after defect counts and wants a verdict
- Is reviewing CAPAs closed on their implementation date

The CAPA itself: [capa-plan-writer](../capa-plan-writer/SKILL.md).

## Workflow

```
1. CRITERION -> at CAPA opening: metric, baseline, target, window, evidence source, owner, date
2. COLLECT   -> defects and units before and after, measured at the process (not after a sort)
3. TEST      -> python scripts/effectiveness.py rate --before 12 --before-units 4000 --after 1 --after-units 3500
4. RARE      -> python scripts/effectiveness.py zero --target 0.001 --so-far 1200
5. STATE     -> python scripts/effectiveness.py upper --defects 0 --units 3000 --target 0.001
6. DECIDE    -> effective: close and remove containment; not yet: keep monitoring; not effective: re-open root cause
```

## Verdicts

| Verdict | Condition | Action |
|---------|-----------|--------|
| EFFECTIVE | p < alpha and reduction >= min-reduction (default 50%) | Close, remove extra containment |
| NOT YET DEMONSTRATED | Rate fell but not significantly, or reduction too small | Continue to the stated quantity |
| NOT EFFECTIVE | After rate >= before rate | Re-open root cause analysis |

```
Before: 12 defects in 4000 units = 3,000 ppm (0.3000%)
After:  1 defects in 3500 units = 286 ppm (0.0286%)
Reduction: 90%   one-sided p-value (after < before): 0.0035
Verdict: EFFECTIVE - significant at alpha 0.05 with 90% reduction (>= 50%)
```

Criterion elements, monitoring windows by problem frequency, leading indicators and traps:
[effectiveness-criteria.md](references/effectiveness-criteria.md). The test, zero-defect table, upper bounds and
continuous characteristics: [statistics-guide.md](references/statistics-guide.md).

## Output Format

Deliver:
1. **Criterion** - metric, baseline, target, window.
2. **Data** - before and after defects and units, source, and whether measured before any containment sort.
3. **Result** - `effectiveness.py` output (rate test, upper bound, zero-defect progress).
4. **Verdict and next step** - close, continue to N units, or re-open the root cause.

## Scripts

```bash
python scripts/effectiveness.py rate --before 12 --before-units 4000 --after 1 --after-units 3500 [--alpha 0.05 --min-reduction 0.5]
python scripts/effectiveness.py zero --target 0.001 --confidence 0.95 --so-far 1200
python scripts/effectiveness.py upper --defects 1 --units 3500 --confidence 0.95 --target 0.002
```
Exit codes: 0 effective / requirement met, 1 not effective or not yet demonstrated, 2 usage error.

## Additional Resources

| File | Content |
|------|---------|
| [effectiveness-criteria.md](references/effectiveness-criteria.md) | Criterion elements, windows, leading indicators, verdict actions, traps |
| [statistics-guide.md](references/statistics-guide.md) | Exact rate test, zero-defect sample sizes, Clopper-Pearson bounds, practical vs statistical significance |
