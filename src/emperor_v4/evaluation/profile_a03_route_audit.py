"""A03 cross-axis route closure for the formal profile pool.

The audit is deliberately score-neutral.  It closes only an already declared
route to an existing target parent, or records an explicit freeze when the
current formal data does not provide a stable target parent.  It never creates
a target-axis parent and never changes a grade, position, or radar value.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Iterator

import yaml

from emperor_v4.evaluation.formal_json_store import (
    load_json,
    load_ruler_polities,
    write_json,
)
from emperor_v4.evaluation.profile_registry import profile_axis_order


ROOT = Path(__file__).resolve().parents[3]
AUDIT = ROOT / "docs/评分结算/皇帝人物画像/M2/14-M2-A03跨轴路由闭环审计.json"
FORMAL_AXES = tuple(profile_axis_order())
TERMINAL_ROUTE_STATUSES = {"CLOSED", "EXPLICITLY_FROZEN"}


def _profile_config() -> dict[str, Any]:
    project = yaml.safe_load((ROOT / "config/project.yml").read_text(encoding="utf-8"))
    profile = project.get("profile_assessment")
    if not isinstance(profile, dict):
        raise ValueError("project.yml缺少profile_assessment")
    return profile


def _formal_payloads() -> dict[str, dict[str, Any]]:
    profile = _profile_config()
    return {
        axis: load_json(ROOT / profile["settled_axes"][axis]["json"])
        for axis in FORMAL_AXES
    }


def _walk(
    value: Any,
    *,
    axis: str,
    path: tuple[str, ...] = (),
    context: dict[str, Any] | None = None,
) -> Iterator[tuple[str, tuple[str, ...], dict[str, Any], dict[str, Any]]]:
    """Yield structured nodes with the nearest formal identity context."""

    inherited = dict(context or {})
    if isinstance(value, dict):
        current = dict(inherited)
        for key in (
            "ruler_id",
            "ruler_name",
            "polity",
            "task_code",
            "record_index",
            "parent_id",
        ):
            if key in value and key not in current:
                current[key] = value[key]
        yield axis, path, current, value
        for key, child in value.items():
            yield from _walk(
                child,
                axis=axis,
                path=path + (str(key),),
                context=current,
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(
                child,
                axis=axis,
                path=path + (str(index),),
                context=inherited,
            )


def _route_nodes(
    payloads: dict[str, dict[str, Any]],
) -> Iterator[tuple[str, tuple[str, ...], dict[str, Any], dict[str, Any]]]:
    for axis in FORMAL_AXES:
        for item in _walk(payloads[axis], axis=axis):
            if "route_handoff" in item[3] and isinstance(item[3]["route_handoff"], dict):
                yield item


def _axis_out_unit_nodes(
    payloads: dict[str, dict[str, Any]],
) -> Iterator[tuple[str, tuple[str, ...], dict[str, Any], dict[str, Any]]]:
    for axis in FORMAL_AXES:
        for item in _walk(payloads[axis], axis=axis):
            node = item[3]
            if node.get("status") == "AXIS_OUT_WITH_REASON" and "route_handoff" not in node:
                yield item


def _parent_index(payloads: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    result = {axis: set() for axis in FORMAL_AXES}
    for axis, _, _, node in _walk_all(payloads):
        parent_id = node.get("parent_id")
        if parent_id:
            result[axis].add(str(parent_id))
    return result


def _parent_index_by_ruler(
    payloads: dict[str, dict[str, Any]],
) -> dict[str, dict[str, set[str]]]:
    result = {axis: {} for axis in FORMAL_AXES}
    for axis, _, context, node in _walk_all(payloads):
        parent_id = node.get("parent_id")
        ruler_id = context.get("ruler_id")
        if not parent_id or not ruler_id:
            continue
        result[axis].setdefault(str(ruler_id), set()).add(str(parent_id))
    return result


def _walk_all(
    payloads: dict[str, dict[str, Any]],
) -> Iterator[tuple[str, tuple[str, ...], dict[str, Any], dict[str, Any]]]:
    for axis in FORMAL_AXES:
        yield from _walk(payloads[axis], axis=axis)


def _target_axes(value: Any) -> list[str]:
    return [axis for axis in str(value or "").split("/") if axis in FORMAL_AXES]


def _target_parent_ids(
    target_ref: str,
    target_axes: Iterable[str],
    parent_index: dict[str, set[str]],
    *,
    ruler_id: str | None = None,
    parent_index_by_ruler: dict[str, dict[str, set[str]]] | None = None,
) -> tuple[str | None, str | None]:
    """Resolve an exact or legacy abbreviated target parent without guessing."""

    axes = list(target_axes)
    def candidates_for(axis: str) -> set[str]:
        if parent_index_by_ruler is not None and ruler_id:
            return parent_index_by_ruler[axis].get(ruler_id, set())
        return parent_index[axis]

    exact = [axis for axis in axes if target_ref in candidates_for(axis)]
    if len(exact) == 1:
        return target_ref, "EXACT_TARGET_PARENT"
    if len(exact) > 1:
        return None, None

    tail = target_ref
    if "-" in target_ref:
        tail = target_ref.split("-", 1)[1]
    candidates = sorted(
        {
            parent_id
            for axis in axes
            for parent_id in candidates_for(axis)
            if parent_id.endswith(f"-{tail}") or parent_id.endswith(tail)
        }
    )
    if len(candidates) == 1:
        return candidates[0], "NORMALIZED_TARGET_PARENT_ALIAS"
    return None, None


def _freeze_route(handoff: dict[str, Any], *, old_status: str, old_target: Any) -> None:
    if old_target not in (None, "", "PENDING_FORMAL_HANDOFF"):
        handoff["original_target_parent_ref"] = str(old_target)
    elif old_target == "PENDING_FORMAL_HANDOFF":
        handoff["original_target_parent_ref"] = "PENDING_FORMAL_HANDOFF"
    handoff["status"] = "EXPLICITLY_FROZEN"
    handoff["target_parent_ref"] = None
    handoff["freeze_reason"] = (
        "A03整改：当前正式快照没有可稳定反查的目标父链；本次不自动代开目标轴父链，"
        "也不把该事实继续计入原轴之外的档位。"
    )
    handoff["reopen_condition"] = (
        "目标轴正式JSON登记与本事实同一事件的稳定parent_id后，补填target_parent_ref并重新运行A03闭环校验；"
        "在此之前保持轴外冻结。"
    )
    handoff["freeze_basis"] = f"原路由状态={old_status}；目标父链未在当前正式入口闭合"


def _close_or_freeze_routes(
    payloads: dict[str, dict[str, Any]],
) -> list[dict[str, str | None]]:
    parent_index = _parent_index(payloads)
    parent_index_by_ruler = _parent_index_by_ruler(payloads)
    changes: list[dict[str, str | None]] = []
    for axis, path, context, node in _route_nodes(payloads):
        handoff = node["route_handoff"]
        old_status = str(handoff.get("status") or "")
        old_target = handoff.get("target_parent_ref")
        source_parent = str(node.get("parent_id") or "")
        source_key = f"{axis}:{context.get('ruler_id', '')}:{source_parent}:{'.'.join(path)}"

        target_axes = _target_axes(handoff.get("target_axis"))
        candidate_target = old_target
        if old_status == "EXPLICITLY_FROZEN":
            candidate_target = handoff.get("original_target_parent_ref")
        if candidate_target not in (None, "", "PENDING_FORMAL_HANDOFF") and old_status in {"ROUTED", "EXPLICITLY_FROZEN"}:
            resolved, basis = _target_parent_ids(
                str(candidate_target),
                target_axes,
                parent_index,
                ruler_id=str(context.get("ruler_id") or "") or None,
                parent_index_by_ruler=parent_index_by_ruler,
            )
            if resolved and basis:
                handoff["status"] = "CLOSED"
                handoff["target_parent_ref"] = resolved
                if resolved != candidate_target:
                    handoff["original_target_parent_ref"] = str(candidate_target)
                handoff["closure_basis"] = basis
                handoff.pop("freeze_reason", None)
                handoff.pop("reopen_condition", None)
                handoff.pop("freeze_basis", None)
                changes.append(
                    {
                        "source": source_key,
                        "old_status": old_status,
                        "new_status": "CLOSED",
                    }
                )
                continue

        if old_status in TERMINAL_ROUTE_STATUSES and old_status != "EXPLICITLY_FROZEN":
            changes.append(
                {
                    "source": source_key,
                    "old_status": old_status,
                    "new_status": old_status,
                }
            )
            continue

        _freeze_route(handoff, old_status=old_status, old_target=old_target)
        changes.append(
            {
                "source": source_key,
                "old_status": old_status,
                "new_status": "EXPLICITLY_FROZEN",
            }
        )
    return changes


def apply_route_closure(root: Path = ROOT) -> list[dict[str, str | None]]:
    """Update only declared route metadata; never touch profile scores."""

    del root  # The formal paths are repository-rooted, matching other profile tools.
    payloads = _formal_payloads()
    changes = _close_or_freeze_routes(payloads)
    if any(change["old_status"] != change["new_status"] for change in changes):
        polities = load_ruler_polities(ROOT)
        profile = _profile_config()
        for axis in FORMAL_AXES:
            path = ROOT / profile["settled_axes"][axis]["json"]
            if any(change["source"].startswith(f"{axis}:") for change in changes):
                write_json(path, payloads[axis], ruler_polities=polities)
    return changes


def _route_row(
    axis: str,
    path: tuple[str, ...],
    context: dict[str, Any],
    node: dict[str, Any],
    parent_index: dict[str, set[str]],
    parent_index_by_ruler: dict[str, dict[str, set[str]]],
) -> dict[str, Any]:
    handoff = node["route_handoff"]
    status = str(handoff.get("status") or "")
    target_axes = _target_axes(handoff.get("target_axis"))
    target_ref = handoff.get("target_parent_ref")
    errors: list[str] = []
    if status == "CLOSED":
        if not target_ref:
            errors.append("CLOSED缺少target_parent_ref")
        elif not any(
            str(target_ref) in parent_index_by_ruler[target_axis].get(str(context.get("ruler_id") or ""), set())
            for target_axis in target_axes
        ):
            errors.append("CLOSED的target_parent_ref不在声明目标轴正式父链中")
    elif status == "EXPLICITLY_FROZEN":
        if target_ref not in (None, ""):
            errors.append("EXPLICITLY_FROZEN不得保留活动target_parent_ref")
        if not str(handoff.get("freeze_reason") or "").strip():
            errors.append("EXPLICITLY_FROZEN缺少freeze_reason")
        if not str(handoff.get("reopen_condition") or "").strip():
            errors.append("EXPLICITLY_FROZEN缺少reopen_condition")
    else:
        errors.append(f"非终态路由状态: {status or 'EMPTY'}")

    row = {
        "source_axis": axis,
        "source_locator": f"{axis}:{'.'.join(path)}",
        "ruler_id": context.get("ruler_id"),
        "ruler_name": context.get("ruler_name"),
        "source_parent_ref": node.get("parent_id"),
        "source_consumption_status": node.get("consumption_status"),
        "route_status": status,
        "target_axis": handoff.get("target_axis"),
        "target_parent_ref": target_ref,
        "original_target_parent_ref": handoff.get("original_target_parent_ref"),
        "reason": handoff.get("reason"),
        "closure_basis": handoff.get("closure_basis"),
        "freeze_reason": handoff.get("freeze_reason"),
        "reopen_condition": handoff.get("reopen_condition"),
    }
    if errors:
        row["validation_errors"] = errors
    return row


def build_audit() -> dict[str, Any]:
    payloads = _formal_payloads()
    parent_index = _parent_index(payloads)
    parent_index_by_ruler = _parent_index_by_ruler(payloads)
    rows = [
        _route_row(axis, path, context, node, parent_index, parent_index_by_ruler)
        for axis, path, context, node in _route_nodes(payloads)
    ]
    unit_rows = []
    for axis, path, context, node in _axis_out_unit_nodes(payloads):
        unit_rows.append(
            {
                "source_axis": axis,
                "source_locator": f"{axis}:{'.'.join(path)}",
                "ruler_id": context.get("ruler_id"),
                "ruler_name": context.get("ruler_name"),
                "unit_ids": list(node.get("unit_ids") or []),
                "reason": node.get("reason"),
                "resolution": "EXPLICITLY_FROZEN_NO_PARENT_ROUTE",
                "reopen_condition": (
                    "仅当该稳定事实单元被正式聚合为目标轴parent_chain并建立target_parent_ref时重新纳入跨轴路由复核。"
                ),
            }
        )
    errors = [
        {"source_locator": row["source_locator"], "errors": row["validation_errors"]}
        for row in rows
        if row.get("validation_errors")
    ]
    closed = sum(row["route_status"] == "CLOSED" for row in rows)
    frozen = sum(row["route_status"] == "EXPLICITLY_FROZEN" for row in rows)
    profile = _profile_config()
    payload = {
        "schema_version": "profile-a03-cross-axis-route-closure-v1",
        "canonical_status": "FORMAL_CURRENT_AUDIT",
        "review_scope": "A03_CROSS_AXIS_ROUTE_CLOSURE_FULL_POOL",
        "contract_basis": "docs/分项规则/人物画像轴/00-共同数据与发布合同.md",
        "source_registry": "config/project.yml:profile_assessment",
        "source_axes": list(FORMAL_AXES),
        "population_count": int(profile.get("population_count") or 0),
        "route_handoff_count": len(rows),
        "closed_count": closed,
        "explicitly_frozen_count": frozen,
        "unresolved_count": len(errors),
        "axis_out_unit_count": len(unit_rows),
        "axis_out_unit_frozen_count": len(unit_rows),
        "formal_score_write": False,
        "grade_write": False,
        "position_write": False,
        "radar_write": False,
        "rows": rows,
        "axis_out_unit_exclusions": unit_rows,
        "validation_errors": errors,
    }
    return payload


def verify(root: Path = ROOT) -> dict[str, Any]:
    del root
    expected = build_audit()
    if not AUDIT.is_file():
        raise ValueError(f"A03审计文件不存在: {AUDIT}")
    actual = load_json(AUDIT)
    if actual != expected:
        raise ValueError("A03审计文件与当前正式画像路由不一致")
    if expected["unresolved_count"]:
        raise ValueError(f"A03存在未闭合且未冻结路由: {expected['unresolved_count']}")
    return {
        "status": "PASS",
        "route_handoff_count": expected["route_handoff_count"],
        "closed_count": expected["closed_count"],
        "explicitly_frozen_count": expected["explicitly_frozen_count"],
        "axis_out_unit_count": expected["axis_out_unit_count"],
        "validation_scope": "FULL_POOL_ROUTE_LINEAGE_AND_UNIT_OUT_BOUNDARY",
        "score_write": False,
    }


def write(root: Path = ROOT) -> dict[str, Any]:
    del root
    changes = apply_route_closure(ROOT)
    from emperor_v4.evaluation.profile_markdown import write_axes

    markdown_paths = write_axes(("M2",))
    payload = build_audit()
    write_json(AUDIT, payload)
    return {
        "audit_json": AUDIT.relative_to(ROOT).as_posix(),
        "markdown": [path.relative_to(ROOT).as_posix() for path in markdown_paths],
        "route_changes": changes,
        "summary": {
            "route_handoff_count": payload["route_handoff_count"],
            "closed_count": payload["closed_count"],
            "explicitly_frozen_count": payload["explicitly_frozen_count"],
            "axis_out_unit_count": payload["axis_out_unit_count"],
            "unresolved_count": payload["unresolved_count"],
        },
    }
