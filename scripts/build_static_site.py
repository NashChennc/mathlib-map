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
    main { position: relative; min-width: 0; }
    h1 { font-size: 20px; margin: 0 0 8px; letter-spacing: 0; }
    h2 { font-size: 13px; text-transform: uppercase; color: var(--muted); margin: 22px 0 10px; letter-spacing: 0.04em; }
    p { line-height: 1.48; color: var(--muted); }
    .selection-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #f8fafc;
      padding: 12px;
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
    .selected-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 10px; }
    .selected-meta div { border-top: 1px solid var(--line); padding-top: 8px; }
    .selected-meta strong { display: block; font-size: 18px; }
    .selected-meta span { color: var(--muted); font-size: 12px; }
    label { display: block; margin: 12px 0 6px; font-size: 13px; color: var(--muted); }
    input, select, button {
      width: 100%;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
      border-radius: 8px;
      padding: 10px 11px;
      font: inherit;
    }
    button { cursor: pointer; background: var(--accent); color: white; border-color: var(--accent); margin-top: 10px; }
    canvas { width: 100%; height: 100%; display: block; background: #f8fafc; }
    .tooltip {
      position: absolute;
      right: 18px;
      top: 18px;
      width: min(430px, calc(100% - 36px));
      background: rgba(255,255,255,.96);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      box-shadow: 0 14px 35px rgba(15, 23, 42, .12);
      pointer-events: none;
    }
    .tooltip h3 { margin: 0 0 8px; font-size: 15px; word-break: break-word; }
    .tooltip h4 { margin: 0 0 7px; font-size: 13px; color: #334155; }
    .tooltip p { margin: 0 0 10px; font-size: 13px; color: #475569; max-height: 115px; overflow: hidden; }
    .tooltip dl { display: grid; grid-template-columns: 118px 1fr; gap: 5px 10px; margin: 0; font-size: 13px; }
    .tooltip dt { color: var(--muted); }
    .tooltip dd { margin: 0; }
    .edge-key { display: grid; gap: 7px; color: var(--muted); font-size: 12px; margin-top: 10px; }
    .edge-key span { display: inline-flex; align-items: center; gap: 7px; }
    .edge-line { width: 30px; height: 3px; border-radius: 999px; display: inline-block; }
    .legend { display: flex; flex-wrap: wrap; gap: 7px; }
    .chip { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--line); border-radius: 999px; padding: 5px 8px; font-size: 12px; }
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
    }
  </style>
</head>
<body>
  <div class="app">
    <aside>
      <h1>Mathlib Network Explorer</h1>
      <h2>Selected</h2>
      <section id="selectionCard" class="selection-card">
        <h3 id="selectedTitle">No module selected</h3>
        <div id="selectedModule" class="module-id">-</div>
        <p id="selectedDescription" hidden></p>
        <a id="selectedSourceLink" class="source-link" hidden>Open Lean file</a>
        <div class="selected-meta">
          <div><strong id="selectedDeps">0</strong><span>Direct imports</span></div>
          <div><strong id="selectedDependents">0</strong><span>Direct dependents</span></div>
          <div><strong id="selectedAncestors">0</strong><span>Transitive imports</span></div>
          <div><strong id="selectedDescendants">0</strong><span>Downstream users</span></div>
        </div>
      </section>
      <h2>Controls</h2>
      <label for="search">Search module</label>
      <input id="search" placeholder="Algebra, Topology, Measure..." />
      <label for="topic">Topic</label>
      <select id="topic"><option value="">All topics</option></select>
      <button id="reset">Reset view</button>
      <h2>Legend</h2>
      <div id="legend" class="legend"></div>
      <div class="edge-key">
        <span><i class="edge-line" style="background:#2563eb"></i>Direct imports from selected module</span>
        <span><i class="edge-line" style="background:#16a34a"></i>Modules that import the selected module</span>
      </div>
    </aside>
    <main>
      <button id="sidebarToggle" class="sidebar-toggle" type="button" aria-label="Collapse sidebar" aria-expanded="true" title="Collapse sidebar">‹</button>
      <canvas id="graph"></canvas>
      <div id="tooltip" class="tooltip" hidden></div>
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
    const appRoot = document.querySelector('.app');
    const canvas = document.getElementById('graph');
    const ctx = canvas.getContext('2d');
    const tooltip = document.getElementById('tooltip');
    const search = document.getElementById('search');
    const topicSelect = document.getElementById('topic');
    const resetButton = document.getElementById('reset');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const selectedTitle = document.getElementById('selectedTitle');
    const selectedModule = document.getElementById('selectedModule');
    const selectedDescription = document.getElementById('selectedDescription');
    const selectedSourceLink = document.getElementById('selectedSourceLink');
    const selectedDeps = document.getElementById('selectedDeps');
    const selectedDependents = document.getElementById('selectedDependents');
    const selectedAncestors = document.getElementById('selectedAncestors');
    const selectedDescendants = document.getElementById('selectedDescendants');
    const nodes = graph.nodes;
    const edges = graph.edges;
    const FIT_Y_COMPRESSION = 0.46;
    const MIN_ZOOM = 0.82;
    const OVERVIEW_LABEL_ZOOM_LIMIT = 1.18;
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
    let lastX = 0;
    let lastY = 0;
    let visibleNodes = nodes;
    let sidebarCollapsed = false;

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
      scaleX = (w - margin * 2) / Math.max(1, b.maxX - b.minX);
      scaleY = ((h - margin * 2) / Math.max(1, b.maxY - b.minY)) * FIT_Y_COMPRESSION;
      zoom = 1;
      panX = margin - b.minX * scaleX;
      panY = (h - (b.maxY - b.minY) * scaleY) / 2 - b.minY * scaleY;
    }

    function project(node) {
      return { x: node.x * scaleX + panX, y: node.y * scaleY + panY };
    }

    function projectPoint(x, y) {
      return { x: x * scaleX + panX, y: y * scaleY + panY };
    }

    function metricSize(node) {
      const mode = appConfig.nodeSizeMode || 'size';
      if (mode === 'pagerank') return 2.5 + Math.sqrt(Math.max(0, node.pagerank)) * 80;
      if (mode === 'betweenness') return 3 + Math.sqrt(Math.max(0, node.betweenness)) * 80;
      if (mode === 'symbols') return 3 + Math.sqrt(Math.max(0, node.nSymbols)) * 1.8;
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
      if (topic && node.topic !== topic) return false;
      const haystack = `${node.id} ${node.label} ${node.sampleSymbols || ''} ${node.descriptionTitle || ''} ${node.description || ''} ${node.sourceFile || ''}`.toLowerCase();
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
        selectedSourceLink.title = 'Open Lean file';
        selectedDeps.textContent = '0';
        selectedDependents.textContent = '0';
        selectedAncestors.textContent = '0';
        selectedDescendants.textContent = '0';
        return;
      }
      selectedTitle.textContent = node.descriptionTitle || node.label || node.id;
      selectedModule.textContent = node.id;
      selectedDescription.textContent = node.description || `Full Mathlib source module in ${node.topic}.`;
      selectedDescription.hidden = false;
      selectedSourceLink.hidden = !node.sourceUri;
      selectedSourceLink.href = node.sourceUri || '';
      selectedSourceLink.title = node.sourceFile ? `Open ${node.sourceFile}` : 'Open Lean file';
      selectedDeps.textContent = node.nDependencies;
      selectedDependents.textContent = node.nDependents;
      selectedAncestors.textContent = node.ancestorCount ?? 0;
      selectedDescendants.textContent = node.descendantCount ?? 0;
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
        let width = edge.isStructural ? 0.45 : 0.25;
        if (selected) {
          if (directImport) {
            stroke = 'rgba(37, 99, 235, 0.9)';
            width = 2.25;
          } else if (directDependent) {
            stroke = 'rgba(22, 163, 74, 0.9)';
            width = 2.25;
          } else if (dependencyFlow) {
            stroke = 'rgba(37, 99, 235, 0.09)';
            width = 0.6;
          } else if (dependentFlow) {
            stroke = 'rgba(22, 163, 74, 0.09)';
            width = 0.6;
          } else {
            stroke = 'rgba(148, 163, 184, 0.012)';
            width = 0.25;
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

    function showTooltip(node) {
      if (!node) {
        tooltip.hidden = true;
        return;
      }
      tooltip.hidden = false;
      const title = node.descriptionTitle || node.label || node.id;
      const description = node.description || `Full Mathlib source module in ${node.topic}.`;
      const sourceFile = node.sourceFile
        ? `<dt>Source</dt><dd>${escapeHtml(node.sourceFile)}</dd>`
        : '';
      tooltip.innerHTML = `<h3>${escapeHtml(node.id)}</h3>
        <h4>${escapeHtml(title)}</h4>
        <p>${escapeHtml(description)}</p>
        <dl>
          <dt>Topic</dt><dd>${escapeHtml(node.topic)}</dd>
          <dt>Lane</dt><dd>${escapeHtml(node.namespaceLane || 'n/a')}</dd>
          <dt>Rank</dt><dd>${escapeHtml(node.rank ?? node.depth)}</dd>
          <dt>Community</dt><dd>${escapeHtml(node.community)}</dd>
          <dt>Depth</dt><dd>${escapeHtml(node.depth)}</dd>
          <dt>Dependencies</dt><dd>${escapeHtml(node.nDependencies)}</dd>
          <dt>Dependents</dt><dd>${escapeHtml(node.nDependents)}</dd>
          <dt>Transitive imports</dt><dd>${escapeHtml(node.ancestorCount ?? 0)}</dd>
          <dt>Downstream users</dt><dd>${escapeHtml(node.descendantCount ?? 0)}</dd>
          <dt>Symbols</dt><dd>${escapeHtml(node.nSymbols)}</dd>
          <dt>PageRank</dt><dd>${node.pagerank.toExponential(3)}</dd>
          <dt>Betweenness</dt><dd>${node.betweenness.toExponential(3)}</dd>
          ${sourceFile}
          <dt>Examples</dt><dd>${escapeHtml(node.sampleSymbols || 'n/a')}</dd>
        </dl>`;
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
        draw();
        return;
      }
      const node = nearestNode(x, y);
      hovered = node?.id || null;
      showTooltip(node);
      draw();
    });
    canvas.addEventListener('mouseleave', () => { hovered = null; showTooltip(null); draw(); });
    canvas.addEventListener('mousedown', event => { dragging = true; lastX = event.offsetX; lastY = event.offsetY; });
    window.addEventListener('mouseup', () => { dragging = false; });
    canvas.addEventListener('click', event => {
      const node = nearestNode(event.offsetX, event.offsetY);
      selected = node ? node.id : null;
      showTooltip(node);
      updateSelectedCard(node);
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
    resetButton.addEventListener('click', () => {
      selected = null;
      search.value = '';
      topicSelect.value = '';
      zoom = 1;
      scaleX = 1;
      scaleY = 1;
      panX = 0;
      panY = 0;
      fitIfNeeded(true);
      updateSelectedCard(null);
      updateVisible();
    });
    function setSidebarCollapsed(collapsed) {
      sidebarCollapsed = collapsed;
      appRoot.classList.toggle('sidebar-collapsed', collapsed);
      sidebarToggle.textContent = collapsed ? '›' : '‹';
      sidebarToggle.setAttribute('aria-label', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
      sidebarToggle.setAttribute('aria-expanded', String(!collapsed));
      sidebarToggle.title = collapsed ? 'Expand sidebar' : 'Collapse sidebar';
      window.setTimeout(() => resize(true), 190);
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
