---
name: my-skill-name
description: One or two sentences on what the skill does, then "Use when ..." listing the requests, keywords and file types that should trigger it. Max 1024 characters. Quote the whole value if it contains " #".
metadata:
  category: programming
  subcategory: sql
  version: "1.0.0"
---

# My Skill Title

One-paragraph summary of what this skill helps the agent do.

## Trigger Conditions

Activate this skill when the user:
- ...

## Workflow

```
1. UNDERSTAND -> ...
2. DO         -> ...
3. VALIDATE   -> run scripts/my_script.py
```

## Guidelines

Core rules, patterns and checklists. Keep this file under 500 lines and move
long material into references/.

## Output Format

What the answer should look like.

## Scripts

Every skill ships at least one tested helper script, written in the skill's own
language (Python skills: `.py`; Rust skills: std-only `.rs` compiled with
`rustc -O scripts/my_tool.rs -o /tmp/my_tool`). Keep each script small and
focused; split work across several scripts rather than one big file. Standard
library only, `--help`, `--json` where useful, meaningful exit codes:

```bash
python scripts/my_script.py --help
```

Add test cases for it in tests/cases/<subcategory>.sh and run tests/run_tests.sh.

## Additional Resources

| File | Content |
|------|---------|
| [examples.md](references/examples.md) | Worked examples |
