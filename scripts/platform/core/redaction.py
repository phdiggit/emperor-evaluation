from __future__ import annotations

import re


SECRET_TOKENS = ("postgres://", "postgresql://", "password=", "pwd=")
DEFAULT_CREDENTIAL_SCHEMES = ("postgres", "postgresql", "amqp", "amqps", "http", "https")


def contains_secret_material(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in SECRET_TOKENS)


def redact_text(text: str, dsn: str | None = None) -> str:
    redacted = text
    if dsn:
        redacted = redacted.replace(dsn, "<redacted-dsn>")
    redacted = re.sub(r"postgres(?:ql)?://\S+", "<redacted-dsn>", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"(password|pwd)=([^\s]+)", r"\1=<redacted>", redacted, flags=re.IGNORECASE)
    return redacted


def redact_connection_secrets(
    text: str,
    *,
    schemes: tuple[str, ...] = DEFAULT_CREDENTIAL_SCHEMES,
) -> str:
    redacted = text
    for scheme in schemes:
        prefix = re.escape(f"{scheme}://")
        redacted = re.sub(
            rf"({prefix})([^@\s/]+@)",
            rf"\1<redacted-credentials>@",
            redacted,
            flags=re.IGNORECASE,
        )
    return re.sub(r"(?i)((?:password|pwd)=)[^&;\s]*", r"\1<redacted>", redacted)
