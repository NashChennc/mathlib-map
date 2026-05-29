"""Build Mathlib module dependency graph artifacts."""

from __future__ import annotations

import json
import math
import random
import urllib.parse
from collections import Counter, defaultdict
from datetime import UTC, datetime
from hashlib import blake2b
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd

from .io import filename_to_module, normalize_import, write_csv, write_json
from .topics import band_for_topic, color_for_topic, namespace_lane, sub_namespace, topic_from_module

_PHYSICS_CFG_PATH = Path(__file__).parent / "physics_config.json"


def _load_physics_config() -> dict[str, float]:
    if _PHYSICS_CFG_PATH.exists():
        raw = json.loads(_PHYSICS_CFG_PATH.read_text())
        return {k: float(v) for k, v in raw.items() if k[0].isalpha() and k.isupper()}
    raise FileNotFoundError(f"Physics config not found at {_PHYSICS_CFG_PATH}")


_CFG = _load_physics_config()

LAYER_GAP = _CFG["LAYER_GAP"]
ANCESTOR_SCALE = _CFG["ANCESTOR_SCALE"]
LANE_GAP = _CFG["LANE_GAP"]
TOPIC_GAP_MULTIPLIER = _CFG["TOPIC_GAP_MULTIPLIER"]
LANE_SUB_OFFSET = _CFG["LANE_SUB_OFFSET"]
MAX_X_DEVIATION_FRAC = _CFG["MAX_X_DEVIATION_FRAC"]
MAX_Y_DEVIATION_FRAC = _CFG["MAX_Y_DEVIATION_FRAC"]
FORCE_SEED = int(_CFG["FORCE_SEED"])
FORCE_ITERATIONS = int(_CFG["FORCE_ITERATIONS"])
ANCHOR_FORCE_STRENGTH = _CFG["ANCHOR_FORCE_STRENGTH"]
COLLISION_RADIUS = _CFG["COLLISION_RADIUS"]
COLLISION_FORCE_STRENGTH = _CFG["COLLISION_FORCE_STRENGTH"]
COLLISION_FORCE_CUTOFF_MULTIPLIER = _CFG["COLLISION_FORCE_CUTOFF_MULTIPLIER"]
SPRING_FORCE_STRENGTH = _CFG["SPRING_FORCE_STRENGTH"]
INITIAL_JITTER_FRAC = _CFG["INITIAL_JITTER_FRAC"]
DAMPING_START = _CFG["DAMPING_START"]
DAMPING_END = _CFG["DAMPING_END"]
VELOCITY_DECAY_START = _CFG["VELOCITY_DECAY_START"]
VELOCITY_DECAY_END = _CFG["VELOCITY_DECAY_END"]
BASE_SPACING = _CFG["BASE_SPACING"]
BUBBLE_BASE_RADIUS = _CFG["BUBBLE_BASE_RADIUS"]
BUBBLE_LOG_SCALE = _CFG["BUBBLE_LOG_SCALE"]


def _sp(value: float) -> float:
    """Convert a normalized config value to absolute spatial units."""
    return value * BASE_SPACING


def _normalized_step(value: float) -> float:
    """Convert a normalized per-iteration step to absolute spatial units."""
    return value * BASE_SPACING


def _max_deviation(frac: float, gap: float) -> float | None:
    """Return an absolute clamp radius, or None when that axis is unclamped."""
    return frac * _sp(gap) if frac >= 0 else None


def _jitter_reference(max_deviation: float | None, gap: float) -> float:
    """Use the clamp radius for jitter, falling back to one gap when unclamped."""
    return max_deviation if max_deviation is not None else _sp(gap)


def _bubble_radius(descendant_count: int) -> float:
    return (BUBBLE_BASE_RADIUS + BUBBLE_LOG_SCALE * math.log1p(max(0, descendant_count))) * BASE_SPACING


def _collision_pair_radius_scale() -> float:
    return 1.0 + max(0.0, COLLISION_RADIUS)


def _safe_str(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def _safe_bool(value: Any) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _fallback_description(module: str, topic: str) -> tuple[str, str]:
    return module.removeprefix("Mathlib."), f"Full Mathlib source module in {topic}."


def _module_rows(records: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    required = {"filename", "imports"}
    missing = required - set(records.columns)
    if missing:
        raise ValueError(f"Input data is missing required columns: {sorted(missing)}")

    rows: dict[str, dict[str, Any]] = {}
    edge_set: set[tuple[str, str]] = set()
    duplicate_edges = 0
    missing_filename_rows = 0

    for _, row in records.iterrows():
        module = filename_to_module(_safe_str(row.get("filename")))
        if not module:
            missing_filename_rows += 1
            continue
        library = _safe_str(row.get("library")) or topic_from_module(module)
        topic = topic_from_module(module, library)
        fallback_title, fallback_description = _fallback_description(module, topic)
        description_title = _safe_str(row.get("description_title")) or fallback_title
        description = _safe_str(row.get("description")) or _safe_str(row.get("docstring")) or fallback_description
        has_description = _safe_bool(row.get("has_description"))
        node = rows.setdefault(
            module,
            {
                "id": module,
                "label": module.removeprefix("Mathlib."),
                "library": library,
                "topic": topic,
                "filename": _safe_str(row.get("filename")),
                "n_symbols": 0,
                "is_import_only": False,
                "type_counts": Counter(),
                "symbols": [],
                "docstring_count": 0,
                "description_title": description_title,
                "description": description,
                "has_description": has_description,
            },
        )
        if node["is_import_only"]:
            node["library"] = library
            node["topic"] = topic
            node["filename"] = _safe_str(row.get("filename"))
            node["is_import_only"] = False
        if has_description and not node["has_description"]:
            node["description_title"] = description_title
            node["description"] = description
            node["has_description"] = True
        elif not node["description"] and description:
            node["description_title"] = description_title
            node["description"] = description
        node["n_symbols"] += 1
        typ = _safe_str(row.get("type")) or "unknown"
        node["type_counts"][typ] += 1
        symbolic_name = _safe_str(row.get("symbolic_name"))
        if symbolic_name and len(node["symbols"]) < 8:
            node["symbols"].append(symbolic_name)
        if _safe_str(row.get("docstring")):
            node["docstring_count"] += 1

        for target in normalize_import(row.get("imports")):
            if not target:
                continue
            if not target.startswith("Mathlib."):
                target = filename_to_module(target) or target
            edge = (module, target)
            if edge in edge_set:
                duplicate_edges += 1
            edge_set.add(edge)
            if target not in rows:
                topic = topic_from_module(target)
                fallback_title, fallback_description = _fallback_description(target, topic)
                rows[target] = {
                    "id": target,
                    "label": target.removeprefix("Mathlib."),
                    "library": topic,
                    "topic": topic,
                    "filename": "",
                    "n_symbols": 0,
                    "is_import_only": True,
                    "type_counts": Counter(),
                    "symbols": [],
                    "docstring_count": 0,
                    "description_title": fallback_title,
                    "description": fallback_description,
                    "has_description": False,
                }

    node_records = []
    for node in rows.values():
        counts = dict(node.pop("type_counts"))
        node["type_counts"] = json.dumps(counts, ensure_ascii=False, sort_keys=True)
        node["sample_symbols"] = "; ".join(node.pop("symbols"))
        node_records.append(node)

    edges = [
        {
            "source": source,
            "target": target,
            "source_library": rows.get(source, {}).get("library", topic_from_module(source)),
            "target_library": rows.get(target, {}).get("library", topic_from_module(target)),
            "kind": "imports",
        }
        for source, target in sorted(edge_set)
    ]
    metrics = {
        "source_rows": int(len(records)),
        "missing_filename_rows": int(missing_filename_rows),
        "duplicate_edges_removed": int(duplicate_edges),
    }
    return pd.DataFrame(node_records), pd.DataFrame(edges), metrics


def _compute_rank(graph: nx.DiGraph) -> tuple[dict[str, int], bool, list[list[str]]]:
    dep_to_depends = graph.reverse(copy=True)
    if nx.is_directed_acyclic_graph(dep_to_depends):
        rank = {node: 0 for node in dep_to_depends.nodes}
        for node in nx.topological_sort(dep_to_depends):
            for child in dep_to_depends.successors(node):
                rank[child] = max(rank[child], rank[node] + 1)
        return rank, True, []

    cycle_examples: list[list[str]] = []
    try:
        for cycle in nx.simple_cycles(dep_to_depends, length_bound=6):
            cycle_examples.append(cycle)
            if len(cycle_examples) >= 5:
                break
    except Exception:
        pass

    condensed = nx.condensation(dep_to_depends)
    component_rank = {node: 0 for node in condensed.nodes}
    for node in nx.topological_sort(condensed):
        for child in condensed.successors(node):
            component_rank[child] = max(component_rank[child], component_rank[node] + 1)
    mapping = condensed.graph["mapping"]
    return {node: component_rank[mapping[node]] for node in dep_to_depends.nodes}, False, cycle_examples


def _compute_ancestors_and_descendants(graph: nx.DiGraph) -> tuple[dict[str, int], dict[str, int]]:
    ancestors: dict[str, int] = {}
    descendants: dict[str, int] = {}
    for node in graph.nodes:
        ancestors[node] = len(nx.descendants(graph, node))
        descendants[node] = len(nx.ancestors(graph, node))
    return ancestors, descendants


def _compute_transitive_reduction(graph: nx.DiGraph, is_dag: bool) -> tuple[set[tuple[str, str]], int]:
    if is_dag:
        reduced = nx.algorithms.dag.transitive_reduction(graph)
        structural = set(reduced.edges)
    else:
        condensation = nx.condensation(graph)
        reduced = nx.algorithms.dag.transitive_reduction(condensation)
        mapping = condensation.graph["mapping"]
        structural: set[tuple[str, str]] = set()
        for u, v in graph.edges:
            cu = mapping[u]
            cv = mapping[v]
            if cu == cv:
                structural.add((u, v))
            elif reduced.has_edge(cu, cv):
                structural.add((u, v))
    raw_count = graph.number_of_edges()
    return structural, raw_count - len(structural)


def _stable_bucket(value: str, buckets: int) -> int:
    digest = blake2b(value.encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(digest, "big") % buckets


def _compute_initial_coords(
    nodes: pd.DataFrame,
    rank_map: dict[str, int],
    ancestor_map: dict[str, int],
) -> tuple[dict[str, float], dict[str, float], dict[str, str], dict[str, int]]:
    x0_map: dict[str, float] = {}
    y0_map: dict[str, float] = {}
    lane_map: dict[str, str] = {}
    index_map: dict[str, int] = {}

    by_topic_lane: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in nodes.itertuples(index=False):
        lane = namespace_lane(row.id)
        topic = row.topic
        by_topic_lane[(topic, lane)].append(row.id)

    for (topic, lane), mods in by_topic_lane.items():
        by_topic_lane[(topic, lane)] = sorted(mods)

    lane_order: dict[str, list[str]] = defaultdict(list)
    for topic, lane in sorted(by_topic_lane):
        lane_order[topic].append(lane)

    lane_y_base: dict[str, float] = {}
    y_cursor = 0.0
    for topic in sorted(lane_order, key=band_for_topic):
        lanes = lane_order[topic]
        for li, lane in enumerate(lanes):
            lane_y_base[lane] = y_cursor + li * _sp(LANE_GAP)
        y_cursor += max(1, len(lanes)) * _sp(LANE_GAP) + _sp(LANE_GAP) * TOPIC_GAP_MULTIPLIER

    for node_id in nodes["id"]:
        lane = namespace_lane(node_id)
        base_y = lane_y_base.get(lane, band_for_topic(topic_from_module(node_id)))
        sub = sub_namespace(node_id)
        sub_parts = sub.split(".") if sub else []
        sub_offset = 0.0
        if sub_parts:
            sub_idx = _stable_bucket(sub_parts[0], 13) - 6
            sub_offset = sub_idx * LANE_SUB_OFFSET * _sp(LANE_GAP)
        rank_val = rank_map.get(node_id, 0)
        anc = ancestor_map.get(node_id, 0)
        x0_map[node_id] = rank_val * _sp(LAYER_GAP) + math.log1p(anc) * ANCESTOR_SCALE * BASE_SPACING
        y0_map[node_id] = base_y + sub_offset
        lane_map[node_id] = lane
        index_map[node_id] = by_topic_lane.get((topic_from_module(node_id), lane), []).index(node_id)

    return x0_map, y0_map, lane_map, index_map


def _community_map(graph: nx.DiGraph) -> dict[str, int]:
    undirected = graph.to_undirected()
    if undirected.number_of_edges() == 0:
        return {node: 0 for node in undirected.nodes}
    try:
        communities = nx.algorithms.community.louvain_communities(undirected, seed=42)
    except Exception:
        communities = nx.algorithms.community.greedy_modularity_communities(undirected)
    result: dict[str, int] = {}
    for idx, community in enumerate(communities):
        for node in community:
            result[node] = idx
    return result


def _force_refine(
    graph: nx.DiGraph,
    x0_map: dict[str, float],
    y0_map: dict[str, float],
    structural_edges: set[tuple[str, str]],
    bubble_radius_map: dict[str, float],
) -> dict[str, tuple[float, float]]:
    rng = random.Random(FORCE_SEED)
    max_dx = _max_deviation(MAX_X_DEVIATION_FRAC, LAYER_GAP)
    max_dy = _max_deviation(MAX_Y_DEVIATION_FRAC, LANE_GAP)
    jitter_dx = _jitter_reference(max_dx, LAYER_GAP)
    jitter_dy = _jitter_reference(max_dy, LANE_GAP)

    node_list = sorted(x0_map)
    collision_radius_scale = _collision_pair_radius_scale()
    collision_step = _normalized_step(COLLISION_FORCE_STRENGTH)
    collision_force_max = (
        collision_step * COLLISION_FORCE_CUTOFF_MULTIPLIER
        if COLLISION_FORCE_CUTOFF_MULTIPLIER > 0
        else None
    )
    spring_step = _normalized_step(SPRING_FORCE_STRENGTH)
    collision_radii = {
        node: bubble_radius_map.get(node, _bubble_radius(0)) * collision_radius_scale
        for node in node_list
    }
    default_collision_radius = _bubble_radius(0) * collision_radius_scale
    max_pair_collision_radius = max((radius * 2 for radius in collision_radii.values()), default=max(1.0, default_collision_radius * 2))
    cell_size = max(1.0, max_pair_collision_radius)
    positions: dict[str, list[float]] = {
        node: [
            x0_map[node] + rng.uniform(-INITIAL_JITTER_FRAC, INITIAL_JITTER_FRAC) * jitter_dx,
            y0_map[node] + rng.uniform(-INITIAL_JITTER_FRAC, INITIAL_JITTER_FRAC) * jitter_dy,
        ]
        for node in node_list
    }
    velocities: dict[str, list[float]] = {node: [0.0, 0.0] for node in node_list}

    for iteration in range(FORCE_ITERATIONS):
        progress = iteration / max(1, FORCE_ITERATIONS - 1)
        damping = DAMPING_START + (DAMPING_END - DAMPING_START) * progress
        velocity_decay = VELOCITY_DECAY_START + (VELOCITY_DECAY_END - VELOCITY_DECAY_START) * progress
        forces: dict[str, list[float]] = {node: [0.0, 0.0] for node in node_list}

        for node in node_list:
            x, y = positions[node]
            x0 = x0_map[node]
            y0 = y0_map[node]
            forces[node][0] += ANCHOR_FORCE_STRENGTH * (x0 - x)
            forces[node][1] += ANCHOR_FORCE_STRENGTH * (y0 - y)

        xs = [positions[n][0] for n in node_list]
        ys = [positions[n][1] for n in node_list]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        grid_width = max(max_x - min_x, 1.0)
        grid_height = max(max_y - min_y, 1.0)
        grid_cols = max(1, int(grid_width / cell_size))
        grid_rows = max(1, int(grid_height / cell_size))
        spatial: dict[tuple[int, int], list[str]] = defaultdict(list)
        for node in node_list:
            cx = int((positions[node][0] - min_x) / grid_width * (grid_cols - 1)) if grid_cols > 0 else 0
            cy = int((positions[node][1] - min_y) / grid_height * (grid_rows - 1)) if grid_rows > 0 else 0
            spatial[(cx, cy)].append(node)

        for node in node_list:
            x, y = positions[node]
            cx = int((x - min_x) / grid_width * (grid_cols - 1)) if grid_cols > 0 else 0
            cy = int((y - min_y) / grid_height * (grid_rows - 1)) if grid_rows > 0 else 0
            for dcx in (-1, 0, 1):
                for dcy in (-1, 0, 1):
                    for other in spatial.get((cx + dcx, cy + dcy), []):
                        if other <= node:
                            continue
                        ox, oy = positions[other]
                        dx = x - ox
                        dy = y - oy
                        dist_sq = dx * dx + dy * dy + 0.01
                        pair_radius = collision_radii[node] + collision_radii[other]
                        if dist_sq < pair_radius * pair_radius:
                            normalized_dist_sq = dist_sq / (pair_radius * pair_radius)
                            force = collision_step / normalized_dist_sq
                            if collision_force_max is not None:
                                force = min(force, collision_force_max)
                            fx = (dx / math.sqrt(dist_sq)) * force
                            fy = (dy / math.sqrt(dist_sq)) * force
                            forces[node][0] += fx
                            forces[node][1] += fy
                            forces[other][0] -= fx
                            forces[other][1] -= fy

        for u, v in structural_edges:
            if u in positions and v in positions:
                ux, uy = positions[u]
                vx, vy = positions[v]
                dx = vx - ux
                dy = vy - uy
                dist = math.sqrt(dx * dx + dy * dy) + 0.01
                fx = spring_step * dx / dist
                fy = spring_step * dy / dist
                forces[u][0] += fx
                forces[u][1] += fy
                forces[v][0] -= fx
                forces[v][1] -= fy

        for node in node_list:
            fx, fy = forces[node]
            vx, vy = velocities[node]
            vx = vx * velocity_decay + fx * damping
            vy = vy * velocity_decay + fy * damping
            positions[node][0] += vx
            positions[node][1] += vy
            if max_dx is not None:
                min_x_allowed = x0_map[node] - max_dx
                max_x_allowed = x0_map[node] + max_dx
                if positions[node][0] < min_x_allowed:
                    positions[node][0] = min_x_allowed
                    vx = 0.0
                elif positions[node][0] > max_x_allowed:
                    positions[node][0] = max_x_allowed
                    vx = 0.0
            if max_dy is not None:
                min_y_allowed = y0_map[node] - max_dy
                max_y_allowed = y0_map[node] + max_dy
                if positions[node][1] < min_y_allowed:
                    positions[node][1] = min_y_allowed
                    vy = 0.0
                elif positions[node][1] > max_y_allowed:
                    positions[node][1] = max_y_allowed
                    vy = 0.0
            velocities[node][0] = vx
            velocities[node][1] = vy

    return {node: (pos[0], pos[1]) for node, pos in positions.items()}


def _betweenness(graph: nx.DiGraph) -> dict[str, float]:
    if graph.number_of_edges() == 0:
        return {node: 0.0 for node in graph.nodes}
    if graph.number_of_nodes() > 700:
        k = min(350, graph.number_of_nodes())
        return nx.betweenness_centrality(graph, k=k, seed=42, normalized=True)
    return nx.betweenness_centrality(graph, normalized=True)


def _assign_metrics(nodes: pd.DataFrame, edges: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes["id"].tolist())
    graph.add_edges_from(edges[["source", "target"]].itertuples(index=False, name=None))

    rank_map, is_dag, cycle_examples = _compute_rank(graph)
    ancestor_map, descendant_map = _compute_ancestors_and_descendants(graph)
    structural_edges, redundant_count = _compute_transitive_reduction(graph, is_dag)
    communities = _community_map(graph)
    betweenness = _betweenness(graph)
    pagerank = nx.pagerank(graph) if graph.number_of_edges() else {node: 0.0 for node in graph.nodes}

    x0_map, y0_map, lane_map, index_map = _compute_initial_coords(nodes, rank_map, ancestor_map)
    bubble_radius_map = {node: _bubble_radius(descendant_map.get(node, 0)) for node in graph.nodes}
    refined = _force_refine(graph, x0_map, y0_map, structural_edges, bubble_radius_map)

    max_pr = max(pagerank.values()) if pagerank else 1.0
    if max_pr <= 0:
        max_pr = 1.0

    enriched = nodes.copy()
    enriched["in_degree"] = enriched["id"].map(dict(graph.in_degree())).fillna(0).astype(int)
    enriched["out_degree"] = enriched["id"].map(dict(graph.out_degree())).fillna(0).astype(int)
    enriched["n_dependents"] = enriched["in_degree"]
    enriched["n_dependencies"] = enriched["out_degree"]
    enriched["depth"] = enriched["id"].map(rank_map).fillna(0).astype(int)
    enriched["rank"] = enriched["depth"]
    enriched["ancestor_count"] = enriched["id"].map(ancestor_map).fillna(0).astype(int)
    enriched["descendant_count"] = enriched["id"].map(descendant_map).fillna(0).astype(int)
    enriched["transitive_dependency_count"] = enriched["descendant_count"]
    enriched["community"] = enriched["id"].map(communities).fillna(0).astype(int)
    enriched["betweenness"] = enriched["id"].map(betweenness).fillna(0.0).astype(float)
    enriched["pagerank"] = enriched["id"].map(pagerank).fillna(0.0).astype(float)
    enriched["color"] = enriched["topic"].map(color_for_topic)
    enriched["namespace_lane"] = enriched["id"].map(lane_map).fillna("")
    enriched["sub_namespace"] = enriched["id"].map(lambda n: sub_namespace(n)).fillna("")
    enriched["lane_index"] = enriched["id"].map(index_map).fillna(0).astype(int)
    enriched["x0"] = enriched["id"].map(x0_map).astype(float)
    enriched["y0"] = enriched["id"].map(y0_map).astype(float)
    enriched["x"] = enriched["id"].map(lambda n: refined.get(n, (x0_map.get(n, 0.0), y0_map.get(n, 0.0)))[0]).astype(float)
    enriched["y"] = enriched["id"].map(lambda n: refined.get(n, (x0_map.get(n, 0.0), y0_map.get(n, 0.0)))[1]).astype(float)
    enriched["radius"] = enriched["id"].map(bubble_radius_map).astype(float)

    edge_struct = set(structural_edges)
    edges_out = edges.copy()
    edges_out["is_structural"] = edges_out.apply(lambda r: (r["source"], r["target"]) in edge_struct, axis=1)

    isolated = [node for node in graph.nodes if graph.degree(node) == 0]
    cross_topic_edges = int(
        sum(
            1
            for source, target in graph.edges
            if topic_from_module(source) != topic_from_module(target)
        )
    )
    top_betweenness = (
        enriched.sort_values("betweenness", ascending=False)
        .head(20)[["id", "topic", "betweenness", "pagerank", "n_dependents", "n_dependencies"]]
        .to_dict(orient="records")
    )
    top_pagerank = (
        enriched.sort_values("pagerank", ascending=False)
        .head(20)[["id", "topic", "pagerank", "betweenness", "n_dependents", "n_dependencies"]]
        .to_dict(orient="records")
    )
    raw_edge_count = int(graph.number_of_edges())
    max_x_deviation = _max_deviation(MAX_X_DEVIATION_FRAC, LAYER_GAP)
    max_y_deviation = _max_deviation(MAX_Y_DEVIATION_FRAC, LANE_GAP)
    jitter_x = INITIAL_JITTER_FRAC * _jitter_reference(max_x_deviation, LAYER_GAP)
    jitter_y = INITIAL_JITTER_FRAC * _jitter_reference(max_y_deviation, LANE_GAP)
    collision_pair_radius_scale = _collision_pair_radius_scale()
    collision_force_step = _normalized_step(COLLISION_FORCE_STRENGTH)
    collision_force_max = (
        collision_force_step * COLLISION_FORCE_CUTOFF_MULTIPLIER
        if COLLISION_FORCE_CUTOFF_MULTIPLIER > 0
        else None
    )
    max_bubble_radius = max(bubble_radius_map.values()) if bubble_radius_map else _bubble_radius(0)
    bubble_base_radius = _sp(BUBBLE_BASE_RADIUS)
    collision_base_pair_padding = 2 * bubble_base_radius * (collision_pair_radius_scale - 1.0)
    collision_base_pair_radius = 2 * bubble_base_radius * collision_pair_radius_scale
    max_collision_pair_radius = 2 * max_bubble_radius * collision_pair_radius_scale
    metrics = {
        "node_count": int(graph.number_of_nodes()),
        "edge_count": raw_edge_count,
        "raw_edge_count": raw_edge_count,
        "structural_edge_count": len(structural_edges),
        "redundant_import_edge_count": redundant_count,
        "isolated_node_count": int(len(isolated)),
        "cross_topic_edge_count": cross_topic_edges,
        "had_cycles": not is_dag,
        "is_dag": is_dag,
        "cycle_examples": cycle_examples,
        "community_count": int(enriched["community"].nunique()),
        "max_depth": int(enriched["depth"].max()) if len(enriched) else 0,
        "layout_mode": "force_refined",
        "physics_config": dict(sorted(_CFG.items())),
        "physics_units": {
            "normalized_spatial_values": "actual layout units = config value * base_spacing",
            "topic_bands": "topic band numbers define ordering only; spacing is controlled by LANE_GAP and TOPIC_GAP_MULTIPLIER",
            "force_strengths": "anchor strength is dimensionless; collision and spring strengths are normalized per-iteration steps, actual layout-unit step = config value * base_spacing, damping scales force contribution, and velocity decay dissipates stored velocity",
            "collision": "reference distance = (bubble_radius(source) + bubble_radius(target)) * collision_pair_radius_scale; at that distance normalized force equals COLLISION_FORCE_STRENGTH; close-range force is capped by COLLISION_FORCE_CUTOFF_MULTIPLIER when enabled",
            "rendering": "frontends render with a uniform x/y scale and no display-only y compression",
        },
        "base_spacing": BASE_SPACING,
        "layer_gap": _sp(LAYER_GAP),
        "lane_gap": _sp(LANE_GAP),
        "topic_gap_multiplier": TOPIC_GAP_MULTIPLIER,
        "topic_gap": _sp(LANE_GAP) * TOPIC_GAP_MULTIPLIER,
        "bubble_base_radius": bubble_base_radius,
        "bubble_log_scale": _sp(BUBBLE_LOG_SCALE),
        "bubble_base_radius_normalized": BUBBLE_BASE_RADIUS,
        "bubble_log_scale_normalized": BUBBLE_LOG_SCALE,
        "max_x_deviation": max_x_deviation,
        "max_y_deviation": max_y_deviation,
        "max_x_deviation_enabled": max_x_deviation is not None,
        "max_y_deviation_enabled": max_y_deviation is not None,
        "collision_radius": collision_base_pair_radius,
        "collision_padding": collision_base_pair_padding,
        "collision_padding_normalized": COLLISION_RADIUS,
        "collision_pair_radius_scale": collision_pair_radius_scale,
        "collision_base_pair_padding": collision_base_pair_padding,
        "collision_base_pair_radius": collision_base_pair_radius,
        "max_bubble_radius": max_bubble_radius,
        "max_collision_pair_radius": max_collision_pair_radius,
        "collision_force_strength": COLLISION_FORCE_STRENGTH,
        "collision_force_step": collision_force_step,
        "collision_reference_force_normalized": COLLISION_FORCE_STRENGTH,
        "collision_reference_force": collision_force_step,
        "collision_force_cutoff_multiplier": COLLISION_FORCE_CUTOFF_MULTIPLIER,
        "collision_force_cutoff_enabled": collision_force_max is not None,
        "collision_force_max": collision_force_max,
        "anchor_force_strength": ANCHOR_FORCE_STRENGTH,
        "spring_force_strength": SPRING_FORCE_STRENGTH,
        "spring_force_step": _normalized_step(SPRING_FORCE_STRENGTH),
        "initial_jitter_frac": INITIAL_JITTER_FRAC,
        "initial_jitter_x": jitter_x,
        "initial_jitter_y": jitter_y,
        "velocity_decay_start": VELOCITY_DECAY_START,
        "velocity_decay_end": VELOCITY_DECAY_END,
        "force_seed": FORCE_SEED,
        "force_iterations": FORCE_ITERATIONS,
        "top_betweenness": top_betweenness,
        "top_pagerank": top_pagerank,
        "visual": {
            "label_hitbox_min": 6,
            "label_hitbox_margin": 5,
            "label_avoid_min": 5,
            "label_avoid_margin": 5,
            "edge_size_structural": 0.45,
            "edge_size_raw": 0.25,
            "edge_size_highlight": 2.4,
            "edge_size_flow": 0.6,
            "edge_size_faint": 0.25,
            "size_pagerank_base": 2.5,
            "size_pagerank_scale": 80,
            "size_betweenness_base": 3,
            "size_betweenness_scale": 80,
            "size_symbols_base": 3,
            "size_symbols_scale": 1.8,
        },
    }
    return enriched.sort_values("id").reset_index(drop=True), edges_out, metrics


def _graph_json(nodes: pd.DataFrame, edges: pd.DataFrame, metrics: dict[str, Any], source_name: str) -> dict[str, Any]:
    node_payload = []
    source_root = _safe_str(metrics.get("mathlib_source_dir"))
    resolved_source_root = Path(source_root).expanduser().resolve() if source_root else None
    for row in nodes.itertuples(index=False):
        source_file = ""
        source_uri = ""
        filename = _safe_str(row.filename)
        if resolved_source_root and filename and not bool(row.is_import_only):
            source_file = filename
            source_path = resolved_source_root / filename
            source_uri = "vscode://file" + urllib.parse.quote(source_path.as_posix(), safe="/")
        node_payload.append(
            {
                "id": row.id,
                "label": row.label,
                "library": row.library,
                "topic": row.topic,
                "community": int(row.community),
                "depth": int(row.depth),
                "rank": int(row.depth),
                "x": float(row.x),
                "y": float(row.y),
                "x0": float(row.x0),
                "y0": float(row.y0),
                "size": float(row.radius),
                "color": row.color,
                "pagerank": float(row.pagerank),
                "betweenness": float(row.betweenness),
                "nSymbols": int(row.n_symbols),
                "nDependencies": int(row.n_dependencies),
                "nDependents": int(row.n_dependents),
                "ancestorCount": int(row.ancestor_count),
                "descendantCount": int(row.descendant_count),
                "namespaceLane": str(row.namespace_lane),
                "subNamespace": str(row.sub_namespace),
                "laneIndex": int(row.lane_index),
                "layoutMode": "force_refined",
                "sampleSymbols": row.sample_symbols,
                "isImportOnly": bool(row.is_import_only),
                "descriptionTitle": row.description_title,
                "description": row.description,
                "hasDescription": bool(row.has_description),
                "sourceFile": source_file,
                "sourceUri": source_uri,
            }
        )
    edge_payload = [
        {
            "id": f"e{idx}",
            "source": row.source,
            "target": row.target,
            "kind": row.kind,
            "crossTopic": row.source_library != row.target_library,
            "isStructural": bool(row.is_structural),
            "isRawImport": True,
        }
        for idx, row in enumerate(edges.itertuples(index=False))
    ]
    return {
        "summary": {
            "generated_at": datetime.now(UTC).isoformat(),
            "data_source": source_name,
            **metrics,
        },
        "nodes": node_payload,
        "edges": edge_payload,
    }


def build_graph_artifacts(records: pd.DataFrame, output_dir: Path, source_name: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    nodes, edges, extraction_metrics = _module_rows(records)
    nodes, edges, graph_metrics = _assign_metrics(nodes, edges)
    source_metadata = {
        key: value
        for key, value in records.attrs.items()
        if isinstance(value, (str, int, float, bool)) or value is None
    }
    metrics = {**extraction_metrics, **graph_metrics, **source_metadata, "data_source": source_name}

    write_csv(nodes, output_dir / "nodes.csv")
    write_csv(edges, output_dir / "edges.csv")
    write_json(metrics, output_dir / "metrics.json")
    write_json(_graph_json(nodes, edges, metrics, source_name), output_dir / "graph.json")
    return metrics
