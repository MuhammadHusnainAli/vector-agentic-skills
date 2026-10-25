---
name: iso-9001-clause-explainer
description: "Explain any ISO 9001:2015 clause (4.1 to 10.3, including the 2024 climate-change amendment) in plain language: its intent, what it actually requires, what compliance looks like in the user's type of organization, the evidence an auditor will ask for, common nonconformities and related clauses. Looks up clauses by number or keyword, maps ISO 9001:2008 clauses to their 2015 equivalents (management representative, preventive action, quality manual), and explains core concepts: Harmonized Structure and PDCA, process approach, risk-based thinking, documented information (maintain vs retain), correction vs corrective action, verification vs validation, shall/should/may. Use when someone asks 'what does clause 8.5.1 mean?', 'what do I need for 7.1.5?', 'where did preventive action go?', is training staff on ISO 9001, or is interpreting a requirement during implementation or an audit."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# ISO 9001 Clause Explainer

Most ISO 9001 confusion comes from reading a clause without its intent. Explain each clause as: the problem it
prevents, what it requires in plain words, what it looks like in this organization, the evidence, the common
mistakes and the related clauses. `scripts/clause_lookup.py` returns that structure for any clause from the
guide in `references/clause-guide.md`.

## Trigger Conditions

Activate this skill when the user:
- Asks what a clause means or requires ("explain 6.1", "what is 8.5.6 about?")
- Needs to know what evidence satisfies a requirement
- Is converting from ISO 9001:2008 thinking (management representative, preventive action, quality manual)
- Is preparing training on ISO 9001 or interpreting a requirement with an auditor

For a full assessment against all clauses use [iso-9001-gap-analyzer](../iso-9001-gap-analyzer/SKILL.md).

## Workflow

```
1. IDENTIFY -> clause number, keyword or old 2008 clause; ask what kind of organization it is
2. LOOK UP  -> python scripts/clause_lookup.py 8.5.1   (or --search, --from-2008)
3. EXPLAIN  -> intent, requirements as checkable items, example in their context
4. EVIDENCE -> what an auditor would sample, and the typical nonconformity
5. CONNECT  -> related clauses and concepts (structure-and-concepts.md)
```

## How to Explain a Clause

| Part | Example for 7.1.5 (machine shop) |
|------|----------------------------------|
| Intent | Measurements used to accept parts are trustworthy |
| Requires | Gauges suitable and maintained; calibrated against traceable standards at intervals; status identified; protected from adjustment; impact assessed when a gauge is found out of tolerance |
| Looks like | Calibration register of every micrometer, caliper and CMM; labels with due dates; certificates from an accredited lab |
| Evidence | Register, certificates, label on the gauge in use, out-of-tolerance investigation |
| Common NC | Operator's personal caliper not in the system; no review of parts measured with a failed gauge |
| Related | 7.1.6, 8.5.1, 8.6 |

Adapt the "looks like" row to the user's sector: a software company's 7.1.5 is test tools and monitoring,
a lab's is reference materials.

## Concepts Readers Trip Over

| Question | Short answer |
|----------|--------------|
| Document or record? | "Maintain documented information" = document; "retain" = record |
| Where did preventive action go? | Risk-based thinking, 6.1 (`--from-2008 8.5.3`) |
| Do we need a management representative? | No; assign the responsibilities under 5.3 |
| Is a quality manual required? | No; scope (4.3) and needed process information (4.4) are |
| What can be excluded? | Only requirements that do not affect conformity: in practice 7.1.5, 8.3, 8.5.3, 8.5.5 |
| Correction vs corrective action? | Fixing the instance vs removing the cause |
| Are notes requirements? | No, but auditors use them to interpret intent |

Structure, PDCA, quality principles, key definitions and the current revision status:
[structure-and-concepts.md](references/structure-and-concepts.md).

## Output Format

When explaining a clause, give:
1. **Clause and title**, with the edition (ISO 9001:2015 + Amd 1:2024).
2. **Intent** in one sentence.
3. **Requirements** as a checklist in plain words.
4. **In your organization** - what it looks like for their sector and size.
5. **Evidence** and **common nonconformities**.
6. **Related clauses**.

## Scripts

```bash
python scripts/clause_lookup.py 8.7            # one clause; 8.3.4 resolves to 8.3
python scripts/clause_lookup.py 8.5            # all 8.5.x
python scripts/clause_lookup.py --search traceability
python scripts/clause_lookup.py --from-2008 7.6
python scripts/clause_lookup.py --list
```
Reads [clause-guide.md](references/clause-guide.md); edit that file to change the explanations.
Exit codes: 0 found, 1 nothing matched, 2 no clause given.

## Additional Resources

| File | Content |
|------|---------|
| [clause-guide.md](references/clause-guide.md) | Every auditable clause: intent, requirements, evidence, pitfalls, related clauses |
| [structure-and-concepts.md](references/structure-and-concepts.md) | Harmonized Structure and PDCA, seven principles, key definitions, verbal forms, related standards, revision status, how to explain a clause |
