from __future__ import annotations

from collections.abc import Iterable


def first_blocking_reason(checks: Iterable[tuple[bool, str]]) -> str | None:
    for passed, reason in checks:
        if not passed:
            return reason
    return None
