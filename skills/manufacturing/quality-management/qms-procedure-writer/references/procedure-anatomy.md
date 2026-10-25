# Procedure Anatomy

## Which document type?

| Type | Answers | Audience | Length | Example |
|------|---------|----------|--------|---------|
| Policy / manual | Why and what the system is | Everyone, auditors | 1-15 pages | Quality manual |
| Procedure (QP) | Who does what, when, across functions | Process owners, supervisors | 2-6 pages | Control of nonconforming product |
| Work instruction (WI) | How to do one task at one station | Operators | 1-2 pages, pictures | Torque the flange bolts |
| Form / record (QF) | Evidence it was done | Whoever completes it | 1 page | NCR form |

Rule of thumb: if a step crosses departments it belongs in a procedure; if it is done by one person at one
place it belongs in a work instruction. ISO 9001:2015 mandates no procedures: write one where its absence would
cause inconsistent results (4.4.2, 7.5.1 b).

## Sections

| Section | Content | Tip |
|---------|---------|-----|
| Header | ID, title, revision, owner, approver, effective date | Controlled under document control |
| 1 Purpose | One or two sentences: the risk it controls | "Prevent nonconforming parts reaching customers" |
| 2 Scope | Where it applies and where it does not; ISO clauses | Name sites, product lines, exceptions |
| 3 Responsibilities | RACI table from the steps | One accountable owner |
| 4 Definitions | Only terms a new employee would not know | MRB, concession, quarantine |
| 5 Procedure | Numbered steps: actor - action - timing - record | 5-20 steps; flowchart for branches |
| 6 Records | Name, retention, location, owner | Ties to 7.5.3 retention |
| 7 References | Other procedures, WIs, forms, standards | Document numbers, not titles only |
| 8 Revision history | Rev, date, change, author | Say what changed, not "updated" |

## Step format

```
<n>. **<Role>** - <verb> <object> <criterion/timing>. Record: <form>.
3. **Quality engineer** - Decide disposition within 2 working days of the NCR. Record: QF-07 section B.
```

Branches: write the decision as its own step with both outcomes, or use a swim-lane flowchart with one lane per role:

```
4. **Quality engineer** - If the disposition is use-as-is or repair, request a customer concession (QF-07B)
   before release; otherwise go to step 5.
```

## Common procedures in a manufacturing QMS

| Procedure | Clauses | Key records |
|-----------|---------|-------------|
| Control of documented information | 7.5 | Document register, change requests |
| Contract review | 8.2 | Order review checklist |
| Purchasing and supplier control | 8.4 | ASL, supplier evaluations, POs |
| Production control and release | 8.5, 8.6 | Travellers, inspection reports, CoC |
| Calibration | 7.1.5 | Calibration register, certificates |
| Nonconforming product | 8.7 | NCRs, concessions |
| Corrective action | 10.2 | CAPA records |
| Internal audit | 9.2 | Programme, reports |
| Management review | 9.3 | Minutes |
| Training and competence | 7.2 | Competence matrix, training records |
