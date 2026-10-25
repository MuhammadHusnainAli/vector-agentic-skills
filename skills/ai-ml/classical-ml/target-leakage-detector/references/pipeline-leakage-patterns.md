# Pipeline Leakage Patterns: Before and After

## LK001 preprocessing before the split

```python
# BEFORE
X = StandardScaler().fit_transform(X)
X_train, X_test, y_train, y_test = train_test_split(X, y)

# AFTER
X_train, X_test, y_train, y_test = train_test_split(X, y, stratify=y, random_state=0)
pipe = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
pipe.fit(X_train, y_train)
```

## LK002 resampling before the split

```python
# BEFORE: synthetic neighbours of test rows are in training
X_res, y_res = SMOTE().fit_resample(X, y)
cross_val_score(model, X_res, y_res, cv=5)

# AFTER
from imblearn.pipeline import Pipeline
pipe = Pipeline([("smote", SMOTE(random_state=0)), ("model", model)])
cross_val_score(pipe, X, y, cv=StratifiedKFold(5, shuffle=True, random_state=0), scoring="average_precision")
```
Samplers in an imblearn Pipeline run only during `fit`, never on validation folds.

## LK003 feature selection before CV

```python
# BEFORE
X_sel = SelectKBest(f_classif, k=20).fit_transform(X, y)
cross_val_score(model, X_sel, y)

# AFTER
cross_val_score(make_pipeline(SelectKBest(f_classif, k=20), model), X, y)
```

## LK004 target in X

```python
# BEFORE
y = df["churned"]
X = df.drop(columns=["customer_id"])

# AFTER
TARGET = "churned"
y = df[TARGET]
X = df.drop(columns=[TARGET, "customer_id", *KNOWN_LEAKS])
assert TARGET not in X.columns
```

## LK005 fitting on test data

```python
# BEFORE
scaler.fit(X_test)              # or fit_transform(X_test)
# AFTER
X_test_t = scaler.transform(X_test)
```

## LK006 in-sample target statistics

```python
# BEFORE
df["plan_rate"] = df.groupby("plan")["churned"].transform("mean")

# AFTER (i.i.d. rows): cross-fitted encoding inside the pipeline
ColumnTransformer([("te", TargetEncoder(smooth="auto"), ["plan"])], remainder="passthrough")

# AFTER (temporal rows): expanding mean of past labels only
df = df.sort_values("ts")
g = df.groupby("plan")["churned"]
df["plan_rate_prior"] = (g.cumsum() - df["churned"]) / g.cumcount().replace(0, np.nan)
```

## LK007 shuffled splits on temporal data

```python
# BEFORE
train_test_split(X, y, test_size=0.2)                       # shuffles by default
# AFTER
df = df.sort_values("score_date")
cut = df["score_date"].quantile(0.8)
train, test = df[df.score_date <= cut], df[df.score_date > cut]
# or for CV: TimeSeriesSplit(n_splits=5, gap=label_window_in_rows)
```
When labels look ahead (30-day churn window), leave a gap of at least the label window between the last
training snapshot and the first test snapshot.

## LK008 global statistics before the split

```python
# BEFORE
df["income"] = df["income"].fillna(df["income"].median())
df["z"] = (df["x"] - df["x"].mean()) / df["x"].std()
# AFTER: SimpleImputer(strategy="median") and StandardScaler inside the Pipeline
```

## LK009 early stopping on the test set

```python
# BEFORE
model.fit(X_train, y_train, eval_set=[(X_test, y_test)])
print(score(model, X_test, y_test))          # test used twice

# AFTER
X_tr, X_val, y_tr, y_val = train_test_split(X_train, y_train, test_size=0.15, stratify=y_train, random_state=0)
model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)])
print(score(model, X_test, y_test))          # test used once
```

## LK010 CV of a bare estimator after preprocessing

```python
# BEFORE
X_prep = prep.fit_transform(X)
cross_val_score(LogisticRegression(), X_prep, y)
# AFTER
cross_val_score(make_pipeline(prep, LogisticRegression()), X, y)
```

## Hyperparameter search and the final score

```python
outer = StratifiedKFold(5, shuffle=True, random_state=1)
inner = StratifiedKFold(5, shuffle=True, random_state=2)
search = GridSearchCV(pipe, grid, cv=inner, scoring="average_precision")
nested = cross_val_score(search, X, y, cv=outer, scoring="average_precision")   # honest
```
