---
name: as9100-gap-analyzer
description: "Run an AS9100D / EN 9100:2018 gap analysis for aviation, space and defence suppliers on the requirements added to ISO 9001: on-time delivery and conformity focus, management representative, ethics and human-factors awareness, operational planning and operational risk management, configuration management, product safety, counterfeit-part prevention, special requirements, critical items and key characteristics, external provider register and flow-down, FOD prevention, tooling and NC program control, special process validation, first article inspection (AS9102), traceability, in-service data and nonconforming product control. Generates and scores a worksheet, grades missing core controls as major, and checks invalid n/a claims. Covers AS9101/AS9104, OASIS, AS9102 FAI forms, counterfeit standards (AS5553, AS6174, AS6081), NADCAP and the planned IA9100 transition. Use when preparing for AS9100 certification, entering the aerospace supply chain, or after a prime contractor or registrar finding."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# AS9100 Gap Analyzer

AS9100D is ISO 9001 plus controls that aerospace failures taught the industry: configuration, counterfeit parts,
FOD, first articles, special processes, product safety and on-time delivery. A company that is ISO 9001 certified
usually lacks most of these. `scripts/as9100_gap.py` produces a worksheet for the AS9100-specific requirements and
grades the gaps the way registrars do.

## Trigger Conditions

Activate this skill when the user:
- Is upgrading from ISO 9001 to AS9100 / EN 9100
- Has won (or wants) work from an aerospace or defence prime
- Asks about FAI, counterfeit-part prevention, FOD or configuration management requirements
- Received an AS9100 audit or customer finding

Use [iso-9001-gap-analyzer](../iso-9001-gap-analyzer/SKILL.md) as well for the ISO 9001 base text.

## Workflow

```
1. SCOPE     -> design responsibility? post-delivery support? special processes in-house or outsourced?
2. WORKSHEET -> python scripts/as9100_gap.py --template > as9100.csv
3. ASSESS    -> status + evidence per row (core-aerospace-controls.md shows what "implemented" looks like)
4. SCORE     -> python scripts/as9100_gap.py as9100.csv
5. CLOSE     -> majors first: counterfeit prevention, FAI, configuration, FOD, special processes, provider register
6. OPERATE   -> 3 months of records, internal audit per AS9101 method, management review with OTD
```

## Gap Codes (as9100_gap.py)

| Code | Grade | Meaning |
|------|-------|---------|
| AG001 | major | Core aerospace control not met (8.1.1-8.1.4, 8.4.1, 8.5.1 FOD, 8.5.1.2, 8.5.1.3, 8.7.1) |
| AG002 | minor | Other requirement not met |
| AG003 | minor | Partially implemented |
| AG004 | check | Met without evidence, missing row or invalid status |
| AG005 | error | n/a where not allowed (only 8.3.4.1, 8.3.5, 8.5.5 when no design / post-delivery responsibility) |

```
AG005 [error] 5.3 Management representative: cannot be not applicable
AG001 [major] 8.1.4 Prevention of counterfeit parts: core aerospace control missing
```

Additions by theme with audit focus, and the related AS standards: [as9100-additions.md](references/as9100-additions.md).
What FAI, configuration management, counterfeit prevention, FOD, special processes, operational risk and OTD
look like when implemented: [core-aerospace-controls.md](references/core-aerospace-controls.md).

## Output Format

Deliver:
1. **Scope** - design responsibility, post-delivery, special processes, sites.
2. **Readiness** - % and gap counts from `as9100_gap.py`.
3. **Majors** - each with the control to build and its evidence.
4. **Plan** - owner and date per gap; customer-specific requirements of each prime added.

## Scripts

```bash
python scripts/as9100_gap.py --template > as9100.csv
python scripts/as9100_gap.py as9100.csv
```
Requirements are paraphrased; use the standard for exact wording. Exit codes: 0 no major gaps, 1 major gaps or
errors, 2 usage or read error.

## Additional Resources

| File | Content |
|------|---------|
| [as9100-additions.md](references/as9100-additions.md) | AS9100 additions by theme, certification scheme, related standards, IA9100 |
| [core-aerospace-controls.md](references/core-aerospace-controls.md) | FAI, configuration, counterfeit, FOD, special processes, operational risk, product safety, OTD |
