from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.jsonl_anchors_target_mapper import (
    PRIMARY_ENV_DSN,
    ResolvedDsn,
    build_contract_report,
    check_environment,
    integration_skip_reason,
    main,
    report_as_json,
    resolve_dsn,
)
from tests.test_anchors_resolver_contract import BLOCKED_REPORT_TERMS, FORBIDDEN_PATHS, mtime, write_fixture_root


def test_resolve_dsn_uses_only_primary_environment_value() -> None:
    assert resolve_dsn(env={PRIMARY_ENV_DSN: "postgresql://primary/db"}).source == f"env:{PRIMARY_ENV_DSN}"
    assert resolve_dsn(env={}).source == "skip"
    assert resolve_dsn(env={"PG_SEARCH_BENCH_DSN": "postgresql://legacy/db"}).source == "skip"


def test_check_without_dsn_or_driver_is_non_failing_and_does_not_connect(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in anchors target mapper contract tests")

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
    fixture_root = write_fixture_root(tmp_path)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in anchors target mapper contract tests")

    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env":
            raise AssertionError("contract report must not read .env")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(socket, "socket", fail_socket)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    report = build_contract_report(source_root=fixture_root)

    assert report["mode"] == "contract-report"
    assert report["target_tables"] == ["anchors", "anchor_links_candidates"]
    assert report["rows_by_source_file"] == {
        "data/evidence_cards.jsonl": 1,
        "data/evidence_clusters.jsonl": 1,
        "data/query_profiles.jsonl": 1,
        "data/thematic_anchor_events.jsonl": 1,
        "data/thematic_anchor_mechanisms.jsonl": 1,
        "data/thematic_anchor_objects.jsonl": 1,
        "data/thematic_anchors.jsonl": 1,
    }
    assert report["candidate_rows_by_target"] == {"anchors": 4, "anchor_links_candidates": 7}


def test_contract_report_contains_relaxed_target_plans(tmp_path: Path) -> None:
    report = build_contract_report(source_root=write_fixture_root(tmp_path))

    assert report["direct_field_plan"]["anchors"]["code"] == "anchor_code_candidate_or_diagnostic_key"
    assert report["direct_field_plan"]["anchor_links_candidates"]["relationship_proven"] is False
    assert report["anchor_link_candidate_plan"]["formal_relationship_table"] is False
    assert report["anchor_link_candidate_plan"]["writes_anchor_links"] is False
    assert report["anchor_link_candidate_plan"]["resolver_status_allowed"] == [
        "unresolved_candidate",
        "manual_review_required",
        "blocked_pending_schema",
    ]


def test_report_never_targets_forbidden_business_tables(tmp_path: Path) -> None:
    report = build_contract_report(source_root=write_fixture_root(tmp_path))
    text = report_as_json(report)

    for table in (
        "anchor_links",
        "evd_src_links",
        "cluster_evd",
        "evd_cards",
        "clusters",
        "src_docs",
        "passages",
        "query_profiles",
        "search_tasks",
        "adjudications",
        "score_records",
        "score_releases",
    ):
        assert table not in report["target_tables"]
    assert '"target_table": "anchor_links"' in text
    assert '"target_table": "anchor_links_candidates"' in text


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
        raise AssertionError("network access is forbidden in anchors target mapper contract tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: mtime(path) for path in FORBIDDEN_PATHS}

    report = build_contract_report(source_root=ROOT)

    after = {path: mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert set(report["target_tables"]) == {"anchors", "anchor_links_candidates"}


def test_contract_report_contains_no_blocked_report_terms(tmp_path: Path) -> None:
    text = report_as_json(build_contract_report(source_root=write_fixture_root(tmp_path))).lower()

    for term in BLOCKED_REPORT_TERMS:
        assert term not in text


def test_contract_report_cli_prints_json_without_connecting(monkeypatch, capsys, tmp_path: Path) -> None:
    fixture_root = write_fixture_root(tmp_path)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in anchors target mapper contract tests")

    monkeypatch.setattr(socket, "socket", fail_socket)

    assert main(["--contract-report", "--source-root", str(fixture_root)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "contract-report"
    assert payload["candidate_rows_by_target"] == {"anchors": 4, "anchor_links_candidates": 7}


def test_target_mapper_uses_python_driver_not_psql_subprocess_or_legacy_dsn() -> None:
    source = (ROOT / "scripts" / "platform" / "jsonl_anchors_target_mapper.py").read_text(encoding="utf-8")

    assert "import subprocess" not in source
    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "scripts.platform.core.jsonl_target_db" in source
    assert "run_with_target_schema_cursor" in source
    assert f'"{PRIMARY_ENV_DSN}"' in source
