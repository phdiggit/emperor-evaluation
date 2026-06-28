from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]

VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "validate.validate_source_evidence_canonical_stores",
    ROOT / "scripts" / "validate" / "validate_source_evidence_canonical_stores.py",
)
assert VALIDATOR_SPEC is not None
validator = importlib.util.module_from_spec(VALIDATOR_SPEC)
assert VALIDATOR_SPEC.loader is not None
VALIDATOR_SPEC.loader.exec_module(validator)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def seed_minimal_data(tmp_path: Path, monkeypatch) -> Path:
    data_dir = tmp_path / "data"
    batches_dir = data_dir / "batches"
    batch_dir = batches_dir / "sample_batch"
    batch_dir.mkdir(parents=True)

    write_jsonl(data_dir / "sources.jsonl", [{"source_id": "SRC-1", "title": "史记"}])
    write_jsonl(
        data_dir / "search_logs.jsonl",
        [{"search_id": "SRCH-1", "person": "测试", "item": "第五项", "subitem": "第五项B"}],
    )
    write_jsonl(
        data_dir / "evidence_cards.jsonl",
        [{"evidence_id": "EVD-1", "source_id": "SRC-1", "person": "测试", "item": "第五项", "subitem": "第五项B"}],
    )
    write_jsonl(data_dir / "evidence_clusters.jsonl", [{"cluster_id": "ADJ-1", "linked_evidence_ids": ["EVD-1"]}])
    write_jsonl(data_dir / "query_profiles.jsonl", [{"query_profile_id": "QRY-1"}])
    write_jsonl(
        data_dir / "source_packs.jsonl",
        [
            {
                "source_pack_id": "SP-1",
                "source_id": "SRC-1",
                "linked_search_ids": ["SRCH-1"],
                "linked_evidence_ids": ["EVD-1"],
                "linked_cluster_ids": ["ADJ-1"],
            }
        ],
    )
    write_jsonl(
        data_dir / "anchors.jsonl",
        [{"anchor_id": "ANCH-1", "anchor_type": "object", "linked_evidence_ids": ["EVD-1"], "linked_cluster_ids": ["ADJ-1"]}],
    )
    write_jsonl(
        data_dir / "object_anchor_coverage.jsonl",
        [
            {
                "anchor_coverage_id": "ANCOV-1",
                "anchor_ids": ["ANCH-1"],
                "linked_search_id": "SRCH-1",
                "linked_source_pack_ids": ["SP-1"],
                "linked_source_ids": ["SRC-1"],
                "linked_evidence_ids": ["EVD-1"],
                "linked_cluster_ids": ["ADJ-1"],
            }
        ],
    )
    write_jsonl(
        data_dir / "query_lane_coverage.jsonl",
        [
            {
                "lane_coverage_id": "LCOV-1",
                "lane_group": "positive",
                "coverage_status": "converted_to_card",
                "query_profile_id": "QRY-1",
                "search_ids": ["SRCH-1"],
                "source_pack_ids": ["SP-1"],
                "linked_evidence_ids": ["EVD-1"],
                "anchor_coverage_ids": ["ANCOV-1"],
            }
        ],
    )
    (batch_dir / "manifest.yml").write_text(
        yaml.safe_dump({"batch_id": "sample_batch", "lifecycle_status": "active_review_batch"}, allow_unicode=True),
        encoding="utf-8",
    )

    monkeypatch.setattr(validator, "DATA_DIR", data_dir)
    monkeypatch.setattr(validator, "BATCHES_DIR", batches_dir)
    for name in [
        "SOURCE_PACKS_PATH",
        "ANCHORS_PATH",
        "OBJECT_ANCHOR_COVERAGE_PATH",
        "QUERY_LANE_COVERAGE_PATH",
        "SOURCES_PATH",
        "SEARCH_LOGS_PATH",
        "EVIDENCE_CARDS_PATH",
        "EVIDENCE_CLUSTERS_PATH",
        "QUERY_PROFILES_PATH",
    ]:
        monkeypatch.setattr(validator, name, data_dir / getattr(validator, name).name)
    return data_dir


def test_validator_cli_passes_on_repo_data() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate" / "validate_source_evidence_canonical_stores.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Source/evidence canonical store validation passed." in result.stdout


def test_validate_source_evidence_store_passes_with_minimal_fixture(tmp_path: Path, monkeypatch) -> None:
    seed_minimal_data(tmp_path, monkeypatch)

    assert validator.validate() == []


def test_duplicate_source_pack_id_fails(tmp_path: Path, monkeypatch) -> None:
    data_dir = seed_minimal_data(tmp_path, monkeypatch)
    write_jsonl(
        data_dir / "source_packs.jsonl",
        [
            {"source_pack_id": "SP-1", "source_id": "SRC-1"},
            {"source_pack_id": "SP-1", "source_id": "SRC-1"},
        ],
    )

    errors = validator.validate()

    assert any("duplicate source_pack_id: SP-1" in error for error in errors)


def test_missing_source_pack_reference_fails(tmp_path: Path, monkeypatch) -> None:
    data_dir = seed_minimal_data(tmp_path, monkeypatch)
    write_jsonl(
        data_dir / "query_lane_coverage.jsonl",
        [
            {
                "lane_coverage_id": "LCOV-1",
                "lane_group": "positive",
                "coverage_status": "converted_to_card",
                "source_pack_ids": ["SP-MISSING"],
            }
        ],
    )

    errors = validator.validate()

    assert any("source_pack_ids references missing id: SP-MISSING" in error for error in errors)


def test_invalid_batch_lifecycle_fails(tmp_path: Path, monkeypatch) -> None:
    data_dir = seed_minimal_data(tmp_path, monkeypatch)
    manifest = data_dir / "batches" / "sample_batch" / "manifest.yml"
    manifest.write_text(
        yaml.safe_dump({"batch_id": "sample_batch", "lifecycle_status": "almost_done"}, allow_unicode=True),
        encoding="utf-8",
    )

    errors = validator.validate()

    assert any("lifecycle_status must be one of" in error for error in errors)
