import "server-only";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { parse as parseYaml } from "yaml";
import { REPO_ROOT } from "./site";

const SKILLS_DIR = path.join(REPO_ROOT, "skills");

export type SkillFile = {
  /** Path inside the skill folder, e.g. "references/examples.md". */
  file: string;
  /** URL segment, e.g. "examples" or "check_sql.py". */
  slug: string;
  kind: "reference" | "script";
  title: string;
  content: string;
  lines: number;
};

export type Skill = {
  name: string;
  title: string;
  description: string;
  /** Description without the "Use when ..." trigger sentence. */
  summary: string;
  category: string;
  subcategory: string;
  version: string;
  /** Repo-relative folder, e.g. "skills/programming/sql-query-writer". */
  dir: string;
  body: string;
  lines: number;
  headings: string[];
  files: SkillFile[];
  updated: string;
};

export type Subcategory = {
  slug: string;
  category: string;
  title: string;
  description: string;
  order: number;
  skills: Skill[];
};

export type Category = {
  slug: string;
  title: string;
  description: string;
  order: number;
  subcategories: Subcategory[];
  /** All skills in the category, across sub-categories. */
  skills: Skill[];
};

function splitFrontmatter(text: string): { meta: Record<string, unknown>; body: string } {
  const m = text.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  if (!m) return { meta: {}, body: text };
  return { meta: (parseYaml(m[1]) as Record<string, unknown>) ?? {}, body: m[2] };
}

function headingsOf(md: string): string[] {
  const out: string[] = [];
  let inFence = false;
  for (const line of md.split("\n")) {
    if (line.startsWith("```")) inFence = !inFence;
    else if (!inFence) {
      const h = line.match(/^#{2,3}\s+(.+)/);
      if (h) out.push(h[1].trim());
    }
  }
  return out;
}

function lastModified(dir: string): string {
  try {
    const out = execFileSync("git", ["log", "-1", "--format=%cI", "--", dir], {
      cwd: REPO_ROOT,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
    if (out) return out;
  } catch {
    // not a git checkout; fall through to mtime
  }
  return fs.statSync(dir).mtime.toISOString();
}

function walk(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    if (e.name === "__pycache__" || e.name.startsWith(".")) return [];
    const p = path.join(dir, e.name);
    return e.isDirectory() ? walk(p) : [p];
  });
}

function loadSkill(category: string, subcategory: string, skillDir: string): Skill {
  const { meta, body } = splitFrontmatter(fs.readFileSync(path.join(skillDir, "SKILL.md"), "utf8"));
  const name = String(meta.name ?? path.basename(skillDir));
  const description = String(meta.description ?? "");
  const metadata = (meta.metadata ?? {}) as Record<string, unknown>;

  const files: SkillFile[] = walk(skillDir)
    .map((p) => path.relative(skillDir, p).split(path.sep).join("/"))
    .filter((f) => f !== "SKILL.md")
    .sort()
    .map((file) => {
      const content = fs.readFileSync(path.join(skillDir, file), "utf8");
      const base = path.basename(file);
      const isMd = base.endsWith(".md");
      return {
        file,
        slug: isMd ? base.slice(0, -3).toLowerCase() : base,
        kind: file.startsWith("scripts/") ? "script" : "reference",
        title: (isMd && content.match(/^# (.+)$/m)?.[1]) || base,
        content,
        lines: content.split("\n").length,
      };
    });

  return {
    name,
    title: body.match(/^# (.+)$/m)?.[1]?.trim() ?? name,
    description,
    summary: description.split(/\.\s+Use\s/)[0].replace(/\.$/, "") + ".",
    category,
    subcategory,
    version: String(metadata.version ?? "1.0.0"),
    dir: path.relative(REPO_ROOT, skillDir),
    body,
    lines: body.split("\n").length,
    headings: headingsOf(body),
    files,
    updated: lastModified(skillDir),
  };
}

function readInfo(file: string): { title?: string; description?: string; order?: number } {
  return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : {};
}

function dirs(parent: string) {
  return fs.readdirSync(parent, { withFileTypes: true }).filter((d) => d.isDirectory());
}

let cache: Category[] | null = null;

/**
 * Categories -> sub-categories -> skills, read from ../skills at build time.
 * Layout: skills/<category>/<subcategory>/<skill>/SKILL.md
 */
export function getCategories(): Category[] {
  if (cache) return cache;
  cache = dirs(SKILLS_DIR)
    .map((c) => {
      const catDir = path.join(SKILLS_DIR, c.name);
      const info = readInfo(path.join(catDir, "category.json"));
      const subcategories: Subcategory[] = dirs(catDir)
        .map((s) => {
          const subDir = path.join(catDir, s.name);
          const subInfo = readInfo(path.join(subDir, "subcategory.json"));
          const skills = dirs(subDir)
            .filter((k) => fs.existsSync(path.join(subDir, k.name, "SKILL.md")))
            .map((k) => loadSkill(c.name, s.name, path.join(subDir, k.name)))
            .sort((a, b) => a.name.localeCompare(b.name));
          return {
            slug: s.name,
            category: c.name,
            title: subInfo.title ?? s.name,
            description: subInfo.description ?? "",
            order: subInfo.order ?? 99,
            skills,
          };
        })
        .filter((s) => s.skills.length > 0)
        .sort((a, b) => a.order - b.order || a.title.localeCompare(b.title));
      return {
        slug: c.name,
        title: info.title ?? c.name,
        description: info.description ?? "",
        order: info.order ?? 99,
        subcategories,
        skills: subcategories.flatMap((s) => s.skills),
      };
    })
    .filter((c) => c.skills.length > 0)
    .sort((a, b) => a.order - b.order);
  return cache;
}

export function getSubcategories(): Subcategory[] {
  return getCategories().flatMap((c) => c.subcategories);
}

export function getSubcategory(category: string, slug: string): Subcategory | undefined {
  return getCategory(category)?.subcategories.find((s) => s.slug === slug);
}

export function getSkills(): Skill[] {
  return getCategories().flatMap((c) => c.skills);
}

export function getSkill(name: string): Skill | undefined {
  return getSkills().find((s) => s.name === name);
}

export function getCategory(slug: string): Category | undefined {
  return getCategories().find((c) => c.slug === slug);
}

export function recentSkills(n: number): Skill[] {
  return [...getSkills()].sort((a, b) => b.updated.localeCompare(a.updated) || a.name.localeCompare(b.name)).slice(0, n);
}

export function stats() {
  const skills = getSkills();
  return {
    skills: skills.length,
    categories: getCategories().length,
    subcategories: getSubcategories().length,
    references: skills.reduce((n, s) => n + s.files.filter((f) => f.kind === "reference").length, 0),
    scripts: skills.reduce((n, s) => n + s.files.filter((f) => f.kind === "script").length, 0),
    lines: skills.reduce((n, s) => n + s.lines + s.files.reduce((m, f) => m + f.lines, 0), 0),
  };
}

/** Compact index shipped to the client for search. */
export type SearchEntry = {
  name: string;
  title: string;
  summary: string;
  category: string;
  categoryTitle: string;
  subcategory: string;
  subcategoryTitle: string;
  keywords: string;
  updated: string;
  files: number;
  scripts: number;
};

export function searchIndex(): SearchEntry[] {
  return getCategories().flatMap((c) =>
    c.subcategories.flatMap((sub) =>
      sub.skills.map((s) => ({
      name: s.name,
      title: s.title,
      summary: s.summary,
      category: c.slug,
      categoryTitle: c.title,
      subcategory: sub.slug,
      subcategoryTitle: sub.title,
      keywords: [s.description, ...s.headings, ...s.files.map((f) => f.title)].join(" ").toLowerCase(),
      updated: s.updated,
      files: s.files.filter((f) => f.kind === "reference").length,
      scripts: s.files.filter((f) => f.kind === "script").length,
      })),
    ),
  );
}
