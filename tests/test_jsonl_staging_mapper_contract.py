from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.jsonl_staging_mapper import (
    PRIMARY_ENV_DSN,
    ResolvedDsn,
    SourceImportRow,
    build_contract_report,
    build_staging_rows,
    check_environment,
    integration_skip_reason,
    main,
    report_as_json,
    resolve_dsn,
)
from scripts.platform.jsonl_target_mapping import CANONICAL_JSONL_FILES


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
BLOCKED_REPORT_TERMS = ("score", "rank", "final_score", "leaderboard")


def test_resolve_dsn_uses_only_primary_env_and_dotenv_without_legacy_fallback(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"{PRIMARY_ENV_DSN}=postgresql://from-dotenv-primary/db",
                "PG_SEARCH_BENCH_DSN=postgresql://legacy-ignored/db",
            ]
        ),
        encoding="utf-8",
    )

    assert resolve_dsn(env={PRIMARY_ENV_DSN: "postgresql://from-shell-primary/db"}, env_path=env_file).source == (
        f"env:{PRIMARY_ENV_DSN}"
    )
    assert resolve_dsn(env={}, env_path=env_file).source == f".env:{PRIMARY_ENV_DSN}"
    env_file.write_text("PG_SEARCH_BENCH_DSN=postgresql://legacy-ignored/db\n", encoding="utf-8")
    assert resolve_dsn(env={"PG_SEARCH_BENCH_DSN": "postgresql://legacy-ignored/db"}, env_path=env_file).source == (
        "skip"
    )


def test_check_without_dsn_or_driver_is_non_failing_and_does_not_connect(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in staging mapper contract tests")

    monkeypatch.setattr(socket, "socket", fail_socket)
    result = check_environment(ResolvedDsn(None, "skip"), driver_available=False)

    assert result["mode"] == "check"
    assert result["dsn_present"] is False
    assert result["dsn_source"] == "skip"
    assert result["driver"] == "psycopg"
    assert result["driver_available"] is False
    assert result["default_tests_require_postgres"] is False
    assert result["will_apply"] is False


def test_apply_skip_reason_requires_primary_dsn_and_python_driver() -> None:
    assert integration_skip_reason(ResolvedDsn(None, "skip"), driver_available=True) == f"{PRIMARY_ENV_DSN} is not set"
    assert integration_skip_reason(ResolvedDsn("postgresql://example/db", f"env:{PRIMARY_ENV_DSN}"), driver_available=False) == (
        "psycopg is not installed"
    )


def test_contract_report_is_offline_and_has_required_shape(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in staging mapper contract tests")

    monkeypatch.setattr(socket, "socket", fail_socket)
    report = build_contract_report(source_root=FIXTURE_ROOT)

    assert report["mode"] == "contract-report"
    assert report["default_tests_require_postgres"] is False
    assert report["source_files"] == ["data/query_profiles.jsonl"]
    assert report["rows_total"] == 4
    assert report["rows_mapped"] == 4
    assert report["rows_with_reference_risk"] == 1
    assert report["rows_with_validation_errors"] == 2
    assert "query_profiles" in report["target_table_candidates"]
    assert "data/search_logs.jsonl" in report["files_missing"]


def test_every_canonical_jsonl_file_maps_to_staging_or_staging_only_rows() -> None:
    report = build_contract_report(source_root=ROOT)

    assert set(report["source_files"]) == set(CANONICAL_JSONL_FILES)
    assert report["files_missing"] == []
    assert report["rows_total"] > 0
    assert report["rows_mapped"] == report["rows_total"]
    for relative in CANONICAL_JSONL_FILES:
        assert report["rows_by_file"][relative] > 0
    assert set(report["staging_only_files"]) == {
        "data/thematic_anchors.jsonl",
        "data/thematic_anchor_objects.jsonl",
        "data/thematic_anchor_events.jsonl",
        "data/thematic_anchor_mechanisms.jsonl",
    }


def test_reference_risk_fields_do_not_enter_direct_or_candidate_fields() -> None:
    rows = build_staging_rows(
        [
            SourceImportRow(
                id=1,
                source_file="data/evidence_cards.jsonl",
                line_no=1,
                import_status="accepted",
                error=None,
                payload={
                    "evidence_id": "EVD-TEST-001",
                    "source_id": "SRC-TEST-001",
                    "linked_cluster_ids": ["CLU-TEST-001"],
                    "cross_item_split_signals": ["相邻项风险"],
                },
            )
        ]
    )
    row = rows[0]

    assert set(row.reference_risk_fields) == {"source_id", "linked_cluster_ids", "cross_item_split_signals"}
    assert "source_id" not in row.direct_fields
    assert "source_id" not in row.candidate_fields
    assert "passage_id" not in json.dumps(row.direct_fields, ensure_ascii=False)


def test_item_subitem_and_person_are_range_filters_not_direct_evidence_relationships() -> None:
    rows = build_staging_rows(
        [
            SourceImportRow(
                id=1,
                source_file="data/evidence_cards.jsonl",
                line_no=1,
                import_status="accepted",
                error=None,
                payload={
                    "evidence_id": "EVD-TEST-002",
                    "item": "第五项",
                    "subitem": "B",
                    "person": "刘秀",
                },
            )
        ]
    )
    row = rows[0]

    assert set(row.range_filter_fields) == {"item", "subitem", "person"}
    assert "item" not in row.direct_fields
    assert "subitem" not in row.direct_fields
    assert "person" not in row.direct_fields


def test_thematic_anchor_files_are_staging_only() -> None:
    rows = build_staging_rows(
        [
            SourceImportRow(
                id=1,
                source_file="data/thematic_anchors.jsonl",
                line_no=1,
                import_status="accepted",
                error=None,
                payload={"anchor_id": "ANCH-TEST-001", "linked_evidence_ids": ["EVD-TEST-001"]},
            )
        ]
    )

    assert rows[0].staging_only is True
    assert "linked_evidence_ids" in rows[0].reference_risk_fields
    assert "anchors_candidate" in rows[0].target_tables


def test_contract_report_contains_no_scoring_or_ranking_terms() -> None:
    text = report_as_json(build_contract_report(source_root=FIXTURE_ROOT))

    for term in BLOCKED_REPORT_TERMS:
        assert term not in text


def test_contract_report_cli_prints_json_without_connecting(monkeypatch, capsys) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in staging mapper contract tests")

    monkeypatch.setattr(socket, "socket", fail_socket)

    assert main(["--contract-report", "--source-root", str(FIXTURE_ROOT)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "contract-report"
    assert payload["rows_total"] == 4


def test_default_contract_paths_do_not_read_batches_archive_or_touch_forbidden_paths(monkeypatch) -> None:
    original_read_text = Path.read_text
    forbidden_parts = (("data", "batches"), ("archive", "data"))

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        parts = tuple(self.parts)
        for first, second in forbidden_parts:
            if first in parts and second in parts:
                raise AssertionError(f"forbidden path read: {self}")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in staging mapper contract tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = build_contract_report(source_root=ROOT)

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["files_missing"] == []


def test_staging_mapper_uses_python_driver_not_psql_or_subprocess() -> None:
    source = (ROOT / "scripts" / "platform" / "jsonl_staging_mapper.py").read_text(encoding="utf-8")

    assert "import subprocess" not in source
    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "import psycopg" in source


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
