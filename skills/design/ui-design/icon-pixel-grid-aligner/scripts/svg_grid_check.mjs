#!/usr/bin/env node
// Check SVG icons for pixel-grid alignment and icon-set consistency.
//
// Crisp edges at 1x need horizontal and vertical edges on the pixel grid:
//   filled shapes        edges on whole pixels (x = 4, not 4.5)
//   odd stroke widths    stroke centre on half pixels (1px stroke at x = 4.5)
//   even stroke widths   stroke centre on whole pixels (2px stroke at x = 4)
// Only axis-aligned segments are checked (H, V, and L/Z segments that are horizontal or vertical, rect edges,
// axis-aligned lines and polyline/polygon segments); curves are judged by eye.
//
// Findings:
//   IG001 warn  viewBox missing, not starting at 0 0, or not the expected --grid size
//   IG002 warn  axis-aligned edge off the pixel grid (blurs at 1x), with the coordinate and the snapped value
//   IG003 warn  stroke width differs from --stroke, or is fractional (blurs at 1x)
//   IG004 warn  transform attribute (moves geometry off-grid in ways the file doesn't show)
//   IG005 warn  geometry outside the live area (--padding from each edge) or outside the viewBox
//   IG006 info  coordinates with more than 2 decimals (export noise)
//   IG007 warn  icon set mixes stroke caps or joins
//
// Usage:
//   node svg_grid_check.mjs icon.svg | icons/ [--grid 24] [--stroke 2] [--padding 2] [--json]
// Exit codes: 0 no warnings, 1 warnings, 2 bad arguments, no SVG files or unparsable path data.

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { basename, extname, join } from "node:path";

const HELP = `usage: node svg_grid_check.mjs PATH [PATH...] [--grid 24] [--stroke W] [--padding P] [--json]
Check SVG icons for off-grid edges, stroke width, viewBox, transforms, live area and set consistency.`;
const argv = process.argv.slice(2);
if (!argv.length || argv.includes("-h") || argv.includes("--help")) { console.log(HELP); process.exit(argv.length ? 0 : 2); }
const fail = (m) => { console.error(`error: ${m}`); process.exit(2); };
const inputs = [];
let grid = 24, stroke = null, padding = null, asJson = false;
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === "--grid") grid = Number(argv[++i]);
  else if (a === "--stroke") stroke = Number(argv[++i]);
  else if (a === "--padding") padding = Number(argv[++i]);
  else if (a === "--json") asJson = true;
  else if (a.startsWith("--")) fail(`unknown option ${a}`);
  else inputs.push(a);
}
if (!(grid > 0) || (stroke !== null && !(stroke > 0)) || (padding !== null && !(padding >= 0))) fail("--grid, --stroke and --padding need positive numbers");

const files = [];
for (const p of inputs) {
  if (!existsSync(p)) fail(`${p} does not exist`);
  if (statSync(p).isDirectory()) for (const n of readdirSync(p).sort()) { if (extname(n) === ".svg") files.push(join(p, n)); }
  else files.push(p);
}
if (!files.length) fail("no .svg files found");

const attr = (tag, name) => { const m = new RegExp(`(?:^|\\s)${name}\\s*=\\s*["']([^"']*)["']`).exec(tag); return m ? m[1] : null; };
const styleProp = (tag, name) => { const s = attr(tag, "style"); const m = s && new RegExp(`${name}\\s*:\\s*([^;]+)`).exec(s); return m ? m[1].trim() : null; };
const prop = (tag, name) => attr(tag, name) ?? styleProp(tag, name);
const near = (a, b) => Math.abs(a - b) < 1e-3;
const frac = (v) => ((v % 1) + 1) % 1;

// Parse path data into axis-aligned segments [{axis:"x"|"y", value}] and all points.
function pathSegments(d) {
  const tokens = d.match(/[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?/g) ?? [];
  const segs = [], points = [];
  let i = 0, cmd = null, x = 0, y = 0, sx = 0, sy = 0;
  const num = () => { const v = Number(tokens[i++]); if (!Number.isFinite(v)) throw new Error(`bad path data near '${tokens[i - 1]}'`); return v; };
  const line = (nx, ny) => {
    if (near(x, nx) && !near(y, ny)) segs.push({ axis: "x", value: nx });
    else if (near(y, ny) && !near(x, nx)) segs.push({ axis: "y", value: ny });
    x = nx; y = ny; points.push([x, y]);
  };
  const ARGS = { M: 2, L: 2, H: 1, V: 1, C: 6, S: 4, Q: 4, T: 2, A: 7, Z: 0 };
  if (tokens.length && !/^[Mm]$/.test(tokens[0])) throw new Error(`path data must start with M, found '${tokens[0]}'`);
  while (i < tokens.length) {
    if (/[A-Za-z]/.test(tokens[i])) cmd = tokens[i++];
    else if (!cmd) throw new Error("path data must start with a command");
    const C = cmd.toUpperCase(), rel = cmd !== C;
    if (C === "Z") { line(sx, sy); continue; }
    if (i + ARGS[C] > tokens.length) throw new Error(`incomplete ${cmd} command`);
    if (C === "M") { x = num() + (rel ? x : 0); y = num() + (rel ? y : 0); sx = x; sy = y; points.push([x, y]); cmd = rel ? "l" : "L"; }
    else if (C === "L" || C === "T") { const nx = num() + (rel ? x : 0), ny = num() + (rel ? y : 0); C === "L" ? line(nx, ny) : (x = nx, y = ny, points.push([x, y])); }
    else if (C === "H") line(num() + (rel ? x : 0), y);
    else if (C === "V") line(x, num() + (rel ? y : 0));
    else {
      const vals = Array.from({ length: ARGS[C] }, num);
      if (C !== "A") for (let k = 0; k < vals.length - 2; k += 2) points.push([vals[k] + (rel ? x : 0), vals[k + 1] + (rel ? y : 0)]);
      x = vals[vals.length - 2] + (rel ? x : 0); y = vals[vals.length - 1] + (rel ? y : 0); points.push([x, y]);
    }
  }
  return { segs, points };
}

const results = [];
const caps = new Map(), joins = new Map();
for (const f of files) {
  const text = readFileSync(f, "utf8");
  const findings = [];
  const add = (code, severity, message) => findings.push({ code, severity, message });
  const svgTag = /<svg\b[^>]*>/i.exec(text)?.[0];
  if (!svgTag) { results.push({ file: f, findings: [{ code: "IG001", severity: "warn", message: "no <svg> element" }] }); continue; }
  const vb = (attr(svgTag, "viewBox") ?? "").trim().split(/[\s,]+/).map(Number);
  let [vx, vy, vw, vh] = vb.length === 4 && vb.every(Number.isFinite) ? vb : [0, 0, Number(attr(svgTag, "width")), Number(attr(svgTag, "height"))];
  if (vb.length !== 4) add("IG001", "warn", `no viewBox; use viewBox="0 0 ${grid} ${grid}"`);
  else if (vx !== 0 || vy !== 0 || vw !== grid || vh !== grid) add("IG001", "warn", `viewBox "${vb.join(" ")}" should be "0 0 ${grid} ${grid}"`);
  if (!(vw > 0)) { vw = grid; vh = grid; }
  const rootStroke = prop(svgTag, "stroke"), rootWidth = prop(svgTag, "stroke-width");
  const offGrid = new Map(), widths = new Set();
  let decimals = 0, minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const track = ([px, py], halfStroke) => {
    minX = Math.min(minX, px - halfStroke); minY = Math.min(minY, py - halfStroke);
    maxX = Math.max(maxX, px + halfStroke); maxY = Math.max(maxY, py + halfStroke);
  };
  if (/\stransform\s*=/.test(text.replace(svgTag, ""))) add("IG004", "warn", "transform attribute found: flatten transforms into the path data");
  for (const m of text.matchAll(/<(path|rect|line|polyline|polygon|circle|ellipse)\b[^>]*>/gi)) {
    const tag = m[0], kind = m[1].toLowerCase();
    const strokeVal = prop(tag, "stroke") ?? rootStroke;
    const stroked = strokeVal && strokeVal !== "none";
    const w = stroked ? Number(prop(tag, "stroke-width") ?? rootWidth ?? 1) : 0;
    if (stroked) {
      widths.add(w);
      const cap = prop(tag, "stroke-linecap") ?? prop(svgTag, "stroke-linecap") ?? "butt";
      const join = prop(tag, "stroke-linejoin") ?? prop(svgTag, "stroke-linejoin") ?? "miter";
      caps.set(cap, (caps.get(cap) ?? new Set()).add(basename(f)));
      joins.set(join, (joins.get(join) ?? new Set()).add(basename(f)));
    }
    const want = !stroked ? 0 : Number.isInteger(w) ? (w % 2 ? 0.5 : 0) : null;   // null: fractional stroke, can't align
    let segs = [], points = [];
    try {
      if (kind === "path") ({ segs, points } = pathSegments(attr(tag, "d") ?? ""));
      else if (kind === "rect") {
        const [rx, ry, rw, rh] = ["x", "y", "width", "height"].map((k) => Number(attr(tag, k) ?? 0));
        segs = [{ axis: "x", value: rx }, { axis: "x", value: rx + rw }, { axis: "y", value: ry }, { axis: "y", value: ry + rh }];
        points = [[rx, ry], [rx + rw, ry + rh]];
      } else if (kind === "line") {
        const [x1, y1, x2, y2] = ["x1", "y1", "x2", "y2"].map((k) => Number(attr(tag, k) ?? 0));
        if (near(x1, x2)) segs.push({ axis: "x", value: x1 }); else if (near(y1, y2)) segs.push({ axis: "y", value: y1 });
        points = [[x1, y1], [x2, y2]];
      } else if (kind === "polyline" || kind === "polygon") {
        const n = (attr(tag, "points") ?? "").trim().split(/[\s,]+/).map(Number);
        const d = n.reduce((s, v, k) => s + (k % 2 ? ` ${v}` : ` ${k ? "L" : "M"}${v}`), "") + (kind === "polygon" ? " Z" : "");
        ({ segs, points } = pathSegments(d));
      } else {
        const cx = Number(attr(tag, "cx") ?? 0), cy = Number(attr(tag, "cy") ?? 0);
        const rx = Number(attr(tag, "r") ?? attr(tag, "rx") ?? 0), ry = Number(attr(tag, "r") ?? attr(tag, "ry") ?? 0);
        points = [[cx - rx, cy - ry], [cx + rx, cy + ry]];
      }
    } catch (e) { console.error(`error: ${f}: ${e.message}`); process.exit(2); }
    for (const p of points) {
      track(p, w / 2);
      for (const v of p) if (/\.\d{3,}/.test(String(v))) decimals++;
    }
    if (want === null) continue;
    for (const s of segs) if (!near(frac(s.value), want)) {
      const snapped = Math.round(s.value - want) + want;
      offGrid.set(`${s.axis}=${+s.value.toFixed(3)}`, `${s.axis}=${+s.value.toFixed(3)} -> ${snapped}`);
    }
  }
  if (offGrid.size) add("IG002", "warn", `${offGrid.size} off-grid edge(s): ${[...offGrid.values()].slice(0, 6).join(", ")}${offGrid.size > 6 ? ", ..." : ""}`);
  for (const w of widths) {
    if (!Number.isInteger(w)) add("IG003", "warn", `fractional stroke width ${w}: edges can't sit on the pixel grid at 1x`);
    else if (stroke !== null && w !== stroke) add("IG003", "warn", `stroke width ${w}, set uses ${stroke}`);
  }
  if (Number.isFinite(minX)) {
    if (minX < vx - 1e-3 || minY < vy - 1e-3 || maxX > vx + vw + 1e-3 || maxY > vy + vh + 1e-3)
      add("IG005", "warn", `geometry extends outside the viewBox (${+minX.toFixed(2)},${+minY.toFixed(2)} to ${+maxX.toFixed(2)},${+maxY.toFixed(2)})`);
    else if (padding !== null && (minX < padding - 1e-3 || minY < padding - 1e-3 || maxX > vw - padding + 1e-3 || maxY > vh - padding + 1e-3))
      add("IG005", "warn", `geometry outside the ${vw - 2 * padding}px live area (padding ${padding})`);
  }
  if (decimals) add("IG006", "info", `${decimals} coordinate(s) with 3+ decimals: round to 2 or snap`);
  results.push({ file: f, findings });
}
const setFindings = [];
if (files.length > 1) {
  if (caps.size > 1) setFindings.push({ code: "IG007", severity: "warn", message: `mixed stroke caps: ${[...caps].map(([k, v]) => `${k} (${v.size})`).join(", ")}` });
  if (joins.size > 1) setFindings.push({ code: "IG007", severity: "warn", message: `mixed stroke joins: ${[...joins].map(([k, v]) => `${k} (${v.size})`).join(", ")}` });
}

const warns = results.reduce((s, r) => s + r.findings.filter((x) => x.severity === "warn").length, 0) + setFindings.length;
if (asJson) console.log(JSON.stringify({ grid, files: results, set: setFindings }, null, 2));
else {
  for (const r of results) {
    console.log(`${r.file}: ${r.findings.length ? "" : "ok"}`);
    for (const x of r.findings) console.log(`  ${x.code} [${x.severity}] ${x.message}`);
  }
  for (const x of setFindings) console.log(`SET ${x.code} [${x.severity}] ${x.message}`);
  console.log(`\n${files.length} icon(s), ${warns} warning(s)`);
}
process.exit(warns ? 1 : 0);
