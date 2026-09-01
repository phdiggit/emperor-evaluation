from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any, Mapping

from emperor_v4.evaluation.battle_registry_store import load_battle_registry
from emperor_v4.evaluation.post_tang_canonical_battle_promotion import CONFIG_PATH


REGISTRY_PATH = Path("docs/公共成果/军事/01-战役登记.json")
POLITY_IDENTITIES = {
    "north_song": "北宋",
    "south_song": "南宋",
    "yuan": "元",
    "ming": "明",
}


def _canonical_polity(value: object) -> str:
    text = str(value or "")
    return POLITY_IDENTITIES.get(text, text)


def _phase_semantic_key(phase: Mapping[str, Any]) -> str:
    return json.dumps({
        key: phase.get(key)
        for key in (
            "evaluation_subject_phase",
            "subject_role",
            "actual_process",
            "cost_axes",
            "strategic_security",
            "strategic_security_detail",
            "material_return",
            "material_return_detail",
            "border_control",
            "phase_return_class",
            "founding_startup_ledger",
        )
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _has_required_raw_axes(phase: Mapping[str, Any]) -> bool:
    costs = phase.get("cost_axes") or {}
    return (
        all(axis in costs for axis in ("P", "S", "M", "A"))
        and "strategic_security" in phase
        and "material_return" in phase
        and bool(phase.get("border_control"))
        and "phase_return_class" in phase
    )


def _has_unknown_raw_axis(phase: Mapping[str, Any]) -> bool:
    values = [
        *(phase.get("cost_axes") or {}).values(),
        phase.get("strategic_security"),
        phase.get("material_return"),
        *((phase.get("border_control") or {}).get(key) for key in ("BCP", "BCN")),
        phase.get("phase_return_class"),
    ]
    return any(value is None or str(value).upper() == "UNKNOWN" for value in values)


def _post_tang_bound_phase_index(
    registry: Mapping[str, Any],
) -> dict[str, list[tuple[Mapping[str, Any], Mapping[str, Any]]]]:
    """Validate the public-registry identity chain once and index bound phases."""

    indexed: dict[str, list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = {}
    phase_identity_by_id: dict[str, tuple[str, str, str, str]] = {}
    semantic_owners: dict[tuple[str, str], set[str]] = {}
    for record in registry.get("records") or ():
        if not record.get("third_item_phase_container"):
            continue
        group = str(record.get("campaign_group_ref") or "")
        war_event_id = str(record.get("war_event_id") or "")
        if not group or not war_event_id:
            raise ValueError("第三项阶段容器缺少war_event_id或campaign_group_ref")
        for phase in record.get("subject_phase_views") or ():
            if str(phase.get("campaign_group_ref") or "") != group:
                raise ValueError(
                    f"公共战役登记阶段与容器父级不一致：{war_event_id}/"
                    f"{phase.get('phase_id')}"
                )
            binding = phase.get("ruler_binding") or {}
            binding_status = str(binding.get("status") or "")
            if not binding_status.startswith("BOUND_") or binding_status == (
                "BOUND_YEAR_WINDOW_BOUNDARY"
            ):
                continue
            phase_id = str(phase.get("phase_id") or "")
            ruler_id = str(binding.get("ruler_id") or "")
            ruler_name = str(binding.get("ruler_name") or "")
            polity = _canonical_polity(
                binding.get("polity") or phase.get("polity_binding")
            )
            subject = str(phase.get("evaluation_subject_phase") or "")
            if not all((phase_id, ruler_id, ruler_name, polity, subject)):
                raise ValueError(f"公共战役登记已绑定阶段身份字段不完整：{war_event_id}")
            identity = (war_event_id, group, ruler_id, polity)
            prior = phase_identity_by_id.setdefault(phase_id, identity)
            if prior != identity:
                raise ValueError(f"公共战役登记phase_id跨事件或主体重复：{phase_id}")
            semantic_key = (group, _phase_semantic_key(phase))
            owners = semantic_owners.setdefault(semantic_key, set())
            owners.add(ruler_id)
            if len(owners) > 1:
                raise ValueError(
                    f"公共战役登记同一主体阶段轴被复制给不同统治窗口："
                    f"{group}/{sorted(owners)}"
                )
            indexed.setdefault(ruler_id, []).append((record, phase))
    return indexed


def iter_post_tang_bound_cycles(
    registry: Mapping[str, Any],
    ruler_id: str,
    *,
    ruler_name: str,
    polity: str,
) -> list[dict[str, Any]]:
    """Consume only ruler-bound canonical phase containers from the public registry.

    campaign_group is a provisional D parent candidate.  This function performs
    exact semantic duplicate removal but deliberately does not merge continuous
    ruler-window investment cycles; that judgment remains in the Third Item D
    parent-cycle review.
    """
    grouped: dict[str, dict[str, Any]] = {}
    seen: set[tuple[str, str]] = set()
    for record, phase in _post_tang_bound_phase_index(registry).get(ruler_id, []):
        group = str(record.get("campaign_group_ref") or "")
        binding = phase.get("ruler_binding") or {}
        if (
            str(binding.get("ruler_id") or "") != ruler_id
            or str(binding.get("ruler_name") or "") != ruler_name
            or _canonical_polity(
                binding.get("polity") or phase.get("polity_binding")
            ) != _canonical_polity(polity)
        ):
            raise ValueError(
                f"公共战役登记主体/政权/统治窗口与正式对象不一致："
                f"{phase.get('phase_id')}->{binding}"
            )
        semantic = _phase_semantic_key(phase)
        duplicate_key = (group, semantic)
        if duplicate_key in seen:
            continue
        seen.add(duplicate_key)
        cycle = grouped.setdefault(
            group,
            {
                "campaign_group_ref": group,
                "provisional_parent_cycle_status": (
                    "REQUIRES_D_RULER_WINDOW_PARENT_REVIEW"
                ),
                "war_event_refs": [],
                "source_partitions": [],
                "phases": [],
            },
        )
        cycle["war_event_refs"].append(str(record["war_event_id"]))
        cycle["source_partitions"].append(
            str(record.get("dynasty_partition") or "")
        )
        normalized_phase = dict(phase)
        normalized_phase["ruler_binding"] = {
            **dict(binding),
            "polity": _canonical_polity(polity),
        }
        normalized_phase["polity_binding"] = _canonical_polity(polity)
        cycle["phases"].append(normalized_phase)
    return [
        {
            **cycle,
            "war_event_refs": list(dict.fromkeys(cycle["war_event_refs"])),
            "source_partitions": list(
                dict.fromkeys(cycle["source_partitions"])
            ),
            "phase_ids": [str(phase["phase_id"]) for phase in cycle["phases"]],
        }
        for _, cycle in sorted(grouped.items())
    ]


def build_post_tang_third_item_consumption_audit(
    workspace_root: Path,
) -> dict[str, Any]:
    config = json.loads((workspace_root / CONFIG_PATH).read_text(encoding="utf-8"))
    registry = load_battle_registry(workspace_root / REGISTRY_PATH)
    ruler_rows: list[dict[str, Any]] = []
    all_phase_ids: list[str] = []
    for polity, polity_config in (config.get("polities") or {}).items():
        for ruler in polity_config.get("rulers") or ():
            cycles = iter_post_tang_bound_cycles(
                registry,
                str(ruler["ruler_id"]),
                ruler_name=str(ruler["ruler_name"]),
                polity=str(polity),
            )
            phases = [phase for cycle in cycles for phase in cycle["phases"]]
            phase_ids = [str(phase["phase_id"]) for phase in phases]
            all_phase_ids.extend(phase_ids)
            missing_axes = [
                phase for phase in phases if not _has_required_raw_axes(phase)
            ]
            unknown_axes = [
                phase for phase in phases if _has_unknown_raw_axis(phase)
            ]
            founding_phases = [
                phase
                for phase in phases
                if (phase.get("founding_startup_ledger") or {}).get(
                    "is_founding_process"
                )
            ]
            ruler_rows.append({
                "polity": polity,
                "ruler_id": ruler["ruler_id"],
                "ruler_name": ruler["ruler_name"],
                "provisional_parent_cycle_count": len(cycles),
                "consumed_phase_count": len(phases),
                "missing_required_raw_axis_phase_count": len(missing_axes),
                "unknown_raw_axis_phase_count": len(unknown_axes),
                "founding_flagged_phase_count": len(founding_phases),
                "source_partition_counts": dict(sorted(Counter(
                    partition
                    for cycle in cycles
                    for partition in cycle["source_partitions"]
                ).items())),
                "consumption_status": (
                    "NO_BOUND_CANONICAL_PHASE"
                    if not phases
                    else "BLOCKED_MISSING_RAW_AXES"
                    if missing_axes
                    else "READY_FOR_D_PARENT_AND_AB_CONSUMPTION_REVIEW"
                ),
            })
    return {
        "schema_version": "post-tang-third-item-consumption-audit-v1",
        "source_registry": REGISTRY_PATH.as_posix(),
        "direct_chronicle_card_consumption_allowed": False,
        "campaign_group_is_final_d_parent_cycle": False,
        "ruler_count": len(ruler_rows),
        "ruler_with_bound_phase_count": sum(
            bool(row["consumed_phase_count"]) for row in ruler_rows
        ),
        "provisional_parent_cycle_count": sum(
            row["provisional_parent_cycle_count"] for row in ruler_rows
        ),
        "consumed_phase_count": len(all_phase_ids),
        "duplicate_consumed_phase_id_count": len(all_phase_ids)
        - len(set(all_phase_ids)),
        "missing_required_raw_axis_phase_count": sum(
            row["missing_required_raw_axis_phase_count"] for row in ruler_rows
        ),
        "unknown_raw_axis_phase_count": sum(
            row["unknown_raw_axis_phase_count"] for row in ruler_rows
        ),
        "founding_flagged_phase_count": sum(
            row["founding_flagged_phase_count"] for row in ruler_rows
        ),
        "rulers": ruler_rows,
    }
