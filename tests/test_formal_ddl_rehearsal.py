from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import formal_ddl_rehearsal  # noqa: E402
from scripts.platform.formal_schema_draft import (  # noqa: E402
    BLOCKED_REPORT_TERMS,
    PHASE_1_BASE_TABLES,
    PHASE_2_RELATIONSHIP_TABLES,
    PHASE_3_DOWNSTREAM_TABLES,
)


FORBIDDEN_PATHS = [
    ROOT / "data",
    ROOT / "archive" / "data",
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
    ROOT / "exports" / "markdown_views",
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
    ROOT / "docs" / "分项规则",
    ROOT / "docs" / "证据规则",
]


def test_contract_report_is_offline_and_preserves_guarded_paths(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in formal DDL rehearsal")

    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env":
            raise AssertionError(f"formal DDL rehearsal must not read: {self}")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(socket, "socket", fail_socket)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = formal_ddl_rehearsal.build_contract_report()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["mode"] == "contract-report"
    assert report["schema_default"] == "emperor_eval_formal_rehearsal"
    assert report["phase_1_tables_emitted"] == list(PHASE_1_BASE_TABLES)
    assert report["phase_2_tables_blocked"] == list(PHASE_2_RELATIONSHIP_TABLES)
    assert report["phase_3_tables_deferred"] == list(PHASE_3_DOWNSTREAM_TABLES)


def test_emit_sql_outputs_isolated_schema_sql() -> None:
    sql = formal_ddl_rehearsal.render_sql("emperor_eval_formal_rehearsal")

    assert sql.startswith(
        "CREATE SCHEMA IF NOT EXISTS emperor_eval_formal_rehearsal;\n"
        "SET search_path TO emperor_eval_formal_rehearsal, public;"
    )
    assert "public." not in sql
    assert "schema_rehearsal_meta" in sql
    assert "canonical_jsonl_remains_source_of_truth" in sql
    for marker in ["proposal_only", "isolated_rehearsal_only", "not_production_migration"]:
        assert marker in sql


def test_sql_contains_phase_1_tables_only() -> None:
    sql = formal_ddl_rehearsal.render_sql()

    for table_name in PHASE_1_BASE_TABLES:
        assert f"CREATE TABLE {table_name} (" in sql
    for table_name in PHASE_2_RELATIONSHIP_TABLES:
        assert f"CREATE TABLE {table_name} (" not in sql
    for table_name in PHASE_3_DOWNSTREAM_TABLES:
        assert f"CREATE TABLE {table_name} (" not in sql


def test_sql_contains_no_blocked_terms() -> None:
    sql = formal_ddl_rehearsal.render_sql().lower()

    for term in BLOCKED_REPORT_TERMS:
        assert term not in sql


def test_lint_sql_passes_generated_sql() -> None:
    result = formal_ddl_rehearsal.lint_sql(
        formal_ddl_rehearsal.render_sql("emperor_eval_formal_rehearsal"),
        "emperor_eval_formal_rehearsal",
    )

    assert result["mode"] == "lint-sql"
    assert result["sql_generated"] is True
    assert result["passed"] is True
    assert result["failed"] == []
    assert result["emitted_tables"] == list(PHASE_1_BASE_TABLES)
    assert result["blocked_tables"] == list(PHASE_2_RELATIONSHIP_TABLES)
    assert result["deferred_tables"] == list(PHASE_3_DOWNSTREAM_TABLES)


def test_lint_sql_fails_public_schema_write() -> None:
    sql = formal_ddl_rehearsal.render_sql() + "\nCREATE TABLE public.imports (id bigint);\n"

    result = formal_ddl_rehearsal.lint_sql(sql)

    assert result["passed"] is False
    assert "no_public_schema_writes" in result["failed"]


def test_lint_sql_fails_relationship_create_table() -> None:
    sql = formal_ddl_rehearsal.render_sql() + "\nCREATE TABLE evd_src_links (id bigint);\n"

    result = formal_ddl_rehearsal.lint_sql(sql)

    assert result["passed"] is False
    assert "relationship_tables_not_created" in result["failed"]
    assert "phase_1_tables_only" in result["failed"]


def test_report_contains_seed_contract_skeleton() -> None:
    report = formal_ddl_rehearsal.build_contract_report()

    assert report["schema_version_marker"]["production_marker"] is False
    assert report["schema_version_marker"]["table_name"] == "schema_rehearsal_meta"
    assert report["seed_contract_skeleton"]["source"] == "canonical JSONL only"
    assert report["seed_contract_skeleton"]["generated_in_this_pr"] is False
    assert report["seed_contract_skeleton"]["secret_free"] is True


def test_cli_modes_print_json_or_sql(capsys) -> None:
    assert formal_ddl_rehearsal.main(["--contract-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "contract-report"

    assert formal_ddl_rehearsal.main(["--emit-sql", "--schema", "emperor_eval_formal_rehearsal"]) == 0
    sql = capsys.readouterr().out
    assert "CREATE SCHEMA IF NOT EXISTS emperor_eval_formal_rehearsal;" in sql

    assert formal_ddl_rehearsal.main(["--lint-sql", "--schema", "emperor_eval_formal_rehearsal"]) == 0
    lint_report = json.loads(capsys.readouterr().out)
    assert lint_report["passed"] is True


def test_source_is_static_rehearsal_only() -> None:
    source = (ROOT / "scripts" / "platform" / "formal_ddl_rehearsal.py").read_text(encoding="utf-8")

    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "EMPEROR_EVAL_PG_DSN" not in source
    assert "psycopg" not in source
    assert "os.environ" not in source


def test_guard_paths_use_utf8_chinese_names() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    protected_paths = {path.as_posix() for path in FORBIDDEN_PATHS}

    assert any(path.endswith("docs/皇帝综合评价体系评分标准.md") for path in protected_paths)
    assert any(path.endswith("docs/分项规则") for path in protected_paths)
    assert any(path.endswith("docs/证据规则") for path in protected_paths)
    for mojibake in ["\u9428\u56e7\u7b23", "\u934a\u55d8\u300d", "\u7487\u4f7a\u5d41"]:
        assert mojibake not in source


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
