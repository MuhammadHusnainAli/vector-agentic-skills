---
name: hypothesis-test-selector
description: "Choose and run the right hypothesis test for Six Sigma Analyze and quality decisions: test roadmap by Y type (continuous, proportion, count) and X type (target, two groups, paired, several groups, continuous) covering 1-sample, 2-sample Welch and paired t-tests, F and Levene tests for variances, one-way ANOVA, Mann-Whitney, Kruskal-Wallis, 2-proportion, McNemar, chi-square of association, Poisson rate tests, correlation, regression and logistic regression, with assumptions, non-parametric alternatives and Minitab menu paths. Runs t1, t2, paired, var2, anova, Mann-Whitney, 2-proportion and chi-square tests from CSV data with confidence intervals and a plain-language conclusion. Covers H0/H1, p-values vs practical significance, type I/II errors, sample size and power tables, and common mistakes. Use when comparing machines, suppliers, shifts or before/after results, testing a suspected root cause with data, or deciding which statistical test to use."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Hypothesis Test Selector

The right test follows from two questions: what type is the output (Y), and what is being compared (X)? Then the
answer is a confidence interval and a practical conclusion, not only a p-value. `scripts/pick_test.py` chooses
the test; `scripts/run_test.py` runs the common ones on CSV data using `scripts/_stats.py` for the distributions.

## Trigger Conditions

Activate this skill when the user:
- Wants to know if two machines, suppliers, shifts or methods really differ
- Needs to verify a suspected root cause with data (DMAIC Analyze)
- Asks which statistical test to use, or how many samples are needed
- Has before/after data and wants to prove an improvement

Interpreting Minitab output instead: [minitab-analysis-interpreter](../minitab-analysis-interpreter/SKILL.md).

## Workflow

```
1. QUESTION -> practical question; Y type; X type; paired?; mean or spread?
2. PICK     -> python scripts/pick_test.py --y continuous --x 2-groups [--paired] [--not-normal]
3. SIZE     -> enough samples for the difference that matters? (assumptions-and-power.md)
4. CHECK    -> normality, equal variances, independence
5. RUN      -> python scripts/run_test.py t2 data.csv --col diameter --group machine
6. DECIDE   -> p-value AND confidence interval -> practical conclusion
```

## Example

```
2-sample Welch t: L1 mean 12.00921 (n 30), L2 mean 12.01062 (n 30); t = -2.817, df = 56.8
  95% CI for L1 - L2: -0.002404547 to -0.0004061197
p = 0.006665 < alpha 0.05: significant - the means differ.
```
L2 runs about 0.0004-0.0024 mm larger: statistically real, and worth an offset correction only if it matters
against the 0.018 mm tolerance.

Roadmap table, the eight steps and reading p-values: [test-roadmap.md](references/test-roadmap.md). Assumption
checks, type I/II errors, sample size tables and common mistakes: [assumptions-and-power.md](references/assumptions-and-power.md).

## Output Format

Deliver:
1. **Question** in practical and statistical form (H0, H1, alpha).
2. **Test choice** and why; assumptions checked.
3. **Result** - statistic, p-value, confidence interval / effect size.
4. **Conclusion** in plain words and the decision it supports; power caveat if not significant.

## Scripts

```bash
python scripts/pick_test.py --y continuous --x 2-groups --paired
python scripts/pick_test.py --y proportion --x k-groups
```
Exit codes: 0 recommendation, 2 combination not covered.

```bash
python scripts/run_test.py t1 data.csv --col diameter --mu 12.009
python scripts/run_test.py t2 data.csv --col diameter --group machine
python scripts/run_test.py paired data.csv --a before --b after
python scripts/run_test.py var2 data.csv --col diameter --group machine
python scripts/run_test.py anova data.csv --col diameter --group machine
python scripts/run_test.py mannwhitney data.csv --col diameter --group machine
python scripts/run_test.py prop2 --x1 12 --n1 400 --x2 4 --n2 380
python scripts/run_test.py chi2 table.csv
```
Exit codes: 0 not significant, 1 significant at --alpha, 2 usage or data error.

## Additional Resources

| File | Content |
|------|---------|
| [test-roadmap.md](references/test-roadmap.md) | Y/X roadmap with alternatives, hypothesis testing steps, reading p-values |
| [assumptions-and-power.md](references/assumptions-and-power.md) | Assumptions and remedies, error types, sample size tables, mistakes |
