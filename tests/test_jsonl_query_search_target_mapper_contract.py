from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.jsonl_query_search_target_mapper import (
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
        raise AssertionError("network access is forbidden in target mapper contract tests")

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
        raise AssertionError("network access is forbidden in target mapper contract tests")

    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env":
            raise AssertionError("contract report must not read .env")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(socket, "socket", fail_socket)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    report = build_contract_report(source_root=fixture_root)

    assert report["mode"] == "contract-report"
    assert report["target_tables"] == ["query_profiles", "search_tasks"]
    assert report["source_files"] == [
        "data/query_profiles.jsonl",
        "data/search_logs.jsonl",
        "data/thematic_anchors.jsonl",
    ]
    assert report["rows_by_source_file"]["data/query_profiles.jsonl"] == 1
    assert report["rows_by_source_file"]["data/search_logs.jsonl"] == 1
    assert report["candidate_rows_by_target"] == {"query_profiles": 1, "search_tasks": 1}
    assert "data/thematic_anchors.jsonl" in report["staging_only_files"]


def test_query_profiles_safe_fields_enter_target_plan(tmp_path: Path) -> None:
    report = build_contract_report(source_root=_write_fixture_root(tmp_path))
    plan = report["direct_field_plan"]["query_profiles"]

    assert plan["query_profile_id"]["target_column"] == "code"
    assert plan["profile_scope"]["target_column"] == "scope"
    assert plan["status"]["target_column"] == "status"
    blocked = {item["field"]: item for item in report["resolver_blocked_fields"]["data/query_profiles.jsonl"]}
    assert blocked["item"]["blocked_action"] == "subitem_id_write"
    assert blocked["subitem"]["blocked_action"] == "subitem_id_write"
    assert blocked["person"]["blocked_action"] == "person_id_write"
    assert blocked["object_anchors"]["blocked_action"] == "anchors_or_anchor_links_write"
    assert blocked["thematic_anchor_targets"]["blocked_action"] == "anchors_or_anchor_links_write"


def test_search_tasks_safe_fields_enter_target_plan_and_refs_are_blocked(tmp_path: Path) -> None:
    report = build_contract_report(source_root=_write_fixture_root(tmp_path))
    plan = report["direct_field_plan"]["search_tasks"]

    assert plan["search_id"]["target_column"] == "code"
    assert plan["query"]["target_column"] == "query_text"
    assert plan["status"]["target_column"] == "status"
    blocked = {item["field"]: item for item in report["resolver_blocked_fields"]["data/search_logs.jsonl"]}
    assert blocked["query_profile_id"]["blocked_action"] == "query_profile_id_fk_write_without_resolver"
    assert blocked["linked_source_ids"]["blocked_action"] == "source_fk_or_search_hits_write"
    assert blocked["linked_evidence_ids"]["blocked_action"] == "evidence_fk_or_relationship_table_write"
    assert blocked["cross_item*"]["blocked_action"] == "relationship_table_write"
    assert blocked["*_ids"]["blocked_action"] == "direct_fk_write"


def test_unresolved_reference_report_keeps_relationship_inputs_out_of_fk_writes(tmp_path: Path) -> None:
    report = build_contract_report(source_root=_write_fixture_root(tmp_path))

    query_fields = {entry["field"]: entry for entry in report["unresolved_references_by_file"]["data/query_profiles.jsonl"]}
    assert query_fields["item"]["kept_as"] == "range_filter_or_resolver_input"
    assert query_fields["subitem"]["kept_as"] == "range_filter_or_resolver_input"
    assert query_fields["person"]["kept_as"] == "range_filter_or_resolver_input"
    assert query_fields["inherits_from"]["kept_as"] == "payload_or_resolver_input"

    search_fields = {entry["field"]: entry for entry in report["unresolved_references_by_file"]["data/search_logs.jsonl"]}
    assert search_fields["query_profile_id"]["kept_as"] == "payload_or_resolver_input"
    assert search_fields["linked_source_ids"]["blocked_action"] == "direct_fk_or_relationship_table_write"
    assert search_fields["linked_evidence_ids"]["blocked_action"] == "direct_fk_or_relationship_table_write"
    assert search_fields["cross_item_split_signals"]["blocked_action"] == "direct_fk_or_relationship_table_write"


def test_contract_report_contains_no_scoring_or_ranking_terms(tmp_path: Path) -> None:
    text = report_as_json(build_contract_report(source_root=_write_fixture_root(tmp_path)))

    for term in BLOCKED_REPORT_TERMS:
        assert term not in text


def test_contract_report_cli_prints_json_without_connecting(monkeypatch, capsys, tmp_path: Path) -> None:
    fixture_root = _write_fixture_root(tmp_path)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in target mapper contract tests")

    monkeypatch.setattr(socket, "socket", fail_socket)

    assert main(["--contract-report", "--source-root", str(fixture_root)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "contract-report"
    assert payload["candidate_rows_by_target"] == {"query_profiles": 1, "search_tasks": 1}


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
        raise AssertionError("network access is forbidden in target mapper contract tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = build_contract_report(source_root=ROOT)

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["candidate_rows_by_target"]["query_profiles"] > 0
    assert report["candidate_rows_by_target"]["search_tasks"] > 0


def test_target_mapper_uses_python_driver_not_psql_subprocess_or_legacy_dsn() -> None:
    source = (ROOT / "scripts" / "platform" / "jsonl_query_search_target_mapper.py").read_text(encoding="utf-8")

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
        data_dir / "query_profiles.jsonl",
        [
            {
                "query_profile_id": "QRY-TARGET-001",
                "profile_scope": "item",
                "status": "active",
                "item": "第五项",
                "subitem": "B",
                "person": "刘秀",
                "query_terms": ["宽政", "民生"],
                "inherits_from": "QRY-BASE-001",
                "object_anchors": [{"name": "轻徭薄赋"}],
                "thematic_anchor_targets": ["民生治理"],
            }
        ],
    )
    _write_jsonl(
        data_dir / "search_logs.jsonl",
        [
            {
                "search_id": "SRCH-TARGET-001",
                "query": "刘秀 宽政 民生",
                "status": "ready",
                "query_terms": ["刘秀", "宽政"],
                "query_profile_id": "QRY-TARGET-001",
                "linked_source_ids": ["SRC-TARGET-001"],
                "linked_evidence_ids": ["EVD-TARGET-001"],
                "cross_item_split_signals": ["相邻项复核"],
            }
        ],
    )
    _write_jsonl(
        data_dir / "thematic_anchors.jsonl",
        [{"anchor_id": "ANCH-TARGET-001", "linked_evidence_ids": ["EVD-TARGET-001"]}],
    )
    return tmp_path


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
