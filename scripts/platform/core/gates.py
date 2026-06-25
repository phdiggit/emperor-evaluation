from __future__ import annotations

from collections.abc import Callable, Iterable


GateCheck = bool | Callable[[], bool]


def first_blocking_reason(checks: Iterable[tuple[GateCheck, str]]) -> str | None:
    for check, reason in checks:
        passed = check() if callable(check) else check
        if not passed:
            return reason
    return None
