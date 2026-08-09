from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from emperor_v4.evaluation.battle_registry_store import load_battle_registry
from emperor_v4.evaluation.post_tang_canonical_battle_promotion import CONFIG_PATH


REGISTRY_PATH = Path("docs/公共成果/军事/01-战役登记.json")


def _digest(value: Any) -> str:
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _phase_semantic_fingerprint(phase: Mapping[str, Any]) -> str:
    return _digest({
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
    })


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


def iter_post_tang_bound_cycles(
    registry: Mapping[str, Any],
    ruler_id: str,
) -> list[dict[str, Any]]:
    """Consume only ruler-bound canonical phase containers from the public registry.

    campaign_group is a provisional D parent candidate.  This function performs
    exact semantic duplicate removal but deliberately does not merge continuous
    ruler-window investment cycles; that judgment remains in the Third Item D
    parent-cycle review.
    """
    grouped: dict[str, dict[str, Any]] = {}
    seen: set[tuple[str, str]] = set()
    for record in registry.get("records") or ():
        if not record.get("third_item_phase_container"):
            continue
        group = str(record.get("campaign_group_ref") or "")
        if not group:
            raise ValueError("第三项阶段容器缺少campaign_group_ref")
        for phase in record.get("subject_phase_views") or ():
            binding = phase.get("ruler_binding") or {}
            if binding.get("status") != "BOUND_EXCLUSIVE_GOVERNING_WINDOW":
                continue
            if str(binding.get("ruler_id") or "") != ruler_id:
                continue
            semantic = _phase_semantic_fingerprint(phase)
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
            cycle["phases"].append(dict(phase))
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
            cycles = iter_post_tang_bound_cycles(registry, str(ruler["ruler_id"]))
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
        "semantic_fingerprint": _digest(ruler_rows),
    }
