---
name: iatf-16949-requirement-checker
description: "Check an automotive supplier against IATF 16949:2016 requirements that add to ISO 9001: customer-specific requirements (CSR matrix), product safety, corporate responsibility, contingency plans, MSA and laboratory requirements, competence and auditor qualification, record retention and engineering specification review, special characteristics and product approval (PPAP), supplier selection and monitoring, control plans, set-up verification, TPM, temporary process-control changes, rework and repair, manufacturing process and product audits, problem solving, error-proofing and warranty management. Generates a worksheet with the 26 required documented processes flagged and one CSR row per customer, scores it, and grades gaps as major (missing documented process, CSRs not met, missing core controls) or minor. Covers core tools (APQP, PPAP, FMEA, SPC, MSA), IATF Rules grading and CSR management. Use when preparing for IATF 16949 certification or surveillance, a new OEM customer, or after an IATF audit finding."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# IATF 16949 Requirement Checker

IATF 16949 is ISO 9001 plus automotive requirements, the core tools and each customer's specific requirements.
Most IATF majors come from three places: a required documented process that does not exist, customer-specific
requirements that were never mapped, and core controls (MSA, control plans, process audits) applied to only some
parts. `scripts/iatf_gap.py` produces and scores a worksheet for exactly those requirements.

## Trigger Conditions

Activate this skill when the user:
- Is moving from ISO 9001 to IATF 16949, or preparing an IATF stage 1/2 or surveillance audit
- Has won a new OEM or tier-1 customer and must absorb their CSRs
- Asks which documented processes IATF requires, or what a CSR matrix is
- Received an IATF major nonconformity

Run [iso-9001-gap-analyzer](../iso-9001-gap-analyzer/SKILL.md) as well: the ISO 9001 base is audited too.

## Workflow

```
1. CUSTOMERS -> list automotive customers; collect their current CSR documents
2. WORKSHEET -> python scripts/iatf_gap.py --template --customers "Ford" "Stellantis" > iatf.csv
3. ASSESS    -> status + evidence for every row; documented processes need a written process AND records
4. SCORE     -> python scripts/iatf_gap.py iatf.csv
5. CLOSE     -> majors first: documented processes, CSR mapping, MSA / control plans / process audits
6. VERIFY    -> internal QMS, manufacturing process and product audits before the certification audit
```

## Gap Codes (iatf_gap.py)

| Code | Grade | Meaning |
|------|-------|---------|
| IG001 | major | Required documented process missing |
| IG002 | major | A customer's CSRs not assessed or not met, or no CSR rows at all |
| IG003 | minor / major | Requirement not met (major for CSR scope, MSA, control plans, process and product audits) |
| IG004 | minor | Partially implemented |
| IG005 | check | Met without evidence, missing row or invalid status |
| IG006 | error | n/a where not allowed (only 7.1.5.3, 7.2.4, 10.2.5 may be) |

```
IG001 [major] 6.1.2.3 Contingency plans: required documented process missing
IG002 [major] CSR:Stellantis: Stellantis CSRs are partial: CSRs are audited as requirements
```

Themes and audit focus per clause group, the core tools and IATF Rules grading:
[iatf-additions.md](references/iatf-additions.md). The documented-process list, how to combine them, and the
CSR collect-review-map-audit cycle: [documented-processes-and-csrs.md](references/documented-processes-and-csrs.md).

## Output Format

Deliver:
1. **Readiness** - IATF-specific % and gap counts from `iatf_gap.py`.
2. **Majors** - each with clause, what is missing and the fix (procedure to write, CSR to map, control to deploy).
3. **CSR matrix status** per customer.
4. **Plan** - owner and date per gap; internal audits planned before the external audit.

## Scripts

```bash
python scripts/iatf_gap.py --template --customers "Ford" "Stellantis" > iatf.csv
python scripts/iatf_gap.py iatf.csv
python scripts/iatf_gap.py --list-processes
```
Requirements are paraphrased; use the standard and current Sanctioned Interpretations for exact wording.
Exit codes: 0 no major gaps, 1 major gaps or errors, 2 usage or read error.

## Additional Resources

| File | Content |
|------|---------|
| [iatf-additions.md](references/iatf-additions.md) | IATF additions by theme, core tools, VDA alternatives, IATF Rules grading |
| [documented-processes-and-csrs.md](references/documented-processes-and-csrs.md) | Documented processes, combining them, CSR management cycle and typical CSR topics |
