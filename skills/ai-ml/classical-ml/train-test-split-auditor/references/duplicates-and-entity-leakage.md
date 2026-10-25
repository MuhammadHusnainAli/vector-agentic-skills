# Duplicates and Entity Leakage

## Exact duplicates

```python
feat = [c for c in df.columns if c not in ("id", "label")]
dup_mask = df.duplicated(subset=feat, keep=False)
df["dup_group"] = df.groupby(feat, dropna=False).ngroup()      # group id for GroupShuffleSplit
```
Duplicates with conflicting labels signal label noise or missing features.

## Near-duplicates

| Data | Technique |
|------|-----------|
| Numeric rows with float noise | round to significant digits, then exact match (near_duplicates.py `--decimals`) |
| Strings with case/space variants | normalise (lower, strip, collapse spaces, unicode NFKC) |
| Edited text | character shingles + MinHash + LSH (near_duplicates.py `--text-col`); `datasketch` for large corpora |
| Semantic paraphrases | sentence embeddings + cosine similarity (approximate nearest neighbours: faiss, hnswlib) |
| Images | perceptual hashes (pHash, dHash via `imagehash`), or embedding similarity |
| Audio | fingerprints (chromaprint) |

Choosing a threshold: inspect pairs at several similarity levels (0.95, 0.9, 0.8) and set the cut where pairs
stop being "the same item".

## Turning matches into groups

Pairs -> connected components (union-find) -> one group id per component -> grouped split.
```python
parent = list(range(n))
def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]; i = parent[i]
    return i
for i, j in pairs:
    parent[find(i)] = find(j)
group = [find(i) for i in range(n)]
```

## Entity leakage

Same entity in train and test: snapshots of one customer, several images of one patient, multiple sessions of
one user, multiple listings of one property. The model learns the entity, not the pattern.
- Identify the entity key (sometimes needs entity resolution: email + phone + address).
- Split by entity (GroupShuffleSplit / GroupKFold).
- Report how many test rows belonged to entities seen in training (split_audit.py SA002).

## Measuring the impact

Evaluate the model on test rows with and without near-duplicates / seen entities. A large score drop on the
clean subset quantifies the inflation, and the clean number is the honest one.
