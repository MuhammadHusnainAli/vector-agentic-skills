# Writing Model Cards

Based on Mitchell et al. (2019), "Model Cards for Model Reporting", the Hugging Face model card guide, and
common model-risk review practice (e.g. SR 11-7 style documentation).

## Section by section

**Model details.** One paragraph that a non-specialist can follow: what is predicted, for whom, when it runs,
and what happens with the score. Add the type, version, date, owners, licence and framework.

> Bad: "A gradient boosting model for churn."
> Good: "Scores active consumer subscribers every Monday with the probability of cancelling within 60 days.
> The top-scored customers are offered a retention call by the retention team."

**Intended use / out of scope.** Name the decision and the users. Out-of-scope entries stop misuse: other
populations, other decisions, automated use without review, uses with legal effects.

**Data.** Give the source, the **period**, the size, the label definition (exactly when an event counts),
the sampling and filtering, and known gaps (segments absent or under-represented). Evaluation data must be
held out from training. Say whether it is random, grouped or out-of-time.

**Evaluation.** Use the metrics the decision needs (see
[ml-success-metric-selector](../../ml-success-metric-selector/SKILL.md)), with 95% CIs, on the evaluation data.
Add the baseline (the current process or a simple rule), the decision threshold and its rationale, and the
calibration if probabilities are used directly.

**Performance across groups.** Use the same metrics for each slice that matters: protected or sensitive
groups (where lawful to use for evaluation), customer segments, regions, channels, and data-quality strata
(new vs long-standing customers). Mark small slices. Explain what is done about gaps.

**Fairness.** State which attributes were assessed, which fairness notion fits the decision and why, the
measured gaps, and the decision taken (accept with reason, mitigate, restrict use).

**Explainability.** Global drivers, and how individual decisions are explained (reason codes, SHAP
background, LIME), with links to the reports.

**Limitations.** List concrete conditions where the model is unreliable: thin-file customers, new products,
regime changes, extrapolation ranges, known label noise.

**Ethical considerations.** Cover who is affected and how, sensitive features and their proxies, potential
harms (denial of service, unequal treatment, privacy), and the human oversight in place.

**Risks and mitigations.** Each risk gets a mitigation and an owner. Unmitigated risks are stated as accepted.

**Monitoring and maintenance.** List the monitored metrics (with label delay), drift checks, alert
thresholds, the retraining cadence or trigger, the owner, and the decommission criteria.

## Words to avoid

| Avoid | Write instead |
|-------|---------------|
| "unbiased", "fair", "bias-free" | the measured gaps and the notion used |
| "state of the art" | the comparison: "+0.11 AUC over the current rule" |
| "highly accurate" | the metric, value and CI |
| "works for all customers" | the populations evaluated and the slices with low n |
| "will be monitored" | what, how often, the threshold, and who |

## Review checklist

- [ ] a non-specialist can tell what the model does and must not be used for
- [ ] data periods and label definition stated; evaluation data held out (out-of-time if applicable)
- [ ] every metric has a CI and a data split; baseline and threshold given
- [ ] performance by group with CIs; small slices marked; gaps addressed
- [ ] limitations and ethical considerations specific to this model
- [ ] risks have mitigations and owners
- [ ] monitoring plan with thresholds and owner
- [ ] version, date and contact; no TODOs (`card_lint.py` clean)
