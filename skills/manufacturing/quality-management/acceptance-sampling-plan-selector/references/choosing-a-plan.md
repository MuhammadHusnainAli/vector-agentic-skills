# Choosing a Sampling Plan

## When sampling is (and is not) appropriate

| Use sampling | Do not rely on sampling |
|--------------|-------------------------|
| Incoming inspection of purchased lots | Safety / critical characteristics (CC): use 100% automatic inspection or error-proofing |
| Testing is destructive or expensive | Process making the lots is unstable: fix the process |
| Large volumes with good supplier history | Customer requires zero defects and c = 0 plans are not enough |
| Audit of outgoing product | As a substitute for process control (SPC) |

## Picking the AQL

AQL is the worst **process average** you will tolerate as acceptable; it is not a promise that each lot is that
good. Common practice by defect class:

| Defect class | Typical AQL |
|--------------|-------------|
| Critical (safety) | 0 accepted: 100% / error-proofing, or c = 0 with high n |
| Major (function, fit) | 0.65-1.0% |
| Minor (cosmetic, non-functional) | 2.5-4.0% |

Use the customer's AQLs when specified. Classify each characteristic and pick a plan per class.

## Reading the OC curve

| Point | Meaning |
|-------|---------|
| p at Pa 0.95 | Quality the producer can expect to pass 95% of the time (producer's risk alpha = 5%) |
| p at Pa 0.10 | LTPD: quality the consumer will accept only 10% of the time (consumer's risk beta = 10%) |
| AOQL | With rejected lots 100% sorted, the worst long-run average outgoing quality |

Example (n = 80, c = 2, lot 1000): accepts 1.0% lots 95% of the time, still accepts 6.3% lots 10% of the time; AOQL
about 1.6%. If 6% nonconforming lots are unacceptable, this plan does not protect you.

## Designing from risks

State the producer's point (AQL, alpha) and the consumer's point (LTPD, beta) and solve for n and c
(`oc_curve.py design`). Example: AQL 1%, alpha 5%, LTPD 5%, beta 10% -> n = 132, c = 3.

## c = 0 plans

Accept only with zero nonconforming units in the sample. Sample size for LTPD p at consumer risk beta:
n = ln(beta) / ln(1 - p) (about 2.3 / p at beta 10%). They reject good lots more often than Z1.4 plans at the same
LTPD, so producers need a process far better than the LTPD.

## Executing the plan

- Draw the sample **at random** from the whole lot (all boxes, layers, cavities), not from the top.
- Define what counts as nonconforming with limit samples and a calibrated gauge.
- Record lot, plan, sample, results and decision; apply switching rules over lot history.
- A rejected lot is not "re-sampled until it passes": sort it 100% or return it.
