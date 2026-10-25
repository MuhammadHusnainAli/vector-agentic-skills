# AIAG-VDA PFMEA Method (FMEA Handbook 2019)

## Seven steps

| Step | Content | Output |
|------|---------|--------|
| 1 Planning and preparation | Scope, team, timing (5T: intent, timing, team, tasks, tools) | Project plan |
| 2 Structure analysis | Process item -> process steps -> process work elements (4M: man, machine, material, environment) | Structure tree from the process flow diagram |
| 3 Function analysis | Functions and requirements (product and process characteristics) for each element | Function net |
| 4 Failure analysis | Failure chain: effect (at the next level / customer) - failure mode (step) - cause (work element) | Failure net |
| 5 Risk analysis | Current prevention and detection controls; rate S, O, D; Action Priority | Ratings, AP |
| 6 Optimisation | Actions to reduce O (prevention) and improve D (detection); owners, dates; re-rate | Action plan |
| 7 Results documentation | Report, communication to customer, link to control plan | FMEA report |

## Rating guidance (process)

| Rating | Severity (effect) | Occurrence (prevention effectiveness) | Detection (detection ability) |
|--------|-------------------|---------------------------------------|-------------------------------|
| 10 | Safety or regulatory noncompliance without warning | Very high: no prevention | No detection or not analysed |
| 9 | Safety / regulatory with warning | | Not likely to detect (random audits) |
| 7-8 | Loss or degradation of primary function; 100% scrap / line shutdown | High: prevention known but ineffective | Visual / manual inspection, low detection |
| 4-6 | Loss of secondary function; rework, partial scrap | Moderate: prevention partly effective | Variable gauging, SPC with human reaction; post-process |
| 2-3 | Appearance / noise noticed by some customers | Low: proven prevention, few occurrences | Automatic detection downstream / in-station |
| 1 | No discernible effect | Extremely low: error-proofed by design or process | Error-proofing prevents the failure mode (cannot be made) |

Use the handbook tables (and customer modifications) for the exact criteria. Two rules prevent most rating errors:
- **D 1-3 requires an automatic or error-proofing detection control.** Visual inspection is never better than about D7.
- **O 1-2 requires a proven prevention control** (error-proofed design or process, history).

## Action Priority table (S band x O band x D band -> H / M / L)

| S | O | D 7-10 | D 5-6 | D 2-4 | D 1 |
|---|---|--------|-------|-------|-----|
| 9-10 | 8-10 | H | H | H | H |
| 9-10 | 6-7 | H | H | H | H |
| 9-10 | 4-5 | H | H | H | M |
| 9-10 | 2-3 | H | M | L | L |
| 9-10 | 1 | L | L | L | L |
| 7-8 | 8-10 | H | H | H | H |
| 7-8 | 6-7 | H | H | H | M |
| 7-8 | 4-5 | H | M | M | M |
| 7-8 | 2-3 | M | M | L | L |
| 7-8 | 1 | L | L | L | L |
| 4-6 | 8-10 | H | H | M | M |
| 4-6 | 6-7 | M | M | M | L |
| 4-6 | 4-5 | M | L | L | L |
| 4-6 | 2-3 | L | L | L | L |
| 4-6 | 1 | L | L | L | L |
| 2-3 | 8-10 | M | M | L | L |
| 2-3 | 6-7 and lower | L | L | L | L |
| 1 | any | L | L | L | L |

**H**: action required to improve prevention and/or detection, or justification documented and approved.
**M**: action should be taken, or justification documented. **L**: action could be taken.

## AP vs RPN

RPN = S x O x D weights the three ratings equally, so S10 O2 D3 (60) ranks below S4 O5 D5 (100). AP puts severity
first, then occurrence, then detection. `pfmea_ap.py` reports both so legacy customers that still ask for RPN
can be served, but prioritise by AP.
