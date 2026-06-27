from __future__ import annotations

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
