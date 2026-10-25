# DMAIC Phases and Tollgate Questions

| Phase | Key tools | Tollgate questions (champion asks) |
|-------|-----------|------------------------------------|
| Define | Charter, SIPOC, VOC/CTQ tree, stakeholder map | Is the problem real, measured and worth solving? Is the scope right? Is the team resourced? |
| Measure | Operational definitions, data collection plan, MSA, baseline capability, process map | Can we trust the measurement? What is the baseline (and its variation)? |
| Analyze | Fishbone, 5 Why, stratification, hypothesis tests, regression, multi-vari | Which root causes are verified with data? How much of the gap do they explain? |
| Improve | DOE, solution selection, pilot, FMEA of the solution | Did the pilot move the metric? Are risks of the solution controlled? |
| Control | Control plan, SPC, error-proofing, standard work, handover | Is the gain sustained? Does the process owner own the controls? Are savings validated? |

## SIPOC (Define)

| Suppliers | Inputs | Process (5-7 steps) | Outputs | Customers |
|-----------|--------|---------------------|---------|-----------|
| Casting supplier, tool supplier | Castings, inserts, programs | Load -> rough bore -> finish bore -> measure -> unload | Machined bodies, inspection data | Assembly, end customer |

## COPQ categories

| Category | Examples |
|----------|----------|
| Internal failure | Scrap, rework, re-inspection, downtime from defects |
| External failure | Returns, sorting at the customer, charge-backs, premium freight, warranty |
| Appraisal | Extra inspection and testing caused by the problem |
| Prevention | Training, error-proofing (investment, not COPQ) |

Use `copq.py` to put a number on the business case; have finance confirm hard savings at the Control tollgate.

## Reasons projects fail

Scope too big; problem statement contains the solution; no baseline or untrusted measurement; champion absent at
tollgates; no process owner to keep the gains; savings claimed but never validated.
