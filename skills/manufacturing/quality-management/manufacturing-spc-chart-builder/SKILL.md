---
name: manufacturing-spc-chart-builder
description: "Build statistical process control charts for manufacturing: choose the chart from the data (I-MR, X-bar/R, X-bar/S for measurements; p, np, c, u for defectives and defects with constant or varying sample size), compute centre lines and control limits with the standard constants, flag points beyond the limits, recompute Phase I limits after special causes are removed, report the within-subgroup sigma for capability, and render the chart as a standalone SVG with optional specification lines. Covers rational subgrouping, Phase I vs Phase II, prerequisites (MSA, sampling frequency, reaction plan), reading the chart, control vs capability and common mistakes such as spec limits used as control limits, mixed-cavity subgroups and tampering. Use when setting up SPC on a characteristic, calculating control limits, building a control chart from production data, or reviewing a chart for a control plan or PPAP."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Manufacturing SPC Chart Builder

A control chart separates common-cause variation (the process as it is) from special causes (something
changed). It only works with the right chart for the data, limits calculated from the process (never from the
specification) and a reaction plan. `scripts/control_limits.py` selects the chart and computes the limits;
`scripts/plot_chart.py` draws it as SVG. Both share the calculations in `scripts/_spc.py`.

## Trigger Conditions

Activate this skill when the user:
- Wants to start SPC on a characteristic or asks which control chart to use
- Has measurement or defect data and needs control limits or a chart
- Needs Phase I limits for a control plan, PPAP or customer requirement
- Asks why a chart shows no signals although parts are bad (often spec limits used as control limits)

Run rules beyond the limits: [western-electric-rules-checker](../western-electric-rules-checker/SKILL.md);
capability from the same data: [manufacturing-cpk-capability-calculator](../manufacturing-cpk-capability-calculator/SKILL.md).

## Workflow

```
1. MSA       -> confirm the gauge is capable (gage-rr-msa-analyzer)
2. SUBGROUP  -> rational subgroups (consecutive parts, one cavity/spindle), 20-25 subgroups
3. LIMITS    -> python scripts/control_limits.py data.csv --value diameter --subgroup hour
4. SIGNALS   -> investigate every point beyond limits; check run rules
5. PHASE I   -> after removing special causes: --exclude-ooc and freeze the limits
6. CHART     -> python scripts/plot_chart.py data.csv --value diameter --subgroup hour --usl 12.018 --lsl 12.000 > chart.svg
7. PHASE II  -> plot new subgroups against frozen limits; react per the control plan
```

## Chart Selection

| Data | Chart |
|------|-------|
| Measurements, n = 1 | I-MR |
| Measurements, n = 2-9 | X-bar / R |
| Measurements, n >= 10 | X-bar / S |
| Defectives, constant / varying n | np / p |
| Defects, constant / varying units | c / u |

```
Chart: XBAR-R  (25 subgroups, n = 5)
  X-bar                    CL 12.00921   UCL 12.01212   LCL 12.00629
    beyond limits at: 17
  Within-subgroup sigma estimate: 0.0021702
```

Selection table, formulas and the constants for n = 2-10: [chart-selection-and-constants.md](references/chart-selection-and-constants.md).
Phase I vs II, prerequisites, reading the chart, control vs capability and common mistakes:
[running-spc.md](references/running-spc.md).

## Output Format

Deliver:
1. **Chart choice** and why (data type, subgroup size, sample size behaviour).
2. **Limits** - CL, UCL, LCL for each panel, and the within sigma.
3. **Signals** - subgroups beyond limits with the investigation needed; Phase I exclusions with their causes.
4. **Chart** - SVG from `plot_chart.py`.
5. **Next steps** - run rules check, capability, sampling frequency and reaction plan for the control plan.

## Scripts

```bash
python scripts/control_limits.py bore.csv --value diameter --size 5
python scripts/control_limits.py bore.csv --value diameter --subgroup hour [--chart xbar-s] [--exclude-ooc] [--json]
python scripts/control_limits.py rejects.csv --defectives rejects --n inspected      # p or np
python scripts/control_limits.py audits.csv --defects defects --n units               # c or u
```
Exit codes: 0 no points beyond limits, 1 points beyond limits, 2 usage or data error.

```bash
python scripts/plot_chart.py bore.csv --value diameter --subgroup hour --usl 12.018 --lsl 12.000 --title "OP20 bore" > bore.svg
```
Exit codes: 0 SVG written, 2 usage or data error.

## Additional Resources

| File | Content |
|------|---------|
| [chart-selection-and-constants.md](references/chart-selection-and-constants.md) | Chart selection, rational subgroups, formulas, constants table |
| [running-spc.md](references/running-spc.md) | Phase I vs II, prerequisites, reading charts, control vs capability, mistakes |
