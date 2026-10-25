# scope_doc.py Spec Reference

Top-level JSON object. Every field is optional; missing ones render as `TODO(owner): ...` and are listed on
stderr (`--strict` exits 1 while any remain).

| Field | Type | Example |
|-------|------|---------|
| `title` | string | `"Churn retention targeting"` |
| `owner` | string | `"Data Science - Retention"` |
| `date` | string | `"2026-11-01"` |
| `status` | string (not checked) | `"draft"`, `"in review"`, `"approved"` |
| `summary` | string | one paragraph: decision, prediction, value |
| `problem` | string | the business problem with a number |
| `decision` | string | `"Which 400 customers the retention team calls each Monday"` |
| `users` | list of strings | `["Retention team leads"]` |
| `success.primary_metric` | string | `"recall@400 of customers cancelling within 30 days"` |
| `success.target` | string | `">= 0.45 on the latest 3-month time holdout"` |
| `success.baseline` | string | `"0.30 for the current rule on the same holdout"` |
| `success.guardrails` | list of strings | `["complaint rate <= 1.5%"]` |
| `success.online_metric` | string | `"saves per 400 calls vs a 5% holdout over 6 weeks"` |
| `data.label` | string | label definition with window and population |
| `data.history` | string | `"24 months of weekly snapshots"` |
| `data.sources` | list of `{name, owner, freshness, available_at_prediction}` | `available_at_prediction` true/false; missing -> TODO |
| `data.known_issues` | list of strings | leaks excluded, gaps |
| `approach` | list of `{phase, work}` | `[{"phase": "Baseline", "work": "rule, dummy, LR"}]` |
| `in_scope` | list of strings | |
| `out_of_scope` | list of strings | missing -> TODO (out of scope is mandatory) |
| `milestones` | list of `{name, date, exit}` | missing date or exit -> TODO |
| `risks` | list of `{risk, likelihood, impact, mitigation}` | missing mitigation -> TODO |
| `team` | list of `{role, fte}` | |
| `costs` | string | effort and run cost |
| `go_no_go` | list of strings | kill criteria |
| `open_questions` | list of strings | rendered only when present |

## Minimal spec that renders without TODOs

```json
{
  "title": "...", "owner": "...", "date": "2026-11-01",
  "summary": "...", "problem": "...", "decision": "...", "users": ["..."],
  "success": {"primary_metric": "...", "target": "...", "baseline": "...", "guardrails": ["..."],
              "online_metric": "..."},
  "data": {"label": "...", "history": "...",
           "sources": [{"name": "...", "owner": "...", "freshness": "...", "available_at_prediction": true}]},
  "approach": [{"phase": "Baseline", "work": "..."}],
  "in_scope": ["..."], "out_of_scope": ["..."],
  "milestones": [{"name": "...", "date": "...", "exit": "..."}],
  "risks": [{"risk": "...", "likelihood": "...", "impact": "...", "mitigation": "..."}],
  "team": [{"role": "...", "fte": 1.0}], "costs": "...", "go_no_go": ["..."]
}
```
