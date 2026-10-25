---
name: qms-procedure-writer
description: "Write and review ISO 9001 quality management system procedures and work instructions that people can follow and auditors can verify: purpose, scope, RACI responsibilities, definitions, numbered actor-action-timing steps, records with retention, references and revision history. Generates a procedure in Markdown from a JSON process description (with a RACI table built from the steps) and lints existing procedures for missing sections, vague wording (as needed, periodically, promptly, etc.), passive steps with no actor, should/may ambiguity, records without retention, overlong steps and missing time limits. Covers when to write a procedure vs a work instruction vs a form, and common manufacturing QMS procedures (document control, contract review, purchasing, calibration, nonconforming product, corrective action, internal audit, management review). Use when drafting an SOP or QP, tidying a procedure before an audit, or after a finding that a procedure is not followed."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# QMS Procedure Writer

A procedure is good when a new employee can follow it, every step has an owner and a time limit, and every
piece of evidence has a named record. `scripts/procedure_scaffold.py` turns a step list into a complete
procedure with a RACI table; `scripts/procedure_lint.py` finds the wording that makes procedures unauditable.

## Trigger Conditions

Activate this skill when the user:
- Needs a QMS procedure, SOP or work instruction written
- Wants an existing procedure reviewed before an audit
- Has an audit finding "procedure not followed" or "procedure does not reflect practice"
- Asks "do we need a procedure for X?" or "procedure or work instruction?"

## Workflow

```
1. DECIDE   -> procedure (cross-functional) or work instruction (one task, one station)? (procedure-anatomy.md)
2. WALK     -> walk the process with the people who do it; list who does what, when, and what is recorded
3. SPEC     -> write spec.json: id, title, owner, purpose, scope, clauses, steps (actor, action, record), records
4. DRAFT    -> python scripts/procedure_scaffold.py spec.json > QP-07.md
5. LINT     -> python scripts/procedure_lint.py QP-07.md   (fix every high and medium finding)
6. VALIDATE -> the people who do the work read it; does it match what they do?
7. RELEASE  -> approve and issue under document control; train; audit it within 3-6 months
```

## Step Format

```
3. **Quality engineer** - Decide disposition within 2 working days of the NCR. Record: QF-07 section B.
```
Role, verb, object, criterion or time limit, record. Branches become their own decision steps. Section list,
document hierarchy and a table of common manufacturing procedures with their records:
[procedure-anatomy.md](references/procedure-anatomy.md).

## Lint Codes (procedure_lint.py)

| Code | Severity | Problem | Fix |
|------|----------|---------|-----|
| PR001 | high | Missing purpose, scope, responsibilities, procedure or records section | Add the section |
| PR002 | medium | Vague wording | Replace with a frequency, quantity, role or deadline |
| PR003 | medium | Passive step with no actor | Put the role first |
| PR004 | medium | should / may / could in a step | must, or state the condition |
| PR005 | medium | Records without retention | Add retention and location |
| PR006 | low | Step over 40 words | Split |
| PR007 | low | No revision/approval block | Add header table |
| PR008 | low | No time limits anywhere | Add "within ..." / "before ..." |
| PR009 | low | More than 25 steps | Move task detail to work instructions |

```
PR003 [medium] line 7: passive step with no actor: 'Nonconforming parts are identified and segregated.'
PR002 [medium] line 9: vague 'promptly': say who, how often, how much or by when
```
Vague-to-specific and passive-to-active rewrite tables: [plain-language-rules.md](references/plain-language-rules.md).

## Output Format

Deliver:
1. **The procedure** in Markdown with header, the eight sections and a RACI table.
2. **Lint result** - `procedure_lint.py` with no high or medium findings left (or each one justified).
3. **Open questions** - anything the walk-through could not confirm (timings, retention, approvers).
4. **Related documents** - work instructions and forms the procedure references that still need writing.

## Scripts

```bash
python scripts/procedure_scaffold.py spec.json > QP-07.md
```
Spec keys: id, title, owner, purpose, scope, clauses, definitions, steps (actor, action, record, consulted,
informed), records (name, retention, location), references. Exit codes: 0 written, 1 a step lacks an actor
or action, 2 read/JSON error.

```bash
python scripts/procedure_lint.py QP-07.md
python scripts/procedure_lint.py WI-10.txt --json
```
Exit codes: 0 no high findings, 1 high findings (missing sections), 2 read error.

## Additional Resources

| File | Content |
|------|---------|
| [procedure-anatomy.md](references/procedure-anatomy.md) | Document hierarchy, procedure vs work instruction, sections, step format, common QMS procedures |
| [plain-language-rules.md](references/plain-language-rules.md) | Seven writing rules, vague -> specific and passive -> active tables, readability checks |
