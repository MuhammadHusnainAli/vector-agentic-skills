# Document Register and Numbering

## Register (master list) columns

| Column | Why |
|--------|-----|
| doc_id | Unique, stable ID; never reused |
| title | Human-readable name |
| type | QM, QP, WI, QF, SP, DWG, EXT, REC |
| revision | Letter or number; separate from the ID |
| status | draft / approved / obsolete |
| owner | Role responsible for content |
| approved_by, approval_date | Evidence of approval (7.5.2 c) |
| last_review, review_months | Drives periodic review (typically 24 months for procedures, 12 for external standards) |
| retention | Required for record series |
| locations | Points of use for controlled copies, so withdrawal is complete |
| parent | Procedure a form or WI belongs to |

Run `register_audit.py` monthly and before every audit.

## Numbering rules

1. **Type prefix + sequence** (`QP-007`), optionally with an area code (`WI-PRD-014`) for large sites.
2. **Revision is not in the ID** (`QP-007 rev D`, not `QP-007D`): links and references stay valid across revisions.
3. **Never reuse** a retired number; retired IDs stay in the register as obsolete.
4. **Keep the ID when the title changes.** Change history explains the rename.
5. **Forms point to their parent** in the register, not through the ID (`QF-031`, parent `QP-007`): forms move
   between procedures more often than IDs can.
6. **Avoid meaning-laden numbers** (`8.7-01` tied to the ISO clause): the standard's numbering changes, yours should not.
7. Size the sequence to the expected volume: 3 digits for small companies, 4 for multi-site.

## Revision conventions

| Convention | Use |
|------------|-----|
| Letters A, B, C ... for released, numbers 0.1, 0.2 for drafts | Common in manufacturing |
| Integers 1, 2, 3 | Simple; fine for eQMS that tracks drafts separately |
| Change summary in a revision table at the end | Required in practice: auditors ask "what changed?" |

## Choosing review intervals

| Document | Review interval |
|----------|-----------------|
| Quality manual, policy | 12 months (with management review) |
| Procedures | 24 months or on process change |
| Work instructions | 24 months, or on equipment/method change |
| External standards and customer specs | 12 months currency check, or on customer notification |
| Forms | With their parent procedure |
