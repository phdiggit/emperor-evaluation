from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from emperor_v4.evaluation.formal_json_store import load_json


OPPONENT_SYSTEM_CONTRACT_PATH = Path(
    "config/military/opponent-system-contract.json"
)
OPPONENT_SYSTEM_CONTRACT_SCHEMA = "opponent-system-contract-v1"


def load_opponent_system_contract(workspace_root: Path) -> dict[str, Any]:
    contract = load_json(workspace_root / OPPONENT_SYSTEM_CONTRACT_PATH)
    if (
        contract.get("schema_version") != OPPONENT_SYSTEM_CONTRACT_SCHEMA
        or contract.get("status") != "CURRENT"
    ):
        raise ValueError("公共军事对手战争机器O档合同非法")
    grades = dict(contract.get("grades") or {})
    grade_order = [str(grade) for grade in contract.get("grade_order") or ()]
    if grade_order != ["O1", "O2", "O3", "O4", "O5", "O6"]:
        raise ValueError("公共O档顺序不正确")
    if set(grades) != set(grade_order):
        raise ValueError("公共O档定义不完整")
    for index, grade in enumerate(grade_order, start=1):
        row = dict(grades[grade] or {})
        if (
            int(row.get("rank") or 0) != index
            or not str(row.get("label") or "").strip()
            or not str(row.get("definition") or "").strip()
        ):
            raise ValueError(f"公共O档定义非法: {grade}")
    return contract


def opponent_system_grade_rates(
    contract: Mapping[str, Any],
) -> dict[str, float]:
    consumer_contracts = dict(contract.get("consumer_contracts") or {})
    first_item = dict(consumer_contracts.get("first_item_opponent_pressure") or {})
    rates = {
        str(grade): float(rate)
        for grade, rate in dict(first_item.get("rate_by_grade") or {}).items()
    }
    expected = {"O1", "O2", "O3", "O4", "O5", "O6"}
    if set(rates) != expected or any(rate <= 0 or rate > 1 for rate in rates.values()):
        raise ValueError("公共O档的第一项压力映射非法")
    return rates


def opponent_system_grades_at_least(
    contract: Mapping[str, Any], minimum_grade: str
) -> set[str]:
    grade_order = [str(grade) for grade in contract.get("grade_order") or ()]
    if minimum_grade not in grade_order:
        raise ValueError(f"公共O档最低门槛非法: {minimum_grade}")
    return set(grade_order[grade_order.index(minimum_grade) :])


def build_opponent_system_index(
    *, registry: Mapping[str, Any], contract: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    allowed_grades = set(dict(contract.get("grades") or {}))
    systems: dict[str, dict[str, Any]] = {}
    for portfolio in registry.get("unification_campaign_portfolios") or ():
        for raw_system in portfolio.get("opponent_systems") or ():
            system_ref = str(raw_system.get("system_id") or "").strip()
            system = dict(raw_system)
            system.pop("system_id", None)
            if not system_ref or (
                system_ref in systems and systems[system_ref] != system
            ):
                raise ValueError(f"公共统一链O体系标识无效或漂移: {system_ref}")
            systems[system_ref] = system

    supplemental = {
        str(system_ref): dict(row)
        for system_ref, row in dict(
            contract.get("supplemental_opponent_systems") or {}
        ).items()
    }
    overlap = set(systems) & set(supplemental)
    if overlap:
        raise ValueError(f"公共统一链与补充O体系重复: {sorted(overlap)}")
    systems.update(supplemental)

    for system_ref, system in systems.items():
        grade = str(system.get("organization_grade") or "")
        if (
            grade not in allowed_grades
            or not str(system.get("opponent_label") or "").strip()
            or not str(system.get("basis") or "").strip()
            or not list(system.get("source_campaign_refs") or ())
        ):
            raise ValueError(f"公共O体系字段无效: {system_ref}")
    return systems
