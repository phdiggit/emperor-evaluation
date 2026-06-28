from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
BATCHES_DIR = DATA_DIR / "batches"

SOURCE_PACKS_PATH = DATA_DIR / "source_packs.jsonl"
ANCHORS_PATH = DATA_DIR / "anchors.jsonl"
OBJECT_ANCHOR_COVERAGE_PATH = DATA_DIR / "object_anchor_coverage.jsonl"
QUERY_LANE_COVERAGE_PATH = DATA_DIR / "query_lane_coverage.jsonl"

SOURCES_PATH = DATA_DIR / "sources.jsonl"
SEARCH_LOGS_PATH = DATA_DIR / "search_logs.jsonl"
EVIDENCE_CARDS_PATH = DATA_DIR / "evidence_cards.jsonl"
EVIDENCE_CLUSTERS_PATH = DATA_DIR / "evidence_clusters.jsonl"
QUERY_PROFILES_PATH = DATA_DIR / "query_profiles.jsonl"

ALLOWED_ANCHOR_TYPES = {"theme", "object", "event", "mechanism"}
ALLOWED_LANE_GROUPS = {"positive", "negative", "adjacent"}
ALLOWED_COVERAGE_STATUSES = {
    "converted_to_card",
    "pending_review",
    "excluded_with_reason",
    "not_applicable_with_reason",
    "covered_by_canonical_refs",
}
ALLOWED_BATCH_LIFECYCLE_STATUSES = {
    "draft_batch",
    "active_review_batch",
    "absorbed_to_canonical",
    "superseded",
    "archive_only",
}
LEGACY_BATCH_STATUSES = {
    "active_batch",
    "review_only_batch",
    "merge_pending_batch",
    "merged_batch",
    "archive_candidate",
    "delete_candidate",
    "needs_human_confirmation",
}


def is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def read_jsonl(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        errors.append(f"{path}: file does not exist")
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                errors.append(f"{path}: line {line_number}: invalid JSON: {exc.msg}")
                continue
            if not isinstance(row, dict):
                errors.append(f"{path}: line {line_number}: JSONL row must be an object")
                continue
            rows.append(row)
    return rows


def build_id_map(rows: list[dict[str, Any]], id_field: str, path: Path, errors: list[str]) -> dict[str, dict[str, Any]]:
    id_map: dict[str, dict[str, Any]] = {}
    for line_number, row in enumerate(rows, start=1):
        identifier = row.get(id_field)
        label = f"{path}: line {line_number}"
        if is_blank(identifier) or not isinstance(identifier, str):
            errors.append(f"{label}: missing required id field: {id_field}")
            continue
        if identifier in id_map:
            errors.append(f"{path}: duplicate {id_field}: {identifier}")
            continue
        id_map[identifier] = row
    return id_map


def expect_refs(
    path: Path,
    row_id: str,
    field: str,
    values: Any,
    target_ids: set[str],
    errors: list[str],
) -> None:
    if values is None or values == "":
        return
    if isinstance(values, str):
        refs = [values]
    elif isinstance(values, list):
        refs = values
    else:
        errors.append(f"{path}: {row_id}: {field} must be a string or list")
        return

    for ref in refs:
        if not isinstance(ref, str) or not ref.strip():
            errors.append(f"{path}: {row_id}: {field} contains a blank or non-string ref")
        elif ref not in target_ids:
            errors.append(f"{path}: {row_id}: {field} references missing id: {ref}")


def validate_source_packs(
    rows: list[dict[str, Any]],
    source_pack_ids: set[str],
    source_ids: set[str],
    search_ids: set[str],
    evidence_ids: set[str],
    cluster_ids: set[str],
    errors: list[str],
) -> None:
    for row in rows:
        row_id = row.get("source_pack_id", "")
        expect_refs(SOURCE_PACKS_PATH, row_id, "source_id", row.get("source_id"), source_ids, errors)
        expect_refs(SOURCE_PACKS_PATH, row_id, "linked_search_ids", row.get("linked_search_ids", []), search_ids, errors)
        expect_refs(SOURCE_PACKS_PATH, row_id, "linked_evidence_ids", row.get("linked_evidence_ids", []), evidence_ids, errors)
        expect_refs(SOURCE_PACKS_PATH, row_id, "linked_cluster_ids", row.get("linked_cluster_ids", []), cluster_ids, errors)
        if row_id not in source_pack_ids:
            errors.append(f"{SOURCE_PACKS_PATH}: missing source_pack_id in source pack map: {row_id}")


def validate_anchors(
    rows: list[dict[str, Any]],
    evidence_ids: set[str],
    cluster_ids: set[str],
    errors: list[str],
) -> None:
    for row in rows:
        row_id = row.get("anchor_id", "")
        anchor_type = row.get("anchor_type")
        if anchor_type not in ALLOWED_ANCHOR_TYPES:
            errors.append(f"{ANCHORS_PATH}: {row_id}: anchor_type must be one of {sorted(ALLOWED_ANCHOR_TYPES)}")
        expect_refs(ANCHORS_PATH, row_id, "linked_evidence_ids", row.get("linked_evidence_ids", []), evidence_ids, errors)
        expect_refs(ANCHORS_PATH, row_id, "linked_cluster_ids", row.get("linked_cluster_ids", []), cluster_ids, errors)


def validate_anchor_coverage(
    rows: list[dict[str, Any]],
    coverage_ids: set[str],
    anchor_ids: set[str],
    source_pack_ids: set[str],
    source_ids: set[str],
    search_ids: set[str],
    evidence_ids: set[str],
    cluster_ids: set[str],
    errors: list[str],
) -> None:
    for row in rows:
        row_id = row.get("anchor_coverage_id", "")
        expect_refs(OBJECT_ANCHOR_COVERAGE_PATH, row_id, "anchor_ids", row.get("anchor_ids", []), anchor_ids, errors)
        expect_refs(
            OBJECT_ANCHOR_COVERAGE_PATH,
            row_id,
            "linked_source_pack_ids",
            row.get("linked_source_pack_ids", []),
            source_pack_ids,
            errors,
        )
        expect_refs(OBJECT_ANCHOR_COVERAGE_PATH, row_id, "linked_source_ids", row.get("linked_source_ids", []), source_ids, errors)
        expect_refs(OBJECT_ANCHOR_COVERAGE_PATH, row_id, "linked_search_id", row.get("linked_search_id"), search_ids, errors)
        expect_refs(
            OBJECT_ANCHOR_COVERAGE_PATH,
            row_id,
            "linked_evidence_ids",
            row.get("linked_evidence_ids", []),
            evidence_ids,
            errors,
        )
        expect_refs(
            OBJECT_ANCHOR_COVERAGE_PATH,
            row_id,
            "linked_cluster_ids",
            row.get("linked_cluster_ids", []),
            cluster_ids,
            errors,
        )
        if not row.get("anchor_ids") and is_blank(row.get("no_anchor_reason")):
            errors.append(f"{OBJECT_ANCHOR_COVERAGE_PATH}: {row_id}: anchor_ids is empty, so no_anchor_reason is required")
        if row_id not in coverage_ids:
            errors.append(f"{OBJECT_ANCHOR_COVERAGE_PATH}: missing anchor_coverage_id in coverage map: {row_id}")


def validate_lane_coverage(
    rows: list[dict[str, Any]],
    search_ids: set[str],
    evidence_ids: set[str],
    query_profile_ids: set[str],
    source_pack_ids: set[str],
    anchor_coverage_ids: set[str],
    errors: list[str],
) -> None:
    for row in rows:
        row_id = row.get("lane_coverage_id", "")
        if row.get("lane_group") not in ALLOWED_LANE_GROUPS:
            errors.append(f"{QUERY_LANE_COVERAGE_PATH}: {row_id}: lane_group must be one of {sorted(ALLOWED_LANE_GROUPS)}")
        if row.get("coverage_status") not in ALLOWED_COVERAGE_STATUSES:
            errors.append(
                f"{QUERY_LANE_COVERAGE_PATH}: {row_id}: coverage_status must be one of {sorted(ALLOWED_COVERAGE_STATUSES)}"
            )
        expect_refs(QUERY_LANE_COVERAGE_PATH, row_id, "query_profile_id", row.get("query_profile_id"), query_profile_ids, errors)
        expect_refs(QUERY_LANE_COVERAGE_PATH, row_id, "search_ids", row.get("search_ids", []), search_ids, errors)
        expect_refs(QUERY_LANE_COVERAGE_PATH, row_id, "source_pack_ids", row.get("source_pack_ids", []), source_pack_ids, errors)
        expect_refs(QUERY_LANE_COVERAGE_PATH, row_id, "linked_evidence_ids", row.get("linked_evidence_ids", []), evidence_ids, errors)
        expect_refs(
            QUERY_LANE_COVERAGE_PATH,
            row_id,
            "anchor_coverage_ids",
            row.get("anchor_coverage_ids", []),
            anchor_coverage_ids,
            errors,
        )


def validate_batch_lifecycle(errors: list[str]) -> None:
    if not BATCHES_DIR.exists():
        errors.append(f"{BATCHES_DIR}: directory does not exist")
        return
    for manifest_path in sorted(BATCHES_DIR.glob("*/manifest.yml")):
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        lifecycle_status = manifest.get("lifecycle_status")
        legacy_status = manifest.get("status")
        if lifecycle_status is not None:
            if lifecycle_status not in ALLOWED_BATCH_LIFECYCLE_STATUSES:
                errors.append(
                    f"{manifest_path}: lifecycle_status must be one of {sorted(ALLOWED_BATCH_LIFECYCLE_STATUSES)}"
                )
        elif legacy_status is not None:
            if legacy_status not in ALLOWED_BATCH_LIFECYCLE_STATUSES | LEGACY_BATCH_STATUSES:
                errors.append(f"{manifest_path}: status must be a known lifecycle or legacy batch status")
        else:
            errors.append(f"{manifest_path}: missing lifecycle_status or legacy status")


def validate() -> list[str]:
    errors: list[str] = []

    source_rows = read_jsonl(SOURCES_PATH, errors)
    search_rows = read_jsonl(SEARCH_LOGS_PATH, errors)
    evidence_rows = read_jsonl(EVIDENCE_CARDS_PATH, errors)
    cluster_rows = read_jsonl(EVIDENCE_CLUSTERS_PATH, errors)
    query_profile_rows = read_jsonl(QUERY_PROFILES_PATH, errors)

    source_pack_rows = read_jsonl(SOURCE_PACKS_PATH, errors)
    anchor_rows = read_jsonl(ANCHORS_PATH, errors)
    coverage_rows = read_jsonl(OBJECT_ANCHOR_COVERAGE_PATH, errors)
    lane_rows = read_jsonl(QUERY_LANE_COVERAGE_PATH, errors)

    source_ids = set(build_id_map(source_rows, "source_id", SOURCES_PATH, errors))
    search_ids = set(build_id_map(search_rows, "search_id", SEARCH_LOGS_PATH, errors))
    evidence_ids = set(build_id_map(evidence_rows, "evidence_id", EVIDENCE_CARDS_PATH, errors))
    cluster_ids = set(build_id_map(cluster_rows, "cluster_id", EVIDENCE_CLUSTERS_PATH, errors))
    query_profile_ids = set(build_id_map(query_profile_rows, "query_profile_id", QUERY_PROFILES_PATH, errors))

    source_pack_ids = set(build_id_map(source_pack_rows, "source_pack_id", SOURCE_PACKS_PATH, errors))
    anchor_ids = set(build_id_map(anchor_rows, "anchor_id", ANCHORS_PATH, errors))
    anchor_coverage_ids = set(build_id_map(coverage_rows, "anchor_coverage_id", OBJECT_ANCHOR_COVERAGE_PATH, errors))
    build_id_map(lane_rows, "lane_coverage_id", QUERY_LANE_COVERAGE_PATH, errors)

    validate_source_packs(source_pack_rows, source_pack_ids, source_ids, search_ids, evidence_ids, cluster_ids, errors)
    validate_anchors(anchor_rows, evidence_ids, cluster_ids, errors)
    validate_anchor_coverage(
        coverage_rows,
        anchor_coverage_ids,
        anchor_ids,
        source_pack_ids,
        source_ids,
        search_ids,
        evidence_ids,
        cluster_ids,
        errors,
    )
    validate_lane_coverage(lane_rows, search_ids, evidence_ids, query_profile_ids, source_pack_ids, anchor_coverage_ids, errors)
    validate_batch_lifecycle(errors)

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Source/evidence canonical store validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Source/evidence canonical store validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
