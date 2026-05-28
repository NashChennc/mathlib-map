#!/usr/bin/env python3
"""Download a mathlib4 source snapshot without requiring Lean or Lake."""

from __future__ import annotations

import argparse
import shutil
import tarfile
import tempfile
import json
import urllib.request
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="data/raw/mathlib4")
    parser.add_argument("--ref", default="master")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def safe_extract(tar: tarfile.TarFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in tar.getmembers():
        target = (destination / member.name).resolve()
        if destination not in target.parents and target != destination:
            raise RuntimeError(f"Unsafe tar member path: {member.name}")
    try:
        tar.extractall(destination, filter="data")
    except TypeError:
        tar.extractall(destination)


def resolve_ref_sha(ref: str) -> str:
    url = f"https://api.github.com/repos/leanprover-community/mathlib4/commits/{ref}"
    request = urllib.request.Request(url, headers={"User-Agent": "mathlib-network-explorer"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return str(payload.get("sha") or ref)
    except Exception:
        return ref


def write_marker(output_dir: Path, ref: str, commit: str) -> None:
    marker = output_dir / ".mathlib_source_ref"
    marker.write_text(
        f"mathlib_source_dir={output_dir}\nmathlib_source_ref={ref}\nmathlib_source_commit={commit}\n",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    commit = resolve_ref_sha(args.ref)
    if (output_dir / "Mathlib").is_dir() and not args.force:
        write_marker(output_dir, args.ref, commit)
        print(f"Mathlib source already exists: {output_dir}")
        return
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://codeload.github.com/leanprover-community/mathlib4/tar.gz/{args.ref}"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        archive = tmp_path / "mathlib4.tar.gz"
        print(f"Downloading {url}")
        urllib.request.urlretrieve(url, archive)
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()
        with tarfile.open(archive, "r:gz") as tar:
            safe_extract(tar, extract_dir)
        roots = [path for path in extract_dir.iterdir() if path.is_dir()]
        if len(roots) != 1:
            raise RuntimeError("Unexpected mathlib4 archive layout.")
        if output_dir.exists():
            shutil.rmtree(output_dir)
        shutil.copytree(roots[0], output_dir)
    write_marker(output_dir, args.ref, commit)
    print(f"Downloaded mathlib4 source to {output_dir}")


if __name__ == "__main__":
    main()
