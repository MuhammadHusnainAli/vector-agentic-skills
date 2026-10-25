# Vector Agentic Skills

**Ready-to-install Agent Skills for Claude Code and other AI agents, organised by category and sub-category.**

Each skill is a folder with a `SKILL.md` (YAML frontmatter + instructions), `references/` for detailed docs, and `scripts/` with tested helper tools the agent can run. This is the [Agent Skills](https://docs.claude.com/en/docs/claude-code/skills) format, so the folders work as-is in Claude Code, the Claude apps, the Claude Agent SDK and any agent that loads `SKILL.md` folders.

**Website:** [agenticskills.vector-ai-lab.com](https://agenticskills.vector-ai-lab.com): search, read and install every skill.

## Skills

| Category | Sub-category | Skills | What's inside |
|----------|--------------|--------|---------------|
| [Programming](skills/programming/README.md) | [SQL](skills/programming/sql/README.md) | 11 | Writing, syntax checking, explaining, optimising, performance tuning, debugging, window functions, analytics, reporting, data quality, dialect translation |
| [Programming](skills/programming/README.md) | [Python](skills/programming/python/README.md) | 13 | Idiomatic code review, comprehensions, type hints, dataclasses, exception design, context managers, asyncio, threads, multiprocessing, the GIL, deadlocks, Trio/AnyIO, beginner tutoring (for AI engineers) |
| [Programming](skills/programming/README.md) | [Rust](skills/programming/rust/README.md) | 7 | Borrow-checker errors, lifetimes, trait design, thiserror/anyhow error handling, unsafe audits, Tokio/axum services, Cargo workspaces |
| [Productivity](skills/productivity/README.md) | [Excel](skills/productivity/excel/README.md) | 3 | Formulas, advanced formulas (LAMBDA, LET, dynamic arrays, regex), workbook fundamentals |
| [AI & Machine Learning](skills/ai-ml/README.md) | [Classical Machine Learning](skills/ai-ml/classical-ml/README.md) | 45 | Problem framing, feature engineering, scikit-learn/XGBoost/LightGBM/CatBoost, clustering, validation, SHAP/PDP/LIME/counterfactuals, model cards, forecasting, survival, recommenders, ranking, fraud, uplift |
| [Languages, Linguistics & Translation](skills/languages/README.md) | [Language Teaching](skills/languages/language-teaching/README.md) | 38 | Lesson planning (PPP, TBL), worksheets, text adaptation, listening and dialogues, CEFR/ACTFL syllabuses and can-dos, placement tests, rubrics, quizzes, error correction, pronunciation, reports, CELTA/Delta, observation, classroom management, online teaching, ESP, EAP, young learners, adult literacy, refugee support |

Every skill ships at least one helper script, written in the skill's language (Rust skills ship std-only `.rs` files compiled with `rustc`) and smoke-tested in CI by `tests/run_tests.sh`:

| Skill | Script | What it does |
|-------|--------|--------------|
| sql-query-writer | `plan_joins.py` | Finds join paths from CREATE TABLE statements and prints a SELECT skeleton |
| sql-syntax-checker | `check_sql.py` | Structural checks, plus full grammar parsing when `sqlglot` is installed |
| sql-query-explainer | `outline_query.py` | Breaks a query into its parts in logical execution order |
| sql-optimizer | `find_antipatterns.py` | Flags 14 performance anti-patterns with rewrites |
| sql-performance-tuning | `analyze_plan.py` | Finds bottlenecks in PostgreSQL `EXPLAIN (ANALYZE, FORMAT JSON)` output |
| sql-debugger | `diagnose_error.py` | Explains error messages from 5 databases with ordered fixes |
| sql-window-functions | `sql_sandbox.py` | Runs queries against CSVs in in-memory SQLite to verify results |
| sql-analytics | `analytics_sql.py` | Generates cohort, funnel, growth and percentile SQL for 4 dialects |
| sql-reporting | `date_ranges.py` | Index-friendly date filters for MTD, YTD, previous period and more |
| sql-data-quality | `profile_data.py` | Profiling SQL, or a CSV profile that can gate a pipeline |
| sql-dialect-translator | `translate_sql.py` | Translates SQL between dialects with `sqlglot` |
| python-idiomatic-code-reviewer | `review_idioms.py` | 46 rules for unpythonic and risky code, incl. hardcoded API keys and blocking calls in async |
| python-comprehension-refactorer | `find_comprehension_candidates.py` | Prints the exact comprehension for loops that build lists, dicts and sets; flags over-complex ones |
| python-type-hints-annotator | `annotation_audit.py` | Annotation coverage with a CI gate, legacy-typing rewrites and inferred types |
| python-dataclass-converter | `to_dataclass.py` | Converts boilerplate classes to dataclasses; generates dataclass/pydantic/TypedDict from a JSON sample |
| python-exception-handling-designer | `audit_exceptions.py` | 14 rules: swallowed errors, missing `from`, swallowed cancellation, bad handler order |
| python-exception-handling-designer | `scaffold_exceptions.py` | Generates an `errors.py` hierarchy with retryable flags and HTTP mapping (`--preset llm-app`) |
| python-context-manager-writer | `ctx_tool.py` | Finds leaked resources and broken `@contextmanager`s; scaffolds 8 recipes (timer, atomic write, GPU inference...) |
| python-beginner-concept-tutor | `explain_concepts.py` | Lists the concepts a file uses in learning order; traces a snippet step by step like Python Tutor |
| python-asyncio-pattern-advisor | `async_lint.py` | 24 asyncio rules: blocking calls on the loop, dangling tasks, unbounded fan-out, swallowed cancellation |
| python-async-deadlock-debugger | `hang_scan.py`, `hang_watchdog.py` | Finds lock-order cycles and hang risks statically; runs a script and dumps every thread/task when it hangs |
| python-gil-bottleneck-analyzer | `gil_probe.py`, `profile_classify.py` | Measures thread vs process scaling; classifies py-spy/pstats profiles as GIL-bound, contended or releasing |
| python-multiprocessing-pool-designer | `pool_tool.py` | Checks Pool code for pickling and lifecycle bugs; plans worker counts from memory, CPU and payload size |
| python-threadpool-executor-builder | `executor_tool.py` | Checks ThreadPoolExecutor code (dropped futures, self-waits); scaffolds bounded-map and other recipes |
| python-trio-anyio-migrator | `migrate_async.py` | Plans and diffs an asyncio -> AnyIO/Trio migration, separating mechanical rewrites from manual items |
| rust-borrow-checker-error-explainer | `parse_diagnostics.rs`, `explain_code.rs`, `runtime_panic.rs` | Explains rustc/cargo borrow errors (text or JSON) with fixes ranked best first; traces RefCell/Mutex panics |
| rust-lifetime-annotation-advisor | `elision_check.rs`, `missing_lifetime.rs`, `static_bounds.rs`, `lifetime_smells.rs` | 12 lifetime rules with corrected signatures: needless, missing (E0106/E0392), over-strict `'static`, design smells |
| rust-trait-design-reviewer | `dyn_compat.rs`, `trait_shape.rs`, `api_traits.rs`, `api_signatures.rs`, `scaffold_trait.rs` | 14 trait/API rules (dyn compatibility, From vs Into, std traits); compiling sealed/typestate/newtype templates |
| rust-error-handling-thiserror-anyhow-designer | `unwrap_audit.rs`, `error_types.rs`, `error_flow.rs`, `scaffold_errors.rs` | 13 error-handling rules; generates a thiserror 2 `error.rs` (codes, retries, HTTP mapping) from a JSON spec |
| rust-unsafe-block-auditor | `unsafe_inventory.rs`, `safety_comments.rs`, `ub_patterns.rs`, `risky_calls.rs`, `ffi_and_globals.rs` | Unsafe inventory with SAFETY status, 28 UB/FFI/edition-2024 rules |
| rust-tokio-async-service-builder | `blocking_in_async.rs`, `await_holding.rs`, `task_hygiene.rs`, `service_hygiene.rs`, `scaffold_service.rs` | 19 Tokio/axum rules; generates an axum 0.8 service that compiles and passes its tests |
| rust-cargo-workspace-designer | `crate_graph.rs`, `manifest_lint.rs`, `dep_audit.rs` | Layered crate graph with cycle detection and 20 Cargo manifest/dependency rules |
| excel-formulas | `check_formula.py` | Lints formulas: parentheses, strings, unknown and volatile functions |
| excel-advanced-formulas | `check_compat.py` | Reports the minimum Excel version a formula needs |
| excel-fundamentals | `inspect_workbook.py` | Reports an .xlsx's sheets, tables, names, validation and links |
| ml-problem-framing-advisor | `frame_check.py`, `target_profile.py` | Checks a problem framing for decision, label windows, leakage-by-framing; profiles the target |
| ml-feasibility-assessor | `feasibility_scan.py`, `sample_size.py` | GO / NO-GO scan: volume, label quality, single-feature signal, leaks; sample-size arithmetic |
| ml-baseline-model-builder | `baseline_scores.py`, `scaffold_baseline.py` | Dummy, rule and OneR baselines with honest metrics; scaffolds a leak-free first model |
| ml-success-metric-selector | `metric_report.py`, `pick_metric.py` | Picks the metric from the decision; full metric panel and cost-optimal threshold (sklearn-identical) |
| ml-vs-rules-decision-advisor | `rule_learner.py`, `rules_vs_ml.py` | Scores rules vs ML on 12 factors; learns a readable rule set and emits it as SQL |
| ml-project-scoping-writer | `scope_doc.py`, `scope_lint.py` | Writes the ML scoping doc from a JSON spec; lints scope docs for vague commitments |
| feature-engineering-idea-generator | `profile_columns.py`, `suggest_features.py` | Infers column roles and proposes ranked, leakage-aware features with pandas code |
| categorical-encoding-selector | `encoding_plan.py`, `te_leakage_check.py` | Per-column encoding plan and ColumnTransformer; measures target-encoding leakage |
| feature-scaling-advisor | `scale_impact.py`, `scaling_plan.py` | Scaling/transform plan per column; measures the effect on a k-NN model |
| feature-selection-analyzer | `filter_select.py`, `importance_stability.py` | Filter selection with redundancy groups; importance stability across folds |
| target-leakage-detector | `code_leak_lint.py`, `leakage_scan.py` | Out-of-fold single-feature and missingness leak scan; AST linter for pipeline leaks |
| time-based-feature-builder | `gen_window_sql.py`, `pit_features.py` | Point-in-time window, recency and RFM features; matching SQL for 4 warehouses |
| feature-store-schema-designer | `gen_feast_repo.py`, `lint_feature_spec.py` | Lints feature specs for 12 design errors; generates a working Feast repo |
| scikit-learn-pipeline-builder | `gen_pipeline.py`, `pipeline_lint.py` | Generates a runnable Pipeline/ColumnTransformer script; lints sklearn API misuse |
| classification-model-selector | `bakeoff_scaffold.py`, `select_classifier.py` | Ranks classifiers for the data and constraints; scaffolds a fair bake-off |
| regression-model-trainer | `residual_report.py`, `target_diagnostics.py` | Target diagnostics to pick the loss; residual report with calibration and segment bias |
| xgboost-lightgbm-tuner | `gbm_param_advisor.py`, `parse_gbm_log.py` | Data-sized GBM parameters; parses training logs for best iteration and overfitting |
| catboost-model-builder | `catboost_params_check.py`, `catboost_plan.py` | Plans cat/text/numeric columns and a training script; checks CatBoost parameter conflicts |
| imbalanced-class-handler | `imbalance_report.py`, `threshold_tuner.py` | Imbalance severity and strategy ladder; thresholds under six policies with prior correction |
| ml-model-comparison-reporter | `compare_models.py`, `paired_predictions.py` | Corrected t-test, Wilcoxon, Bayesian, Friedman on CV folds; DeLong, McNemar, bootstrap on one test set |
| clustering-algorithm-selector | `cluster_tendency.py`, `select_clustering.py` | Hopkins tendency check; recommends a clustering algorithm for the data shape |
| kmeans-cluster-count-finder | `cluster_profile.py`, `k_sweep.py` | Elbow, silhouette, CH, DB and gap statistic sweep; profiles the clusters |
| dbscan-parameter-tuner | `dbscan_grid.py`, `kdist.py` | k-distance knee for eps; stability-checked eps/min_samples grid |
| pca-dimensionality-reducer | `pca_outliers.py`, `pca_report.py` | Explained variance, components to keep, loadings; reconstruction-error outliers |
| umap-tsne-embedding-visualizer | `embedding_trust.py`, `gen_embedding_plot.py` | Trustworthiness and neighbour preservation of 2-D embeddings; plot script generator |
| anomaly-detection-model-builder | `anomaly_eval.py`, `anomaly_scores.py` | Pure-Python Isolation Forest / robust scores; evaluates detectors against labels |
| cross-validation-strategy-designer | `cv_advisor.py`, `fold_preview.py` | Recommends the splitter (grouped, temporal, stratified); previews folds |
| train-test-split-auditor | `near_duplicates.py`, `split_audit.py` | Audits splits for overlap, drift and leakage; finds near-duplicates across splits |
| hyperparameter-search-planner | `analyze_search.py`, `search_planner.py` | Search strategy and spaces from the budget; analyses results for boundaries and 1-SE picks |
| optuna-study-writer | `gen_optuna_study.py`, `optuna_lint.py` | Generates resumable, prunable Optuna studies for 6 model families; lints Optuna code |
| learning-curve-diagnoser | `diagnose_curve.py`, `gen_learning_curve.py` | Variance/bias/data-limited verdict with a capped power-law extrapolation; curve script generator |
| overfitting-underfitting-diagnoser | `training_history.py`, `validation_curve_report.py` | Training-history verdicts and patience; validation-curve zones and the 1-SE pick |
| shap-value-explainer | `explain_row.py`, `gen_shap_script.py`, `shap_summary.py` | Computes SHAP correctly per model type; global summary with interactions; text waterfalls |
| feature-importance-reporter | `compare_importances.py`, `gen_importance_script.py` | Gain, held-out permutation, grouped permutation and SHAP; explains where methods disagree |
| partial-dependence-plot-builder | `gen_pdp_script.py`, `ice_analysis.py` | PDP/ICE/ALE plots; finds subgroups and interactions hidden by the average |
| lime-explanation-generator | `gen_lime_script.py`, `lime_stability.py` | Repeated-seed LIME runs; stability, fidelity and agreement with SHAP |
| model-card-writer | `card_lint.py`, `model_card.py`, `slice_metrics.py` | Slice metrics with CIs and fairness gaps; writes and lints model cards |
| counterfactual-explanation-generator | `cf_validate.py`, `gen_dice_script.py`, `linear_counterfactual.py` | Exact minimal-cost recourse for linear models; DiCE generator; validates any counterfactuals |
| time-series-forecasting-model-builder | `gen_forecast_script.py`, `ts_backtest.py`, `ts_profile.py` | Series profile, rolling-origin baseline backtest (MASE/RMSSE), leak-free LightGBM forecaster |
| survival-analysis-model-builder | `cox_fit.py`, `gen_survival_script.py`, `km_report.py` | Kaplan-Meier, log-rank, RMST; stdlib Cox with PH test (lifelines-identical); model comparison script |
| recommendation-system-designer | `interaction_profile.py`, `rec_eval.py`, `temporal_split.py` | Interaction profile, temporal splits, top-k evaluation vs popularity with beyond-accuracy metrics |
| collaborative-filtering-implementer | `gen_mf_script.py`, `itemknn.py` | Explainable item-kNN; NumPy ALS, BPR and EASE tuned on a temporal validation split |
| learning-to-rank-model-builder | `gen_ltr_script.py`, `ltr_data_check.py`, `rank_eval.py` | LTR data checks, LightGBM/XGBoost rankers, per-query NDCG/MAP/ERR with significance |
| fraud-detection-model-designer | `fraud_eval.py`, `fraud_velocity_features.py`, `gen_fraud_model_script.py` | Point-in-time velocity features, out-of-time fraud model, alert-budget and cost evaluation |
| uplift-model-builder | `gen_uplift_script.py`, `rct_check.py`, `uplift_eval.py` | RCT checks, S/T/X-learners and class transformation, Qini/AUUC (scikit-uplift-identical) and targeting value |
| language-lesson-plan-builder | `plan_check.py`, `plan_scaffold.py` | Turns a lesson outline into a timed plan; checks aims, timing, teacher talk, feedback and freer practice |
| ppp-lesson-structure-planner | `ppp_check.py`, `ppp_timing.py` | Times PPP stages by level; checks meaning/form/pronunciation, CCQs and practice tasks |
| task-based-language-lesson-designer | `task_check.py` | Checks a task against Ellis's criteria and the Willis TBL cycle |
| communicative-activity-generator | `activity_picker.py` | Filters a 38-activity bank by level, skill, class size, time, prep and online use |
| warm-up-icebreaker-generator | `warmer_picker.py` | Picks warmers by purpose, level, size and time, seeded, without repeats |
| language-lesson-differentiation-planner | `group_learners.py` | Builds mixed-level or same-level groups, spreads L1s, flags outliers |
| esl-worksheet-generator | `gap_fill.py`, `matching.py` | Gap-fills and cloze with word banks and keys; shuffled matching exercises |
| reading-comprehension-text-adapter | `question_mix.py`, `text_level.py` | Estimates a text's CEFR level and what to adapt; checks question staging and balance |
| vocabulary-game-generator | `bingo_cards.py`, `wordsearch.py` | Word searches with solutions; unique bingo cards with a caller list |
| authentic-material-lesson-adapter | `vocab_extract.py` | Pre-teach, gloss and ignore lists, cultural references and reading time for real texts |
| listening-task-builder | `transcript_stats.py` | Speech rate, length and speakers vs level; pause points with timestamps |
| dialogue-for-classroom-writer | `dialogue_check.py` | Checks target phrases, role balance, turn length and natural spoken features |
| cefr-aligned-syllabus-builder | `cefr_hours.py`, `syllabus_check.py` | Guided hours between CEFR levels; syllabus coverage against a core grammar inventory |
| language-course-scope-sequence-planner | `pacing.py`, `sequence_check.py` | Prerequisite order and recycling checks; unit pacing over a term calendar |
| can-do-statement-writer | `cando_lint.py` | Lints can-do statements for observable, contextualised outcomes and mode coverage |
| actfl-proficiency-curriculum-mapper | `level_map.py`, `mode_coverage.py` | ACTFL-CEFR-ILR lookups; three-mode and IPA coverage per unit |
| language-program-review-writer | `program_metrics.py` | Retention, pass rate, level gain, attendance and satisfaction by course |
| language-placement-test-builder | `item_analysis.py`, `placement_cutoffs.py` | Item facility, discrimination, distractors, KR-20; placement with borderline bands |
| speaking-rubric-builder | `rater_agreement.py`, `rubric_check.py` | Checks band descriptors; two-rater agreement and weighted kappa |
| writing-rubric-for-l2-builder | `essay_profile.py`, `writing_score.py` | Profiles learner texts (length, linkers, register); weighted rubric totals and levels |
| language-quiz-generator | `quiz_build.py`, `quiz_check.py` | Seeded quizzes with keys from a tagged bank; item-writing flaw checks |
| formative-assessment-for-language-planner | `exit_ticket_tally.py` | Exit-ticket results to reteach, group or move-on decisions |
| l2-error-correction-strategy-advisor | `error_log.py` | Error log by category and pattern, persistent errors, strategy per category |
| student-writing-feedback-generator | `correction_codes.py` | Summarises correction-coded texts and writes a learner summary |
| pronunciation-feedback-for-teachers-tool | `l1_issues.py`, `minimal_pairs.py` | Likely difficulties for 18 L1s; minimal pairs and listening drills |
| recast-and-prompt-technique-coach | `feedback_coder.py` | Codes teacher feedback moves in a transcript with uptake and repair |
| student-progress-report-writer | `comment_check.py`, `progress_summary.py` | Progress by skill and term; checks report comments for pasted names, vagueness, jargon |
| tefl-celta-prep-tutor | `quiz.py` | CELTA/TESOL practice quizzes with grading and weak domains |
| delta-assignment-planner | `citation_check.py`, `word_count.py` | Section word counts against limits; citation vs reference list checks |
| language-teacher-observation-form-builder | `observation_form.py`, `observation_trends.py` | Observation forms from a criteria bank; rating trends per teacher |
| classroom-management-for-esl-coach | `instruction_check.py`, `seating_plan.py` | Checks task instructions and ICQs; seating plans with constraints |
| online-language-teaching-setup-advisor | `setup_check.py` | Checks bandwidth, audio, platform features, safeguarding and consent |
| language-teacher-cv-writer | `cv_check.py` | Checks ELT CVs for qualifications, evidence, levels, action verbs, regional norms |
| esp-english-course-designer | `needs_analysis.py` | Ranks needs-analysis tasks by frequency x importance x difficulty |
| academic-english-eap-course-planner | `academic_style_check.py`, `ielts_gap.py` | IELTS gap to study hours; academic style check with alternatives |
| young-learner-esl-activity-generator | `yl_lesson_timer.py` | Stir/settle lesson sequence within children's attention span |
| adult-literacy-esl-lesson-builder | `decodable_check.py` | Decodability of a text against taught graphemes and sight words |
| refugee-language-support-planner | `learner_pathways.py` | Learner pathways and class groups from intake data |

See [SITEMAP.md](SITEMAP.md) for every file, or [catalog.json](catalog.json) for a machine-readable index.

## Install

### npx skills (any agent)

Installs straight from the website (it publishes `/.well-known/agent-skills/index.json`), not from GitHub:

```bash
npx skills add https://agenticskills.vector-ai-lab.com --skill sql-query-writer
npx skills add https://agenticskills.vector-ai-lab.com --list
```

### Claude Code plugin marketplace

Each sub-category is a plugin:

```bash
/plugin marketplace add MuhammadHusnainAli/vector-agentic-skills
/plugin install sql-skills@vector-agentic-skills
/plugin install python-skills@vector-agentic-skills
/plugin install rust-skills@vector-agentic-skills
/plugin install excel-skills@vector-agentic-skills
/plugin install classical-ml-skills@vector-agentic-skills
/plugin install language-teaching-skills@vector-agentic-skills
```

### curl

```bash
mkdir -p ~/.claude/skills
curl -fsSL https://agenticskills.vector-ai-lab.com/dl/sql-query-writer.tar.gz | tar -xz -C ~/.claude/skills   # one skill
curl -fsSL https://agenticskills.vector-ai-lab.com/dl/sql-skills.tar.gz | tar -xz -C ~/.claude/skills         # a sub-category
```

### From a clone

```bash
git clone https://github.com/MuhammadHusnainAli/vector-agentic-skills.git
cd vector-agentic-skills

./scripts/install.sh --list                          # see what's available
./scripts/install.sh --all                           # everything -> ~/.claude/skills
./scripts/install.sh --category programming         # one category
./scripts/install.sh --subcategory sql               # one sub-category
./scripts/install.sh sql-query-writer excel-formulas # specific skills
./scripts/install.sh --project /path/to/repo --all   # -> /path/to/repo/.claude/skills
./scripts/install.sh --link --all                    # symlink, so git pull updates them
./scripts/install.sh --dest ~/.other-agent/skills --all
```

Restart your agent session after installing. Skills load automatically when a request matches their `description`. In Claude Code you can also call one directly, e.g. `/sql-query-writer`.

## Layout

```
skills/
└── <category>/                  # e.g. programming
    ├── category.json            # title, description, display order
    ├── README.md                # generated
    └── <subcategory>/           # e.g. sql
        ├── subcategory.json     # title, description, display order
        ├── README.md            # generated
        └── <skill-name>/        # e.g. sql-query-writer
            ├── SKILL.md         # frontmatter + core instructions (< 500 lines)
            ├── references/      # detailed docs, loaded only when needed
            └── scripts/         # tested helper scripts (at least one)
```

`SKILL.md` frontmatter:

```yaml
---
name: sql-query-writer          # lowercase-hyphenated, matches the folder name
description: What the skill does and when to use it (max 1024 chars).
metadata:
  category: programming         # matches the category folder
  subcategory: sql              # matches the sub-category folder
  version: "1.0.0"
---
```

## Website and releases

The site in [`agenticskill-portfolio/`](agenticskill-portfolio/README.md) is built from `skills/` on every push to `main` and deployed to Cloudflare Pages at agenticskills.vector-ai-lab.com by [.github/workflows/deploy.yml](.github/workflows/deploy.yml). Each deploy:

- validates every skill, runs every script's smoke test and regenerates `catalog.json`
- prerenders a page for every category, sub-category, skill, reference file and script
- regenerates `sitemap.xml` and `robots.txt`, so new skills are indexed on the next deploy
- publishes raw files under `/raw/` and tarballs under `/dl/` (per skill, per sub-category, and all)
- deploys to Cloudflare Pages and tags the release, e.g. `v0.1.7`

**Versions:** the patch number goes up by one on every deploy. The major and minor numbers come from the [`VERSION`](VERSION) file. Change it by hand (for example `0.1` → `1.0`) and the next deploy is `v1.0.0`.

Pull requests run the same checks without deploying ([validate.yml](.github/workflows/validate.yml)).

## Contributing

1. Pick a category and sub-category under `skills/`, or create new ones with a `category.json` / `subcategory.json`:
   ```json
   { "title": "Python", "description": "Skills for writing, testing and packaging Python.", "order": 2 }
   ```
2. Copy [templates/skill](templates/skill/SKILL.md) to `skills/<category>/<subcategory>/<skill-name>/` and fill it in. Keep `SKILL.md` under 500 lines and move long material into `references/`.
3. Add helper scripts in `scripts/`, written in the skill's own language (Python skills ship `.py`, Rust skills ship std-only `.rs` files compiled with `rustc`), standard library only, small and focused, each with `--help`. Add test cases for them in [tests/cases/](tests/cases/) (one file per sub-category).
4. Validate, test and regenerate the indexes:
   ```bash
   pip install pyyaml
   python scripts/validate_skills.py
   bash tests/run_tests.sh          # needs rustc for Rust scripts; -k <text> to filter
   python scripts/build_catalog.py
   ```
5. Test the skill with at least one agent, then open a pull request.

`build_catalog.py` regenerates `catalog.json`, `SITEMAP.md`, the category and sub-category READMEs and `.claude-plugin/marketplace.json`, so don't edit those by hand. CI fails if they are out of date.

## Community

- **Discussions**: [GitHub Discussions](https://github.com/MuhammadHusnainAli/vector-agentic-skills/discussions) for questions and ideas
- **Issues**: [GitHub Issues](https://github.com/MuhammadHusnainAli/vector-agentic-skills/issues) for bugs and skill requests
- **Pull Requests**: [contribute directly](https://github.com/MuhammadHusnainAli/vector-agentic-skills/pulls)

Built by [vector-ai-lab.com](https://vector-ai-lab.com).
