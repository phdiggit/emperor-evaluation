from __future__ import annotations

import hashlib
import posixpath
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from . import constants as c
from .paths import (
    _decode_text,
    _git_blob,
    _is_text_path,
    _normalized_text,
    git_lines,
    git_output_text,
    normalize_repo_path,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _title(text: str | None) -> str | None:
    if not text:
        return None
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or None
    return None


def _date_suffix(path: str) -> str | None:
    match = c.DATE_SUFFIX_RE.search(Path(path).stem)
    return match.group(1) if match else None


def _tracked_docs(ref: str) -> list[str]:
    paths = git_lines("ls-tree", "-r", "--name-only", ref, "--", "docs", c.ARCHIVE_DOCS_ROOT)
    return sorted(path for path in paths if path.startswith(("docs/", c.ARCHIVE_DOCS_ROOT)))


def _tracked_reference_files(ref: str) -> list[str]:
    candidates: list[str] = []
    for path in git_lines("ls-tree", "-r", "--name-only", ref):
        if path.startswith((".tmp/", "exports/", "data/configs/")):
            continue
        if path in {"README.md", "AGENTS.md"}:
            candidates.append(path)
        elif path.startswith(("docs/", "scripts/", "tests/", ".github/")):
            candidates.append(path)
        elif "/" not in path and _is_text_path(path):
            candidates.append(path)
    return sorted(dict.fromkeys(candidates))


def _read_ref_text(ref: str, path: str) -> str | None:
    if not _is_text_path(path):
        return None
    return _decode_text(_git_blob(ref, path))


def _markdown_link_targets(text: str) -> list[str]:
    targets: list[str] = []
    for raw in c.MARKDOWN_LINK_RE.findall(text):
        target = raw.split("#", 1)[0].strip()
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        targets.append(normalize_repo_path(target))
    return targets


def _candidate_reference_paths(source_path: str, text: str) -> set[str]:
    refs: set[str] = set()
    source_dir = Path(source_path).parent.as_posix()
    for target in _markdown_link_targets(text):
        normalized_target = normalize_repo_path(posixpath.normpath(target))
        if target.startswith("docs/"):
            refs.add(normalized_target)
        elif target.endswith(".md") or target.startswith("../"):
            refs.add(normalize_repo_path(posixpath.normpath(posixpath.join(source_dir, target))))
    refs.update(match.rstrip(".,;:，。；：") for match in c.DOCS_LITERAL_RE.findall(text))
    return refs


def _build_reference_maps(
    ref: str, docs_paths: list[str]
) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, list[str]], dict[str, list[str]], dict[str, list[str]]]:
    docs_set = set(docs_paths)
    inbound: dict[str, set[str]] = {path: set() for path in docs_paths}
    governance: dict[str, set[str]] = {path: set() for path in docs_paths}
    weak: dict[str, set[str]] = {path: set() for path in docs_paths}
    tests: dict[str, set[str]] = {path: set() for path in docs_paths}
    generators: dict[str, set[str]] = {path: set() for path in docs_paths}
    basenames: dict[str, list[str]] = defaultdict(list)
    for doc_path in docs_paths:
        basenames[Path(doc_path).name].append(doc_path)

    for source_path in _tracked_reference_files(ref):
        text = _read_ref_text(ref, source_path)
        if text is None:
            continue
        target_map = governance if source_path in c.GOVERNANCE_REFERENCE_SOURCES else inbound
        explicit_refs = _candidate_reference_paths(source_path, text)
        for target_ref in explicit_refs:
            normalized = normalize_repo_path(target_ref)
            if normalized in docs_set and normalized != source_path:
                target_map[normalized].add(source_path)
                if source_path in c.GOVERNANCE_REFERENCE_SOURCES:
                    continue
                if source_path.startswith("tests/"):
                    tests[normalized].add(source_path)
                if source_path.startswith(("scripts/", "tests/")) and any(marker in text for marker in c.WRITE_MARKERS):
                    generators[normalized].add(source_path)
        for name, matching_docs in basenames.items():
            if name in text:
                for doc_path in matching_docs:
                    if doc_path != source_path and source_path not in inbound[doc_path]:
                        weak[doc_path].add(source_path)
        if source_path.startswith(("scripts/", "tests/")) and any(marker in text for marker in c.WRITE_MARKERS):
            for doc_path in docs_paths:
                if doc_path in text or Path(doc_path).name in text:
                    generators[doc_path].add(source_path)

    return (
        {path: sorted(values) for path, values in inbound.items()},
        {path: sorted(values) for path, values in governance.items()},
        {path: sorted(values) for path, values in weak.items()},
        {path: sorted(values) for path, values in tests.items()},
        {path: sorted(values) for path, values in generators.items()},
    )


def _group_values(values: dict[str, str | None], prefix: str) -> dict[str, str | None]:
    reverse: dict[str, list[str]] = defaultdict(list)
    for path, value in values.items():
        if value:
            reverse[value].append(path)
    groups: dict[str, str | None] = {path: None for path in values}
    index = 1
    for _, paths in sorted(reverse.items(), key=lambda item: sorted(item[1])):
        if len(paths) < 2:
            continue
        group_id = f"{prefix}{index:03d}"
        index += 1
        for path in paths:
            groups[path] = group_id
    return groups


def build_inventory(ref: str = "origin/GPT") -> dict[str, Any]:
    docs_paths = _tracked_docs(ref)
    inbound, governance, weak, referenced_by_tests, generator_candidates = _build_reference_maps(ref, docs_paths)
    items: list[dict[str, Any]] = []
    exact_values: dict[str, str | None] = {}
    normalized_values: dict[str, str | None] = {}
    title_values: dict[str, str | None] = {}
    extension_counts: Counter[str] = Counter()
    directory_counts: Counter[str] = Counter()
    generated_count = 0
    markdown_count = 0
    date_suffix_count = 0

    for path in docs_paths:
        data = _git_blob(ref, path)
        suffix = Path(path).suffix.lower()
        extension_counts[suffix or "<none>"] += 1
        parts = Path(path).parts
        directory_counts["/".join(parts[:2]) if len(parts) > 1 else "docs"] += 1
        markdown_count += int(suffix == ".md")
        date_suffix = _date_suffix(path)
        date_suffix_count += int(bool(date_suffix))
        text = _decode_text(data) if _is_text_path(path) else None
        normalized_hash = _sha256(_normalized_text(text).encode("utf-8")) if text is not None else None
        title = _title(text)
        generated_marker = bool(text and any(marker in text for marker in c.AUTO_GENERATED_MARKERS))
        generated_count += int(generated_marker or bool(generator_candidates[path]))
        exact_values[path] = _sha256(data)
        normalized_values[path] = normalized_hash
        title_values[path] = title
        items.append(
            {
                "date_suffix": date_suffix,
                "exact_duplicate_group": None,
                "generator_candidates": generator_candidates[path],
                "generated_marker": generated_marker,
                "governance_references": governance[path],
                "inbound_references": inbound[path],
                "is_text": text is not None,
                "line_count": len(text.splitlines()) if text is not None else None,
                "normalized_duplicate_group": None,
                "normalized_text_sha256": normalized_hash,
                "path": path,
                "referenced_by_tests": referenced_by_tests[path],
                "same_title_group": None,
                "sha256": _sha256(data),
                "size_bytes": len(data),
                "suffix": suffix,
                "title": title,
                "weak_reference_candidates": weak[path],
            }
        )

    exact_groups = _group_values(exact_values, "exact-")
    normalized_groups = _group_values(normalized_values, "norm-")
    title_groups = _group_values(title_values, "title-")
    for item in items:
        item["exact_duplicate_group"] = exact_groups[item["path"]]
        item["normalized_duplicate_group"] = normalized_groups[item["path"]]
        item["same_title_group"] = title_groups[item["path"]]

    return {
        "documents": sorted(items, key=lambda item: item["path"]),
        "ref": ref,
        "ref_sha": git_output_text("rev-parse", ref).strip(),
        "schema_version": 1,
        "stats": {
            "date_suffix_files": date_suffix_count,
            "extension_counts": dict(sorted(extension_counts.items())),
            "first_level_counts": dict(sorted(directory_counts.items())),
            "generated_candidate_files": generated_count,
            "markdown_files": markdown_count,
            "referenced_files": sum(1 for item in items if item["inbound_references"]),
            "total_files": len(items),
            "unreferenced_files": sum(1 for item in items if not item["inbound_references"]),
        },
    }
