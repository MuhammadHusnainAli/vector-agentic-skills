# Interpreting Item Analysis

## Statistics

| Statistic | Meaning | Good range (placement / proficiency) |
|-----------|---------|--------------------------------------|
| Facility (p) | Proportion answering correctly | 0.2-0.9 overall; each level's items easiest for that level and above |
| Discrimination (D, upper-lower 27%) | Do stronger test-takers get it right more often? | 0.30+ good; 0.20-0.29 acceptable; under 0.20 revise; negative = fault |
| Distractor share | % choosing each wrong option | Each distractor chosen by at least 5% |
| Distractor direction | Weaker group chooses it more than stronger group | Always |
| KR-20 / Cronbach's alpha | Internal consistency of the whole test | 0.80+ for placement; 0.90+ for high-stakes |

Item statistics need data: under 30 test-takers treat them as indications; under 10 they are noise.

## Diagnosing problem items

| Pattern | Likely cause | Fix |
|---------|--------------|-----|
| Negative D, one distractor popular with the top group | Miskeyed, or two defensible answers | Check the key; rewrite the option |
| D near zero, facility near 0.5 | Item measures something else (trick, culture, reading load) | Rewrite or drop |
| Facility above 0.9 | Too easy for this population | Keep only if it targets A1 in a test for beginners too |
| Facility below 0.2, D low | Too hard or ambiguous | Check level and wording |
| A distractor nobody picks | Implausible option | Replace with a real learner error |
| Higher-level item easier than lower-level items | Item mis-levelled, or tests a familiar chunk | Re-tag or rewrite |

## Improving reliability

- More good items (reliability rises with length).
- Remove items with low or negative discrimination.
- Spread item difficulty to match the levels you separate.
- Clear instructions and examples; avoid speededness unless intended.

## Workflow

1. Pilot the test with 30+ learners across the levels (existing classes are ideal).
2. `python scripts/item_analysis.py responses.csv`.
3. Fix or drop IA001 and IA002 items; replace non-working distractors.
4. Re-pilot changed items or run them as unscored trial items in live tests.
5. Recalculate cut scores if items changed.
