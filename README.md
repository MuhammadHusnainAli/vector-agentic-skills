# Vector Agentic Skills

**Ready-to-install Agent Skills for Claude Code and other AI agents, organised by category and sub-category.**

Each skill is a folder with a `SKILL.md` (YAML frontmatter + instructions), `references/` for detailed docs, and `scripts/` with tested helper tools the agent can run. This is the [Agent Skills](https://docs.claude.com/en/docs/claude-code/skills) format, so the folders work as-is in Claude Code, the Claude apps, the Claude Agent SDK and any agent that loads `SKILL.md` folders.

**Website:** [agenticskills.vector-ai-lab.com](https://agenticskills.vector-ai-lab.com): search, read and install every skill.

## Skills

| Category | Sub-category | Skills | What's inside |
|----------|--------------|--------|---------------|
| [Programming](skills/programming/README.md) | [SQL](skills/programming/sql/README.md) | 11 | Writing, syntax checking, explaining, optimising, performance tuning, debugging, window functions, analytics, reporting, data quality, dialect translation |
| [Programming](skills/programming/README.md) | [Python](skills/programming/python/README.md) | 7 | Idiomatic code review, comprehensions, type hints, dataclasses, exception design, context managers, beginner tutoring (for AI engineers) |
| [Productivity](skills/productivity/README.md) | [Excel](skills/productivity/excel/README.md) | 3 | Formulas, advanced formulas (LAMBDA, LET, dynamic arrays, regex), workbook fundamentals |

Every skill ships at least one helper script, smoke-tested in CI:

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
| excel-formulas | `check_formula.py` | Lints formulas: parentheses, strings, unknown and volatile functions |
| excel-advanced-formulas | `check_compat.py` | Reports the minimum Excel version a formula needs |
| excel-fundamentals | `inspect_workbook.py` | Reports an .xlsx's sheets, tables, names, validation and links |

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
/plugin install excel-skills@vector-agentic-skills
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
3. Add at least one helper script in `scripts/` (standard library only, with `--help`) and a test case for it in [scripts/test_skill_scripts.py](scripts/test_skill_scripts.py).
4. Validate, test and regenerate the indexes:
   ```bash
   pip install pyyaml
   python scripts/validate_skills.py
   python scripts/test_skill_scripts.py
   python scripts/build_catalog.py
   ```
5. Test the skill with at least one agent, then open a pull request.

`build_catalog.py` regenerates `catalog.json`, `SITEMAP.md`, the category and sub-category READMEs and `.claude-plugin/marketplace.json`, so don't edit those by hand. CI fails if they are out of date.

## Community

- **Discussions**: [GitHub Discussions](https://github.com/MuhammadHusnainAli/vector-agentic-skills/discussions) for questions and ideas
- **Issues**: [GitHub Issues](https://github.com/MuhammadHusnainAli/vector-agentic-skills/issues) for bugs and skill requests
- **Pull Requests**: [contribute directly](https://github.com/MuhammadHusnainAli/vector-agentic-skills/pulls)

Built by [vector-ai-lab.com](https://vector-ai-lab.com).
