from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.jsonl_evidence_clusters_resolver import (
    PRIMARY_ENV_DSN,
    ResolvedDsn,
    build_contract_report,
    check_environment,
    integration_skip_reason,
    main,
    report_as_json,
    resolve_dsn,
)


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


def test_resolve_dsn_uses_only_primary_environment_value() -> None:
    assert resolve_dsn(env={PRIMARY_ENV_DSN: "postgresql://primary/db"}).source == f"env:{PRIMARY_ENV_DSN}"
    assert resolve_dsn(env={}).source == "skip"
    assert resolve_dsn(env={"PG_SEARCH_BENCH_DSN": "postgresql://legacy/db"}).source == "skip"


def test_check_without_dsn_or_driver_is_non_failing_and_does_not_connect(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in evidence cluster resolver contract tests")

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


def test_contract_report_is_offline_and_has_required_shape(monkeypatch, tmp_path: Path) -> None:
    fixture_root = _write_fixture_root(tmp_path)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in evidence cluster resolver contract tests")

    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env":
            raise AssertionError("contract report must not read .env")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(socket, "socket", fail_socket)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    report = build_contract_report(source_root=fixture_root)

    assert report["mode"] == "contract-report"
    assert report["target_tables"] == ["clusters", "cluster_evd_candidates"]
    assert report["source_files"] == ["data/evidence_clusters.jsonl"]
    assert report["rows_by_source_file"]["data/evidence_clusters.jsonl"] == 2
    assert report["candidate_rows_by_target"] == {"clusters": 2, "cluster_evd_candidates": 4}
    assert report["linked_evidence_plan"]["blocked_action"] == "cluster_evd_write"


def test_default_contract_paths_do_not_read_batches_archive_env_or_touch_forbidden_paths(monkeypatch) -> None:
    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        parts = tuple(self.parts)
        if "batches" in parts or ("archive" in parts and "data" in parts):
            raise AssertionError(f"forbidden path read: {self}")
        if self.name == ".env":
            raise AssertionError("contract report must not read .env")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in evidence cluster resolver contract tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = build_contract_report(source_root=ROOT)

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["source_files"] == ["data/evidence_clusters.jsonl"]
    assert report["candidate_rows_by_target"]["clusters"] > 0
    assert report["candidate_rows_by_target"]["cluster_evd_candidates"] > 0


def test_cluster_id_enters_clusters_code_plan(tmp_path: Path) -> None:
    report = build_contract_report(source_root=_write_fixture_root(tmp_path))

    plan = report["direct_field_plan"]["cluster_id"]
    assert plan["target_column"] == "clusters.code"
    assert plan["present"] is True


def test_core_cluster_fields_enter_relaxed_cluster_plan(tmp_path: Path) -> None:
    report = build_contract_report(source_root=_write_fixture_root(tmp_path))

    assert report["direct_field_plan"]["summary"]["target_column"] == "clusters.summary"
    assert report["direct_field_plan"]["status"]["target_column"] == "clusters.status candidate"
    assert report["direct_field_plan"]["cluster_type"]["target_column"] == "clusters.cluster_type candidate"
    assert report["direct_field_plan"]["candidate_strength"]["target_column"] == "clusters.candidate_strength candidate"
    assert report["direct_field_plan"]["polarity"]["target_column"] == "clusters.polarity candidate"


def test_linked_evidence_ids_do_not_write_formal_cluster_evd(tmp_path: Path) -> None:
    report = build_contract_report(source_root=_write_fixture_root(tmp_path))

    assert report["linked_evidence_plan"]["allowed_action"] == "unresolved_cluster_evd_candidate_report"
    blocked = {item["target_table"]: item for item in report["blocked_relationship_writes"]}
    assert blocked["cluster_evd"]["line_numbers"] == [1, 2]
    assert report["cluster_evd_candidate_plan"]["formal_relationship_table"] is False
    assert report["cluster_evd_candidate_plan"]["writes_cluster_evd"] is False


def test_linked_evidence_ids_enter_unresolved_candidate_report(tmp_path: Path) -> None:
    report = build_contract_report(source_root=_write_fixture_root(tmp_path))

    unresolved = report["unresolved_references_by_file"]["data/evidence_clusters.jsonl"][0]
    assert unresolved["field"] == "linked_evidence_ids"
    assert unresolved["candidate_count"] == 4
    assert unresolved["blocked_action"] == "cluster_evd_write"
    assert report["cluster_evd_candidate_plan"]["resolver_status_allowed"] == [
        "unresolved_candidate",
        "manual_review_required",
    ]


def test_adjudication_and_diagnostic_fields_are_payload_only(tmp_path: Path) -> None:
    report = build_contract_report(source_root=_write_fixture_root(tmp_path))

    assert report["payload_field_plan"]["adjudication_status"]["target_column"] == "clusters.payload review_state_only"
    assert report["payload_field_plan"]["five_axis_assessment"]["target_column"] == "clusters.payload"
    assert report["payload_field_plan"]["upper_probe"]["target_column"] == "clusters.payload diagnostic_only"
    blocked_fields = {item["field"]: item for item in report["resolver_blocked_fields"]["data/evidence_clusters.jsonl"]}
    assert blocked_fields["adjudication_status"]["blocked_action"] == "downstream_business_conclusion_write"


def test_duplicate_link_candidates_require_manual_review(tmp_path: Path) -> None:
    report = build_contract_report(source_root=_write_fixture_root(tmp_path))

    assert report["linked_evidence_plan"]["manual_review_required"] is True
    assert report["linked_evidence_plan"]["duplicate_link_candidates"] == [
        {
            "cluster_code": "ADJ-CLUSTER-002",
            "evidence_code": "EVD-CLUSTER-003",
            "source_file": "data/evidence_clusters.jsonl",
            "line_no": 2,
        }
    ]


def test_contract_report_contains_no_blocked_report_terms(tmp_path: Path) -> None:
    text = report_as_json(build_contract_report(source_root=_write_fixture_root(tmp_path))).lower()

    for term in BLOCKED_REPORT_TERMS:
        assert term not in text


def test_contract_report_cli_prints_json_without_connecting(monkeypatch, capsys, tmp_path: Path) -> None:
    fixture_root = _write_fixture_root(tmp_path)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in evidence cluster resolver contract tests")

    monkeypatch.setattr(socket, "socket", fail_socket)

    assert main(["--contract-report", "--source-root", str(fixture_root)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "contract-report"
    assert payload["candidate_rows_by_target"] == {"clusters": 2, "cluster_evd_candidates": 4}


def test_resolver_uses_python_driver_not_psql_subprocess_or_legacy_dsn() -> None:
    source = (ROOT / "scripts" / "platform" / "jsonl_evidence_clusters_resolver.py").read_text(encoding="utf-8")

    assert "import subprocess" not in source
    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "scripts.platform.core.jsonl_target_db" in source
    assert "make_insert_target_rows" in source


def _write_fixture_root(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_jsonl(
        data_dir / "evidence_clusters.jsonl",
        [
            {
                "cluster_id": "ADJ-CLUSTER-001",
                "summary": "cluster summary",
                "status": "batch_draft",
                "cluster_type": "talent_ecosystem",
                "candidate_strength": 3,
                "polarity": "positive",
                "linked_evidence_ids": ["EVD-CLUSTER-001", "EVD-CLUSTER-002"],
                "adjudication_status": "source_verified_pending_human_adjudication",
                "five_axis_assessment": {"directness": "high"},
                "upper_probe": "diagnostic_only",
                "cross_item_split": "manual review note",
                "note": "payload note",
            },
            {
                "cluster_id": "ADJ-CLUSTER-002",
                "summary": "cluster summary two",
                "status": "batch_draft",
                "cluster_type": "talent_risk",
                "candidate_strength": 2,
                "polarity": "negative",
                "linked_evidence_ids": ["EVD-CLUSTER-003", "EVD-CLUSTER-003"],
                "adjudication_status": "source_verified_pending_human_adjudication",
                "five_axis_assessment": {"directness": "medium"},
                "upper_probe": "diagnostic_only",
                "notes": "payload notes",
            },
        ],
    )
    _write_jsonl(data_dir / "evidence_cards.jsonl", [{"evidence_id": "EVD-IGNORED-001"}])
    return tmp_path


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
