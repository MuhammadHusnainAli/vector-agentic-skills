#!/usr/bin/env node
// Scan UI code for the fingerprints of generic AI-generated design ("AI slop") and score it 0-100.
//
// Reads .html .css .scss .jsx .tsx .js .ts .vue .svelte .astro .mdx files (Tailwind classes, CSS and copy).
// Each rule counts matches; the score weighs how many distinct slop patterns appear and how heavily.
//
// Rules (weight):
//   AS001 (8) gradient text (bg-clip-text + text-transparent, background-clip: text)
//   AS002 (8) purple/violet/indigo gradients (Tailwind from-/via-/to- purple hues, CSS gradients with hue 255-320)
//   AS003 (7) emoji used as icons or decoration in UI text
//   AS004 (6) glassmorphism (backdrop blur on translucent white/black panels; a blurred sticky header alone is fine)
//   AS005 (7) hype copy (unlock, seamless, revolutionize, supercharge, elevate, cutting-edge, game-changer ...)
//   AS006 (5) blurred glow blobs and orbs (blur-3xl / blur-[100px] decorations, glow keyframes)
//   AS007 (5) decorative motion (animate-bounce/pulse/ping on non-loading UI, float/glow keyframes)
//   AS008 (4) hover lift on everything (hover:scale-*, hover:-translate-y-*)
//   AS009 (4) oversized radius everywhere (rounded-2xl/3xl or radius >= 20px in at least half of all radius uses)
//   AS010 (4) heavy shadows everywhere (shadow-xl/2xl or large blur box-shadows in at least half of all shadow uses)
//   AS011 (5) template social proof (Trusted by 10,000+, 99.9% uptime, John Doe, 5-star rows, Acme logos)
//   AS012 (3) default Tailwind accent palette as the brand (indigo/violet/purple 500-600 as primary)
//   AS013 (3) icon-in-tinted-square feature cards (bg-*-100 + rounded + icon in a 3-column grid)
//   AS014 (3) only default fonts (Inter / system-ui / no font choice at all)
//   AS015 (4) placeholder content (lorem ipsum, "Feature 1", example@email.com)
//
// Usage:
//   node slop_scan.mjs PATH [PATH...] [--max 30] [--json]
// Exit codes: 0 score <= --max (default 30), 1 above, 2 bad arguments or nothing to scan.

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { extname, join, relative } from "node:path";

const HELP = `usage: node slop_scan.mjs PATH [PATH...] [--max 30] [--json]
Score UI code for generic AI-generated design patterns (0 clean - 100 heavy) with file:line evidence.
Exit 0 score <= --max, 1 above, 2 bad input.`;
const argv = process.argv.slice(2);
if (!argv.length || argv.includes("-h") || argv.includes("--help")) { console.log(HELP); process.exit(argv.length ? 0 : 2); }
const fail = (m) => { console.error(`error: ${m}`); process.exit(2); };
const paths = [];
let max = 30, asJson = false;
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === "--max") max = Number(argv[++i]);
  else if (a === "--json") asJson = true;
  else if (a.startsWith("--")) fail(`unknown option ${a}`);
  else paths.push(a);
}
if (!paths.length) fail("give at least one file or folder");
if (!(max >= 0 && max <= 100)) fail("--max must be 0-100");

const EXT = new Set([".html", ".css", ".scss", ".jsx", ".tsx", ".js", ".ts", ".vue", ".svelte", ".astro", ".mdx"]);
const SKIP = new Set(["node_modules", ".git", "dist", "build", ".next", "out", "coverage", "storybook-static", "vendor"]);
const files = [];
const collect = (p) => {
  if (!existsSync(p)) fail(`${p} does not exist`);
  if (statSync(p).isFile()) { files.push(p); return; }
  for (const n of readdirSync(p)) {
    if (SKIP.has(n) || n.startsWith(".")) continue;
    const q = join(p, n);
    if (statSync(q).isDirectory()) collect(q); else if (EXT.has(extname(n)) && !/\.(test|spec|min)\./.test(n)) files.push(q);
  }
};
paths.forEach(collect);
if (!files.length) fail("no UI source files found");

function hue(hex) {
  let h = hex.replace("#", "");
  if (h.length <= 4) h = [...h.slice(0, 3)].map((c) => c + c).join("");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn, l = (mx + mn) / 2;
  const s = d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1));
  if (d === 0) return { h: 0, s: 0 };
  const hh = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return { h: (hh * 60 + 360) % 360, s };
}
const purpleGradient = (body) => (body.match(/#[0-9a-fA-F]{3,8}\b/g) ?? []).some((c) => { const { h, s } = hue(c); return h >= 255 && h <= 320 && s > 0.35; });

const HYPE = /\b(unlock(?:ing)?|unleash|seamless(?:ly)?|revolutioni[sz]e|supercharge|elevate your|empower(?:ing)?|cutting[- ]edge|game[- ]chang(?:er|ing)|next[- ]level|effortless(?:ly)?|transform your|reimagin(?:e|ing)|harness the power|in today'?s fast[- ]paced|take .{1,20} to the next level|all[- ]in[- ]one|blazing(?:ly)? fast|built for the future|like never before|magic(?:al)?ly)\b/gi;
const RULES = [
  { code: "AS001", w: 8, name: "gradient text", rx: [/\bbg-clip-text\b/g, /background-clip\s*:\s*text/g] },
  { code: "AS002", w: 8, name: "purple/indigo gradients", rx: [/\b(?:from|via|to)-(?:purple|violet|indigo|fuchsia)-\d{2,3}\b/g], custom: "gradient" },
  { code: "AS003", w: 7, name: "emoji as icons or decoration", rx: [/\p{Emoji_Presentation}|\p{Extended_Pictographic}\uFE0F/gu] },
  { code: "AS004", w: 6, name: "glassmorphism panels", rx: [/\bbackdrop-blur(?:-\w+)?\b(?=[^"'`]*\bbg-(?:white|black)\/(?:[5-9]|[1-3]\d)\b)|\bbg-(?:white|black)\/(?:[5-9]|[1-3]\d)\b(?=[^"'`]*\bbackdrop-blur)/g,
    /\{[^{}]*backdrop-filter\s*:\s*blur[^{}]*rgba\(\s*(?:255\s*,\s*255\s*,\s*255|0\s*,\s*0\s*,\s*0)\s*,\s*0?\.[0-3]\d*\s*\)[^{}]*\}|\{[^{}]*rgba\(\s*(?:255\s*,\s*255\s*,\s*255|0\s*,\s*0\s*,\s*0)\s*,\s*0?\.[0-3]\d*\s*\)[^{}]*backdrop-filter\s*:\s*blur[^{}]*\}/g] },
  { code: "AS005", w: 7, name: "hype marketing copy", rx: [HYPE] },
  { code: "AS006", w: 5, name: "glow blobs and orbs", rx: [/\bblur-(?:2xl|3xl|\[\d{2,3}px\])\b/g, /@keyframes\s+[\w-]*glow/g, /filter\s*:\s*blur\(\s*(?:[4-9]\d|\d{3})px/g] },
  { code: "AS007", w: 5, name: "decorative motion", rx: [/\banimate-(?:bounce|pulse|ping)\b/g, /@keyframes\s+[\w-]*(?:float|wiggle|gradient)/g] },
  { code: "AS008", w: 4, name: "hover lift everywhere", rx: [/\bhover:scale-1\d{2}\b/g, /\bhover:-translate-y-\d/g, /:hover[^{]*\{[^}]*transform\s*:\s*(?:scale|translateY\(-)/g] },
  { code: "AS009", w: 4, name: "oversized radius everywhere", rx: [/\brounded-(?:2xl|3xl)\b/g, /border-radius\s*:\s*(?:2\d|[3-9]\d)px/g], min: 4,
    all: [/\brounded(?:-[a-z0-9]+)?\b/g, /border-radius\s*:/g] },
  { code: "AS010", w: 4, name: "heavy shadows everywhere", rx: [/\bshadow-(?:xl|2xl)\b/g, /box-shadow\s*:[^;]*\b(?:[3-9]\d)px\s+(?:-?\d+px\s+)?rgba/g], min: 3,
    all: [/\bshadow(?:-[a-z0-9]+)?\b(?![-:])/g, /box-shadow\s*:/g] },
  { code: "AS011", w: 5, name: "template social proof", rx: [/\b(?:trusted|loved|used) by (?:over )?[\d,.]+k?\+?/gi, /\b(?:10,?000|50,?000|100,?000)\+/g, /99\.9+%/g, /\b(?:john|jane) (?:doe|smith)\b/gi, /★{4,}|⭐{3,}/g, /\bAcme\b/g] },
  { code: "AS012", w: 3, name: "default Tailwind accent as brand", rx: [/\b(?:bg|text|border|ring)-(?:indigo|violet|purple)-(?:500|600)\b/g], min: 3 },
  { code: "AS013", w: 3, name: "icon-in-tinted-square feature cards", rx: [/\bbg-\w+-(?:50|100)\b[^"'`]*\brounded-(?:lg|xl|2xl|full)\b|\brounded-(?:lg|xl|2xl|full)\b[^"'`]*\bbg-\w+-(?:50|100)\b/g], min: 3 },
  { code: "AS014", w: 3, name: "only default fonts", custom: "fonts" },
  { code: "AS015", w: 4, name: "placeholder content", rx: [/lorem ipsum/gi, /\bFeature (?:One|Two|Three|[123])\b/g, /\b(?:example|you)@(?:email|example)\.com\b/gi] },
];

const hits = new Map(RULES.map((r) => [r.code, []]));
const totals = new Map(RULES.map((r) => [r.code, 0]));   // all radius / shadow uses, for "everywhere" ratios
const seenLine = new Set();
let fontDecl = 0, defaultFontDecl = 0, threeCols = 0;
for (const f of files) {
  const text = readFileSync(f, "utf8"), rel = relative(process.cwd(), f) || f;
  const lineAt = (i) => text.slice(0, i).split("\n").length;
  for (const r of RULES) {
    for (const rx of r.all ?? []) totals.set(r.code, totals.get(r.code) + (text.match(rx) ?? []).length);
    for (const rx of r.rx ?? []) for (const m of text.matchAll(rx)) {
      if (r.code === "AS007" && /load|spin|skeleton|progress/i.test(text.slice(Math.max(0, m.index - 80), m.index + 80))) continue;
      const at = `${rel}:${lineAt(m.index)}`, key = `${r.code}|${at}|${m[0]}|${r.code === "AS003" || r.code === "AS005" ? m.index : ""}`;
      if (seenLine.has(key)) continue;    // identical match twice on one line counts once (except emoji and copy)
      seenLine.add(key);
      hits.get(r.code).push({ at, text: m[0].replace(/\s+/g, " ").slice(0, 40) });
    }
  }
  for (const m of text.matchAll(/linear-gradient\(([^;]*?)\)\s*[;"'}]/g)) if (purpleGradient(m[1])) hits.get("AS002").push({ at: `${rel}:${lineAt(m.index)}`, text: "linear-gradient (purple hue)" });
  for (const m of text.matchAll(/font-family\s*:\s*([^;}{]+)/g)) { fontDecl++; if (/^\s*["']?(?:inter|system-ui|-apple-system|ui-sans-serif|sans-serif)\b/i.test(m[1])) defaultFontDecl++; }
  for (const m of text.matchAll(/\bfont-\[['"]?([\w ]+)/g)) { fontDecl++; if (/^inter$/i.test(m[1].trim())) defaultFontDecl++; }
  if (/fonts\.googleapis\.com\/css2?\?family=Inter\b/.test(text)) { fontDecl++; defaultFontDecl++; }
  threeCols += (text.match(/\bgrid-cols-3\b|\bmd:grid-cols-3\b|\blg:grid-cols-3\b/g) ?? []).length;
}
if (fontDecl === 0 || defaultFontDecl === fontDecl) hits.get("AS014").push({ at: "(project)", text: fontDecl ? "Inter/system fonts only" : "no font choice found" });

const findings = [];
let score = 0;
for (const r of RULES) {
  const h = hits.get(r.code);
  if (!h.length || h.length < (r.min ?? 1)) continue;
  if (r.code === "AS013" && threeCols === 0) continue;
  if (r.all && h.length / Math.max(totals.get(r.code), h.length) < 0.5) continue;   // big radius/shadow is not the default
  const weight = r.w * Math.min(1 + Math.log2(h.length) / 3, 2);    // more uses -> heavier, capped at 2x
  score += weight;
  findings.push({ code: r.code, pattern: r.name, count: h.length, weight: Math.round(weight * 10) / 10, examples: h.slice(0, 4) });
}
const maxScore = RULES.reduce((s, r) => s + r.w * 2, 0) * 0.55;    // a page hitting about half the rules heavily = 100
score = Math.min(100, Math.round((100 * score) / maxScore));
const verdict = score < 15 ? "clean: no strong AI-template signals" : score < 35 ? "noticeable: some template defaults to replace"
  : score < 60 ? "heavy: reads as AI-generated; redesign foundations" : "severe: template look throughout; rebuild the visual system";
findings.sort((a, b) => b.weight - a.weight);

if (asJson) console.log(JSON.stringify({ files: files.length, score, verdict, findings }, null, 2));
else {
  for (const f of findings) console.log(`${f.code} [${f.pattern}] x${f.count}: ${f.examples.map((e) => `${e.at} "${e.text}"`).join("; ")}`);
  console.log(`\n${files.length} file(s). Slop score ${score}/100: ${verdict}`);
}
process.exit(score > max ? 1 : 0);
