#!/usr/bin/env node
// Compare a design export and an implementation screenshot pixel by pixel.
//
// Decodes 8-bit PNGs (greyscale, RGB, palette, grey+alpha, RGBA; non-interlaced) with node:zlib, composites
// transparency over white, and counts pixels whose largest channel difference exceeds --tolerance. Differences are
// grouped into regions (8x8 px cells joined with their neighbours) and reported as bounding boxes, largest first;
// regions smaller than --min-region pixels are treated as anti-aliasing noise.
//
// Findings:
//   VD001 warn  image sizes differ (only the overlapping area is compared): check export scale / device pixel ratio
//   VD002 warn  difference region with its box, pixel count and the average colour in each image
//   VD003 info  noise ignored (tiny regions under --min-region)
//
// Usage:
//   node png_diff.mjs design.png build.png [--tolerance 16] [--min-region 4] [--max 0.1] [--out diff.png] [--json]
// Exit codes: 0 mismatch <= --max percent (default 0) and sizes match, 1 otherwise, 2 bad arguments or unreadable PNG.

import { readFileSync, writeFileSync } from "node:fs";
import { deflateSync, inflateSync } from "node:zlib";

const HELP = `usage: node png_diff.mjs DESIGN.png BUILD.png [--tolerance 16] [--min-region 4] [--max PCT] [--out diff.png] [--json]
Pixel diff of two PNGs: mismatch %, difference regions with boxes and colours, optional diff image.`;
const argv = process.argv.slice(2);
if (!argv.length || argv.includes("-h") || argv.includes("--help")) { console.log(HELP); process.exit(argv.length ? 0 : 2); }
const fail = (m) => { console.error(`error: ${m}`); process.exit(2); };
const files = [];
let tolerance = 16, minRegion = 4, maxPct = 0, out = null, asJson = false;
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === "--tolerance") tolerance = Number(argv[++i]);
  else if (a === "--min-region") minRegion = Number(argv[++i]);
  else if (a === "--max") maxPct = Number(argv[++i]);
  else if (a === "--out") out = argv[++i];
  else if (a === "--json") asJson = true;
  else if (a.startsWith("--")) fail(`unknown option ${a}`);
  else files.push(a);
}
if (files.length !== 2) fail("give exactly two PNG files: the design export and the screenshot");
if (!(tolerance >= 0 && tolerance <= 255) || !(minRegion >= 0) || !(maxPct >= 0)) fail("--tolerance 0-255, --min-region >= 0, --max >= 0");

function decode(path) {
  let buf;
  try { buf = readFileSync(path); } catch (e) { fail(`${path}: ${e.message}`); }
  if (buf.length < 8 || buf.readUInt32BE(0) !== 0x89504e47) fail(`${path}: not a PNG file`);
  let pos = 8, ihdr = null, palette = null, trns = null;
  const idat = [];
  while (pos + 8 <= buf.length) {
    const len = buf.readUInt32BE(pos), type = buf.toString("latin1", pos + 4, pos + 8), data = buf.subarray(pos + 8, pos + 8 + len);
    if (type === "IHDR") ihdr = { w: data.readUInt32BE(0), h: data.readUInt32BE(4), depth: data[8], color: data[9], interlace: data[12] };
    else if (type === "PLTE") palette = data;
    else if (type === "tRNS") trns = data;
    else if (type === "IDAT") idat.push(data);
    else if (type === "IEND") break;
    pos += 12 + len;
  }
  if (!ihdr) fail(`${path}: missing IHDR`);
  if (ihdr.depth !== 8) fail(`${path}: ${ihdr.depth}-bit PNG not supported; export 8-bit`);
  if (ihdr.interlace) fail(`${path}: interlaced PNG not supported; re-export without interlacing`);
  const ch = { 0: 1, 2: 3, 3: 1, 4: 2, 6: 4 }[ihdr.color];
  if (!ch) fail(`${path}: unknown colour type ${ihdr.color}`);
  if (ihdr.color === 3 && !palette) fail(`${path}: palette PNG without PLTE`);
  let raw;
  try { raw = inflateSync(Buffer.concat(idat)); } catch (e) { fail(`${path}: corrupt image data (${e.message})`); }
  const { w, h } = ihdr, stride = w * ch;
  if (raw.length < h * (stride + 1)) fail(`${path}: truncated image data`);
  const px = Buffer.alloc(h * stride);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (stride + 1)], src = y * (stride + 1) + 1, row = y * stride, prev = row - stride;
    for (let x = 0; x < stride; x++) {
      const a = x >= ch ? px[row + x - ch] : 0, b = y ? px[prev + x] : 0, c = x >= ch && y ? px[prev + x - ch] : 0;
      let v = raw[src + x];
      if (f === 1) v += a; else if (f === 2) v += b; else if (f === 3) v += (a + b) >> 1;
      else if (f === 4) { const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c); v += pa <= pb && pa <= pc ? a : pb <= pc ? b : c; }
      else if (f !== 0) fail(`${path}: bad filter type ${f}`);
      px[row + x] = v & 255;
    }
  }
  const rgb = new Uint8Array(w * h * 3);   // composited over white
  for (let i = 0; i < w * h; i++) {
    let r, g, b, al = 255;
    const o = i * ch;
    if (ihdr.color === 0) { r = g = b = px[o]; if (trns && trns.length >= 2 && px[o] === trns.readUInt16BE(0)) al = 0; }
    else if (ihdr.color === 2) { r = px[o]; g = px[o + 1]; b = px[o + 2]; }
    else if (ihdr.color === 3) { const k = px[o] * 3; r = palette[k]; g = palette[k + 1]; b = palette[k + 2]; if (trns && px[o] < trns.length) al = trns[px[o]]; }
    else if (ihdr.color === 4) { r = g = b = px[o]; al = px[o + 1]; }
    else { r = px[o]; g = px[o + 1]; b = px[o + 2]; al = px[o + 3]; }
    const t = al / 255;
    rgb[i * 3] = Math.round(r * t + 255 * (1 - t)); rgb[i * 3 + 1] = Math.round(g * t + 255 * (1 - t)); rgb[i * 3 + 2] = Math.round(b * t + 255 * (1 - t));
  }
  return { w, h, rgb };
}

const CRC = new Int32Array(256).map((_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c; });
const crc32 = (b) => { let c = -1; for (const x of b) c = CRC[(c ^ x) & 255] ^ (c >>> 8); return (c ^ -1) >>> 0; };
function encode(w, h, rgba) {
  const chunk = (type, data) => {
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type, "latin1"), data]);
    const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(td));
    return Buffer.concat([len, td, crc]);
  };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 6;
  const raw = Buffer.alloc(h * (w * 4 + 1));
  for (let y = 0; y < h; y++) Buffer.from(rgba.buffer, y * w * 4, w * 4).copy(raw, y * (w * 4 + 1) + 1);
  return Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), chunk("IHDR", ihdr), chunk("IDAT", deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]);
}

const A = decode(files[0]), B = decode(files[1]);
const w = Math.min(A.w, B.w), h = Math.min(A.h, B.h);
const diff = new Uint8Array(w * h);
for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
  const ia = (y * A.w + x) * 3, ib = (y * B.w + x) * 3;
  const d = Math.max(Math.abs(A.rgb[ia] - B.rgb[ib]), Math.abs(A.rgb[ia + 1] - B.rgb[ib + 1]), Math.abs(A.rgb[ia + 2] - B.rgb[ib + 2]));
  if (d > tolerance) diff[y * w + x] = 1;
}

// Group differing pixels: 8x8 cells, cells joined with 8-connected neighbours.
const CELL = 8, cw = Math.ceil(w / CELL), chh = Math.ceil(h / CELL);
const cellCount = new Int32Array(cw * chh);
for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) if (diff[y * w + x]) cellCount[((y / CELL) | 0) * cw + ((x / CELL) | 0)]++;
const seen = new Uint8Array(cw * chh), regions = [];
for (let s = 0; s < cw * chh; s++) {
  if (!cellCount[s] || seen[s]) continue;
  const stack = [s]; seen[s] = 1;
  const cells = [];
  while (stack.length) {
    const c = stack.pop(); cells.push(c);
    const cx = c % cw, cy = (c / cw) | 0;
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      const nx = cx + dx, ny = cy + dy, n = ny * cw + nx;
      if (nx >= 0 && ny >= 0 && nx < cw && ny < chh && cellCount[n] && !seen[n]) { seen[n] = 1; stack.push(n); }
    }
  }
  let x0 = Infinity, y0 = Infinity, x1 = -1, y1 = -1, count = 0;
  const sum = [0, 0, 0, 0, 0, 0];
  for (const c of cells) {
    const cx = (c % cw) * CELL, cy = ((c / cw) | 0) * CELL;
    for (let y = cy; y < Math.min(cy + CELL, h); y++) for (let x = cx; x < Math.min(cx + CELL, w); x++) {
      if (!diff[y * w + x]) continue;
      count++; x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
      const ia = (y * A.w + x) * 3, ib = (y * B.w + x) * 3;
      for (let k = 0; k < 3; k++) { sum[k] += A.rgb[ia + k]; sum[k + 3] += B.rgb[ib + k]; }
    }
  }
  const hex = (o) => "#" + [0, 1, 2].map((k) => Math.round(sum[o + k] / count).toString(16).padStart(2, "0")).join("");
  regions.push({ x: x0, y: y0, width: x1 - x0 + 1, height: y1 - y0 + 1, pixels: count, design: hex(0), build: hex(3) });
}
regions.sort((a, b) => b.pixels - a.pixels);
const real = regions.filter((r) => r.pixels >= minRegion), noise = regions.filter((r) => r.pixels < minRegion);
const mismatched = real.reduce((s, r) => s + r.pixels, 0);
const pct = Math.round((10000 * mismatched) / (w * h)) / 100;
const sizeDiffers = A.w !== B.w || A.h !== B.h;

if (out) {
  const rgba = new Uint8Array(w * h * 4);
  for (let i = 0; i < w * h; i++) {
    const ia = ((i / w) | 0) * A.w + (i % w);
    const grey = Math.round(0.299 * A.rgb[ia * 3] + 0.587 * A.rgb[ia * 3 + 1] + 0.114 * A.rgb[ia * 3 + 2]);
    const faded = Math.round(255 - (255 - grey) * 0.25);
    const hit = diff[i];
    rgba.set(hit ? [230, 30, 60, 255] : [faded, faded, faded, 255], i * 4);
  }
  writeFileSync(out, encode(w, h, rgba));
}

if (asJson) console.log(JSON.stringify({ design: { file: files[0], width: A.w, height: A.h }, build: { file: files[1], width: B.w, height: B.h },
  compared: { width: w, height: h }, tolerance, mismatchedPixels: mismatched, mismatchPercent: pct, regions: real, noiseRegions: noise.length }, null, 2));
else {
  console.log(`Design ${files[0]} ${A.w}x${A.h}, build ${files[1]} ${B.w}x${B.h}, tolerance ${tolerance}`);
  if (sizeDiffers) {
    const ratio = A.w / B.w;
    const hint = Math.abs(ratio - Math.round(ratio)) < 0.01 && Math.round(ratio) > 1 ? ` (design is ${Math.round(ratio)}x: export at 1x or capture at DPR ${Math.round(ratio)})` : "";
    console.log(`VD001 [warn] sizes differ; compared the top-left ${w}x${h}${hint}`);
  }
  real.forEach((r, i) => console.log(`VD002 [warn] region ${i + 1}: x=${r.x} y=${r.y} ${r.width}x${r.height}, ${r.pixels} px differ (design ${r.design}, build ${r.build})`));
  if (noise.length) console.log(`VD003 [info] ignored ${noise.length} tiny region(s) under ${minRegion} px (anti-aliasing noise)`);
  if (out) console.log(`Diff image written to ${out}`);
  console.log(`\n${mismatched} of ${w * h} px differ (${pct}%) in ${real.length} region(s)`);
}
process.exit(pct > maxPct || sizeDiffers ? 1 : 0);
