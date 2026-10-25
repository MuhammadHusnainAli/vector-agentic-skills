# Rules Engineering: Rules as Software

## Representation

Prefer data over code for rules that business users change:

```yaml
# rules/retention.yaml
- id: RET-001
  owner: retention-team
  description: High support load on new customers
  when:
    all:
      - {field: tenure_months, op: "<", value: 16}
      - {field: support_calls, op: ">=", value: 2}
  then: {action: call, priority: 1}
  created: 2026-03-01
  review_by: 2026-09-01
```

A small evaluator interprets the YAML; the rule set is versioned in git and reviewed like code.

### Decision tables
For many conditions with mutually exclusive outcomes, a decision table is easier to audit than nested ifs:

| tenure < 16 | support_calls >= 2 | last_login >= 13 | action |
|-------------|--------------------|------------------|--------|
| yes | yes | - | call |
| yes | no | yes | email |
| no | - | >= 23 | email |
| otherwise | | | none |

Check completeness (every combination covered) and exclusivity (no two rows match the same case).

## Testing rules

```python
import pytest
from rules import evaluate

@pytest.mark.parametrize("row, expected", [
    ({"tenure_months": 3, "support_calls": 4, "last_login_days": 1}, "call"),
    ({"tenure_months": 30, "support_calls": 0, "last_login_days": 2}, "none"),
    ({"tenure_months": None, "support_calls": 3, "last_login_days": 0}, "call"),   # missing tenure
])
def test_retention_rules(row, expected):
    assert evaluate(row) == expected
```
Include boundary values (exactly at the threshold) and missing values in every test table.

## Metrics for rules

Measure each rule and the whole set over a labelled period:

| Metric | Meaning |
|--------|---------|
| Hit rate | share of rows the rule fires on |
| Precision | positives among hits |
| Incremental recall | positives caught by this rule and no earlier rule |
| Overlap | share of hits also caught by other rules (redundancy) |
| Conflicts | rows where rules recommend different actions |
| Staleness | days since last edit vs review date |

Rules with near-zero incremental recall and high overlap are candidates for deletion.

## Conflict resolution

Make ordering explicit: priority numbers, or "first match wins" with the order in the file. Detect
conflicts automatically by evaluating every rule on a sample and listing rows matched by rules with different
actions.

## Extracting rules from data or models

- **Shallow trees:** `rule_learner.py` (pure Python) or `sklearn.tree.DecisionTreeClassifier(max_depth=3)` +
  `export_text`.
- **Surrogate trees:** fit a shallow tree to a complex model's predictions to approximate it with rules;
  report fidelity (agreement with the model) as well as accuracy.
- **Rule lists / RuleFit / skope-rules / imodels:** sparse rule sets with better accuracy than a single tree.
- **High-lift segments:** group by two or three key features and list segments with lift > 3 and enough rows.

```python
from sklearn.tree import DecisionTreeClassifier, export_text
tree = DecisionTreeClassifier(max_depth=3, min_samples_leaf=20, class_weight=None).fit(X_train, y_train)
print(export_text(tree, feature_names=list(X_train.columns), show_weights=True))
```

## Rule hygiene checklist

- [ ] Every rule has an ID, owner, description, creation date and review date.
- [ ] Rules live in version control; changes are reviewed.
- [ ] Each rule has tests with boundary and missing values.
- [ ] Rule metrics are reported monthly; dead rules are removed.
- [ ] Order and conflict resolution are explicit.
- [ ] Every decision logs which rule fired (for audits and future labels).
