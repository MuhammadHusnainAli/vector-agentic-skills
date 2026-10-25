# Plain-Language Rules for Procedures

Auditors check that people follow the procedure as written. Every vague phrase is a place where two people do
different things, and every passive step is a place where nobody does it.

## Seven rules

1. **Actor first.** Every step names a role: "The inspector tags..." not "Parts are tagged...".
2. **One action per step.** Over 40 words means two steps.
3. **Measurable timing.** "Within 2 working days", "before the first part is run", "at every shift start".
4. **Obligation words.** Use imperative or "must"; reserve "may" for real options and say when.
5. **Name the record.** "Record the result on QF-12" makes the evidence auditable.
6. **Use the words people use on the floor.** If they say "red tag", write "red tag" (define it once).
7. **No "etc."** Lists in procedures must be complete; if they cannot be, refer to a controlled list.

## Vague -> specific

| Vague | Specific |
|-------|----------|
| as needed / as appropriate | when the gauge reading is outside the green zone |
| periodically / regularly | every 4 hours, at shift start, monthly |
| promptly / as soon as possible | within 1 hour, before the next lot starts |
| relevant personnel / concerned department | the production supervisor and the quality engineer |
| adequate / suitable training | completion of WI-10 training and 3 supervised runs signed off |
| records are kept | the inspector files QF-12 in the job folder; retained 10 years |
| should inform | must inform (or: may inform if ..., otherwise ...) |
| and/or | say which combinations are allowed |

## Passive -> active

| Passive (no actor) | Active |
|--------------------|--------|
| The first piece is approved. | The setter measures the first piece and the inspector approves it on QF-03. |
| Nonconforming parts are segregated. | The operator moves nonconforming parts to the red quarantine bin. |
| The NCR is closed. | The quality engineer closes the NCR after the disposition is complete. |

## Readability checks

- A new employee can follow it without asking anyone.
- Every step that produces evidence names the record.
- Steps match what people actually do (walk the process with the operator before approval).
- Run `procedure_lint.py` until it reports no medium findings.
