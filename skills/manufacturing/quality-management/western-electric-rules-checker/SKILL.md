---
name: western-electric-rules-checker
description: "Detect special-cause patterns on control charts with the Western Electric rules (1 point beyond 3 sigma, 2 of 3 beyond 2 sigma, 4 of 5 beyond 1 sigma, 8 in a row on one side) and optionally the Nelson rules (9 in a row, 6-point trends, 14 alternating points, 15 points hugging the centre, 8 points avoiding the centre). Works from given centre and sigma, from control limits, or from a Phase I baseline; merges overlapping hits into one signal per pattern and names the likely manufacturing cause (setting change, new lot, tool wear, tampering, stratification, mixture). Covers zones, false-alarm rates and average run length, which rules to use in Phase I vs Phase II and on range or attribute charts, autocorrelation, and how to respond to a signal without tampering. Use when reviewing an SPC chart, deciding whether a process is in control, or explaining a pattern on a chart."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Western Electric Rules Checker

Points beyond the control limits catch big changes; run rules catch the small shifts, trends and mixtures that
cause most drift into nonconformity. `scripts/we_rules.py` applies the Western Electric (and optionally Nelson)
rules, merges overlapping hits so a single shift reports once, and gives the usual cause of each pattern.

## Trigger Conditions

Activate this skill when the user:
- Has control chart data and wants to know whether the process is in control
- Sees a pattern (run, trend, saw-tooth, hugging) and asks what it means
- Asks which run rules to use, or why the chart signals so often
- Needs to document special-cause signals for a Phase I study or audit

Limits for the chart: [manufacturing-spc-chart-builder](../manufacturing-spc-chart-builder/SKILL.md).

## Workflow

```
1. LIMITS   -> centre and sigma of the plotted statistic from a stable baseline (or the chart's UCL/LCL)
2. CHECK    -> python scripts/we_rules.py chart.csv --value xbar --ucl 12.0121 --lcl 12.0063 [--nelson]
3. ORDER    -> investigate signals in time order; the first point of a run is where something changed
4. CAUSE    -> what changed then (lot, tool, operator, setting, maintenance)? patterns-and-causes.md
5. RESPOND  -> contain if needed, fix the cause, annotate the chart; no limit recalculation to hide signals
```

## Rules

| Code | Rule | Pattern |
|------|------|---------|
| WE1 | 1 point beyond 3 sigma | Sudden special cause |
| WE2 | 2 of 3 beyond 2 sigma, same side | Shift starting |
| WE3 | 4 of 5 beyond 1 sigma, same side | Small shift |
| WE4 / N2 | 8 (Nelson: 9) in a row on one side | Sustained shift |
| N3 | 6 in a row increasing or decreasing | Trend (wear, heating) |
| N4 | 14 alternating | Tampering, two streams |
| N7 | 15 within 1 sigma | Stratification |
| N8 | 8 beyond 1 sigma on both sides | Mixture |

```
WE3 at 19 (points 15-24): a small sustained shift: tool wear, temperature, gradual change
N2 at 23 (points 15-24): a sustained shift in the mean
N3 at 45 (points 40-47): a trend: tool wear, heating, chemical depletion
```

Zones, Nelson numbering, false-alarm rates and ARL, rule choice for Phase I/II, R and attribute charts,
autocorrelation: [rules-and-false-alarms.md](references/rules-and-false-alarms.md). Pattern-to-cause table and how to
respond: [patterns-and-causes.md](references/patterns-and-causes.md).

## Output Format

Deliver:
1. **Basis** - centre and sigma used and where they came from; rule set.
2. **Signals** - rule, span of points, likely cause, in time order.
3. **Verdict** - in control or not; which signals need investigation first.
4. **Actions** - containment (if parts may be bad), cause investigation, chart annotation.

## Scripts

```bash
python scripts/we_rules.py xbar.csv --value xbar --center 12.0092 --sigma 0.00097
python scripts/we_rules.py xbar.csv --value xbar --ucl 12.0121 --lcl 12.0063 --nelson
python scripts/we_rules.py data.csv --value x --baseline 25 --label sample
```
Exit codes: 0 no signals, 1 signals found, 2 usage or data error (fewer than 8 points, sigma <= 0).

## Additional Resources

| File | Content |
|------|---------|
| [rules-and-false-alarms.md](references/rules-and-false-alarms.md) | Zones, WE and Nelson rules, false-alarm rates, rule choice, prerequisites |
| [patterns-and-causes.md](references/patterns-and-causes.md) | Patterns with typical manufacturing causes, first checks, responding without tampering |
