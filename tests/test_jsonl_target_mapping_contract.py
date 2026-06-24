from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.jsonl_target_mapping import (
    BLOCKED_REPORT_TERMS,
    CANONICAL_JSONL_FILES,
    MAPPING_VERSION,
    build_contract_report,
    build_mappings,
    is_reference_risk_field,
    main,
    report_as_json,
)


FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "jsonl_import"
FORBIDDEN_PATHS = [
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "db" / "schema.sql",
    ROOT / "exports" / "markdown_views",
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
    ROOT / "docs" / "分项规则",
    ROOT / "docs" / "证据规则",
]


def test_every_canonical_jsonl_file_has_mapping_entry() -> None:
    report = build_contract_report(source_root=FIXTURE_ROOT)

    assert report["mapping_version"] == MAPPING_VERSION
    assert set(report["files"]) == set(CANONICAL_JSONL_FILES)
    assert report["unmapped_files"] == []
    for relative in CANONICAL_JSONL_FILES:
        assert report["files"][relative]["target_tables"]
        assert "staging_only" in report["files"][relative]


def test_contract_report_uses_only_canonical_files_not_batches_or_archive(monkeypatch) -> None:
    original_read_text = Path.read_text
    forbidden_parts = (("data", "batches"), ("archive", "data"))

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        parts = tuple(self.parts)
        for first, second in forbidden_parts:
            if first in parts and second in parts:
                raise AssertionError(f"forbidden path read: {self}")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    report = build_contract_report(source_root=ROOT)

    assert report["files_missing"] == []


def test_thematic_anchor_files_are_staging_only_without_target_schema() -> None:
    report = build_contract_report(source_root=FIXTURE_ROOT)

    for relative in [
        "data/thematic_anchors.jsonl",
        "data/thematic_anchor_objects.jsonl",
        "data/thematic_anchor_events.jsonl",
        "data/thematic_anchor_mechanisms.jsonl",
    ]:
        entry = report["files"][relative]
        assert entry["staging_only"] is True
        assert "anchors_candidate" in entry["target_tables"]
        assert entry["blocked_reason"] == "current PostgreSQL schema has no anchors or anchor_links target tables"


def test_reference_risk_fields_are_reported_and_recognized() -> None:
    report = build_contract_report(source_root=FIXTURE_ROOT)

    for field in ["linked_evidence_ids", "linked_source_ids", "other_ids", "source_id", "cross_item_split_signals"]:
        assert is_reference_risk_field(field)

    assert report["reference_risk_summary"]["data/evidence_cards.jsonl"] == [
        "cross_item_split_signals",
        "linked_cluster_ids",
        "linked_source_ids",
        "source_id",
    ]
    assert "linked_evidence_ids" in report["reference_risk_summary"]["data/search_logs.jsonl"]


def test_dynamic_reference_risk_fields_are_not_reported_as_unknown(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    data_dir = fixture / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "search_logs.jsonl").write_text(
        '{"search_id":"SRCH-TEST-001","linked_evidence_id":"EVD-TEST-001","cross_item_watch":true}\n',
        encoding="utf-8",
    )

    report = build_contract_report(source_root=fixture)

    assert "linked_evidence_id" in report["reference_risk_summary"]["data/search_logs.jsonl"]
    assert "cross_item_watch" in report["reference_risk_summary"]["data/search_logs.jsonl"]
    assert "data/search_logs.jsonl" not in report["unknown_fields_by_file"]


def test_evidence_card_source_id_is_not_direct_passage_mapping() -> None:
    mapping = build_mappings()["data/evidence_cards.jsonl"].as_report()
    direct_text = json.dumps(mapping["direct_fields"], sort_keys=True)

    assert "source_id" not in mapping["direct_fields"]
    assert "passage_id" not in direct_text
    assert mapping["reference_risk_fields"]["source_id"].startswith("source_id is not passage_id")


def test_item_and_subitem_are_range_filters_not_direct_evidence_relationships() -> None:
    report = build_contract_report(source_root=FIXTURE_ROOT)

    for relative in [
        "data/query_profiles.jsonl",
        "data/search_logs.jsonl",
        "data/evidence_cards.jsonl",
        "data/evidence_clusters.jsonl",
    ]:
        entry = report["files"][relative]
        assert "item" in entry["range_filter_fields"]
        assert "subitem" in entry["range_filter_fields"]
        assert "item" not in entry["direct_fields"]
        assert "subitem" not in entry["direct_fields"]


def test_contract_report_exposes_fixture_duplicates_missing_and_unknown_fields(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    data_dir = fixture / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "query_profiles.jsonl").write_text(
        "\n".join(
            [
                '{"query_profile_id":"QRY-TEST-001","item":"talent","subitem":"B","unexpected_field":1}',
                '{"query_profile_id":"QRY-TEST-001","item":"talent","subitem":"B"}',
                '{"item":"talent","subitem":"B"}',
            ]
        ),
        encoding="utf-8",
    )

    report = build_contract_report(source_root=fixture)

    assert report["files_seen"] == ["data/query_profiles.jsonl"]
    assert "data/search_logs.jsonl" in report["files_missing"]
    assert report["duplicate_codes_by_file"]["data/query_profiles.jsonl"]["QRY-TEST-001"] == [1, 2]
    assert report["missing_required_fields_by_file"]["data/query_profiles.jsonl"]["query_profile_id"] == [3]
    assert report["unknown_fields_by_file"]["data/query_profiles.jsonl"] == ["unexpected_field"]


def test_contract_report_contains_no_blocked_scoring_or_ranking_terms() -> None:
    text = report_as_json(build_contract_report(source_root=FIXTURE_ROOT))

    for term in BLOCKED_REPORT_TERMS:
        assert term not in text


def test_contract_report_cli_is_offline_and_prints_json(monkeypatch, capsys) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in JSONL target mapping contract tests")

    monkeypatch.setattr(socket, "socket", fail_socket)

    assert main(["--contract-report", "--source-root", str(FIXTURE_ROOT)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "contract-report"
    assert payload["mapping_version"] == MAPPING_VERSION


def test_default_contract_paths_do_not_touch_forbidden_paths(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in JSONL target mapping contract tests")

    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    build_contract_report()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before


def test_target_mapping_tool_uses_no_psql_or_subprocess() -> None:
    source = (ROOT / "scripts" / "platform" / "jsonl_target_mapping.py").read_text(encoding="utf-8")

    assert "import subprocess" not in source
    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "psycopg" not in source


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
