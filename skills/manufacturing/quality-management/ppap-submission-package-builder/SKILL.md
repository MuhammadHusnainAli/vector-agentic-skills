---
name: ppap-submission-package-builder
description: "Build and check Production Part Approval Process (AIAG PPAP 4th edition, IATF 16949 8.3.4.4) submissions: the 18 PPAP elements (design records, engineering changes, customer engineering approval, DFMEA, process flow, PFMEA, control plan, MSA, dimensional results, material and performance tests, initial process studies, lab documentation, appearance approval, samples, master sample, checking aids, CSR records, PSW), what to submit vs retain at levels 1-5, which elements are still missing, and when a PPAP is triggered by changes. Checks the Part Submission Warrant for identification, weight, results declarations, IMDS, signature and the initial process study acceptance rules (Ppk > 1.67 accepted, 1.33-1.67 customer review, < 1.33 not accepted, 100 readings in 25 subgroups, stability). Use when preparing or reviewing a PPAP package, deciding the submission level, filling in a PSW, or after a PPAP rejection."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# PPAP Submission Package Builder

A PPAP proves that production tooling, processes and people make parts that meet every requirement at the quoted
rate. Rejections usually come from missing elements for the level, a PSW signed despite a known nonconformity,
or initial process studies that do not meet the acceptance index. `scripts/ppap_package.py` lists and checks the
elements; `scripts/psw_check.py` checks the warrant and study results before anyone signs.

## Trigger Conditions

Activate this skill when the user:
- Is preparing a PPAP for a new part or a change (material, tooling, process, site, sub-supplier)
- Asks what to submit for level 2, 3 or another level
- Is filling in a PSW or reviewing initial process study results
- Had a PPAP rejected or received interim approval

Upstream deliverables: [apqp-phase-planner](../apqp-phase-planner/SKILL.md), [process-fmea-builder](../process-fmea-builder/SKILL.md),
[control-plan-writer](../control-plan-writer/SKILL.md), [gage-rr-msa-analyzer](../gage-rr-msa-analyzer/SKILL.md),
[manufacturing-cpk-capability-calculator](../manufacturing-cpk-capability-calculator/SKILL.md).

## Workflow

```
1. TRIGGER  -> confirm a PPAP is required (new part or change) and notify the customer before the change
2. LEVEL    -> level from the customer (default 3); appearance item? design responsibility?
3. ELEMENTS -> python scripts/ppap_package.py --level 3 --have have.txt [--no-appearance] [--no-design]
4. RUN      -> significant production run with production tooling, people and rate; take samples
5. STUDIES  -> MSA, dimensional results on every characteristic, Ppk on special characteristics
6. PSW      -> python scripts/psw_check.py psw.json   (no high findings before signing)
7. SUBMIT   -> package per level; track approval status (approved / interim / rejected)
```

## Submit vs Retain (level 3, the default)

All elements are submitted except master sample and checking aids (retained). Level 1 submits only the PSW
(and appearance approval report); level 2 adds design records, changes, dimensional and material results, lab
documentation and samples; level 4 is as the customer defines; level 5 is reviewed on site. Full table, element
content and PPAP triggers: [ppap-elements.md](references/ppap-elements.md).

## PSW Checks (psw_check.py)

| Code | Severity | Problem |
|------|----------|---------|
| PS001 | high | Identification incomplete |
| PS002 | high | Weight missing |
| PS003 | high | A results declaration is not "meets requirements" |
| PS004 | high / medium | Special (high) or other (medium) characteristic index < 1.33 |
| PS005 | medium | Index 1.33-1.67, or unstable process: customer approval needed |
| PS006 | medium | Fewer than 100 readings |
| PS007 | medium | Reason or level missing |
| PS008 | medium | Material reporting (IMDS) missing |
| PS009 | low | Not signed / dated |

```
PS005 [medium] Flange thickness 8.0 +/-0.1: index 1.41 between 1.33 and 1.67 - contact the customer for approval
```

PSW fields, acceptance criteria, approval statuses and dimensional results rules:
[psw-and-acceptance.md](references/psw-and-acceptance.md).

## Output Format

Deliver:
1. **Submission summary** - part, reason, level, customer.
2. **Element table** - submit / retain / n/a and status (from `ppap_package.py`).
3. **Study results** - special characteristics with index and n, and the acceptance decision.
4. **PSW check** - findings and the sign / do-not-sign recommendation.
5. **Open actions** - missing elements and items needing customer agreement, with owners.

## Scripts

```bash
python scripts/ppap_package.py --level 3
python scripts/ppap_package.py --level 3 --have have.txt --no-appearance
```
`have.txt` lists prepared elements by number, name or abbreviation (PSW, AAR, DFMEA, PFMEA, MSA). Exit codes:
0 complete or listing only, 1 elements to submit are missing, 2 read error.

```bash
python scripts/psw_check.py psw.json
```
Exit codes: 0 no high findings, 1 high findings (do not sign), 2 read or JSON error.

## Additional Resources

| File | Content |
|------|---------|
| [ppap-elements.md](references/ppap-elements.md) | The 18 elements, submit/retain table for levels 1-5, PPAP triggers |
| [psw-and-acceptance.md](references/psw-and-acceptance.md) | PSW fields, initial process study acceptance, approval statuses, dimensional results |
