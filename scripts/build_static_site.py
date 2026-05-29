#!/usr/bin/env python3
"""Build a dependency-light interactive static visualization page."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/processed")
    parser.add_argument("--docs-dir", default="docs")
    parser.add_argument("--config", default="web/config.json")
    return parser.parse_args()


HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Mathlib Network Explorer</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f8fafc;
      --panel: #ffffff;
      --ink: #0f172a;
      --muted: #64748b;
      --line: #dbe3ef;
      --accent: #2563eb;
      --dependent: #16a34a;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
      overflow: hidden;
    }
    .app {
      display: grid;
      grid-template-columns: 360px minmax(0, 1fr);
      height: 100vh;
      transition: grid-template-columns 180ms ease;
    }
    .app.sidebar-collapsed {
      grid-template-columns: 0 minmax(0, 1fr);
    }
    aside {
      border-right: 1px solid var(--line);
      background: var(--panel);
      padding: 18px;
      overflow-y: auto;
      min-width: 0;
      transition: padding 180ms ease, opacity 140ms ease;
    }
    .app.sidebar-collapsed aside {
      border-right: 0;
      opacity: 0;
      overflow: hidden;
      padding: 0;
      pointer-events: none;
    }
    main { display: flex; flex-direction: column; position: relative; min-width: 0; }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 6px 10px;
      flex-shrink: 0;
      flex-wrap: wrap;
    }
    .topbar input,
    .topbar select {
      width: auto;
      margin-top: 0;
      align-self: stretch;
      height: 40px;
      box-sizing: border-box;
    }
    .topbar button {
      width: auto;
      margin-top: 0;
    }
    .topbar input {
      flex: 1;
      min-width: 120px;
      max-width: 320px;
    }
    .topbar select {
      min-width: 100px;
      appearance: none;
      padding-right: 28px;
    }
    .select-wrap {
      position: relative;
      display: inline-flex;
    }
    .select-wrap::after {
      content: '';
      position: absolute;
      right: 11px;
      top: 50%;
      transform: translateY(-50%);
      width: 0;
      height: 0;
      border-left: 5px solid transparent;
      border-right: 5px solid transparent;
      border-top: 6px solid var(--muted);
      pointer-events: none;
    }
    .topbar-label {
      display: inline;
      margin: 0;
      font-size: 12px;
      color: var(--muted);
      white-space: nowrap;
    }
    h1 { font-size: 20px; margin: 0 0 8px; letter-spacing: 0; }
    h2 { font-size: 13px; text-transform: uppercase; color: var(--muted); margin: 22px 0 10px; letter-spacing: 0.04em; }
    p { line-height: 1.48; color: var(--muted); }
    .selection-card {
      padding: 12px 0;
      margin-top: 10px;
    }
    .selection-card h3 { margin: 0 0 5px; font-size: 14px; word-break: break-word; }
    .selection-card .module-id { margin: 0 0 9px; color: var(--muted); font-size: 12px; word-break: break-word; }
    .selection-card p { margin: 0; font-size: 13px; color: #334155; }
    .source-link {
      align-items: center;
      border: 1px solid #bfdbfe;
      border-radius: 8px;
      color: #1d4ed8;
      display: inline-flex;
      font-size: 13px;
      font-weight: 600;
      line-height: 1.2;
      margin-top: 10px;
      max-width: 100%;
      padding: 8px 10px;
      text-decoration: none;
    }
    .source-link:hover { background: #eff6ff; }
    .source-link[hidden] { display: none; }
    .detail-disclosure {
      border-top: 1px solid var(--line);
      margin-top: 10px;
      padding-top: 8px;
    }
    .detail-disclosure dl {
      display: grid;
      grid-template-columns: 118px 1fr;
      gap: 5px 9px;
      margin: 9px 0 0;
      font-size: 12px;
    }
    .detail-disclosure dt { color: var(--muted); }
    .detail-disclosure dd { color: #334155; margin: 0; min-width: 0; overflow-wrap: anywhere; }
    .neighbor-lists { display: grid; grid-template-columns: 1fr; gap: 8px; margin-top: 10px; }
    .neighbor-disclosure {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
    }
    .neighbor-disclosure summary {
      display: flex;
      align-items: center;
      justify-content: space-between;
      color: #334155;
      font-size: 13px;
      font-weight: 700;
      cursor: pointer;
      list-style: none;
    }
    .neighbor-disclosure summary::-webkit-details-marker { display: none; }
    .neighbor-disclosure summary::after {
      content: '▸';
      font-size: 20px;
      color: var(--muted);
      transition: transform 140ms ease;
    }
    .neighbor-disclosure[open] summary::after {
      transform: rotate(90deg);
    }
    .neighbor-disclosure summary strong {
      display: block;
      font-size: 20px;
      color: var(--ink);
    }
    .neighbor-disclosure summary > div {
      display: flex;
      flex-direction: column;
    }
    .neighbor-disclosure summary span {
      color: var(--muted);
      font-size: 12px;
    }
    .neighbor-list { display: grid; gap: 5px; max-height: 180px; margin-top: 7px; overflow-y: auto; padding-right: 2px; }
    .neighbor-link {
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 7px;
      color: var(--ink);
      cursor: pointer;
      display: grid;
      gap: 2px;
      margin: 0;
      padding: 7px 8px;
      text-align: left;
      width: 100%;
    }
    .neighbor-link:hover, .neighbor-link:focus-visible { background: #eff6ff; border-color: #93c5fd; outline: none; }
    .neighbor-title { font-size: 12px; font-weight: 700; line-height: 1.25; overflow-wrap: anywhere; }
    .neighbor-id { color: var(--muted); font-size: 11px; line-height: 1.2; overflow-wrap: anywhere; }
    input, select, button {
      width: 100%;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
      border-radius: 12px;
      padding: 10px 11px;
      font: inherit;
    }
    button { cursor: pointer; background: var(--accent); color: white; border-color: var(--accent); margin-top: 10px; }
    canvas { flex: 1; min-height: 0; width: 100%; display: block; background: #f8fafc; }
    .tooltip {
      position: absolute;
      z-index: 3;
      max-width: min(220px, 36vw);
      overflow: hidden;
      background: rgba(255,255,255,.96);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 4px 7px;
      box-shadow: 0 8px 20px rgba(15, 23, 42, .12);
      color: var(--ink);
      font-size: 11px;
      font-weight: 700;
      line-height: 1.15;
      pointer-events: none;
      text-align: center;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .graph-legend {
      position: absolute;
      left: 14px;
      bottom: 54px;
      z-index: 2;
    }
    .edge-key { display: grid; gap: 7px; color: var(--muted); font-size: 12px; margin-top: 10px; }
    .edge-key span { display: inline-flex; align-items: center; gap: 7px; }
    .edge-line { width: 30px; height: 3px; border-radius: 999px; display: inline-block; }
    .legend { display: flex; flex-wrap: wrap; gap: 7px; }
    .chip { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--line); border-radius: 999px; padding: 5px 8px; font-size: 12px; background: rgba(255, 255, 255, 0.88); cursor: pointer; }
    .swatch { width: 9px; height: 9px; border-radius: 999px; display: inline-block; }
    .stats-bar { position: absolute; left: 18px; right: 18px; bottom: 16px; color: var(--muted); font-size: 13px; display: flex; gap: 18px; justify-content: center; flex-wrap: wrap; white-space: nowrap; }
    .stats-bar strong { color: var(--ink); }
    .sidebar-toggle {
      position: absolute;
      left: 14px;
      top: 14px;
      z-index: 3;
      width: 34px;
      height: 34px;
      border-radius: 999px;
      padding: 0;
      margin: 0;
      display: grid;
      place-items: center;
      color: var(--ink);
      background: rgba(255, 255, 255, 0.94);
      border: 1px solid var(--line);
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
      font-size: 20px;
      line-height: 1;
    }
    @media (max-width: 700px) {
      .app { grid-template-columns: 1fr; grid-template-rows: auto 1fr; }
      aside { max-height: 42vh; border-right: 0; border-bottom: 1px solid var(--line); }
      .app.sidebar-collapsed { grid-template-columns: 1fr; grid-template-rows: 0 1fr; }
      .app.sidebar-collapsed aside { border-bottom: 0; max-height: 0; }
      .topbar { padding: 6px 8px; gap: 6px; }
      .topbar input { min-width: 0; max-width: none; }
      .topbar-label { display: none; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside>
      <h1>Mathlib Network Explorer</h1>
      <section id="selectionCard" class="selection-card">
        <h3 id="selectedTitle">No module selected</h3>
        <div id="selectedModule" class="module-id">-</div>
        <p id="selectedDescription" hidden></p>
        <a id="selectedSourceLink" class="source-link" hidden>Open Mathlib source</a>
        <div id="selectedNeighborLists" class="neighbor-lists"></div>
        <div id="selectedDetailPanel" class="detail-disclosure" hidden>
          <dl id="selectedDetailList"></dl>
        </div>
      </section>
    </aside>
    <main>
      <div class="topbar">
        <label for="search" class="topbar-label">Search</label>
        <input id="search" type="text" placeholder="Algebra, Topology, Measure..." aria-label="Search module" />
        <label for="topic" class="topbar-label">Topic</label>
        <span class="select-wrap"><select id="topic" aria-label="Filter by topic"><option value="">All topics</option></select></span>
      </div>
      <canvas id="graph"></canvas>
      <button id="sidebarToggle" class="sidebar-toggle" type="button" aria-label="Collapse sidebar" aria-expanded="true" title="Collapse sidebar">‹</button>
      <div id="tooltip" class="tooltip" hidden></div>
      <div class="graph-legend">
        <div id="legend" class="legend"></div>
        <div class="edge-key">
          <span><i class="edge-line" style="background:#2563eb"></i>Direct imports from selected module</span>
          <span><i class="edge-line" style="background:#16a34a"></i>Modules that import the selected module</span>
        </div>
      </div>
      <div class="stats-bar">
        <strong id="nodeCount">0</strong> Modules ·
        <strong id="edgeCount">0</strong> Imports ·
        <strong id="structuralCount">0</strong> Structure edges ·
        <strong id="communityCount">0</strong> Communities ·
        Max depth <strong id="maxDepth">0</strong>
      </div>
    </main>
  </div>
  <script id="graph-data" type="application/json">__GRAPH_JSON__</script>
  <script id="app-config" type="application/json">__APP_CONFIG__</script>
  <script>
    const graph = JSON.parse(document.getElementById('graph-data').textContent);
    const appConfig = JSON.parse(document.getElementById('app-config').textContent);
    const visual = graph.summary.visual;
    const LBL_HITBOX_MIN = visual.label_hitbox_min;
    const LBL_HITBOX_MARGIN = visual.label_hitbox_margin;
    const LBL_AVOID_MIN = visual.label_avoid_min;
    const LBL_AVOID_MARGIN = visual.label_avoid_margin;
    const EDGE_SIZE_STRUCTURAL = visual.edge_size_structural;
    const EDGE_SIZE_RAW = visual.edge_size_raw;
    const EDGE_SIZE_HIGHLIGHT = visual.edge_size_highlight;
    const EDGE_SIZE_FLOW = visual.edge_size_flow;
    const EDGE_SIZE_FAINT = visual.edge_size_faint;
    const SIZE_PAGERANK_BASE = visual.size_pagerank_base;
    const SIZE_PAGERANK_SCALE = visual.size_pagerank_scale;
    const SIZE_BETWEENNESS_BASE = visual.size_betweenness_base;
    const SIZE_BETWEENNESS_SCALE = visual.size_betweenness_scale;
    const SIZE_SYMBOLS_BASE = visual.size_symbols_base;
    const SIZE_SYMBOLS_SCALE = visual.size_symbols_scale;
    const appRoot = document.querySelector('.app');
    const canvas = document.getElementById('graph');
    const ctx = canvas.getContext('2d');
    const tooltip = document.getElementById('tooltip');
    const search = document.getElementById('search');
    const topicSelect = document.getElementById('topic');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const selectedTitle = document.getElementById('selectedTitle');
    const selectedModule = document.getElementById('selectedModule');
    const selectedDescription = document.getElementById('selectedDescription');
    const selectedSourceLink = document.getElementById('selectedSourceLink');
    const selectedDetailPanel = document.getElementById('selectedDetailPanel');
    const selectedDetailList = document.getElementById('selectedDetailList');
    const selectedNeighborLists = document.getElementById('selectedNeighborLists');
    const nodes = graph.nodes;
    const edges = graph.edges;
    const MIN_ZOOM = 0.82;
    const OVERVIEW_LABEL_ZOOM_LIMIT = 2.5;
    const SELECTION_LABEL_MAX_CHARS = 48;
    const SELECTION_LABEL_MAX_WIDTH = 220;
    const SELECTION_LABEL_PADDING = 8;
    const SELECTION_LABEL_GAP = 10;
    const byId = new Map(nodes.map(n => [n.id, n]));
    const outgoing = new Map();
    const incoming = new Map();
    for (const edge of edges) {
      if (!outgoing.has(edge.source)) outgoing.set(edge.source, new Set());
      if (!incoming.has(edge.target)) incoming.set(edge.target, new Set());
      outgoing.get(edge.source).add(edge.target);
      incoming.get(edge.target).add(edge.source);
    }
    const topics = [...new Set(nodes.map(n => n.topic))].sort();
    for (const topic of topics) {
      const option = document.createElement('option');
      option.value = topic;
      option.textContent = topic;
      topicSelect.appendChild(option);
    }
    const legend = document.getElementById('legend');
    const topicColors = new Map();
    for (const node of nodes) if (!topicColors.has(node.topic)) topicColors.set(node.topic, node.color);
    const topicAnchors = new Map();
    for (const topic of topics) {
      const group = nodes.filter(node => node.topic === topic);
      if (group.length < 4) continue;
      const xs = group.map(node => node.x).sort((a, b) => a - b);
      const ys = group.map(node => node.y).sort((a, b) => a - b);
      topicAnchors.set(topic, {
        topic,
        color: topicColors.get(topic) || '#64748b',
        x: xs[Math.floor(xs.length * 0.08)],
        y: ys[Math.floor(ys.length / 2)],
        minX: xs[0]
      });
    }
    for (const [topic, color] of topicColors) {
      const chip = document.createElement('span');
      chip.className = 'chip';
      chip.innerHTML = `<span class="swatch" style="background:${color}"></span>${topic}`;
      chip.addEventListener('click', () => {
        topicSelect.value = topicSelect.value === topic ? '' : topic;
        updateVisible();
      });
      legend.appendChild(chip);
    }
    document.getElementById('nodeCount').textContent = graph.summary.node_count ?? nodes.length;
    document.getElementById('edgeCount').textContent = graph.summary.edge_count ?? edges.length;
    document.getElementById('communityCount').textContent = graph.summary.community_count ?? '-';
    document.getElementById('maxDepth').textContent = graph.summary.max_depth ?? '-';
    document.getElementById('structuralCount').textContent = graph.summary.structural_edge_count ?? edges.filter(e => e.isStructural).length;

    let selected = null;
    let hovered = null;
    let zoom = 1;
    let scaleX = 1;
    let scaleY = 1;
    let panX = 0;
    let panY = 0;
    let dragging = false;
    let didDrag = false;
    let lastX = 0;
    let lastY = 0;
    let visibleNodes = nodes;
    let sidebarCollapsed = false;
    let hoverLabelRect = null;
    let hoverLabelPoint = null;

    function resize(force = false) {
      const ratio = window.devicePixelRatio || 1;
      canvas.width = Math.floor(canvas.clientWidth * ratio);
      canvas.height = Math.floor(canvas.clientHeight * ratio);
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      fitIfNeeded(force);
      draw();
    }

    function bounds(list) {
      const xs = list.map(n => n.x);
      const ys = list.map(n => n.y);
      return { minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) };
    }

    function fitIfNeeded(force = false) {
      if (!force && (panX !== 0 || panY !== 0 || zoom !== 1)) return;
      const b = bounds(nodes);
      const w = canvas.clientWidth || 1;
      const h = canvas.clientHeight || 1;
      const margin = 34;
      const spanX = Math.max(1, b.maxX - b.minX);
      const spanY = Math.max(1, b.maxY - b.minY);
      const fitScale = Math.min(
        Math.max(1, w - margin * 2) / spanX,
        Math.max(1, h - margin * 2) / spanY
      );
      scaleX = fitScale;
      scaleY = fitScale;
      zoom = 1;
      panX = (w - spanX * fitScale) / 2 - b.minX * fitScale;
      panY = (h - spanY * fitScale) / 2 - b.minY * fitScale;
    }

    function project(node) {
      return { x: node.x * scaleX + panX, y: node.y * scaleY + panY };
    }

    function projectPoint(x, y) {
      return { x: x * scaleX + panX, y: y * scaleY + panY };
    }

    function metricSize(node) {
      const mode = appConfig.nodeSizeMode || 'size';
      if (mode === 'pagerank') return SIZE_PAGERANK_BASE + Math.sqrt(Math.max(0, node.pagerank)) * SIZE_PAGERANK_SCALE;
      if (mode === 'betweenness') return SIZE_BETWEENNESS_BASE + Math.sqrt(Math.max(0, node.betweenness)) * SIZE_BETWEENNESS_SCALE;
      if (mode === 'symbols') return SIZE_SYMBOLS_BASE + Math.sqrt(Math.max(0, node.nSymbols)) * SIZE_SYMBOLS_SCALE;
      return node.size;
    }

    function colorWithAlpha(hex, alpha) {
      const value = String(hex || '#64748b').replace('#', '');
      const full = value.length === 3 ? value.split('').map(c => c + c).join('') : value;
      const r = parseInt(full.slice(0, 2), 16);
      const g = parseInt(full.slice(2, 4), 16);
      const b = parseInt(full.slice(4, 6), 16);
      return `rgba(${r || 100}, ${g || 116}, ${b || 139}, ${alpha})`;
    }

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[char]));
    }

    function nodeTitle(node) {
      return node.descriptionTitle || node.label || node.id;
    }

    function nodeSearchHaystack(node) {
      return `${node.id} ${node.label} ${node.sampleSymbols || ''} ${node.descriptionTitle || ''} ${node.description || ''} ${node.sourceFile || ''}`.toLowerCase();
    }

    function detailRows(node) {
      const rows = [
        ['Topic', node.topic],
        ['Lane', node.namespaceLane || 'n/a'],
        ['Rank', String(node.rank ?? node.depth)],
        ['Community', String(node.community)],
        ['Depth', String(node.depth)],
        ['Dependencies', String(node.nDependencies)],
        ['Dependents', String(node.nDependents)],
        ['Transitive imports', String(node.ancestorCount ?? 0)],
        ['Downstream users', String(node.descendantCount ?? 0)],
        ['Symbols', String(node.nSymbols)],
        ['PageRank', node.pagerank.toExponential(3)],
        ['Betweenness', node.betweenness.toExponential(3)]
      ];
      if (node.sourceFile) rows.push(['Source', node.sourceFile]);
      if (node.sampleSymbols) rows.push(['Examples', node.sampleSymbols]);
      return rows;
    }

    function updateDetailPanel(node) {
      selectedDetailList.innerHTML = '';
      selectedNeighborLists.innerHTML = '';
      selectedDetailPanel.hidden = !node;
      if (!node) return;
      selectedDetailList.innerHTML = detailRows(node)
        .map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd>`)
        .join('');
      renderNeighborLists(node);
    }

    function sortedNeighborNodes(nodeId, map) {
      return [...(map.get(nodeId) || [])]
        .map(id => byId.get(id))
        .filter(Boolean)
        .sort((a, b) => nodeTitle(a).localeCompare(nodeTitle(b), undefined, { sensitivity: 'base' }) || a.id.localeCompare(b.id));
    }

    function renderNeighborSection(title, neighbors) {
      if (!neighbors.length) return;
      const section = document.createElement('details');
      section.className = 'neighbor-disclosure';
      section.open = false;
      const summary = document.createElement('summary');
      summary.innerHTML = `<div><strong>${neighbors.length}</strong><span>${title}</span></div>`;
      const list = document.createElement('div');
      list.className = 'neighbor-list';
      for (const neighbor of neighbors) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'neighbor-link';
        button.title = neighbor.id;
        button.addEventListener('click', () => selectNodeById(neighbor.id, { focus: true }));
        const label = document.createElement('span');
        label.className = 'neighbor-title';
        label.textContent = nodeTitle(neighbor);
        const id = document.createElement('span');
        id.className = 'neighbor-id';
        id.textContent = neighbor.id;
        button.append(label, id);
        list.appendChild(button);
      }
      section.append(summary, list);
      selectedNeighborLists.appendChild(section);
    }

    function renderNeighborLists(node) {
      renderNeighborSection('Direct imports', sortedNeighborNodes(node.id, outgoing));
      renderNeighborSection('Direct dependents', sortedNeighborNodes(node.id, incoming));
    }

    function truncateLabel(value, maxChars = SELECTION_LABEL_MAX_CHARS) {
      return value.length > maxChars ? `${value.slice(0, maxChars - 3).trimEnd()}...` : value;
    }

    function fitCanvasLabel(text, maxWidth) {
      let fitted = truncateLabel(text);
      while (fitted.length > 6 && ctx.measureText(fitted).width > maxWidth) {
        fitted = `${fitted.slice(0, -4).trimEnd()}...`;
      }
      return fitted;
    }

    function roundedRect(x, y, width, height, radius) {
      const r = Math.min(radius, width / 2, height / 2);
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.lineTo(x + width - r, y);
      ctx.quadraticCurveTo(x + width, y, x + width, y + r);
      ctx.lineTo(x + width, y + height - r);
      ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
      ctx.lineTo(x + r, y + height);
      ctx.quadraticCurveTo(x, y + height, x, y + height - r);
      ctx.lineTo(x, y + r);
      ctx.quadraticCurveTo(x, y, x + r, y);
      ctx.closePath();
    }

    function clamp(value, min, max) {
      return Math.max(min, Math.min(max, value));
    }

    function rectsOverlap(a, b, padding = 0) {
      return !(
        a.right + padding <= b.left ||
        a.left - padding >= b.right ||
        a.bottom + padding <= b.top ||
        a.top - padding >= b.bottom
      );
    }

    function overlapArea(a, b) {
      const width = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
      const height = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
      return width * height;
    }

    function rectFromCenter(x, y, radius) {
      return { left: x - radius, top: y - radius, right: x + radius, bottom: y + radius };
    }

    function placementCandidates(point, width, height, radius, viewportWidth, viewportHeight) {
      const step = height + SELECTION_LABEL_GAP;
      const distances = Array.from({ length: 10 }, (_, index) => radius + SELECTION_LABEL_GAP + index * step);
      const candidates = [];
      for (const distance of distances) {
        const raw = [
          { left: point.x - width / 2, top: point.y - distance - height },
          { left: point.x - width / 2, top: point.y + distance }
        ];
        for (const candidate of raw) {
          const left = clamp(candidate.left, SELECTION_LABEL_PADDING, Math.max(SELECTION_LABEL_PADDING, viewportWidth - width - SELECTION_LABEL_PADDING));
          const top = clamp(candidate.top, SELECTION_LABEL_PADDING, Math.max(SELECTION_LABEL_PADDING, viewportHeight - height - SELECTION_LABEL_PADDING));
          candidates.push({ left, top, right: left + width, bottom: top + height });
        }
      }
      return candidates;
    }

    function chooseLabelPlacement(point, width, height, radius, viewportWidth, viewportHeight, avoidRects, occupiedRects) {
      const candidates = placementCandidates(point, width, height, radius, viewportWidth, viewportHeight);
      const collisions = [...avoidRects, ...occupiedRects];
      for (const candidate of candidates) {
        if (!collisions.some(rect => rectsOverlap(candidate, rect, 2))) return candidate;
      }
      return candidates.reduce((best, candidate) => {
        const score = collisions.reduce((sum, rect) => sum + overlapArea(candidate, rect), 0);
        return score < best.score ? { rect: candidate, score } : best;
      }, { rect: candidates[0], score: Number.POSITIVE_INFINITY }).rect;
    }

    function connectorEndpoint(point, rect) {
      return {
        x: clamp(point.x, rect.left, rect.right),
        y: rect.bottom <= point.y ? rect.bottom : rect.top
      };
    }

    function collectTransitive(start, map) {
      const seen = new Set();
      const stack = [...(map.get(start) || [])];
      while (stack.length) {
        const id = stack.pop();
        if (seen.has(id)) continue;
        seen.add(id);
        for (const next of map.get(id) || []) stack.push(next);
      }
      return seen;
    }

    function selectionSets() {
      if (!selected) return { directImports: new Set(), directDependents: new Set(), direct: new Set(), deps: new Set(), dependents: new Set() };
      const directImports = new Set(outgoing.get(selected) || []);
      const directDependents = new Set(incoming.get(selected) || []);
      const direct = new Set([...directImports, ...directDependents]);
      return {
        directImports,
        directDependents,
        direct,
        deps: collectTransitive(selected, outgoing),
        dependents: collectTransitive(selected, incoming)
      };
    }

    function passesFilters(node) {
      const q = search.value.trim().toLowerCase();
      const topic = topicSelect.value;
      if (topic && node.topic !== topic) {
        if (!selected) return false;
        const directImports = outgoing.get(selected) || new Set();
        const directDependents = incoming.get(selected) || new Set();
        if (!directImports.has(node.id) && !directDependents.has(node.id) && node.id !== selected)
          return false;
      }
      const haystack = nodeSearchHaystack(node);
      if (q && !haystack.includes(q)) return false;
      return true;
    }

    function updateVisible() {
      visibleNodes = nodes.filter(passesFilters);
      draw();
    }

    function updateSelectedCard(node) {
      if (!node) {
        selectedTitle.textContent = 'No module selected';
        selectedModule.textContent = '-';
        selectedDescription.textContent = '';
        selectedDescription.hidden = true;
        selectedSourceLink.hidden = true;
        selectedSourceLink.removeAttribute('href');
        selectedSourceLink.title = 'Open Mathlib source';
        updateDetailPanel(null);
        return;
      }
      selectedTitle.textContent = nodeTitle(node);
      selectedModule.textContent = node.id;
      selectedDescription.textContent = node.description || `Full Mathlib source module in ${node.topic}.`;
      selectedDescription.hidden = false;
      selectedSourceLink.hidden = !node.sourceUri;
      selectedSourceLink.href = node.sourceUri || '';
      selectedSourceLink.title = node.sourceFile
        ? `Open ${node.sourceFile} at ${node.sourceRef || 'master'}`
        : 'Open Mathlib source';
      updateDetailPanel(node);
    }

    function revealNodeIfFiltered(node) {
      const q = search.value.trim().toLowerCase();
      if (q && !nodeSearchHaystack(node).includes(q)) search.value = '';
      if (topicSelect.value && node.topic !== topicSelect.value) topicSelect.value = '';
    }

    function focusNode(node) {
      const point = project(node);
      panX += (canvas.clientWidth || 1) / 2 - point.x;
      panY += (canvas.clientHeight || 1) / 2 - point.y;
    }

    function selectNodeById(nodeId, options = {}) {
      const node = byId.get(nodeId);
      if (!node) return;
      selected = node.id;
      hovered = null;
      tooltip.hidden = true;
      hoverLabelRect = null;
      hoverLabelPoint = null;
      if (options.reveal !== false) revealNodeIfFiltered(node);
      visibleNodes = nodes.filter(passesFilters);
      updateSelectedCard(node);
      if (options.focus) focusNode(node);
      draw();
    }

    function drawOverviewTopicLabels() {
      const q = search.value.trim();
      const topicFilter = topicSelect.value;
      if (selected || q || topicFilter || zoom > OVERVIEW_LABEL_ZOOM_LIMIT) return;
      const labels = [];
      for (const anchor of topicAnchors.values()) {
        const point = projectPoint(anchor.x, anchor.y);
        const minPoint = projectPoint(anchor.minX, anchor.y);
        if (point.y < -40 || point.y > canvas.clientHeight + 40) continue;
        labels.push({
          topic: anchor.topic,
          color: anchor.color,
          y: point.y,
          x: Math.max(10, Math.min(canvas.clientWidth - 130, point.x + 8)),
          minX: Math.max(0, minPoint.x)
        });
      }
      labels.sort((a, b) => a.y - b.y);
      const labelAlpha = Math.max(0, Math.min(1, (OVERVIEW_LABEL_ZOOM_LIMIT - zoom) / (OVERVIEW_LABEL_ZOOM_LIMIT - 1)));
      ctx.save();
      ctx.font = '600 12px Inter, ui-sans-serif, system-ui, sans-serif';
      ctx.textBaseline = 'middle';
      for (const label of labels) {
        const y = label.y;
        if (y < 14 || y > canvas.clientHeight - 14) continue;
        ctx.globalAlpha = 0.18 * labelAlpha;
        ctx.strokeStyle = colorWithAlpha(label.color, 0.38);
        ctx.lineWidth = 0.8;
        ctx.beginPath();
        ctx.moveTo(Math.max(0, label.minX - 4), y);
        ctx.lineTo(canvas.clientWidth - 16, y);
        ctx.stroke();
        ctx.globalAlpha = 0.95 * labelAlpha;
        ctx.lineWidth = 4;
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.9)';
        ctx.strokeText(label.topic, label.x, y);
        ctx.fillStyle = colorWithAlpha(label.color, 0.94);
        ctx.fillText(label.topic, label.x, y);
      }
      ctx.restore();
      ctx.globalAlpha = 1;
    }

    function drawDashedConnector(point, rect, selectedLine = false) {
      const end = connectorEndpoint(point, rect);
      ctx.save();
      ctx.globalAlpha = 1;
      ctx.strokeStyle = selectedLine ? 'rgba(15, 23, 42, 0.58)' : 'rgba(71, 85, 105, 0.45)';
      ctx.lineWidth = selectedLine ? 1.2 : 1;
      ctx.setLineDash([4, 4]);
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.moveTo(point.x, point.y);
      ctx.lineTo(end.x, end.y);
      ctx.stroke();
      ctx.restore();
    }

    function drawSelectionLabels(visible, sel) {
      if (!selected) return;
      const labelIds = new Set([selected, ...sel.directImports, ...sel.directDependents]);
      const labelHeight = 20;
      const labels = [];
      ctx.save();
      ctx.font = '700 11px Inter, ui-sans-serif, system-ui, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      for (const id of labelIds) {
        const node = byId.get(id);
        if (!node || !visible.has(id)) continue;
        const p = project(node);
        const r = Math.max(2, metricSize(node) * Math.sqrt(Math.min(scaleX, scaleY)) * 0.5);
        const text = fitCanvasLabel(nodeTitle(node), SELECTION_LABEL_MAX_WIDTH - 14);
        const labelWidth = Math.min(SELECTION_LABEL_MAX_WIDTH, ctx.measureText(text).width + 14);
        labels.push({ id, node, point: p, radius: Math.max(LBL_HITBOX_MIN, r + LBL_HITBOX_MARGIN), text, labelWidth });
      }
      const avoidRects = labels.map(label => rectFromCenter(label.point.x, label.point.y, label.radius + 3));
      const occupiedRects = [];
      const placedLabels = [];
      for (const label of labels) {
        const rect = chooseLabelPlacement(
          label.point,
          label.labelWidth,
          labelHeight,
          label.radius,
          canvas.clientWidth,
          canvas.clientHeight,
          avoidRects,
          occupiedRects
        );
        placedLabels.push({ ...label, rect });
        occupiedRects.push(rect);
      }
      for (const label of placedLabels) {
        drawDashedConnector(label.point, label.rect, label.id === selected);
      }
      for (const label of placedLabels) {
        const rect = label.rect;
        const x = rect.left + label.labelWidth / 2;
        const y = rect.top + labelHeight / 2;
        ctx.globalAlpha = 1;
        ctx.shadowColor = 'rgba(15, 23, 42, 0.12)';
        ctx.shadowBlur = label.id === selected ? 14 : 10;
        ctx.shadowOffsetY = 4;
        roundedRect(rect.left, rect.top, label.labelWidth, labelHeight, 6);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.96)';
        ctx.fill();
        ctx.shadowColor = 'transparent';
        ctx.lineWidth = label.id === selected ? 1.2 : 1;
        ctx.strokeStyle = label.id === selected ? 'rgba(15, 23, 42, 0.45)' : 'rgba(203, 213, 225, 0.95)';
        ctx.stroke();
        ctx.fillStyle = '#0f172a';
        ctx.fillText(label.text, x, y + 0.5);
      }
      ctx.restore();
      ctx.globalAlpha = 1;
    }

    function drawHoverConnector() {
      if (!hoverLabelRect || !hoverLabelPoint || tooltip.hidden) return;
      ctx.save();
      drawDashedConnector(hoverLabelPoint, hoverLabelRect, false);
      ctx.restore();
    }

    function draw() {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);
      const visible = new Set(visibleNodes.map(n => n.id));
      const sel = selectionSets();
      const edgeMode = appConfig.edgeMode || 'structural';

      for (const edge of edges) {
        if (!visible.has(edge.source) || !visible.has(edge.target)) continue;
        const directImport = selected && edge.source === selected;
        const directDependent = selected && edge.target === selected;
        const dependencyFlow = selected && !directImport && (sel.deps.has(edge.source) || sel.deps.has(edge.target));
        const dependentFlow = selected && !directDependent && (sel.dependents.has(edge.source) || sel.dependents.has(edge.target));
        if (edgeMode === 'structural' && !edge.isStructural && !directImport && !directDependent) continue;
        if (edgeMode === 'selected' && !directImport && !directDependent && !dependencyFlow && !dependentFlow) continue;
        const source = project(byId.get(edge.source));
        const target = project(byId.get(edge.target));
        let stroke = edge.isStructural ? 'rgba(148, 163, 184, 0.10)' : 'rgba(148, 163, 184, 0.035)';
        let width = edge.isStructural ? EDGE_SIZE_STRUCTURAL : EDGE_SIZE_RAW;
        if (selected) {
          if (directImport) {
            stroke = 'rgba(37, 99, 235, 0.9)';
            width = EDGE_SIZE_HIGHLIGHT;
          } else if (directDependent) {
            stroke = 'rgba(22, 163, 74, 0.9)';
            width = EDGE_SIZE_HIGHLIGHT;
          } else if (dependencyFlow) {
            stroke = 'rgba(37, 99, 235, 0.09)';
            width = EDGE_SIZE_FLOW;
          } else if (dependentFlow) {
            stroke = 'rgba(22, 163, 74, 0.09)';
            width = EDGE_SIZE_FLOW;
          } else {
            stroke = 'rgba(148, 163, 184, 0.012)';
            width = EDGE_SIZE_FAINT;
          }
        }
        ctx.strokeStyle = stroke;
        ctx.lineWidth = width;
        ctx.beginPath();
        ctx.moveTo(source.x, source.y);
        ctx.lineTo(target.x, target.y);
        ctx.stroke();
      }

      for (const node of visibleNodes) {
        const p = project(node);
        const r = Math.max(2, metricSize(node) * Math.sqrt(Math.min(scaleX, scaleY)) * 0.5);
        let alpha = 0.88;
        if (selected && node.id !== selected && !sel.direct.has(node.id) && !sel.deps.has(node.id) && !sel.dependents.has(node.id)) alpha = 0.08;
        if (selected && (sel.deps.has(node.id) || sel.dependents.has(node.id))) alpha = 0.42;
        if (selected && sel.direct.has(node.id)) alpha = 0.95;
        if (selected && node.id === selected) alpha = 1;
        ctx.globalAlpha = alpha;
        ctx.fillStyle = node.color;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
        ctx.fill();
        if (node.id === selected || node.id === hovered) {
          ctx.lineWidth = 2;
          ctx.strokeStyle = node.id === selected ? '#0f172a' : '#2563eb';
          ctx.stroke();
        }
      }
      ctx.globalAlpha = 1;
      drawSelectionLabels(visible, sel);
      drawHoverConnector();
      drawOverviewTopicLabels();
    }

    function nearestNode(x, y) {
      let best = null;
      let bestDistance = 18;
      for (const node of visibleNodes) {
        const p = project(node);
        const distance = Math.hypot(p.x - x, p.y - y);
        if (distance < bestDistance) {
          best = node;
          bestDistance = distance;
        }
      }
      return best;
    }

    function relatedNodeAvoidRects(extraNode) {
      const rects = [];
      const ids = selected ? new Set([selected, ...(outgoing.get(selected) || []), ...(incoming.get(selected) || [])]) : new Set();
      if (extraNode) ids.add(extraNode.id);
      for (const id of ids) {
        const node = byId.get(id);
        if (!node || !passesFilters(node)) continue;
        const p = project(node);
        const r = Math.max(2, metricSize(node) * Math.sqrt(Math.min(scaleX, scaleY)) * 0.5);
        const radius = Math.max(LBL_AVOID_MIN, r + LBL_AVOID_MARGIN);
        if (p.x + radius < 0 || p.y + radius < 0 || p.x - radius > canvas.clientWidth || p.y - radius > canvas.clientHeight) continue;
        rects.push(rectFromCenter(p.x, p.y, radius));
      }
      return rects;
    }

    function showTooltip(node) {
      if (!node) {
        tooltip.hidden = true;
        hoverLabelRect = null;
        hoverLabelPoint = null;
        return;
      }
      const p = project(node);
      const r = Math.max(2, metricSize(node) * Math.sqrt(Math.min(scaleX, scaleY)) * 0.5);
      tooltip.hidden = false;
      tooltip.style.visibility = 'hidden';
      tooltip.style.left = '0';
      tooltip.style.top = '0';
      tooltip.textContent = truncateLabel(nodeTitle(node));
      const rect = chooseLabelPlacement(
        p,
        tooltip.offsetWidth,
        tooltip.offsetHeight,
        Math.max(LBL_HITBOX_MIN, r + LBL_HITBOX_MARGIN),
        canvas.clientWidth,
        canvas.clientHeight,
        relatedNodeAvoidRects(node),
        []
      );
      const canvasLeft = canvas.offsetLeft;
      const canvasTop = canvas.offsetTop;
      tooltip.style.left = `${rect.left + canvasLeft}px`;
      tooltip.style.top = `${rect.top + canvasTop}px`;
      tooltip.style.visibility = '';
      hoverLabelRect = rect;
      hoverLabelPoint = p;
    }

    canvas.addEventListener('mousemove', event => {
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      if (dragging) {
        panX += x - lastX;
        panY += y - lastY;
        lastX = x;
        lastY = y;
        didDrag = true;
        draw();
        return;
      }
      const node = nearestNode(x, y);
      hovered = node?.id || null;
      showTooltip(node);
      draw();
    });
    canvas.addEventListener('mouseleave', () => { hovered = null; showTooltip(null); draw(); });
    canvas.addEventListener('mousedown', event => { dragging = true; didDrag = false; lastX = event.offsetX; lastY = event.offsetY; });
    window.addEventListener('mouseup', () => { dragging = false; });
    canvas.addEventListener('click', event => {
      if (didDrag) return;
      const node = nearestNode(event.offsetX, event.offsetY);
      if (node) {
        selectNodeById(node.id, { focus: false, reveal: false });
        return;
      }
      selected = null;
      visibleNodes = nodes.filter(passesFilters);
      showTooltip(null);
      updateSelectedCard(null);
      draw();
    });
    canvas.addEventListener('wheel', event => {
      event.preventDefault();
      const requestedFactor = event.deltaY < 0 ? 1.12 : 0.89;
      const nextZoom = Math.max(MIN_ZOOM, zoom * requestedFactor);
      const factor = nextZoom / zoom;
      if (factor === 1) return;
      const mx = event.offsetX;
      const my = event.offsetY;
      panX = mx - (mx - panX) * factor;
      panY = my - (my - panY) * factor;
      scaleX *= factor;
      scaleY *= factor;
      zoom = nextZoom;
      draw();
    }, { passive: false });
    search.addEventListener('input', updateVisible);
    topicSelect.addEventListener('change', updateVisible);
    function setSidebarCollapsed(collapsed) {
      sidebarCollapsed = collapsed;
      appRoot.classList.toggle('sidebar-collapsed', collapsed);
      sidebarToggle.textContent = collapsed ? '›' : '‹';
      sidebarToggle.setAttribute('aria-label', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
      sidebarToggle.setAttribute('aria-expanded', String(!collapsed));
      sidebarToggle.title = collapsed ? 'Expand sidebar' : 'Collapse sidebar';
      tooltip.hidden = true;
      window.setTimeout(() => {
        resize(true);
        updateDetailPanel(selected ? byId.get(selected) : null);
      }, 190);
    }
    sidebarToggle.addEventListener('click', () => setSidebarCollapsed(!sidebarCollapsed));
    window.addEventListener('resize', resize);
    updateSelectedCard(null);
    resize();
  </script>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    docs_dir = Path(args.docs_dir)
    config_path = Path(args.config)
    docs_dir.mkdir(parents=True, exist_ok=True)
    graph_text = (data_dir / "graph.json").read_text(encoding="utf-8")
    graph = json.loads(graph_text)
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    compact = json.dumps(graph, ensure_ascii=False, separators=(",", ":"))
    script_safe = compact.replace("<", "\\u003c").replace("</script", "<\\/script")
    config_json = json.dumps(config, ensure_ascii=False)
    html_text = HTML_TEMPLATE.replace("__GRAPH_JSON__", script_safe).replace("__APP_CONFIG__", config_json)
    (docs_dir / "index.html").write_text(html_text, encoding="utf-8")
    (docs_dir / "graph.json").write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Built static visualization: {docs_dir / 'index.html'}")


if __name__ == "__main__":
    main()
