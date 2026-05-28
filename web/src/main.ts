import Graph from "graphology";
import Sigma from "sigma";
import "./styles.css";

type GraphNode = {
  id: string;
  label: string;
  topic: string;
  community: number;
  depth: number;
  rank: number;
  x: number;
  y: number;
  x0: number;
  y0: number;
  size: number;
  color: string;
  pagerank: number;
  betweenness: number;
  nSymbols: number;
  nDependencies: number;
  nDependents: number;
  ancestorCount: number;
  descendantCount: number;
  namespaceLane: string;
  subNamespace: string;
  laneIndex: number;
  layoutMode: string;
  sampleSymbols: string;
  descriptionTitle: string;
  description: string;
  hasDescription: boolean;
};

type GraphEdge = {
  id: string;
  source: string;
  target: string;
  crossTopic: boolean;
  isStructural: boolean;
  isRawImport: boolean;
};

type GraphPayload = {
  summary: Record<string, unknown>;
  nodes: GraphNode[];
  edges: GraphEdge[];
};

const DISPLAY_Y_COMPRESSION = 0.46;
const OVERVIEW_LABEL_ZOOM_IN_LIMIT = 0.85;
const MAX_OVERVIEW_RATIO_MULTIPLIER = 1.18;

const app = document.querySelector<HTMLDivElement>("#app");

if (!app) {
  throw new Error("Missing #app root.");
}

app.innerHTML = `
  <aside class="sidebar">
    <h1>Mathlib Network Explorer</h1>
    <div class="stats">
      <div class="stat"><strong id="node-count">0</strong><span>Modules</span></div>
      <div class="stat"><strong id="edge-count">0</strong><span>Imports</span></div>
      <div class="stat"><strong id="community-count">0</strong><span>Communities</span></div>
      <div class="stat"><strong id="max-depth">0</strong><span>Max depth</span></div>
      <div class="stat"><strong id="structural-count">0</strong><span>Structure edges</span></div>
    </div>
    <section class="selection-card">
      <h2 id="selected-title">No module selected</h2>
      <div id="selected-module" class="module-id">-</div>
      <p id="selected-description" hidden></p>
      <div class="selected-meta">
        <div><strong id="selected-deps">0</strong><span>Direct imports</span></div>
        <div><strong id="selected-dependents">0</strong><span>Direct dependents</span></div>
        <div><strong id="selected-ancestors">0</strong><span>Transitive imports</span></div>
        <div><strong id="selected-descendants">0</strong><span>Downstream users</span></div>
      </div>
    </section>
    <div class="controls">
      <input id="search" placeholder="Search module" />
      <select id="topic"><option value="">All topics</option></select>
      <select id="edge-mode">
        <option value="structural">Structure edges</option>
        <option value="raw">Raw imports</option>
        <option value="selected">Selected only</option>
      </select>
      <p id="edge-mode-info" class="mode-note">Showing the transitive-reduction backbone.</p>
      <select id="size-mode">
        <option value="influence">Downstream influence</option>
        <option value="pagerank">PageRank influence</option>
        <option value="betweenness">Betweenness bridge score</option>
        <option value="symbols">Symbol count</option>
      </select>
      <button id="reset">Reset filters</button>
    </div>
  </aside>
  <main class="graph-shell">
    <button id="sidebar-toggle" class="sidebar-toggle" type="button" aria-label="Collapse sidebar" aria-expanded="true" title="Collapse sidebar">‹</button>
    <div id="sigma-container"></div>
    <div id="topic-overlay" class="topic-overlay"></div>
    <div id="tooltip" class="tooltip" hidden></div>
  </main>
`;

async function loadGraph(): Promise<GraphPayload> {
  const response = await fetch("./graph.json");
  if (!response.ok) {
    throw new Error("Unable to load graph.json. Run `make web` or copy data/processed/graph.json next to this build.");
  }
  return response.json() as Promise<GraphPayload>;
}

function metricSize(node: GraphNode, mode: string): number {
  if (mode === "pagerank") return 2.5 + Math.sqrt(Math.max(0, node.pagerank)) * 80;
  if (mode === "betweenness") return 3 + Math.sqrt(Math.max(0, node.betweenness)) * 80;
  if (mode === "symbols") return 3 + Math.sqrt(Math.max(0, node.nSymbols)) * 1.8;
  return node.size;
}

function setText(id: string, value: unknown): void {
  const element = document.querySelector<HTMLElement>(`#${id}`);
  if (element) element.textContent = String(value ?? "-");
}

function escapeHtml(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[char] ?? char));
}

function colorWithAlpha(hex: string, alpha: number): string {
  const raw = (hex || "#64748b").replace("#", "");
  const full = raw.length === 3 ? raw.split("").map((char) => char + char).join("") : raw;
  const r = Number.parseInt(full.slice(0, 2), 16) || 100;
  const g = Number.parseInt(full.slice(2, 4), 16) || 116;
  const b = Number.parseInt(full.slice(4, 6), 16) || 139;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function showTooltip(node: GraphNode | null): void {
  const tooltip = document.querySelector<HTMLDivElement>("#tooltip");
  if (!tooltip) return;
  if (!node) {
    tooltip.hidden = true;
    return;
  }
  tooltip.hidden = false;
  const title = node.descriptionTitle || node.label || node.id;
  const description = node.description || `Full Mathlib source module in ${node.topic}.`;
  tooltip.innerHTML = `
    <h2>${escapeHtml(node.id)}</h2>
    <h3>${escapeHtml(title)}</h3>
    <p>${escapeHtml(description)}</p>
    <dl>
      <dt>Topic</dt><dd>${escapeHtml(node.topic)}</dd>
      <dt>Lane</dt><dd>${escapeHtml(node.namespaceLane || "n/a")}</dd>
      <dt>Rank</dt><dd>${node.rank ?? node.depth}</dd>
      <dt>Community</dt><dd>${node.community}</dd>
      <dt>Depth</dt><dd>${node.depth}</dd>
      <dt>Dependencies</dt><dd>${node.nDependencies}</dd>
      <dt>Dependents</dt><dd>${node.nDependents}</dd>
      <dt>Transitive imports</dt><dd>${node.ancestorCount ?? 0}</dd>
      <dt>Downstream users</dt><dd>${node.descendantCount ?? 0}</dd>
      <dt>PageRank</dt><dd>${node.pagerank.toExponential(3)}</dd>
      <dt>Betweenness</dt><dd>${node.betweenness.toExponential(3)}</dd>
    </dl>
  `;
}

function updateSelectedCard(node: GraphNode | null): void {
  const description = document.querySelector<HTMLParagraphElement>("#selected-description");
  setText("selected-title", node?.descriptionTitle || node?.label || "No module selected");
  setText("selected-module", node?.id || "-");
  if (description) {
    description.textContent = node?.description || "";
    description.hidden = !node;
  }
  setText("selected-deps", node?.nDependencies ?? 0);
  setText("selected-dependents", node?.nDependents ?? 0);
  setText("selected-ancestors", node?.ancestorCount ?? 0);
  setText("selected-descendants", node?.descendantCount ?? 0);
}

function updateEdgeModeInfo(edgeMode: string, selectedNode: string | null, payload: GraphPayload): void {
  const rawCount = Number(payload.summary.raw_edge_count ?? payload.edges.length);
  const structuralCount = Number(payload.summary.structural_edge_count ?? payload.edges.filter((edge) => edge.isStructural).length);
  if (edgeMode === "raw") {
    setText("edge-mode-info", `Showing all ${rawCount} source import edges.`);
  } else if (edgeMode === "selected") {
    setText("edge-mode-info", selectedNode ? "Showing selected-module dependency flow." : "Select a module to show its dependency flow.");
  } else {
    setText("edge-mode-info", `Showing ${structuralCount} structural edges; ${rawCount - structuralCount} redundant raw edges are hidden.`);
  }
}

function collectTransitive(start: string, map: Map<string, Set<string>>): Set<string> {
  const seen = new Set<string>();
  const stack = [...(map.get(start) ?? [])];
  while (stack.length) {
    const id = stack.pop();
    if (!id || seen.has(id)) continue;
    seen.add(id);
    for (const next of map.get(id) ?? []) stack.push(next);
  }
  return seen;
}

loadGraph().then((payload) => {
  setText("node-count", payload.summary.node_count ?? payload.nodes.length);
  setText("edge-count", payload.summary.edge_count ?? payload.edges.length);
  setText("community-count", payload.summary.community_count);
  setText("max-depth", payload.summary.max_depth);
  setText("structural-count", payload.summary.structural_edge_count ?? payload.edges.filter((edge) => edge.isStructural).length);

  const graph = new Graph();
  const outgoing = new Map<string, Set<string>>();
  const incoming = new Map<string, Set<string>>();
  for (const node of payload.nodes) {
    graph.addNode(node.id, {
      ...node,
      label: node.label,
      x: node.x,
      y: node.y * DISPLAY_Y_COMPRESSION,
      size: node.size,
      color: node.color,
      baseColor: node.color,
      hidden: false
    });
  }
  for (const edge of payload.edges) {
    if (graph.hasNode(edge.source) && graph.hasNode(edge.target)) {
      if (!outgoing.has(edge.source)) outgoing.set(edge.source, new Set());
      if (!incoming.has(edge.target)) incoming.set(edge.target, new Set());
      outgoing.get(edge.source)?.add(edge.target);
      incoming.get(edge.target)?.add(edge.source);
      graph.addDirectedEdgeWithKey(edge.id, edge.source, edge.target, {
        color: edge.isStructural ? "rgba(148, 163, 184, 0.10)" : "rgba(148, 163, 184, 0.035)",
        baseColor: edge.isStructural ? "rgba(148, 163, 184, 0.10)" : "rgba(148, 163, 184, 0.035)",
        isStructural: edge.isStructural,
        size: edge.isStructural ? 0.45 : 0.25,
        hidden: false
      });
    }
  }

  const topics = [...new Set(payload.nodes.map((node) => node.topic))].sort();
  const topicAnchors = new Map<string, { topic: string; color: string; x: number; y: number; minX: number }>();
  for (const topic of topics) {
    const group = payload.nodes.filter((node) => node.topic === topic);
    if (group.length < 4) continue;
    const xs = group.map((node) => node.x).sort((a, b) => a - b);
    const ys = group.map((node) => node.y * DISPLAY_Y_COMPRESSION).sort((a, b) => a - b);
    topicAnchors.set(topic, {
      topic,
      color: group[0]?.color || "#64748b",
      x: xs[Math.floor(xs.length * 0.08)],
      y: ys[Math.floor(ys.length / 2)],
      minX: xs[0]
    });
  }
  const topicSelect = document.querySelector<HTMLSelectElement>("#topic");
  const edgeModeSelect = document.querySelector<HTMLSelectElement>("#edge-mode");
  for (const topic of topics) {
    const option = document.createElement("option");
    option.value = topic;
    option.textContent = topic;
    topicSelect?.appendChild(option);
  }

  const container = document.querySelector<HTMLDivElement>("#sigma-container");
  if (!container) throw new Error("Missing Sigma container.");
  const renderer = new Sigma(graph, container, {
    renderEdgeLabels: false,
    defaultEdgeColor: "rgba(148, 163, 184, 0.18)",
    labelRenderedSizeThreshold: 12,
    maxCameraRatio: MAX_OVERVIEW_RATIO_MULTIPLIER
  });
  const overlay = document.querySelector<HTMLDivElement>("#topic-overlay");
  const rendererAny = renderer as unknown as {
    graphToViewport?: (coordinates: { x: number; y: number }) => { x: number; y: number };
  };
  const cameraAny = renderer.getCamera() as unknown as {
    getState?: () => { ratio?: number };
    maxRatio?: number | null;
    on?: (event: string, callback: () => void) => void;
  };
  const initialRatio = Number(cameraAny.getState?.().ratio ?? 1);
  cameraAny.maxRatio = initialRatio * MAX_OVERVIEW_RATIO_MULTIPLIER;

  let selectedNode: string | null = null;
  let sidebarCollapsed = false;

  const renderTopicOverlay = (): void => {
    if (!overlay || !rendererAny.graphToViewport) return;
    const query = document.querySelector<HTMLInputElement>("#search")?.value.trim() ?? "";
    const topicFilter = topicSelect?.value ?? "";
    const ratio = Number(cameraAny.getState?.().ratio ?? initialRatio);
    overlay.innerHTML = "";
    if (selectedNode || query || topicFilter || ratio < initialRatio * OVERVIEW_LABEL_ZOOM_IN_LIMIT) return;
    const labels = [...topicAnchors.values()]
      .map((anchor) => {
        const point = rendererAny.graphToViewport?.({ x: anchor.x, y: anchor.y });
        const minPoint = rendererAny.graphToViewport?.({ x: anchor.minX, y: anchor.y });
        if (!point || !minPoint) return null;
        return {
          topic: anchor.topic,
          color: anchor.color,
          x: Math.max(10, Math.min(container.clientWidth - 130, point.x + 8)),
          y: point.y,
          minX: Math.max(0, minPoint.x)
        };
      })
      .filter((label): label is { topic: string; color: string; x: number; y: number; minX: number } => Boolean(label))
      .sort((a, b) => a.y - b.y);
    for (const label of labels) {
      const y = label.y;
      if (y < 14 || y > container.clientHeight - 14) continue;
      const guide = document.createElement("div");
      guide.className = "topic-guide";
      guide.style.left = `${Math.max(0, label.minX - 4)}px`;
      guide.style.top = `${y}px`;
      guide.style.width = `${Math.max(0, container.clientWidth - label.minX - 12)}px`;
      guide.style.background = colorWithAlpha(label.color, 0.08);
      overlay.appendChild(guide);
      const el = document.createElement("div");
      el.className = "topic-label";
      el.textContent = label.topic;
      el.style.left = `${label.x}px`;
      el.style.top = `${y}px`;
      el.style.color = colorWithAlpha(label.color, 0.94);
      overlay.appendChild(el);
    }
  };

  const applyFilters = (): void => {
    const query = document.querySelector<HTMLInputElement>("#search")?.value.trim().toLowerCase() ?? "";
    const topic = topicSelect?.value ?? "";
    const edgeMode = edgeModeSelect?.value ?? "structural";
    const sizeMode = document.querySelector<HTMLSelectElement>("#size-mode")?.value ?? "influence";
    const directImports = new Set(outgoing.get(selectedNode ?? "") ?? []);
    const directDependents = new Set(incoming.get(selectedNode ?? "") ?? []);
    const dependencies = selectedNode ? collectTransitive(selectedNode, outgoing) : new Set<string>();
    const dependents = selectedNode ? collectTransitive(selectedNode, incoming) : new Set<string>();
    updateEdgeModeInfo(edgeMode, selectedNode, payload);
    for (const nodeId of graph.nodes()) {
      const attrs = graph.getNodeAttributes(nodeId) as GraphNode & { baseColor: string };
      const haystack = `${nodeId} ${attrs.label} ${attrs.sampleSymbols || ""} ${attrs.descriptionTitle || ""} ${attrs.description || ""}`.toLowerCase();
      const hidden = Boolean(topic && attrs.topic !== topic) || Boolean(query && !haystack.includes(query));
      graph.setNodeAttribute(nodeId, "hidden", hidden);
      graph.setNodeAttribute(nodeId, "size", metricSize(attrs, sizeMode));
      if (!selectedNode || nodeId === selectedNode || directImports.has(nodeId) || directDependents.has(nodeId)) {
        graph.setNodeAttribute(nodeId, "color", attrs.baseColor);
      } else if (dependencies.has(nodeId) || dependents.has(nodeId)) {
        graph.setNodeAttribute(nodeId, "color", "rgba(100, 116, 139, 0.55)");
      } else {
        graph.setNodeAttribute(nodeId, "color", "rgba(148, 163, 184, 0.18)");
      }
    }
    for (const edgeId of graph.edges()) {
      const [source, target] = graph.extremities(edgeId);
      const directImport = selectedNode !== null && source === selectedNode;
      const directDependent = selectedNode !== null && target === selectedNode;
      const dependencyFlow = selectedNode !== null && !directImport && (dependencies.has(source) || dependencies.has(target));
      const dependentFlow = selectedNode !== null && !directDependent && (dependents.has(source) || dependents.has(target));
      const isStructural = Boolean(graph.getEdgeAttribute(edgeId, "isStructural"));
      let modeHidden = false;
      if (edgeMode === "structural" && !isStructural && !directImport && !directDependent) modeHidden = true;
      if (edgeMode === "selected" && !directImport && !directDependent && !dependencyFlow && !dependentFlow) modeHidden = true;
      graph.setEdgeAttribute(
        edgeId,
        "hidden",
        graph.getNodeAttribute(source, "hidden") || graph.getNodeAttribute(target, "hidden") || modeHidden
      );
      if (!selectedNode) {
        graph.setEdgeAttribute(edgeId, "color", graph.getEdgeAttribute(edgeId, "baseColor"));
        graph.setEdgeAttribute(edgeId, "size", isStructural ? 0.45 : 0.25);
      } else if (directImport) {
        graph.setEdgeAttribute(edgeId, "color", "rgba(37, 99, 235, 0.9)");
        graph.setEdgeAttribute(edgeId, "size", 2.4);
      } else if (directDependent) {
        graph.setEdgeAttribute(edgeId, "color", "rgba(22, 163, 74, 0.9)");
        graph.setEdgeAttribute(edgeId, "size", 2.4);
      } else if (dependencyFlow) {
        graph.setEdgeAttribute(edgeId, "color", "rgba(37, 99, 235, 0.09)");
        graph.setEdgeAttribute(edgeId, "size", 0.6);
      } else if (dependentFlow) {
        graph.setEdgeAttribute(edgeId, "color", "rgba(22, 163, 74, 0.09)");
        graph.setEdgeAttribute(edgeId, "size", 0.6);
      } else {
        graph.setEdgeAttribute(edgeId, "color", "rgba(148, 163, 184, 0.012)");
        graph.setEdgeAttribute(edgeId, "size", 0.25);
      }
    }
    renderer.refresh();
    renderTopicOverlay();
  };

  document.querySelector<HTMLInputElement>("#search")?.addEventListener("input", applyFilters);
  topicSelect?.addEventListener("change", applyFilters);
  edgeModeSelect?.addEventListener("change", applyFilters);
  document.querySelector<HTMLSelectElement>("#size-mode")?.addEventListener("change", applyFilters);
  document.querySelector<HTMLButtonElement>("#reset")?.addEventListener("click", () => {
    const search = document.querySelector<HTMLInputElement>("#search");
    const sizeMode = document.querySelector<HTMLSelectElement>("#size-mode");
    if (search) search.value = "";
    if (topicSelect) topicSelect.value = "";
    if (edgeModeSelect) edgeModeSelect.value = "structural";
    if (sizeMode) sizeMode.value = "influence";
    selectedNode = null;
    updateSelectedCard(null);
    applyFilters();
    renderer.getCamera().animatedReset();
  });
  document.querySelector<HTMLButtonElement>("#sidebar-toggle")?.addEventListener("click", () => {
    sidebarCollapsed = !sidebarCollapsed;
    app.classList.toggle("sidebar-collapsed", sidebarCollapsed);
    const toggle = document.querySelector<HTMLButtonElement>("#sidebar-toggle");
    if (toggle) {
      toggle.textContent = sidebarCollapsed ? "›" : "‹";
      toggle.setAttribute("aria-label", sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar");
      toggle.setAttribute("aria-expanded", String(!sidebarCollapsed));
      toggle.title = sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar";
    }
    window.setTimeout(() => {
      renderer.resize(true);
      renderTopicOverlay();
    }, 190);
  });

  renderer.on("enterNode", ({ node }) => showTooltip(graph.getNodeAttributes(node) as GraphNode));
  renderer.on("leaveNode", () => showTooltip(null));
  renderer.on("clickNode", ({ node }) => {
    selectedNode = node;
    updateSelectedCard(graph.getNodeAttributes(node) as GraphNode);
    applyFilters();
  });
  renderer.on("clickStage", () => {
    selectedNode = null;
    updateSelectedCard(null);
    applyFilters();
  });
  cameraAny.on?.("updated", renderTopicOverlay);
  window.addEventListener("resize", renderTopicOverlay);
  updateSelectedCard(null);
  applyFilters();
}).catch((error: unknown) => {
  app.innerHTML = `<pre>${String(error)}</pre>`;
});
