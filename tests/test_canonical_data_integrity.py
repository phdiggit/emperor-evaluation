import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]

VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "validate.validate_canonical_data_integrity",
    ROOT / "scripts" / "validate" / "validate_canonical_data_integrity.py",
)
assert VALIDATOR_SPEC is not None
validator = importlib.util.module_from_spec(VALIDATOR_SPEC)
assert VALIDATOR_SPEC.loader is not None
VALIDATOR_SPEC.loader.exec_module(validator)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


@pytest.fixture()
def canonical_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data_dir = tmp_path / "data"
    (data_dir / "query_profile_batches").mkdir(parents=True)
    (data_dir / "search_log_batches").mkdir(parents=True)
    (data_dir / "thematic_anchor_batches").mkdir(parents=True)

    write_jsonl(
        data_dir / "query_profiles.jsonl",
        [
            {
                "query_profile_id": "QRY-I5B-LISHIMIN-MIGRATION-20260618",
                "item": "第五项",
                "subitem": "第五项B",
                "search_modes": [],
                "positive_terms": [],
                "negative_terms": [],
                "reversal_terms": [],
                "source_scopes": [],
                "reverse_search_required_when": [],
                "thematic_anchor_targets": [],
                "cross_item_split_notes": [],
                "note": "",
                "source_batch": "data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl",
            }
        ],
    )
    write_jsonl(
        data_dir / "search_logs.jsonl",
        [
            {
                "search_id": "SRCH-I5B-LIUBANG-CUT-ADJACENT-001",
                "person": "刘邦",
                "item": "第五项",
                "subitem": "第五项B",
                "polarity": "negative",
                "trigger_family": "跨项边界风险",
                "query_terms": "测试",
                "query": "测试",
                "source_scope": "primary_sources_web",
                "searched_at": "2026-06-18",
                "result_status": "lead_needs_source_review",
                "result_summary": "测试",
                "linked_evidence_id": "",
                "note": "",
                "query_profile_id": "QRY-I5B-LIUBANG-20260618",
                "source_batch": "data/search_log_batches/i5b_next_four_20260618.jsonl",
                "source_status": "lead_needs_source_review",
                "source_polarity": "neutral",
            }
        ],
    )
    write_jsonl(
        data_dir / "thematic_anchors.jsonl",
        [
            {
                "anchor_id": "ANCH-I5B-AGG-TEST-001",
                "theme": "测试主题",
                "item": "第五项",
                "subitem": "第五项B",
                "persons": ["李世民"],
                "linked_evidence_ids": [],
                "linked_cluster_ids": [],
                "anchor_summary": "测试",
                "comparative_value": "测试",
                "note": "",
            }
        ],
    )
    write_jsonl(
        data_dir / "thematic_anchor_objects.jsonl",
        [
            {
                "anchor_id": "ANCH-I5B-PERSON-TEST-001",
                "item": "第五项",
                "subitem": "第五项B",
                "anchor_kind": "person",
                "anchor_scope": "three_pilot_migration",
                "object_type": "人物",
                "object_name": "测试对象",
                "object_level": "中",
                "anchor_role": "测试",
                "usable_for": [],
                "cross_item_risks": [],
                "consensus_level": "medium",
                "review_status": "provisional",
                "source_batch": "data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl",
                "note": "",
            }
        ],
    )
    write_jsonl(
        data_dir / "thematic_anchor_mechanisms.jsonl",
        [
            {
                "anchor_id": validator.SHENTUGANG_MECHANISM_ANCHOR_ID,
                "item": "第五项",
                "subitem": "第五项B",
                "anchor_kind": "mechanism",
                "anchor_scope": "three_pilot_migration",
                "object_type": "机制",
                "object_name": "申屠刚表达安全机制",
                "object_level": "高",
                "anchor_role": "测试",
                "usable_for": [],
                "cross_item_risks": [],
                "consensus_level": "medium_high",
                "review_status": "provisional",
                "linked_persons": ["刘秀"],
                "source_batch": "data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl",
                "note": "",
            }
        ],
    )
    write_jsonl(
        data_dir / "thematic_anchor_events.jsonl",
        [
            {
                "anchor_id": validator.CHUWANGYING_EVENT_ANCHOR_ID,
                "item": "第五项",
                "subitem": "第五项B",
                "anchor_kind": "event",
                "anchor_scope": "three_pilot_migration",
                "object_type": "事件",
                "object_name": "楚王英案扩大牵连",
                "object_level": "高",
                "anchor_role": "测试",
                "usable_for": [],
                "cross_item_risks": [],
                "consensus_level": "medium_high",
                "review_status": "provisional",
                "linked_persons": ["刘庄"],
                "source_batch": "data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl",
                "note": "",
            }
        ],
    )

    write_jsonl(
        data_dir / "query_profile_batches" / "i5b_three_pilot_profiles_migration_20260618.jsonl",
        [
            {
                "query_profile_id": "QRY-I5B-LISHIMIN-MIGRATION-20260618",
            }
        ],
    )
    write_jsonl(
        data_dir / "search_log_batches" / "i5b_next_four_20260618.jsonl",
        [
            {
                "search_id": "SRCH-I5B-LIUBANG-CUT-ADJACENT-001",
            }
        ],
    )
    write_jsonl(
        data_dir / "thematic_anchor_batches" / "i5b_three_pilot_object_anchors_20260618.jsonl",
        [
            {"anchor_id": "ANCH-I5B-PERSON-TEST-001"},
            {"anchor_id": validator.SHENTUGANG_MECHANISM_ANCHOR_ID},
            {"anchor_id": validator.CHUWANGYING_EVENT_ANCHOR_ID},
        ],
    )

    monkeypatch.setattr(validator, "DATA_DIR", data_dir)
    monkeypatch.setattr(validator, "QUERY_PROFILES_PATH", data_dir / "query_profiles.jsonl")
    monkeypatch.setattr(validator, "SEARCH_LOGS_PATH", data_dir / "search_logs.jsonl")
    monkeypatch.setattr(validator, "THEMATIC_ANCHORS_PATH", data_dir / "thematic_anchors.jsonl")
    monkeypatch.setattr(validator, "THEMATIC_OBJECTS_PATH", data_dir / "thematic_anchor_objects.jsonl")
    monkeypatch.setattr(validator, "THEMATIC_MECHANISMS_PATH", data_dir / "thematic_anchor_mechanisms.jsonl")
    monkeypatch.setattr(validator, "THEMATIC_EVENTS_PATH", data_dir / "thematic_anchor_events.jsonl")
    monkeypatch.setattr(
        validator,
        "CANONICAL_FILES",
        [
            data_dir / "query_profiles.jsonl",
            data_dir / "search_logs.jsonl",
            data_dir / "thematic_anchors.jsonl",
            data_dir / "thematic_anchor_objects.jsonl",
            data_dir / "thematic_anchor_mechanisms.jsonl",
            data_dir / "thematic_anchor_events.jsonl",
        ],
    )
    monkeypatch.setattr(
        validator,
        "QUERY_PROFILE_BATCH_PATH",
        data_dir / "query_profile_batches" / "i5b_three_pilot_profiles_migration_20260618.jsonl",
    )
    monkeypatch.setattr(
        validator,
        "SEARCH_LOG_BATCH_PATH",
        data_dir / "search_log_batches" / "i5b_next_four_20260618.jsonl",
    )
    monkeypatch.setattr(
        validator,
        "THEMATIC_BATCH_PATH",
        data_dir / "thematic_anchor_batches" / "i5b_three_pilot_object_anchors_20260618.jsonl",
    )
    monkeypatch.setattr(
        validator,
        "LANE_FILES",
        [
            data_dir / "thematic_anchor_objects.jsonl",
            data_dir / "thematic_anchor_mechanisms.jsonl",
            data_dir / "thematic_anchor_events.jsonl",
        ],
    )
    return data_dir


def test_validator_cli_passes_on_repo_data() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate" / "validate_canonical_data_integrity.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Canonical data integrity validation passed." in result.stdout


def test_validate_canonical_data_integrity_passes_with_temp_dir(canonical_data_dir: Path) -> None:
    assert validator.validate() == []


def test_duplicate_lane_anchor_id_fails(canonical_data_dir: Path) -> None:
    write_jsonl(
        canonical_data_dir / "thematic_anchor_events.jsonl",
        [
            {
                "anchor_id": validator.SHENTUGANG_MECHANISM_ANCHOR_ID,
                "item": "第五项",
                "subitem": "第五项B",
                "anchor_kind": "event",
                "anchor_scope": "three_pilot_migration",
                "object_type": "事件",
                "object_name": "错放",
                "object_level": "高",
                "anchor_role": "测试",
                "usable_for": [],
                "cross_item_risks": [],
                "consensus_level": "medium_high",
                "review_status": "provisional",
                "linked_persons": ["刘庄"],
                "source_batch": "data/thematic_anchor_batches/i5b_three_pilot_object_anchors_20260618.jsonl",
                "note": "",
            }
        ],
    )

    errors = validator.validate()

    assert any("duplicate anchor_id across lanes" in error for error in errors)


def test_missing_source_batch_fails_for_query_profile_import(canonical_data_dir: Path) -> None:
    write_jsonl(
        canonical_data_dir / "query_profiles.jsonl",
        [
            {
                "query_profile_id": "QRY-I5B-LISHIMIN-MIGRATION-20260618",
                "item": "第五项",
                "subitem": "第五项B",
                "search_modes": [],
                "positive_terms": [],
                "negative_terms": [],
                "reversal_terms": [],
                "source_scopes": [],
                "reverse_search_required_when": [],
                "thematic_anchor_targets": [],
                "cross_item_split_notes": [],
                "note": "",
            }
        ],
    )

    errors = validator.validate()

    assert any("must retain source_batch=data/query_profile_batches/i5b_three_pilot_profiles_migration_20260618.jsonl" in error for error in errors)


def test_neutral_source_polarity_requires_preserved_source_field_and_negative_canonical_polarity(
    canonical_data_dir: Path,
) -> None:
    write_jsonl(
        canonical_data_dir / "search_logs.jsonl",
        [
            {
                "search_id": "SRCH-I5B-LIUBANG-CUT-ADJACENT-001",
                "person": "刘邦",
                "item": "第五项",
                "subitem": "第五项B",
                "polarity": "positive",
                "trigger_family": "跨项边界风险",
                "query_terms": "测试",
                "query": "测试",
                "source_scope": "primary_sources_web",
                "searched_at": "2026-06-18",
                "result_status": "lead_needs_source_review",
                "result_summary": "测试",
                "linked_evidence_id": "",
                "note": "",
                "query_profile_id": "QRY-I5B-LIUBANG-20260618",
                "source_batch": "data/search_log_batches/i5b_next_four_20260618.jsonl",
                "source_status": "lead_needs_source_review",
                "source_polarity": "neutral",
            }
        ],
    )

    errors = validator.validate()

    assert any("must keep canonical polarity=negative when source_polarity=neutral" in error for error in errors)
