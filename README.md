# Mathlib Network Explorer

![Mathlib dependency network overview](figures/overview.png)

![Subindex analysis](figures/subindex.png)

<p align="center">
  <strong>Interactive dependency graph explorer for the Mathlib4 mathematical library.</strong>
</p>

<p align="center">
  <a href="https://github.com/leanprover-community/mathlib4">mathlib4</a> ·
  <a href="README_CN.md">中文文档</a>
</p>

---

An open-source reproduction of [Crispher/MathlibExplorer](https://github.com/Crispher/MathlibExplorer),
powered by [leanprover-community/mathlib4](https://github.com/leanprover-community/mathlib4) as
the upstream data source. The project keeps the strongest ideas from the original
tool: dependency-aware horizontal layout, topic grouping, zoom/pan navigation,
node highlighting, and precomputed graph metrics.

The main full-data path uses a local `leanprover-community/mathlib4` source
snapshot and statically parses `Mathlib/**/*.lean` import declarations. The
Hugging Face dataset `phanerozoic/Lean4-Mathlib` remains available as a theorem
and symbol-level supplement, and the sample fixture keeps tests runnable offline.

## Quick Start

Run the complete offline demo:

```bash
make all
```

This uses `data/sample/lean4_mathlib_sample.jsonl` and produces:

- `data/processed/nodes.csv`
- `data/processed/edges.csv`
- `data/processed/graph.json`
- `data/processed/metrics.json`
- `docs/index.html`

Run the full Mathlib module import network:

```bash
make mathlib-source
make data DATA_SOURCE=mathlib-source
make web
```

When built from the local Mathlib source snapshot, selected modules include an
`Open Mathlib source` link that opens the corresponding `.lean` file in the
upstream Mathlib4 GitHub repository at the exact source commit recorded in the
generated graph.

To use the Hugging Face dataset when network access is available:

```bash
make data DATA_SOURCE=hf
make web
```

For a faster real-data smoke test, cap the Dataset Viewer fallback:

```bash
make data DATA_SOURCE=hf HF_ROW_LIMIT=1000
make web
```

The current local `pyarrow` build may fail to read Hugging Face's generated
Parquet shard with a repetition-level error. The downloader records the Parquet
metadata, then automatically falls back to the Hugging Face Dataset Viewer rows
API. `HF_ROW_LIMIT=0` means "fetch all rows" through that fallback if needed;
large full-dataset pulls can take a while because the API pages at 100 rows.

If you already have a local Parquet/CSV/JSONL export:

```bash
make data DATA_SOURCE=file RAW_INPUT=/absolute/path/to/export.parquet
```

## Visualization Guide

`docs/index.html` is the dependency-light interactive demo. The sidebar can be
collapsed with the round button in the graph corner when you want a wider
overview.

Import direction determines horizontal position: modules further right have
deeper dependency chains. Topic/namespace lanes separate major mathematical areas
vertically, while a weak force refinement keeps local neighborhoods from
collapsing into identical rows.

Click a node to highlight its direct neighbors, transitive dependencies, and
transitive dependents:

- Direct import edges are shown in blue; direct reverse-dependency edges in green.
- Transitive relations remain visible with a weaker color.
- Unrelated nodes and edges are faded.

The default edge view shows the transitive-reduction backbone. The raw import
mode restores all source import edges, and selected-only mode focuses on the
currently selected module's local flow.

detailed node information and dependency view.

![Hausdorff dimension analysis](figures/hausdorff.png)

Lie group node search and local neighborhood exploration.

![Lie group and algebra structure](figures/lie.png)

## Project Layout

- `scripts/`: data extraction and graph pipeline
- `scripts/mathlib_graph/`: reusable graph pipeline package
- `web/`: TypeScript + Vite + Sigma.js/Graphology frontend scaffold
- `docs/`: static deliverable and project notes
- `data/sample/`: offline fixture
- `data/raw/`: [leanprover-community/mathlib4](https://github.com/leanprover-community/mathlib4) source snapshot
- `data/processed/`: generated graph data
- `tests/`: offline unit tests

## Main Commands

```bash
make mathlib-source # Download a mathlib4 source snapshot
make data           # Build nodes.csv, edges.csv, graph.json, metrics.json
make web            # Build static interactive page in docs/index.html
make web-vite       # Build the long-term Vite/Sigma frontend when npm deps are available
make test           # Run offline tests
make all            # Full artifact pipeline
```

Use `make mathlib-source MATHLIB_FORCE=1` to force-refresh the cached Mathlib
source snapshot.

## Data Model

The stable generated files are:

- `nodes.csv`: one module per row, with centrality, community, depth, layout, and topic fields.
- `edges.csv`: one import relation per row, `source imports target`.
- `graph.json`: frontend-ready graph payload; local Mathlib source builds also include `sourceFile`, `sourceUri`, and `sourceRef` on nodes.
- `metrics.json`: counts, validation checks, and top analytic results.
