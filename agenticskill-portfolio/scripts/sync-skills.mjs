#!/usr/bin/env node
// Copy the repo's skills into public/ so the site serves them directly.
//
//   public/raw/skills/<category>/<sub>/<skill>/...    raw files (SKILL.md, references, scripts)
//   public/dl/<skill>.tar.gz                          one skill, extracts to <skill>/
//   public/dl/<subcategory>-skills.tar.gz             one sub-category, flat
//   public/dl/all-skills.tar.gz                       every skill, flat
//   public/catalog.json                               machine-readable index
//
// Agent Skills well-known discovery, so `npx skills add <site> --skill <name>`
// installs from this website instead of GitHub:
//   public/.well-known/agent-skills/index.json        v0.2.0 index (archive + sha256 digest)
//   public/.well-known/agent-skills/<skill>.tar.gz    SKILL.md at the archive root
//   public/.well-known/skills/index.json              legacy index (file list) for older CLIs
//   public/.well-known/skills/<skill>/...             legacy raw files
//
// Runs automatically before `npm run dev` and `npm run build`.

import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parse as parseYaml } from "yaml";

const APP = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ROOT = path.resolve(APP, "..");
const SKILLS = path.join(ROOT, "skills");
const PUBLIC = path.join(APP, "public");
const RAW = path.join(PUBLIC, "raw", "skills");
const DL = path.join(PUBLIC, "dl");
const WK = path.join(PUBLIC, ".well-known");
const WK_V2 = path.join(WK, "agent-skills");
const WK_V1 = path.join(WK, "skills");
const DISCOVERY_SCHEMA = "https://schemas.agentskills.io/discovery/0.2.0/schema.json";

for (const dir of [path.join(PUBLIC, "raw"), DL, WK]) fs.rmSync(dir, { recursive: true, force: true });
for (const dir of [DL, WK_V2, WK_V1]) fs.mkdirSync(dir, { recursive: true });

const skip = (src) => !src.includes("__pycache__") && !path.basename(src).startsWith(".");
fs.cpSync(SKILLS, RAW, { recursive: true, filter: skip });

const subdirs = (p) => fs.readdirSync(p).filter((n) => fs.statSync(path.join(p, n)).isDirectory()).sort();
const filesIn = (dir, base = dir) =>
  fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    if (!skip(p)) return [];
    return e.isDirectory() ? filesIn(p, base) : [path.relative(base, p).split(path.sep).join("/")];
  });
const frontmatter = (file) => {
  const m = fs.readFileSync(file, "utf8").match(/^---\n([\s\S]*?)\n---/);
  return m ? parseYaml(m[1]) ?? {} : {};
};
const tar = (args) => execFileSync("tar", ["--exclude=__pycache__", "--format=ustar", ...args]);

// Layout: skills/<category>/<subcategory>/<skill>/SKILL.md
const tarArgs = [];
const indexV2 = [];
const indexV1 = [];
for (const category of subdirs(SKILLS)) {
  for (const sub of subdirs(path.join(SKILLS, category))) {
    const subDir = path.join(SKILLS, category, sub);
    const skills = subdirs(subDir).filter((s) => fs.existsSync(path.join(subDir, s, "SKILL.md")));
    for (const skill of skills) {
      const skillDir = path.join(subDir, skill);
      const files = filesIn(skillDir).sort((a, b) => (a === "SKILL.md" ? -1 : b === "SKILL.md" ? 1 : a.localeCompare(b)));
      const { description = "" } = frontmatter(path.join(skillDir, "SKILL.md"));

      tar(["-czf", path.join(DL, `${skill}.tar.gz`), "-C", subDir, skill]);

      // Well-known v0.2.0: archive with SKILL.md at its root, pinned by digest.
      const archive = path.join(WK_V2, `${skill}.tar.gz`);
      tar(["-czf", archive, "-C", skillDir, ...files]);
      const digest = createHash("sha256").update(fs.readFileSync(archive)).digest("hex");
      indexV2.push({ name: skill, type: "archive", description, url: `${skill}.tar.gz`, digest: `sha256:${digest}` });

      // Legacy well-known: plain files listed in the index.
      fs.cpSync(skillDir, path.join(WK_V1, skill), { recursive: true, filter: skip });
      indexV1.push({ name: skill, description, files });
    }
    if (skills.length) {
      tar(["-czf", path.join(DL, `${sub}-skills.tar.gz`), "-C", subDir, ...skills]);
      tarArgs.push("-C", subDir, ...skills);
    }
  }
}
tar(["-czf", path.join(DL, "all-skills.tar.gz"), ...tarArgs]);

fs.writeFileSync(path.join(WK_V2, "index.json"), JSON.stringify({ $schema: DISCOVERY_SCHEMA, skills: indexV2 }, null, 2) + "\n");
fs.writeFileSync(path.join(WK_V1, "index.json"), JSON.stringify({ skills: indexV1 }, null, 2) + "\n");

const catalog = path.join(ROOT, "catalog.json");
if (fs.existsSync(catalog)) fs.copyFileSync(catalog, path.join(PUBLIC, "catalog.json"));

console.log(`sync-skills: ${indexV2.length} skills -> public/raw, public/dl, public/.well-known`);
