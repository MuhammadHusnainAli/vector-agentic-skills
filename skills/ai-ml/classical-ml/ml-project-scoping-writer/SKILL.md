---
name: ml-project-scoping-writer
description: "Write the scoping document (one-pager, PRD section or project charter) for a machine learning project: summary, the decision and its users, success criteria with a primary metric at the operating point, target, baseline, guardrails and online confirmation, data sources with availability at prediction time and the label definition, a phased simplest-first approach, explicit in-scope and out-of-scope lists, milestones with dates and exit criteria, risks with mitigations (leakage, labels, feedback loops, adoption, drift), team and cost, go/no-go kill criteria and open questions. Generates the Markdown from a JSON spec with visible TODOs and lints existing scope docs for missing sections and vague commitments (\"leverage AI\", \"real-time\", \"state-of-the-art\", metrics with no target). Use when someone asks to write, review or tighten an ML project proposal, scope, charter, one-pager or PRD."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# ML Project Scoping Writer

A scope document is a contract: what decision the model changes, how success is measured against today's
process, what is deliberately *not* being built, and when the team stops if the evidence is not there.
Good ML scopes are short, numeric and phased (baseline first), with kill criteria written before the work
starts. `scripts/scope_doc.py` renders the full document from a JSON spec and marks every gap as a TODO;
`scripts/scope_lint.py` reviews an existing document for missing sections and vague promises.

## Trigger Conditions

Activate this skill when the user:
- Asks to write an ML project proposal, scope, charter, one-pager, PRD section or "pitch" for leadership
- Wants an existing ML proposal reviewed, tightened or made "more concrete"
- Needs success criteria, milestones, risks or go/no-go criteria for an ML initiative
- Is turning a framing and feasibility assessment into a plan others can approve

Inputs normally come from [ml-problem-framing-advisor](../ml-problem-framing-advisor/SKILL.md) (decision,
label, unit), [ml-feasibility-assessor](../ml-feasibility-assessor/SKILL.md) (data, value, risks) and
[ml-success-metric-selector](../ml-success-metric-selector/SKILL.md) (metric, target, guardrails). After launch,
the model's documentation belongs in a model card ([model-card-writer](../model-card-writer/SKILL.md)).

## Workflow

```
1. GATHER    -> framing, feasibility verdict, metric choice, stakeholder answers
2. SPEC      -> python scripts/scope_doc.py --template > scope.json; fill it
3. RENDER    -> python scripts/scope_doc.py scope.json -o SCOPE.md   (TODOs listed on stderr)
4. TIGHTEN   -> numbers in success criteria, out-of-scope list, dated milestones with exit criteria
5. LINT      -> python scripts/scope_lint.py SCOPE.md   (also for documents written by others)
6. REVIEW    -> owner, ML lead, data owner, the team that acts on predictions; resolve open questions
7. FREEZE    -> --strict passes (no TODOs); version the doc; changes go through the owner
```

## The Sections and What "Good" Looks Like

| Section | Good | Weak |
|---------|------|------|
| Summary | "Rank active subscribers weekly by 30-day cancellation risk so retention calls the top 400." | "Use AI to reduce churn." |
| Problem | a number: "voluntary churn 2.1%/month, $1.2M/month lost" | "churn is high" |
| Decision + users | who acts, how, how often, capacity | "the business" |
| Primary metric | at the operating point, on a named split: "recall@400, latest 3-month holdout" | "accuracy", "AUC" alone |
| Target + baseline | ">= 0.45 vs 0.30 for the current rule" | "as high as possible" |
| Guardrails | complaint rate, per-segment floors, PSI | none |
| Online metric | A/B or holdout plan with duration | "monitor after launch" |
| Data | sources, owners, freshness, available at prediction time; label definition | "we have all the data" |
| Approach | phased: baseline -> model -> shadow -> test | "train a deep learning model" |
| Scope | in scope AND out of scope | only in scope |
| Milestones | date + exit criterion each | "Q1: model" |
| Risks | likelihood, impact, mitigation | "data quality" |
| Team + cost | roles, FTE, run cost | missing |
| Go/no-go | kill criteria per phase | missing |

Fully worked example (churn) and a second one (demand forecasting): [scope-examples.md](references/scope-examples.md).

## Writing Rules

1. **Lead with the decision**, not the algorithm. Algorithms belong in Approach, phrased as options.
2. **Numbers everywhere**: problem size, target, baseline, capacity, latency, dates, FTE.
3. **Simplest first**: the first milestone is always a baseline table; the model must beat the current
   process, not just a dummy.
4. **Out of scope is mandatory**. List the tempting extensions you will not do (real-time, other segments,
   personalisation, other decisions).
5. **Every milestone has an exit criterion** that someone could check without asking you.
6. **Kill criteria up front**: "if offline recall@400 is not >= 0.40 by Dec 13, stop and report".
7. **Risks are specific** to ML: leakage, label delay, selection bias, feedback loops, train/serve skew,
   adoption by the acting team, drift, fairness.
8. **One page of body text** for the core; detail goes to appendices or linked docs.
9. **Plain words**: replace "leverage", "optimise", "insights", "state-of-the-art", "real-time" with what
   they mean and a number. `scope_lint.py` flags them.

## Milestone Pattern for Most Tabular ML Projects

| # | Milestone | Typical length | Exit criterion |
|---|-----------|----------------|----------------|
| 1 | Data + label table | 1-3 weeks | label query reviewed; point-in-time features; leakage scan clean |
| 2 | Baseline table | 1 week | current rule, dummy, simple model on a deployment-like split |
| 3 | Candidate model | 2-4 weeks | beats baseline at the operating point with CI; error analysis done |
| 4 | Shadow mode | 2-4 weeks | feature availability, latency, drift within limits |
| 5 | Online test | 4-8 weeks | pre-registered analysis; go/no-go decision |
| 6 | Launch + monitoring | ongoing | dashboards, alerts, retraining cadence, model card |

Effort split and estimation heuristics: [estimation-and-milestones.md](references/estimation-and-milestones.md).

## Risk Register: ML-Specific Entries

| Risk | Typical mitigation |
|------|-------------------|
| Target leakage inflates offline results | point-in-time features; leakage scan; time-based holdout |
| Labels arrive late (chargebacks, churn windows) | proxy label for monitoring; schedule around delay |
| Feedback loop (acting changes labels) | random untreated holdout; log actions |
| Selection bias (labels only where reviewed) | random exploration sample |
| Train/serve skew | one feature definition for both; shadow mode comparison |
| Acting team does not adopt the scores | involve them in design; explanations; capacity-sized lists |
| Drift after launch | PSI/metric monitoring; retraining cadence; rollback to rules |
| Fairness / regulatory exposure | sliced metrics; legal review; reason codes |
| Data owner changes a source | data contracts; schema checks in the pipeline |

## Reviewing Someone Else's Scope

Run `scope_lint.py`, then ask, in this order:
1. Which decision changes, and who acts? (If unclear, send back to framing.)
2. What does the current process achieve on the same metric?
3. Where is the out-of-scope list?
4. What happens if milestone 3 misses its exit criterion?
5. Is every feature available at prediction time?
6. Who owns the model after launch?

Review checklist and comment templates: [review-checklist.md](references/review-checklist.md).

## Output Format

When writing a scope, deliver:
1. **The document** in Markdown, sections in the order above, generated with `scope_doc.py` or by hand.
2. **TODO list** - every unresolved item with the owner who must answer it.
3. **Lint result** - `scope_lint.py` output, with errors fixed.
4. **Open questions** for the review meeting.

When reviewing, deliver the lint findings, the six questions above answered from the document (or marked
"not answered"), and suggested rewrites for the three weakest sentences.

## Scripts

```bash
python scripts/scope_doc.py --template > scope.json          # complete example spec (churn retention)
python scripts/scope_doc.py scope.json > SCOPE.md
python scripts/scope_doc.py scope.json -o SCOPE.md --strict  # exit 1 while TODOs remain
cat scope.json | python scripts/scope_doc.py -
```
Renders summary, owner/date/status, problem and decision, users, a success-criteria table (primary metric,
target, baseline, guardrails, online metric), data sources with availability at prediction time, label and
history, known data issues, phased approach, in-scope/out-of-scope table, milestones with dates and exit
criteria, risks with likelihood/impact/mitigation, team and cost, go/no-go criteria and open questions.
Missing items appear as `TODO(owner): ...` in the document and are listed on stderr. Exit codes: 0 rendered,
1 TODOs remain with `--strict`, 2 usage error.

```bash
python scripts/scope_lint.py SCOPE.md
python scripts/scope_lint.py proposal.md --json
```
SC001-SC003 errors (missing required section, no out-of-scope list, no baseline), SC004-SC009 warnings (no
numbers in success criteria, metric without operating point or split, undated milestones, risks without
mitigations, vague language outside the Scope section, no go/no-go criteria), SC010 info (TODO/TBD count).
Exit codes: 0 no errors, 1 errors, 2 read error.

## Additional Resources

| File | Content |
|------|---------|
| [scope-examples.md](references/scope-examples.md) | Two complete scopes (churn retention, store-SKU demand forecasting) and before/after rewrites of weak sentences |
| [estimation-and-milestones.md](references/estimation-and-milestones.md) | Where ML effort goes, estimation heuristics, milestone and exit-criteria patterns, staffing |
| [review-checklist.md](references/review-checklist.md) | Reviewer checklist, red-flag phrases, comment templates, approval sign-offs |
| [spec-reference.md](references/spec-reference.md) | Every field of the JSON spec read by `scope_doc.py`, with types and examples |
