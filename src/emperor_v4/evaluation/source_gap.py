from __future__ import annotations

import hashlib
import json
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
    related_window_rows: set[tuple[str, str, str, str]] = set()
    for item in request.get("requests", []):
        identity = _source_identity(item.get("edition_identity") or "")
        if identity.startswith("Wikisource/"):
            identity = identity.removeprefix("Wikisource/")
        for locator in item.get("locator_requests", []):
            row = (
                locator.get("episode_code") or "",
                item.get("ruler") or "",
                identity,
                locator.get("locator") or "",
            )
            if locator.get("related_window") is True:
                related_window_rows.add(row)
            else:
                request_rows.add(row)

    missing_from_request = sorted(missing_rows - request_rows)
    extra_in_request = sorted(request_rows - missing_rows)
    errors: list[str] = []
    if request.get("execution_authorized") not in {False, True}:
        errors.append("execution_authorized 必须是显式布尔值")
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
        "related_window_count": len(related_window_rows),
        "requested_document_count": len(request.get("requests", [])),
        "missing_from_request": missing_from_request,
        "extra_in_request": extra_in_request,
        "execution_authorized": request.get("execution_authorized"),
        "production_write_authorized": request.get("production_write_authorized"),
        "errors": errors,
    }


def _all_strings(value: Any):
    if isinstance(value, dict):
        for item in value.values():
            yield from _all_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _all_strings(item)
    elif isinstance(value, str):
        yield value


def check_source_supplement_response(
    request_path: Path,
    response_path: Path,
    execution_path: Path | None = None,
) -> dict[str, Any]:
    request = _load_yaml(request_path)
    response_bytes = response_path.read_bytes()
    response = json.loads(response_bytes.decode("utf-8"))
    errors: list[str] = []

    expected_documents = {
        item.get("edition_identity") for item in request.get("requests", [])
    }
    actual_documents = {
        item.get("edition_identity") for item in response.get("documents", [])
    }
    if expected_documents != actual_documents:
        errors.append("response document set 与 request 不一致")

    expected_passages = {
        (
            locator.get("episode_code"),
            locator.get("locator"),
            locator.get("related_window") is True,
        )
        for item in request.get("requests", [])
        for locator in item.get("locator_requests", [])
    }
    actual_passages = {
        (
            item.get("episode_code"),
            str(item.get("locator") or "").split(" | chars:", 1)[0],
            item.get("related_window") is True,
        )
        for item in response.get("passages", [])
    }
    if expected_passages != actual_passages:
        errors.append("response passage set 与 request 不一致")

    document_ids = [item.get("document_cache_id") for item in response.get("documents", [])]
    passage_ids = [item.get("passage_cache_id") for item in response.get("passages", [])]
    if len(document_ids) != len(set(document_ids)):
        errors.append("response 包含重复 document_cache_id")
    if len(passage_ids) != len(set(passage_ids)):
        errors.append("response 包含重复 passage_cache_id")
    if any(
        item.get("document_cache_id") not in set(document_ids)
        for item in response.get("passages", [])
    ):
        errors.append("response passage 引用了未知 document")

    for item in response.get("documents", []):
        if len(str(item.get("content_hash") or "")) != 64:
            errors.append(f"document content_hash 非 SHA-256: {item.get('document_cache_id')}")
    for item in response.get("passages", []):
        expected_hash = hashlib.sha256(item.get("raw_text", "").encode("utf-8")).hexdigest()
        if item.get("content_hash") != expected_hash:
            errors.append(f"passage content_hash 不一致: {item.get('passage_cache_id')}")
        reason = item.get("selection_reason") or {}
        if set(reason.get("requested_anchor_terms") or ()) != set(
            reason.get("matched_anchor_terms") or ()
        ):
            errors.append(f"passage anchor 未完全命中: {item.get('passage_cache_id')}")

    if response.get("status") != "succeeded" or response.get("errors"):
        errors.append("response 未无错误完成")
    if response.get("production_write_performed") is not False:
        errors.append("response 发生了生产写入")
    if response.get("model_call_count") != 0:
        errors.append("response 发生了模型调用")
    if response.get("network_fetch_count") != 0:
        errors.append("最终 fixture 不是零网络幂等重跑")
    if response.get("cache_hit_count") != len(expected_documents):
        errors.append("最终 fixture 未全部命中缓存")

    request_hash = hashlib.sha256(request_path.read_bytes()).hexdigest()
    if response.get("provenance", {}).get("request_sha256") != request_hash:
        errors.append("response request_sha256 与当前 request 不一致")
    response_hash = hashlib.sha256(response_bytes).hexdigest()

    if execution_path is not None:
        execution = _load_yaml(execution_path)
        final_run = (execution.get("runs") or [])[-1]
        if final_run.get("request_sha256") != request_hash:
            errors.append("execution final request_sha256 不一致")
        if final_run.get("response_sha256") != response_hash:
            errors.append("execution final response_sha256 不一致")

    forbidden_values = [
        value
        for value in _all_strings(response)
        if value.startswith(("/data1/", "/home/")) or "192.168." in value
    ]
    if forbidden_values:
        errors.append("response 包含运行环境绝对路径或内网地址")

    return {
        "report_schema_version": 1,
        "check": "source_supplement_response",
        "status": "passed" if not errors else "failed",
        "request_sha256": request_hash,
        "response_sha256": response_hash,
        "document_count": len(document_ids),
        "passage_count": len(passage_ids),
        "related_window_count": sum(
            item.get("related_window") is True for item in response.get("passages", [])
        ),
        "all_anchor_terms_matched": not any("anchor" in error for error in errors),
        "cache_hit_count": response.get("cache_hit_count"),
        "network_fetch_count": response.get("network_fetch_count"),
        "model_call_count": response.get("model_call_count"),
        "production_write_performed": response.get("production_write_performed"),
        "errors": errors,
    }


def check_source_segmentation_repair_response(
    request_path: Path,
    execution_path: Path,
    response_path: Path,
) -> dict[str, Any]:
    request = _load_yaml(request_path)
    execution = _load_yaml(execution_path)
    response_bytes = response_path.read_bytes()
    response = json.loads(response_bytes.decode("utf-8"))
    errors: list[str] = []

    expected_codes = {item["repair_code"] for item in request.get("windows", [])}
    actual_codes = {item.get("repair_code") for item in response.get("passages", [])}
    if expected_codes != actual_codes:
        errors.append("segmentation repair passage set 与 request 不一致")
    for item in response.get("passages", []):
        expected_hash = hashlib.sha256(item.get("raw_text", "").encode("utf-8")).hexdigest()
        if item.get("content_hash") != expected_hash:
            errors.append(f"repair passage content_hash 不一致: {item.get('repair_code')}")
        matched = set(item.get("selection_reason", {}).get("matched_anchor_terms") or ())
        requested = next(
            set(row.get("required_anchor_terms") or ())
            for row in request["windows"]
            if row["repair_code"] == item.get("repair_code")
        )
        if matched != requested:
            errors.append(f"repair passage anchor 不完整: {item.get('repair_code')}")
        if not item.get("supersedes_passage_ref") and not item.get(
            "fills_missing_boundary"
        ):
            errors.append(
                f"repair passage 缺少 supersedes 或 gap lineage: {item.get('repair_code')}"
            )

    if response.get("status") != "succeeded" or response.get("errors"):
        errors.append("segmentation repair 未无错误完成")
    if response.get("network_fetch_count") != 0:
        errors.append("segmentation repair 访问了网络")
    if response.get("model_call_count") != 0:
        errors.append("segmentation repair 调用了模型")
    if response.get("production_write_performed") is not False:
        errors.append("segmentation repair 发生生产写入")

    request_hash = hashlib.sha256(request_path.read_bytes()).hexdigest()
    response_hash = hashlib.sha256(response_bytes).hexdigest()
    if response.get("provenance", {}).get("request_sha256") != request_hash:
        errors.append("segmentation repair request hash 不一致")
    if execution.get("request_sha256") != request_hash:
        errors.append("segmentation execution request hash 不一致")
    if execution.get("response_sha256") != response_hash:
        errors.append("segmentation execution response hash 不一致")

    return {
        "report_schema_version": 1,
        "check": "source_segmentation_repair_response",
        "status": "passed" if not errors else "failed",
        "request_sha256": request_hash,
        "response_sha256": response_hash,
        "passage_count": len(actual_codes),
        "superseded_passage_count": len(
            {
                item.get("supersedes_passage_ref")
                for item in response.get("passages", [])
                if item.get("supersedes_passage_ref")
            }
        ),
        "filled_missing_boundary_count": sum(
            item.get("fills_missing_boundary") is True
            for item in response.get("passages", [])
        ),
        "network_fetch_count": response.get("network_fetch_count"),
        "model_call_count": response.get("model_call_count"),
        "errors": errors,
    }
