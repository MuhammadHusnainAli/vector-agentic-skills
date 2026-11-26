#!/usr/bin/env node
// Lint W3C Design Tokens (DTCG) JSON: aliases, cycles, types, tiers and mode parity.
//
// Accepts one or more token files; they are merged in order (later files override earlier ones), so pass
// the primitive file first and theme files after it. Works with the DTCG 2025.10 object values
// ({colorSpace, components} colours, {value, unit} dimensions) and the older string values.
//
// Checks:
//   TK001 error  alias points to a token that does not exist
//   TK002 error  alias cycle
//   TK003 error  node has $value and child tokens, or a token has no $value
//   TK004 error  invalid value for its $type (colour, dimension, duration, fontWeight, number, cubicBezier)
//   TK005 warn   alias resolves to a token of a different $type
//   TK006 warn   tier skip: component token references a primitive directly (bypasses the semantic layer)
//   TK007 warn   hard-coded value in the semantic or component tier (should be an alias)
//   TK008 warn   primitive token aliases another tier (primitives hold raw values only)
//   TK009 warn   invalid token or group name (starts with $, contains { } or .)
//   TK010 warn   token missing from one mode file (with --modes)
//   TK011 info   primitive never referenced
//
// Tiers come from the first path segment: primitive|primitives|core|base|ref|palette, semantic|sys|system|
// alias|theme, component|components|comp. Override with --tiers "primitive=core;semantic=sys;component=cmp".
//
// Usage:
//   node token_lint.mjs core.json light.json
//   node token_lint.mjs core.json semantic.json --modes light.json dark.json
//   node token_lint.mjs tokens.json --json
// Exit codes: 0 no errors, 1 errors (or warnings with --strict), 2 bad arguments or unreadable JSON.

import { readFileSync } from "node:fs";

const HELP = `usage: node token_lint.mjs FILE [FILE...] [--modes A.json B.json ...] [--tiers SPEC] [--json] [--strict]
Lint W3C design token (DTCG) files for broken aliases, cycles, invalid values, type mismatches,
tier violations and mode parity. Exit 0 clean, 1 errors, 2 bad input.`;

const args = process.argv.slice(2);
if (!args.length || args.includes("-h") || args.includes("--help")) { console.log(HELP); process.exit(args.length ? 0 : 2); }

const files = [], modes = [];
let asJson = false, strict = false, tierSpec = "";
for (let i = 0, target = files; i < args.length; i++) {
  const a = args[i];
  if (a === "--json") asJson = true;
  else if (a === "--strict") strict = true;
  else if (a === "--modes") target = modes;
  else if (a === "--tiers") tierSpec = args[++i] ?? "";
  else if (a.startsWith("--")) { console.error(`error: unknown option ${a}`); process.exit(2); }
  else target.push(a);
}

const TIERS = { primitive: ["primitive", "primitives", "core", "base", "ref", "palette"],
  semantic: ["semantic", "sys", "system", "alias", "theme"], component: ["component", "components", "comp"] };
for (const part of tierSpec.split(";").filter(Boolean)) {
  const [tier, names] = part.split("=");
  if (!TIERS[tier]) { console.error(`error: unknown tier '${tier}' in --tiers`); process.exit(2); }
  TIERS[tier] = names.split(",").map((s) => s.trim());
}
const tierOf = (path) => Object.keys(TIERS).find((t) => TIERS[t].includes(path.split(".")[0])) ?? null;

function load(file) {
  try { return JSON.parse(readFileSync(file, "utf8")); }
  catch (e) { console.error(`error: ${file}: ${e.message}`); process.exit(2); }
}

const findings = [];
const add = (code, severity, path, message) => findings.push({ code, severity, path, message });

// Flatten a token tree into Map(path -> {value, type}); $type inherits from parent groups.
function flatten(tree, file, out = new Map(), prefix = "", inherited = undefined) {
  if (typeof tree !== "object" || tree === null || Array.isArray(tree)) return out;
  const type = tree.$type ?? inherited;
  const children = Object.keys(tree).filter((k) => !k.startsWith("$"));
  if ("$value" in tree) {
    if (children.length) add("TK003", "error", prefix, `has $value and child tokens (${children.slice(0, 3).join(", ")})`);
    out.set(prefix, { value: tree.$value, type, file });
    return out;
  }
  for (const k of children) {
    const path = prefix ? `${prefix}.${k}` : k;
    if (/[{}.]/.test(k)) add("TK009", "warn", path, `name '${k}' contains { } or .`);
    const child = tree[k];
    if (typeof child !== "object" || child === null) { add("TK003", "error", path, "not a group and has no $value"); continue; }
    flatten(child, file, out, path, type);
  }
  return out;
}

const ALIAS = /^\{([^{}]+)\}$/;
const aliasOf = (v) => (typeof v === "string" && ALIAS.test(v.trim()) ? v.trim().slice(1, -1) : null);
const COLOR_STR = /^(#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})|(rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)\(.+\))$/i;
const DIM_STR = /^-?\d*\.?\d+(px|rem)$|^0$/;
const DUR_STR = /^\d*\.?\d+(ms|s)$/;
const WEIGHTS = ["thin", "hairline", "extra-light", "ultra-light", "light", "normal", "regular", "book", "medium",
  "semi-bold", "demi-bold", "bold", "extra-bold", "ultra-bold", "black", "heavy", "extra-black", "ultra-black"];

function validValue(type, v) {
  if (aliasOf(v) || typeof v === "object" && v !== null && Object.values(v).some((x) => aliasOf(x))) return true;
  switch (type) {
    case "color": return typeof v === "string" ? COLOR_STR.test(v.trim())
      : typeof v === "object" && v !== null && typeof v.colorSpace === "string" && Array.isArray(v.components);
    case "dimension": return typeof v === "string" ? DIM_STR.test(v.trim())
      : typeof v === "object" && v !== null && typeof v.value === "number" && ["px", "rem"].includes(v.unit);
    case "duration": return typeof v === "string" ? DUR_STR.test(v.trim())
      : typeof v === "object" && v !== null && typeof v.value === "number" && ["ms", "s"].includes(v.unit);
    case "fontWeight": return (typeof v === "number" && v >= 1 && v <= 1000) || WEIGHTS.includes(v);
    case "number": return typeof v === "number";
    case "cubicBezier": return Array.isArray(v) && v.length === 4 && v.every((n) => typeof n === "number")
      && v[0] >= 0 && v[0] <= 1 && v[2] >= 0 && v[2] <= 1;
    default: return true;
  }
}

const tokens = new Map();
for (const f of files) for (const [k, t] of flatten(load(f), f)) tokens.set(k, t);
if (!tokens.size) { console.error("error: no tokens found"); process.exit(2); }

// Resolve aliases with cycle detection; returns the final token or null.
function resolve(path, seen = []) {
  if (seen.includes(path)) return { cycle: [...seen, path] };
  const t = tokens.get(path);
  if (!t) return { missing: path };
  const target = aliasOf(t.value);
  return target ? resolve(target, [...seen, path]) : { token: t, depth: seen.length };
}

const referenced = new Set();
const reportedCycles = new Set();
let maxDepth = 0;
for (const [path, t] of tokens) {
  const tier = tierOf(path);
  const target = aliasOf(t.value);
  if (!target) {
    if (!validValue(t.type, t.value)) add("TK004", "error", path, `invalid ${t.type} value ${JSON.stringify(t.value)}`);
    if (tier === "semantic" || tier === "component") add("TK007", "warn", path, `hard-coded ${JSON.stringify(t.value)} in the ${tier} tier: alias a primitive`);
    continue;
  }
  referenced.add(target);
  const targetTier = tierOf(target);
  if (tier === "component" && targetTier === "primitive") add("TK006", "warn", path, `references primitive {${target}} directly: go through a semantic token`);
  if (tier === "primitive" && targetTier && targetTier !== "primitive") add("TK008", "warn", path, `primitive aliases the ${targetTier} tier {${target}}`);
  const r = resolve(path);
  if (r.cycle) {
    const key = [...new Set(r.cycle)].sort().join("|");
    if (!reportedCycles.has(key)) { reportedCycles.add(key); add("TK002", "error", path, `cycle: ${r.cycle.join(" -> ")}`); }
    continue;
  }
  if (r.missing) { add("TK001", "error", path, `alias {${target}} not found${r.missing !== target ? ` (chain breaks at {${r.missing}})` : ""}`); continue; }
  maxDepth = Math.max(maxDepth, r.depth);
  if (t.type && r.token.type && t.type !== r.token.type) add("TK005", "warn", path, `is ${t.type} but resolves to a ${r.token.type}`);
}

if (modes.length > 1) {
  const sets = modes.map((m) => ({ file: m, keys: new Set(flatten(load(m), m).keys()) }));
  const all = new Set(sets.flatMap((s) => [...s.keys]));
  for (const key of all) {
    const missingIn = sets.filter((s) => !s.keys.has(key)).map((s) => s.file);
    if (missingIn.length) add("TK010", "warn", key, `missing in mode file(s): ${missingIn.join(", ")}`);
  }
  for (const s of sets) for (const [k, t] of flatten(load(s.file), s.file)) {
    const target = aliasOf(t.value);
    if (target) { referenced.add(target); if (!tokens.has(target)) add("TK001", "error", k, `alias {${target}} (in ${s.file}) not found`); }
  }
}

for (const [path] of tokens) if (tierOf(path) === "primitive" && !referenced.has(path)) add("TK011", "info", path, "primitive never referenced");

const order = { error: 0, warn: 1, info: 2 };
findings.sort((a, b) => order[a.severity] - order[b.severity] || a.code.localeCompare(b.code) || a.path.localeCompare(b.path));
const count = (s) => findings.filter((f) => f.severity === s).length;
const byTier = Object.fromEntries([...Object.keys(TIERS), "untiered"].map((t) => [t, 0]));
for (const [p] of tokens) byTier[tierOf(p) ?? "untiered"]++;

if (asJson) console.log(JSON.stringify({ tokens: tokens.size, tiers: byTier, maxAliasDepth: maxDepth, findings }, null, 2));
else {
  for (const f of findings) console.log(`${f.code} [${f.severity}] ${f.path}: ${f.message}`);
  console.log(`\n${tokens.size} tokens (${Object.entries(byTier).map(([k, v]) => `${k} ${v}`).join(", ")}), max alias depth ${maxDepth}`);
  console.log(`${count("error")} error(s), ${count("warn")} warning(s), ${count("info")} info`);
}
process.exit(count("error") || (strict && count("warn")) ? 1 : 0);
