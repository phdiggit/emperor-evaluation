from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.jsonl_import_dry_run import (
    PRIMARY_ENV_DSN,
    ResolvedDsn,
    build_contract_report,
    check_environment,
    integration_skip_reason,
    main,
    report_as_json,
    resolve_dsn,
)


FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "jsonl_import"
FORBIDDEN_PATHS = [
    ROOT / "data",
    ROOT / "archive" / "data",
    ROOT / "db" / "schema.sql",
    ROOT / "exports" / "markdown_views",
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
    ROOT / "docs" / "分项规则",
    ROOT / "docs" / "证据规则",
]
BLOCKED_REPORT_TERMS = ("score", "rank", "final_score", "leaderboard")


def test_resolve_dsn_uses_only_primary_env_and_dotenv_without_overriding_shell(tmp_path: Path) -> None:
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
        raise AssertionError("network access is forbidden in JSONL dry-run contract tests")

    monkeypatch.setattr(socket, "socket", fail_socket)
    result = check_environment(ResolvedDsn(None, "skip"), driver_available=False)

    assert result["mode"] == "check"
    assert result["dsn_present"] is False
    assert result["dsn_source"] == "skip"
    assert result["driver"] == "psycopg"
    assert result["driver_available"] is False
    assert result["will_apply"] is False


def test_apply_skip_reason_requires_primary_dsn_and_python_driver() -> None:
    assert integration_skip_reason(ResolvedDsn(None, "skip"), driver_available=True) == f"{PRIMARY_ENV_DSN} is not set"
    assert integration_skip_reason(ResolvedDsn("postgresql://example/db", f"env:{PRIMARY_ENV_DSN}"), driver_available=False) == (
        "psycopg is not installed"
    )


def test_contract_report_parses_fixture_errors_duplicates_and_missing_fields() -> None:
    report, rows = build_contract_report(source_root=FIXTURE_ROOT)

    assert report["mode"] == "contract-report"
    assert report["files_seen"] == ["data/query_profiles.jsonl"]
    assert "data/search_logs.jsonl" in report["files_missing"]
    assert report["rows_total"] == 4
    assert report["rows_valid_json"] == 3
    assert report["rows_invalid_json"] == 1
    assert report["rows_with_code"] == 2
    assert report["would_write_import_rows"] == 4
    assert report["duplicate_codes_by_file"]["data/query_profiles.jsonl"]["QRY-TEST-001"] == [1, 2]
    assert report["missing_recommended_fields_by_file"]["data/query_profiles.jsonl"]["query_profile_id"] == [3]
    assert report["reference_risk_summary"]["data/query_profiles.jsonl"] == ["linked_evidence_ids"]
    assert rows[-1].import_status == "error"
    assert rows[-1].error == "invalid JSON: Expecting ',' delimiter"


def test_contract_report_contains_no_scoring_or_ranking_terms() -> None:
    report, _rows = build_contract_report(source_root=FIXTURE_ROOT)
    text = report_as_json(report)

    for term in BLOCKED_REPORT_TERMS:
        assert term not in text


def test_contract_report_cli_prints_json_without_connecting(monkeypatch, capsys) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in JSONL dry-run contract tests")

    monkeypatch.setattr(socket, "socket", fail_socket)

    assert main(["--contract-report", "--source-root", str(FIXTURE_ROOT)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["rows_total"] == 4
    assert payload["rows_invalid_json"] == 1


def test_default_contract_paths_do_not_connect_or_touch_forbidden_paths(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in JSONL dry-run contract tests")

    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report, _rows = build_contract_report()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["files_missing"] == []
    assert report["would_write_import_rows"] > 0


def test_new_import_dry_run_uses_python_driver_not_psql_or_subprocess() -> None:
    source = (ROOT / "scripts" / "platform" / "jsonl_import_dry_run.py").read_text(encoding="utf-8")

    assert "import subprocess" not in source
    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
