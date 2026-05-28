from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts.mathlib_graph.io import filename_to_module, normalize_import
from scripts.mathlib_graph.pipeline import build_graph_artifacts
from scripts.mathlib_graph.source import extract_module_doc, load_mathlib_source_records, module_from_source_path, parse_imports


class IoTests(unittest.TestCase):
    def test_filename_to_module(self) -> None:
        self.assertEqual(
            filename_to_module("Mathlib/Algebra/Group/Defs.lean"),
            "Mathlib.Algebra.Group.Defs",
        )
        self.assertEqual(filename_to_module("Mathlib\\Data\\Nat\\Basic.lean"), "Mathlib.Data.Nat.Basic")

    def test_normalize_import(self) -> None:
        self.assertEqual(normalize_import("['Mathlib.Init', 'Mathlib.Data.Nat.Basic']"), ["Mathlib.Init", "Mathlib.Data.Nat.Basic"])
        self.assertEqual(normalize_import("Mathlib.Init, Mathlib.Logic.Basic"), ["Mathlib.Init", "Mathlib.Logic.Basic"])


class PipelineTests(unittest.TestCase):
    def test_build_graph_artifacts_schema(self) -> None:
        rows = pd.DataFrame(
            [
                {
                    "fact": "a",
                    "type": "theorem",
                    "library": "Data",
                    "imports": ["Mathlib.Init"],
                    "filename": "Mathlib/Data/A.lean",
                    "symbolic_name": "A",
                    "docstring": "A",
                },
                {
                    "fact": "b",
                    "type": "theorem",
                    "library": "Algebra",
                    "imports": ["Mathlib.Data.A", "Mathlib.Init"],
                    "filename": "Mathlib/Algebra/B.lean",
                    "symbolic_name": "B",
                    "docstring": "B",
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "one"
            metrics = build_graph_artifacts(rows, out, "unit")
            self.assertEqual(metrics["edge_count"], 3)
            self.assertTrue(metrics["is_dag"])
            self.assertEqual(metrics["raw_edge_count"], 3)
            self.assertEqual(metrics["structural_edge_count"], 2)
            self.assertEqual(metrics["redundant_import_edge_count"], 1)
            nodes = pd.read_csv(out / "nodes.csv")
            edges = pd.read_csv(out / "edges.csv")
            graph = json.loads((out / "graph.json").read_text(encoding="utf-8"))
            self.assertIn("pagerank", nodes.columns)
            self.assertIn("source", edges.columns)
            self.assertEqual(len(graph["nodes"]), metrics["node_count"])
            self.assertEqual(len(graph["edges"]), metrics["edge_count"])
            self.assertIn("force_iterations", metrics)
            self.assertIn("is_structural", edges.columns)
            self.assertIn("descriptionTitle", graph["nodes"][0])
            self.assertIn("description", graph["nodes"][0])
            self.assertIn("hasDescription", graph["nodes"][0])
            self.assertIn("rank", graph["nodes"][0])
            self.assertIn("ancestorCount", graph["nodes"][0])
            self.assertIn("descendantCount", graph["nodes"][0])
            self.assertIn("namespaceLane", graph["nodes"][0])
            self.assertIn("subNamespace", graph["nodes"][0])
            self.assertIn("laneIndex", graph["nodes"][0])
            self.assertIn("x0", graph["nodes"][0])
            self.assertIn("y0", graph["nodes"][0])
            self.assertIn("layoutMode", graph["nodes"][0])
            self.assertIn("isStructural", graph["edges"][0])
            self.assertIn("isRawImport", graph["edges"][0])

            out_two = Path(tmp) / "two"
            build_graph_artifacts(rows, out_two, "unit")
            graph_two = json.loads((out_two / "graph.json").read_text(encoding="utf-8"))
            coords_one = {node["id"]: (node["x"], node["y"]) for node in graph["nodes"]}
            coords_two = {node["id"]: (node["x"], node["y"]) for node in graph_two["nodes"]}
            self.assertEqual(coords_one, coords_two)


class SourceParserTests(unittest.TestCase):
    def test_module_from_source_path(self) -> None:
        root = Path("/tmp/mathlib4")
        path = root / "Mathlib" / "Topology" / "Basic.lean"
        self.assertEqual(module_from_source_path(path, root), "Mathlib.Topology.Basic")

    def test_parse_imports(self) -> None:
        text = """
/-!
This example import must be ignored:
```lean
import Mathlib.Bad.DocExample
```
-/
-- import Mathlib.Bad.LineComment
def snippet := "
import Mathlib.Bad.String
"
import Mathlib.Algebra.Group.Defs
public import Mathlib.Data.Set.Basic
public meta import Mathlib.Data.Finset.Basic
meta import Mathlib.Data.Int.Basic
import Mathlib.Data.Nat.Basic Mathlib.Topology.Basic -- same line
import all Mathlib.Tactic.NormNum.Prime
import Std.Data.HashMap
theorem x : True := trivial
"""
        self.assertEqual(
            parse_imports(text),
            [
                "Mathlib.Algebra.Group.Defs",
                "Mathlib.Data.Set.Basic",
                "Mathlib.Data.Finset.Basic",
                "Mathlib.Data.Int.Basic",
                "Mathlib.Data.Nat.Basic",
                "Mathlib.Topology.Basic",
                "Mathlib.Tactic.NormNum.Prime",
            ],
        )

    def test_extract_module_doc(self) -> None:
        text = """
/-!
# Typeclasses for groups

This file defines the basic typeclasses for groups and monoids.

## Main declarations

- `Monoid`
- `Group`
-/
import Mathlib.Init
"""
        title, description, has_description = extract_module_doc(text, "Mathlib.Algebra.Group.Defs", "Algebra")
        self.assertTrue(has_description)
        self.assertEqual(title, "Typeclasses for groups")
        self.assertIn("basic typeclasses", description)
        self.assertNotIn("Main declarations", description)

    def test_extract_module_doc_fallback(self) -> None:
        title, description, has_description = extract_module_doc("import Mathlib.Init\n", "Mathlib.Data.A", "Data")
        self.assertFalse(has_description)
        self.assertEqual(title, "Data.A")
        self.assertEqual(description, "Full Mathlib source module in Data.")

    def test_load_mathlib_source_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module_dir = root / "Mathlib" / "Data"
            module_dir.mkdir(parents=True)
            (module_dir / "A.lean").write_text("import Mathlib.Init\n", encoding="utf-8")
            (module_dir / "B.lean").write_text(
                "/-!\n# Module B\n\nThis module documents a small test fixture.\n-/\nimport Mathlib.Data.A\nimport Std.Data.HashMap\n",
                encoding="utf-8",
            )
            records = load_mathlib_source_records(root)
            self.assertEqual(len(records), 2)
            row = records[records["filename"] == "Mathlib/Data/B.lean"].iloc[0]
            self.assertEqual(row["imports"], ["Mathlib.Data.A"])
            self.assertEqual(row["description_title"], "Module B")
            self.assertTrue(row["has_description"])


if __name__ == "__main__":
    unittest.main()
