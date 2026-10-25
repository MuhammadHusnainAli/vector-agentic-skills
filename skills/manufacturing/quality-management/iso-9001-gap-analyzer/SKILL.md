---
name: iso-9001-gap-analyzer
description: "Run an ISO 9001:2015 gap analysis (including the 2024 climate-change amendment) against an organization's current quality system: generate a clause-by-clause worksheet of auditable requirements, record status and evidence, score readiness by clause and section, grade each gap as a likely major or minor nonconformity, flag invalid exclusions (n/a outside 7.1.5, 8.3, 8.5.3, 8.5.5), 'met' with no evidence and missing mandatory documented information, and turn the gaps into an ordered closure plan with owners and evidence of closure. Use when a company is starting ISO 9001, preparing for a stage 1 or stage 2 certification audit, inheriting an existing QMS, or asks 'how far are we from ISO 9001?' or 'what are we missing for certification?'."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# ISO 9001 Gap Analyzer

A gap analysis compares what the organization does today with each ISO 9001:2015 requirement and
answers three questions: how ready are we, which gaps would stop certification, and in what order do we
close them. `scripts/gap_template.py` prints the worksheet (45 auditable clauses, paraphrased);
`scripts/gap_score.py` scores it, grades the gaps and gives a verdict.

## Trigger Conditions

Activate this skill when the user:
- Is starting ISO 9001 and wants a baseline before writing documents
- Has a stage 1 or stage 2 certification audit coming and wants to know the risks
- Has inherited a QMS (new quality manager, acquisition) and needs a health check
- Asks "what are we missing for ISO 9001?", "are we ready for certification?", "what is mandatory?"

For explaining a single clause in depth use [iso-9001-clause-explainer](../iso-9001-clause-explainer/SKILL.md);
for the timeline to certification, [iso-9001-certification-roadmap-planner](../iso-9001-certification-roadmap-planner/SKILL.md).

## Workflow

```
1. SCOPE      -> agree sites, products/services and any clause that may not apply (only 7.1.5, 8.3, 8.5.3, 8.5.5)
2. WORKSHEET  -> python scripts/gap_template.py > gap.csv
3. ASSESS     -> walk each process; for every row set status met / partial / not-met / n/a and write the evidence seen
4. SCORE      -> python scripts/gap_score.py gap.csv
5. PRIORITISE -> majors first, then by dependency (context -> processes -> controls -> audit -> review)
6. PLAN       -> owner, action, evidence of closure and due date per gap
7. RE-SCORE   -> monthly, same worksheet, report the trend to top management
```

## Assessing Each Row

| Status | Use when | Evidence column must say |
|--------|----------|--------------------------|
| met | It is done, consistently, and you have seen proof | Document number, record date, who was interviewed |
| partial | It exists but is incomplete, inconsistent or not recorded | What exists and what is missing |
| not-met | Nothing in place | - |
| n/a | Only for 7.1.5, 8.3, 8.5.3, 8.5.5, and only if it does not affect conformity | The justification that will go in the scope (4.3) |

"Met" without evidence is an opinion. Sample on the shop floor and across shifts, not only in the quality office.
Evidence expected per clause and the most common first-assessment gaps:
[clause-evidence-guide.md](references/clause-evidence-guide.md).

## Gap Codes (gap_score.py)

| Code | Grade | Meaning |
|------|-------|---------|
| GA001 | major | Core clause not met: 4.3, 4.4, 5.2.1, 6.1, 6.2, 7.5, 8.4, 8.6, 8.7, 9.2, 9.3, 10.2 |
| GA002 | minor | Other clause not met |
| GA003 | minor | Partially implemented |
| GA004 | check | Marked met, no evidence written |
| GA005 | error | n/a on a requirement that always applies |
| GA006 | check | Clause missing or status blank / invalid |

```
Readiness: 90.2% across 41 assessed clauses  ->  NOT READY
By section:  4: 87.5%  5: 100%  6: 50%  7: 94.4%  8: 100%  9: 70%  10: 100%
GA001 [major] 9.2 Internal audit: not implemented (needs a record)
GA003 [minor] 9.3 Management review: partially implemented (needs a record): one review held; outputs not recorded
```

A high percentage with a major is still NOT READY: a single missing internal audit or management review stops
certification. Grade definitions, readiness thresholds and how to turn gaps into a plan:
[grading-and-closure.md](references/grading-and-closure.md).

## Mandatory Documented Information

ISO 9001 requires only a short list of documents (scope, process support information, policy, objectives,
operational criteria) and about twenty kinds of records. The worksheet's `documented_info` column marks them;
the full list is in [clause-evidence-guide.md](references/clause-evidence-guide.md#mandatory-documented-information).
A quality manual and most procedures are optional: recommend them only where their absence would cause errors.

## Output Format

When reporting a gap analysis, give:
1. **Scope assessed** - sites, products/services, declared non-applicable clauses with justification.
2. **Readiness** - overall %, by section, and the verdict from `gap_score.py`.
3. **Gaps** - majors first, each with clause, what is missing and why it matters.
4. **Closure plan** - table of gap, owner, action, evidence of closure, due date, ordered by dependency.
5. **Earliest credible certification date** - allowing about 3 months of records, one audit cycle and one
   management review before stage 2.

## Scripts

```bash
python scripts/gap_template.py > gap.csv          # CSV worksheet: clause, title, requirement, documented_info, status, evidence, notes
python scripts/gap_template.py --clause 8.5       # one clause family
python scripts/gap_template.py --markdown         # handout table for a workshop
```
Exit codes: 0 printed, 2 unknown clause.

```bash
python scripts/gap_score.py gap.csv
python scripts/gap_score.py gap.csv --json
```
Accepts status aliases (yes/no/partially/na). Exit codes: 0 no major gaps or errors, 1 major gaps or
errors, 2 read error or missing columns. Both scripts share the clause table in `scripts/_clauses.py`.

## Additional Resources

| File | Content |
|------|---------|
| [clause-evidence-guide.md](references/clause-evidence-guide.md) | Evidence an auditor samples per clause, common gaps, full list of mandatory documents and records |
| [grading-and-closure.md](references/grading-and-closure.md) | Major/minor/OFI definitions, readiness thresholds, dependency-ordered closure plan, interview tips |
