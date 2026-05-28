#!/usr/bin/env python3
"""Build normalized Mathlib graph data artifacts."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from mathlib_graph.io import download_hf_parquet, download_hf_rows, load_records
from mathlib_graph.pipeline import build_graph_artifacts
from mathlib_graph.source import load_mathlib_source_records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["sample", "hf", "file", "mathlib-source"], default="sample")
    parser.add_argument("--input", default="")
    parser.add_argument("--output-dir", default="data/processed")
    parser.add_argument("--raw-dir", default="data/raw")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.source == "sample":
        input_path = Path("data/sample/lean4_mathlib_sample.jsonl")
        source_name = "sample fixture"
        records = load_records(input_path)
    elif args.source == "hf":
        row_limit = int(os.environ.get("HF_ROW_LIMIT", "0") or "0")
        if row_limit:
            input_path = download_hf_rows(Path(args.raw_dir))
            source_name = "Hugging Face phanerozoic/Lean4-Mathlib rows API"
            records = load_records(input_path)
        else:
            input_path = download_hf_parquet(Path(args.raw_dir))
            source_name = "Hugging Face phanerozoic/Lean4-Mathlib"
            try:
                records = load_records(input_path)
            except Exception as exc:
                print(f"Parquet read failed ({exc}); falling back to Dataset Viewer rows API.")
                input_path = download_hf_rows(Path(args.raw_dir))
                source_name = "Hugging Face phanerozoic/Lean4-Mathlib rows API"
                records = load_records(input_path)
    elif args.source == "mathlib-source":
        source_root = Path(args.input) if args.input else Path(args.raw_dir) / "mathlib4"
        source_name = f"Full Mathlib source import graph ({source_root})"
        records = load_mathlib_source_records(source_root)
    else:
        if not args.input:
            raise SystemExit("--input is required when --source=file")
        input_path = Path(args.input)
        source_name = str(input_path)
        records = load_records(input_path)
    metrics = build_graph_artifacts(records, Path(args.output_dir), source_name)
    print(
        "Built graph artifacts: "
        f"{metrics['node_count']} nodes, {metrics['edge_count']} edges, "
        f"{metrics['community_count']} communities"
    )


if __name__ == "__main__":
    main()
