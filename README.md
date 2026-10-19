# Vector Agentic Skills

**Ready-to-install Agent Skills for Claude Code and other AI agents, organised by category.**

Each skill is a folder with a `SKILL.md` (YAML frontmatter + instructions), plus optional `references/` for detailed docs and `scripts/` for helper tools the agent can run. This is the [Agent Skills](https://docs.claude.com/en/docs/claude-code/skills) format, so the folders work as-is in Claude Code, the Claude apps, the Claude Agent SDK and any agent that loads `SKILL.md` folders.

## Categories

| Category | Skills | What's inside |
|----------|--------|---------------|
| [Programming](skills/programming/README.md) | 12 | SQL: writing, syntax checking, explaining, optimising, debugging, window functions, performance tuning, analytics, dialect translation, data quality, reporting |
| [Productivity](skills/productivity/README.md) | 3 | Excel: formulas, advanced formulas (LAMBDA, LET, dynamic arrays, regex), workbook fundamentals |

See [SITEMAP.md](SITEMAP.md) for every skill and file, or [catalog.json](catalog.json) for a machine-readable index.

## Install

### Claude Code plugin marketplace

```bash
/plugin marketplace add MuhammadHusnainAli/vector-agentic-skills
/plugin install programming-skills@vector-agentic-skills
/plugin install productivity-skills@vector-agentic-skills
```

### Copy skills manually

```bash
git clone https://github.com/MuhammadHusnainAli/vector-agentic-skills.git
cd vector-agentic-skills

./scripts/install.sh --list                          # see what's available
./scripts/install.sh --all                           # everything -> ~/.claude/skills
./scripts/install.sh --category programming          # one category
./scripts/install.sh sql-query-writer excel-formulas # specific skills
./scripts/install.sh --project /path/to/repo --all   # -> /path/to/repo/.claude/skills
./scripts/install.sh --link --all                    # symlink, so git pull updates them
./scripts/install.sh --dest ~/.other-agent/skills --all
```

Restart your agent session after installing. Skills load automatically when a request matches their `description`; in Claude Code you can also call one directly, e.g. `/sql-query-writer`.

## Skill layout

```
skills/
└── <category>/
    ├── category.json            # title, description, display order
    ├── README.md                # generated category index
    └── <skill-name>/
        ├── SKILL.md             # frontmatter + core instructions (required)
        ├── references/          # detailed docs, loaded only when needed
        └── scripts/             # helper scripts the agent can run
```

`SKILL.md` frontmatter:

```yaml
---
name: sql-query-writer          # lowercase-hyphenated, matches the folder name
description: What the skill does and when to use it (max 1024 chars).
metadata:
  category: programming         # matches the category folder
  version: "1.0.0"
---
```

### Bundled scripts

| Skill | Script | Purpose |
|-------|--------|---------|
| sql-syntax-checker | `scripts/check_sql.py` | Structural SQL checks, plus full grammar parsing when `sqlglot` is installed |
| sql-dialect-translator | `scripts/translate_sql.py` | Translate SQL between dialects with `sqlglot` |
| excel-formulas | `scripts/check_formula.py` | Lint formulas: parentheses, strings, unknown functions, volatile functions, lookup pitfalls |
| excel-advanced-formulas | `scripts/check_compat.py` | Report the minimum Excel version a formula needs |

## Contributing

1. Pick a category under `skills/`, or create a new one with a `category.json`:
   ```json
   { "title": "Design", "description": "Skills for UI, UX and visual design.", "order": 3 }
   ```
2. Copy [templates/skill](templates/skill/SKILL.md) to `skills/<category>/<skill-name>/` and fill it in. Keep `SKILL.md` under ~500 lines and move long material into `references/`.
3. Validate and regenerate the indexes:
   ```bash
   pip install pyyaml
   python scripts/validate_skills.py
   python scripts/build_catalog.py
   ```
4. Test the skill with at least one agent, then open a pull request.

`build_catalog.py` regenerates `catalog.json`, `SITEMAP.md`, `sitemap.xml`, the category READMEs and `.claude-plugin/marketplace.json`, so don't edit those by hand. CI fails if they are out of date. To point the sitemap at your website, set `SITE_URL=https://your-site.com` when you run it.

## Community

- **Discussions**: [GitHub Discussions](https://github.com/MuhammadHusnainAli/vector-agentic-skills/discussions) for questions and ideas
- **Issues**: [GitHub Issues](https://github.com/MuhammadHusnainAli/vector-agentic-skills/issues) for bugs and skill requests
- **Pull Requests**: [contribute directly](https://github.com/MuhammadHusnainAli/vector-agentic-skills/pulls)
