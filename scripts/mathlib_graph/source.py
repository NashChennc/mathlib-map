"""Static Mathlib source parser for full module import graphs."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Iterable

import pandas as pd

from .io import filename_to_module
from .topics import topic_from_module

IMPORT_RE = re.compile(r"^\s*(?:(?:public|private|protected|meta)\s+)*import\s+(.+?)\s*$")
DOC_BLOCK_RE = re.compile(r"/-!(.*?)-/", re.DOTALL)
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
MARKDOWN_REF_RE = re.compile(r"\[([^\]]+)\]\[[^\]]+\]")
HTML_TAG_RE = re.compile(r"<[^>]+>")
MAX_DESCRIPTION_CHARS = 520


def _strip_non_code_text(text: str) -> str:
    result: list[str] = []
    depth = 0
    i = 0
    in_line_comment = False
    in_string = False
    escaped = False
    while i < len(text):
        pair = text[i : i + 2]
        if in_line_comment:
            if text[i] == "\n":
                in_line_comment = False
                result.append("\n")
            else:
                result.append(" ")
            i += 1
            continue
        if in_string:
            if text[i] == "\n":
                result.append("\n")
            else:
                result.append(" ")
            if escaped:
                escaped = False
            elif text[i] == "\\":
                escaped = True
            elif text[i] == '"':
                in_string = False
            i += 1
            continue
        if depth == 0 and pair == "--":
            in_line_comment = True
            result.append("  ")
            i += 2
            continue
        if depth == 0 and pair == "/-" and (i + 2 >= len(text) or text[i + 2] != "/"):
            depth = 1
            result.append("  ")
            i += 2
            continue
        if depth > 0 and pair == "-/":
            depth -= 1
            result.append("  ")
            i += 2
            continue
        if depth > 0 and pair == "/-" and (i + 2 >= len(text) or text[i + 2] != "/"):
            depth += 1
            result.append("  ")
            i += 2
            continue
        if depth > 0 and text[i] == "\n":
            result.append("\n")
        elif depth > 0:
            result.append(" ")
        elif text[i] == '"':
            in_string = True
            result.append(" ")
        else:
            result.append(text[i])
        i += 1
    return "".join(result)


def module_from_source_path(path: Path, source_root: Path) -> str | None:
    try:
        relative = path.relative_to(source_root)
    except ValueError:
        relative = path
    return filename_to_module(str(relative))


def parse_imports(text: str) -> list[str]:
    imports: list[str] = []
    seen: set[str] = set()
    clean = _strip_non_code_text(text)
    for line in clean.splitlines():
        match = IMPORT_RE.match(line)
        if not match:
            continue
        for item in match.group(1).split():
            item = item.strip()
            if not item or item.startswith("--"):
                break
            if item == "all":
                continue
            if not item.startswith("Mathlib."):
                continue
            if item not in seen:
                seen.add(item)
                imports.append(item)
    return imports


def _clean_doc_text(text: str) -> str:
    text = MARKDOWN_LINK_RE.sub(r"\1", text)
    text = MARKDOWN_REF_RE.sub(r"\1", text)
    text = HTML_TAG_RE.sub("", text)
    text = text.replace("`", "")
    text = text.replace("*", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -")


def _clip_description(text: str) -> str:
    if len(text) <= MAX_DESCRIPTION_CHARS:
        return text
    sentence_break = text.rfind(". ", 0, MAX_DESCRIPTION_CHARS)
    if sentence_break > 180:
        return text[: sentence_break + 1]
    return text[: MAX_DESCRIPTION_CHARS - 3].rstrip() + "..."


def _fallback_doc(module: str, topic: str) -> tuple[str, str, bool]:
    return module.removeprefix("Mathlib."), f"Full Mathlib source module in {topic}.", False


def extract_module_doc(text: str, module: str, topic: str) -> tuple[str, str, bool]:
    """Return title, first prose paragraph, and whether a module doc was found."""

    match = DOC_BLOCK_RE.search(text)
    if not match:
        return _fallback_doc(module, topic)

    raw_lines = [line.strip() for line in match.group(1).replace("\r\n", "\n").splitlines()]
    lines = [line for line in raw_lines if line]
    if not lines:
        return _fallback_doc(module, topic)

    title = ""
    title_index = -1
    for idx, line in enumerate(lines):
        if line.startswith("#"):
            title = _clean_doc_text(line.lstrip("#").strip())
            title_index = idx
            break
    if not title:
        title = _clean_doc_text(lines[0])

    paragraphs: list[str] = []
    current: list[str] = []
    in_code_block = False
    for line in raw_lines[title_index + 1 if title_index >= 0 else 1 :]:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if not stripped:
            if current:
                paragraphs.append(_clean_doc_text(" ".join(current)))
                current = []
            continue
        if stripped.startswith("#"):
            if current:
                paragraphs.append(_clean_doc_text(" ".join(current)))
                current = []
            continue
        if stripped.startswith(("- ", "* ", "+ ")):
            continue
        if stripped.lower().startswith(("tags:", "references:", "reference:", "authors:")):
            continue
        current.append(stripped)
    if current:
        paragraphs.append(_clean_doc_text(" ".join(current)))

    description = next((paragraph for paragraph in paragraphs if len(paragraph) >= 24), "")
    if not description:
        description = f"Module documentation is present for {module.removeprefix('Mathlib.')}."
    return title or module.removeprefix("Mathlib."), _clip_description(description), True


def iter_mathlib_files(source_root: Path) -> Iterable[Path]:
    mathlib_dir = source_root / "Mathlib"
    if not mathlib_dir.is_dir():
        raise FileNotFoundError(f"Missing Mathlib directory in {source_root}")
    yield from sorted(mathlib_dir.rglob("*.lean"))


def source_metadata(source_root: Path) -> dict[str, str]:
    metadata = {
        "mathlib_source_dir": str(source_root),
        "mathlib_source_commit": "",
        "mathlib_source_ref": "",
    }
    git_dir = source_root / ".git"
    if git_dir.exists():
        try:
            metadata["mathlib_source_commit"] = subprocess.check_output(
                ["git", "-C", str(source_root), "rev-parse", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            metadata["mathlib_source_ref"] = subprocess.check_output(
                ["git", "-C", str(source_root), "rev-parse", "--abbrev-ref", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    marker = source_root / ".mathlib_source_ref"
    if marker.exists():
        for line in marker.read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key in metadata and key != "mathlib_source_dir":
                metadata[key] = value
    return metadata


def load_mathlib_source_records(source_root: Path) -> pd.DataFrame:
    source_root = source_root.resolve()
    rows = []
    for path in iter_mathlib_files(source_root):
        module = module_from_source_path(path, source_root)
        if not module or module == "Mathlib":
            continue
        relative = path.relative_to(source_root)
        text = path.read_text(encoding="utf-8")
        topic = topic_from_module(module)
        description_title, description, has_description = extract_module_doc(text, module, topic)
        rows.append(
            {
                "fact": module,
                "type": "module",
                "library": topic,
                "imports": parse_imports(text),
                "filename": str(relative),
                "symbolic_name": module,
                "docstring": description,
                "description_title": description_title,
                "description": description,
                "has_description": has_description,
            }
        )
    records = pd.DataFrame(rows)
    records.attrs.update(source_metadata(source_root))
    records.attrs["mathlib_source_file_count"] = len(records)
    return records
