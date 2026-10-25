# Rater Standardisation and Reliability

A rubric is only as reliable as the raters using it. Standardise before every rating session.

## Standardisation session (60-90 minutes)

1. **Read** the rubric together; clarify terms ("range", "occasional").
2. **Benchmarks**: listen to 3-4 recorded performances already rated by experienced raters (low, middle, high,
   borderline). Discuss which descriptor words justify each band.
3. **Practice**: rate 3-4 new recordings independently; compare; discuss differences of a band or more.
4. **Qualify**: each rater rates 4-6 recordings; agreement within one band on at least 90% before rating live.
5. **Record** decisions about borderline features in a rater guide.

## During rating

- Rate criteria in the same order every time; take notes on evidence (quotes, error examples).
- Rate the performance, not the person or the previous candidate (avoid contrast effects).
- Do not average criteria in your head; give each criterion its own band.
- For live interviews: one interlocutor and one assessor where possible; the assessor does not speak.

## Double rating

- Double-rate a sample (10-20%) or all performances for high stakes.
- Agreement targets: within one band 90%+; exact agreement 60%+; weighted kappa 0.70+.
- Differences of two or more bands go to a third rater; report the two closest scores or the third rater's.
- Track each rater's mean against the group (severity) and over time (drift).

`scripts/rater_agreement.py` calculates all of these from a two-column score file.

## Common rater effects

| Effect | Sign | Fix |
|--------|------|-----|
| Severity / leniency | One rater's mean consistently higher or lower | Feedback with data; benchmarks |
| Central tendency | Few top or bottom bands | Benchmarks at the extremes |
| Halo | All criteria get the same band | Rate one criterion across all candidates; notes per criterion |
| Accent bias | Lower pronunciation bands for familiar or unfamiliar accents | Focus on intelligibility; varied benchmarks |
| Drift | Ratings change during a long session | Breaks; re-check benchmarks midway |

## Converting bands to scores and levels

- Total = sum or weighted sum of criteria; report criteria too.
- Map totals to levels with cut points set on benchmark samples, not by percentage alone.
- Round consistently and state the rule (e.g. totals ending in .5 round down).
