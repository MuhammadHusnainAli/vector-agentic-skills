# Estimation and Milestones

## Where the effort goes (typical tabular ML project to first launch)

| Work | Share | Notes |
|------|-------|-------|
| Data access, label definition, point-in-time features | 35-50% | the most underestimated part |
| Baselines, modelling, validation, error analysis | 15-25% | |
| Serving integration, feature pipelines in production | 15-25% | batch is much cheaper than real-time |
| Shadow mode, online test, analysis | 10-15% | calendar time dominated by the test duration |
| Monitoring, documentation, handover | 5-10% | model card, runbook, dashboards |

## Estimation heuristics

- **Data first:** if any key source has no owner or no history, add 2-4 weeks.
- **Real-time vs batch:** real-time features and serving add 1.5-3x engineering effort.
- **New label pipelines** (surveys, human labelling) add the labelling calendar time plus quality checks.
- **Online test duration** comes from the sample-size calculation, not from the project plan: e.g. 6-8 weeks
  for weekly decisions.
- **Regulated domains:** add legal/model-risk review cycles (often 2-6 weeks each).
- Add **30% contingency**; ML projects rarely run short.

## Milestone design

Each milestone states an artefact and a checkable exit criterion:

| Milestone | Artefact | Exit criterion examples |
|-----------|----------|-------------------------|
| Data + labels | training table, label SQL, data dictionary | label reviewed by the data owner; leakage scan clean; row counts reconcile with finance |
| Baseline | baseline table | current process, dummy, simple model on a deployment-like split, with CIs |
| Candidate | model, validation report | beats baseline at the operating point; error analysis by segment; calibration if needed |
| Shadow | live scoring logs | feature availability >= 98%; latency within budget; live vs offline score PSI < 0.2 |
| Online test | test analysis | pre-registered primary metric significant at the planned power |
| Launch | dashboards, alerts, runbook, model card | on-call owner named; rollback tested |

## Staffing patterns

| Project size | Team |
|--------------|------|
| Small (batch, existing data, one decision) | 1 DS + 0.3 DE + product owner 0.1 |
| Medium (new features, batch serving, A/B test) | 1-2 DS + 1 DE + 0.5 ML engineer + PO |
| Large (real-time, many teams, regulated) | 2-3 DS + 2 DE + 1-2 MLE + analyst + PO + model-risk reviewer |

## Phase gates

Write the gate decision options explicitly: **continue**, **pivot** (change framing/scope), or **stop**.

| Gate | Continue if | Pivot if | Stop if |
|------|-------------|----------|---------|
| After baseline | simple model beats rule clearly | signal exists but metric/decision mismatch | nothing beats dummy |
| After candidate | target met with CI | target met only for some segments | gap to target > half the planned lift |
| After shadow | live matches offline | features unavailable for a segment | systemic train/serve skew |
| After test | primary metric significant | positive but below target | no effect or harm |

## Timeline example (weekly batch model)

```
Week  1-2   data access, label SQL, point-in-time features
Week  3     baseline table                              <- gate 1
Week  4-7   modelling, validation, error analysis       <- gate 2
Week  8-11  batch pipeline, shadow mode                 <- gate 3
Week 12-17  randomised test                             <- gate 4
Week 18     launch, monitoring, model card
```
