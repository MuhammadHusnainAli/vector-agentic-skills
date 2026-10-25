---
name: document-control-system-designer
description: "Design and audit a document control system for ISO 9001:2015 clause 7.5 (and IATF 16949 / AS9100 / ISO 13485 variants): document hierarchy, document vs record, numbering scheme with separate revision, master list / document register fields, review and approval workflow, change control, point-of-use control, obsolete document withdrawal, external documents (standards, customer drawings), electronic systems (SharePoint, eQMS) and record retention schedules. Designs a numbering scheme and validates existing IDs (duplicates, revision letters in IDs, next free number), and audits a document register for duplicate or multiple approved revisions, missing approvals, obsolete copies at points of use, overdue reviews, self-approval, missing revisions, records without retention and stale external documents. Use when setting up document control, migrating to an eQMS, cleaning up a master list before an audit, or after findings about uncontrolled or obsolete documents."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Document Control System Designer

Document control has one job: the right revision is in the right place, approved by the right person, and the
evidence (records) survives as long as it is needed. `scripts/numbering_scheme.py` designs and checks document
IDs; `scripts/register_audit.py` audits the master list for the failures auditors find most.

## Trigger Conditions

Activate this skill when the user:
- Is setting up document control for a new QMS or migrating to SharePoint / an eQMS
- Needs a numbering scheme, master list, review cycle or retention schedule
- Has audit findings about obsolete documents at workstations, missing approvals or uncontrolled copies
- Asks "document or record?", "how long do we keep inspection records?", "how do we control customer drawings?"

## Workflow

```
1. HIERARCHY -> decide document types (manual, procedures, WIs, forms, specs, external, record series)
2. NUMBERING -> python scripts/numbering_scheme.py --types QM QP WI QF EXT REC [--areas PRD QA]
3. REGISTER  -> build the master list with the columns in register-and-numbering.md
4. WORKFLOW  -> draft -> review -> independent approval -> issue -> periodic review -> obsolete
5. RETENTION -> set retention per record series from customer, legal and standard requirements
6. AUDIT     -> python scripts/register_audit.py register.csv --today YYYY-MM-DD --pattern '<regex>'
7. FLOOR     -> walk the points of use; compare revisions at stations against the register
```

## Design Decisions

| Decision | Recommendation |
|----------|----------------|
| ID format | `TYPE-NNN` or `TYPE-AREA-NNN`; revision held separately |
| Approval | Someone other than the author; record name and date |
| Distribution | Portal with only approved versions visible; prints marked uncontrolled or dated |
| Point of use | Location list per document; swap on revision; QR links at stations |
| External documents | In the register (type EXT) with source and yearly currency check |
| Review cycle | 12 months for manual/external, 24 months for procedures and WIs |
| Records | Retention per series, protected from change, retrievable, disposed of on schedule |

Lifecycle, electronic-system criteria, point-of-use controls and a retention table:
[document-lifecycle.md](references/document-lifecycle.md). Register columns, numbering rules, revision
conventions and review intervals: [register-and-numbering.md](references/register-and-numbering.md).

## Register Audit Codes (register_audit.py)

| Code | Severity | Finding |
|------|----------|---------|
| DC001 | high | Same doc and revision listed twice |
| DC002 | high | Two approved revisions at once |
| DC003 | high | Approved without approver or date |
| DC004 | high | Obsolete document still at points of use |
| DC005 | medium | Periodic review overdue |
| DC006 | medium | Approved by its own owner |
| DC007 | medium | No revision |
| DC008 | medium | Record series without retention |
| DC009 | low | External document currency check overdue |
| DC010 | low | ID breaks the numbering pattern |

```
DC002 [high] QP-007: revisions C, D all approved; obsolete the old one
DC004 [high] WI-010: obsolete but still at: Lathe 3 station; withdraw or mark OBSOLETE
```

## Output Format

Deliver:
1. **Document hierarchy and types** with ID format and examples.
2. **Register template** and the review/approval workflow (who drafts, reviews, approves; intervals).
3. **Retention schedule** per record series with the requirement driving it.
4. **Audit result** of the current register and a cleanup list (high findings first).
5. **Point-of-use plan** - how revisions reach and leave the shop floor.

## Scripts

```bash
python scripts/numbering_scheme.py --types QM QP WI QF EXT --areas PRD QA
python scripts/numbering_scheme.py --types QP WI QF --check ids.txt
```
Exit codes: 0 scheme printed / all IDs valid, 1 duplicate or invalid IDs, 2 bad codes or unreadable file.

```bash
python scripts/register_audit.py register.csv --today 2026-10-24
python scripts/register_audit.py register.csv --pattern '^(QM|QP|WI|QF|REC|EXT)-\d{3}$'
```
Register columns: doc_id, title, type, revision, status, owner, approved_by, approval_date, last_review,
review_months, retention, locations. Exit codes: 0 no high findings, 1 high findings, 2 read error.

## Additional Resources

| File | Content |
|------|---------|
| [document-lifecycle.md](references/document-lifecycle.md) | Document vs record, lifecycle and 7.5 controls, electronic systems, point-of-use control, retention table |
| [register-and-numbering.md](references/register-and-numbering.md) | Register columns, numbering rules, revision conventions, review intervals |
