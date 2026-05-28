# MathlibExplorer Reference Notes

This project is inspired by `Crispher/MathlibExplorer`, but it is not a fork of
that repository.

## What We Keep

- Dependency direction shapes the layout: if module `B` imports module `A`, then
  `B` should appear farther to the right than `A`.
- The graph is precomputed before rendering. The browser should load prepared
  node positions, sizes, colors, centralities, and community ids.
- Interaction should support zooming, panning, node selection, and topic-level
  highlighting.
- Node size should encode mathematical influence, with PageRank or dependency
  centrality as the default.

## What We Change

- The implementation is web-first instead of a desktop binary.
- The data pipeline has stable CSV/JSON outputs so the frontend and analysis can
  evolve independently.
- The first version uses the public Hugging Face `phanerozoic/Lean4-Mathlib`
  dataset because the current local environment has no `lake`.
- A `lake exe graph` adapter is reserved for future refreshes from a local
  `mathlib4` checkout.

## Why Not Fork Directly

The public MathlibExplorer repository provides binaries, screenshots, and some
data/script artifacts, but not a complete maintainable application source tree.
The project owner has also explained that the original C++/bgfx code is hard to
build and that the Unity rewrite is unfinished. A clean independent repository is
therefore safer for coursework and better for long-term maintenance.

## Local Implementation Mapping

- `scripts/mathlib_graph/`: data model, graph analysis, and layout.
- `docs/index.html`: dependency-light static deliverable.
- `web/`: TypeScript/Vite/Sigma.js path for long-term frontend work.

