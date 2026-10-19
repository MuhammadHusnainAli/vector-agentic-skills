#!/usr/bin/env python3
"""Validate every skill in skills/<category>/<skill>/SKILL.md.

Checks the Agent Skills format used by Claude Code and other agents:
  - SKILL.md starts with YAML frontmatter containing `name` and `description`
  - `name` is lowercase-hyphenated, <= 64 chars, matches its folder, and is unique
  - `description` is non-empty and <= 1024 chars
  - `metadata.category` matches the category folder, which has a category.json
  - every relative Markdown link inside the skill resolves to a file

Usage:
    python scripts/validate_skills.py

Requires: PyYAML (pip install pyyaml). Exit code 1 if any check fails.
"""

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(#[^)]*)?\)")
MAX_SKILL_LINES = 500


def parse_skill(path):
    """Return (frontmatter dict, body str) for a SKILL.md file."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        raise ValueError("missing YAML frontmatter (--- ... ---) at top of file")
    meta = yaml.safe_load(m.group(1)) or {}
    if not isinstance(meta, dict):
        raise ValueError("frontmatter is not a mapping")
    return meta, m.group(2)


def load_categories():
    cats = {}
    for cat_dir in sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir()):
        info_path = cat_dir / "category.json"
        info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else None
        cats[cat_dir.name] = info
    return cats


def load_skills():
    """Yield (category, skill_dir, meta, body) for every skill, sorted by path."""
    for skill_md in sorted(SKILLS_DIR.glob("*/*/SKILL.md")):
        meta, body = parse_skill(skill_md)
        yield skill_md.parent.parent.name, skill_md.parent, meta, body


def validate():
    errors, warnings = [], []
    categories = load_categories()
    for cat, info in categories.items():
        if info is None:
            errors.append(f"skills/{cat}: missing category.json")
        elif not {"title", "description"} <= info.keys():
            errors.append(f"skills/{cat}/category.json: needs 'title' and 'description'")

    seen = {}
    for skill_md in sorted(SKILLS_DIR.glob("*/*/SKILL.md")):
        rel = skill_md.relative_to(ROOT)
        cat, folder = skill_md.parent.parent.name, skill_md.parent.name
        try:
            meta, body = parse_skill(skill_md)
        except (ValueError, yaml.YAMLError) as e:
            errors.append(f"{rel}: {e}")
            continue

        name = meta.get("name")
        desc = meta.get("description")
        if not isinstance(name, str) or not NAME_RE.match(name) or len(name) > 64:
            errors.append(f"{rel}: name {name!r} must be lowercase letters/digits/hyphens, <= 64 chars")
        elif name != folder:
            errors.append(f"{rel}: name {name!r} must match folder name {folder!r}")
        elif name in seen:
            errors.append(f"{rel}: duplicate skill name {name!r} (also in {seen[name]})")
        else:
            seen[name] = rel
        if not isinstance(desc, str) or not desc.strip():
            errors.append(f"{rel}: description is required")
        elif len(desc) > 1024:
            errors.append(f"{rel}: description is {len(desc)} chars (max 1024)")

        meta_cat = (meta.get("metadata") or {}).get("category")
        if meta_cat != cat:
            errors.append(f"{rel}: metadata.category {meta_cat!r} must be {cat!r}")

        lines = body.count("\n") + 1
        if lines > MAX_SKILL_LINES:
            warnings.append(f"{rel}: {lines} lines; consider moving detail into references/ (< {MAX_SKILL_LINES} recommended)")

        for md in skill_md.parent.rglob("*.md"):
            for target, _ in LINK_RE.findall(md.read_text(encoding="utf-8")):
                if re.match(r"^[a-z]+:", target):
                    continue
                if not (md.parent / target).resolve().exists():
                    errors.append(f"{md.relative_to(ROOT)}: broken link -> {target}")

    for skill_dir in sorted(p for p in SKILLS_DIR.glob("*/*") if p.is_dir()):
        if not (skill_dir / "SKILL.md").exists():
            errors.append(f"{skill_dir.relative_to(ROOT)}: folder has no SKILL.md")
    return errors, warnings, len(seen)


def main():
    errors, warnings, count = validate()
    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error:   {e}")
    print(f"\n{count} skills checked, {len(errors)} errors, {len(warnings)} warnings")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
