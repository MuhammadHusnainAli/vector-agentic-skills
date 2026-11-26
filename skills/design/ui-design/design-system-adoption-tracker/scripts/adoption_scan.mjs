#!/usr/bin/env node
// Measure design-system adoption per app or team folder, and the change since a previous snapshot.
//
// For each group (folders at --depth under ROOT, e.g. apps/web, apps/admin):
//   ds         JSX/template elements whose component is imported from a design-system package (--ds)
//   local      PascalCase elements imported from relative paths or aliases (./, ../, @/, ~/, src/) or defined in place
//   thirdParty PascalCase elements imported from other packages (@mui/material, antd ...)
//   rawHtml    raw <button> <input> <select> <textarea> <dialog> <table> the design system replaces
//   adoption   ds / (ds + local + thirdParty + rawHtml)
//   tokens     var(--...) references;  raw  hard-coded colours (hex, rgb(), hsl())
//   version    design-system version in the nearest package.json
//
// Usage:
//   node adoption_scan.mjs ROOT --ds @acme/ui [--depth 2] [--min 60] [--latest 3.2.0] [--baseline prev.json] [--json | --csv]
// Exit codes: 0 every group meets --min (or no --min), 1 a group is below --min, 2 bad arguments or nothing to scan.

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, extname, join, relative, sep } from "node:path";

const HELP = `usage: node adoption_scan.mjs ROOT --ds PACKAGE [--ds ...] [--depth N] [--min PCT] [--latest X.Y.Z]
                          [--baseline previous.json] [--json | --csv]
Design-system adoption per app/team folder: DS vs local, third-party and raw HTML elements,
token vs hard-coded colours, DS version lag, and change against a baseline snapshot.`;

const argv = process.argv.slice(2);
if (!argv.length || argv.includes("-h") || argv.includes("--help")) { console.log(HELP); process.exit(argv.length ? 0 : 2); }
let root = null, depth = 1, min = null, latest = null, baselinePath = null, out = "text";
const ds = [];
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === "--ds") ds.push(argv[++i]);
  else if (a === "--depth") depth = Number(argv[++i]);
  else if (a === "--min") min = Number(argv[++i]);
  else if (a === "--latest") latest = argv[++i];
  else if (a === "--baseline") baselinePath = argv[++i];
  else if (a === "--json") out = "json";
  else if (a === "--csv") out = "csv";
  else if (a.startsWith("--")) { console.error(`error: unknown option ${a}`); process.exit(2); }
  else root = a;
}
const fail = (m) => { console.error(`error: ${m}`); process.exit(2); };
if (!root) fail("give the root folder to scan");
if (!ds.length) fail("name the design-system package with --ds (e.g. --ds @acme/ui)");
if (!Number.isInteger(depth) || depth < 1) fail("--depth must be a positive integer");
if (min !== null && !(min >= 0 && min <= 100)) fail("--min must be a percentage 0-100");
if (!existsSync(root) || !statSync(root).isDirectory()) fail(`${root} is not a directory`);
let baseline = null;
if (baselinePath) {
  try { baseline = JSON.parse(readFileSync(baselinePath, "utf8")); } catch (e) { fail(`baseline ${baselinePath}: ${e.message}`); }
}

const CODE = new Set([".jsx", ".tsx", ".js", ".ts", ".vue", ".svelte"]);
const STYLE = new Set([".css", ".scss", ".less"]);
const SKIP = new Set(["node_modules", ".git", "dist", "build", ".next", "out", "coverage", "storybook-static", ".turbo"]);
const TEST = /\.(test|spec|stories|story)\.[jt]sx?$|__tests__|__mocks__/;
const RAW_TAGS = ["button", "input", "select", "textarea", "dialog", "table"];

function walk(dir, files = []) {
  for (const name of readdirSync(dir)) {
    if (SKIP.has(name) || name.startsWith(".")) continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, files);
    else if ((CODE.has(extname(name)) || STYLE.has(extname(name))) && !name.endsWith(".d.ts") && !TEST.test(p)) files.push(p);
  }
  return files;
}

const IMPORT = /import\s+(?:type\s+)?(?:(\w+)\s*,?\s*)?(?:\{([^}]*)\})?\s*from\s*["']([^"']+)["']/g;
const ELEMENT = /<([A-Za-z][\w.-]*)(?=[\s/>])/g;
const RAW_COLOR = /(?<![\w&-])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b|\b(?:rgba?|hsla?)\(\s*\d/g;
const TOKEN = /var\(\s*--[\w-]+/g;
const isLocalSource = (s) => /^(\.|@\/|~\/|src\/|#)/.test(s);
const isDs = (s) => ds.some((p) => s === p || s.startsWith(`${p}/`));

function groupOf(file) {
  const parts = relative(root, file).split(sep);
  return parts.length <= depth ? "(root)" : parts.slice(0, depth).join("/");
}

const versionCache = new Map();
function dsVersion(file) {
  for (let dir = dirname(file); ; dir = dirname(dir)) {
    if (versionCache.has(dir)) return versionCache.get(dir);
    const pkg = join(dir, "package.json");
    if (existsSync(pkg)) {
      let v = null;
      try {
        const j = JSON.parse(readFileSync(pkg, "utf8"));
        const deps = { ...j.dependencies, ...j.devDependencies, ...j.peerDependencies };
        const name = ds.find((p) => deps[p]);
        v = name ? deps[name] : null;
      } catch { /* unreadable package.json: no version */ }
      if (v) { versionCache.set(dir, v); return v; }
    }
    if (dir === dirname(dir) || relative(root, dir).startsWith("..")) { versionCache.set(dir, null); return null; }
  }
}

const files = walk(root);
if (!files.length) fail(`no source or style files under ${root}`);
const groups = new Map();
for (const f of files) {
  const g = groupOf(f);
  const s = groups.get(g) ?? { group: g, ds: 0, local: 0, thirdParty: 0, rawHtml: 0, tokens: 0, raw: 0, versions: new Set(), rawByTag: {} };
  groups.set(g, s);
  const text = readFileSync(f, "utf8");
  s.tokens += (text.match(TOKEN) ?? []).length;
  s.raw += (text.match(RAW_COLOR) ?? []).length;
  const v = dsVersion(f);
  if (v) s.versions.add(v);
  if (!CODE.has(extname(f))) continue;
  const source = new Map();
  for (const m of text.matchAll(IMPORT)) {
    const names = [m[1], ...(m[2] ?? "").split(",").map((p) => p.trim().split(/\s+as\s+/).pop())].filter(Boolean);
    for (const n of names) source.set(n, m[3]);
  }
  for (const m of text.matchAll(ELEMENT)) {
    const tag = m[1];
    const root0 = tag.split(".")[0];
    if (/^[A-Z]/.test(root0)) {
      const src = source.get(root0);
      if (src && isDs(src)) s.ds++;
      else if (src && !isLocalSource(src)) s.thirdParty++;
      else s.local++;
    } else if (RAW_TAGS.includes(tag)) { s.rawHtml++; s.rawByTag[tag] = (s.rawByTag[tag] ?? 0) + 1; }
  }
}

const pct = (n, d) => (d ? Math.round((1000 * n) / d) / 10 : 0);
const rows = [...groups.values()].sort((a, b) => a.group.localeCompare(b.group)).map((s) => {
  const total = s.ds + s.local + s.thirdParty + s.rawHtml;
  const row = { group: s.group, adoption: pct(s.ds, total), ds: s.ds, local: s.local, thirdParty: s.thirdParty, rawHtml: s.rawHtml,
    tokenShare: pct(s.tokens, s.tokens + s.raw), tokens: s.tokens, rawColors: s.raw, version: [...s.versions].join(" ") || "-",
    rawByTag: s.rawByTag };
  const prev = baseline?.groups?.find((g) => g.group === s.group);
  row.delta = prev ? Math.round((row.adoption - prev.adoption) * 10) / 10 : null;
  return row;
});
const sum = (k) => rows.reduce((t, r) => t + r[k], 0);
const overall = pct(sum("ds"), sum("ds") + sum("local") + sum("thirdParty") + sum("rawHtml"));
const below = min === null ? [] : rows.filter((r) => r.adoption < min && r.ds + r.local + r.thirdParty + r.rawHtml > 0);
const major = (v) => Number(String(v).replace(/^[^\d]*/, "").split(".")[0]);
const lagging = latest ? rows.filter((r) => r.version !== "-" && r.version.split(" ").some((v) => major(v) < major(latest))) : [];

if (out === "json") console.log(JSON.stringify({ date: new Date().toISOString().slice(0, 10), overall, groups: rows }, null, 2));
else if (out === "csv") {
  console.log("date,group,adoption,ds,local,third_party,raw_html,token_share,raw_colors,version");
  const d = new Date().toISOString().slice(0, 10);
  for (const r of rows) console.log([d, r.group, r.adoption, r.ds, r.local, r.thirdParty, r.rawHtml, r.tokenShare, r.rawColors, r.version].join(","));
} else {
  console.log("| Group | Adoption | Change | DS | Local | 3rd party | Raw HTML | Token share | Raw colours | DS version |");
  console.log("|---|---|---|---|---|---|---|---|---|---|");
  for (const r of rows) {
    const change = r.delta === null ? "-" : `${r.delta > 0 ? "+" : ""}${r.delta} pts`;
    console.log(`| ${r.group} | ${r.adoption}% | ${change} | ${r.ds} | ${r.local} | ${r.thirdParty} | ${r.rawHtml} | ${r.tokenShare}% | ${r.rawColors} | ${r.version} |`);
  }
  console.log(`\nOverall adoption: ${overall}% of UI elements come from ${ds.join(", ")}`);
  for (const r of rows) {
    const tags = Object.entries(r.rawByTag).sort((a, b) => b[1] - a[1]).map(([t, n]) => `<${t}> x${n}`).join(", ");
    if (tags) console.log(`AD002 [info] ${r.group}: raw HTML the design system replaces: ${tags}`);
  }
  for (const r of lagging) console.log(`AD003 [warn] ${r.group}: on ${ds[0]} ${r.version}, latest major is ${major(latest)}`);
  for (const r of below) console.log(`AD001 [warn] ${r.group}: adoption ${r.adoption}% is below the ${min}% target`);
}
process.exit(below.length ? 1 : 0);
