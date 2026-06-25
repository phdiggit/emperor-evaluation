from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files_byte_identical(left: Path, right: Path) -> bool:
    return left.read_bytes() == right.read_bytes()


def relative_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def file_fingerprints(
    paths: Sequence[Path],
    *,
    root: Path,
    extra: Callable[[Path, str], Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    fingerprints: list[dict[str, Any]] = []
    for path in paths:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        item: dict[str, Any] = {
            "path": relative_path(root, path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "line_count": len(text.splitlines()),
            "read_only": True,
        }
        if extra is not None:
            item.update(extra(path, text))
        fingerprints.append(item)
    return fingerprints


def stable_json_sha256(payload: Mapping[str, Any], *, omit_key: str | None = None) -> str:
    source = {key: value for key, value in payload.items() if key != omit_key} if omit_key else dict(payload)
    encoded = json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
