from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_consumer import target_scope_cte  # noqa: E402
from scripts.dev.retrieval_v2_factorization_worklists import DEFAULT_FORMULA_CODE, DEFAULT_ITEM_CODE, DEFAULT_RULE_CODE  # noqa: E402
from scripts.dev.retrieval_v2_import_plan import ImportPlanError  # noqa: E402
from scripts.dev.retrieval_v2_intake_manifest import text  # noqa: E402

DEFAULT_DSN_ENV = "EMPEROR_EVAL_RETRIEVAL_V2_DSN"
SCOPES = ("active-targets", "accepted-packs")
DEFAULT_TOP_MATERIALS_PER_TARGET = 8

class RetrievalV2DiagnosticsError(ImportPlanError):
    pass


def fetch_scalar(cur: Any, sql: str, params: Sequence[Any]) -> int:
    cur.execute(sql, tuple(params))
    row = cur.fetchone()
    if row is None:
        return 0
    if isinstance(row, Mapping):
        return int(row.get("n") or row.get("rows") or 0)
    return int(row[0] or 0)


def fetch_rows(cur: Any, sql: str, params: Sequence[Any]) -> list[dict[str, Any]]:
    cur.execute(sql, tuple(params))
    return [dict(row) for row in cur.fetchall()]


def short_text(value: Any, *, max_chars: int = 120) -> str:
    value_text = " ".join(text(value).split())
    if len(value_text) <= max_chars:
        return value_text
    return value_text[: max_chars - 1].rstrip() + "…"


def decimal_text(value: Any) -> str:
    return text(value) if value is not None else "0.000"


def json_object(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def json_array(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def numeric_sort_value(value: Any) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def scoped_with(scope: str) -> str:
    return f"with {target_scope_cte(scope)}"


def base_params(item_code: str) -> tuple[str, str]:
    return (item_code, item_code)


def rule_params(item_code: str, rule_code: str, formula_code: str) -> tuple[str, str, str, str, str]:
    return (item_code, item_code, rule_code, rule_code, formula_code)


def check_entry(
    code: str,
    *,
    count: int,
    severity: str,
    owner: str,
    description: str,
    next_command: str = "",
    examples: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "code": code,
        "status": "ok" if int(count) == 0 else severity,
        "severity": severity,
        "owner": owner,
        "count": int(count),
        "description": description,
        "next_command": next_command,
        "examples": [dict(row) for row in examples],
    }

