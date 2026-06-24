from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.jsonl_staging_mapper import SourceImportRow, build_staging_rows
from scripts.platform.jsonl_target_mapping import CANONICAL_JSONL_FILES
from scripts.platform.jsonl_unknown_field_triage import (
    TRIAGE_VERSION,
    build_contract_report,
    main,
    report_as_json,
)


FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "jsonl_import"
BLOCKED_REPORT_TERMS = ("score", "rank", "final_score", "leaderboard")
FORBIDDEN_PATHS = [
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "db" / "schema.sql",
    ROOT / "exports" / "markdown_views",
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
    ROOT / "docs" / "分项规则",
    ROOT / "docs" / "证据规则",
]


def test_triage_report_has_required_shape_and_line_traceability() -> None:
    report = build_contract_report(source_root=ROOT)

    assert report["mode"] == "contract-report"
    assert report["triage_version"] == TRIAGE_VERSION
    assert set(report["source_files"]) == set(CANONICAL_JSONL_FILES)
    assert report["decision_counts"]["payload"] > 0
    assert report["decision_counts"]["reference_risk"] > 0
    assert report["decision_counts"]["manual_review"] > 0
    assert report["decision_counts"]["suspected_deprecated"] > 0

    evidence_decisions = {
        item["field"]: item for item in report["decisions_by_file"]["data/evidence_cards.jsonl"]
    }
    assert evidence_decisions["aggravating_factors"]["category"] == "payload"
    assert evidence_decisions["aggravating_factors"]["line_numbers"][:2] == [1, 2]
    assert evidence_decisions["cluster_candidate_id"]["category"] == "reference_risk"
    assert "resolver_risk_guidance" in evidence_decisions["cluster_candidate_id"]


def test_confirmed_fields_enter_mapping_payload_and_reference_risk_buckets() -> None:
    rows = build_staging_rows(
        [
            SourceImportRow(
                id=1,
                source_file="data/evidence_clusters.jsonl",
                line_no=1,
                import_status="accepted",
                error=None,
                payload={
                    "cluster_id": "CLU-TEST-001",
                    "cluster_type": "talent_ecosystem",
                    "status": "draft",
                    "five_axis_assessment": {"directness": "high"},
                },
            ),
            SourceImportRow(
                id=2,
                source_file="data/evidence_cards.jsonl",
                line_no=1,
                import_status="accepted",
                error=None,
                payload={
                    "evidence_id": "EVD-TEST-001",
                    "cluster_candidate_id": "CLU-TEST-001",
                    "aggravating_factors": ["factor-a"],
                },
            ),
        ]
    )

    cluster_row, evidence_row = rows
    assert "cluster_type" in cluster_row.candidate_fields
    assert "status" in cluster_row.direct_fields
    assert "five_axis_assessment" in cluster_row.payload_fields
    assert "cluster_candidate_id" in evidence_row.reference_risk_fields
    assert "aggravating_factors" in evidence_row.payload_fields


def test_unregistered_unknown_field_falls_back_to_manual_review(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    data_dir = fixture / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "query_profiles.jsonl").write_text(
        '{"query_profile_id":"QRY-TEST-001","item":"talent","subitem":"B","new_unknown_field":true}\n',
        encoding="utf-8",
    )

    report = build_contract_report(source_root=fixture)
    decisions = {
        item["field"]: item for item in report["decisions_by_file"]["data/query_profiles.jsonl"]
    }

    assert decisions["new_unknown_field"]["category"] == "manual_review"
    assert report["unclassified_fields_by_file"]["data/query_profiles.jsonl"] == ["new_unknown_field"]
    assert report["remaining_unknown_fields_by_file"]["data/query_profiles.jsonl"] == ["new_unknown_field"]


def test_suspected_deprecated_is_report_only_and_original_value_is_preserved() -> None:
    report = build_contract_report(source_root=ROOT)
    decisions = {
        item["field"]: item for item in report["decisions_by_file"]["data/query_profiles.jsonl"]
    }
    rows = build_staging_rows(
        [
            SourceImportRow(
                id=1,
                source_file="data/query_profiles.jsonl",
                line_no=1,
                import_status="accepted",
                error=None,
                payload={
                    "query_profile_id": "QRY-TEST-001",
                    "item": "talent",
                    "subitem": "B",
                    "schema_version": "1.0",
                },
            )
        ]
    )

    assert decisions["schema_version"]["category"] == "suspected_deprecated"
    assert rows[0].payload_fields["schema_version"] == "1.0"
    assert "schema_version" not in rows[0].unknown_fields


def test_dynamic_reference_risk_fields_are_not_ordinary_unknowns(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    data_dir = fixture / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "search_logs.jsonl").write_text(
        '{"search_id":"SRCH-TEST-001","linked_evidence_id":"EVD-TEST-001","cross_item_watch":true}\n',
        encoding="utf-8",
    )

    report = build_contract_report(source_root=fixture)
    decisions = {item["field"]: item for item in report["decisions_by_file"]["data/search_logs.jsonl"]}

    assert decisions["linked_evidence_id"]["category"] == "reference_risk"
    assert decisions["cross_item_watch"]["category"] == "reference_risk"
    assert report["remaining_unknown_fields_by_file"] == {}


def test_contract_report_reads_only_canonical_jsonl_not_batches_or_archive(monkeypatch) -> None:
    original_read_text = Path.read_text
    forbidden_parts = (("data", "batches"), ("archive", "data"))

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        parts = tuple(self.parts)
        for first, second in forbidden_parts:
            if first in parts and second in parts:
                raise AssertionError(f"forbidden path read: {self}")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = build_contract_report(source_root=ROOT)

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert set(report["source_files"]) == set(CANONICAL_JSONL_FILES)
    assert after == before


def test_contract_report_cli_emits_json_under_no_network_environment(monkeypatch, capsys) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in unknown-field triage contract tests")

    monkeypatch.setattr(socket, "socket", fail_socket)

    assert main(["--contract-report", "--source-root", str(FIXTURE_ROOT)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "contract-report"
    assert payload["triage_version"] == TRIAGE_VERSION


def test_contract_report_contains_no_blocked_terms() -> None:
    text = report_as_json(build_contract_report(source_root=ROOT)).lower()

    for term in BLOCKED_REPORT_TERMS:
        assert term not in text


def test_unknown_field_triage_tool_uses_no_database_shell_or_legacy_dsn() -> None:
    source = (ROOT / "scripts" / "platform" / "jsonl_unknown_field_triage.py").read_text(encoding="utf-8")

    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "psycopg" not in source


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
