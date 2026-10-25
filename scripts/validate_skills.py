#!/usr/bin/env python3
"""Validate every skill in skills/<category>/<subcategory>/<skill>/SKILL.md.

Checks the Agent Skills format used by Claude Code and other agents, plus this
repo's quality bar:
  - every category has category.json and every sub-category has subcategory.json
    (each with "title" and "description"); optional sub-category "groups" list
    every skill exactly once
  - SKILL.md starts with YAML frontmatter containing `name` and `description`
  - `name` is lowercase-hyphenated, <= 64 chars, matches its folder, and is unique
  - `description` is non-empty and <= 1024 chars
  - `metadata.category` / `metadata.subcategory` match the folders
  - each skill ships at least one script in scripts/ and every script parses
  - every relative Markdown link inside the skill resolves to a file
  - SKILL.md stays under 500 lines (warning) and has references/ (warning)

Usage:
    python scripts/validate_skills.py

Requires: PyYAML (pip install pyyaml). Exit code 1 if any check fails.
"""

import ast
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(#[^)]*)?\)")
# Fenced blocks and inline code spans, removed before link checking so code
# such as `class Store[T](Protocol)` isn't read as a Markdown link.
CODE_RE = re.compile(r"^(```|~~~).*?^\1[ \t]*$|`[^`\n]+`", re.M | re.S)
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


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def load_categories():
    """{category: {"info": dict|None, "subcategories": {sub: dict|None}}} in folder order."""
    cats = {}
    for cat_dir in sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir()):
        subs = {s.name: read_json(s / "subcategory.json") for s in sorted(cat_dir.iterdir()) if s.is_dir()}
        cats[cat_dir.name] = {"info": read_json(cat_dir / "category.json"), "subcategories": subs}
    return cats


def load_skills():
    """Yield (category, subcategory, skill_dir, meta, body) for every skill, sorted by path."""
    for skill_md in sorted(SKILLS_DIR.glob("*/*/*/SKILL.md")):
        meta, body = parse_skill(skill_md)
        yield skill_md.parents[2].name, skill_md.parents[1].name, skill_md.parent, meta, body


def check_groups(sub_rel, groups):
    """Optional "groups" in subcategory.json must list every skill folder exactly once."""
    where = f"{sub_rel}/subcategory.json"
    if not isinstance(groups, list) or not all(
            isinstance(g, dict) and isinstance(g.get("title"), str) and isinstance(g.get("skills"), list) for g in groups):
        return [f"{where}: 'groups' must be a list of {{\"title\": str, \"skills\": [str]}}"]
    listed = [n for g in groups for n in g["skills"]]
    folders = {p.parent.name for p in (ROOT / sub_rel).glob("*/SKILL.md")}
    errors = [f"{where}: skill {n!r} is listed in more than one group" for n in sorted({n for n in listed if listed.count(n) > 1})]
    errors += [f"{where}: group lists {n!r} but there is no such skill folder" for n in sorted(set(listed) - folders)]
    errors += [f"{where}: skill {n!r} is not in any group" for n in sorted(folders - set(listed))]
    return errors


def validate():
    errors, warnings = [], []
    for cat, data in load_categories().items():
        if not data["info"] or not {"title", "description"} <= data["info"].keys():
            errors.append(f"skills/{cat}/category.json: missing, or lacks 'title' and 'description'")
        for sub, info in data["subcategories"].items():
            if not info or not {"title", "description"} <= info.keys():
                errors.append(f"skills/{cat}/{sub}/subcategory.json: missing, or lacks 'title' and 'description'")
            elif "groups" in info:
                errors += check_groups(f"skills/{cat}/{sub}", info["groups"])

    seen = {}
    for skill_md in sorted(SKILLS_DIR.glob("*/*/*/SKILL.md")):
        rel = skill_md.relative_to(ROOT)
        skill_dir = skill_md.parent
        cat, sub, folder = skill_md.parents[2].name, skill_md.parents[1].name, skill_dir.name
        try:
            meta, body = parse_skill(skill_md)
        except (ValueError, yaml.YAMLError) as e:
            errors.append(f"{rel}: {e}")
            continue

        name, desc = meta.get("name"), meta.get("description")
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

        md = meta.get("metadata") or {}
        if md.get("category") != cat:
            errors.append(f"{rel}: metadata.category {md.get('category')!r} must be {cat!r}")
        if md.get("subcategory") != sub:
            errors.append(f"{rel}: metadata.subcategory {md.get('subcategory')!r} must be {sub!r}")

        scripts = sorted((skill_dir / "scripts").glob("*")) if (skill_dir / "scripts").is_dir() else []
        scripts = [s for s in scripts if s.is_file() and s.suffix in (".py", ".sh", ".js", ".mjs", ".rs")]
        if not scripts:
            errors.append(f"{rel}: skill must ship at least one helper script in scripts/")
        for s in scripts:
            if s.suffix == ".py":
                try:
                    ast.parse(s.read_text(encoding="utf-8"), filename=str(s))
                except SyntaxError as e:
                    errors.append(f"{s.relative_to(ROOT)}: syntax error: {e}")
            if f"scripts/{s.name}" not in body:
                warnings.append(f"{rel}: scripts/{s.name} is not documented in SKILL.md")
        if not (skill_dir / "references").is_dir():
            warnings.append(f"{rel}: no references/ folder")

        lines = body.count("\n") + 1
        if lines > MAX_SKILL_LINES:
            warnings.append(f"{rel}: {lines} lines; move detail into references/ (< {MAX_SKILL_LINES} recommended)")

        for doc in skill_dir.rglob("*.md"):
            for target, _ in LINK_RE.findall(CODE_RE.sub("", doc.read_text(encoding="utf-8"))):
                if re.match(r"^[a-z]+:", target):
                    continue
                if not (doc.parent / target).resolve().exists():
                    errors.append(f"{doc.relative_to(ROOT)}: broken link -> {target}")

    for d in sorted(p for p in SKILLS_DIR.glob("*/*/*") if p.is_dir()):
        if not (d / "SKILL.md").exists():
            errors.append(f"{d.relative_to(ROOT)}: folder has no SKILL.md")
    for stray in sorted(SKILLS_DIR.glob("*/*/SKILL.md")):
        errors.append(f"{stray.relative_to(ROOT)}: skills must live in skills/<category>/<subcategory>/<skill>/")
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
