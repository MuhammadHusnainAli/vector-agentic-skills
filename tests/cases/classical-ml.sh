# Classical ML skill script cases. Syntax: see tests/run_tests.sh.

# ---- problem framing
t 'frame_check: vague churn ask is not ready' 1 'FR002 [blocking]' \
  "$ML/ml-problem-framing-advisor/scripts/frame_check.py" "$FX/ml/framing_vague.json"
t 'frame_check: feature written after prediction time' 1 "FR007 [high] feature 'refund_issued' becomes available" \
  "$ML/ml-problem-framing-advisor/scripts/frame_check.py" "$FX/ml/framing_vague.json"
t 'frame_check: complete spec passes' 0 'READY TO PROTOTYPE' \
  "$ML/ml-problem-framing-advisor/scripts/frame_check.py" "$FX/ml/framing_good.json"
STDIN='[1,2]' t 'frame_check: non-object spec exits 2' 2 'top level must be a JSON object' \
  "$ML/ml-problem-framing-advisor/scripts/frame_check.py" -
t 'target_profile: binary churn label' 0 'binary  ->  binary classification' \
  "$ML/ml-problem-framing-advisor/scripts/target_profile.py" "$FX/ml/churn.csv" --target churned
t 'target_profile: skewed price is regression' 0 'right-skewed' \
  "$ML/ml-problem-framing-advisor/scripts/target_profile.py" "$FX/ml/house.csv" --target price
t 'target_profile: id column is not a target' 1 'looks like an ID' \
  "$ML/ml-problem-framing-advisor/scripts/target_profile.py" "$FX/ml/churn.csv" --target customer_id
t 'target_profile: ratings are ordinal' 0 'ordinal  ->' \
  "$ML/ml-problem-framing-advisor/scripts/target_profile.py" "$FX/ml/ratings.csv" --target rating

t 'feasibility_scan: churn has probable leaks' 0 'cancellation_reason: single-feature signal is-missing AUC 1.000' \
  "$ML/ml-feasibility-assessor/scripts/feasibility_scan.py" "$FX/ml/churn.csv" --target churned --time-col signup_date --drop customer_id
t 'feasibility_scan: regression signal ranking' 0 'sqft                     numeric      signal  0.714' \
  "$ML/ml-feasibility-assessor/scripts/feasibility_scan.py" "$FX/ml/house.csv" --target price --drop house_id
STDIN=$'a,y\n1,0\n2,1\n3,0\n' t 'feasibility_scan: tiny data is NO-GO' 1 'Feasibility: NO-GO' \
  "$ML/ml-feasibility-assessor/scripts/feasibility_scan.py" - --target y
t 'feasibility_scan: unknown target exits 2' 2 "target 'nope' not in columns" \
  "$ML/ml-feasibility-assessor/scripts/feasibility_scan.py" "$FX/ml/churn.csv" --target nope
t 'sample_size: auc confidence interval' 0 'SE 0.0309, 95% CI [0.739, 0.861]' \
  "$ML/ml-feasibility-assessor/scripts/sample_size.py" auc --auc 0.80 --pos 82 --neg 318
t 'sample_size: proportion metric' 0 'n = 897 evaluated cases' \
  "$ML/ml-feasibility-assessor/scripts/sample_size.py" metric --p 0.7 --margin 0.03
t 'sample_size: epv too low' 1 'Max features at 10 EPV: 8.' \
  "$ML/ml-feasibility-assessor/scripts/sample_size.py" epv --events 82 --features 25
t 'sample_size: mcnemar test size' 0 'needs about 870 rows' \
  "$ML/ml-feasibility-assessor/scripts/sample_size.py" compare --p-disagree 0.10 --diff 0.03

t 'baseline_scores: classification ladder with rule' 0 'rule             0.8500       0.7225' \
  "$ML/ml-baseline-model-builder/scripts/baseline_scores.py" "$FX/ml/churn.csv" --target churned --time-col signup_date \
  --drop customer_id refund_issued cancellation_reason --rule "support_calls >= 3 or last_login_days > 30"
t 'baseline_scores: constant score PR-AUC equals prevalence' 0 'prior            0.8300       0.5000       0.5000       0.1700' \
  "$ML/ml-baseline-model-builder/scripts/baseline_scores.py" "$FX/ml/churn.csv" --target churned --time-col signup_date --drop customer_id
t 'baseline_scores: regression baselines' 0 'median       65573.6533' \
  "$ML/ml-baseline-model-builder/scripts/baseline_scores.py" "$FX/ml/house.csv" --target price --drop house_id
t 'baseline_scores: bad rule exits 2' 2 "cannot parse rule term" \
  "$ML/ml-baseline-model-builder/scripts/baseline_scores.py" "$FX/ml/churn.csv" --target churned --rule "calls is big"
t 'scaffold_baseline: time split pipeline' 0 "df = df.sort_values('signup_date')" \
  "$ML/ml-baseline-model-builder/scripts/scaffold_baseline.py" "$FX/ml/churn.csv" --target churned --time-col signup_date
t 'scaffold_baseline: grouped split' 0 'GroupShuffleSplit(n_splits=1' \
  "$ML/ml-baseline-model-builder/scripts/scaffold_baseline.py" "$FX/ml/churn.csv" --target churned --group-col customer_id
t 'scaffold_baseline: regression uses Ridge' 0 'Ridge(alpha=1.0)' \
  "$ML/ml-baseline-model-builder/scripts/scaffold_baseline.py" "$FX/ml/house.csv" --target price

t 'pick_metric: capacity-bound rare event' 0 'PRIMARY    precision@K and recall@K at K = top 400 of 50000 (0.8%)' \
  "$ML/ml-success-metric-selector/scripts/pick_metric.py" --task binary --prevalence 0.02 --capacity 400 --population 50000 --cost-fp 8 --cost-fn 600
t 'pick_metric: accuracy flagged at low prevalence' 0 "avoid      accuracy: at 2.0% prevalence" \
  "$ML/ml-success-metric-selector/scripts/pick_metric.py" --task binary --prevalence 0.02
t 'pick_metric: forecasts near zero avoid MAPE' 0 'avoid      MAPE / sMAPE' \
  "$ML/ml-success-metric-selector/scripts/pick_metric.py" --task forecast --many-series --near-zero
t 'pick_metric: bad prevalence exits 2' 2 'between 0 and 1' \
  "$ML/ml-success-metric-selector/scripts/pick_metric.py" --task binary --prevalence 3
t 'metric_report: binary panel matches sklearn' 0 'ROC-AUC 0.9788   PR-AUC 0.8530' \
  "$ML/ml-success-metric-selector/scripts/metric_report.py" "$FX/ml/preds.csv" --k 50 --threshold 0.3
t 'metric_report: cost-optimal threshold' 0 'best threshold 0.3325' \
  "$ML/ml-success-metric-selector/scripts/metric_report.py" "$FX/ml/preds.csv" --cost-fp 8 --cost-fn 600
t 'metric_report: regression segments show bias' 0 'segment large        n=102   MAE 136.5  bias -134.2 (-14.8%)' \
  "$ML/ml-success-metric-selector/scripts/metric_report.py" "$FX/ml/reg_preds.csv" --regression --segment segment
t 'metric_report: missing column exits 2' 2 "missing column(s) ['p']" \
  "$ML/ml-success-metric-selector/scripts/metric_report.py" "$FX/ml/preds.csv" --score-col p

t 'rules_vs_ml: fraud review favours ML' 0 'Recommendation: ML' \
  "$ML/ml-vs-rules-decision-advisor/scripts/rules_vs_ml.py" "$FX/ml/rules_fraud.json"
t 'rules_vs_ml: simple reminder gated to rules' 0 'gate: simple signal and a manageable rule set' \
  "$ML/ml-vs-rules-decision-advisor/scripts/rules_vs_ml.py" "$FX/ml/rules_simple.json"
STDIN='{"data_volume": 9}' t 'rules_vs_ml: invalid answers exit 2' 2 'factors missing or not in 1..5' \
  "$ML/ml-vs-rules-decision-advisor/scripts/rules_vs_ml.py" -
t 'rule_learner: readable churn rules' 0 'FLAG IF support_calls >= 2 AND tenure_months < 16 (or missing)' \
  "$ML/ml-vs-rules-decision-advisor/scripts/rule_learner.py" "$FX/ml/churn.csv" --target churned --time-col signup_date \
  --drop customer_id zip_code refund_issued cancellation_reason --ml-auc 0.87
t 'rule_learner: null-safe SQL' 0 '(support_calls >= 2 AND (tenure_months < 16 OR tenure_months IS NULL))' \
  "$ML/ml-vs-rules-decision-advisor/scripts/rule_learner.py" "$FX/ml/churn.csv" --target churned --time-col signup_date \
  --drop customer_id zip_code refund_issued cancellation_reason
t 'rule_learner: leak shows as a perfect leaf' 0 "FLAG IF cancellation_reason != ''" \
  "$ML/ml-vs-rules-decision-advisor/scripts/rule_learner.py" "$FX/ml/churn.csv" --target churned --drop customer_id
t 'rule_learner: non-binary target exits 2' 2 'exactly 2 values' \
  "$ML/ml-vs-rules-decision-advisor/scripts/rule_learner.py" "$FX/ml/house.csv" --target price

t 'scope_doc: complete spec renders without TODOs' 0 '| Primary metric | recall@400 of customers cancelling within 30 days |' \
  "$ML/ml-project-scoping-writer/scripts/scope_doc.py" "$FX/ml/scope_spec.json" --strict
STDIN='{"title": "Demand forecast"}' t 'scope_doc: gaps become TODOs and fail --strict' 1 'TODO(owner): out-of-scope items' \
  "$ML/ml-project-scoping-writer/scripts/scope_doc.py" - --strict
t 'scope_lint: vague proposal fails' 1 "SC008 [warning] vague: 'leverage AI'" \
  "$ML/ml-project-scoping-writer/scripts/scope_lint.py" "$FX/ml/scope_vague.md"
t 'scope_lint: missing out-of-scope is an error' 1 'SC002 [error] no out-of-scope list' \
  "$ML/ml-project-scoping-writer/scripts/scope_lint.py" "$FX/ml/scope_vague.md"

t 'profile_columns: roles for churn' 0 'zip_code                 code' \
  "$ML/feature-engineering-idea-generator/scripts/profile_columns.py" "$FX/ml/churn.csv" --target churned
t 'profile_columns: entity key and epoch time' 0 'note=unix epoch (s)' \
  "$ML/feature-engineering-idea-generator/scripts/profile_columns.py" "$FX/ml/ratings.csv"
t 'suggest_features: leaks excluded' 0 'POSSIBLE LEAKS (excluded from ideas; check when they are written): refund_issued, cancellation_reason' \
  "$ML/feature-engineering-idea-generator/scripts/suggest_features.py" "$FX/ml/churn.csv" --target churned
t 'suggest_features: rate feature' 0 'rate: total_charges per unit of tenure_months' \
  "$ML/feature-engineering-idea-generator/scripts/suggest_features.py" "$FX/ml/churn.csv" --target churned
t 'suggest_features: point-in-time entity code' 0 'df["card_id_amount_mean_prior"] = g["amount"].transform(lambda s: s.shift().expanding().mean())' \
  "$ML/feature-engineering-idea-generator/scripts/suggest_features.py" "$FX/ml/transactions.csv" --target is_fraud --entity card_id --time-col timestamp --code
t 'suggest_features: unknown entity exits 2' 2 "column 'nope' not found" \
  "$ML/feature-engineering-idea-generator/scripts/suggest_features.py" "$FX/ml/churn.csv" --entity nope

t 'encoding_plan: ordered plan levels and date skip' 0 "ordered levels ['basic', 'standard', 'premium']" \
  "$ML/categorical-encoding-selector/scripts/encoding_plan.py" "$FX/ml/churn.csv" --target churned --model linear --drop customer_id
t 'encoding_plan: near-unique zip becomes prefix' 0 'zip_code                  397                          prefix' \
  "$ML/categorical-encoding-selector/scripts/encoding_plan.py" "$FX/ml/churn.csv" --target churned --model linear --drop customer_id
t 'encoding_plan: high-card target encoding with unseen note' 0 'note: 7% of recent rows have levels unseen in training' \
  "$ML/categorical-encoding-selector/scripts/encoding_plan.py" "$FX/ml/merchants.csv" --target is_fraud --model linear --time-col date
t 'encoding_plan: gbm native categoricals' 0 'native             LightGBM categorical_feature' \
  "$ML/categorical-encoding-selector/scripts/encoding_plan.py" "$FX/ml/merchants.csv" --target is_fraud --model gbm --time-col date
t 'encoding_plan: transformer code' 0 'TargetEncoder(cv=5, smooth="auto")' \
  "$ML/categorical-encoding-selector/scripts/encoding_plan.py" "$FX/ml/merchants.csv" --target is_fraud --model linear --code
t 'te_leakage_check: high-card in-sample leak flagged' 1 'merchant_id_name          471      6.4     0.858   0.723    0.755  +0.135  <- in-sample encoding leaks' \
  "$ML/categorical-encoding-selector/scripts/te_leakage_check.py" "$FX/ml/merchants.csv" --target is_fraud --time-col date
t 'te_leakage_check: low-card columns pass' 0 'region                      4    100.0' \
  "$ML/categorical-encoding-selector/scripts/te_leakage_check.py" "$FX/ml/churn.csv" --target churned --columns plan region

t 'scaling_plan: box-cox for skewed lot size' 0 'lot_size                    637  3.486e+04   2.20   4.7%   0.0%  PowerTransformer(box-cox)' \
  "$ML/feature-scaling-advisor/scripts/scaling_plan.py" "$FX/ml/house.csv" --model linear --target price --drop house_id
t 'scaling_plan: trees need no scaling' 0 'trees split on thresholds' \
  "$ML/feature-scaling-advisor/scripts/scaling_plan.py" "$FX/ml/house.csv" --model tree --target price
t 'scaling_plan: quantile transform for heavy tails in nn' 0 'QuantileTransformer(normal)' \
  "$ML/feature-scaling-advisor/scripts/scaling_plan.py" "$FX/ml/transactions.csv" --model nn --target is_fraud
t 'scaling_plan: unique step names in code' 0 '("powertransformer_box_cox"' \
  "$ML/feature-scaling-advisor/scripts/scaling_plan.py" "$FX/ml/house.csv" --model linear --target price --drop house_id --code
t 'scale_impact: raw distances dominated by one column' 0 'total_charges           99.9%' \
  "$ML/feature-scaling-advisor/scripts/scale_impact.py" "$FX/ml/churn.csv" --target churned --drop customer_id zip_code refund_issued
t 'scale_impact: regression MAE comparison' 0 'standard   55090.3247   <- best' \
  "$ML/feature-scaling-advisor/scripts/scale_impact.py" "$FX/ml/house.csv" --target price --drop house_id

t 'filter_select: leaks flagged' 0 'refund_issued            keep     0.889     0.0%  AUC 0.945  possible leak' \
  "$ML/feature-selection-analyzer/scripts/filter_select.py" "$FX/ml/churn.csv" --target churned --drop customer_id signup_date
t 'filter_select: redundant group keeps strongest' 0 'f4                       drop     0.046     0.0%  spearman +0.046  redundant with f5' \
  "$ML/feature-selection-analyzer/scripts/filter_select.py" "$FX/ml/wide.csv" --target f9 --corr 0.85
t 'filter_select: weak features marked' 0 'plan                     weak' \
  "$ML/feature-selection-analyzer/scripts/filter_select.py" "$FX/ml/churn.csv" --target churned --drop customer_id signup_date --min-signal 0.05
t 'importance_stability: correlated pair is unstable' 0 'unstable (2): total_charges, monthly_x_tenure' \
  "$ML/feature-selection-analyzer/scripts/importance_stability.py" "$FX/ml/importances_folds.csv" --top-k 5
t 'importance_stability: strict agreement gate fails' 1 'UNSTABLE' \
  "$ML/feature-selection-analyzer/scripts/importance_stability.py" "$FX/ml/importances_folds.csv" --min-agreement 0.95

t 'leakage_scan: future dates in snapshot' 1 'LD003 [high] last_login_date: 10% of values are later than score_date' \
  "$ML/target-leakage-detector/scripts/leakage_scan.py" "$FX/ml/leaky_snapshots.csv" --target churned --time-col score_date
t 'leakage_scan: sorted by outcome' 1 'LD005 [medium] (row order)' \
  "$ML/target-leakage-detector/scripts/leakage_scan.py" "$FX/ml/leaky_snapshots.csv" --target churned --time-col score_date
t 'leakage_scan: missingness leak' 1 'LD002 [high] cancellation_reason: missingness predicts the target' \
  "$ML/target-leakage-detector/scripts/leakage_scan.py" "$FX/ml/churn.csv" --target churned --drop customer_id
t 'leakage_scan: clean regression table' 0 'No leakage signals found' \
  "$ML/target-leakage-detector/scripts/leakage_scan.py" "$FX/ml/house.csv" --target price --drop house_id
t 'code_leak_lint: smote before split' 1 'LK002 [high] SMOTE.fit_resample() before the split' \
  "$ML/target-leakage-detector/scripts/code_leak_lint.py" "$FX/ml/leaky_train.py"
t 'code_leak_lint: target left in X' 1 "LK004 [high] X built from df without removing the target column 'churned'" \
  "$ML/target-leakage-detector/scripts/code_leak_lint.py" "$FX/ml/leaky_train.py"
t 'code_leak_lint: early stopping on test' 1 'LK009 [medium] early stopping on the test set' \
  "$ML/target-leakage-detector/scripts/code_leak_lint.py" "$FX/ml/leaky_train.py"
t 'code_leak_lint: clean pipeline passes' 0 'no leakage patterns found' \
  "$ML/target-leakage-detector/scripts/code_leak_lint.py" "$FX/ml/clean_train.py"
STDIN=$'def f(:\n' t 'code_leak_lint: syntax error exits 2' 2 'error' \
  "$ML/target-leakage-detector/scripts/code_leak_lint.py" -

t 'pit_features: event-level velocity excludes current event' 0 'T90005,K007,2024-03-13T00:15:00,848.67,electronics,US,1,0.91,6,180.0,5,2982.36' \
  "$ML/time-based-feature-builder/scripts/pit_features.py" --events "$FX/ml/transactions.csv" --entity card_id --time timestamp \
  --value amount --event-level --windows 1h 24h 7d --distinct merchant_category
t 'pit_features: spine with latency' 0 'K007,2024-03-13T00:10:00,3,120.0,2,1352.58,676.29,771.4,3,1362.31' \
  "$ML/time-based-feature-builder/scripts/pit_features.py" --events "$FX/ml/transactions.csv" --entity card_id --time timestamp \
  --value amount --spine "$FX/ml/spine.csv" --windows 1h 7d --latency 5m
t 'pit_features: bad window exits 2' 2 "bad window '7days'" \
  "$ML/time-based-feature-builder/scripts/pit_features.py" --events "$FX/ml/transactions.csv" --entity card_id --time timestamp --event-level --windows 7days
t 'gen_window_sql: event-level excludes current row' 0 'AND e.txn_id <> s.txn_id' \
  "$ML/time-based-feature-builder/scripts/gen_window_sql.py" --dialect duckdb --events txns --entity card_id --time ts --value amount --windows 1h 24h --event-level --id txn_id
t 'gen_window_sql: bigquery latency anchor' 0 'e.event_ts < TIMESTAMP_SUB(s.score_ts, INTERVAL 6 HOUR)' \
  "$ML/time-based-feature-builder/scripts/gen_window_sql.py" --dialect bigquery --events ev --entity customer_id --time event_ts --spine sp --cutoff score_ts --windows 7d --latency 6h
t 'gen_window_sql: event-level needs id' 2 'needs --id' \
  "$ML/time-based-feature-builder/scripts/gen_window_sql.py" --events ev --entity c --time ts --event-level

t 'lint_feature_spec: template spec is clean' 0 '2 view(s), 6 feature(s): 0 finding(s), 0 error(s)' \
  "$ML/feature-store-schema-designer/scripts/lint_feature_spec.py" "$FX/ml/feature_spec.json"
t 'lint_feature_spec: ttl shorter than cadence' 1 "FS006 [warning] view CardVelocity: ttl 6h is shorter than the source cadence 'daily'" \
  "$ML/feature-store-schema-designer/scripts/lint_feature_spec.py" "$FX/ml/feature_spec_bad.json"
t 'lint_feature_spec: missing timestamp field' 1 'FS002 [error] source txn_agg: no timestamp_field' \
  "$ML/feature-store-schema-designer/scripts/lint_feature_spec.py" "$FX/ml/feature_spec_bad.json"
t 'lint_feature_spec: label inside a feature view' 1 'FS012 [warning] CardVelocity:is_fraud' \
  "$ML/feature-store-schema-designer/scripts/lint_feature_spec.py" "$FX/ml/feature_spec_bad.json"
t 'gen_feast_repo: feature service projection' 0 'customer_profile_fv[["plan", "tenure_days"]]' \
  "$ML/feature-store-schema-designer/scripts/gen_feast_repo.py" "$FX/ml/feature_spec.json" --stdout
t 'gen_feast_repo: refuses spec with lint errors' 1 'lint error(s); fix them or pass --force' \
  "$ML/feature-store-schema-designer/scripts/gen_feast_repo.py" "$FX/ml/feature_spec_bad.json" --stdout

t 'gen_pipeline: time-ordered hgb pipeline' 0 'TimeSeriesSplit(n_splits=5, gap=0)' \
  "$ML/scikit-learn-pipeline-builder/scripts/gen_pipeline.py" "$FX/ml/churn.csv" --target churned --model hgb --time-col signup_date --drop customer_id refund_issued cancellation_reason
t 'gen_pipeline: grouped search' 0 'search.fit(X, y, groups=groups)' \
  "$ML/scikit-learn-pipeline-builder/scripts/gen_pipeline.py" "$FX/ml/churn.csv" --target churned --model linear --group-col customer_id --search random
t 'gen_pipeline: halving import order' 0 'from sklearn.experimental import enable_halving_search_cv' \
  "$ML/scikit-learn-pipeline-builder/scripts/gen_pipeline.py" "$FX/ml/house.csv" --target price --model rf --search halving
t 'gen_pipeline: text column with capped SVD' 0 'class TextSVD(BaseEstimator, TransformerMixin)' \
  "$ML/scikit-learn-pipeline-builder/scripts/gen_pipeline.py" "$FX/ml/tickets.csv" --target queue --model hgb --text-cols body
t 'gen_pipeline: unknown column exits 2' 2 "column 'nope' not found" \
  "$ML/scikit-learn-pipeline-builder/scripts/gen_pipeline.py" "$FX/ml/churn.csv" --target churned --group-col nope
t 'pipeline_lint: hard labels into roc_auc' 1 'SK001 [high] roc_auc_score() given hard labels' \
  "$ML/scikit-learn-pipeline-builder/scripts/pipeline_lint.py" "$FX/ml/sklearn_misuse.py"
t 'pipeline_lint: removed parameters' 1 'SK002 [high] squared= was removed (1.6)' \
  "$ML/scikit-learn-pipeline-builder/scripts/pipeline_lint.py" "$FX/ml/sklearn_misuse.py"
t 'pipeline_lint: nested n_jobs' 1 'SK008 [low] n_jobs=-1 on the search and its estimator' \
  "$ML/scikit-learn-pipeline-builder/scripts/pipeline_lint.py" "$FX/ml/sklearn_misuse.py"
t 'pipeline_lint: only minor findings in a clean pipeline' 0 '2 finding(s), 0 high' \
  "$ML/scikit-learn-pipeline-builder/scripts/pipeline_lint.py" "$FX/ml/clean_train.py"

t 'select_classifier: small mixed data shortlist' 0 '2. Logistic regression (L2)' \
  "$ML/classification-model-selector/scripts/select_classifier.py" --csv "$FX/ml/churn.csv" --target churned --drop customer_id refund_issued cancellation_reason
t 'select_classifier: interpretable and monotone' 0 '1. Explainable boosting machine (EBM / GAM)' \
  "$ML/classification-model-selector/scripts/select_classifier.py" --rows 20000 --features 40 --interpretable --monotone
t 'select_classifier: text data favours linear tf-idf' 0 '1. Linear model on TF-IDF (logistic / linear SVM)' \
  "$ML/classification-model-selector/scripts/select_classifier.py" --csv "$FX/ml/tickets.csv" --target queue --drop ticket_id
t 'select_classifier: needs data' 2 'give --csv/--target or --rows and --features' \
  "$ML/classification-model-selector/scripts/select_classifier.py"
t 'bakeoff_scaffold: identical folds for all models' 0 'folds = list(StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED).split(X, y, groups))' \
  "$ML/classification-model-selector/scripts/bakeoff_scaffold.py" "$FX/ml/churn.csv" --target churned --group-col customer_id
t 'bakeoff_scaffold: unknown model exits 2' 2 "unknown model(s) ['svm']" \
  "$ML/classification-model-selector/scripts/bakeoff_scaffold.py" "$FX/ml/churn.csv" --target churned --models svm

t 'target_diagnostics: skewed price -> log target' 0 'RECOMMENDED: log1p target + squared error' \
  "$ML/regression-model-trainer/scripts/target_diagnostics.py" "$FX/ml/house.csv" --target price
t 'target_diagnostics: counts -> poisson' 0 'RECOMMENDED: Poisson deviance (log link)' \
  "$ML/regression-model-trainer/scripts/target_diagnostics.py" "$FX/ml/claims.csv" --target n_claims
t 'target_diagnostics: zero-heavy amounts -> tweedie' 0 'RECOMMENDED: Tweedie deviance, power in (1, 2)' \
  "$ML/regression-model-trainer/scripts/target_diagnostics.py" "$FX/ml/claims.csv" --target claim_amount
t 'target_diagnostics: proportion -> logit' 0 'RECOMMENDED: logit-transformed proportion' \
  "$ML/regression-model-trainer/scripts/target_diagnostics.py" "$FX/ml/claims.csv" --target utilisation
t 'target_diagnostics: non-numeric target exits 2' 2 'error' \
  "$ML/regression-model-trainer/scripts/target_diagnostics.py" "$FX/ml/churn.csv" --target plan
t 'residual_report: segment bias and narrow intervals' 1 'Interval coverage 57.3% (nominal 80%), mean width 82.06  <- too narrow' \
  "$ML/regression-model-trainer/scripts/residual_report.py" "$FX/ml/reg_preds_intervals.csv" --segment segment --lower p10 --upper p90 --max-abs-bias-pct 10
t 'residual_report: top decile under-predicted' 0 'the highest decile is under-predicted (0.87)' \
  "$ML/regression-model-trainer/scripts/residual_report.py" "$FX/ml/reg_preds.csv" --segment segment

t 'gbm_param_advisor: lightgbm sized to data' 0 'min_child_samples = 400' \
  "$ML/xgboost-lightgbm-tuner/scripts/gbm_param_advisor.py" --library lightgbm --rows 200000 --features 80 --task binary --positives 4000
t 'gbm_param_advisor: xgboost small data' 0 "early_stopping_rounds = 100" \
  "$ML/xgboost-lightgbm-tuner/scripts/gbm_param_advisor.py" --library xgboost --rows 3000 --features 25 --task regression
t 'gbm_param_advisor: parameter map' 0 'min data in leaf         min_child_samples (min_data_in_leaf)' \
  "$ML/xgboost-lightgbm-tuner/scripts/gbm_param_advisor.py" --map
t 'gbm_param_advisor: needs size' 2 '--rows and --features are required' \
  "$ML/xgboost-lightgbm-tuner/scripts/gbm_param_advisor.py"
t 'parse_gbm_log: csv history overfits' 0 'best 0.2688 at iteration 225' \
  "$ML/xgboost-lightgbm-tuner/scripts/parse_gbm_log.py" "$FX/ml/history.csv"
t 'parse_gbm_log: lightgbm log learning rate too high' 0 'best at iteration 10: the learning rate is high' \
  "$ML/xgboost-lightgbm-tuner/scripts/parse_gbm_log.py" "$FX/ml/lgbm_train.log"
t 'parse_gbm_log: xgboost validation_0 treated as train' 0 'train/valid gap at best 0.05535' \
  "$ML/xgboost-lightgbm-tuner/scripts/parse_gbm_log.py" "$FX/ml/xgb_train.log"
t 'parse_gbm_log: catboost log' 0 'best 0.34 at iteration 100' \
  "$ML/xgboost-lightgbm-tuner/scripts/parse_gbm_log.py" "$FX/ml/catboost_train.log"
STDIN='hello world' t 'parse_gbm_log: unparseable input exits 2' 2 'no LightGBM / XGBoost / CatBoost / CSV training lines' \
  "$ML/xgboost-lightgbm-tuner/scripts/parse_gbm_log.py" -

t 'catboost_plan: raw categoricals and dropped date' 0 'dropped: signup_date (date: derive year/month/day-of-week/days-since features first)' \
  "$ML/catboost-model-builder/scripts/catboost_plan.py" "$FX/ml/churn.csv" --target churned --drop customer_id
t 'catboost_plan: text features detected' 0 'text_features (1): body' \
  "$ML/catboost-model-builder/scripts/catboost_plan.py" "$FX/ml/tickets.csv" --target queue --drop ticket_id
t 'catboost_plan: time-aware script' 0 'has_time=True' \
  "$ML/catboost-model-builder/scripts/catboost_plan.py" "$FX/ml/churn.csv" --target churned --time-col signup_date --code
t 'catboost_plan: tweedie loss passthrough' 0 "loss_function='Tweedie:variance_power=1.5'" \
  "$ML/catboost-model-builder/scripts/catboost_plan.py" "$FX/ml/claims.csv" --target claim_amount --loss "Tweedie:variance_power=1.5" --code
t 'catboost_params_check: bayesian with subsample' 1 'CB004 [error] Bayesian bootstrap does not support subsample' \
  "$ML/catboost-model-builder/scripts/catboost_params_check.py" "$FX/ml/catboost_bad_params.json" --task binary
t 'catboost_params_check: max_leaves ignored' 1 "CB007 [warning] max_leaves only applies with grow_policy='Lossguide'" \
  "$ML/catboost-model-builder/scripts/catboost_params_check.py" "$FX/ml/catboost_bad_params.json" --task binary
t 'catboost_params_check: good params' 0 'parameters look consistent' \
  "$ML/catboost-model-builder/scripts/catboost_params_check.py" "$FX/ml/catboost_good_params.json" --task binary --has-eval-set

t 'imbalance_report: extreme by count' 0 'severity: EXTREME' \
  "$ML/imbalanced-class-handler/scripts/imbalance_report.py" "$FX/ml/transactions.csv" --target is_fraud
t 'imbalance_report: data-derived undersampling ratio' 0 'RandomUnderSampler(sampling_strategy=0.516, random_state=0)' \
  "$ML/imbalanced-class-handler/scripts/imbalance_report.py" "$FX/ml/churn.csv" --target churned --code
STDIN=$'y\n1\n1\n1\n' t 'imbalance_report: single class exits 2' 2 'need at least two classes' \
  "$ML/imbalanced-class-handler/scripts/imbalance_report.py" - --target y
t 'threshold_tuner: policies table' 0 'top-50                0.6468     0.880   0.710  0.786     8.3%      6    18' \
  "$ML/imbalanced-class-handler/scripts/threshold_tuner.py" "$FX/ml/preds.csv" --beta 2 --min-precision 0.5 --k 50 --cost-fp 8 --cost-fn 600
t 'threshold_tuner: prior correction fixes calibration' 0 'ECE 0.3183 -> 0.0121' \
  "$ML/imbalanced-class-handler/scripts/threshold_tuner.py" "$FX/ml/preds_resampled.csv" --train-rate 0.5 --true-rate 0.03
t 'threshold_tuner: rates need each other' 2 'give both --train-rate and --true-rate' \
  "$ML/imbalanced-class-handler/scripts/threshold_tuner.py" "$FX/ml/preds.csv" --train-rate 0.5

t 'compare_models: corrected vs naive t-test' 0 'random_forest     +0.0042   8/10     0.154      0.050       0.064      0.39      0.61' \
  "$ML/ml-model-comparison-reporter/scripts/compare_models.py" "$FX/ml/cv_scores.csv" --metric roc_auc --rope 0.005
t 'compare_models: friedman across models' 0 'Friedman test across 3 models: chi2 = 16.80 (df 2), p = 0.0002' \
  "$ML/ml-model-comparison-reporter/scripts/compare_models.py" "$FX/ml/cv_scores.csv" --metric roc_auc
t 'compare_models: lower-is-better detected' 0 'log_loss (lower is better)' \
  "$ML/ml-model-comparison-reporter/scripts/compare_models.py" "$FX/ml/bakeoff_folds.csv" --metric log_loss
t 'compare_models: markdown table' 0 '| **logreg** | 0.6212 ± 0.0950 |' \
  "$ML/ml-model-comparison-reporter/scripts/compare_models.py" "$FX/ml/bakeoff_folds.csv" --metric average_precision --markdown
t 'compare_models: missing metric exits 2' 2 "column 'f1' not found" \
  "$ML/ml-model-comparison-reporter/scripts/compare_models.py" "$FX/ml/cv_scores.csv" --metric f1
t 'paired_predictions: delong matches reference' 0 'diff +0.0657 (95% CI +0.0355 .. +0.0960), z 4.26' \
  "$ML/ml-model-comparison-reporter/scripts/paired_predictions.py" "$FX/ml/preds_ab.csv" --a model_a --b model_b --n-boot 200
t 'paired_predictions: mcnemar at top-k' 0 'A right/B wrong 32, A wrong/B right 8, p 0.0002 (exact binomial)' \
  "$ML/ml-model-comparison-reporter/scripts/paired_predictions.py" "$FX/ml/preds_ab.csv" --a model_a --b model_b --k 50 --n-boot 200
t 'paired_predictions: regression mode' 0 'MAE   A 56.69' \
  "$ML/ml-model-comparison-reporter/scripts/paired_predictions.py" "$FX/ml/reg_preds.csv" --regression --a y_pred --b y_true --n-boot 200

# ---- unsupervised
t 'cluster_tendency: blobs are clustered' 0 '-> clustered' \
  "$ML/clustering-algorithm-selector/scripts/cluster_tendency.py" "$FX/ml/blobs.csv" --drop true_cluster
t 'cluster_tendency: uniform has no structure' 1 'no clear structure (close to random)' \
  "$ML/clustering-algorithm-selector/scripts/cluster_tendency.py" "$FX/ml/uniform.csv"
t 'cluster_tendency: correlated features caveat' 0 '13 column pair(s) with |r| > 0.7' \
  "$ML/clustering-algorithm-selector/scripts/cluster_tendency.py" "$FX/ml/wide.csv"
t 'select_clustering: noisy arbitrary shapes -> HDBSCAN' 0 '1. HDBSCAN' \
  "$ML/clustering-algorithm-selector/scripts/select_clustering.py" --rows 5000 --dims 3 --shapes arbitrary --noise --varying-density
t 'select_clustering: mixed data -> k-prototypes' 0 '1. k-prototypes (kmodes package)' \
  "$ML/clustering-algorithm-selector/scripts/select_clustering.py" --csv "$FX/ml/churn.csv" --drop customer_id churned
t 'select_clustering: needs data' 2 'give --csv or --rows and --dims' \
  "$ML/clustering-algorithm-selector/scripts/select_clustering.py"

t 'k_sweep: blobs recommend k=3' 0 'RECOMMENDED k = 3' \
  "$ML/kmeans-cluster-count-finder/scripts/k_sweep.py" "$FX/ml/blobs.csv" --drop true_cluster --k-max 6 --b 3
t 'k_sweep: metrics match scikit-learn' 0 '  3       188.9      0.676     559.2  0.461' \
  "$ML/kmeans-cluster-count-finder/scripts/k_sweep.py" "$FX/ml/blobs.csv" --drop true_cluster --k-max 5 --b 0
t 'k_sweep: uniform data has no clear k' 1 'NO CLEAR k: gap statistic' \
  "$ML/kmeans-cluster-count-finder/scripts/k_sweep.py" "$FX/ml/uniform.csv" --k-max 6 --b 3
t 'k_sweep: bad k range exits 2' 2 '2 <= k_min < k_max' \
  "$ML/kmeans-cluster-count-finder/scripts/k_sweep.py" "$FX/ml/blobs.csv" --k-min 5 --k-max 3
t 'cluster_profile: distinguishing feature' 0 'support_calls          mean 4.756 vs 0.707 elsewhere  (d +3.85, higher)' \
  "$ML/kmeans-cluster-count-finder/scripts/cluster_profile.py" "$FX/ml/segments.csv" --label cluster --outcome churned --drop customer_id
t 'cluster_profile: category lift' 0 'plan=premium          97% vs 32% overall (lift 3.0x)' \
  "$ML/kmeans-cluster-count-finder/scripts/cluster_profile.py" "$FX/ml/segments.csv" --label cluster --drop customer_id

t 'kdist: knee near planted noise share' 0 'knee at rank 277/300: eps ~ 0.5133 (points beyond it: 7.3% -> likely noise)' \
  "$ML/dbscan-parameter-tuner/scripts/kdist.py" "$FX/ml/blobs.csv" --drop true_cluster
t 'kdist: min_samples too large exits 2' 2 'min_samples must be smaller' \
  "$ML/dbscan-parameter-tuner/scripts/kdist.py" "$FX/ml/blobs.csv" --drop true_cluster --min-samples 500
t 'dbscan_grid: stable recommendation with ARI' 0 'RECOMMENDED: DBSCAN(eps=0.4, min_samples=6) -> 3 clusters, 5.7% noise' \
  "$ML/dbscan-parameter-tuner/scripts/dbscan_grid.py" "$FX/ml/blobs.csv" --labels true_cluster --eps 0.3 0.4 0.5 0.6 0.8 1.0 --min-samples 4 6 10
t 'dbscan_grid: uniform data has no stable setting' 1 'No stable setting' \
  "$ML/dbscan-parameter-tuner/scripts/dbscan_grid.py" "$FX/ml/uniform.csv"

t 'pca_report: matches sklearn variance ratios' 0 'explained: PC1 46.0%  PC2 27.8%  PC3 10.2%  PC4 9.6%' \
  "$ML/pca-dimensionality-reducer/scripts/pca_report.py" "$FX/ml/wide.csv"
t 'pca_report: parallel analysis finds two factors' 0 'parallel analysis (20 shuffles, q0.95): 2' \
  "$ML/pca-dimensionality-reducer/scripts/pca_report.py" "$FX/ml/wide.csv"
t 'pca_report: unscaled dominance warning' 0 'WARNING: unscaled - revenue_usd holds 100% of the total variance' \
  "$ML/pca-dimensionality-reducer/scripts/pca_report.py" "$FX/ml/wide.csv" --no-scale
t 'pca_report: needs two columns' 2 'need >= 2 numeric columns' \
  "$ML/pca-dimensionality-reducer/scripts/pca_report.py" "$FX/ml/wide.csv" --columns f1
t 'pca_outliers: T2 and Q flags vs labels' 0 'against is_anomaly: precision 0.83, recall 0.83' \
  "$ML/pca-dimensionality-reducer/scripts/pca_outliers.py" --train "$FX/ml/sensors.csv" --drop reading_id --label is_anomaly --k 2
t 'pca_outliers: Q contributors listed' 0 'top Q contributors: temperature +4.04' \
  "$ML/pca-dimensionality-reducer/scripts/pca_outliers.py" --train "$FX/ml/sensors.csv" --drop reading_id is_anomaly --k 2

t 'embedding_trust: matches sklearn trustworthiness' 0 'trustworthiness  0.884' \
  "$ML/umap-tsne-embedding-visualizer/scripts/embedding_trust.py" --high "$FX/ml/emb_high.csv" --low "$FX/ml/emb_2d.csv" --label label
t 'embedding_trust: label accuracy comparison' 0 '10-NN label accuracy: original 1.000, embedding 1.000' \
  "$ML/umap-tsne-embedding-visualizer/scripts/embedding_trust.py" --high "$FX/ml/emb_high.csv" --low "$FX/ml/emb_2d.csv" --label label
t 'embedding_trust: row mismatch exits 2' 2 'row counts differ' \
  "$ML/umap-tsne-embedding-visualizer/scripts/embedding_trust.py" --high "$FX/ml/emb_high.csv" --low "$FX/ml/blobs.csv"
t 'gen_embedding_plot: grid script' 0 "GRID = {'tsne': [5, 15, 45], 'umap': [5, 15, 45]}" \
  "$ML/umap-tsne-embedding-visualizer/scripts/gen_embedding_plot.py" "$FX/ml/churn.csv" --drop customer_id churned zip_code --label plan --grid --perplexity 15
t 'gen_embedding_plot: cosine normalisation' 0 'METRIC = '"'"'cosine'"'" \
  "$ML/umap-tsne-embedding-visualizer/scripts/gen_embedding_plot.py" "$FX/ml/emb_high.csv" --label label --metric cosine

t 'anomaly_scores: planted anomalies on top' 0 '   262    0.998     8.86   11.21   8.383   0.766  vibration +8.9' \
  "$ML/anomaly-detection-model-builder/scripts/anomaly_scores.py" --train "$FX/ml/sensors.csv" --drop reading_id is_anomaly --top 8
t 'anomaly_scores: contextual anomaly via mahalanobis' 0 '   202    0.970     2.29    3.46' \
  "$ML/anomaly-detection-model-builder/scripts/anomaly_scores.py" --train "$FX/ml/sensors.csv" --drop reading_id is_anomaly --top 8
t 'anomaly_scores: too few rows exits 2' 2 'need >= 20 complete numeric training rows' \
  "$ML/anomaly-detection-model-builder/scripts/anomaly_scores.py" --train "$FX/ml/importances.csv"
t 'anomaly_eval: labelled evaluation' 0 'score_iforest           0.999   0.976   1.00   0.83   0.60   1.00' \
  "$ML/anomaly-detection-model-builder/scripts/anomaly_eval.py" "$FX/ml/sensor_scores.csv" --scores score_robust_z score_iforest --label is_anomaly --k 5 10
t 'anomaly_eval: unlabelled agreement' 0 'agreement score_robust_z vs score_mahalanobis: Spearman 0.96' \
  "$ML/anomaly-detection-model-builder/scripts/anomaly_eval.py" "$FX/ml/sensor_scores.csv" --scores score_robust_z score_mahalanobis --k 10

# ---- model validation
t 'cv_advisor: repeated cards -> stratified group' 0 'RECOMMENDED: StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=0)' \
  "$ML/cross-validation-strategy-designer/scripts/cv_advisor.py" "$FX/ml/transactions.csv" --target is_fraud
t 'cv_advisor: forward with missing gap warning' 0 'need gap >= window' \
  "$ML/cross-validation-strategy-designer/scripts/cv_advisor.py" "$FX/ml/transactions.csv" --target is_fraud --time-col timestamp
t 'cv_advisor: small iid regression -> repeated kfold' 0 'RepeatedKFold(n_splits=5, n_repeats=5, random_state=0)' \
  "$ML/cross-validation-strategy-designer/scripts/cv_advisor.py" "$FX/ml/house.csv" --target price
t 'fold_preview: random folds leak entities' 1 'card_id value(s) shared between train and test' \
  "$ML/cross-validation-strategy-designer/scripts/fold_preview.py" "$FX/ml/transactions.csv" --target is_fraud --strategy stratified --group-col card_id
t 'fold_preview: grouped folds are clean' 0 'folds look sound' \
  "$ML/cross-validation-strategy-designer/scripts/fold_preview.py" "$FX/ml/transactions.csv" --target is_fraud --strategy stratified-group --group-col card_id
t 'fold_preview: time folds need a gap' 1 'gap 0.0 days < label window 2' \
  "$ML/cross-validation-strategy-designer/scripts/fold_preview.py" "$FX/ml/transactions.csv" --target is_fraud --strategy time --time-col timestamp --label-window 2
t 'fold_preview: gap fixes time folds' 0 'folds look sound' \
  "$ML/cross-validation-strategy-designer/scripts/fold_preview.py" "$FX/ml/transactions.csv" --target is_fraud --strategy time --time-col timestamp --label-window 2 --gap 120

t 'split_audit: duplicates entity and time overlap' 1 'SA002 [high] customer_id: 12 customer_id value(s) in both sets' \
  "$ML/train-test-split-auditor/scripts/split_audit.py" "$FX/ml/churn_train.csv" "$FX/ml/churn_test.csv" --target churned --id-col customer_id --time-col signup_date --expect forward
t 'split_audit: forward-time violation' 1 'SA003 [high] signup_date: 12 test row(s) (10.7%) are not after the last training time' \
  "$ML/train-test-split-auditor/scripts/split_audit.py" "$FX/ml/churn_train.csv" "$FX/ml/churn_test.csv" --target churned --time-col signup_date --expect forward
t 'split_audit: production drift' 0 'SA004 [medium] monthly_charges: drift: PSI 1.607, KS 0.274' \
  "$ML/train-test-split-auditor/scripts/split_audit.py" "$FX/ml/churn_train.csv" "$FX/ml/churn_prod.csv" --target churned --id-col customer_id --drop zip_code cancellation_reason
t 'split_audit: unseen levels' 0 'SA007 [low] payment_method: 15 test row(s) (15.0%) have levels unseen in train' \
  "$ML/train-test-split-auditor/scripts/split_audit.py" "$FX/ml/churn_train.csv" "$FX/ml/churn_prod.csv" --drop zip_code cancellation_reason customer_id
t 'near_duplicates: edited text copies' 1 '20 test rows with a near-duplicate in train (9.1%)' \
  "$ML/train-test-split-auditor/scripts/near_duplicates.py" "$FX/ml/tickets_train.csv" "$FX/ml/tickets_test.csv" --drop ticket_id --text-col body --threshold 0.8
t 'near_duplicates: clean split' 0 '0 test rows with a near-duplicate' \
  "$ML/train-test-split-auditor/scripts/near_duplicates.py" "$FX/ml/churn_train.csv" "$FX/ml/churn_prod.csv" --drop customer_id

t 'search_planner: tpe with pruning for lgbm' 0 'STRATEGY: TPE (Optuna) with pruning   trials: 200' \
  "$ML/hyperparameter-search-planner/scripts/search_planner.py" --model lgbm --rows 200000 --fit-seconds 40 --budget-hours 4 --folds 5 --workers 4
t 'search_planner: small logreg grid' 0 'STRATEGY: grid   trials: 10' \
  "$ML/hyperparameter-search-planner/scripts/search_planner.py" --model logreg --rows 5000 --fit-seconds 0.5 --trials 60
t 'search_planner: optuna format' 0 'trial.suggest_int("min_samples_leaf", 1, 50, log=True)' \
  "$ML/hyperparameter-search-planner/scripts/search_planner.py" --model rf --rows 50000 --fit-seconds 20 --budget-hours 1 --format optuna
t 'search_planner: needs a budget' 2 'give --budget-hours or --trials' \
  "$ML/hyperparameter-search-planner/scripts/search_planner.py" --model rf --rows 100 --fit-seconds 1
t 'analyze_search: boundary detection on sklearn results' 0 'BOUNDARY: best learning_rate=0.0175242 sits at the low end' \
  "$ML/hyperparameter-search-planner/scripts/analyze_search.py" "$FX/ml/cv_results.csv" --folds 5
t 'analyze_search: one-SE simplest pick' 0 '9 configuration(s) within 1 SE (0.0239) of the best; pick: l2_regularization=0.5000452302280258' \
  "$ML/hyperparameter-search-planner/scripts/analyze_search.py" "$FX/ml/cv_results.csv" --folds 5 --simpler "max_leaf_nodes:low"
t 'analyze_search: optuna trials' 0 'optuna search: 30 trials; best 0.8224' \
  "$ML/hyperparameter-search-planner/scripts/analyze_search.py" "$FX/ml/optuna_trials.csv"

t 'gen_optuna_study: fixed folds and pruning' 0 'trial.report(float(np.mean(values)), step=k)' \
  "$ML/optuna-study-writer/scripts/gen_optuna_study.py" "$FX/ml/churn.csv" --target churned --model lgbm --metric average_precision --drop customer_id
t 'gen_optuna_study: resumable storage' 0 'load_if_exists=True, direction="minimize"' \
  "$ML/optuna-study-writer/scripts/gen_optuna_study.py" "$FX/ml/house.csv" --target price --model xgb --metric neg_root_mean_squared_error
t 'gen_optuna_study: catboost conditional bootstrap' 0 'params["bagging_temperature"] = trial.suggest_float("bagging_temperature", 0.0, 1.0)' \
  "$ML/optuna-study-writer/scripts/gen_optuna_study.py" "$FX/ml/churn.csv" --target churned --model catboost --group-col customer_id --pruner hyperband
t 'gen_optuna_study: unknown column exits 2' 2 "column 'nope' not found" \
  "$ML/optuna-study-writer/scripts/gen_optuna_study.py" "$FX/ml/churn.csv" --target nope
t 'optuna_lint: inconsistent parameter definition' 1 "OP003 [high] parameter 'depth' suggested twice" \
  "$ML/optuna-study-writer/scripts/optuna_lint.py" "$FX/ml/optuna_bad.py"
t 'optuna_lint: wrong direction' 1 "OP006 [medium] direction='maximize' but the objective returns a loss/error" \
  "$ML/optuna-study-writer/scripts/optuna_lint.py" "$FX/ml/optuna_bad.py"
t 'optuna_lint: constant from except' 1 'OP007 [medium] broad except returns a constant score' \
  "$ML/optuna-study-writer/scripts/optuna_lint.py" "$FX/ml/optuna_bad.py"

t 'diagnose_curve: variance, data-limited' 0 'VERDICT: HIGH VARIANCE - DATA-LIMITED' \
  "$ML/learning-curve-diagnoser/scripts/diagnose_curve.py" "$FX/ml/learning_curve_variance.csv"
t 'diagnose_curve: power-law capped at training score' 0 'power-law fit: asymptote 0.9661, exponent 0.610, R^2 0.969' \
  "$ML/learning-curve-diagnoser/scripts/diagnose_curve.py" "$FX/ml/learning_curve_variance.csv" --target 0.95
t 'diagnose_curve: bias' 0 'VERDICT: HIGH BIAS' \
  "$ML/learning-curve-diagnoser/scripts/diagnose_curve.py" "$FX/ml/learning_curve_bias.csv"
t 'diagnose_curve: target above the ceiling' 0 'target 0.8: above the ceiling (asymptote) - not reachable with more data alone' \
  "$ML/learning-curve-diagnoser/scripts/diagnose_curve.py" "$FX/ml/learning_curve_bias.csv" --target 0.8
t 'diagnose_curve: missing column exits 2' 2 "column 'train_size' not found" \
  "$ML/learning-curve-diagnoser/scripts/diagnose_curve.py" "$FX/ml/history.csv"
t 'gen_learning_curve: geometric seeded sizes' 0 'sizes = np.unique(np.geomspace(0.1, 1.0, 6))' \
  "$ML/learning-curve-diagnoser/scripts/gen_learning_curve.py" "$FX/ml/churn.csv" --target churned --drop customer_id
t 'gen_learning_curve: time order kept' 0 'train_sizes=sizes, cv=cv, scoring=SCORING, shuffle=False' \
  "$ML/learning-curve-diagnoser/scripts/gen_learning_curve.py" "$FX/ml/churn.csv" --target churned --time-col signup_date
t 'gen_learning_curve: scorer must fit the task' 2 "scorer 'roc_auc' does not fit a regression target" \
  "$ML/learning-curve-diagnoser/scripts/gen_learning_curve.py" "$FX/ml/house.csv" --target price --scoring roc_auc

t 'training_history: overfitting after the best round' 0 'validation is best at iteration 225 and worsens from about 258' \
  "$ML/overfitting-underfitting-diagnoser/scripts/training_history.py" "$FX/ml/history.csv"
t 'training_history: column pair detection' 0 'train: train_logloss   validation: valid_logloss' \
  "$ML/overfitting-underfitting-diagnoser/scripts/training_history.py" "$FX/ml/history.csv"
t 'training_history: needs a validation column' 2 'cannot find validation column' \
  "$ML/overfitting-underfitting-diagnoser/scripts/training_history.py" "$FX/ml/sales.csv"
t 'validation_curve_report: best and zones' 0 'BEST: max_depth=6 (validation 0.8402, 1 SE = 0.003154)' \
  "$ML/overfitting-underfitting-diagnoser/scripts/validation_curve_report.py" "$FX/ml/validation_curve.csv"
t 'validation_curve_report: current value in overfit zone' 0 'CURRENT: max_depth=14 is in the overfit zone: move to a less complex setting (smaller max_depth, towards 6)' \
  "$ML/overfitting-underfitting-diagnoser/scripts/validation_curve_report.py" "$FX/ml/validation_curve.csv" --current 14
t 'validation_curve_report: missing column exits 2' 2 "column 'train_score' not found" \
  "$ML/overfitting-underfitting-diagnoser/scripts/validation_curve_report.py" "$FX/ml/history.csv"

t 'shap_summary: additivity and ranking' 0 'additivity: base + sum(SHAP) = prediction, max error' \
  "$ML/shap-value-explainer/scripts/shap_summary.py" "$FX/ml/shap_values.csv" --features "$FX/ml/shap_features.csv"
t 'shap_summary: direction from feature values' 0 '- tenure_months: higher values lower the output' \
  "$ML/shap-value-explainer/scripts/shap_summary.py" "$FX/ml/shap_values.csv" --features "$FX/ml/shap_features.csv"
t 'shap_summary: minor features not interpreted' 0 'minor feature (< 5% of the total): its shape is mostly noise' \
  "$ML/shap-value-explainer/scripts/shap_summary.py" "$FX/ml/shap_values.csv" --features "$FX/ml/shap_features.csv"
t 'shap_summary: misaligned features exit 2' 2 'features file has 400 rows, SHAP file has 200' \
  "$ML/shap-value-explainer/scripts/shap_summary.py" "$FX/ml/shap_values.csv" --features "$FX/ml/churn.csv"
t 'explain_row: waterfall with probabilities' 0 'support_calls = 12                    +3.638       2.038   88.5%' \
  "$ML/shap-value-explainer/scripts/explain_row.py" "$FX/ml/shap_values.csv" --features "$FX/ml/shap_features.csv" --select highest --top 3 --link logit
t 'explain_row: plain-language summary' 0 'Predicted churn probability: 93.6% for this case, against a baseline of 16.8%' \
  "$ML/shap-value-explainer/scripts/explain_row.py" "$FX/ml/shap_values.csv" --features "$FX/ml/shap_features.csv" --select highest --link logit --label "churn probability"
t 'explain_row: row out of range' 2 'error: --row 999 out of range (0..199)' \
  "$ML/shap-value-explainer/scripts/explain_row.py" "$FX/ml/shap_values.csv" --row 999
t 'gen_shap_script: HGB uses path-dependent' 0 'HistGradientBoosting -> tree_path_dependent' \
  "$ML/shap-value-explainer/scripts/gen_shap_script.py" --model m.joblib --data "$FX/ml/churn.csv" --target churned
t 'gen_shap_script: additivity asserted' 0 'assert err < 1e-3 * max(1.0, float(np.abs(output).max()))' \
  "$ML/shap-value-explainer/scripts/gen_shap_script.py" --model m.joblib --data "$FX/ml/churn.csv" --group

t 'compare_importances: split bias / redundancy' 1 'IMPURITY-ONLY  total_charges: 22% of gain but 2% of permutation' \
  "$ML/feature-importance-reporter/scripts/compare_importances.py" "$FX/ml/importances.csv"
t 'compare_importances: ID-like feature' 1 'ID-LIKE        customer_id_hash: identifier/hash/timestamp-like name' \
  "$ML/feature-importance-reporter/scripts/compare_importances.py" "$FX/ml/importances.csv"
t 'compare_importances: method agreement' 1 'permutation vs mean_abs_shap               0.95' \
  "$ML/feature-importance-reporter/scripts/compare_importances.py" "$FX/ml/importances.csv"
t 'compare_importances: shared information in a group' 1 'SHARED-INFO    tenure_months+total_charges: joint permutation 0.112 vs 0.085' \
  "$ML/feature-importance-reporter/scripts/compare_importances.py" "$FX/ml/importances.csv" --groups "$FX/ml/importance_groups.csv"
t 'compare_importances: long format rejected' 2 'features repeat: this looks like a long (run, feature, importance) file' \
  "$ML/feature-importance-reporter/scripts/compare_importances.py" "$FX/ml/importances_folds.csv"
t 'gen_importance_script: held-out permutation with repeats' 0 'perm = permutation_importance(model, X, y, scoring=SCORING, n_repeats=REPEATS' \
  "$ML/feature-importance-reporter/scripts/gen_importance_script.py" --model m.joblib --data "$FX/ml/churn_test.csv" --target churned
t 'gen_importance_script: invalid repeats' 2 'error: --repeats must be >= 2' \
  "$ML/feature-importance-reporter/scripts/gen_importance_script.py" --model m.joblib --data x.csv --target y --repeats 1

t 'ice_analysis: PDP shape' 0 'PDP decreases by 0.3805 over the grid (range 0.3805); 100% of steps go the same way' \
  "$ML/partial-dependence-plot-builder/scripts/ice_analysis.py" "$FX/ml/ice_tenure.csv"
t 'ice_analysis: subgroups hidden by the average' 0 'SUBGROUPS: two groups of curves with different strength: 20 rows change by -0.4885, 10 rows by -0.1645' \
  "$ML/partial-dependence-plot-builder/scripts/ice_analysis.py" "$FX/ml/ice_tenure.csv"
t 'ice_analysis: separator names the interaction' 0 'separator: contract_monthly (AUC 1.00' \
  "$ML/partial-dependence-plot-builder/scripts/ice_analysis.py" "$FX/ml/ice_tenure.csv" --features "$FX/ml/ice_rows.csv"
t 'ice_analysis: low-support grid' 0 'WARNING: 4 grid value(s) outside the 5th-95th percentile [3, 46.65]' \
  "$ML/partial-dependence-plot-builder/scripts/ice_analysis.py" "$FX/ml/ice_tenure.csv" --features "$FX/ml/ice_rows.csv"
t 'ice_analysis: wrong file exits 2' 2 "column 'row_id' not found" \
  "$ML/partial-dependence-plot-builder/scripts/ice_analysis.py" "$FX/ml/history.csv"
t 'gen_pdp_script: integer columns converted' 0 'X[ints] = X[ints].astype(float)' \
  "$ML/partial-dependence-plot-builder/scripts/gen_pdp_script.py" --model m.joblib --data "$FX/ml/churn.csv" --features tenure_months
t 'gen_pdp_script: ALE and pair' 0 'FEATURES, PAIR, ALE = ['"'"'tenure_months'"'"'], ['"'"'tenure_months'"'"', '"'"'plan'"'"'], True' \
  "$ML/partial-dependence-plot-builder/scripts/gen_pdp_script.py" --model m.joblib --data "$FX/ml/churn.csv" --features tenure_months --ale --pair tenure_months plan
t 'gen_pdp_script: grid too small' 2 'error: --sample must be >= 20 and --grid >= 3' \
  "$ML/partial-dependence-plot-builder/scripts/gen_pdp_script.py" --model m.joblib --data x.csv --features a --grid 2

t 'lime_stability: stable explanation' 0 'VERDICT: STABLE - report the stable features with their mean weights' \
  "$ML/lime-explanation-generator/scripts/lime_stability.py" "$FX/ml/lime_runs.csv"
t 'lime_stability: negligible features ignored' 0 'region=west                       +0.0211  0.0255   1.21   75%    50%  negligible' \
  "$ML/lime-explanation-generator/scripts/lime_stability.py" "$FX/ml/lime_runs.csv"
t 'lime_stability: low fidelity flagged' 0 'VERDICT: STABLE BUT LOW FIDELITY' \
  "$ML/lime-explanation-generator/scripts/lime_stability.py" "$FX/ml/lime_runs_lowfid.csv"
t 'lime_stability: sign disagreement with SHAP' 0 'DISAGREES: last_login_days vs last_login_days' \
  "$ML/lime-explanation-generator/scripts/lime_stability.py" "$FX/ml/lime_runs.csv" --compare "$FX/ml/lime_compare_shap.csv"
t 'lime_stability: wrong columns exit 2' 2 "column 'weight' not found" \
  "$ML/lime-explanation-generator/scripts/lime_stability.py" "$FX/ml/importances_folds.csv"
t 'gen_lime_script: new seed per repeat' 0 'explainer.random_state = np.random.RandomState(SEED + r)' \
  "$ML/lime-explanation-generator/scripts/gen_lime_script.py" --model m.joblib --train "$FX/ml/churn_train.csv" --rows "$FX/ml/churn_test.csv" --target churned
t 'gen_lime_script: continuous mode' 0 'DISCRETIZE = False' \
  "$ML/lime-explanation-generator/scripts/gen_lime_script.py" --model m.joblib --train a.csv --rows b.csv --no-discretize
t 'gen_lime_script: too few samples' 2 'error: --repeats must be >= 2, --samples >= 500' \
  "$ML/lime-explanation-generator/scripts/gen_lime_script.py" --model m.joblib --train a.csv --rows b.csv --samples 100

t 'slice_metrics: underperforming group' 1 'UNDERPERFORMS: group = B: AUC 0.689 (CI 0.629-0.739) below overall 0.795' \
  "$ML/model-card-writer/scripts/slice_metrics.py" "$FX/ml/preds_slices.csv" --slices group age_band --threshold 0.4
t 'slice_metrics: equal-opportunity gap' 1 'GAP: group: tpr differs by 0.327 across levels (> 0.1)' \
  "$ML/model-card-writer/scripts/slice_metrics.py" "$FX/ml/preds_slices.csv" --slices group --threshold 0.4
t 'slice_metrics: low-n slice' 1 'LOW-N: age_band = unknown: n=16, positives=5' \
  "$ML/model-card-writer/scripts/slice_metrics.py" "$FX/ml/preds_slices.csv" --slices group age_band --threshold 0.4
t 'slice_metrics: regression slices' 0 '| segment = large | 102 | 136.523' \
  "$ML/model-card-writer/scripts/slice_metrics.py" "$FX/ml/reg_preds.csv" --regression --slices segment
t 'slice_metrics: labels must be binary' 2 'labels must be 0/1 for classification' \
  "$ML/model-card-writer/scripts/slice_metrics.py" "$FX/ml/reg_preds.csv" --score-col y_pred
t 'model_card: slice table in the card' 0 '| group = B | 490 | 127 | 0.689 [0.629, 0.739] | 0.512 [0.418, 0.605]' \
  "$ML/model-card-writer/scripts/model_card.py" "$FX/ml/model_card_spec.json" --slices "$FX/ml/slices_report.json"
t 'model_card: TODOs visible and strict fails' 1 '**TODO:** uses the model must not be used for.' \
  "$ML/model-card-writer/scripts/model_card.py" "$FX/ml/model_card_minimal.json" --strict
t 'card_lint: missing sections and overclaiming' 1 "MC006 [medium] overclaiming 'unbiased'" \
  "$ML/model-card-writer/scripts/card_lint.py" "$FX/ml/model_card_bad.md"
t 'card_lint: placeholder' 1 'MC002 [high] placeholder left in: Customer table. TODO: add the period.' \
  "$ML/model-card-writer/scripts/card_lint.py" "$FX/ml/model_card_bad.md"

t 'linear_counterfactual: optimal with integer branching' 0 'cost 3.167 (MAD units), 2 feature(s) changed, new probability 74.3%' \
  "$ML/counterfactual-explanation-generator/scripts/linear_counterfactual.py" "$FX/ml/cf_logreg.json" "$FX/ml/cf_row.json" --target-prob 0.75
t 'linear_counterfactual: essential feature' 0 'no feasible counterfactual without changing support_calls' \
  "$ML/counterfactual-explanation-generator/scripts/linear_counterfactual.py" "$FX/ml/cf_logreg.json" "$FX/ml/cf_row.json" --target-prob 0.3
t 'linear_counterfactual: no recourse' 1 'NO RECOURSE: no combination of allowed changes reaches the target' \
  "$ML/counterfactual-explanation-generator/scripts/linear_counterfactual.py" "$FX/ml/cf_logreg.json" "$FX/ml/cf_row.json" --target-prob 0.02
t 'linear_counterfactual: linear needs a target value' 2 'linear models need --target-value' \
  "$ML/counterfactual-explanation-generator/scripts/linear_counterfactual.py" "$FX/ml/cf_linear_bad.json" "$FX/ml/cf_row.json"
t 'cf_validate: constraint violations' 1 'violation: DIRECTION monthly_charges (84.15 -> 250, allowed: decrease)' \
  "$ML/counterfactual-explanation-generator/scripts/cf_validate.py" --original "$FX/ml/cf_row.json" --cfs "$FX/ml/cf_candidates.csv" --train "$FX/ml/cf_train.csv" --constraints "$FX/ml/cf_logreg.json"
t 'cf_validate: immutable feature' 1 'violation: IMMUTABLE tenure_months' \
  "$ML/counterfactual-explanation-generator/scripts/cf_validate.py" --original "$FX/ml/cf_row.json" --cfs "$FX/ml/cf_candidates.csv" --train "$FX/ml/cf_train.csv" --constraints "$FX/ml/cf_logreg.json"
t 'cf_validate: prediction must flip' 1 'invalid: prediction 0.88 does not meet the target' \
  "$ML/counterfactual-explanation-generator/scripts/cf_validate.py" --original "$FX/ml/cf_row.json" --cfs "$FX/ml/cf_candidates.csv" --train "$FX/ml/cf_train.csv" --pred-col churn_prob --target-prob 0.75 --side below
t 'cf_validate: derived-feature relation' 1 'violation: RELATION total_charges = 515.55 but tenure_months*monthly_charges = 1520.55' \
  "$ML/counterfactual-explanation-generator/scripts/cf_validate.py" --original "$FX/ml/cf_dice_row.json" --cfs "$FX/ml/cf_dice_cfs.csv" --train "$FX/ml/cf_train_cat.csv" --constraints "$FX/ml/cf_constraints_cat.json" --relation "total_charges=tenure_months*monthly_charges" --relation-tol 0.25
t 'gen_dice_script: directions become permitted ranges' 0 'if cfg.get("direction") == "decrease":' \
  "$ML/counterfactual-explanation-generator/scripts/gen_dice_script.py" --model m.joblib --train "$FX/ml/cf_train.csv" --rows "$FX/ml/cf_train.csv" --target churned
t 'gen_dice_script: total must be positive' 2 'error: --total must be >= 1' \
  "$ML/counterfactual-explanation-generator/scripts/gen_dice_script.py" --model m.joblib --train a.csv --rows b.csv --target y --total 0

t 'ts_profile: weekly season and strengths' 0 'season length: 7   trend strength: 0.89   seasonal strength: 0.94' \
  "$ML/time-series-forecasting-model-builder/scripts/ts_profile.py" "$FX/ml/sales.csv"
t 'ts_profile: gaps reported' 0 'missing periods: 3' \
  "$ML/time-series-forecasting-model-builder/scripts/ts_profile.py" "$FX/ml/sales.csv"
t 'ts_profile: intermittent demand class' 0 'demand type: intermittent   zeros: 82%   ADI 5.33   CV^2 0.22' \
  "$ML/time-series-forecasting-model-builder/scripts/ts_profile.py" "$FX/ml/spares.csv"
t 'ts_backtest: Holt-Winters beats seasonal naive' 0 'holt_winters       1.155   1.264  +30.5%' \
  "$ML/time-series-forecasting-model-builder/scripts/ts_backtest.py" "$FX/ml/sales.csv" --horizon 28 --folds 6
t 'ts_backtest: external forecasts on the same origins' 0 'AutoETS            1.367' \
  "$ML/time-series-forecasting-model-builder/scripts/ts_backtest.py" "$FX/ml/sales.csv" --horizon 28 --folds 6 --forecasts "$FX/ml/sf_forecasts.csv"
t 'ts_backtest: intermittent ranked by RMSSE' 0 'WARNING: naive forecasts almost nothing (bias -100%)' \
  "$ML/time-series-forecasting-model-builder/scripts/ts_backtest.py" "$FX/ml/spares.csv" --horizon 28 --folds 4
t 'ts_backtest: needs a horizon' 2 'the following arguments are required: --horizon' \
  "$ML/time-series-forecasting-model-builder/scripts/ts_backtest.py" "$FX/ml/sales.csv"
t 'gen_forecast_script: leak-free lags' 0 'base = s.shift(H)                                    # every window ends H periods back' \
  "$ML/time-series-forecasting-model-builder/scripts/gen_forecast_script.py" --data "$FX/ml/sales.csv" --value-col units --horizon 28
t 'gen_forecast_script: bad coverage' 2 'error: need --horizon >= 1, --folds >= 1 and 0.5 <= --coverage < 1' \
  "$ML/time-series-forecasting-model-builder/scripts/gen_forecast_script.py" --data x.csv --horizon 7 --coverage 0.3

t 'km_report: medians with confidence intervals' 0 'median survival: 283.4 (95% CI 177.6 - 388.3)' \
  "$ML/survival-analysis-model-builder/scripts/km_report.py" "$FX/ml/survival.csv" --duration-col duration_days --event-col event --group plan --at 90 180 365
t 'km_report: log-rank test' 0 'log-rank test: chi2 = 18.845, df = 1, p = 1.418e-05' \
  "$ML/survival-analysis-model-builder/scripts/km_report.py" "$FX/ml/survival.csv" --duration-col duration_days --event-col event --group plan
t 'km_report: crossing curves' 0 'WARNING: the survival curves cross' \
  "$ML/survival-analysis-model-builder/scripts/km_report.py" "$FX/ml/survival_ph.csv" --duration-col days --event-col died --group arm
t 'km_report: event must be 0/1' 2 'event must be 0 (censored) or 1 (event)' \
  "$ML/survival-analysis-model-builder/scripts/km_report.py" "$FX/ml/survival.csv" --duration-col duration_days --event-col age
t 'cox_fit: hazard ratios match lifelines' 0 'plan=premium            -0.7946   0.452    [0.310, 0.658]   -4.13  3.57e-05   0.952' \
  "$ML/survival-analysis-model-builder/scripts/cox_fit.py" "$FX/ml/survival.csv" --duration-col duration_days --event-col event --covariates plan age
t 'cox_fit: proportional hazards violated' 1 'PH assumption violated for: arm=surgery' \
  "$ML/survival-analysis-model-builder/scripts/cox_fit.py" "$FX/ml/survival_ph.csv" --duration-col days --event-col died --covariates arm age
t 'cox_fit: unknown covariate' 2 'covariates not found: region' \
  "$ML/survival-analysis-model-builder/scripts/cox_fit.py" "$FX/ml/survival.csv" --duration-col duration_days --event-col event --covariates region
t 'gen_survival_script: survival metrics' 0 'ibs = integrated_brier_score(y_tr, y_te, S, times)' \
  "$ML/survival-analysis-model-builder/scripts/gen_survival_script.py" --data "$FX/ml/survival.csv" --duration-col duration_days --event-col event --covariates plan age
t 'gen_survival_script: test size bounds' 2 'error: --test-size must be between 0.1 and 0.5' \
  "$ML/survival-analysis-model-builder/scripts/gen_survival_script.py" --data x.csv --duration-col t --event-col e --covariates a --test-size 0.9

t 'interaction_profile: size and popularity' 0 'item popularity Gini 0.28; share of interactions on top 1% / 10% / 20% of items: 4% / 22% / 38%' \
  "$ML/recommendation-system-designer/scripts/interaction_profile.py" "$FX/ml/ratings.csv"
t 'interaction_profile: explicit feedback advice' 0 'explicit ratings: rating prediction (RMSE) rarely matches the product goal' \
  "$ML/recommendation-system-designer/scripts/interaction_profile.py" "$FX/ml/ratings.csv"
t 'interaction_profile: missing columns' 2 'cannot find the user column' \
  "$ML/recommendation-system-designer/scripts/interaction_profile.py" "$FX/ml/sales.csv"
t 'rec_eval: model beats popularity' 0 'genre_pop             0.1020      0.6973      0.7551      0.3741      0.3378      0.4395' \
  "$ML/recommendation-system-designer/scripts/rec_eval.py" --recs "$FX/ml/rec_lists.csv" --test "$FX/ml/ratings_test.csv" --train "$FX/ml/ratings_train.csv" --k 10 --min-rating 4 --item-features "$FX/ml/item_genres.csv"
t 'rec_eval: popularity baseline always computed' 0 'popularity            0.0490      0.3639' \
  "$ML/recommendation-system-designer/scripts/rec_eval.py" --recs "$FX/ml/rec_lists.csv" --test "$FX/ml/ratings_test.csv" --train "$FX/ml/ratings_train.csv" --k 10 --min-rating 4
t 'rec_eval: random list loses to popularity' 1 'NO MODEL BEATS POPULARITY on NDCG@10' \
  "$ML/recommendation-system-designer/scripts/rec_eval.py" --recs "$FX/ml/rec_random.csv" --test "$FX/ml/ratings_test.csv" --train "$FX/ml/ratings_train.csv" --k 10 --min-rating 4
t 'temporal_split: leave-last split' 0 'leave-last: train 1425 rows, test 165 rows (55 users)' \
  "$ML/recommendation-system-designer/scripts/temporal_split.py" "$FX/ml/ratings.csv" --mode leave-last --n 3 --min-train 3 --prefix "$WORK/rs_split"
t 'temporal_split: missing time column' 2 "column 'timestamp' not found" \
  "$ML/recommendation-system-designer/scripts/temporal_split.py" "$FX/ml/churn.csv" --user-col customer_id --item-col plan

t 'itemknn: explained recommendations' 0 'user_id,item_id,rank,score,because' \
  "$ML/collaborative-filtering-implementer/scripts/itemknn.py" "$FX/ml/ratings_train.csv" --min-rating 4 --k 3
t 'itemknn: first recommendation for u00' 0 'u00,i64,1,1.562703,i76' \
  "$ML/collaborative-filtering-implementer/scripts/itemknn.py" "$FX/ml/ratings_train.csv" --weighted --k 10
t 'itemknn: rating column needed for --min-rating' 2 "rating column 'rating' not found" \
  "$ML/collaborative-filtering-implementer/scripts/itemknn.py" "$FX/ml/importances_folds.csv" --user-col run --item-col feature --min-rating 4
t 'gen_mf_script: EASE closed form' 0 'B = -P / np.diag(P)' \
  "$ML/collaborative-filtering-implementer/scripts/gen_mf_script.py" --train "$FX/ml/ratings_train.csv" --min-rating 4
t 'gen_mf_script: ALS confidence weighting' 0 'C = 1 + alpha * X' \
  "$ML/collaborative-filtering-implementer/scripts/gen_mf_script.py" --train "$FX/ml/ratings_train.csv" --models als
t 'gen_mf_script: k must be positive' 2 'error: --k and --val-n must be >= 1' \
  "$ML/collaborative-filtering-implementer/scripts/gen_mf_script.py" --train x.csv --k 0

t 'ltr_data_check: unsorted groups are blocking' 1 'BLOCKING: rows of some queries are not contiguous' \
  "$ML/learning-to-rank-model-builder/scripts/ltr_data_check.py" "$FX/ml/ltr.csv" --exclude score
t 'ltr_data_check: single-label query' 1 'WARNING: 1 query(ies) where every document has the same label (q07)' \
  "$ML/learning-to-rank-model-builder/scripts/ltr_data_check.py" "$FX/ml/ltr.csv" --exclude score
t 'ltr_data_check: single-feature baseline' 1 'bm25                         0.9148        0.4508              0%' \
  "$ML/learning-to-rank-model-builder/scripts/ltr_data_check.py" "$FX/ml/ltr.csv" --exclude score
t 'rank_eval: linear gain matches sklearn' 0 'bm25                   0.9322' \
  "$ML/learning-to-rank-model-builder/scripts/rank_eval.py" "$FX/ml/ltr.csv" --scores bm25 --k 10 --gain linear
t 'rank_eval: input-order ties reproduce LightGBM' 0 'pred                   0.9019' \
  "$ML/learning-to-rank-model-builder/scripts/rank_eval.py" "$FX/ml/ltr_coarse_scores.csv" --scores pred --k 5 --empty one --ties input
t 'rank_eval: no significant gain over bm25' 1 'score              diff +0.0049 [95% CI -0.0240, +0.0350]  p = 0.7410' \
  "$ML/learning-to-rank-model-builder/scripts/rank_eval.py" "$FX/ml/ltr.csv" --scores score clicks --baseline bm25 --k 5
t 'rank_eval: unknown score column' 2 'columns not found: nope' \
  "$ML/learning-to-rank-model-builder/scripts/rank_eval.py" "$FX/ml/ltr.csv" --scores nope
t 'gen_ltr_script: groups sorted before training' 0 'df = df.sort_values(QID, kind="stable").reset_index(drop=True)' \
  "$ML/learning-to-rank-model-builder/scripts/gen_ltr_script.py" --data "$FX/ml/ltr.csv" --features bm25 clicks
t 'gen_ltr_script: folds must be >= 2' 2 'error: --k must be >= 1 and --folds >= 2' \
  "$ML/learning-to-rank-model-builder/scripts/gen_ltr_script.py" --data x.csv --folds 1

t 'fraud_velocity_features: burst detected point-in-time' 0 'T90005,K007,2024-03-13T00:15:00,848.67,electronics,US,1,0.91,5,6,6,2982.36' \
  "$ML/fraud-detection-model-designer/scripts/fraud_velocity_features.py" "$FX/ml/transactions.csv" --entity card_id --categorical merchant_category country
t 'fraud_velocity_features: bad window unit' 2 "window '1w': use a number with s, m, h or d" \
  "$ML/fraud-detection-model-designer/scripts/fraud_velocity_features.py" "$FX/ml/transactions.csv" --entity card_id --windows 1w
t 'fraud_eval: ranking metrics' 0 'ROC AUC 0.9884   average precision 0.8312 (random = 0.0226)' \
  "$ML/fraud-detection-model-designer/scripts/fraud_eval.py" "$FX/ml/transactions.csv"
t 'fraud_eval: cost-optimal threshold' 0 'cost-optimal threshold 0.3331: 121 alerts, precision 27.3%, value detection 98.6%' \
  "$ML/fraud-detection-model-designer/scripts/fraud_eval.py" "$FX/ml/transactions.csv"
t 'fraud_eval: alert capacity' 0 'within 1 alerts/day: threshold 0.5695, recall 70.6%, value detection 73.1%' \
  "$ML/fraud-detection-model-designer/scripts/fraud_eval.py" "$FX/ml/transactions.csv" --alerts-per-day 1
t 'fraud_eval: labels must be binary' 2 'labels must be 0/1' \
  "$ML/fraud-detection-model-designer/scripts/fraud_eval.py" "$FX/ml/transactions.csv" --label-col amount
t 'gen_fraud_model_script: out-of-time gap' 0 't_train_end = t_test - pd.to_timedelta(GAP_DAYS, unit="D")' \
  "$ML/fraud-detection-model-designer/scripts/gen_fraud_model_script.py" --data "$FX/ml/transactions.csv" --entity card_id
t 'gen_fraud_model_script: leak-free windows' 0 'roll = g.rolling(w, closed="left")' \
  "$ML/fraud-detection-model-designer/scripts/gen_fraud_model_script.py" --data "$FX/ml/transactions.csv" --entity card_id

t 'rct_check: average effect with CI' 0 'ATE: treated 0.1404 vs control 0.1082 -> +0.0322 [95% CI +0.0033, +0.0612]' \
  "$ML/uplift-model-builder/scripts/rct_check.py" "$FX/ml/uplift.csv" --covariates age segment --segments segment
t 'rct_check: heterogeneity across segments' 0 'heterogeneity: Q = 21.509, df = 2, p = 2.135e-05' \
  "$ML/uplift-model-builder/scripts/rct_check.py" "$FX/ml/uplift.csv" --segments segment
t 'rct_check: sample ratio mismatch' 1 'FLAG: sample ratio mismatch' \
  "$ML/uplift-model-builder/scripts/rct_check.py" "$FX/ml/uplift.csv" --expected-share 0.3
t 'rct_check: treatment must be binary' 2 'treatment must be 0/1' \
  "$ML/uplift-model-builder/scripts/rct_check.py" "$FX/ml/uplift.csv" --treatment-col age
t 'uplift_eval: Qini and AUUC match scikit-uplift' 0 '[uplift_score]   Qini coefficient 0.1768   AUUC 0.0785' \
  "$ML/uplift-model-builder/scripts/uplift_eval.py" "$FX/ml/uplift.csv" --scores uplift_score
t 'uplift_eval: sleeping dogs' 0 '-0.1010  [-0.1964, -0.0055]  sleeping dogs' \
  "$ML/uplift-model-builder/scripts/uplift_eval.py" "$FX/ml/uplift.csv" --scores uplift_score
t 'uplift_eval: profit of targeting' 0 'best: treat the top 30% (profit +2.864 per person)' \
  "$ML/uplift-model-builder/scripts/uplift_eval.py" "$FX/ml/uplift.csv" --scores uplift_score --cost-per-treatment 0.5 --value-per-outcome 20
t 'uplift_eval: learner comparison on holdout' 0 '[class_transform]   Qini coefficient 0.2143' \
  "$ML/uplift-model-builder/scripts/uplift_eval.py" "$FX/ml/uplift_holdout_scores.csv" --scores t_learner x_learner class_transform
t 'gen_uplift_script: X-learner propensity weighting' 0 'scores["x_learner"] = e * g0.predict(Xho) + (1 - e) * g1.predict(Xho)' \
  "$ML/uplift-model-builder/scripts/gen_uplift_script.py" --data "$FX/ml/uplift.csv" --covariates age segment
t 'gen_uplift_script: holdout bounds' 2 'error: --holdout must be between 0.2 and 0.6' \
  "$ML/uplift-model-builder/scripts/gen_uplift_script.py" --data x.csv --covariates a --holdout 0.9
