# Communicating Recourse

## Wording

> "Based on the information we used, any one of the following would likely have led to a different outcome:
> - reducing your number of open support tickets from 10 to 7 and logging in within the next two weeks, or
> - reducing your number of open support tickets to 5.
> These are not guarantees. Our assessment can also change as other information changes."

- Give options, ordered by effort, in real units and time frames.
- Avoid technical terms (MAD, log-odds) and model internals.
- Do not present a single counterfactual as "the reason". Reasons come from attribution (SHAP reason codes).
- Do not suggest changing immutable or protected characteristics, or their proxies.
- Re-check before sending: the counterfactual must still flip the current model version.

## Regulation (orientation, not legal advice)

| Context | Relevance |
|---------|-----------|
| US credit (ECOA / Regulation B adverse-action notices, FCRA) | principal reasons for denial are required. Counterfactuals can complement them, but do not replace them |
| EU GDPR Art. 22 and recital 71 | safeguards for solely automated decisions, including the right to contest. Counterfactuals are widely discussed as a way to provide meaningful information (Wachter, Mittelstadt and Russell 2017) |
| EU AI Act (high-risk systems) | transparency and human oversight obligations; recourse supports both |

Have legal and compliance review the method and the wording before customer-facing use.

## Fairness of recourse

Equal accuracy does not imply equal recourse. Audit across groups:
- the share of negatively decided people with **no recourse** (immutable features decide)
- the **cost** of the cheapest recourse (median MAD units) per group
- **essential** features per group (e.g. income is essential for one group and not another)

```bash
# loop linear_counterfactual.py over rejected rows and aggregate by group
for row in rejected/*.json; do
  python linear_counterfactual.py model.json "$row" --threshold 0.5 --json
done > recourse.jsonl
```
Large gaps in recourse cost (Ustun et al. 2019; Gupta et al. 2019 "equalizing recourse") belong in the model
card ([model-card-writer](../../model-card-writer/SKILL.md)) and may need model changes (fewer immutable
drivers, monotonic constraints).

## Gaming and robustness

- Counterfactuals reveal the model's decision boundary. Customers may change proxies without changing the
  underlying risk ("game" the model). Prefer recourse through features that are causally related to the
  outcome.
- A counterfactual valid for today's model can be invalid after a retrain. Recompute it, and avoid making
  commitments ("if you do X, you will be approved") unless you will honour them.
- Prefer robust counterfactuals: a small margin beyond the threshold (`--margin`, or a target probability
  below the threshold) survives small model changes.
