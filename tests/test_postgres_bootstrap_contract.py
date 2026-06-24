from __future__ import annotations

import re
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.env_loader import load_dotenv
from scripts.platform.postgres_bootstrap import (
    LEGACY_ENV_DSN,
    PRIMARY_ENV_DSN,
    ResolvedDsn,
    check_environment,
    integration_skip_reason,
    render_bootstrap_sql,
    resolve_dsn,
)


FORBIDDEN_PATHS = [
    ROOT / "data",
    ROOT / "archive" / "data",
    ROOT / "db" / "schema.sql",
    ROOT / "exports" / "markdown_views",
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
    ROOT / "docs" / "分项规则",
    ROOT / "docs" / "证据规则",
]


def test_env_example_documents_primary_and_legacy_dsn_without_real_secret() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert f"{PRIMARY_ENV_DSN}=postgresql://USER:PASSWORD@HOST:5432/emperor_eval_dev" in text
    assert f"{LEGACY_ENV_DSN}=postgresql://USER:PASSWORD@HOST:5432/emperor_eval_dev" in text
    assert not re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text)
    assert "postgresql://postgres:" not in text


def test_gitignore_protects_local_env_but_allows_example() -> None:
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert ".env" in text
    assert ".env.*" in text
    assert "!.env.example" in text


def test_load_dotenv_does_not_override_shell_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"{PRIMARY_ENV_DSN}=postgresql://from-dotenv-primary/db",
                f"{LEGACY_ENV_DSN}='postgresql://from-dotenv-legacy/db'",
                "EXISTING_KEY=from-dotenv",
            ]
        ),
        encoding="utf-8",
    )
    environ = {
        PRIMARY_ENV_DSN: "postgresql://from-shell-primary/db",
        "EXISTING_KEY": "from-shell",
    }

    load_dotenv(env_file, environ=environ)

    assert environ[PRIMARY_ENV_DSN] == "postgresql://from-shell-primary/db"
    assert environ[LEGACY_ENV_DSN] == "postgresql://from-dotenv-legacy/db"
    assert environ["EXISTING_KEY"] == "from-shell"


def test_resolve_dsn_precedence(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"{PRIMARY_ENV_DSN}=postgresql://dotenv-primary/db",
                f"{LEGACY_ENV_DSN}=postgresql://dotenv-legacy/db",
            ]
        ),
        encoding="utf-8",
    )

    assert resolve_dsn("postgresql://explicit/db", env={}, env_path=env_file).source == "--dsn"
    assert resolve_dsn(env={PRIMARY_ENV_DSN: "postgresql://shell-primary/db"}, env_path=env_file).source == (
        f"env:{PRIMARY_ENV_DSN}"
    )
    assert resolve_dsn(env={LEGACY_ENV_DSN: "postgresql://shell-legacy/db"}, env_path=env_file).source == (
        f"env:{LEGACY_ENV_DSN}"
    )
    assert resolve_dsn(env={}, env_path=env_file).source == f".env:{PRIMARY_ENV_DSN}"
    env_file.write_text(f"{LEGACY_ENV_DSN}=postgresql://dotenv-legacy/db\n", encoding="utf-8")
    assert resolve_dsn(env={}, env_path=env_file).source == f".env:{LEGACY_ENV_DSN}"
    assert resolve_dsn(env={}, env_path=tmp_path / "missing.env").source == "skip"


def test_check_without_dsn_or_driver_is_non_failing_skip() -> None:
    result = check_environment(ResolvedDsn(None, "skip"), driver_available=False)

    assert result["mode"] == "check"
    assert result["dsn_present"] is False
    assert result["dsn_source"] == "skip"
    assert result["driver"] == "psycopg"
    assert result["driver_available"] is False
    assert result["will_apply"] is False


def test_apply_skip_reason_requires_dsn_and_python_driver() -> None:
    assert integration_skip_reason(ResolvedDsn(None, "skip"), driver_available=True) == (
        f"{PRIMARY_ENV_DSN} or {LEGACY_ENV_DSN} is not set"
    )
    assert integration_skip_reason(ResolvedDsn("postgresql://example/db", "--dsn"), driver_available=False) == (
        "psycopg is not installed"
    )


def test_sql_wrapper_contains_isolated_schema_and_init_contract() -> None:
    sql = render_bootstrap_sql("emperor_eval_bootstrap_check")

    assert 'CREATE SCHEMA IF NOT EXISTS "emperor_eval_bootstrap_check";' in sql
    assert 'SET search_path TO "emperor_eval_bootstrap_check", public;' in sql
    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in sql
    assert "CREATE TABLE persons" in sql
    assert "CREATE TABLE passages" in sql
    assert "CREATE INDEX passage_search_gin ON passages USING GIN (search_vec)" in sql
    assert "CREATE INDEX passage_norm_trgm ON passages USING GIN (norm_text gin_trgm_ops)" in sql
    assert "CONSTRAINT job_idem_uk UNIQUE (idem_key)" in sql
    assert "CREATE INDEX outbox_ready_idx ON outbox" in sql
    assert "db/schema.sql" not in sql


def test_sql_only_and_contract_paths_do_not_connect_or_touch_forbidden_paths(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in bootstrap contract tests")

    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    render_bootstrap_sql("emperor_eval_bootstrap_check")
    check_environment(ResolvedDsn(None, "skip"), driver_available=False)

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before


def test_bootstrap_uses_python_driver_not_psql_subprocess() -> None:
    source = (ROOT / "scripts" / "platform" / "postgres_bootstrap.py").read_text(encoding="utf-8")

    assert "import subprocess" not in source
    assert "import shutil" not in source
    assert "subprocess.run" not in source
    assert "shutil.which" not in source
    assert '"psql"' not in source
    assert "import psycopg" in source


def test_schema_identifier_rejects_unsafe_names() -> None:
    try:
        render_bootstrap_sql("bad;drop")
    except ValueError as exc:
        assert "invalid PostgreSQL identifier" in str(exc)
    else:
        raise AssertionError("unsafe schema name should be rejected")


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
