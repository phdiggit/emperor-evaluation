from __future__ import annotations

import re
from typing import Any, Mapping

from scripts.dev.retrieval_v2_contracts import (
    source_hints_for_metadata,
    source_root_aliases_for_hint,
)


BLOCKED_TITLE_FRAGMENTS = ("四部叢刊本", "四部丛刊本", "演義", "演义", "志傳", "志传")


def compact_source_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip()


def unique_strings(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def source_title_root(title: str) -> str:
    return re.sub(r"[（(].*?[）)]", "", compact_source_text(title).split("/", 1)[0])


def task_metadata(task: Mapping[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("target_payload", "target_profile"):
        value = task.get(key)
        if isinstance(value, Mapping):
            metadata.update({str(k): v for k, v in value.items()})
    for key in ("emperor_name", "name", "period", "title", "temple_name", "posthumous_name"):
        if task.get(key):
            metadata.setdefault(key, task.get(key))
    return metadata


def task_source_hints(task: Mapping[str, Any]) -> list[str]:
    strategy = task.get("source_strategy") if isinstance(task.get("source_strategy"), Mapping) else {}
    hints = list(strategy.get("source_hints") or [])
    metadata = task_metadata(task)
    has_period_context = any(metadata.get(key) for key in ("period", "title", "temple_name", "posthumous_name"))
    if hints and not has_period_context and unique_strings(hints) == ["資治通鑑"]:
        return []
    if not hints and has_period_context:
        hints.extend(source_hints_for_metadata(metadata))
    return unique_strings(hints)


def allowed_source_roots_for_task(task: Mapping[str, Any]) -> list[str]:
    metadata = task_metadata(task)
    roots: list[Any] = []
    for hint in task_source_hints(task):
        roots.extend(source_root_aliases_for_hint(str(hint), metadata))
    return unique_strings(roots)


def source_document_skip(
    task: Mapping[str, Any],
    document: Mapping[str, Any],
) -> dict[str, Any] | None:
    title = compact_source_text(str(document.get("wikisource_title") or document.get("title") or ""))
    if not title or not (document.get("wikisource_title") or document.get("title")):
        return None
    if "/" not in title:
        return {
            "reason": "root_page_discovery_scaffold",
            "title": title,
        }
    if any(fragment in title for fragment in BLOCKED_TITLE_FRAGMENTS):
        return {
            "reason": "blocked_source_title_variant",
            "title": title,
        }
    allowed_roots = allowed_source_roots_for_task(task)
    if not allowed_roots:
        return None
    root = source_title_root(title)
    if root and root not in allowed_roots:
        return {
            "reason": "source_root_mismatch",
            "title": title,
            "source_root": root,
            "allowed_source_roots": allowed_roots,
        }
    return None
