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
  sourceFile: string;
  sourceUri: string;
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
const SELECTION_LABEL_MAX_CHARS = 48;
const SELECTION_LABEL_PADDING = 8;
const SELECTION_LABEL_GAP = 10;

type LabelRect = {
  left: number;
  top: number;
  right: number;
  bottom: number;
};

type SelectionLabel = {
  id: string;
  attrs: GraphNode;
  point: { x: number; y: number };
  radius: number;
  isSelected: boolean;
};

type PlacedSelectionLabel = SelectionLabel & {
  rect: LabelRect;
};

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
      <a id="selected-source-link" class="source-link" hidden>Open Lean file</a>
      <div class="selected-meta">
        <div><strong id="selected-deps">0</strong><span>Direct imports</span></div>
        <div><strong id="selected-dependents">0</strong><span>Direct dependents</span></div>
        <div><strong id="selected-ancestors">0</strong><span>Transitive imports</span></div>
        <div><strong id="selected-descendants">0</strong><span>Downstream users</span></div>
      </div>
      <details id="selected-detail-panel" class="detail-disclosure" hidden>
        <summary>Details</summary>
        <dl id="selected-detail-list"></dl>
        <div id="selected-neighbor-lists" class="neighbor-lists"></div>
      </details>
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
    <div id="selection-label-overlay" class="selection-label-overlay"></div>
    <svg id="hover-label-line" class="hover-label-line-layer"></svg>
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

function nodeTitle(node: GraphNode): string {
  return node.descriptionTitle || node.label || node.id;
}

function nodeSearchHaystack(node: GraphNode): string {
  return `${node.id} ${node.label} ${node.sampleSymbols || ""} ${node.descriptionTitle || ""} ${node.description || ""} ${node.sourceFile || ""}`.toLowerCase();
}

function truncateLabel(value: string, maxChars = SELECTION_LABEL_MAX_CHARS): string {
  return value.length > maxChars ? `${value.slice(0, maxChars - 3).trimEnd()}...` : value;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function rectsOverlap(a: LabelRect, b: LabelRect, padding = 0): boolean {
  return !(
    a.right + padding <= b.left ||
    a.left - padding >= b.right ||
    a.bottom + padding <= b.top ||
    a.top - padding >= b.bottom
  );
}

function overlapArea(a: LabelRect, b: LabelRect): number {
  const width = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
  const height = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
  return width * height;
}

function rectFromCenter(x: number, y: number, radius: number): LabelRect {
  return { left: x - radius, top: y - radius, right: x + radius, bottom: y + radius };
}

function placementCandidates(
  point: { x: number; y: number },
  width: number,
  height: number,
  radius: number,
  viewportWidth: number,
  viewportHeight: number
): LabelRect[] {
  const step = height + SELECTION_LABEL_GAP;
  const distances = Array.from({ length: 10 }, (_, index) => radius + SELECTION_LABEL_GAP + index * step);
  const candidates: LabelRect[] = [];
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

function connectorEndpoint(point: { x: number; y: number }, rect: LabelRect): { x: number; y: number } {
  return {
    x: clamp(point.x, rect.left, rect.right),
    y: rect.bottom <= point.y ? rect.bottom : rect.top
  };
}

function chooseLabelPlacement(
  point: { x: number; y: number },
  width: number,
  height: number,
  radius: number,
  viewportWidth: number,
  viewportHeight: number,
  avoidRects: LabelRect[],
  occupiedRects: LabelRect[]
): LabelRect {
  const candidates = placementCandidates(point, width, height, radius, viewportWidth, viewportHeight);
  const collisions = [...avoidRects, ...occupiedRects];
  for (const candidate of candidates) {
    if (!collisions.some((rect) => rectsOverlap(candidate, rect, 2))) return candidate;
  }
  return candidates.reduce((best, candidate) => {
    const score = collisions.reduce((sum, rect) => sum + overlapArea(candidate, rect), 0);
    return score < best.score ? { rect: candidate, score } : best;
  }, { rect: candidates[0], score: Number.POSITIVE_INFINITY }).rect;
}

function setText(id: string, value: unknown): void {
  const element = document.querySelector<HTMLElement>(`#${id}`);
  if (element) element.textContent = String(value ?? "-");
}

function detailRows(node: GraphNode): Array<[string, string]> {
  const rows: Array<[string, string]> = [
    ["Topic", node.topic],
    ["Lane", node.namespaceLane || "n/a"],
    ["Rank", String(node.rank ?? node.depth)],
    ["Community", String(node.community)],
    ["Depth", String(node.depth)],
    ["Dependencies", String(node.nDependencies)],
    ["Dependents", String(node.nDependents)],
    ["Transitive imports", String(node.ancestorCount ?? 0)],
    ["Downstream users", String(node.descendantCount ?? 0)],
    ["Symbols", String(node.nSymbols)],
    ["PageRank", node.pagerank.toExponential(3)],
    ["Betweenness", node.betweenness.toExponential(3)]
  ];
  if (node.sourceFile) rows.push(["Source", node.sourceFile]);
  if (node.sampleSymbols) rows.push(["Examples", node.sampleSymbols]);
  return rows;
}

function updateDetailPanel(node: GraphNode | null): void {
  const panel = document.querySelector<HTMLDetailsElement>("#selected-detail-panel");
  const list = document.querySelector<HTMLDListElement>("#selected-detail-list");
  const neighbors = document.querySelector<HTMLDivElement>("#selected-neighbor-lists");
  if (!panel || !list) return;
  list.innerHTML = "";
  if (neighbors) neighbors.innerHTML = "";
  panel.hidden = !node;
  if (!node) return;
  for (const [label, value] of detailRows(node)) {
    const term = document.createElement("dt");
    const description = document.createElement("dd");
    term.textContent = label;
    description.textContent = value;
    list.append(term, description);
  }
}

function colorWithAlpha(hex: string, alpha: number): string {
  const raw = (hex || "#64748b").replace("#", "");
  const full = raw.length === 3 ? raw.split("").map((char) => char + char).join("") : raw;
  const r = Number.parseInt(full.slice(0, 2), 16) || 100;
  const g = Number.parseInt(full.slice(2, 4), 16) || 116;
  const b = Number.parseInt(full.slice(4, 6), 16) || 139;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function updateSelectedCard(
  node: GraphNode | null,
  renderDetails: (node: GraphNode | null) => void = updateDetailPanel
): void {
  const description = document.querySelector<HTMLParagraphElement>("#selected-description");
  const sourceLink = document.querySelector<HTMLAnchorElement>("#selected-source-link");
  setText("selected-title", node ? nodeTitle(node) : "No module selected");
  setText("selected-module", node?.id || "-");
  if (description) {
    description.textContent = node?.description || "";
    description.hidden = !node;
  }
  if (sourceLink) {
    const sourceUri = node?.sourceUri || "";
    sourceLink.hidden = !sourceUri;
    sourceLink.href = sourceUri;
    sourceLink.title = node?.sourceFile ? `Open ${node.sourceFile}` : "Open Lean file";
  }
  setText("selected-deps", node?.nDependencies ?? 0);
  setText("selected-dependents", node?.nDependents ?? 0);
  setText("selected-ancestors", node?.ancestorCount ?? 0);
  setText("selected-descendants", node?.descendantCount ?? 0);
  renderDetails(node);
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
  const selectionLabelOverlay = document.querySelector<HTMLDivElement>("#selection-label-overlay");
  const hoverLabelLine = document.querySelector<SVGSVGElement>("#hover-label-line");
  const hoverLabel = document.querySelector<HTMLDivElement>("#tooltip");
  const rendererAny = renderer as unknown as {
    graphToViewport?: (coordinates: { x: number; y: number }) => { x: number; y: number };
    viewportToFramedGraph?: (coordinates: { x: number; y: number }) => { x: number; y: number };
  };
  const cameraAny = renderer.getCamera() as unknown as {
    getState?: () => { ratio?: number };
    maxRatio?: number | null;
    on?: (event: string, callback: () => void) => void;
    animate?: (
      state: { x?: number; y?: number; ratio?: number },
      options?: { duration?: number; easing?: string }
    ) => Promise<void>;
  };
  const initialRatio = Number(cameraAny.getState?.().ratio ?? 1);
  cameraAny.maxRatio = initialRatio * MAX_OVERVIEW_RATIO_MULTIPLIER;

  let selectedNode: string | null = null;
  let sidebarCollapsed = false;

  const sortedNeighborNodes = (nodeId: string, map: Map<string, Set<string>>): GraphNode[] => {
    return [...(map.get(nodeId) ?? [])]
      .filter((id) => graph.hasNode(id))
      .map((id) => graph.getNodeAttributes(id) as GraphNode)
      .sort((a, b) => nodeTitle(a).localeCompare(nodeTitle(b), undefined, { sensitivity: "base" }) || a.id.localeCompare(b.id));
  };

  const renderNeighborSection = (
    containerElement: HTMLElement,
    title: string,
    neighbors: GraphNode[]
  ): void => {
    if (!neighbors.length) return;
    const section = document.createElement("details");
    section.className = "neighbor-disclosure";
    section.open = true;
    const summary = document.createElement("summary");
    summary.textContent = `${title} (${neighbors.length})`;
    const list = document.createElement("div");
    list.className = "neighbor-list";
    for (const neighbor of neighbors) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "neighbor-link";
      button.title = neighbor.id;
      button.addEventListener("click", () => selectNodeById(neighbor.id, { focus: true }));
      const label = document.createElement("span");
      label.className = "neighbor-title";
      label.textContent = nodeTitle(neighbor);
      const id = document.createElement("span");
      id.className = "neighbor-id";
      id.textContent = neighbor.id;
      button.append(label, id);
      list.appendChild(button);
    }
    section.append(summary, list);
    containerElement.appendChild(section);
  };

  const updateDetailPanelWithNeighbors = (node: GraphNode | null): void => {
    updateDetailPanel(node);
    const containerElement = document.querySelector<HTMLDivElement>("#selected-neighbor-lists");
    if (!node || !containerElement) return;
    renderNeighborSection(containerElement, "Direct imports", sortedNeighborNodes(node.id, outgoing));
    renderNeighborSection(containerElement, "Direct dependents", sortedNeighborNodes(node.id, incoming));
  };

  const revealNodeIfFiltered = (node: GraphNode): void => {
    const search = document.querySelector<HTMLInputElement>("#search");
    const query = search?.value.trim().toLowerCase() ?? "";
    if (query && !nodeSearchHaystack(node).includes(query) && search) search.value = "";
    if (topicSelect?.value && node.topic !== topicSelect.value) topicSelect.value = "";
  };

  const focusNode = (nodeId: string): void => {
    if (!graph.hasNode(nodeId) || !rendererAny.graphToViewport || !rendererAny.viewportToFramedGraph || !cameraAny.animate) return;
    const attrs = graph.getNodeAttributes(nodeId) as GraphNode;
    const viewportPoint = rendererAny.graphToViewport({ x: attrs.x, y: attrs.y });
    const target = rendererAny.viewportToFramedGraph(viewportPoint);
    const ratio = Number(cameraAny.getState?.().ratio ?? initialRatio);
    void cameraAny.animate({ x: target.x, y: target.y, ratio }, { duration: 420, easing: "quadraticInOut" });
  };

  function selectNodeById(nodeId: string, options: { focus?: boolean; reveal?: boolean } = {}): void {
    if (!graph.hasNode(nodeId)) return;
    const attrs = graph.getNodeAttributes(nodeId) as GraphNode;
    selectedNode = nodeId;
    if (options.reveal !== false) revealNodeIfFiltered(attrs);
    updateSelectedCard(attrs, updateDetailPanelWithNeighbors);
    applyFilters();
    if (options.focus) focusNode(nodeId);
  }

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

  const renderSelectionLabels = (): void => {
    if (!selectionLabelOverlay || !rendererAny.graphToViewport) return;
    selectionLabelOverlay.innerHTML = "";
    if (!selectedNode || !graph.hasNode(selectedNode)) return;
    const labeledIds = [
      selectedNode,
      ...(outgoing.get(selectedNode) ?? []),
      ...(incoming.get(selectedNode) ?? [])
    ];
    const labels: SelectionLabel[] = [];
    for (const nodeId of new Set(labeledIds)) {
      if (!graph.hasNode(nodeId) || graph.getNodeAttribute(nodeId, "hidden")) continue;
      const attrs = graph.getNodeAttributes(nodeId) as GraphNode;
      const point = rendererAny.graphToViewport({ x: attrs.x, y: attrs.y });
      const size = Number(graph.getNodeAttribute(nodeId, "size") ?? attrs.size ?? 4);
      labels.push({
        id: nodeId,
        attrs,
        point,
        radius: Math.max(6, size + 5),
        isSelected: nodeId === selectedNode
      });
    }
    const avoidRects = labels.map((label) => rectFromCenter(label.point.x, label.point.y, label.radius + 3));
    const occupiedRects: LabelRect[] = [];
    const placedLabels: PlacedSelectionLabel[] = [];
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "selection-label-lines");
    svg.setAttribute("width", String(container.clientWidth));
    svg.setAttribute("height", String(container.clientHeight));
    svg.setAttribute("viewBox", `0 0 ${container.clientWidth} ${container.clientHeight}`);
    selectionLabelOverlay.appendChild(svg);
    for (const label of labels) {
      const el = document.createElement("div");
      el.className = label.isSelected ? "selection-node-label selected" : "selection-node-label";
      el.textContent = truncateLabel(nodeTitle(label.attrs));
      el.style.left = "0";
      el.style.top = "0";
      el.style.visibility = "hidden";
      selectionLabelOverlay.appendChild(el);
      const width = el.offsetWidth;
      const height = el.offsetHeight;
      const rect = chooseLabelPlacement(
        label.point,
        width,
        height,
        label.radius,
        container.clientWidth,
        container.clientHeight,
        avoidRects,
        occupiedRects
      );
      el.style.left = `${rect.left}px`;
      el.style.top = `${rect.top}px`;
      el.style.visibility = "";
      occupiedRects.push(rect);
      placedLabels.push({ ...label, rect });
    }
    for (const label of placedLabels) {
      const end = connectorEndpoint(label.point, label.rect);
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", String(label.point.x));
      line.setAttribute("y1", String(label.point.y));
      line.setAttribute("x2", String(end.x));
      line.setAttribute("y2", String(end.y));
      line.setAttribute("class", label.isSelected ? "selection-label-line selected" : "selection-label-line");
      svg.appendChild(line);
    }
  };

  const relatedNodeAvoidRects = (extraNodeId?: string): LabelRect[] => {
    const rects: LabelRect[] = [];
    if (!rendererAny.graphToViewport) return rects;
    const ids = selectedNode && graph.hasNode(selectedNode)
      ? new Set([
        selectedNode,
        ...(outgoing.get(selectedNode) ?? []),
        ...(incoming.get(selectedNode) ?? [])
      ])
      : new Set<string>();
    if (extraNodeId) ids.add(extraNodeId);
    for (const nodeId of ids) {
      if (!graph.hasNode(nodeId)) continue;
      if (graph.getNodeAttribute(nodeId, "hidden")) continue;
      const attrs = graph.getNodeAttributes(nodeId) as GraphNode;
      const point = rendererAny.graphToViewport({ x: attrs.x, y: attrs.y });
      const radius = Math.max(5, Number(graph.getNodeAttribute(nodeId, "size") ?? attrs.size ?? 4) + 5);
      if (
        point.x + radius < 0 ||
        point.y + radius < 0 ||
        point.x - radius > container.clientWidth ||
        point.y - radius > container.clientHeight
      ) {
        continue;
      }
      rects.push(rectFromCenter(point.x, point.y, radius));
    }
    return rects;
  };

  const selectedDetailNode = (): GraphNode | null => {
    return selectedNode && graph.hasNode(selectedNode) ? graph.getNodeAttributes(selectedNode) as GraphNode : null;
  };

  const renderHoverLabel = (nodeId: string | null): void => {
    if (!hoverLabel || !rendererAny.graphToViewport || !nodeId || !graph.hasNode(nodeId)) {
      if (hoverLabel) hoverLabel.hidden = true;
      if (hoverLabelLine) {
        hoverLabelLine.hidden = true;
        hoverLabelLine.innerHTML = "";
      }
      updateDetailPanelWithNeighbors(selectedDetailNode());
      return;
    }
    const attrs = graph.getNodeAttributes(nodeId) as GraphNode;
    const point = rendererAny.graphToViewport({ x: attrs.x, y: attrs.y });
    const size = Number(graph.getNodeAttribute(nodeId, "size") ?? attrs.size ?? 4);
    hoverLabel.textContent = truncateLabel(nodeTitle(attrs));
    hoverLabel.hidden = false;
    hoverLabel.style.visibility = "hidden";
    hoverLabel.style.left = "0";
    hoverLabel.style.top = "0";
    const rect = chooseLabelPlacement(
      point,
      hoverLabel.offsetWidth,
      hoverLabel.offsetHeight,
      Math.max(6, size + 5),
        container.clientWidth,
        container.clientHeight,
        relatedNodeAvoidRects(nodeId),
        []
      );
    hoverLabel.style.left = `${rect.left}px`;
    hoverLabel.style.top = `${rect.top}px`;
    hoverLabel.style.visibility = "";
    if (hoverLabelLine) {
      const end = connectorEndpoint(point, rect);
      hoverLabelLine.hidden = false;
      hoverLabelLine.setAttribute("width", String(container.clientWidth));
      hoverLabelLine.setAttribute("height", String(container.clientHeight));
      hoverLabelLine.setAttribute("viewBox", `0 0 ${container.clientWidth} ${container.clientHeight}`);
      hoverLabelLine.innerHTML = "";
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", String(point.x));
      line.setAttribute("y1", String(point.y));
      line.setAttribute("x2", String(end.x));
      line.setAttribute("y2", String(end.y));
      line.setAttribute("class", "hover-label-line");
      hoverLabelLine.appendChild(line);
    }
    updateDetailPanelWithNeighbors(attrs);
  };

  function applyFilters(): void {
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
      const haystack = nodeSearchHaystack(attrs);
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
    renderSelectionLabels();
    if (hoverLabel && !hoverLabel.hidden) {
      hoverLabel.hidden = true;
      if (hoverLabelLine) {
        hoverLabelLine.hidden = true;
        hoverLabelLine.innerHTML = "";
      }
      updateDetailPanelWithNeighbors(selectedDetailNode());
    }
  }

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
    updateSelectedCard(null, updateDetailPanelWithNeighbors);
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
      renderSelectionLabels();
    }, 190);
  });

  renderer.on("enterNode", ({ node }) => renderHoverLabel(node));
  renderer.on("leaveNode", () => renderHoverLabel(null));
  renderer.on("clickNode", ({ node }) => {
    selectNodeById(node, { focus: false, reveal: false });
  });
  renderer.on("clickStage", () => {
    selectedNode = null;
    updateSelectedCard(null, updateDetailPanelWithNeighbors);
    applyFilters();
  });
  cameraAny.on?.("updated", () => {
    renderTopicOverlay();
    renderSelectionLabels();
    if (hoverLabel) {
      hoverLabel.hidden = true;
      if (hoverLabelLine) {
        hoverLabelLine.hidden = true;
        hoverLabelLine.innerHTML = "";
      }
      updateDetailPanelWithNeighbors(selectedDetailNode());
    }
  });
  window.addEventListener("resize", () => {
    renderTopicOverlay();
    renderSelectionLabels();
    if (hoverLabel) {
      hoverLabel.hidden = true;
      if (hoverLabelLine) {
        hoverLabelLine.hidden = true;
        hoverLabelLine.innerHTML = "";
      }
      updateDetailPanelWithNeighbors(selectedDetailNode());
    }
  });
  updateSelectedCard(null, updateDetailPanelWithNeighbors);
  applyFilters();
}).catch((error: unknown) => {
  app.innerHTML = `<pre>${String(error)}</pre>`;
});
