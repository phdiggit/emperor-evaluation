from __future__ import annotations

import json
import re
import socket
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import schema_changing_formal_schema_update as update  # noqa: E402


SCHEMA_PATHS = [
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
]
REQUIRED_FLAGS = {
    "schema_changing_pr": True,
    "schema_files_modified": True,
    "production_migration_approved": True,
    "schema_change_user_approval_recorded": True,
    "sql_executed": False,
    "production_db_connected": False,
    "production_dsn_read": False,
    "production_seed_executed": False,
    "live_apply_executed": False,
    "ready_for_schema_change_pr": True,
    "ready_for_production_migration": False,
    "future_live_apply_pr_required": True,
    "future_seed_apply_pr_required": True,
}
FORBIDDEN_SOURCE_TOKENS = [
    "subprocess",
    "psycopg",
    "asyncpg",
    "sqlalchemy",
    "os.environ",
    "PG_SEARCH_BENCH_DSN",
    "EMPEROR_EVAL_PG_DSN",
]
FORBIDDEN_SCHEMA_TOKENS = [
    "postgres://",
    "postgresql://",
    "password=",
    "connection string",
    "credential value",
    "INSERT INTO",
    "COPY ",
    "LOAD DATA",
    "psql",
    "subprocess",
    "apply-ready live command",
    "score",
    "rank",
    "final_score",
    "leaderboard",
]


def test_render_schema_change_json_has_required_flags_and_approval_source() -> None:
    report = update.render_schema_change_json()

    assert report["pr_number"] == 281
    assert report["title"] == "platform: apply guarded formal schema files"
    for key, expected in REQUIRED_FLAGS.items():
        assert report[key] is expected
    assert "随时可以开启数据迁移" in report["approval_source"]
    assert report["ready_for_production_migration"] is False


def test_cli_modes_print_expected_json(monkeypatch) -> None:
    _guard_network(monkeypatch)
    for args, mode in [
        (["--contract-report"], "contract-report"),
        (["--schema-change-report"], "schema-change-report"),
        (["--render-schema-change-json"], "render-schema-change-json"),
        (["--lint-schema-change-report"], "lint-schema-change-report"),
        (["--adr-check"], "adr-check"),
    ]:
        buffer = StringIO()
        with redirect_stdout(buffer):
            assert update.main(args) == 0
        assert json.loads(buffer.getvalue())["mode"] == mode


def test_schema_files_exist_are_utf8_and_are_same_formal_schema() -> None:
    texts = []
    for path in SCHEMA_PATHS:
        assert path.is_file()
        texts.append(path.read_text(encoding="utf-8"))

    assert texts[0] == texts[1]
    assert set(update.created_tables(texts[0])) == set(update.created_tables(texts[1]))
    for table in update.EXPECTED_SCHEMA_TABLES:
        assert f"CREATE TABLE {table} (" in texts[0]
    assert "CREATE TABLE anchors (" in texts[0]
    assert "anchor_type_review_idx" in texts[0]


def test_schema_files_contain_no_connection_seed_shell_or_business_result_terms() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in SCHEMA_PATHS)
    lowered = combined.lower()

    for token in FORBIDDEN_SCHEMA_TOKENS:
        assert token.lower() not in lowered


def test_schema_file_fingerprints_are_hash_line_count_only() -> None:
    fingerprints = update.schema_file_fingerprints()

    assert [item["path"] for item in fingerprints] == ["db/schema.sql", "db/postgres/001_init.sql"]
    for item in fingerprints:
        assert set(item) == {"path", "sha256", "line_count"}
        assert re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
        assert isinstance(item["line_count"], int)
        assert item["line_count"] > 0


def test_schema_change_report_declares_schema_only_not_live_apply() -> None:
    report = update.build_schema_change_report()

    assert report["schema_changing_pr"] is True
    assert report["schema_files_modified"] is True
    assert report["sql_executed"] is False
    assert report["production_db_connected"] is False
    assert report["production_seed_executed"] is False
    assert report["live_apply_executed"] is False
    assert report["ready_for_production_migration"] is False
    assert report["blocking_failures"] == []


def test_lint_fails_for_required_flag_drift() -> None:
    for key, expected in REQUIRED_FLAGS.items():
        report = update.render_schema_change_json()
        report[key] = not expected
        lint = update.lint_schema_change_report(report)
        assert lint["passed"] is False
        assert any(key in failed for failed in lint["failed"])


def test_lint_fails_for_injected_blocking_values(monkeypatch, tmp_path: Path) -> None:
    base = update.render_schema_change_json()
    injected_text = "\n".join(
        [
            "CREATE TABLE demo (id bigint);",
            "INSERT INTO demo VALUES (1);",
            "postgresql://example",
            "apply-ready live command",
            "score",
        ]
    )
    left = tmp_path / "schema.sql"
    right = tmp_path / "001_init.sql"
    left.write_text(injected_text, encoding="utf-8")
    right.write_text(injected_text, encoding="utf-8")

    monkeypatch.setattr(update, "SCHEMA_PATHS", (left, right))
    lint = update.lint_schema_change_report(base)

    assert lint["passed"] is False
    assert "no_connection_material" in lint["failed"]
    assert "no_seed_or_data_load" in lint["failed"]
    assert "no_shell_or_live_apply" in lint["failed"]
    assert "no_blocked_business_terms" in lint["failed"]


def test_adr_file_exists_and_check_passes() -> None:
    path = ROOT / "docs" / "adr" / "ADR-schema-changing-formal-schema-update.md"

    assert path.is_file()
    check = update.build_adr_check(path)

    assert check["passed"] is True
    assert check["failed"] == []
    assert update.status_value(path.read_text(encoding="utf-8")) == "Proposed / Schema-changing formal schema file update"


def test_adr_check_fails_for_live_apply_or_production_ready_claim(tmp_path: Path) -> None:
    adr = tmp_path / "ADR-schema-changing-formal-schema-update.md"
    base = (ROOT / "docs" / "adr" / "ADR-schema-changing-formal-schema-update.md").read_text(encoding="utf-8")
    for injected in ["sql_executed=true", "production_db_connected=true", "ready_for_production_migration=true"]:
        adr.write_text(base + f"\n\n{injected}\n", encoding="utf-8")
        check = update.build_adr_check(adr)
        assert check["passed"] is False
        assert "no_live_apply_or_production_ready_claim" in check["failed"]


def test_source_inspection_forbidden_terms_are_absent() -> None:
    source = (ROOT / "scripts" / "platform" / "schema_changing_formal_schema_update.py").read_text(encoding="utf-8")

    for forbidden in FORBIDDEN_SOURCE_TOKENS:
        assert forbidden not in source
    assert "subprocess.run" not in source
    assert "score" not in source
    assert "rank" not in source


def _guard_network(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in schema-changing formal schema update")

    monkeypatch.setattr(socket, "socket", fail_socket)
