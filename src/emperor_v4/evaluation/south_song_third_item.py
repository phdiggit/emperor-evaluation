from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from emperor_v4.evaluation.battle_registry_store import load_battle_registry
from emperor_v4.evaluation.five_dynasties_third_item import (
    CONTROL_CONTRIBUTION_CAPS,
    _axis_a,
    _axis_b,
    _c_score,
    _d_grade_and_score,
    _expected_b1_grade,
    _rollup_parent_axes,
    _semantic_internal_route,
    _third_item_cycles,
)
from emperor_v4.evaluation.north_song_third_item import _aggregate_d_cycle
from emperor_v4.evaluation.north_song_third_item import (
    _build_combined as _build_north_song_combined,
    build_north_song_ab_records,
    build_north_song_c_records,
    build_north_song_d_records,
)
from emperor_v4.evaluation.five_dynasties_third_item import (
    AB_PATH,
    C_PATH,
    D_PATH,
    FORMAL_PATH,
    _align_bc_to_system_stress_parent_cycles,
    _assign_global_third_item_ranks,
    _normalize_formal_d_records,
    _normalize_qin_tang_bc_parent_cycles,
    _recalculate_qin_tang_d_records,
    _render_combined_markdown,
    _render_formal_markdown,
    _replace_partition_records,
    _sync_formal_ab_into_combined,
    _sync_formal_c_into_combined,
    _sync_formal_d_into_combined,
    _validate_bc_parent_cycle_alignment,
    _validate_d_empirical_calibration,
    _validate_formal_abc_contracts,
    _write_text_atomic,
)
from emperor_v4.evaluation.post_tang_third_item_consumption import (
    REGISTRY_PATH,
    iter_post_tang_bound_cycles,
)


FIRST_ITEM_PATH = Path(
    "docs/评分结算/第一项创业与政权取得能力/"
    "01-第一项创业与政权取得能力正式结算.json"
)
CYCLE_ADJUDICATION_PATH = Path(
    "config/south-song-third-item-cycle-adjudications.json"
)
RULERS: tuple[tuple[str, str], ...] = (
    ("RULER-SS-ZHAO-GOU", "赵构"),
    ("RULER-SS-ZHAO-SHEN", "赵昚"),
    ("RULER-SS-ZHAO-DUN", "赵惇"),
    ("RULER-SS-ZHAO-KUO", "赵扩"),
    ("RULER-SS-ZHAO-YUN", "赵昀"),
)


def _has_founding_phase(cycle: Mapping[str, Any]) -> bool:
    return any(
        bool((phase.get("founding_startup_ledger") or {}).get("is_founding_process"))
        for phase in cycle.get("phases") or ()
    )


def _cycle_axis_audit(cycle: Mapping[str, Any]) -> dict[str, Any]:
    costs, benefits, _, unknown_axes = _rollup_parent_axes(cycle["phases"])
    return {
        "route": _semantic_internal_route(cycle["phases"]),
        "material": max(costs.values()) >= 3 or max(benefits.values()) >= 3,
        "unknown_axes": unknown_axes,
    }


def build_south_song_cycle_admission_audit(
    workspace_root: Path,
) -> dict[str, Any]:
    """Apply cross-item admission before D parent-cycle merging or scoring.

    A founding flag excludes a cycle only when the ruler actually obtained a
    First Item score.  Non-founders cannot lose military evidence to an item
    in which they were not admitted.
    """
    registry = load_battle_registry(workspace_root / REGISTRY_PATH)
    first = json.loads((workspace_root / FIRST_ITEM_PATH).read_text(encoding="utf-8"))
    first_by_name = {str(row["ruler_name"]): row for row in first["records"]}
    rows: list[dict[str, Any]] = []
    admitted_refs: set[str] = set()
    excluded_refs: set[str] = set()
    for ruler_id, ruler_name in RULERS:
        raw_cycles = iter_post_tang_bound_cycles(registry, ruler_id)
        first_row = first_by_name[ruler_name]
        obtained_first_item_score = bool(first_row.get("score_applicable")) and float(
            first_row.get("first_item_score_points") or 0
        ) > 0
        admitted: list[Mapping[str, Any]] = []
        excluded: list[Mapping[str, Any]] = []
        for cycle in raw_cycles:
            if obtained_first_item_score and _has_founding_phase(cycle):
                excluded.append(cycle)
                excluded_refs.add(str(cycle["campaign_group_ref"]))
            else:
                admitted.append(cycle)
                admitted_refs.add(str(cycle["campaign_group_ref"]))
        axis_audits = [_cycle_axis_audit(cycle) for cycle in admitted]
        rows.append({
            "ruler_id": ruler_id,
            "ruler_name": ruler_name,
            "first_item_score_applicable": bool(first_row.get("score_applicable")),
            "actual_first_item_score_points": first_row.get("first_item_score_points"),
            "raw_bound_cycle_count": len(raw_cycles),
            "admitted_cycle_count": len(admitted),
            "excluded_first_item_founding_cycle_count": len(excluded),
            "retained_founding_flag_cycle_count": sum(
                _has_founding_phase(cycle) for cycle in admitted
            ),
            "internal_restoration_candidate_count": sum(
                audit["route"] == "D_INTERNAL_RESTORATION"
                for audit in axis_audits
            ),
            "material_cycle_count": sum(audit["material"] for audit in axis_audits),
            "unknown_axis_cycle_count": sum(
                bool(audit["unknown_axes"]) for audit in axis_audits
            ),
            "admission_status": "ADMITTED_FOR_PARENT_CYCLE_REVIEW",
        })
    if admitted_refs & excluded_refs:
        raise ValueError("南宋第三项同一campaign_group同时准入和排除")
    return {
        "schema_version": "south-song-third-item-cycle-admission-audit-v1",
        "source_registry": REGISTRY_PATH.as_posix(),
        "source_first_item_settlement": FIRST_ITEM_PATH.as_posix(),
        "cross_item_exclusion_policy": (
            "EXCLUDE_FOUNDING_CYCLE_ONLY_WHEN_RULER_ACTUALLY_OBTAINED_FIRST_ITEM_SCORE"
        ),
        "campaign_group_is_final_d_parent_cycle": False,
        "ruler_count": len(rows),
        "raw_bound_cycle_count": sum(row["raw_bound_cycle_count"] for row in rows),
        "admitted_cycle_count": sum(row["admitted_cycle_count"] for row in rows),
        "excluded_first_item_founding_cycle_count": sum(
            row["excluded_first_item_founding_cycle_count"] for row in rows
        ),
        "retained_founding_flag_cycle_count": sum(
            row["retained_founding_flag_cycle_count"] for row in rows
        ),
        "internal_restoration_candidate_count": sum(
            row["internal_restoration_candidate_count"] for row in rows
        ),
        "material_cycle_count": sum(row["material_cycle_count"] for row in rows),
        "unknown_axis_cycle_count": sum(
            row["unknown_axis_cycle_count"] for row in rows
        ),
        "route_status_counts": dict(sorted(Counter(
            row["admission_status"] for row in rows
        ).items())),
        "rulers": rows,
    }


def _load_cycle_adjudications(workspace_root: Path) -> list[dict[str, Any]]:
    payload = json.loads(
        (workspace_root / CYCLE_ADJUDICATION_PATH).read_text(encoding="utf-8")
    )
    if payload.get("schema_version") != "south-song-third-item-cycle-adjudications-v1":
        raise ValueError("南宋第三项父周期裁决schema错误")
    if payload.get("status") != "CURRENT":
        raise ValueError("南宋第三项父周期裁决不是当前值")
    rows = [dict(row) for row in payload.get("rulers") or ()]
    for row in rows:
        row["large_rebellion_audit_status"] = payload.get(
            "large_rebellion_audit_status"
        )
    if [(row["ruler_id"], row["ruler_name"]) for row in rows] != list(RULERS):
        raise ValueError("南宋第三项父周期裁决对象或顺序漂移")
    return rows


def build_south_song_parent_cycle_audit(
    workspace_root: Path,
) -> dict[str, Any]:
    registry = load_battle_registry(workspace_root / REGISTRY_PATH)
    decisions = _load_cycle_adjudications(workspace_root)
    ruler_rows: list[dict[str, Any]] = []
    all_phase_ids: list[str] = []
    for decision in decisions:
        raw_cycles = iter_post_tang_bound_cycles(
            registry, str(decision["ruler_id"])
        )
        route_decision = {
            "ruler_name": decision["ruler_name"],
            "third_item_cycle_merges": decision.get("cycle_merges") or [],
            "third_item_route_overrides": decision.get("route_overrides") or [],
            "third_item_cycle_exclusions": [],
            "admitted_large_rebellion_refs": list(
                decision.get("admitted_large_rebellion_refs") or ()
            ),
        }
        cycles, excluded = _third_item_cycles(route_decision, raw_cycles)
        parent_audits = [_aggregate_d_cycle(cycle) for cycle in cycles]
        phase_ids = [
            str(phase_id) for cycle in cycles for phase_id in cycle["phase_ids"]
        ]
        all_phase_ids.extend(phase_ids)
        ruler_rows.append({
            "ruler_id": decision["ruler_id"],
            "ruler_name": decision["ruler_name"],
            "raw_bound_cycle_count": len(raw_cycles),
            "reviewed_parent_cycle_count": len(cycles),
            "excluded_first_item_founding_cycle_count": len(excluded),
            "cycle_merge_count": len(decision.get("cycle_merges") or ()),
            "merged_member_cycle_count": sum(
                len(spec["member_campaign_group_refs"])
                for spec in decision.get("cycle_merges") or ()
            ),
            "explicit_route_override_count": len(
                decision.get("route_overrides") or ()
            ),
            "route_counts": dict(sorted(Counter(
                str(audit["route"]) for audit in parent_audits
            ).items())),
            "material_parent_cycle_count": sum(
                audit["material"] for audit in parent_audits
            ),
            "unknown_axis_parent_cycle_count": sum(
                bool(audit["unknown_axes"]) for audit in parent_audits
            ),
            "consumed_phase_count": len(phase_ids),
        })
    if len(all_phase_ids) != len(set(all_phase_ids)):
        raise ValueError("南宋第三项父周期之间重复消费主体阶段")
    return {
        "schema_version": "south-song-third-item-parent-cycle-audit-v1",
        "source_registry": REGISTRY_PATH.as_posix(),
        "source_adjudications": CYCLE_ADJUDICATION_PATH.as_posix(),
        "ruler_count": len(ruler_rows),
        "raw_bound_cycle_count": sum(
            row["raw_bound_cycle_count"] for row in ruler_rows
        ),
        "reviewed_parent_cycle_count": sum(
            row["reviewed_parent_cycle_count"] for row in ruler_rows
        ),
        "excluded_first_item_founding_cycle_count": sum(
            row["excluded_first_item_founding_cycle_count"] for row in ruler_rows
        ),
        "cycle_merge_count": sum(row["cycle_merge_count"] for row in ruler_rows),
        "merged_member_cycle_count": sum(
            row["merged_member_cycle_count"] for row in ruler_rows
        ),
        "material_parent_cycle_count": sum(
            row["material_parent_cycle_count"] for row in ruler_rows
        ),
        "unknown_axis_parent_cycle_count": sum(
            row["unknown_axis_parent_cycle_count"] for row in ruler_rows
        ),
        "consumed_phase_count": len(all_phase_ids),
        "duplicate_consumed_phase_id_count": 0,
        "rulers": ruler_rows,
    }


def build_south_song_d_preview(workspace_root: Path) -> dict[str, Any]:
    """Compute a non-formal D preview after admission, routing, and parent dedup."""
    registry = load_battle_registry(workspace_root / REGISTRY_PATH)
    decisions = _load_cycle_adjudications(workspace_root)
    rows: list[dict[str, Any]] = []
    for decision in decisions:
        raw_cycles = iter_post_tang_bound_cycles(
            registry, str(decision["ruler_id"])
        )
        route_decision = {
            "ruler_name": decision["ruler_name"],
            "third_item_cycle_merges": decision.get("cycle_merges") or [],
            "third_item_route_overrides": decision.get("route_overrides") or [],
            "third_item_cycle_exclusions": [],
            "admitted_large_rebellion_refs": list(
                decision.get("admitted_large_rebellion_refs") or ()
            ),
        }
        cycles, _ = _third_item_cycles(route_decision, raw_cycles)
        aggregated = [_aggregate_d_cycle(cycle) for cycle in cycles]
        grade, score, metrics = _d_grade_and_score(aggregated)
        rows.append({
            "ruler_id": decision["ruler_id"],
            "ruler_name": decision["ruler_name"],
            "D_preview_grade": grade,
            "D_preview_score_points": score,
            "reviewed_parent_cycle_count": len(cycles),
            "material_parent_cycle_count": metrics["material_cycle_count"],
            "known_material_parent_cycle_count": metrics[
                "known_material_cycle_count"
            ],
            "material_return_closure_rate": metrics[
                "material_return_closure_rate"
            ],
            "portfolio_efficiency_index": metrics[
                "portfolio_efficiency_index"
            ],
            "return_class_counts": metrics["return_class_counts"],
            "national_negative_return_refs": metrics[
                "national_negative_return_refs"
            ],
            "material_unknown_cycle_refs": metrics[
                "material_unknown_cycle_refs"
            ],
            "preview_only": True,
        })
    return {
        "schema_version": "south-song-third-item-d-preview-v1",
        "formal_score_write": False,
        "preview_limit": (
            "AB/C尚未裁决；D预览仅验证父周期、路由、成本收益聚合和UNKNOWN闭合率。"
        ),
        "ruler_count": len(rows),
        "rulers": rows,
    }


def build_south_song_abc_preview(workspace_root: Path) -> dict[str, Any]:
    """Build AB/C/D score previews from the reviewed South Song evidence chain."""
    registry = load_battle_registry(workspace_root / REGISTRY_PATH)
    decisions = _load_cycle_adjudications(workspace_root)
    d_by_id = {
        row["ruler_id"]: row
        for row in build_south_song_d_preview(workspace_root)["rulers"]
    }
    rows: list[dict[str, Any]] = []
    for decision in decisions:
        raw_cycles = iter_post_tang_bound_cycles(
            registry, str(decision["ruler_id"])
        )
        route_decision = {
            "ruler_name": decision["ruler_name"],
            "third_item_cycle_merges": decision.get("cycle_merges") or [],
            "third_item_route_overrides": decision.get("route_overrides") or [],
            "third_item_cycle_exclusions": [],
            "admitted_large_rebellion_refs": list(
                decision.get("admitted_large_rebellion_refs") or ()
            ),
        }
        cycles, _ = _third_item_cycles(route_decision, raw_cycles)
        known_refs = {str(cycle["campaign_group_ref"]) for cycle in cycles}

        ab = decision["AB"]
        axes = {
            axis: (
                _axis_a(axis, ab[axis])
                if axis.startswith("A")
                else _axis_b(axis, ab[axis])
            )
            for axis in ("A1", "A2", "B1", "B2", "B4")
        }
        start = float(ab["B1"]["start_equivalent"])
        end = float(ab["B1"]["end_equivalent"])
        weighted = round(0.6 * (end - start) + 0.4 * end, 3)
        expected_grade = _expected_b1_grade(weighted)
        if int(ab["B1"]["grade"]) != expected_grade:
            raise ValueError(
                f"{decision['ruler_name']} B1档位不符合加权控制值{weighted}: "
                f"应为B1-{expected_grade}"
            )
        contribution_type = str(ab["control_contribution_type"])
        cap = CONTROL_CONTRIBUTION_CAPS.get(contribution_type)
        if cap is None:
            raise ValueError(f"{decision['ruler_name']}控制成果归责类型非法")
        if any(int(ab[axis]["grade"]) > cap for axis in ("B2", "B4")):
            raise ValueError(f"{decision['ruler_name']} B2/B4超过归责上限{cap}")
        ab_points = round(sum(axis["axis_points"] for axis in axes.values()), 2)

        c = decision["C"]
        c1, c2, c3 = (int(c[key]) for key in ("C1", "C2", "C3"))
        ceiling = 3 if len(cycles) <= 1 else 4 if len(cycles) == 2 else 5
        if c1 > ceiling or c3 > ceiling:
            raise ValueError(f"{decision['ruler_name']} C1/C3超过证据任务上限{ceiling}")
        failures = list(dict.fromkeys(str(ref) for ref in c.get("major_system_failure_group_refs") or ()))
        successes = list(dict.fromkeys(str(ref) for ref in c.get("major_system_success_group_refs") or ()))
        unknown_refs = sorted((set(failures) | set(successes)) - known_refs)
        if unknown_refs:
            raise ValueError(
                f"{decision['ruler_name']} C项重大胜负引用不属于本人父周期: {unknown_refs}"
            )
        c_grade, c_rate, c_points, c_surplus = _c_score(c1, c2, c3)
        grade_number = min(c1, c2, c3)
        required_successes = max(1, len(failures)) if grade_number >= 4 else 0
        if len(successes) < required_successes:
            raise ValueError(
                f"{decision['ruler_name']} C4/C5重大胜绩门禁未通过: "
                f"需{required_successes}项，实有{len(successes)}项"
            )

        d = d_by_id[decision["ruler_id"]]
        d_points = d["D_preview_score_points"]
        rows.append({
            "ruler_id": decision["ruler_id"],
            "ruler_name": decision["ruler_name"],
            "reign_range": decision["reign_range"],
            "AB_preview_score_points": ab_points,
            "AB_axes": axes,
            "B1_weighted_control_value": weighted,
            "control_contribution_type": contribution_type,
            "C_preview_grade": c_grade,
            "C_preview_score_rate": c_rate,
            "C_preview_score_points": c_points,
            "C_score_support_surplus": c_surplus,
            "major_system_failure_refs": failures,
            "major_system_success_refs": successes,
            "D_preview_grade": d["D_preview_grade"],
            "D_preview_score_points": d_points,
            "D_material_return_closure_rate": d["material_return_closure_rate"],
            "third_item_preview_score_points": (
                round(ab_points + c_points + float(d_points), 2)
                if d_points is not None else None
            ),
            "formal_score_write": False,
        })
    return {
        "schema_version": "south-song-third-item-abc-preview-v1",
        "formal_score_write": False,
        "score_ceiling_points": 250,
        "ruler_count": len(rows),
        "rulers": rows,
    }


def _formal_decisions(workspace_root: Path) -> list[dict[str, Any]]:
    decisions = []
    for raw in _load_cycle_adjudications(workspace_root):
        decision = dict(raw)
        decision.update({
            "polity": "南宋",
            "third_item_cycle_merges": raw.get("cycle_merges") or [],
            "third_item_route_overrides": raw.get("route_overrides") or [],
            "third_item_cycle_exclusions": [],
            "admitted_large_rebellion_refs": list(
                decision.get("admitted_large_rebellion_refs") or ()
            ),
        })
        decisions.append(decision)
    return decisions


def _north_song_consumer_view(registry: Mapping[str, Any]) -> dict[str, Any]:
    """Expose South Song phases to the reviewed North Song ABC row builders."""
    records = []
    for raw in registry.get("records") or ():
        row = dict(raw)
        if (
            row.get("dynasty_partition") == "south_song"
            and row.get("third_item_phase_container")
        ):
            row["dynasty_partition"] = "north_song"
        records.append(row)
    return {**registry, "records": records}


def build_south_song_formal_payloads(
    workspace_root: Path, registry: Mapping[str, Any]
) -> dict[str, Any]:
    decisions = _formal_decisions(workspace_root)
    consumer_registry = _north_song_consumer_view(registry)
    ab_rows = build_north_song_ab_records(consumer_registry, decisions)
    c_rows = build_north_song_c_records(consumer_registry, decisions)
    d_rows = build_north_song_d_records(
        consumer_registry, decisions, ab_rows, c_rows
    )
    combined_rows = _build_north_song_combined(
        decisions, ab_rows, c_rows, d_rows
    )
    for row in ab_rows:
        row.update({"polity": "南宋", "partition": "南宋"})
        row["rationale"] = "按南宋主体阶段卡、互斥主政窗口及父周期终局裁决完成结算。"
    for row in c_rows:
        row.update({"polity": "南宋", "partition": "南宋"})
    for row in d_rows:
        row["polity"] = "南宋"
    for row in combined_rows:
        row.update({"polity": "南宋", "partition": "南宋"})

    ab = _replace_partition_records(
        json.loads((workspace_root / AB_PATH).read_text(encoding="utf-8")),
        ab_rows,
    )
    c = _replace_partition_records(
        json.loads((workspace_root / C_PATH).read_text(encoding="utf-8")),
        c_rows,
    )
    d = _replace_partition_records(
        json.loads((workspace_root / D_PATH).read_text(encoding="utf-8")),
        d_rows,
    )
    combined = _replace_partition_records(
        json.loads((workspace_root / FORMAL_PATH).read_text(encoding="utf-8")),
        combined_rows,
    )
    for row in c["records"]:
        row.pop("confidence", None)
    _normalize_qin_tang_bc_parent_cycles(
        workspace_root, ab["records"], c["records"]
    )
    _validate_formal_abc_contracts(ab["records"], c["records"])
    _recalculate_qin_tang_d_records(
        workspace_root, d["records"], ab["records"], c["records"]
    )
    _normalize_formal_d_records(d["records"])
    _align_bc_to_system_stress_parent_cycles(
        workspace_root, ab["records"], c["records"], d["records"]
    )
    _validate_bc_parent_cycle_alignment(ab["records"], c["records"])
    _validate_formal_abc_contracts(ab["records"], c["records"])
    _validate_d_empirical_calibration(d["records"])
    _sync_formal_ab_into_combined(ab["records"], combined["records"])
    _sync_formal_c_into_combined(c["records"], combined["records"])
    _sync_formal_d_into_combined(d["records"], combined["records"])
    _assign_global_third_item_ranks(combined["records"])
    for row in combined["records"]:
        row["military_long_term_debt"] = {
            "status": "PENDING_ITEM_7_SETTLEMENT",
            "score_points": None,
            "included_in_third_item_total": False,
        }
    partition_ids = {str(row["ruler_id"]) for row in combined_rows}
    partition_rows = [
        row for row in combined["records"]
        if str(row.get("ruler_id")) in partition_ids
    ]
    for rank, row in enumerate(
        sorted(partition_rows, key=lambda item: -float(item["third_item_score_points"])),
        start=1,
    ):
        row["partition_rank"] = rank
    total = len(combined["records"])
    for payload, count_key in (
        (ab, "ruler_count"), (c, "record_count"), (d, "record_count")
    ):
        payload[count_key] = len(payload["records"])
        payload["scope"] = "秦至北宋118人当前结算 + 南宋5人当前结算"
        payload["south_song_parent_cycle_config"] = CYCLE_ADJUDICATION_PATH.as_posix()
    ab.update({
        "reviewed_count": sum(row.get("adjudication_status") == "REVIEWED" for row in ab["records"]),
        "pending_count": sum(not row.get("score_ready") for row in ab["records"]),
        "score_ready_count": sum(bool(row.get("score_ready")) for row in ab["records"]),
    })
    c.update({
        "score_ready_count": sum(bool(row.get("score_ready")) for row in c["records"]),
        "partition_counts": dict(sorted(Counter(str(row.get("partition")) for row in c["records"]).items())),
        "grade_distribution": dict(sorted(Counter(str(row.get("C_overall_grade")) for row in c["records"]).items())),
    })
    d["grade_distribution"] = dict(sorted(Counter(str(row.get("D_grade")) for row in d["records"]).items()))
    combined.update({
        "scope": f"秦至南宋{total}人统一第三项当前排名",
        "record_count": total,
        "score_ready_count": sum(row.get("third_item_score_points") is not None for row in combined["records"]),
        "D_no_material_exposure_count": sum((row.get("axes") or {}).get("D") == "D-N" for row in combined["records"]),
        "D_pending_count": sum(row.get("D_score_points") is None for row in combined["records"]),
        "south_song_ready_count": sum(row.get("third_item_score_points") is not None for row in partition_rows),
        "south_song_pending_count": sum(row.get("third_item_score_points") is None for row in partition_rows),
        "south_song_parent_cycle_config": CYCLE_ADJUDICATION_PATH.as_posix(),
        "military_long_term_debt_policy": "PENDING_ITEM_7_NOT_INCLUDED_IN_THIRD_ITEM_STAGE_TOTAL",
        "score_recalculation_policy": "ALL_RECORDS_REVIEWABLE_CURRENT_VALUE",
        "global_ranking_enabled": True,
        "rank_tie_policy": "COMPETITION_RANK",
        "shared_source_root": "docs/史料通读产物",
    })
    return {
        "AB": ab, "C": c, "D": d, "combined": combined,
        "partition_records": partition_rows,
    }


def write_south_song_third_item(workspace_root: Path) -> dict[str, Any]:
    registry = load_battle_registry(workspace_root / REGISTRY_PATH)
    payloads = build_south_song_formal_payloads(workspace_root, registry)
    paths = {"AB": AB_PATH, "C": C_PATH, "D": D_PATH, "combined": FORMAL_PATH}
    for kind, path in paths.items():
        _write_text_atomic(
            workspace_root / path,
            json.dumps(payloads[kind], ensure_ascii=False, indent=2) + "\n",
        )
        renderer = _render_combined_markdown if kind == "combined" else lambda rows, current_kind=kind: _render_formal_markdown(current_kind, rows)
        _write_text_atomic(
            workspace_root / path.with_suffix(".md"),
            renderer(payloads[kind]["records"]),
        )
    return {
        "formal_ready_count": sum(row["third_item_score_points"] is not None for row in payloads["partition_records"]),
        "formal_pending_count": sum(row["third_item_score_points"] is None for row in payloads["partition_records"]),
        "hashes": {
            kind: sha256((workspace_root / path).read_bytes()).hexdigest()
            for kind, path in paths.items()
        },
        "records": payloads["partition_records"],
    }
