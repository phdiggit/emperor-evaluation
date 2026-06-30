from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]

# Lifecycle: transitional #380 legacy batch cleanup guard. Retire this section
# after these folders are archived or covered by a generic manifest validator.
LEGACY_BATCH_CLEANUP_MANIFESTS = {
    "i5b_zhu_yuanzhang_micro_supplement": "absorbed_to_canonical",
    "i5b_next_four": "absorbed_to_canonical",
    "i5b_expanded_pilot_batch1": "active_review_batch",
}
RETIRED_BATCH_LOCAL_FACT_FILES = [
    ROOT / "data" / "batches" / "i5b_zhu_yuanzhang_micro_supplement" / "sources.jsonl",
    ROOT / "data" / "batches" / "i5b_zhu_yuanzhang_micro_supplement" / "evidence_cards.jsonl",
    ROOT / "data" / "batches" / "i5b_next_four" / "query_profiles.jsonl",
    ROOT / "data" / "batches" / "i5b_next_four" / "search_logs.jsonl",
    ROOT / "data" / "batches" / "i5b_expanded_pilot_batch1" / "query_profiles.jsonl",
    ROOT / "data" / "batches" / "i5b_expanded_pilot_batch1" / "search_logs.jsonl",
    ROOT / "data" / "batches" / "i5b_expanded_pilot_batch1" / "sources_targeted_supplement.jsonl",
    ROOT / "data" / "batches" / "i5b_expanded_pilot_batch1" / "evidence_cards_targeted_supplement.jsonl",
]
EXPANDED_PILOT_REVIEW_FILES = [
    ROOT / "data" / "batches" / "i5b_expanded_pilot_batch1" / "review" / "adjudication_cluster.jsonl",
    ROOT / "data" / "batches" / "i5b_expanded_pilot_batch1" / "review" / "adjudication_post_supplement.jsonl",
    ROOT / "data" / "batches" / "i5b_expanded_pilot_batch1" / "review" / "readiness_audit.jsonl",
    ROOT / "data" / "batches" / "i5b_expanded_pilot_batch1" / "review" / "readiness_followup.jsonl",
    ROOT / "data" / "batches" / "i5b_expanded_pilot_batch1" / "review" / "relative_band_preparation.jsonl",
    ROOT / "data" / "batches" / "i5b_expanded_pilot_batch1" / "review" / "human_review_package.jsonl",
    ROOT / "data" / "batches" / "i5b_expanded_pilot_batch1" / "review" / "yongzheng_rule_boundary_review.jsonl",
    ROOT / "data" / "batches" / "i5b_expanded_pilot_batch1" / "review" / "yongzheng_role_class_sweep.jsonl",
]
I5B_TYPICAL_SOURCE_EVIDENCE_MANIFEST = ROOT / "data" / "batches" / "i5b_typical_source_evidence" / "manifest.yml"
CANONICAL_REF_STORE_SPECS = {
    "source_pack_ids": ("source_packs.jsonl", "source_pack_id"),
    "anchor_ids": ("anchors.jsonl", "anchor_id"),
    "anchor_coverage_ids": ("object_anchor_coverage.jsonl", "anchor_coverage_id"),
    "lane_coverage_ids": ("query_lane_coverage.jsonl", "lane_coverage_id"),
    "query_profile_ids": ("query_profiles.jsonl", "query_profile_id"),
    "search_ids": ("search_logs.jsonl", "search_id"),
    "evidence_ids": ("evidence_cards.jsonl", "evidence_id"),
    "cluster_ids": ("evidence_clusters.jsonl", "cluster_id"),
}
B3_CUT_ADJACENT_ANCHOR_IDS = {
    "ANCH-I5B-B3-LILONGJI-CUT-ADJACENT-001",
    "ANCH-I5B-B3-WUZETIAN-CUT-ADJACENT-001",
    "ANCH-I5B-B3-LIZHI-CUT-ADJACENT-001",
    "ANCH-I5B-B3-LIYUAN-CUT-ADJACENT-001",
    "ANCH-I5B-B3-LICHUN-CUT-ADJACENT-001",
}
B3_CUT_ADJACENT_ANCHOR_COVERAGE_IDS = {
    "ANCOV-I5B-B3-LILONGJI-CUT-ADJACENT-001",
    "ANCOV-I5B-B3-WUZETIAN-CUT-ADJACENT-001",
    "ANCOV-I5B-B3-LIZHI-CUT-ADJACENT-001",
    "ANCOV-I5B-B3-LIYUAN-CUT-ADJACENT-001",
    "ANCOV-I5B-B3-LICHUN-CUT-ADJACENT-001",
}
B3_CUT_ADJACENT_LANE_COVERAGE_IDS = {
    "LCOV-I5B-B3-LILONGJI-CUT-ADJACENT-001",
    "LCOV-I5B-B3-WUZETIAN-CUT-ADJACENT-001",
    "LCOV-I5B-B3-LIZHI-CUT-ADJACENT-001",
    "LCOV-I5B-B3-LIYUAN-CUT-ADJACENT-001",
    "LCOV-I5B-B3-LICHUN-CUT-ADJACENT-001",
}
B3_SOURCE_VERIFIED_ANCHOR_OBJECT_NAMES = {
    "ANCH-I5B-B3-LILONGJI-POS-YAOCONG-001": "姚崇",
    "ANCH-I5B-B3-LILONGJI-NEG-LILINFU-001": "李林甫",
    "ANCH-I5B-B3-WUZETIAN-POS-LIZHAODE-001": "李昭德",
    "ANCH-I5B-B3-WUZETIAN-NEG-KULI-001": "酷吏罗织机制",
    "ANCH-I5B-B3-LIZHI-POS-LAIJI-001": "来济",
    "ANCH-I5B-B3-LIZHI-NEG-LIYIFU-001": "李义府",
    "ANCH-I5B-B3-LIYUAN-POS-LIUWENJING-001": "刘文静",
    "ANCH-I5B-B3-LIYUAN-NEG-LIUWENJING-001": "刘文静",
    "ANCH-I5B-B3-LICHUN-POS-PEIDU-001": "裴度",
    "ANCH-I5B-B3-LICHUN-NEG-HANYU-001": "韩愈",
}
B3_FORBIDDEN_OBJECT_NAME_LABELS = {
    "相邻项剥离",
    "ADJACENT",
    "授权专任",
    "容谏纳言",
    "人才安全",
    "近臣任用风险",
    "创业谋议采纳",
    "功臣旧臣处置",
    "权相蔽才",
    "酷吏任用风险",
    "强正核心",
    "强负核心",
    "正向核心",
}

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


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_manifest(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def assert_refs_live_in_canonical_stores(refs: dict[str, list[str]]) -> None:
    assert set(refs) <= set(CANONICAL_REF_STORE_SPECS)
    for ref_key, values in refs.items():
        store_name, id_field = CANONICAL_REF_STORE_SPECS[ref_key]
        canonical_ids = {row[id_field] for row in load_jsonl(ROOT / "data" / store_name)}
        assert set(values) <= canonical_ids


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


def test_issue380_legacy_batches_no_longer_expose_batch_local_fact_stores() -> None:
    for batch_id, expected_status in LEGACY_BATCH_CLEANUP_MANIFESTS.items():
        manifest_path = ROOT / "data" / "batches" / batch_id / "manifest.yml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

        assert manifest["lifecycle_status"] == expected_status
        assert manifest.get("status") != "active_batch"
        assert manifest.get("current_input") is not True
        assert manifest.get("classification_reason")
        assert manifest.get("canonical_row_refs")

    for path in RETIRED_BATCH_LOCAL_FACT_FILES:
        assert not path.exists(), f"{path} should be represented by canonical_row_refs, not batch-local JSONL"


def test_issue380_expanded_review_snapshots_have_archive_triggers() -> None:
    manifest_path = ROOT / "data" / "batches" / "i5b_expanded_pilot_batch1" / "manifest.yml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    review_entries = {ROOT / entry["path"]: entry for entry in manifest["review_only_files"]}

    assert set(review_entries) == set(EXPANDED_PILOT_REVIEW_FILES)
    for path in EXPANDED_PILOT_REVIEW_FILES:
        manifest_entry = review_entries[path]
        assert manifest_entry["current_review_input"] is True
        assert manifest_entry["retirement_condition"]
        assert manifest_entry["archive_trigger"]

        for row in load_jsonl(path):
            assert row["retirement_condition"] == manifest_entry["retirement_condition"]
            assert row["archive_trigger"] == manifest_entry["archive_trigger"]


def test_issue384_object_anchor_coverage_reconciles_canonical_evidence() -> None:
    evidence_ids = {row["evidence_id"] for row in load_jsonl(ROOT / "data" / "evidence_cards.jsonl")}
    anchor_rows = load_jsonl(ROOT / "data" / "anchors.jsonl")
    coverage_rows = load_jsonl(ROOT / "data" / "object_anchor_coverage.jsonl")
    lane_rows = load_jsonl(ROOT / "data" / "query_lane_coverage.jsonl")

    covered_evidence_ids = {evidence_id for row in coverage_rows for evidence_id in row.get("linked_evidence_ids", [])}
    anchor_linked_evidence_ids = {
        evidence_id for row in anchor_rows for evidence_id in row.get("linked_evidence_ids", [])
    }
    lane_linked_evidence_ids = {
        evidence_id for row in lane_rows for evidence_id in row.get("linked_evidence_ids", [])
    }

    assert not [row["anchor_coverage_id"] for row in coverage_rows if row.get("anchor_status") == "no_anchor_pending_review"]
    assert evidence_ids <= covered_evidence_ids
    assert anchor_linked_evidence_ids <= covered_evidence_ids
    assert lane_linked_evidence_ids <= covered_evidence_ids
    assert not [
        row["anchor_coverage_id"]
        for row in coverage_rows
        if not row.get("anchor_ids") and not row.get("no_anchor_reason")
    ]

    for batch_id in ["i5b_expanded_pilot_batch1", "i5b_zhu_yuanzhang_micro_supplement"]:
        manifest_path = ROOT / "data" / "batches" / batch_id / "manifest.yml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest_evidence_ids = set(manifest["canonical_row_refs"]["evidence_ids"])

        assert manifest_evidence_ids <= covered_evidence_ids


def test_issue366_aggregate_batch_manifest_refs_live_in_canonical_stores() -> None:
    manifest = load_manifest(I5B_TYPICAL_SOURCE_EVIDENCE_MANIFEST)
    entries = {entry["batch_id"]: entry for entry in manifest["entries"]}

    assert manifest["issue"] == 366
    assert manifest["lifecycle_status"] == "active_review_batch"
    assert manifest["manifest_kind"] == "aggregate_track_manifest"
    assert set(entries) == {
        "i5b_typical_batch_a_20260628",
        "i5b_typical_batch_b1_qin_han_20260628",
        "i5b_typical_batch_b2_han_sui_seed_20260629",
        "i5b_typical_batch_b3_tang_seed_20260630",
    }
    assert "timing" not in manifest

    for entry in entries.values():
        child_manifest = load_manifest(ROOT / entry["source_manifest"])
        refs = entry["canonical_row_refs"]

        assert child_manifest["issue"] == 366
        assert entry["batch_id"] == child_manifest["batch_id"]
        assert entry["persons"] == child_manifest["persons"]
        assert entry["lifecycle_status"] == child_manifest["lifecycle_status"] == "absorbed_to_canonical"
        assert refs == child_manifest["canonical_row_refs"]
        assert_refs_live_in_canonical_stores(refs)

    b2_refs = entries["i5b_typical_batch_b2_han_sui_seed_20260629"]["canonical_row_refs"]
    search_rows = {
        row["search_id"]: row
        for row in load_jsonl(ROOT / "data" / "search_logs.jsonl")
        if row["search_id"] in b2_refs["search_ids"]
    }
    lane_rows = {
        row["lane_coverage_id"]: row
        for row in load_jsonl(ROOT / "data" / "query_lane_coverage.jsonl")
        if row["lane_coverage_id"] in b2_refs["lane_coverage_ids"]
    }

    assert search_rows
    assert lane_rows
    assert all(isinstance(row["query_terms"], list) for row in search_rows.values())
    assert not [
        lane_id
        for row in lane_rows.values()
        for lane_id in row.get("covered_lane_ids", [])
        if lane_id.startswith("I5B-I5B-B2-")
    ]

    b3_refs = entries["i5b_typical_batch_b3_tang_seed_20260630"]["canonical_row_refs"]
    assert len(b3_refs["query_profile_ids"]) == 5
    assert len(b3_refs["search_ids"]) == 15
    assert set(b3_refs["anchor_ids"]) == set(B3_SOURCE_VERIFIED_ANCHOR_OBJECT_NAMES)
    assert not (set(b3_refs["anchor_ids"]) & B3_CUT_ADJACENT_ANCHOR_IDS)
    assert not (set(b3_refs["anchor_coverage_ids"]) & B3_CUT_ADJACENT_ANCHOR_COVERAGE_IDS)
    assert len(b3_refs["evidence_ids"]) == 10
    assert len(b3_refs["cluster_ids"]) == 10


def test_b3_adjacent_only_lanes_do_not_create_object_anchor_rows() -> None:
    anchors = {row["anchor_id"]: row for row in load_jsonl(ROOT / "data" / "anchors.jsonl")}
    coverage = {
        row["anchor_coverage_id"]: row
        for row in load_jsonl(ROOT / "data" / "object_anchor_coverage.jsonl")
    }
    lane_rows = {
        row["lane_coverage_id"]: row
        for row in load_jsonl(ROOT / "data" / "query_lane_coverage.jsonl")
    }

    assert not (B3_CUT_ADJACENT_ANCHOR_IDS & set(anchors))
    assert not (B3_CUT_ADJACENT_ANCHOR_COVERAGE_IDS & set(coverage))

    for lane_id in B3_CUT_ADJACENT_LANE_COVERAGE_IDS:
        row = lane_rows[lane_id]
        assert row["lane_group"] == "adjacent"
        assert row["coverage_status"] == "pending_review"
        assert row["unresolved_reason"]
        assert row["anchor_coverage_ids"] == []
        assert row["source_pack_ids"] == []
        assert row["linked_evidence_ids"] == []


def test_b3_source_verified_anchor_object_names_are_real_objects() -> None:
    anchors = {row["anchor_id"]: row for row in load_jsonl(ROOT / "data" / "anchors.jsonl")}

    b3_anchor_ids = {
        anchor_id for anchor_id in anchors if str(anchor_id).startswith("ANCH-I5B-B3-")
    }
    assert b3_anchor_ids == set(B3_SOURCE_VERIFIED_ANCHOR_OBJECT_NAMES)

    for anchor_id, expected_object_name in B3_SOURCE_VERIFIED_ANCHOR_OBJECT_NAMES.items():
        row = anchors[anchor_id]
        object_name = str(row["object_name"])

        assert object_name == expected_object_name
        assert "相邻项剥离" not in object_name
        assert object_name not in B3_FORBIDDEN_OBJECT_NAME_LABELS
        assert row["anchor_status"] == "source_verified_card_anchor"
        assert str(row["anchor_role"]).startswith("source_verified_evidence_anchor")
        assert row["usable_for"]


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
