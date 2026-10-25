# Facilitating a 5 Why Session

## Before

- **Go to the gemba** (where it happened) with the parts, records and the people who do the work.
- Write a factual problem statement: effect, where, how many, when. No cause.
- Invite 3-6 people: operator, setter or technician, supervisor, quality, engineering. The facilitator asks, does not answer.

## Rules during the session

1. Each answer must be a **fact you can check**, not a guess. If unsure, mark it "to verify" and go and check.
2. Ask "why did that happen?" of the previous answer, not of the original problem.
3. One cause per answer. If there are two, **branch** and follow both.
4. No names. "The operator forgot" becomes "nothing in the process prevents or detects forgetting".
5. Stop when the cause is **in a process or system you control**, and fixing it would prevent recurrence.
   Five is a guide: three to seven is normal.
6. Run three legs: **occurrence** (why made), **escape** (why not detected), **systemic** (why the system allowed both).

## Therefore test

Read the chain from the bottom up, joining each line with "therefore". If any link does not follow, a step is
missing or the logic is wrong. `whys_check.py` prints this test for every leg.

## Verifying the root cause

| Method | Example |
|--------|---------|
| Switch on / off | Remove the dividers and the scratches return; put them back and they stop |
| Reproduce | Run the old insert grade past 250 parts and measure the bore growth |
| Data | Defect rate by shift, machine or lot matches the proposed cause and nothing else |
| Is / is-not | Cause explains every "is" and every "is not" |

## When 5 Why is not enough

| Situation | Use instead |
|-----------|-------------|
| Many possible causes, nobody knows where to start | Fishbone (6M) brainstorm, then 5 Why on the likely branches |
| Interactions between variables | Design of experiments |
| Intermittent defect with no obvious pattern | Data stratification, multi-vari study |
| Customer complaint needing a formal report | 8D with 5 Why inside D4 |
