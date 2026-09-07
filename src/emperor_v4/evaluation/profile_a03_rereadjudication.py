"""Post-A03 semantic re-adjudication, kept separate from formal score data.

A03 changes route lineage only.  This module records the affected rulers and
checks whether that lineage change altered any formal scoring input.  Existing
target parents are not re-counted, and a frozen handoff is not treated as new
evidence.  The expected outcome is therefore an explicit, auditable
``MAINTAIN_CURRENT`` decision unless a later human adjudication changes it.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.formal_json_store import load_json, write_json
from emperor_v4.evaluation.profile_a03_route_audit import (
    AUDIT,
    FORMAL_AXES,
    ROOT,
    _formal_payloads,
    _profile_config,
)


READJUDICATION = ROOT / "docs/评分结算/皇帝人物画像/M2/15-M2-A03整改后复裁.json"


def _records_and_parents() -> tuple[dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str, str], dict[str, Any]]]:
    payloads = _formal_payloads()
    records: dict[tuple[str, str], dict[str, Any]] = {}
    parents: dict[tuple[str, str, str], dict[str, Any]] = {}
    for axis, payload in payloads.items():
        for record in payload["records"]:
            ruler_id = str(record["ruler_id"])
            records[(axis, ruler_id)] = record
            for parent in record.get("parent_chains") or record.get("parents") or []:
                parent_id = parent.get("parent_id")
                if parent_id:
                    parents[(axis, ruler_id, str(parent_id))] = parent
    return records, parents


def _formal_value(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "axis_grade": record.get("axis_grade"),
        "position": record.get("position"),
        "score_100": record.get("score_100"),
        "radar_value": record.get("radar_value"),
        "score_status": record.get("score_status"),
        "axis_evidence_level": record.get("axis_evidence_level"),
        "output_mode": record.get("output_mode"),
    }


def _target_axes(value: Any) -> list[str]:
    return [axis for axis in str(value or "").split("/") if axis in FORMAL_AXES]


def _target_matches(
    row: dict[str, Any],
    ruler_id: str,
    parents: dict[tuple[str, str, str], dict[str, Any]],
) -> list[tuple[str, dict[str, Any]]]:
    target_ref = row.get("target_parent_ref")
    if row.get("route_status") != "CLOSED" or not target_ref:
        return []
    matches = [
        (axis, parents[(axis, ruler_id, str(target_ref))])
        for axis in _target_axes(row.get("target_axis"))
        if (axis, ruler_id, str(target_ref)) in parents
    ]
    if len(matches) != 1:
        raise ValueError(
            f"A03复裁目标父链无法唯一定位: {ruler_id}/{row.get('source_parent_ref')}"
        )
    return matches


def build_readjudication() -> dict[str, Any]:
    audit = load_json(AUDIT)
    records, parents = _records_and_parents()
    by_ruler: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in audit["rows"]:
        by_ruler[str(row["ruler_id"])].append(row)

    decisions: list[dict[str, Any]] = []
    for ruler_id, rows in by_ruler.items():
        source = records[("M2", ruler_id)]
        target_values: dict[str, dict[str, Any]] = {}
        target_parent_rows: list[dict[str, Any]] = []
        closed_count = 0
        frozen_count = 0
        impact_axes = {"M2"}
        for row in rows:
            if row["route_status"] == "CLOSED":
                closed_count += 1
                matches = _target_matches(row, ruler_id, parents)
                for target_axis, target_parent in matches:
                    target_record = records[(target_axis, ruler_id)]
                    target_values[target_axis] = _formal_value(target_record)
                    impact_axes.add(target_axis)
                    target_parent_rows.append(
                        {
                            "source_parent_ref": row["source_parent_ref"],
                            "route_status": row["route_status"],
                            "target_axis": target_axis,
                            "target_parent_ref": target_parent.get("parent_id"),
                            "target_parent_already_formal": True,
                        }
                    )
            elif row["route_status"] == "EXPLICITLY_FROZEN":
                frozen_count += 1
                impact_axes.update(_target_axes(row.get("target_axis")))
                target_parent_rows.append(
                    {
                        "source_parent_ref": row["source_parent_ref"],
                        "route_status": row["route_status"],
                        "target_axis": row.get("target_axis"),
                        "target_parent_ref": None,
                        "target_parent_already_formal": False,
                    }
                )
            else:
                raise ValueError(f"A03复裁遇到非终态路由: {row}")

        current_values = {"M2": _formal_value(source), **target_values}
        decisions.append(
            {
                "ruler_id": ruler_id,
                "ruler_name": source.get("ruler_name"),
                "affected_axis_codes": sorted(impact_axes),
                "route_count": len(rows),
                "closed_route_count": closed_count,
                "frozen_route_count": frozen_count,
                "source_parent_refs": [row["source_parent_ref"] for row in rows],
                "target_parent_routes": target_parent_rows,
                "current_formal_values": current_values,
                "post_review_formal_values": current_values,
                "decision": "MAINTAIN_CURRENT",
                "formal_action": "NO_FORMAL_WRITE",
                "grade_basis": (
                    "A03只改变已有路由的闭合状态或冻结状态：闭合项的目标父链已在正式目标轴存在，"
                    "冻结项没有目标父链，均未新增可计分父链，故不改变当前档位、位置或雷达值。"
                ),
                "reopen_condition": (
                    "若冻结项后续建立同一事实的正式目标父链，或目标轴现有父链的归责/消费状态发生正式变化，"
                    "重新运行A03复裁并只复核受影响人物与轴。"
                ),
            }
        )

    decisions.sort(key=lambda row: row["ruler_id"])
    profile = _profile_config()
    affected = len(decisions)
    return {
        "schema_version": "profile-a03-post-route-readjudication-v1",
        "canonical_status": "FORMAL_CURRENT_AUDIT",
        "review_scope": "A03_POST_ROUTE_CLOSURE_READJUDICATION",
        "source_audit": "docs/评分结算/皇帝人物画像/M2/14-M2-A03跨轴路由闭环审计.json",
        "source_registry": "config/project.yml:profile_assessment",
        "population_count": int(profile.get("population_count") or 0),
        "affected_ruler_count": affected,
        "unaffected_ruler_count": int(profile.get("population_count") or 0) - affected,
        "route_handoff_count": len(audit["rows"]),
        "closed_route_count": audit["closed_count"],
        "explicitly_frozen_count": audit["explicitly_frozen_count"],
        "decision_counts": {"MAINTAIN_CURRENT": affected},
        "grade_changed_count": 0,
        "position_changed_count": 0,
        "radar_changed_count": 0,
        "formal_parent_write_count": 0,
        "formal_score_write": False,
        "grade_write": False,
        "position_write": False,
        "radar_write": False,
        "decisions": decisions,
    }


def verify(root: Path = ROOT) -> dict[str, Any]:
    del root
    if not READJUDICATION.is_file():
        raise ValueError(f"A03复裁文件不存在: {READJUDICATION}")
    expected = build_readjudication()
    actual = load_json(READJUDICATION)
    if actual != expected:
        raise ValueError("A03复裁文件与当前正式画像路由或档位不一致")
    if any(row["decision"] != "MAINTAIN_CURRENT" for row in expected["decisions"]):
        raise ValueError("A03复裁存在未处置决定")
    return {
        "status": "PASS",
        "affected_ruler_count": expected["affected_ruler_count"],
        "route_handoff_count": expected["route_handoff_count"],
        "grade_changed_count": expected["grade_changed_count"],
        "formal_score_write": expected["formal_score_write"],
        "validation_scope": "A03_AFFECTED_RULERS_SEMANTIC_REVIEW",
    }


def write(root: Path = ROOT) -> dict[str, Any]:
    del root
    payload = build_readjudication()
    write_json(READJUDICATION, payload)
    return {
        "readjudication_json": READJUDICATION.relative_to(ROOT).as_posix(),
        "summary": {
            "affected_ruler_count": payload["affected_ruler_count"],
            "route_handoff_count": payload["route_handoff_count"],
            "grade_changed_count": payload["grade_changed_count"],
            "formal_score_write": payload["formal_score_write"],
        },
    }
