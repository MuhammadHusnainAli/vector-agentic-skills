---
name: minitab-analysis-interpreter
description: "Interpret Minitab output for quality and Six Sigma work: read pasted Session window or report text and extract the key numbers from Process Capability reports (Cp, Cpk, Pp, Ppk, observed vs expected PPM), Gage R&R ANOVA (%Study Var, %Tolerance, ndc, Part*Operator interaction, dominant component), regression (coefficients, P-values, VIF, S, R-sq, R-sq(adj), R-sq(pred)), one-way ANOVA, two-sample and paired t-tests (P-value, confidence interval), Anderson-Darling normality tests and DOE coded coefficients; flag what needs attention (Cpk below 1.33, Ppk well below Cpk, PPM far above prediction, GRR above 10 or 30 percent, ndc below 5, over-fitted models, insignificant terms, multicollinearity) and state the conclusion in plain words. Covers how to read each output and the most common misreadings. Use when someone pastes Minitab results and asks what they mean, before presenting results at a tollgate, or when checking a Green Belt's analysis."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Minitab Analysis Interpreter

Minitab prints everything; the skill is knowing which numbers decide the question and which warnings are hiding
in the output. `scripts/parse_minitab.py` recognises the common analyses in pasted text, extracts the deciding
numbers and marks problems (WARN) and conclusions (RESULT).

## Trigger Conditions

Activate this skill when the user:
- Pastes Minitab output and asks "what does this mean?" or "is this good?"
- Is preparing a DMAIC tollgate or report from Minitab results
- Needs a Green Belt or supplier analysis checked for mistakes
- Asks about R-sq(pred), VIF, %Study Var, ndc, Ppk vs Cpk or a p-value

Running the tests without Minitab: [hypothesis-test-selector](../hypothesis-test-selector/SKILL.md),
[manufacturing-cpk-capability-calculator](../manufacturing-cpk-capability-calculator/SKILL.md),
[gage-rr-msa-analyzer](../gage-rr-msa-analyzer/SKILL.md).

## Workflow

```
1. PASTE    -> save the Session window text (or copy from the report) to output.txt
2. PARSE    -> python scripts/parse_minitab.py output.txt
3. CONTEXT  -> what question was the analysis meant to answer? what data, how collected?
4. INTERPRET-> deciding numbers, warnings, conclusion in plain words (reading-minitab-output.md)
5. CHECK    -> graphs Minitab also produced: control chart, residual plots, normal probability plot
6. NEXT     -> what to do: collect more data, reduce the model, fix the gauge, act on the finding
```

## Example

```
Recognised: regression
        Regression: S 0.08812, R-sq 87.4%, R-sq(adj) 84.1%, R-sq(pred) 71.2%
WARN    R-sq(pred) 71.2% is 16 points below R-sq: the model is over-fitted; remove weak terms
WARN    term Speed: VIF 6.8 > 5: correlated with other predictors; coefficients unstable
```

Per-analysis guide (capability, Gage R&R, regression, t-tests, ANOVA, DOE) with criteria:
[reading-minitab-output.md](references/reading-minitab-output.md). Misreadings to correct:
[common-misreadings.md](references/common-misreadings.md).

## Output Format

Deliver:
1. **What was analysed** and the question it answers.
2. **Key numbers** (from `parse_minitab.py`).
3. **Interpretation** in plain words, including what the warnings mean.
4. **Validity checks** still needed (graphs, assumptions, data collection).
5. **Recommended next step.**

## Scripts

```bash
python scripts/parse_minitab.py output.txt [--alpha 0.05]
pbpaste | python scripts/parse_minitab.py -
```
Exit codes: 0 parsed with no warnings, 1 parsed with warnings, 2 nothing recognised or read error.

## Additional Resources

| File | Content |
|------|---------|
| [reading-minitab-output.md](references/reading-minitab-output.md) | Capability, Gage R&R, regression, t-test, ANOVA and DOE outputs and criteria |
| [common-misreadings.md](references/common-misreadings.md) | Ten common misreadings and the correct reading |
