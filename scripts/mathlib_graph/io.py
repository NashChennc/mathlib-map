"""Input/output helpers for Mathlib graph artifacts."""

from __future__ import annotations

import ast
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd

HF_DATASET = "phanerozoic/Lean4-Mathlib"
HF_PARQUET_API = f"https://datasets-server.huggingface.co/parquet?dataset={HF_DATASET}"
HF_ROWS_API = "https://datasets-server.huggingface.co/rows"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def filename_to_module(filename: str | None) -> str | None:
    if not filename or not isinstance(filename, str):
        return None
    cleaned = filename.strip().replace("\\", "/")
    if cleaned.endswith(".lean"):
        cleaned = cleaned[:-5]
    cleaned = cleaned.strip("/")
    if not cleaned:
        return None
    return ".".join(part for part in cleaned.split("/") if part)


def normalize_import(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            try:
                parsed = ast.literal_eval(stripped)
                return normalize_import(parsed)
            except (SyntaxError, ValueError):
                pass
        return [part.strip() for part in stripped.split(",") if part.strip()]
    return [str(value).strip()]


def load_records(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".jsonl", ".ndjson"}:
        return pd.read_json(path, lines=True)
    if suffix == ".json":
        return pd.read_json(path)
    raise ValueError(f"Unsupported input format: {path}")


def download_hf_parquet(raw_dir: Path) -> Path:
    ensure_dir(raw_dir)
    metadata_path = raw_dir / "hf_parquet_files.json"
    with urllib.request.urlopen(HF_PARQUET_API, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    parquet_files = payload.get("parquet_files") or []
    if not parquet_files:
        raise RuntimeError("Hugging Face dataset server returned no parquet files.")
    first = parquet_files[0]
    url = first.get("url")
    filename = first.get("filename") or "lean4_mathlib.parquet"
    if not url:
        raise RuntimeError("Hugging Face parquet metadata did not include a URL.")
    output_path = raw_dir / Path(filename).name
    urllib.request.urlretrieve(url, output_path)
    return output_path


def download_hf_rows(raw_dir: Path, limit: int | None = None, page_size: int = 100) -> Path:
    ensure_dir(raw_dir)
    output_path = raw_dir / "lean4_mathlib_rows.jsonl"
    page_size = min(max(page_size, 1), 100)
    if limit is None:
        limit = int(os.environ.get("HF_ROW_LIMIT", "0") or "0")

    rows_written = 0
    total_rows = None
    with output_path.open("w", encoding="utf-8") as handle:
        while total_rows is None or rows_written < total_rows:
            if limit and rows_written >= limit:
                break
            length = page_size if not limit else min(page_size, limit - rows_written)
            query = urllib.parse.urlencode(
                {
                    "dataset": HF_DATASET,
                    "config": "default",
                    "split": "train",
                    "offset": rows_written,
                    "length": length,
                }
            )
            with urllib.request.urlopen(f"{HF_ROWS_API}?{query}", timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
            total_rows = int(payload.get("num_rows_total") or 0)
            page_rows = payload.get("rows") or []
            if not page_rows:
                break
            for item in page_rows:
                handle.write(json.dumps(item.get("row", {}), ensure_ascii=False))
                handle.write("\n")
            rows_written += len(page_rows)

    if rows_written == 0:
        raise RuntimeError("Hugging Face Dataset Viewer returned no rows.")
    metadata = {
        "dataset": HF_DATASET,
        "rows_written": rows_written,
        "total_rows": total_rows,
        "limited": bool(limit),
    }
    (raw_dir / "hf_rows_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return output_path


def write_csv(df: pd.DataFrame, path: Path) -> None:
    ensure_dir(path.parent)
    df.to_csv(path, index=False)


def write_json(payload: dict[str, Any], path: Path) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
