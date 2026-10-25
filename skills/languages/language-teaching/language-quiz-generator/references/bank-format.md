# Question Bank Format

`quiz_build.py` and `quiz_check.py` read plain-text banks. Each item is a block separated by a blank line:

```
## <topic> | <level> | <type>
Q: <stem; use ___ for the gap>
A) option
B) option *            <- the correct option is marked with *
C) option
E: <explanation shown in the answer key>
```

Types:

| Type | Lines | Example answer line |
|------|-------|---------------------|
| mcq | `A)` ... `D)` with one `*` | `B) went *` |
| gap | `ANS:` with alternatives separated by `|` | `ANS: has lived | 's lived` |
| tf | `ANS: T` or `ANS: F` | `ANS: F` |

Lines starting with `#` (a single hash) are comments. Topics are free text (use the same spelling for the same
topic); levels are CEFR levels.

## Example bank

```
## past simple | A2 | mcq
Q: Yesterday I ___ to the cinema with my sister.
A) go
B) went *
C) gone
D) going
E: "Yesterday" is finished past time, so use the past simple: went.

## past simple | A2 | gap
Q: We ___ (not / see) the film because the tickets were sold out.
ANS: didn't see | did not see
E: Past simple negative: didn't + base verb.

## present perfect | B1 | mcq
Q: I ___ in this city since 2019.
A) live
B) am living
C) have lived *
D) lived
E: "Since 2019" + a situation that continues now: present perfect.

## present perfect | B1 | tf
Q: "I've lost my keys" means the speaker probably still doesn't have them.
ANS: T
E: Present perfect links a past action to the present result.

## vocabulary: travel | A2 | mcq
Q: You show your ___ at passport control.
A) ticket
B) passport *
C) luggage
D) receipt
E: Passport control checks passports.

## collocation | B2 | mcq
Q: The company ___ a decision to close two factories.
A) did
B) made *
C) took part
D) put
E: Collocation: make a decision (take a decision is also used in British English, but is not an option here).
```

## Writing good banks

- One tested point per item; say it in the topic.
- Write several items per point and level so quizzes can be varied with `--seed`.
- Explanations teach: give the rule or the clue in the sentence.
- Run `python scripts/quiz_check.py bank.txt` after every edit.
