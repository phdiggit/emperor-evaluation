from __future__ import annotations

from pathlib import Path
from typing import Any

from emperor_v4.evaluation.episode_pilot import (
    _load_json,
    _load_yaml,
    _required_identity,
    _source_identity,
)


def check_source_gap_request(
    manifest_path: Path,
    source_fixture_path: Path,
    request_path: Path,
) -> dict[str, Any]:
    manifest = _load_yaml(manifest_path)
    source_snapshot = _load_json(source_fixture_path)
    request = _load_yaml(request_path)

    actual_by_ruler = {
        person.get("ruler"): {
            _source_identity(document.get("title") or "")
            for document in person.get("payload", {}).get("source_documents", [])
        }
        for person in source_snapshot.get("people", [])
    }
    frozen_codes = set(manifest.get("frozen_episode_codes") or ())
    missing_rows: set[tuple[str, str, str, str]] = set()
    for episode in manifest.get("episodes", []):
        episode_code = episode.get("episode_code")
        if episode_code not in frozen_codes:
            continue
        ruler = episode.get("ruler")
        for passage in episode.get("required_source_passages", []):
            identity = _required_identity(passage)
            if identity not in actual_by_ruler.get(ruler, set()):
                missing_rows.add(
                    (episode_code, ruler, identity, passage.get("locator") or "")
                )

    request_rows: set[tuple[str, str, str, str]] = set()
    for item in request.get("requests", []):
        identity = _source_identity(item.get("edition_identity") or "")
        if identity.startswith("Wikisource/"):
            identity = identity.removeprefix("Wikisource/")
        for locator in item.get("locator_requests", []):
            request_rows.add(
                (
                    locator.get("episode_code") or "",
                    item.get("ruler") or "",
                    identity,
                    locator.get("locator") or "",
                )
            )

    missing_from_request = sorted(missing_rows - request_rows)
    extra_in_request = sorted(request_rows - missing_rows)
    errors: list[str] = []
    if request.get("execution_authorized") is not False:
        errors.append("execution_authorized 必须为 false")
    if request.get("production_write_authorized") is not False:
        errors.append("production_write_authorized 必须为 false")
    if missing_from_request:
        errors.append("source gap request 未覆盖全部缺口")
    if extra_in_request:
        errors.append("source gap request 包含非缺口条目")

    return {
        "report_schema_version": 1,
        "check": "source_gap_request",
        "status": "passed" if not errors else "failed",
        "missing_required_passage_count": len(missing_rows),
        "requested_locator_count": len(request_rows),
        "requested_document_count": len(request.get("requests", [])),
        "missing_from_request": missing_from_request,
        "extra_in_request": extra_in_request,
        "execution_authorized": request.get("execution_authorized"),
        "production_write_authorized": request.get("production_write_authorized"),
        "errors": errors,
    }
