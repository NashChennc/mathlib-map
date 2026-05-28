#!/usr/bin/env python3
"""Generate analysis figures from graph artifacts."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/matplotlib-cache")

import matplotlib.pyplot as plt
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/processed")
    parser.add_argument("--figures-dir", default="figures")
    return parser.parse_args()


def save_top_centrality(nodes: pd.DataFrame, output: Path) -> None:
    top = nodes.sort_values("betweenness", ascending=False).head(15).copy()
    top["short"] = top["id"].str.replace("Mathlib.", "", regex=False).str[-42:]
    plt.figure(figsize=(12, 8))
    plt.barh(top["short"][::-1], top["betweenness"][::-1], color="#2563eb")
    plt.xlabel("Betweenness centrality")
    plt.title("Bridge modules by betweenness centrality")
    plt.tight_layout()
    plt.savefig(output, dpi=180)
    plt.close()


def save_depth_distribution(nodes: pd.DataFrame, output: Path) -> None:
    plt.figure(figsize=(10, 6))
    plt.hist(nodes["depth"], bins=min(28, max(5, nodes["depth"].nunique())), color="#16a34a", edgecolor="white")
    plt.xlabel("Dependency depth")
    plt.ylabel("Module count")
    plt.title("Mathlib module depth distribution")
    plt.tight_layout()
    plt.savefig(output, dpi=180)
    plt.close()


def save_topic_community(nodes: pd.DataFrame, output: Path) -> None:
    table = pd.crosstab(nodes["topic"], nodes["community"])
    if table.shape[1] > 16:
        top_cols = table.sum(axis=0).sort_values(ascending=False).head(16).index
        table = table[top_cols]
    plt.figure(figsize=(12, max(6, 0.32 * len(table))))
    plt.imshow(table.values, aspect="auto", cmap="viridis")
    plt.colorbar(label="Module count")
    plt.xticks(range(len(table.columns)), table.columns, rotation=45, ha="right")
    plt.yticks(range(len(table.index)), table.index)
    plt.title("Topic and detected community overlap")
    plt.tight_layout()
    plt.savefig(output, dpi=180)
    plt.close()


def save_network_overview(nodes: pd.DataFrame, edges: pd.DataFrame, output: Path) -> None:
    if "is_structural" in edges.columns:
        sample_edges = edges[edges["is_structural"]].head(2500)
    else:
        sample_edges = edges.head(2500)
    positions = nodes.set_index("id")[["x", "y"]].to_dict("index")
    plt.figure(figsize=(14, 9))
    for row in sample_edges.itertuples(index=False):
        source = positions.get(row.source)
        target = positions.get(row.target)
        if not source or not target:
            continue
        plt.plot([source["x"], target["x"]], [source["y"], target["y"]], color="#cbd5e1", linewidth=0.35, alpha=0.25)
    plt.scatter(nodes["x"], nodes["y"], s=nodes["radius"] * 3, c=nodes["color"], alpha=0.88, linewidths=0)
    plt.xlabel("Import depth with weak force refinement")
    plt.ylabel("Namespace / topic lane")
    plt.title("Mathlib dependency network structural layout")
    plt.tight_layout()
    plt.savefig(output, dpi=180)
    plt.close()


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    figures_dir = Path(args.figures_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)

    nodes = pd.read_csv(data_dir / "nodes.csv")
    edges = pd.read_csv(data_dir / "edges.csv")
    metrics = json.loads((data_dir / "metrics.json").read_text(encoding="utf-8"))

    save_top_centrality(nodes, figures_dir / "centrality_top_modules.png")
    save_depth_distribution(nodes, figures_dir / "depth_distribution.png")
    save_topic_community(nodes, figures_dir / "topic_community_heatmap.png")
    save_network_overview(nodes, edges, figures_dir / "network_overview.png")
    (figures_dir / "figure_manifest.json").write_text(
        json.dumps(
            {
                "figures": [
                    "centrality_top_modules.png",
                    "depth_distribution.png",
                    "topic_community_heatmap.png",
                    "network_overview.png",
                ],
                "node_count": metrics.get("node_count"),
                "edge_count": metrics.get("edge_count"),
                "raw_edge_count": metrics.get("raw_edge_count"),
                "structural_edge_count": metrics.get("structural_edge_count"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Generated figures in {figures_dir}")


if __name__ == "__main__":
    main()
