---
name: iso-9001-quality-manual-writer
description: "Write or modernise an ISO 9001:2015 quality manual that describes the company's own QMS: scope with products, services and sites, justified requirements not applicable (only 7.1.5, 8.3, 8.5.3, 8.5.5), process map and interaction table with owners, inputs, outputs, KPIs and documents, quality policy, roles and authorities, pointers to procedures and registers, and a clause cross-reference. Generates a Markdown manual draft from a JSON company profile and reviews an existing manual for missing scope, unjustified or invalid exclusions, missing policy or process interaction, ISO 9001:2008 leftovers (management representative, preventive action, six mandatory procedures), text that parrots 'the organization shall', placeholders and the 2024 climate-change amendment. Use when a company needs a quality manual, is updating a 2008-style manual, or an auditor criticised the manual."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# ISO 9001 Quality Manual Writer

A quality manual is optional under ISO 9001:2015, but the **scope** it contains is mandatory and the
**process map** is what auditors ask for first. A good manual is short (8-15 pages), true to how the company
works, and points to the procedures and registers that hold the detail. `scripts/manual_scaffold.py` drafts
one from a company profile; `scripts/manual_check.py` reviews an existing manual.

## Trigger Conditions

Activate this skill when the user:
- Needs a quality manual for a new ISO 9001 system
- Has a 2008-era manual (management representative, preventive action, six procedures) to modernise
- Received an audit finding about scope, exclusions or process interaction
- Asks "do we need a quality manual?", "what goes in a quality manual?", "can we exclude design?"

Policy wording: [quality-policy-objectives-drafter](../quality-policy-objectives-drafter/SKILL.md);
procedures the manual points to: [qms-procedure-writer](../qms-procedure-writer/SKILL.md).

## Workflow

```
1. COLLECT   -> company, sites, products/services, design authority, outsourced processes, policy, process list
2. SCOPE     -> decide requirements not applicable and write the justification (scope-and-exclusions.md)
3. PROFILE   -> write profile.json (format in manual_scaffold.py --help)
4. DRAFT     -> python scripts/manual_scaffold.py profile.json > quality-manual.md
5. COMPLETE  -> replace every TODO with the company's register / procedure references
6. REVIEW    -> python scripts/manual_check.py quality-manual.md   (aim for no findings)
7. APPROVE   -> top management signs; the manual enters document control
```

## What the Manual Must Get Right

| Element | Requirement | Typical failure |
|---------|-------------|-----------------|
| Scope | Products/services, sites, activities (4.3) | "Manufacturing" with no product type; a site missing |
| Not applicable | Only if conformity is unaffected, with justification | Excluding 8.3 while choosing materials or tolerances; excluding 7.3 (now Awareness) |
| Process interaction | Sequence, owners, inputs, outputs, KPIs (4.4) | An org chart presented as a process map |
| Policy | Text or reference to controlled copy (5.2) | Missing commitments (see policy drafter) |
| Outsourced processes | Listed with how they are controlled (8.4) | Heat treat or plating not shown |
| Modern terms | Documented information, risk-based thinking | Management representative, preventive action procedure |

Section-by-section structure, writing rules and the 2008 -> 2015 conversion table:
[manual-structure.md](references/manual-structure.md). Valid and invalid exclusions with example
justifications: [scope-and-exclusions.md](references/scope-and-exclusions.md).

## Review Codes (manual_check.py)

| Code | Severity | Finding |
|------|----------|---------|
| QM001 | high | No scope naming products/services |
| QM002 | high | Exclusion of a clause that always applies, or without justification |
| QM003 | high | No quality policy or reference to it |
| QM004 | medium | Processes and interaction not described |
| QM005 | medium | No revision / approval block |
| QM006 | medium | ISO 9001:2008 leftovers |
| QM007 | low | Copies "the organization shall" instead of describing practice |
| QM008 | low | Placeholders left (TODO, [Company], XXX) |
| QM009 | low | Climate-change relevance not addressed (Amd 1:2024) |

```
QM002 [high] clause 7.3 declared not applicable; it cannot be excluded (7.3 was design in ISO 9001:2008; design is 8.3 now)
QM006 [medium] 'management representative' was removed in 2015; assign the responsibilities in 5.3
```

## Output Format

When writing or reviewing a manual, deliver:
1. **The manual** (Markdown) with scope, exclusions, process table, policy, section pointers and cross-reference.
2. **Open items** - every TODO the company must fill, grouped by owner.
3. **Review result** - `manual_check.py` findings and how each was resolved.
4. **Exclusion rationale** - why each not-applicable requirement is valid, and what would invalidate it.

## Scripts

```bash
python scripts/manual_scaffold.py profile.json > quality-manual.md
cat profile.json | python scripts/manual_scaffold.py -
```
Profile keys: company, sites, products, exclusions (clause + justification), policy, processes (name, type
core/support/management, owner, inputs, outputs, kpi, documents, clauses), approved_by, revision.
Exit codes: 0 written, 1 invalid exclusion (clause that cannot be excluded or justification under 5 words), 2 read/JSON error.

```bash
python scripts/manual_check.py quality-manual.md
python scripts/manual_check.py manual.txt --json
```
Exit codes: 0 no high findings, 1 high findings, 2 read error.

## Additional Resources

| File | Content |
|------|---------|
| [manual-structure.md](references/manual-structure.md) | Recommended sections, writing rules, 2008 -> 2015 conversions, process interaction |
| [scope-and-exclusions.md](references/scope-and-exclusions.md) | Strong scope statements, which requirements may be not applicable and when, justification wording |
