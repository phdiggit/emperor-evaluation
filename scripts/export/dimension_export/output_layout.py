from __future__ import annotations

from pathlib import Path


def ensure_directories(paths: list[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def write_markdown_outputs(outputs: dict[Path, str]) -> None:
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def remove_existing_paths(paths: list[Path]) -> None:
    for path in paths:
        if path.exists():
            path.unlink()
