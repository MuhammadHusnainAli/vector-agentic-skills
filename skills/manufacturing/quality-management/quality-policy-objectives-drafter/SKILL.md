---
name: quality-policy-objectives-drafter
description: "Draft and check an ISO 9001:2015 quality policy (5.2) and quality objectives register (6.2). Writes a 50-120 word policy in the company's own words that covers the mandatory commitments (satisfy applicable requirements, continual improvement, framework for objectives) and checks existing policies for missing commitments, generic slogans (world-class, zero defects), numeric targets and length. Builds measurable objectives cascaded to functions with baseline, target, due date, owner, resources and evaluation method, and checks a register for unmeasurable targets, missing owners, overdue or unplanned objectives, targets no better than the baseline and functions without objectives. Includes a KPI library by function. Use when writing or revising a quality policy, setting annual quality objectives or KPIs, preparing for management review, or after an audit finding on 5.2 or 6.2."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Quality Policy and Objectives Drafter

The policy states the company's intent and commitments; objectives turn it into numbers with owners and dates.
Auditors test both: is the policy specific and understood, and does every objective have a plan (what, resources,
who, when, how evaluated)? `scripts/policy_check.py` checks the policy; `scripts/objective_check.py` checks the
objectives register.

## Trigger Conditions

Activate this skill when the user:
- Needs a quality policy or wants to improve a generic one
- Is setting annual quality objectives, KPIs or targets for the QMS
- Got an audit finding on 5.2 (policy) or 6.2 (objectives)
- Is preparing management review inputs on objective performance

## Workflow

```
1. INTERVIEW  -> what customers buy, what quality failure costs, strategic direction (top management's words)
2. DRAFT      -> 50-120 words covering the mandatory commitments; no numbers
3. CHECK      -> python scripts/policy_check.py policy.txt --company "Acme Precision"
4. DERIVE     -> one or two objectives per relevant function, each linked to a policy phrase
5. PLAN       -> baseline, target with direction (< or >=), due date, owner, resources, evaluation
6. CHECK      -> python scripts/objective_check.py objectives.csv --today 2026-10-24 --functions Production Quality Sales
7. DEPLOY     -> communicate, post on boards, review monthly and at management review
```

## Quality Policy

Must be appropriate to the company, support strategy, provide a framework for objectives and commit to
**satisfying applicable requirements** and **continual improvement** (5.2.1); it must be documented,
communicated, understood and available to interested parties (5.2.2).

| Code | Severity | Check |
|------|----------|-------|
| PO001 | high | No commitment to meet applicable (customer, statutory, regulatory) requirements |
| PO002 | high | No continual-improvement commitment |
| PO003 | medium | No objectives framework |
| PO004 | medium | Generic slogans |
| PO005 | medium | Company not named / not recognisably theirs |
| PO006 | low | Numeric targets in the policy |
| PO007 | low | Under 25 or over 150 words |

Drafting method, worked examples and how auditors test understanding:
[policy-writing.md](references/policy-writing.md).

## Quality Objectives

| Code | Severity | Check (6.2) |
|------|----------|-------------|
| OB001 | high | Target has no number |
| OB002 | high | No owner |
| OB003 | medium | No / invalid / past due date |
| OB004 | medium | No baseline |
| OB005 | medium | No resources or action plan |
| OB006 | medium | No evaluation method |
| OB007 | low | No link to the policy |
| OB008 | medium | Target not better than the baseline |
| OB009 | medium | A required function has no objective |

```
[3] Cut customer complaints  (Quality)  SMART 2/7
    OB002 [high] no owner
    OB008 [medium] lower is better but target 8 is not below baseline 6
OB009 [medium] function 'Sales' has no quality objective
```

Register columns, a KPI library for each function, target-setting and cascading:
[objectives-library.md](references/objectives-library.md).

## Output Format

Deliver:
1. **Policy** - final text (50-120 words) and the `policy_check.py` result.
2. **Objectives register** - table with objective, function, metric, baseline, target, due, owner, resources,
   evaluation, policy link.
3. **Check result** - `objective_check.py` output with every finding resolved or explained.
4. **Deployment** - how the policy and objectives are communicated and reviewed (boards, induction, MR).

## Scripts

```bash
python scripts/policy_check.py policy.txt --company "Acme Precision"
echo "We are committed to quality." | python scripts/policy_check.py -
```
Exit codes: 0 no high findings, 1 high findings, 2 read error.

```bash
python scripts/objective_check.py objectives.csv
python scripts/objective_check.py objectives.csv --today 2026-10-24 --functions Production Quality Sales Purchasing
```
Direction is read from the target prefix (`<`, `>=`, below, at least) or from the metric name (scrap, ppm,
complaints, downtime are lower-is-better). Exit codes: 0 no high findings, 1 high findings, 2 read error.

## Additional Resources

| File | Content |
|------|---------|
| [policy-writing.md](references/policy-writing.md) | 5.2 requirements, drafting method, example policies, weak-policy anatomy, auditor interviews |
| [objectives-library.md](references/objectives-library.md) | 6.2 planning elements, register columns, KPI library by function, target setting, cascading, review |
