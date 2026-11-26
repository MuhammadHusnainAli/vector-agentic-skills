#!/usr/bin/env node
// Find drift between design tokens and the colours actually used in code.
//
// Tokens come from DTCG JSON ({"$value": ...} with {alias} references), flat JSON ({"color.blue.600": "#2563eb"})
// or a CSS file of custom properties (--color-blue-600: #2563eb). Each token's CSS variable name is its path joined
// with "-" (prefix with --prefix). Code is scanned for raw colours (hex, rgb(), hsl()) and var(--...) references.
//
// Findings:
//   TD001 warn  raw colour exactly equals a token value: use the token
//   TD002 warn  raw colour within --delta (OKLab deltaE x100, default 3) of a token: probably meant that token
//   TD003 warn  raw colour far from every token: off-palette (new token, or a design question)
//   TD004 info  token never referenced in code (by var() or by value)
//   TD005 info  var(--name) used in code that matches no token (typo, local variable or undeclared token)
//
// Usage:
//   node token_drift.mjs TOKENS(.json|.css) CODE_DIR... [--prefix ds] [--delta 3] [--ignore tokens.css] [--json]
// Exit codes: 0 no warnings, 1 warnings, 2 bad arguments or unreadable tokens.

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { extname, join, relative } from "node:path";

const HELP = `usage: node token_drift.mjs TOKENS CODE_DIR [CODE_DIR...] [--prefix P] [--delta 3] [--ignore SUBSTR] [--json]
Compare raw colours in code with design tokens: exact matches, near-misses (OKLab deltaE), off-palette
colours, unused tokens and unknown var() references.`;
const argv = process.argv.slice(2);
if (!argv.length || argv.includes("-h") || argv.includes("--help")) { console.log(HELP); process.exit(argv.length ? 0 : 2); }
const fail = (m) => { console.error(`error: ${m}`); process.exit(2); };
const pos = [], ignore = [];
let prefix = "", delta = 3, asJson = false;
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === "--prefix") prefix = (argv[++i] ?? "").replace(/^-+|-+$/g, "");
  else if (a === "--delta") delta = Number(argv[++i]);
  else if (a === "--ignore") ignore.push(argv[++i]);
  else if (a === "--json") asJson = true;
  else if (a.startsWith("--")) fail(`unknown option ${a}`);
  else pos.push(a);
}
if (pos.length < 2) fail("give a tokens file and at least one code folder");
if (!(delta >= 0)) fail("--delta must be a non-negative number");
const [tokenFile, ...codePaths] = pos;

function parseColor(s) {
  s = String(s).trim().toLowerCase();
  let m = /^#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/.exec(s);
  if (m) {
    let h = m[1]; if (h.length <= 4) h = [...h].map((c) => c + c).join("");
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16), h.length === 8 ? parseInt(h.slice(6), 16) / 255 : 1];
  }
  m = /^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:\s*[,/]\s*([\d.]+)(%?))?\s*\)$/.exec(s);
  if (m) return [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : m[5] ? m[4] / 100 : +m[4]];
  m = /^hsla?\(\s*([\d.]+)(?:deg)?[\s,]+([\d.]+)%[\s,]+([\d.]+)%(?:\s*[,/]\s*([\d.]+)(%?))?\s*\)$/.exec(s);
  if (m) {
    const h = +m[1] / 360, sat = +m[2] / 100, l = +m[3] / 100;
    const f = (n) => { const k = (n + h * 12) % 12, a = sat * Math.min(l, 1 - l); return 255 * (l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1))); };
    return [f(0), f(8), f(4), m[4] === undefined ? 1 : m[5] ? m[4] / 100 : +m[4]];
  }
  return null;
}
const dtcgColor = (v) => (v && typeof v === "object" && v.hex ? parseColor(v.hex)
  : v && typeof v === "object" && v.colorSpace === "srgb" && Array.isArray(v.components) ? [...v.components.map((c) => c * 255), v.alpha ?? 1] : parseColor(v));
const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
function oklab([r, g, b]) {
  const [R, G, B] = [lin(r), lin(g), lin(b)];
  const l = Math.cbrt(0.4122214708 * R + 0.5363325363 * G + 0.0514459929 * B);
  const m = Math.cbrt(0.2119034982 * R + 0.6806995451 * G + 0.1073969566 * B);
  const s = Math.cbrt(0.0883024619 * R + 0.2817188376 * G + 0.6299787005 * B);
  return [0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s, 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s, 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s];
}
const deltaE = (c1, c2) => { const a = oklab(c1), b = oklab(c2); return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]) * 100 + Math.abs(c1[3] - c2[3]) * 100; };
const hex = (c) => "#" + c.slice(0, 3).map((v) => Math.round(v).toString(16).padStart(2, "0")).join("") + (c[3] < 1 ? Math.round(c[3] * 255).toString(16).padStart(2, "0") : "");

// ---- load tokens: Map(cssVar -> {path, color|null})
if (!existsSync(tokenFile)) fail(`${tokenFile} does not exist`);
const tokenText = readFileSync(tokenFile, "utf8");
const raw = new Map();   // path -> value (maybe alias)
if (extname(tokenFile) === ".css") {
  for (const m of tokenText.matchAll(/--([\w-]+)\s*:\s*([^;}]+)/g)) raw.set(m[1], m[2].trim().replace(/^var\(--([\w-]+)\)$/, "{$1}"));
} else {
  let json; try { json = JSON.parse(tokenText); } catch (e) { fail(`${tokenFile}: ${e.message}`); }
  const walk = (node, path) => {
    if (node && typeof node === "object" && "$value" in node) { raw.set(path.join("."), node.$value); return; }
    if (node && typeof node === "object" && !Array.isArray(node)) { for (const [k, v] of Object.entries(node)) if (!k.startsWith("$")) walk(v, [...path, k]); return; }
    raw.set(path.join("."), node);
  };
  walk(json, []);
}
const chainOf = (p, seen = []) => {          // [p, alias target, ...] ending at the token holding the value
  const v = raw.get(p);
  const m = typeof v === "string" && /^\{([^}]+)\}$/.exec(v.trim());
  if (!m || seen.includes(p)) return [...seen, p];
  const target = raw.has(m[1]) ? m[1] : [...raw.keys()].find((k) => k.replace(/\./g, "-") === m[1].replace(/\./g, "-"));
  return target ? chainOf(target, [...seen, p]) : [...seen, p, null];
};
const resolveTok = (p) => { const c = chainOf(p); const last = c[c.length - 1]; return last === null ? null : raw.get(last); };
const varName = (p) => (prefix ? `${prefix}-` : "") + p.replace(/\./g, "-");
const tokens = new Map();
const isCss = extname(tokenFile) === ".css", nameOf = (p) => (isCss ? p : varName(p));
for (const p of raw.keys()) {
  const chain = chainOf(p).filter(Boolean).map(nameOf);
  tokens.set(nameOf(p), { path: p, color: dtcgColor(resolveTok(p)), alias: chain.length > 1, chain });
}
const colorTokens = [...tokens.entries()].filter(([, t]) => t.color);
if (!colorTokens.length) fail(`no colour tokens found in ${tokenFile}`);

// ---- scan code
const EXT = new Set([".css", ".scss", ".less", ".jsx", ".tsx", ".js", ".ts", ".vue", ".svelte", ".html"]);
const SKIP = new Set(["node_modules", ".git", "dist", "build", ".next", "out", "coverage", "storybook-static"]);
const files = [];
const collect = (p) => {
  if (!existsSync(p)) fail(`${p} does not exist`);
  if (statSync(p).isFile()) { files.push(p); return; }
  for (const n of readdirSync(p)) {
    if (SKIP.has(n) || n.startsWith(".")) continue;
    const q = join(p, n);
    if (statSync(q).isDirectory()) collect(q); else if (EXT.has(extname(n))) files.push(q);
  }
};
codePaths.forEach(collect);
const scanned = files.filter((f) => !ignore.some((s) => f.includes(s)) && relative(".", f) !== relative(".", tokenFile));
const COLOR = /(?<![\w&-])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b|\b(?:rgba?|hsla?)\([^)]*\)/g;
const VAR = /var\(\s*--([\w-]+)/g;
const rawUses = new Map(), varUses = new Map();
for (const f of scanned) {
  const text = readFileSync(f, "utf8"), rel = relative(process.cwd(), f) || f;
  const line = (i) => text.slice(0, i).split("\n").length;
  for (const m of text.matchAll(COLOR)) {
    const c = parseColor(m[0]); if (!c) continue;
    const key = hex(c);
    const u = rawUses.get(key) ?? { color: c, where: [] };
    u.where.push(`${rel}:${line(m.index)}`); rawUses.set(key, u);
  }
  for (const m of text.matchAll(VAR)) varUses.set(m[1], [...(varUses.get(m[1]) ?? []), `${rel}:${line(m.index)}`]);
}

const findings = [];
const add = (code, severity, message, where = []) => findings.push({ code, severity, message, where });
const usedTokens = new Set([...varUses.keys()].filter((v) => tokens.has(v)).flatMap((v) => tokens.get(v).chain));
for (const [key, u] of [...rawUses].sort((a, b) => b[1].where.length - a[1].where.length)) {
  let best = null;
  for (const [v, t] of colorTokens) { const d = deltaE(u.color, t.color); if (!best || d < best.d) best = { v, t, d }; }
  const n = u.where.length, at = u.where.slice(0, 3).join(", ") + (n > 3 ? `, +${n - 3} more` : "");
  if (best.d < 0.05) {
    const equal = colorTokens.filter(([, t]) => deltaE(u.color, t.color) < 0.05).sort((a, b) => b[1].alias - a[1].alias).map(([v]) => v);
    equal.forEach((v) => usedTokens.add(v));
    const others = equal.length > 1 ? ` (same value: ${equal.slice(1).map((v) => `--${v}`).join(", ")})` : "";
    add("TD001", "warn", `${key} (${n}x) equals token --${equal[0]}${others}: use var(--${equal[0]})  [${at}]`, u.where);
  }
  else if (best.d <= delta) add("TD002", "warn", `${key} (${n}x) is deltaE ${best.d.toFixed(1)} from --${best.v} ${hex(best.t.color)}: probably meant the token  [${at}]`, u.where);
  else add("TD003", "warn", `${key} (${n}x) is off-palette; nearest --${best.v} ${hex(best.t.color)} (deltaE ${best.d.toFixed(1)})  [${at}]`, u.where);
}
for (const [v, t] of tokens) if (!usedTokens.has(v) && t.color) add("TD004", "info", `--${v} never used in code`);
for (const [v, where] of varUses) if (!tokens.has(v)) add("TD005", "info", `var(--${v}) matches no token  [${where.slice(0, 2).join(", ")}]`, where);

const warns = findings.filter((f) => f.severity === "warn").length;
const totalRaw = [...rawUses.values()].reduce((s, u) => s + u.where.length, 0);
const totalVar = [...varUses.entries()].filter(([v]) => tokens.has(v)).reduce((s, [, w]) => s + w.length, 0);
if (asJson) console.log(JSON.stringify({ tokens: tokens.size, colorTokens: colorTokens.length, files: scanned.length, rawColorUses: totalRaw, tokenVarUses: totalVar, findings }, null, 2));
else {
  for (const f of findings) console.log(`${f.code} [${f.severity}] ${f.message}`);
  const share = totalRaw + totalVar ? Math.round((1000 * totalVar) / (totalRaw + totalVar)) / 10 : 100;
  console.log(`\n${scanned.length} files, ${colorTokens.length} colour tokens: ${totalVar} token references, ${totalRaw} raw colours (${share}% via tokens)`);
  console.log(`${warns} warning(s), ${findings.length - warns} info`);
}
process.exit(warns ? 1 : 0);
