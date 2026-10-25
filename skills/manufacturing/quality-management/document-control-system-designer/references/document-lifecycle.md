# Document and Record Control (ISO 9001:2015 7.5)

## Documents vs records

| | Document ("maintain documented information") | Record ("retain documented information") |
|---|---|---|
| Purpose | Tells people what to do | Proves what was done |
| Changes | Revised under change control | Never changed after completion (corrections traceable) |
| Control focus | Approval, current revision at point of use, obsolete removal | Identification, storage, protection, retrieval, retention, disposal |
| Examples | Manual, procedures, work instructions, drawings, specs, blank forms | Completed inspection reports, NCRs, training records, audit reports |

A blank form is a document; once filled in it is a record.

## Document lifecycle

```
Request -> Draft (author) -> Review (user + process owner) -> Approve (independent authority)
   -> Issue (register updated, training if needed, old revision withdrawn) -> In use
   -> Periodic review (no change / revise / retire) -> Change request -> ... -> Obsolete (withdrawn, archived)
```

| Stage | Control | 7.5 reference |
|-------|---------|---------------|
| Create | ID, title, revision, owner, format | 7.5.2 a, b |
| Review and approve | Someone other than the author approves; record name and date | 7.5.2 c |
| Distribute | Only the current revision at points of use; controlled print or portal | 7.5.3.1 a, 7.5.3.2 a |
| Change | Change request, reason, what changed (highlight), re-approval, re-training | 7.5.3.2 c |
| Obsolete | Withdraw from points of use; mark retained copies OBSOLETE | 7.5.3.2 d |
| External documents | Standards, customer drawings and specs: identify, check currency, control distribution | 7.5.3.2 (last paragraph) |

## Electronic systems

A controlled portal or eQMS (SharePoint with versioning and approval flows, Q-Pulse, MasterControl, ETQ, Qualio)
replaces paper control if: only approved versions are visible to users, approvals are recorded, change history is
kept, printouts are marked "uncontrolled when printed" or carry a print date and validity, and access is
restricted. Back up and test restores (7.5.3.1 b).

## Point-of-use control

The most common audit finding is an old copy at a machine. Controls that work: QR code on the station linking
to the portal; laminated work instructions with a register of locations; supervisors check revision letters
in layered process audits; issue new revisions by swapping, not adding.

## Retention schedule (typical; check customer and legal requirements)

| Record | Typical retention | Driver |
|--------|-------------------|--------|
| Inspection and test records, CoCs | Life of product + 1 year, min. 10 years for safety parts | Customer, product liability |
| PPAP / FAI packages | Part active life + 1 year (IATF) | IATF 16949 7.5.3.2.1 |
| NCRs, CAPAs, concessions | 10 years | Liability, trends |
| Calibration records | Life of gauge + 2 years | 7.1.5 traceability |
| Training records | Employment + 6 years | Legal, competence evidence |
| Internal audit and management review | 2 certification cycles (6 years) | Certification evidence |
| Aerospace product records | Often 10+ years or per contract | AS9100 / customer |
| Medical device records | Product lifetime, at least 2 years from release | ISO 13485 / regulation |
