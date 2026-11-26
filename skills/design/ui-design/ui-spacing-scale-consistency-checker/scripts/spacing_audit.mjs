#!/usr/bin/env node
// Audit spacing values (margin, padding, gap, inset) in a codebase against a spacing scale.
//
// Reads .css .scss .less .jsx .tsx .js .ts .vue .svelte .html files. Finds:
//   CSS declarations           padding: 12px 18px;  margin-top: 1.25rem;  gap: 10px
//   JSX/JS style objects        style={{ paddingTop: 14, marginInline: "6px" }}   (unitless numbers are px)
//   Tailwind arbitrary values   p-[18px]  mt-[1.1rem]  gap-x-[10px]
// Values in rem are converted with --rem (default 16). var(--...) references count as token usage; em, %, auto,
// calc() and 0 are ignored.
//
// Findings:
//   SP001 warn  off-scale value, with the nearest scale step(s) and where it occurs
//   SP002 info  raw on-scale values that could be tokens (counted, not listed)
//
// Usage:
//   node spacing_audit.mjs DIR_OR_FILE... [--scale 0,4,8,12,16,24,32,48,64] [--base 4] [--rem 16] [--min 90] [--json]
// Exit codes: 0 all values on scale (or on-scale share >= --min), 1 otherwise, 2 bad arguments or nothing found.

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { extname, join, relative } from "node:path";

const HELP = `usage: node spacing_audit.mjs PATH [PATH...] [--scale LIST | --base N] [--rem 16] [--min PCT] [--json]
Audit margin/padding/gap/inset values in CSS, style objects and Tailwind arbitrary classes against
a spacing scale (default 0 2 4 8 12 16 20 24 32 40 48 64 80 96 128). Exit 0 clean, 1 off-scale, 2 bad input.`;

const argv = process.argv.slice(2);
if (!argv.length || argv.includes("-h") || argv.includes("--help")) { console.log(HELP); process.exit(argv.length ? 0 : 2); }
const paths = [];
let scale = [0, 2, 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128], base = null, rem = 16, min = null, asJson = false;
const fail = (m) => { console.error(`error: ${m}`); process.exit(2); };
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === "--scale") scale = (argv[++i] ?? "").split(",").map(Number);
  else if (a === "--base") base = Number(argv[++i]);
  else if (a === "--rem") rem = Number(argv[++i]);
  else if (a === "--min") min = Number(argv[++i]);
  else if (a === "--json") asJson = true;
  else if (a.startsWith("--")) fail(`unknown option ${a}`);
  else paths.push(a);
}
if (!paths.length) fail("give at least one folder or file");
if (scale.some((n) => !Number.isFinite(n) || n < 0)) fail("--scale must be comma-separated non-negative numbers");
if (base !== null && !(base > 0)) fail("--base must be a positive number");
if (!(rem > 0)) fail("--rem must be a positive number");
if (min !== null && !(min >= 0 && min <= 100)) fail("--min must be a percentage 0-100");
const onScale = (px) => (base ? Math.abs(px / base - Math.round(px / base)) < 1e-6 : scale.some((s) => Math.abs(s - px) < 0.01));
const nearest = (px) => {
  if (base) { const lo = Math.floor(px / base) * base; return [...new Set([lo, lo + base])]; }
  const sorted = [...scale].sort((a, b) => Math.abs(a - px) - Math.abs(b - px));
  const d = Math.abs(sorted[0] - px);
  return sorted.filter((s) => Math.abs(Math.abs(s - px) - d) < 0.01).sort((a, b) => a - b);
};

const EXT = new Set([".css", ".scss", ".less", ".jsx", ".tsx", ".js", ".ts", ".vue", ".svelte", ".html"]);
const SKIP = new Set(["node_modules", ".git", "dist", "build", ".next", "out", "coverage", "storybook-static", "vendor"]);
function collect(p, files = []) {
  if (!existsSync(p)) fail(`${p} does not exist`);
  const st = statSync(p);
  if (st.isFile()) { files.push(p); return files; }
  for (const name of readdirSync(p)) {
    if (SKIP.has(name) || name.startsWith(".")) continue;
    const q = join(p, name);
    if (statSync(q).isDirectory()) collect(q, files);
    else if (EXT.has(extname(name)) && !/\.min\.css$/.test(name)) files.push(q);
  }
  return files;
}

const CSS_DECL = /(?:^|[;{\s])((?:margin|padding|gap|row-gap|column-gap|inset|scroll-margin|scroll-padding)(?:-[a-z-]+)?)\s*:\s*([^;{}\n]+)/g;
const JS_DECL = /\b((?:margin|padding|gap|rowGap|columnGap|inset)(?:Top|Right|Bottom|Left|Inline|Block|InlineStart|InlineEnd|BlockStart|BlockEnd|Horizontal|Vertical)?)\s*:\s*("[^"\n]*"|'[^'\n]*'|-?\d+(?:\.\d+)?)(?=\s*[,}\n])/g;
const TW = /(?<![\w-])-?(?:p|px|py|pt|pr|pb|pl|ps|pe|m|mx|my|mt|mr|mb|ml|ms|me|gap|gap-x|gap-y|space-x|space-y|inset|inset-x|inset-y|top|right|bottom|left)-\[(-?\d*\.?\d+(?:px|rem))\]/g;
const VALUE = /^(-?\d*\.?\d+)(px|rem)?$/;

const files = paths.flatMap((p) => collect(p));
if (!files.length) fail("no CSS, style or markup files found");
const values = new Map();      // px -> {count, onScale, where: Map(file -> lines)}
let tokenRefs = 0;
const record = (px, file, line) => {
  const v = values.get(px) ?? { px, count: 0, onScale: onScale(px), where: new Map() };
  v.count++;
  const lines = v.where.get(file) ?? [];
  if (lines.length < 5) lines.push(line);
  v.where.set(file, lines);
  values.set(px, v);
};
const parseTokens = (raw, file, line, unitlessPx) => {
  for (const tok of raw.replace(/!important/g, "").trim().split(/\s+/)) {
    if (tok.startsWith("var(")) { tokenRefs++; continue; }
    const m = VALUE.exec(tok.replace(/,$/, ""));
    if (!m) continue;
    if (!m[2] && !unitlessPx && Number(m[1]) !== 0) continue;
    const px = Math.abs(Number(m[1]) * (m[2] === "rem" ? rem : 1));
    if (px === 0) continue;
    record(Math.round(px * 100) / 100, file, line);
  }
};
for (const f of files) {
  const text = readFileSync(f, "utf8");
  const rel = relative(process.cwd(), f) || f;
  const lineAt = (idx) => text.slice(0, idx).split("\n").length;
  const isCss = [".css", ".scss", ".less"].includes(extname(f));
  const styleBlocks = isCss ? [{ start: 0, body: text }]
    : [...text.matchAll(/<style[^>]*>([\s\S]*?)<\/style>|style\s*=\s*"([^"]*)"/g)].map((m) => ({ start: m.index, body: m[1] ?? m[2] }));
  for (const b of styleBlocks) for (const m of b.body.matchAll(CSS_DECL)) parseTokens(m[2], rel, lineAt(b.start + m.index), false);
  if (!isCss) {
    for (const m of text.matchAll(JS_DECL)) parseTokens(m[2].replace(/^["']|["']$/g, ""), rel, lineAt(m.index), true);
    for (const m of text.matchAll(TW)) parseTokens(m[1], rel, lineAt(m.index), false);
  }
}

const all = [...values.values()].sort((a, b) => a.px - b.px);
const total = all.reduce((s, v) => s + v.count, 0);
if (!total && !tokenRefs) fail("no spacing values found");
const onCount = all.filter((v) => v.onScale).reduce((s, v) => s + v.count, 0);
const share = total ? Math.round((1000 * onCount) / total) / 10 : 100;
const off = all.filter((v) => !v.onScale).sort((a, b) => b.count - a.count);
const failed = min === null ? off.length > 0 : share < min;

if (asJson) {
  console.log(JSON.stringify({ scale: base ? `multiples of ${base}` : scale, total, onScale: onCount, share, tokenRefs,
    values: all.map((v) => ({ px: v.px, count: v.count, onScale: v.onScale, nearest: v.onScale ? null : nearest(v.px),
      where: Object.fromEntries(v.where) })) }, null, 2));
} else {
  console.log(`Scale: ${base ? `multiples of ${base}px` : scale.join(" ")} (rem = ${rem}px)\n`);
  console.log("| Value | Uses | On scale |\n|---|---|---|");
  for (const v of all) console.log(`| ${v.px}px | ${v.count} | ${v.onScale ? "yes" : `no -> ${nearest(v.px).join(" or ")}`} |`);
  console.log("");
  for (const v of off) {
    const where = [...v.where].map(([f, l]) => `${f}:${l.join(",")}`).join("  ");
    console.log(`SP001 [warn] ${v.px}px used ${v.count}x is off scale -> ${nearest(v.px).join(" or ")}px  (${where})`);
  }
  if (onCount) console.log(`SP002 [info] ${onCount} raw on-scale value(s) could reference spacing tokens; ${tokenRefs} var(--...) reference(s) found`);
  console.log(`\n${total} raw spacing values in ${files.length} files: ${share}% on scale, ${off.length} off-scale value(s)`);
}
process.exit(failed ? 1 : 0);
