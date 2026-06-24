from __future__ import annotations

import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.source_ingest.postgres_search_benchmark import (
    BENCH_SQL_PATH,
    DEFAULT_CASES,
    ENV_DSN,
    build_contract_report,
    integration_skip_reason,
    render_benchmark_sql,
    render_explain_sql,
)
from scripts.source_ingest.search_benchmark import build_token_text


FORBIDDEN_OUTPUT_KEYS = {
    "score",
    "rank",
    "final_score",
    "leaderboard",
}


def test_integration_skip_when_dsn_is_not_set() -> None:
    assert integration_skip_reason({}, psql_path="psql") == f"{ENV_DSN} is not set"


def test_integration_skip_when_psql_is_missing() -> None:
    assert integration_skip_reason({ENV_DSN: "postgresql://example/db"}, psql_path="") == (
        "psql is not installed or not on PATH"
    )


def test_runner_does_not_access_network_for_contract_report(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in postgres search benchmark contract tests")

    monkeypatch.setattr(socket, "socket", fail_socket)

    report = build_contract_report()

    assert report["default_tests_require_postgres"] is False
    assert report["opt_in_env_var"] == ENV_DSN


def test_runner_does_not_modify_forbidden_repo_paths() -> None:
    forbidden_paths = [
        ROOT / "data",
        ROOT / "archive" / "data",
        ROOT / "db" / "schema.sql",
        ROOT / "exports" / "markdown_views",
    ]
    before = {path: _mtime(path) for path in forbidden_paths}

    render_benchmark_sql()
    build_contract_report()

    after = {path: _mtime(path) for path in forbidden_paths}
    assert after == before


def test_generated_sql_contains_postgres_search_contract() -> None:
    sql = render_benchmark_sql()
    explain_sql = render_explain_sql()
    static_sql = BENCH_SQL_PATH.read_text(encoding="utf-8")

    for required in [
        "CREATE EXTENSION IF NOT EXISTS pg_trgm",
        "CREATE TEMP TABLE bench_passages",
        "tsvector GENERATED ALWAYS",
        "USING gin (search_vec)",
        "gin_trgm_ops",
        "plainto_tsquery('simple', q.normalized_query)",
        "norm_text LIKE '%' || q.normalized_query || '%'",
        "norm_text % q.normalized_query",
    ]:
        assert required in sql

    assert "EXPLAIN (FORMAT JSON)" in explain_sql
    assert "CREATE TEMP TABLE bench_plans" not in sql
    assert "CREATE TEMP TABLE bench_passages" in static_sql
    assert "CREATE TABLE passages" not in sql
    assert "CREATE TABLE search_hits" not in sql


def test_generated_sql_inserts_fixture_values_without_touching_init_schema() -> None:
    sql = render_benchmark_sql()

    assert "INSERT INTO bench_passages" in sql
    assert "bench-shiji-008-p0001" in sql
    assert "高祖，沛豐邑中陽里人。［1］" in sql
    assert "INSERT INTO bench_queries" in sql
    assert "single_char_pei" in sql
    assert "001_init.sql" not in sql


def test_contract_report_exposes_strategy_matches_and_risk_sets() -> None:
    report = build_contract_report()
    cases = {case["case_id"]: case for case in report["cases"]}

    assert report["strategies"] == ["tsvector", "like", "trgm"]
    assert set(cases["alias_liubang"]["missed_by_strategy"]) == {"tsvector", "like", "trgm"}
    assert set(cases["alias_liubang"]["unexpected_by_strategy"]) == {"tsvector", "like", "trgm"}
    assert cases["alias_liubang"]["matched_by_tsvector"] == ["bench-shiji-008-p0001"]
    assert cases["alias_liubang"]["matched_by_like"] == []
    assert cases["alias_liubang"]["missed_by_strategy"]["like"] == ["bench-shiji-008-p0001"]


def test_report_contains_no_scoring_or_ranking_fields() -> None:
    assert not _contains_forbidden_key(build_contract_report())


def test_default_cases_cover_required_query_categories() -> None:
    categories = {case.category for case in DEFAULT_CASES}

    assert {
        "single_char",
        "two_char",
        "long_term",
        "alias",
        "variant",
        "noise",
        "false_positive_probe",
    } <= categories


def test_benchmark_does_not_change_parser_default_token_text_behavior() -> None:
    assert build_token_text("魏徵") == "魏 徵 魏徵"


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns


def _contains_forbidden_key(value: object) -> bool:
    if isinstance(value, dict):
        return any(key in FORBIDDEN_OUTPUT_KEYS or _contains_forbidden_key(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden_key(child) for child in value)
    return False
