from __future__ import annotations

from pathlib import Path

import pytest

from scripts.platform.core.db_env import (
    LEGACY_ENV_DSN,
    PRIMARY_ENV_DSN,
    ResolvedDsn,
    make_check_environment,
    make_integration_skip_reason,
    make_resolve_dsn,
    make_validate_isolated_schema,
    primary_env_check_report,
    resolve_database_dsn,
)
from scripts.platform.core.fingerprints import stable_json_sha256
from scripts.platform.core.redaction import redact_connection_secrets


def test_stable_json_sha256_can_omit_plan_hash_field() -> None:
    payload = {
        "mode": "execution-plan-json",
        "items": [{"id": "a", "count": 1}],
        "execution_plan_sha256": "old",
    }
    updated = {**payload, "execution_plan_sha256": "new"}

    assert stable_json_sha256(payload, omit_key="execution_plan_sha256") == stable_json_sha256(
        updated,
        omit_key="execution_plan_sha256",
    )
    assert stable_json_sha256(payload) != stable_json_sha256(updated)


def test_redact_connection_secrets_removes_uri_credentials_and_password_values() -> None:
    raw = (
        "pg=postgresql://user:uriSecret@example.local/prod?password=querySecret&sslmode=require "
        "mq=amqps://worker:mqSecret@rabbit.local/vhost "
        "http=https://token:httpSecret@example.local/path "
        "keyword password=spaceSecret next pwd=semiSecret;tail password=tailSecret"
    )

    redacted = redact_connection_secrets(raw)

    for secret in (
        "uriSecret",
        "querySecret",
        "mqSecret",
        "httpSecret",
        "spaceSecret",
        "semiSecret",
        "tailSecret",
    ):
        assert secret not in redacted
    assert "postgresql://<redacted-credentials>@example.local/prod" in redacted
    assert "amqps://<redacted-credentials>@rabbit.local/vhost" in redacted
    assert "https://<redacted-credentials>@example.local/path" in redacted
    assert "password=<redacted>&sslmode=require" in redacted
    assert "password=<redacted> next" in redacted
    assert "pwd=<redacted>;tail" in redacted
    assert redacted.endswith("password=<redacted>")


def test_resolve_database_dsn_preserves_explicit_env_dotenv_precedence() -> None:
    dotenv = {
        PRIMARY_ENV_DSN: "postgresql://dotenv-primary/db",
        LEGACY_ENV_DSN: "postgresql://dotenv-legacy/db",
    }

    assert (
        resolve_database_dsn(
            "postgresql://explicit/db",
            env={},
            env_names=(PRIMARY_ENV_DSN, LEGACY_ENV_DSN),
            env_path=Path(".env"),
            dotenv_reader=lambda _path: dotenv,
        ).source
        == "--dsn"
    )
    assert (
        resolve_database_dsn(
            env={LEGACY_ENV_DSN: "postgresql://env-legacy/db"},
            env_names=(PRIMARY_ENV_DSN, LEGACY_ENV_DSN),
            env_path=Path(".env"),
            dotenv_reader=lambda _path: dotenv,
        ).source
        == f"env:{LEGACY_ENV_DSN}"
    )
    assert (
        resolve_database_dsn(
            env={},
            env_names=(PRIMARY_ENV_DSN, LEGACY_ENV_DSN),
            env_path=Path(".env"),
            dotenv_reader=lambda _path: dotenv,
        ).source
        == f".env:{PRIMARY_ENV_DSN}"
    )


def test_primary_only_resolver_ignores_legacy_env_and_dotenv() -> None:
    resolve_dsn = make_resolve_dsn(
        env_path=Path(".env"),
        dotenv_reader=lambda _path: {LEGACY_ENV_DSN: "postgresql://legacy/db"},
    )

    assert resolve_dsn(env={LEGACY_ENV_DSN: "postgresql://legacy/db"}).source == "skip"
    assert resolve_dsn(env={PRIMARY_ENV_DSN: "postgresql://primary/db"}).source == f"env:{PRIMARY_ENV_DSN}"


def test_generated_check_and_skip_helpers_match_script_contract() -> None:
    resolve_dsn = make_resolve_dsn()
    check_environment = make_check_environment(resolve_dsn)
    integration_skip_reason = make_integration_skip_reason(
        resolve_dsn,
        missing_reason=f"{PRIMARY_ENV_DSN} is not set",
    )

    report = check_environment(ResolvedDsn(None, "skip"), driver_available=False)

    assert report["mode"] == "check"
    assert report["dsn_present"] is False
    assert report["dsn_source"] == "skip"
    assert report["driver"] == "psycopg"
    assert report["driver_available"] is False
    assert report["default_tests_require_postgres"] is False
    assert report["will_apply"] is False
    assert integration_skip_reason(ResolvedDsn(None, "skip"), driver_available=True) == (
        f"{PRIMARY_ENV_DSN} is not set"
    )
    assert integration_skip_reason(ResolvedDsn("postgresql://example/db", "env"), driver_available=False) == (
        "psycopg is not installed"
    )


def test_primary_env_check_report_does_not_expose_secret_values() -> None:
    report = primary_env_check_report(
        env={PRIMARY_ENV_DSN: "postgresql://user:secret@example.local/db"},
        driver_available=True,
        extra_fields={"will_connect": False},
    )

    assert report["dsn_present"] is True
    assert report["dsn_source"] == f"env:{PRIMARY_ENV_DSN}"
    assert report["will_connect"] is False
    assert "secret" not in repr(report)


def test_isolated_schema_validator_delegates_identifier_and_public_guards() -> None:
    def quote_identifier(value: str) -> str:
        if "-" in value:
            raise ValueError("invalid PostgreSQL identifier")
        return f'"{value}"'

    validate_isolated_schema = make_validate_isolated_schema(
        quote_identifier,
        public_schema_message="refusing public schema",
    )

    validate_isolated_schema("safe_schema")
    with pytest.raises(ValueError, match="refusing public schema"):
        validate_isolated_schema("public")
    with pytest.raises(ValueError, match="invalid PostgreSQL identifier"):
        validate_isolated_schema("bad-schema")
