#!/usr/bin/env node
// Contrast matrix for a light/dark palette: WCAG 2 ratio and APCA Lc for every declared pair in every mode,
// plus OKLCH values for each colour.
//
// Input JSON:
//   { "modes": { "light": { "text.default": "#0f172a", "surface.default": "#ffffff", ... },
//                "dark":  { "text.default": "#e2e8f0", "surface.default": "#0b1220", ... } },
//     "pairs": [ ["text.default", "surface.default", "body"],
//                ["border.default", "surface.default", "non-text"] ] }
// Pair kinds and thresholds (WCAG 2.x / APCA Lc):
//   body 4.5 / 75     large 3 / 60     non-text 3 / 45     incidental (reported only)
// Colours: #rgb, #rrggbb, #rrggbbaa (alpha composited over the pair's background), rgb(r g b) / rgb(r,g,b).
//
// Findings:
//   DM001 error  pair below the WCAG 2 threshold for its kind
//   DM002 warn   pair below the APCA threshold (reported always; affects exit code with --apca)
//   DM003 error  token used in a pair is missing in a mode
//   DM004 info   pure black (#000) surface in dark mode: smearing on OLED, harsh contrast; use a dark grey
//   DM005 info   pure white text on a very dark surface in dark mode: halation for many readers; soften slightly
//   DM006 info   highly saturated colour (OKLCH C > 0.18) used as dark-mode text: vibrates on dark backgrounds
//
// Usage:
//   node contrast_matrix.mjs palette.json [--apca] [--json]
// Exit codes: 0 all pairs pass, 1 failures, 2 bad input.

import { readFileSync } from "node:fs";

const HELP = `usage: node contrast_matrix.mjs palette.json [--apca] [--json]
WCAG 2 contrast ratio, APCA Lc and OKLCH for every text/surface pair in every mode of a palette.
Exit 0 all pass, 1 failures (WCAG; APCA too with --apca), 2 bad input.`;
const argv = process.argv.slice(2);
if (!argv.length || argv.includes("-h") || argv.includes("--help")) { console.log(HELP); process.exit(argv.length ? 0 : 2); }
const fail = (m) => { console.error(`error: ${m}`); process.exit(2); };
const file = argv.find((a) => !a.startsWith("--"));
const useApca = argv.includes("--apca"), asJson = argv.includes("--json");
const unknown = argv.filter((a) => a.startsWith("--") && !["--apca", "--json"].includes(a));
if (unknown.length) fail(`unknown option ${unknown[0]}`);
if (!file) fail("give a palette JSON file");
let spec;
try { spec = JSON.parse(readFileSync(file, "utf8")); } catch (e) { fail(`${file}: ${e.message}`); }
if (!spec?.modes || typeof spec.modes !== "object" || !Array.isArray(spec.pairs)) fail("palette needs 'modes' {mode: {token: colour}} and 'pairs' [[fg, bg, kind]]");

const KINDS = { body: [4.5, 75], large: [3, 60], "non-text": [3, 45], incidental: [0, 0] };

function parse(c) {
  const s = String(c).trim().toLowerCase();
  let m = /^#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/.exec(s);
  if (m) {
    let h = m[1];
    if (h.length <= 4) h = [...h].map((x) => x + x).join("");
    return { r: parseInt(h.slice(0, 2), 16), g: parseInt(h.slice(2, 4), 16), b: parseInt(h.slice(4, 6), 16), a: h.length === 8 ? parseInt(h.slice(6, 8), 16) / 255 : 1 };
  }
  m = /^rgba?\(\s*(\d+(?:\.\d+)?)[\s,]+(\d+(?:\.\d+)?)[\s,]+(\d+(?:\.\d+)?)(?:\s*[,/]\s*(\d*\.?\d+)(%?))?\s*\)$/.exec(s);
  if (m) return { r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : m[5] ? +m[4] / 100 : +m[4] };
  return null;
}
const over = (fg, bg) => ({ r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a), b: fg.b * fg.a + bg.b * (1 - fg.a), a: 1 });
const lin = (v) => { const c = v / 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
const luminance = ({ r, g, b }) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
const wcag = (a, b) => { const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };

// APCA-W3 0.0.98G-4g (text colour first, background second); returns Lc (positive: dark on light).
function apca(txt, bg) {
  const Y = ({ r, g, b }) => 0.2126729 * (r / 255) ** 2.4 + 0.7151522 * (g / 255) ** 2.4 + 0.072175 * (b / 255) ** 2.4;
  const clamp = (y) => (y > 0.022 ? y : y + (0.022 - y) ** 1.414);
  const yt = clamp(Y(txt)), yb = clamp(Y(bg));
  if (Math.abs(yb - yt) < 0.0005) return 0;
  if (yb > yt) { const s = (yb ** 0.56 - yt ** 0.57) * 1.14; return s < 0.1 ? 0 : (s - 0.027) * 100; }
  const s = (yb ** 0.65 - yt ** 0.62) * 1.14; return s > -0.1 ? 0 : (s + 0.027) * 100;
}

function oklch({ r, g, b }) {
  const [R, G, B] = [lin(r), lin(g), lin(b)];
  const l = Math.cbrt(0.4122214708 * R + 0.5363325363 * G + 0.0514459929 * B);
  const m = Math.cbrt(0.2119034982 * R + 0.6806995451 * G + 0.1073969566 * B);
  const s = Math.cbrt(0.0883024619 * R + 0.2817188376 * G + 0.6299787005 * B);
  const L = 0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s;
  const A = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s;
  const Bb = 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s;
  const C = Math.hypot(A, Bb);
  return { L, C, h: C < 1e-4 ? 0 : ((Math.atan2(Bb, A) * 180) / Math.PI + 360) % 360 };
}
const fmtOk = (o) => `oklch(${(o.L * 100).toFixed(1)}% ${o.C.toFixed(3)} ${o.h.toFixed(0)})`;

const findings = [], rows = [];
const add = (code, severity, mode, message) => findings.push({ code, severity, mode, message });
for (const [mode, colours] of Object.entries(spec.modes)) {
  for (const [token, value] of Object.entries(colours)) if (!parse(value)) fail(`${mode}.${token}: unreadable colour '${value}'`);
  const dark = /dark|night|dim/i.test(mode);
  for (const pair of spec.pairs) {
    const [fgName, bgName, kind = "body"] = pair;
    if (!KINDS[kind]) fail(`pair ${fgName} / ${bgName}: unknown kind '${kind}' (body, large, non-text, incidental)`);
    const missing = [fgName, bgName].filter((t) => !(t in colours));
    if (missing.length) { add("DM003", "error", mode, `${missing.join(", ")} missing in ${mode}`); continue; }
    const bg = over(parse(colours[bgName]), { r: dark ? 0 : 255, g: dark ? 0 : 255, b: dark ? 0 : 255, a: 1 });
    const fg = over(parse(colours[fgName]), bg);
    const ratio = wcag(fg, bg), lc = apca(fg, bg);
    const [minRatio, minLc] = KINDS[kind];
    const okW = ratio + 1e-9 >= minRatio, okA = Math.abs(lc) + 1e-9 >= minLc;
    rows.push({ mode, fg: fgName, bg: bgName, kind, ratio: Math.floor(ratio * 100) / 100, lc: Math.round(lc * 10) / 10, wcag: okW, apca: okA });
    if (!okW) add("DM001", "error", mode, `${fgName} on ${bgName} (${kind}): ${(Math.floor(ratio * 100) / 100).toFixed(2)}:1, needs ${minRatio}:1`);
    if (!okA) add("DM002", "warn", mode, `${fgName} on ${bgName} (${kind}): APCA Lc ${Math.abs(lc).toFixed(1)}, needs ${minLc}`);
    if (dark && kind !== "non-text") {
      const fgOk = oklch(fg), bgOk = oklch(bg);
      if (fg.r === 255 && fg.g === 255 && fg.b === 255 && bgOk.L < 0.25) add("DM005", "info", mode, `${fgName} is pure white on ${bgName}: try about 90% lightness to reduce halation`);
      if (fgOk.C > 0.18) add("DM006", "info", mode, `${fgName} has chroma ${fgOk.C.toFixed(3)}: desaturate text colours for dark surfaces`);
    }
  }
  if (dark) for (const [t, v] of Object.entries(colours)) {
    const c = parse(v);
    if (/surface|background|bg|canvas/i.test(t) && c.r === 0 && c.g === 0 && c.b === 0 && c.a === 1) add("DM004", "info", mode, `${t} is pure black: use a dark grey (e.g. oklch(18% 0.01 h)) and lighten raised surfaces`);
  }
}
const uniq = [...new Map(findings.map((f) => [`${f.code}|${f.mode}|${f.message}`, f])).values()];
const errors = uniq.filter((f) => f.severity === "error").length, apcaFails = uniq.filter((f) => f.code === "DM002").length;

if (asJson) {
  const colours = Object.fromEntries(Object.entries(spec.modes).map(([m, cs]) => [m, Object.fromEntries(Object.entries(cs).map(([t, v]) => [t, fmtOk(oklch(parse(v)))]))]));
  console.log(JSON.stringify({ rows, oklch: colours, findings: uniq }, null, 2));
} else {
  for (const mode of Object.keys(spec.modes)) {
    console.log(`## ${mode}\n\n| Foreground | Background | Kind | WCAG | APCA Lc | Result |\n|---|---|---|---|---|---|`);
    for (const r of rows.filter((x) => x.mode === mode))
      console.log(`| ${r.fg} | ${r.bg} | ${r.kind} | ${r.ratio.toFixed(2)}:1 | ${r.lc} | ${r.wcag ? (r.apca ? "pass" : "pass (APCA low)") : "FAIL"} |`);
    console.log("\n| Token | Value | OKLCH |\n|---|---|---|");
    for (const [t, v] of Object.entries(spec.modes[mode])) console.log(`| ${t} | ${v} | ${fmtOk(oklch(parse(v)))} |`);
    console.log("");
  }
  for (const f of uniq) console.log(`${f.code} [${f.severity}] ${f.mode}: ${f.message}`);
  console.log(`\n${rows.length} pair checks, ${errors} error(s), ${apcaFails} APCA warning(s)`);
}
process.exit(errors || (useApca && apcaFails) ? 1 : 0);
