# Scope and Sequence for Language Courses

**Scope** is what the course covers (outcomes, language, skills, topics). **Sequence** is the order and spacing:
when each item is introduced, revisited and assessed.

## Sequencing principles

| Principle | Meaning | Example |
|-----------|---------|---------|
| Need first | Teach what learners need soonest | Survival language before narrative tenses for new arrivals |
| Frequency | Frequent before rare | *will* before *shall*; *get* before *obtain* |
| Simple to complex | Form and concept | Past simple before past perfect; first before second conditional |
| Prerequisites | Build on known items | Present perfect vs past simple only after both are taught |
| Contrast later | Teach items separately, then contrast | *some/any* separately, then *much/many/a lot of* |
| Learnability | Developmental readiness | Questions with *do* after statements; third person *-s* is late-acquired: recycle, do not expect mastery early |
| Topic coherence | Group language around situations | Travel unit: past simple, transport lexis, asking for information |
| Spiral | Revisit each item in a wider or deeper form | Present perfect: experiences (A2) -> unfinished time (B1) -> continuous (B1+) -> perfect aspect across tenses (B2) |

## Recycling plan

Introduce, then revisit within 1-3 units, then again before assessment. Recycling is not re-teaching: use the
item in new contexts, tasks, reading texts and warmers.

| Item introduced | Recycle 1 | Recycle 2 | Assessed |
|-----------------|-----------|-----------|----------|
| Unit 3: past simple | Unit 4 (story writing) | Unit 6 (warmer, reading) | Progress test 2 |

## Scope and sequence chart

| Unit | Weeks | Topic | Can-do outcomes | Grammar | Vocabulary | Functions | Pronunciation | Skills focus | Recycles | Assessment |
|------|-------|-------|-----------------|---------|------------|-----------|---------------|--------------|----------|------------|

Read the chart vertically (does every column progress?) and horizontally (does every unit hang together?).

## Pacing

- Count real lessons: term dates minus holidays, exam days, events, likely absences (`scripts/pacing.py`).
- Keep 10-15% of lessons unallocated for review, catch-up and assessment.
- Weight units by their load rather than splitting time equally (a tense contrast unit needs more time than a
  lexical unit).
- Plan review lessons after every 2-4 units and before each test.
- Mid-term check: compare progress with the plan; cut or merge units rather than rushing.

## Multi-level and multi-year programmes

- Align level exit outcomes so that one level's exit equals the next level's entry.
- Use the same unit structure across levels so learners and teachers know what to expect.
- Hold a programme-wide item map so items are not taught as new at two levels without a reason (spiral, not
  repeat).

## Common problems

| Problem | Fix |
|---------|-----|
| Coursebook order followed blindly | Reorder or skip units to match learner needs; note it in the scope chart |
| Everything taught once | Add recycling columns and plan them into lesson materials |
| Too much in the first term | Move low-priority items to later or to self-study |
| No time for skills | Fix a minimum of skills lessons per unit (e.g. one reading/listening, one speaking, one writing) |
| Contrasts taught before both items | Use `sequence_check.py` prerequisites |
