#!/usr/bin/env node
// Inventory the UI components in a codebase: where each is defined, how often it is used, and where the
// library has drifted (near-duplicates, local copies of design-system components, unused components,
// hard-coded colours).
//
// Scans .jsx .tsx .js .ts .vue .svelte files, skipping node_modules, build output and (by default) tests
// and stories when counting usages.
//
// Findings:
//   IN001 warn  near-duplicate components (Button, Btn, PrimaryButton, CustomButton -> one group)
//   IN002 warn  local component with the same name as a design-system component (--ds package)
//   IN003 info  component defined but never used
//   IN004 warn  file with more hard-coded colours than --max-raw (hex, rgb(), hsl())
//   IN005 info  component used exactly once (candidate to inline or fold into a shared one)
//
// Usage:
//   node inventory_scan.mjs src/ [--ds @acme/ui] [--max-raw 5] [--include-tests] [--csv] [--json]
// Exit codes: 0 no warnings, 1 warnings, 2 bad arguments or no source files.

import { readdirSync, readFileSync, statSync } from "node:fs";
import { basename, extname, join, relative } from "node:path";

const HELP = `usage: node inventory_scan.mjs DIR [--ds PACKAGE ...] [--max-raw N] [--include-tests] [--csv | --json]
Inventory UI components: definitions, usages, near-duplicates, local copies of design-system
components, unused components and hard-coded colours. Exit 0 clean, 1 warnings, 2 bad input.`;

const argv = process.argv.slice(2);
if (!argv.length || argv.includes("-h") || argv.includes("--help")) { console.log(HELP); process.exit(argv.length ? 0 : 2); }
let root = null, maxRaw = 5, includeTests = false, out = "text";
const dsPackages = [];
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === "--ds") dsPackages.push(argv[++i]);
  else if (a === "--max-raw") maxRaw = Number(argv[++i]);
  else if (a === "--include-tests") includeTests = true;
  else if (a === "--csv") out = "csv";
  else if (a === "--json") out = "json";
  else if (a.startsWith("--")) { console.error(`error: unknown option ${a}`); process.exit(2); }
  else root = a;
}
if (!root || !Number.isFinite(maxRaw)) { console.error("error: give a directory (and a number for --max-raw)"); process.exit(2); }
try { if (!statSync(root).isDirectory()) throw new Error("not a directory"); }
catch (e) { console.error(`error: ${root}: ${e.message}`); process.exit(2); }

const EXT = new Set([".jsx", ".tsx", ".js", ".ts", ".vue", ".svelte"]);
const SKIP = new Set(["node_modules", ".git", "dist", "build", ".next", "out", "coverage", "storybook-static", ".turbo", "vendor"]);
const TEST = /\.(test|spec|stories|story)\.[jt]sx?$|__tests__|__mocks__/;
const ENTRY = /(^|[\\/])(pages|app|routes|views|screens)[\\/]/;   // route files: rendered by the router, not by JSX

function walk(dir, files = []) {
  for (const name of readdirSync(dir)) {
    if (SKIP.has(name) || name.startsWith(".")) continue;
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) walk(p, files);
    else if (EXT.has(extname(name)) && !name.endsWith(".d.ts")) files.push(p);
  }
  return files;
}

const DEFS = [
  /export\s+(?:default\s+)?function\s+([A-Z]\w*)/g,
  /(?:^|\n)\s*(?:export\s+)?function\s+([A-Z]\w*)\s*\(/g,
  /(?:^|\n)\s*(?:export\s+)?const\s+([A-Z]\w*)\s*(?::[^=\n]+)?=\s*(?:React\.)?(?:memo|forwardRef|styled|\(|function|async\s*\(|\w+\s*=>)/g,
  /class\s+([A-Z]\w*)\s+extends\s+(?:React\.)?(?:Pure)?Component\b/g,
];
const USE = /<([A-Z][\w]*)(?=[\s/>.])/g;
const KEBAB_USE = /<([a-z][a-z0-9]*(?:-[a-z0-9]+)+)(?=[\s/>])/g;
const IMPORT = /import\s+(?:type\s+)?(?:(\w+)\s*,?\s*)?(?:\{([^}]*)\})?\s*from\s*["']([^"']+)["']/g;
const RAW_COLOR = /(?<![\w&-])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b|\b(?:rgba?|hsla?)\(\s*\d/g;

const pascal = (s) => s.split("-").map((w) => w[0].toUpperCase() + w.slice(1)).join("");
const files = walk(root);
if (!files.length) { console.error(`error: no .jsx/.tsx/.js/.ts/.vue/.svelte files under ${root}`); process.exit(2); }

const defs = new Map();          // name -> [file]
const uses = new Map();          // name -> {count, files:Set}
const dsNames = new Set();       // local names of design-system imports (aliases included), for usage counts
const dsOriginal = new Set();    // exported names in the design-system package, for duplicate matching
const rawByFile = [];
for (const f of files) {
  const text = readFileSync(f, "utf8");
  const rel = relative(root, f) || basename(f);
  const isTest = TEST.test(f);
  const found = new Set();
  for (const rx of DEFS) for (const m of text.matchAll(rx)) found.add(m[1]);
  if ([".vue", ".svelte"].includes(extname(f))) found.add(pascal(basename(f, extname(f))));
  if (!isTest) for (const n of found) defs.set(n, [...(defs.get(n) ?? []), rel]);
  for (const m of text.matchAll(IMPORT)) {
    if (!dsPackages.some((p) => m[3] === p || m[3].startsWith(`${p}/`))) continue;
    if (m[1]) { dsNames.add(m[1]); dsOriginal.add(m[1]); }
    for (const part of (m[2] ?? "").split(",")) {
      const [orig, alias] = part.trim().split(/\s+as\s+/);
      if (/^[A-Z]/.test(orig ?? "")) { dsOriginal.add(orig); dsNames.add(alias ?? orig); }
    }
  }
  if (isTest && !includeTests) continue;
  const names = [...text.matchAll(USE)].map((m) => m[1]).concat([...text.matchAll(KEBAB_USE)].map((m) => pascal(m[1])));
  for (const n of names) {
    const u = uses.get(n) ?? { count: 0, files: new Set() };
    u.count++; u.files.add(rel); uses.set(n, u);
  }
  const raw = (text.match(RAW_COLOR) ?? []).length;
  if (raw) rawByFile.push({ file: rel, raw });
}

// Near-duplicate grouping: split camel case, drop decoration and variant words, apply abbreviations.
const NOISE = new Set(["custom", "new", "old", "base", "my", "app", "ui", "ds", "core", "simple", "generic", "common", "shared",
  "legacy", "v1", "v2", "v3", "wrapper", "component", "styled", "primary", "secondary", "tertiary", "large", "small", "big",
  "mini", "blue", "red", "green", "grey", "gray", "rounded", "outlined", "outline", "ghost", "fancy", "default", "basic"]);
const ABBR = { btn: "button", img: "image", txt: "text", lbl: "label", modal: "dialog", popup: "dialog", tooltip: "tooltip", tip: "tooltip", chk: "checkbox" };
const keyOf = (name) => {
  const parts = name.replace(/([a-z0-9])([A-Z])/g, "$1 $2").replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2").toLowerCase().split(/\s+/);
  const kept = parts.map((p) => ABBR[p] ?? p).filter((p) => !NOISE.has(p));
  return kept.join("-") || parts.join("-");
};

const findings = [];
const add = (code, severity, subject, message) => findings.push({ code, severity, subject, message });
const groups = new Map();
for (const n of defs.keys()) groups.set(keyOf(n), [...(groups.get(keyOf(n)) ?? []), n]);
for (const [key, names] of groups) if (names.length > 1)
  add("IN001", "warn", key, `near-duplicates: ${names.map((n) => `${n} (${uses.get(n)?.count ?? 0} uses)`).join(", ")}`);
for (const [n, where] of defs) {
  const ds = [...dsOriginal].find((d) => d === n || keyOf(d) === keyOf(n));
  if (ds) add("IN002", "warn", n, `local ${n} in ${where[0]} duplicates design-system ${ds}: migrate usages and delete it`);
  const u = uses.get(n)?.count ?? 0;
  if (u === 0 && where.every((w) => ENTRY.test(w))) continue;
  if (u === 0) add("IN003", "info", n, `defined in ${where[0]} but never used`);
  else if (u === 1) add("IN005", "info", n, `used once (${[...uses.get(n).files][0]})`);
}
for (const r of rawByFile.sort((a, b) => b.raw - a.raw)) if (r.raw > maxRaw)
  add("IN004", "warn", r.file, `${r.raw} hard-coded colours: replace with tokens`);

const rows = [...defs.keys()].sort((a, b) => (uses.get(b)?.count ?? 0) - (uses.get(a)?.count ?? 0) || a.localeCompare(b))
  .map((n) => ({ component: n, defined_in: defs.get(n).join(" "), uses: uses.get(n)?.count ?? 0,
    used_in_files: uses.get(n)?.files.size ?? 0, group: keyOf(n),
    design_system: [...dsOriginal].find((d) => d === n || keyOf(d) === keyOf(n)) ?? "" }));
const dsUses = [...dsNames].reduce((s, n) => s + (uses.get(n)?.count ?? 0), 0);
const localUses = rows.reduce((s, r) => s + r.uses, 0);
const warnings = findings.filter((f) => f.severity === "warn").length;

if (out === "json") console.log(JSON.stringify({ files: files.length, components: rows, designSystemUses: dsUses, localUses, findings }, null, 2));
else if (out === "csv") {
  console.log("component,defined_in,uses,used_in_files,group,design_system");
  for (const r of rows) console.log([r.component, r.defined_in, r.uses, r.used_in_files, r.group, r.design_system].map((v) => `"${String(v).replace(/"/g, '""')}"`).join(","));
} else {
  console.log(`| Component | Defined in | Uses | Files | Group |\n|---|---|---|---|---|`);
  for (const r of rows) console.log(`| ${r.component} | ${r.defined_in} | ${r.uses} | ${r.used_in_files} | ${r.group} |`);
  console.log("");
  for (const f of findings.sort((a, b) => a.severity.localeCompare(b.severity, "en") * -1 || a.code.localeCompare(b.code)))
    console.log(`${f.code} [${f.severity}] ${f.subject}: ${f.message}`);
  const share = dsUses + localUses ? Math.round((100 * dsUses) / (dsUses + localUses)) : 0;
  console.log(`\n${files.length} files, ${rows.length} local components, ${dsOriginal.size} design-system components imported`);
  if (dsPackages.length) console.log(`Usage share: design system ${dsUses} (${share}%), local ${localUses}`);
  console.log(`${warnings} warning(s), ${findings.length - warnings} info`);
}
process.exit(warnings ? 1 : 0);
