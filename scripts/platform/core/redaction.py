from __future__ import annotations

import re


SECRET_TOKENS = ("postgres://", "postgresql://", "password=", "pwd=")


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
