"""Helpers for loading extracted competition JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json_file(path: str | Path) -> dict[str, Any]:
    """Load one JSON file and return its parsed content."""
    file_path = Path(path)

    with file_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {file_path}, got {type(data).__name__}.")

    return data


def load_json_files_from_dir(directory: str | Path) -> list[dict[str, Any]]:
    """Load all JSON files from a directory recursively."""
    directory_path = Path(directory)
    records: list[dict[str, Any]] = []

    for file_path in sorted(directory_path.rglob("*.json")):
        records.append(load_json_file(file_path))

    return records
