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

Every skill ships at least one tested helper script (standard library only,
`--help`, `--json` where useful, meaningful exit codes):

```bash
python scripts/my_script.py --help
```

Add a test case for it in scripts/test_skill_scripts.py.

## Additional Resources

| File | Content |
|------|---------|
| [examples.md](references/examples.md) | Worked examples |
