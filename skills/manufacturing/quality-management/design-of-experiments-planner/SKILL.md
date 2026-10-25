---
name: design-of-experiments-planner
description: "Plan and analyse two-level designed experiments (DOE) for manufacturing process improvement: choose screening, characterisation or optimisation designs; generate full and fractional factorial designs (2^(k-p) with standard minimum-aberration generators up to 8 factors) with replicates, centre points and randomised run order; print the defining relation, resolution and alias structure; analyse results with effects for main effects and two-factor interactions, t-tests from replicates or Lenth's method for unreplicated designs, curvature tests from centre points, the coded model and recommended settings. Covers resolution III/IV/V, factor and level selection, sample size for a target effect, half-normal thinking, aliases and fold-overs, interaction interpretation and confirmation runs. Use when planning an experiment on process parameters, choosing how many runs, building a run sheet, or analysing DOE results in DMAIC Improve."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Design of Experiments Planner

One-factor-at-a-time testing misses interactions and wastes runs. A two-level factorial changes several factors
together in a planned pattern so every run informs every effect. `scripts/doe_design.py` builds the run sheet with
its alias structure; `scripts/doe_analyze.py` turns the results into effects, significance, a model and settings.

## Trigger Conditions

Activate this skill when the user:
- Wants to find which process parameters affect a response (screening)
- Needs to optimise settings (speed, feed, temperature, pressure, time) for a CTQ
- Asks how many runs are needed, or what a fractional factorial can separate
- Has DOE results to analyse in DMAIC Improve

Choosing between candidate causes first: [quality-fishbone-diagram-builder](../quality-fishbone-diagram-builder/SKILL.md);
simpler two-group comparisons: [hypothesis-test-selector](../hypothesis-test-selector/SKILL.md).

## Workflow

```
1. GOAL     -> response, goal (max/min/target), gauge capable, factors and safe levels
2. DESIGN   -> python scripts/doe_design.py --factors Speed:800:1200 Feed:0.10:0.20 Nose:0.4:0.8 Coolant:5:8 --center 3 > runs.csv
3. CHECK    -> resolution and aliases (stderr) acceptable for the question?
4. RUN      -> in the randomised order; hold everything else constant; record the response
5. ANALYSE  -> python scripts/doe_analyze.py runs.csv --response ra --goal min
6. CONFIRM  -> 3-5 confirmation runs at the recommended settings; update the control plan
```

## Example

```
Design: 2^4-1 = 8 runs x 1 replicate(s) + 0 centre point(s) = 8 runs
Defining relation: I = ABCD   Resolution IV
  AB = CD
```
```
Significance: Lenth: PSE 0.01294, margin of error 0.03894 (unreplicated)
Feed                                  0.9346        -  *
Feed*Nose                             0.3954        -  *
Coded model (significant terms): y = 1.581 + 0.06531*Speed + 0.4673*Feed - 0.3103*Nose + 0.1977*Feed*Nose
```

Designs by goal, the generator table, resolution and the planning checklist with sample size:
[design-selection.md](references/design-selection.md). Effects, Lenth vs replicates, curvature, aliases and from model
to action: [analysis-guide.md](references/analysis-guide.md).

## Output Format

Deliver:
1. **Plan** - response, goal, factors with levels, design (runs, resolution, aliases), replicates/centre points.
2. **Run sheet** - randomised CSV.
3. **Analysis** - effects ranked, significance method, coded model, curvature result.
4. **Recommendation** - settings, predicted response, confirmation-run plan, control plan update.

## Scripts

```bash
python scripts/doe_design.py --factors Speed:800:1200 Feed:0.10:0.20 Insert:A:B --replicates 2 --seed 7 > runs.csv
python scripts/doe_design.py --factors A:1:2 B:1:2 C:1:2 D:1:2 E:1:2 F:1:2 G:1:2 --max-runs 16 > runs.csv
```
Design summary on stderr, CSV on stdout. Exit codes: 0 written, 2 usage error.

```bash
python scripts/doe_analyze.py runs.csv --response ra --goal min [--alpha 0.05]
```
Exit codes: 0 analysed, 2 usage or data error.

## Additional Resources

| File | Content |
|------|---------|
| [design-selection.md](references/design-selection.md) | Designs by goal, fractional factorial generators, resolution, planning checklist, sample size |
| [analysis-guide.md](references/analysis-guide.md) | Effects, t-tests vs Lenth, curvature, aliases, confirmation runs |
