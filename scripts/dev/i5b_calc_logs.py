from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


class I5BCalcLogError(ValueError):
    pass


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise I5BCalcLogError(f"{path}:{line_number}: expected object")
            rows.append(row)
    return rows


def _filter(values: Iterable[str] | None) -> set[str]:
    return {value for value in values or () if value}


def latest_cluster_log_rows(
    path: Path,
    *,
    formula_code: str,
    emperors: Iterable[str] | None = None,
    rule_codes: Iterable[str] | None = None,
    require_calc_detail: bool = False,
) -> dict[tuple[str, str], dict[str, Any]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    emperor_filter = _filter(emperors)
    rule_filter = _filter(rule_codes)
    for row in read_jsonl(path):
        if row.get("formula_code") != formula_code:
            continue
        emperor = row.get("emperor")
        rule_code = row.get("rule_code")
        if not isinstance(emperor, str) or not isinstance(rule_code, str):
            continue
        if emperor_filter and emperor not in emperor_filter:
            continue
        if rule_filter and rule_code not in rule_filter:
            continue
        if require_calc_detail and not isinstance(row.get("calc_detail"), dict):
            continue
        latest[(emperor, rule_code)] = row
    return latest


def latest_item_result_log_rows(
    path: Path,
    *,
    formula_code: str,
    emperors: Iterable[str] | None = None,
) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    emperor_filter = _filter(emperors)
    for row in read_jsonl(path):
        if row.get("formula_code") != formula_code:
            continue
        emperor = row.get("emperor")
        if not isinstance(emperor, str):
            continue
        if emperor_filter and emperor not in emperor_filter:
            continue
        latest[emperor] = row
    return latest
