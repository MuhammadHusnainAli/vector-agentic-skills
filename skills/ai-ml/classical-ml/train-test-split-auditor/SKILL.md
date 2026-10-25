---
name: train-test-split-auditor
description: "Audit a train/test (or train/validation, train/production) split before trusting test scores: exact duplicate rows across sets, entity leakage (the same customer, patient, device or session on both sides), time overlap in forward splits, near-duplicates (rounded numerics, case/whitespace variants, edited text copies via MinHash and LSH), feature drift (PSI, KS), single features that separate train from test (univariate adversarial AUC), target-distribution shift, unseen categories and missing-value differences; plus how to build a correct split (random, stratified, grouped, time-based, out-of-distribution) and how to run full adversarial validation. Use when someone asks whether their train/test split is valid, why the test score is too good or collapses in production, how to check for duplicates or leakage between splits, or how different the test or production data is from training."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Train-Test Split Auditor

A test score is only as honest as the split behind it. Three failures inflate it: **the same thing on both
sides** (duplicate rows, near-duplicates, the same entity), **the future in the past** (training rows later
than test rows when the model predicts forward), and **an easy test set** (test data that differs from
production). Shift is not inflation but matters just as much: a test set that looks unlike production
measures the wrong thing. `scripts/split_audit.py` runs nine checks on two CSVs; `scripts/near_duplicates.py`
finds the duplicates that exact matching misses, including edited text copies.

## Trigger Conditions

Activate this skill when the user:
- Asks "is my train/test split OK?" or "why is my test score so high?"
- Sees a model collapse in production after a great test score
- Has repeated entities, dumps from several systems, scraped or user-generated text (likely duplicates)
- Wants to compare a training set with a production sample (drift before deployment)
- Builds a holdout set and wants to be sure it is clean

CV design (folds rather than one split): [cross-validation-strategy-designer](../cross-validation-strategy-designer/SKILL.md);
feature-level leakage: [target-leakage-detector](../target-leakage-detector/SKILL.md).

## Workflow

```
1. DESCRIBE  -> how was the split made? what will production look like (new entities, later time)?
2. AUDIT     -> python scripts/split_audit.py train.csv test.csv --target y --id-col id [--time-col ts --expect forward]
3. NEAR-DUPS -> python scripts/near_duplicates.py train.csv test.csv --drop id [--text-col body]
4. FIX       -> dedupe / group split / time split; rebuild the test set
5. SHIFT     -> python scripts/split_audit.py train.csv prod_sample.csv --drop id   (is test like production?)
6. RECHECK   -> re-run both scripts; re-evaluate the model on the cleaned split
```

## Checks

| Code | Check | Why it matters | Fix |
|------|-------|----------------|-----|
| SA001 | identical feature rows in both sets | the model has memorised test rows | dedupe before splitting, or group duplicates |
| SA002 | ID / entity on both sides | entity memorisation (customer, patient) | grouped split by entity |
| SA003 | test rows not after the last training time (forward expectation) | future information in training | time-based split, with a gap for label windows |
| SA004 | feature drift (PSI > 0.25; KS) | test unlike training | investigate; maybe the split is right and the world changed |
| SA005 | one feature separates the sets (AUC > 0.7) | split encoded in a feature (time, source system) | remove/rebuild the feature or accept and document a time split |
| SA006 | target distribution shift | metrics not comparable; prior shift | stratify, or recalibrate |
| SA007 | unseen categories in test | encoders must handle unknowns | `handle_unknown`, monitor rate |
| SA008 | missing-share difference > 10 points | pipeline / source differences | fix extraction |
| SA009 | sizes, ratio, forward/backward | context | - |

On the churn fixture the audit finds the three planted problems (12 duplicated customers, 10.7% of test):
```
SA001 [high] (rows): 12 test row(s) (10.7%) have an identical feature row in train
SA002 [high] customer_id: 12 customer_id value(s) in both sets, covering 12 test rows (10.7%)
SA003 [high] signup_date: 12 test row(s) (10.7%) are not after the last training time 2024-02-02
```

## Near-Duplicates

Exact matching misses: floats re-exported with noise (`3` vs `3.0000000001`), case and whitespace changes, and
edited copies of text (tickets re-opened, reviews posted twice, product titles with a suffix). `near_duplicates.py`
rounds numerics to significant digits, normalises text, and uses MinHash with LSH banding on character shingles
to find text pairs above a Jaccard threshold. On the tickets fixture it finds all 20 planted copies (15
upper-cased bodies, 5 float-noise rows). Methods, thresholds and image/audio equivalents:
[duplicates-and-entity-leakage.md](references/duplicates-and-entity-leakage.md).

## Building a Correct Split

| Production | Split |
|------------|-------|
| i.i.d. rows | stratified random (`train_test_split(stratify=y)`) after deduplication |
| New entities | `GroupShuffleSplit` by entity |
| Next period | train on dates < cutoff, test on dates >= cutoff (+ gap for label windows) |
| New regions / segments | hold out whole segments (out-of-distribution test) |
| Several of the above | time split first, then drop test entities from training if new entities matter |

```python
from sklearn.model_selection import GroupShuffleSplit
df = df.drop_duplicates(subset=feature_cols)                          # before splitting
tr_idx, te_idx = next(GroupShuffleSplit(test_size=0.2, random_state=0).split(df, groups=df.customer_id))
```
Size guidance, holdout policy and multi-way splits: [split-design.md](references/split-design.md).

## Drift and Adversarial Validation

PSI and KS describe per-feature shift; **adversarial validation** answers the joint question: train a
classifier to tell train rows from test (or production) rows.

| Adversarial AUC | Meaning |
|-----------------|---------|
| ~0.5 | indistinguishable: the test set represents training conditions |
| 0.6-0.7 | mild shift; check the top features |
| > 0.8 | strong shift or an encoded split (time, source); investigate before trusting test scores |

Code, PSI/KS/Wasserstein details and what to do about shift: [drift-and-adversarial-validation.md](references/drift-and-adversarial-validation.md).

## Output Format

When auditing a split, deliver:
1. **Split description** - how it was made and what production looks like.
2. **Findings** - `split_audit.py` and `near_duplicates.py` output, high findings first, with the affected share.
3. **Impact** - re-evaluated test score after fixing (when possible), or the expected direction of bias.
4. **Fixes** - dedupe, grouped or time split, rebuilt holdout; code.
5. **Shift** - drift and adversarial AUC between test and production samples.
6. **Holdout policy** - how the cleaned test set will be protected and used once.

## Scripts

```bash
python scripts/split_audit.py train.csv test.csv --target churned --id-col customer_id
python scripts/split_audit.py train.csv test.csv --target churned --time-col signup_date --expect forward
python scripts/split_audit.py train.csv prod_sample.csv --drop customer_id --psi-max 0.2 --json
```
SA001-SA009: duplicate feature rows across sets, ID/group overlap, forward-time violations, PSI (train deciles
or level shares) with KS for numerics (ISO dates compared as day numbers), univariate train-vs-test AUC,
target shift (PSI or binary rate outside 3 SE), unseen levels, missing-share gaps and set sizes. Exit codes:
0 no high findings, 1 high findings, 2 usage error.

```bash
python scripts/near_duplicates.py train.csv test.csv --drop id --decimals 3
python scripts/near_duplicates.py train.csv test.csv --text-col body --threshold 0.8 --shingle 5
python scripts/near_duplicates.py data.csv --text-col title --threshold 0.9          # within one file
```
Fuzzy row keys (numerics rounded to `--decimals` significant digits, normalised text) and MinHash/LSH text
similarity (`--perms`, `--shingle`, `--threshold`); counts of affected test rows and example pairs with line
numbers. Exit codes: 0 none found, 1 near-duplicates found, 2 usage error.

## Additional Resources

| File | Content |
|------|---------|
| [split-design.md](references/split-design.md) | Random, stratified, grouped, time and OOD splits; sizes; train/validation/test roles; holdout protection |
| [duplicates-and-entity-leakage.md](references/duplicates-and-entity-leakage.md) | Exact and near-duplicate detection (hashing, MinHash, embeddings, perceptual hashes), entity resolution, building group ids |
| [drift-and-adversarial-validation.md](references/drift-and-adversarial-validation.md) | PSI, KS, chi-square, Wasserstein, JS divergence; adversarial validation code; handling covariate, prior and concept shift |
