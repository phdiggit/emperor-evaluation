from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

QUERY_PROFILES_PATH = DATA_DIR / "query_profiles.jsonl"
SEARCH_LOGS_PATH = DATA_DIR / "search_logs.jsonl"
THEMATIC_ANCHORS_PATH = DATA_DIR / "thematic_anchors.jsonl"
THEMATIC_OBJECTS_PATH = DATA_DIR / "thematic_anchor_objects.jsonl"
THEMATIC_MECHANISMS_PATH = DATA_DIR / "thematic_anchor_mechanisms.jsonl"
THEMATIC_EVENTS_PATH = DATA_DIR / "thematic_anchor_events.jsonl"

CANONICAL_FILES = [
    QUERY_PROFILES_PATH,
    SEARCH_LOGS_PATH,
    THEMATIC_ANCHORS_PATH,
    THEMATIC_OBJECTS_PATH,
    THEMATIC_MECHANISMS_PATH,
    THEMATIC_EVENTS_PATH,
]

QUERY_PROFILE_BATCH_PATH = DATA_DIR / "query_profile_batches" / "i5b_three_pilot_profiles_migration_20260618.jsonl"
SEARCH_LOG_BATCH_PATH = DATA_DIR / "search_log_batches" / "i5b_next_four_20260618.jsonl"
THEMATIC_BATCH_PATH = DATA_DIR / "thematic_anchor_batches" / "i5b_three_pilot_object_anchors_20260618.jsonl"

LANE_FILES = [
    THEMATIC_OBJECTS_PATH,
    THEMATIC_MECHANISMS_PATH,
    THEMATIC_EVENTS_PATH,
]

CHUWANGYING_EVENT_ANCHOR_ID = "ANCH-I5B-EVENT-CHUWANGYING-CASE-EXPANSION-20260618"
SHENTUGANG_MECHANISM_ANCHOR_ID = "ANCH-I5B-MECHANISM-SHENTUGANG-EXPRESSION-SAFETY-20260618"


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
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:
                errors.append(f"{path}: line {line_number}: invalid JSON: {exc.msg}")
                continue
            if not isinstance(value, dict):
                errors.append(f"{path}: line {line_number}: JSONL row must be an object")
                continue
            rows.append(value)
    return rows


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def build_row_map(rows: list[dict[str, Any]], key: str, path: Path, errors: list[str]) -> dict[str, dict[str, Any]]:
    row_map: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    for line_number, row in enumerate(rows, start=1):
        identifier = row.get(key)
        line_label = f"{path}: line {line_number}"
        if is_blank(identifier):
            errors.append(f"{line_label}: missing required id field: {key}")
            continue
        if not isinstance(identifier, str):
            errors.append(f"{line_label}: {key} must be a non-empty string")
            continue
        if identifier in seen:
            errors.append(f"{path}: duplicate {key}: {identifier}")
            continue
        seen.add(identifier)
        row_map[identifier] = row
    return row_map


def validate_source_batch_presence(
    batch_rows: list[dict[str, Any]],
    batch_id_key: str,
    batch_path: Path,
    canonical_map: dict[str, dict[str, Any]],
    source_batch_field_value: str,
    errors: list[str],
) -> None:
    for line_number, batch_row in enumerate(batch_rows, start=1):
        identifier = batch_row.get(batch_id_key)
        if is_blank(identifier) or not isinstance(identifier, str):
            errors.append(f"{batch_path}: line {line_number}: missing required id field: {batch_id_key}")
            continue
        canonical_row = canonical_map.get(identifier)
        if canonical_row is None:
            errors.append(f"{batch_path}: {batch_id_key} not found in canonical data: {identifier}")
            continue
        if canonical_row.get("source_batch") != source_batch_field_value:
            errors.append(
                f"{batch_path}: canonical row {identifier} must retain source_batch={source_batch_field_value}"
            )


def validate_search_log_source_fields(
    batch_rows: list[dict[str, Any]],
    canonical_map: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    for batch_row in batch_rows:
        search_id = batch_row.get("search_id")
        if not isinstance(search_id, str) or not search_id.strip():
            continue
        canonical_row = canonical_map.get(search_id)
        if canonical_row is None:
            continue

        if "source_status" in canonical_row and is_blank(canonical_row.get("source_status")):
            errors.append(f"{SEARCH_LOGS_PATH}: search_id {search_id} has blank source_status")
        if "source_polarity" in canonical_row and is_blank(canonical_row.get("source_polarity")):
            errors.append(f"{SEARCH_LOGS_PATH}: search_id {search_id} has blank source_polarity")
        if canonical_row.get("source_polarity") == "neutral" and canonical_row.get("polarity") != "negative":
            errors.append(
                f"{SEARCH_LOGS_PATH}: search_id {search_id} must keep canonical polarity=negative when source_polarity=neutral"
            )


def validate_cross_lane_uniqueness(
    lane_maps: dict[Path, dict[str, dict[str, Any]]],
    errors: list[str],
) -> None:
    anchor_locations: dict[str, list[str]] = {}
    for path, row_map in lane_maps.items():
        for anchor_id in row_map:
            anchor_locations.setdefault(anchor_id, []).append(path.name)

    for anchor_id, file_names in sorted(anchor_locations.items()):
        if len(file_names) > 1:
            errors.append(
                f"thematic anchor lane files: duplicate anchor_id across lanes: {anchor_id} -> {', '.join(file_names)}"
            )


def validate_special_lane_row(
    row_map: dict[str, dict[str, Any]],
    expected_path: Path,
    anchor_id: str,
    expected_kind: str,
    errors: list[str],
) -> None:
    row = row_map.get(anchor_id)
    if row is None:
        errors.append(f"{expected_path}: required anchor not found: {anchor_id}")
        return
    if row.get("anchor_kind") != expected_kind:
        errors.append(f"{expected_path}: {anchor_id} must keep anchor_kind={expected_kind}")


def validate() -> list[str]:
    errors: list[str] = []

    canonical_rows = {path: read_jsonl(path, errors) for path in CANONICAL_FILES}
    batch_rows = {
        QUERY_PROFILE_BATCH_PATH: read_jsonl(QUERY_PROFILE_BATCH_PATH, errors),
        SEARCH_LOG_BATCH_PATH: read_jsonl(SEARCH_LOG_BATCH_PATH, errors),
        THEMATIC_BATCH_PATH: read_jsonl(THEMATIC_BATCH_PATH, errors),
    }

    query_profile_map = build_row_map(canonical_rows[QUERY_PROFILES_PATH], "query_profile_id", QUERY_PROFILES_PATH, errors)
    search_log_map = build_row_map(canonical_rows[SEARCH_LOGS_PATH], "search_id", SEARCH_LOGS_PATH, errors)
    build_row_map(canonical_rows[THEMATIC_ANCHORS_PATH], "anchor_id", THEMATIC_ANCHORS_PATH, errors)

    lane_maps = {
        THEMATIC_OBJECTS_PATH: build_row_map(canonical_rows[THEMATIC_OBJECTS_PATH], "anchor_id", THEMATIC_OBJECTS_PATH, errors),
        THEMATIC_MECHANISMS_PATH: build_row_map(
            canonical_rows[THEMATIC_MECHANISMS_PATH], "anchor_id", THEMATIC_MECHANISMS_PATH, errors
        ),
        THEMATIC_EVENTS_PATH: build_row_map(canonical_rows[THEMATIC_EVENTS_PATH], "anchor_id", THEMATIC_EVENTS_PATH, errors),
    }

    validate_cross_lane_uniqueness(lane_maps, errors)

    validate_source_batch_presence(
        batch_rows[QUERY_PROFILE_BATCH_PATH],
        "query_profile_id",
        QUERY_PROFILE_BATCH_PATH,
        query_profile_map,
        "data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl",
        errors,
    )
    validate_source_batch_presence(
        batch_rows[SEARCH_LOG_BATCH_PATH],
        "search_id",
        SEARCH_LOG_BATCH_PATH,
        search_log_map,
        "data/search_log_batches/i5b_next_four_20260618.jsonl",
        errors,
    )

    thematic_lane_union: dict[str, dict[str, Any]] = {}
    for row_map in lane_maps.values():
        thematic_lane_union.update(row_map)
    validate_source_batch_presence(
        batch_rows[THEMATIC_BATCH_PATH],
        "anchor_id",
        THEMATIC_BATCH_PATH,
        thematic_lane_union,
        "data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl",
        errors,
    )

    validate_search_log_source_fields(batch_rows[SEARCH_LOG_BATCH_PATH], search_log_map, errors)
    validate_special_lane_row(
        lane_maps[THEMATIC_EVENTS_PATH],
        THEMATIC_EVENTS_PATH,
        CHUWANGYING_EVENT_ANCHOR_ID,
        "event",
        errors,
    )
    validate_special_lane_row(
        lane_maps[THEMATIC_MECHANISMS_PATH],
        THEMATIC_MECHANISMS_PATH,
        SHENTUGANG_MECHANISM_ANCHOR_ID,
        "mechanism",
        errors,
    )

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Canonical data integrity validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Canonical data integrity validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
