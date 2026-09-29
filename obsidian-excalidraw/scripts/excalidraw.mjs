#!/usr/bin/env node
// Obsidian Excalidraw (.excalidraw.md, "parsed" format) toolkit.
// Subcommands: decode | encode | layout | validate. Exit 0 = success, 1 = validation failure, 2 = usage/IO error.
import fs from 'node:fs';
import LZString from 'lz-string';

const DEFAULT_HEADER = (tags) => `---

excalidraw-plugin: parsed
tags: [${tags.join(', ')}]

---
==⚠  Switch to EXCALIDRAW VIEW in the MORE OPTIONS menu of this document. ⚠==

`;
const BLOCK_RE = /```(compressed-json|json)\n([\s\S]*?)\n```/;
const CHUNK = 256;
const FIXED_UPDATED = 1700000000000;

class UsageError extends Error {}

export function parseMd(text) {
  const m = text.match(BLOCK_RE);
  if (!m) throw new UsageError('no ```compressed-json or ```json drawing block found');
  const raw = m[1] === 'compressed-json'
    ? LZString.decompressFromBase64(m[2].replace(/\s+/g, ''))
    : m[2];
  if (!raw) throw new UsageError('compressed-json block failed to decompress');
  let data;
  try { data = JSON.parse(raw); } catch (e) { throw new UsageError(`drawing JSON is invalid: ${e.message}`); }
  const idx = text.indexOf('# Excalidraw Data');
  const header = idx >= 0 ? text.slice(0, idx) : DEFAULT_HEADER(['excalidraw']);
  return { header, data, textSection: parseTextSection(text) };
}

export function parseTextSection(text) {
  const start = text.indexOf('## Text Elements');
  if (start < 0) return null;
  const end = text.indexOf('%%', start);
  const body = text.slice(start + '## Text Elements'.length, end < 0 ? undefined : end);
  const map = new Map();
  const re = /([\s\S]*?) \^([A-Za-z0-9_-]+)\n/g;
  let m;
  while ((m = re.exec(body + '\n')) !== null) map.set(m[2], m[1].replace(/^\n+/, ''));
  return map;
}

export function serialize(data, header = DEFAULT_HEADER(['excalidraw'])) {
  const texts = data.elements
    .filter((e) => e.type === 'text' && !e.isDeleted)
    .map((e) => `${e.text} ^${e.id}`);
  const b64 = LZString.compressToBase64(JSON.stringify(data));
  const chunks = [];
  for (let i = 0; i < b64.length; i += CHUNK) chunks.push(b64.slice(i, i + CHUNK));
  return `${header}# Excalidraw Data\n\n## Text Elements\n${texts.join('\n\n')}${texts.length ? '\n' : ''}\n%%\n## Drawing\n\`\`\`compressed-json\n${chunks.join('\n\n')}\n\`\`\`\n%%\n`;
}

const live = (els) => els.filter((e) => !e.isDeleted);
const bbox = (e) => ({ x1: e.x, y1: e.y, x2: e.x + e.width, y2: e.y + e.height });
const distToBox = ([px, py], b) => {
  const dx = Math.max(b.x1 - px, 0, px - b.x2);
  const dy = Math.max(b.y1 - py, 0, py - b.y2);
  return Math.hypot(dx, dy);
};
const absPoints = (a) => a.points.map(([x, y]) => [a.x + x, a.y + y]);

function segCross(p, q, r, s) {
  const d = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  const d1 = d(r, s, p), d2 = d(r, s, q), d3 = d(p, q, r), d4 = d(p, q, s);
  return ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) && ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0));
}

export function validate(data, textSection, { maxGap = 40 } = {}) {
  const errors = [];
  const warnings = [];
  const els = live(data.elements || []);
  const byId = new Map();
  for (const e of els) {
    if (byId.has(e.id)) errors.push(`duplicate element id ${e.id}`);
    byId.set(e.id, e);
    for (const f of ['version', 'versionNonce', 'updated']) {
      if (typeof e[f] !== 'number') errors.push(`${e.id}: missing numeric ${f}`);
    }
  }
  for (const e of els) {
    for (const be of e.boundElements || []) {
      const t = byId.get(be.id);
      if (!t) { errors.push(`${e.id}: boundElements references missing ${be.id}`); continue; }
      if (be.type === 'text' && t.containerId !== e.id) errors.push(`${e.id}: bound text ${be.id} has containerId ${t.containerId}`);
      if (be.type === 'arrow') {
        const ends = [t.startBinding?.elementId, t.endBinding?.elementId];
        if (!ends.includes(e.id)) errors.push(`${e.id}: lists arrow ${be.id} but the arrow is not bound to it`);
      }
    }
    if (e.type === 'text' && e.containerId) {
      const c = byId.get(e.containerId);
      if (!c) errors.push(`${e.id}: containerId ${e.containerId} missing`);
      else if (!(c.boundElements || []).some((b) => b.id === e.id)) errors.push(`${e.id}: container ${c.id} does not list it in boundElements`);
    }
    if (e.type === 'arrow' || e.type === 'line') {
      if (!Array.isArray(e.points) || e.points.length < 2) { errors.push(`${e.id}: needs >=2 points`); continue; }
      if (e.points[0][0] !== 0 || e.points[0][1] !== 0) errors.push(`${e.id}: points[0] must be [0,0] (points are relative to x/y)`);
      const pts = absPoints(e);
      for (const [key, pt] of [['startBinding', pts[0]], ['endBinding', pts[pts.length - 1]]]) {
        const b = e[key];
        if (!b) continue;
        const t = byId.get(b.elementId);
        if (!t) { errors.push(`${e.id}: ${key} target ${b.elementId} missing`); continue; }
        if (!(t.boundElements || []).some((x) => x.id === e.id)) errors.push(`${e.id}: ${key} to ${t.id} is one-way (target boundElements lacks arrow)`);
        const gap = distToBox(pt, bbox(t));
        if (gap > maxGap) errors.push(`${e.id}: ${key} endpoint is ${gap.toFixed(0)}px from ${t.id} (max ${maxGap})`);
        else if (gap === 0) warnings.push(`${e.id}: ${key} endpoint lies inside ${t.id}; place it 4-8px outside the border`);
      }
    }
  }
  if (textSection) {
    for (const e of els.filter((x) => x.type === 'text')) {
      if (!textSection.has(e.id)) errors.push(`Text Elements section lacks ^${e.id}`);
      else if (textSection.get(e.id) !== e.text) errors.push(`Text Elements section text for ^${e.id} is stale`);
    }
    for (const id of textSection.keys()) if (!byId.has(id)) errors.push(`Text Elements section has orphan ^${id}`);
  } else {
    errors.push('missing "## Text Elements" section');
  }
  const arrows = els.filter((e) => e.type === 'arrow' && Array.isArray(e.points));
  for (let i = 0; i < arrows.length; i++) {
    for (let j = i + 1; j < arrows.length; j++) {
      const A = absPoints(arrows[i]), B = absPoints(arrows[j]);
      let hit = false;
      for (let a = 0; a < A.length - 1 && !hit; a++) {
        for (let b = 0; b < B.length - 1 && !hit; b++) hit = segCross(A[a], A[a + 1], B[b], B[b + 1]);
      }
      if (hit) warnings.push(`arrows ${arrows[i].id} and ${arrows[j].id} cross`);
    }
  }
  return { errors, warnings };
}

// ---------- layout ----------
function hash(s) {
  let h = 2166136261;
  for (const c of s) { h ^= c.codePointAt(0); h = Math.imul(h, 16777619); }
  return h >>> 0;
}
const STYLES = {
  process: { stroke: '#1e1e1e', bg: '#e7f5ff' },
  decision: { stroke: '#e67700', bg: '#fff3bf', type: 'diamond' },
  terminal: { stroke: '#2b8a3e', bg: '#d3f9d8' },
  blocked: { stroke: '#c92a2a', bg: '#ffe3e3' },
};
const EDGE = { normal: { stroke: '#1e1e1e', dash: 'solid' }, rework: { stroke: '#6741d9', dash: 'dashed' }, blocked: { stroke: '#c92a2a', dash: 'dashed' } };

function base(id, type, extra) {
  const h = hash(id);
  return {
    id, type, angle: 0, strokeColor: '#1e1e1e', backgroundColor: 'transparent', fillStyle: 'solid',
    strokeWidth: 2, strokeStyle: 'solid', roughness: 1, opacity: 100, groupIds: [], frameId: null,
    roundness: null, seed: h, version: 1, versionNonce: hash(`${id}#n`), isDeleted: false,
    boundElements: [], updated: FIXED_UPDATED, link: null, locked: false, ...extra,
  };
}
function textEl(id, text, x, y, w, h, containerId, size = 16) {
  return base(id, 'text', {
    x, y, width: w, height: h, text, originalText: text, fontSize: size, fontFamily: 5,
    textAlign: 'center', verticalAlign: 'middle', containerId, autoResize: true, lineHeight: 1.25, boundElements: null,
  });
}

export function layout(spec) {
  if (!spec || !Array.isArray(spec.nodes) || !Array.isArray(spec.edges)) throw new UsageError('layout spec needs "nodes" and "edges" arrays');
  const ids = new Set();
  for (const n of spec.nodes) {
    if (!n.id || !n.label) throw new UsageError('every node needs id and label');
    if (ids.has(n.id)) throw new UsageError(`duplicate node id ${n.id}`);
    ids.add(n.id);
  }
  for (const e of spec.edges) if (!ids.has(e.from) || !ids.has(e.to)) throw new UsageError(`edge ${e.from}->${e.to} references unknown node`);
  // Layer by longest path over the DAG of forward edges; edges closing a cycle become back edges.
  const order = spec.nodes.map((n) => n.id);
  const pos = new Map(order.map((id, i) => [id, i]));
  const back = (e) => pos.get(e.to) <= pos.get(e.from);
  const layer = new Map(order.map((id) => [id, 0]));
  for (const id of order) for (const e of spec.edges) if (e.from === id && !back(e)) layer.set(e.to, Math.max(layer.get(e.to), layer.get(id) + 1));
  const rows = [];
  for (const id of order) (rows[layer.get(id)] ||= []).push(id);
  const W = 220, H = 80, GX = 80, GY = 110, TOP = spec.title ? 120 : 40;
  const maxCols = Math.max(...rows.map((r) => r.length));
  const box = new Map();
  rows.forEach((row, r) => {
    const offset = ((maxCols - row.length) * (W + GX)) / 2;
    row.forEach((id, c) => box.set(id, { x: 40 + offset + c * (W + GX), y: TOP + r * (H + GY), width: W, height: H }));
  });
  const els = [];
  if (spec.title) els.push(textEl('title', spec.title, 40, 30, Math.max(W, maxCols * (W + GX) - GX), 40, null, 28));
  const byId = new Map();
  for (const n of spec.nodes) {
    const st = STYLES[n.kind || 'process'];
    if (!st) throw new UsageError(`unknown node kind ${n.kind}`);
    const b = box.get(n.id);
    const shape = base(n.id, st.type || 'rectangle', { ...b, strokeColor: st.stroke, backgroundColor: st.bg, roundness: st.type ? null : { type: 3 } });
    const tid = `${n.id}-t`;
    shape.boundElements.push({ type: 'text', id: tid });
    const lines = n.label.split('\n').length;
    const th = lines * 20;
    els.push(shape, textEl(tid, n.label, b.x + 10, b.y + (H - th) / 2, W - 20, th, n.id));
    byId.set(n.id, shape);
  }
  const rightEdge = Math.max(...[...box.values()].map((b) => b.x + b.width));
  const GAP = 6;
  let lane = 0;
  spec.edges.forEach((e, i) => {
    const s = box.get(e.from), t = box.get(e.to);
    const style = EDGE[e.style || (back(e) ? 'rework' : 'normal')];
    if (!style) throw new UsageError(`unknown edge style ${e.style}`);
    let pts;
    if (back(e)) {
      const lx = rightEdge + 40 + 30 * lane++;
      const sy = s.y + s.height / 2, ty = t.y + t.height / 2;
      pts = [[s.x + s.width + GAP, sy], [lx, sy], [lx, ty], [t.x + t.width + GAP, ty]];
    } else if (layer.get(e.to) === layer.get(e.from)) {
      const y = s.y + s.height / 2;
      pts = s.x < t.x ? [[s.x + s.width + GAP, y], [t.x - GAP, y]] : [[s.x - GAP, y], [t.x + t.width + GAP, y]];
    } else {
      const sx = s.x + s.width / 2, tx = t.x + t.width / 2;
      const sy = s.y + s.height + GAP, ty = t.y - GAP;
      pts = sx === tx ? [[sx, sy], [tx, ty]] : [[sx, sy], [sx, (sy + ty) / 2], [tx, (sy + ty) / 2], [tx, ty]];
    }
    const aid = `e${i}-${e.from}-${e.to}`;
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const fp = (b, [x, y]) => [+((x - b.x) / b.width).toFixed(4), +((y - b.y) / b.height).toFixed(4)];
    const arrow = base(aid, 'arrow', {
      x: pts[0][0], y: pts[0][1], width: Math.max(...xs) - Math.min(...xs), height: Math.max(...ys) - Math.min(...ys),
      points: pts.map(([x, y]) => [x - pts[0][0], y - pts[0][1]]), strokeColor: style.stroke, strokeStyle: style.dash,
      roundness: { type: 2 }, lastCommittedPoint: null, startArrowhead: null, endArrowhead: 'arrow', elbowed: false,
      startBinding: { mode: 'orbit', elementId: e.from, fixedPoint: fp(s, pts[0]) },
      endBinding: { mode: 'orbit', elementId: e.to, fixedPoint: fp(t, pts[pts.length - 1]) },
    });
    byId.get(e.from).boundElements.push({ type: 'arrow', id: aid });
    byId.get(e.to).boundElements.push({ type: 'arrow', id: aid });
    els.push(arrow);
    if (e.label) {
      const mid = Math.floor((pts.length - 1) / 2);
      const [mx, my] = [(pts[mid][0] + pts[mid + 1][0]) / 2, (pts[mid][1] + pts[mid + 1][1]) / 2];
      const lw = Math.max(40, [...e.label].length * 14);
      const lid = `${aid}-t`;
      arrow.boundElements.push({ type: 'text', id: lid });
      els.push(textEl(lid, e.label, mx - lw / 2, my - 10, lw, 20, aid, 14));
    }
  });
  return {
    type: 'excalidraw', version: 2, source: 'obsidian-excalidraw-skill', elements: els,
    appState: { gridSize: null, viewBackgroundColor: '#ffffff' }, files: {},
  };
}

// ---------- CLI ----------
const USAGE = `usage:
  excalidraw.mjs decode <file.excalidraw.md>              print scene JSON
  excalidraw.mjs encode <scene.json> <out.excalidraw.md> [--header-from <file.excalidraw.md>] [--force]
  excalidraw.mjs layout <spec.json> <out.excalidraw.md> [--tags a,b] [--force]
  excalidraw.mjs validate <file.excalidraw.md> [--strict]  OK/FAIL; --strict makes warnings fail`;

function readJson(p) {
  try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch (e) { throw new UsageError(`cannot read JSON ${p}: ${e.message}`); }
}
function readText(p) {
  try { return fs.readFileSync(p, 'utf8'); } catch (e) { throw new UsageError(`cannot read ${p}: ${e.message}`); }
}
function writeOut(p, content, force) {
  if (fs.existsSync(p) && !force) throw new UsageError(`${p} exists; pass --force only after the user approved overwriting it`);
  fs.writeFileSync(p, content);
}

function main(argv) {
  const flags = new Set(argv.filter((a) => a.startsWith('--')));
  const opt = (name) => { const i = argv.indexOf(name); return i >= 0 ? argv[i + 1] : undefined; };
  const optVals = new Set(['--header-from', '--tags'].map(opt).filter(Boolean));
  const pos = argv.filter((a) => !a.startsWith('--') && !optVals.has(a));
  const [cmd, a, b] = pos;
  switch (cmd) {
    case 'decode': {
      if (!a) throw new UsageError(USAGE);
      process.stdout.write(`${JSON.stringify(parseMd(readText(a)).data, null, 2)}\n`);
      return 0;
    }
    case 'encode': {
      if (!a || !b) throw new UsageError(USAGE);
      const data = readJson(a);
      if (!Array.isArray(data.elements)) throw new UsageError('scene JSON needs an "elements" array');
      const hf = opt('--header-from');
      const header = hf ? parseMd(readText(hf)).header : DEFAULT_HEADER(['excalidraw']);
      writeOut(b, serialize(data, header), flags.has('--force'));
      console.log(`wrote ${b}`);
      return 0;
    }
    case 'layout': {
      if (!a || !b) throw new UsageError(USAGE);
      const tags = (opt('--tags') || 'excalidraw').split(',').map((s) => s.trim()).filter(Boolean);
      writeOut(b, serialize(layout(readJson(a)), DEFAULT_HEADER(tags)), flags.has('--force'));
      console.log(`wrote ${b}`);
      return 0;
    }
    case 'validate': {
      if (!a) throw new UsageError(USAGE);
      const { data, textSection } = parseMd(readText(a));
      const { errors, warnings } = validate(data, textSection);
      const n = live(data.elements);
      for (const w of warnings) console.log(`WARN ${w}`);
      for (const e of errors) console.log(`ERROR ${e}`);
      const failed = errors.length > 0 || (flags.has('--strict') && warnings.length > 0);
      console.log(`${failed ? 'FAIL' : 'OK'} ${a}: ${n.length} elements, ${n.filter((e) => e.type === 'arrow').length} arrows, ${errors.length} errors, ${warnings.length} warnings`);
      return failed ? 1 : 0;
    }
    default:
      throw new UsageError(USAGE);
  }
}

if (import.meta.url === `file://${process.argv[1]}` || process.argv[1]?.endsWith('excalidraw.mjs')) {
  try { process.exitCode = main(process.argv.slice(2)); } catch (e) {
    if (e instanceof UsageError) { console.error(e.message); process.exitCode = 2; } else throw e;
  }
}
