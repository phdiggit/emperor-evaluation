from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from emperor_v4.evaluation.battle_registry_store import load_battle_registry
from emperor_v4.evaluation.five_dynasties_third_item import (
    AB_PATH,
    C_PATH,
    CONTROL_CONTRIBUTION_CAPS,
    D_PATH,
    FORMAL_PATH,
    _align_bc_to_system_stress_parent_cycles,
    _assign_global_third_item_ranks,
    _axis_a,
    _axis_b,
    _c_score,
    _d_grade_and_score,
    _expected_b1_grade,
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
    validate_ab_shared_handoffs,
)
from emperor_v4.evaluation.north_song_third_item import (
    _aggregate_d_cycle,
    _build_combined as _build_north_song_combined,
    build_north_song_ab_records,
    build_north_song_c_records,
    build_north_song_d_records,
)
from emperor_v4.evaluation.post_tang_third_item_consumption import (
    REGISTRY_PATH,
    iter_post_tang_bound_cycles,
)
from emperor_v4.evaluation.south_song_third_item import (
    FIRST_ITEM_PATH,
    _cycle_axis_audit,
)
from emperor_v4.evaluation.yuan_third_item import (
    _first_item_score_by_name,
    _is_first_item_cycle,
    _reviewed_cycles as _base_reviewed_cycles,
)


ADJUDICATION_PATH = Path("config/ming-third-item-cycle-adjudications.json")


def _reviewed_cycles(workspace_root: Path, registry: dict[str, Any], decision: dict[str, Any]):
    registry = _north_song_consumer_view(workspace_root, registry)
    raw, cycles, excluded = _base_reviewed_cycles(workspace_root, registry, decision)
    for cycle in cycles:
        cycle["allow_explicit_phase_return_fallback"] = True
    return raw, cycles, excluded


def _load_adjudications(workspace_root: Path) -> list[dict[str, Any]]:
    payload = json.loads((workspace_root / ADJUDICATION_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "ming-third-item-cycle-adjudications-v1":
        raise ValueError("明朝第三项周期裁决schema错误")
    if payload.get("status") != "CURRENT":
        raise ValueError("明朝第三项周期裁决不是当前值")
    rows = [dict(row) for row in payload.get("rulers") or ()]
    for row in rows:
        row["large_rebellion_audit_status"] = payload.get(
            "large_rebellion_audit_status"
        )
    if len(rows) != 17 or len({row["ruler_id"] for row in rows}) != 17:
        raise ValueError("明朝第三项裁决必须唯一覆盖17个主政窗口")
    compact_by_id = {
        str(row["ruler_id"]): dict(row)
        for row in payload.get("abc_compact_decisions") or ()
    }
    if set(compact_by_id) != {str(row["ruler_id"]) for row in rows}:
        raise ValueError("明朝第三项AB/C紧凑裁决必须唯一覆盖17个主政窗口")
    for row in rows:
        compact = compact_by_id[str(row["ruler_id"])]
        reason = str(compact["reason"])
        b1_start = float(compact["B1"][0])
        b1_end = float(compact["B1"][1])
        b1_weighted = round(0.6 * (b1_end - b1_start) + 0.4 * b1_end, 3)
        b1_reason = (
            f"非统一控制当量{b1_start:g}→{b1_end:g}，净变化"
            f"{b1_end - b1_start:g}、加权控制值{b1_weighted:g}，"
            f"据此落B1-{int(compact['B1'][2])}；只衡量控制规模与强度。"
        )
        b2_reason = (
            f"非统一军事成果的作用范围与控制强度裁为B2-{int(compact['B2'][0])}；"
            "不以单场胜负或整体安全形势代替成果规模判断。"
        )
        b4_reason = (
            f"可移交控制结构的覆盖、持续和承载强度裁为B4-{int(compact['B4'][0])}；"
            "不重复计算A项宏观边疆态势。"
        )
        row["AB"] = {
            "control_contribution_type": compact["control_contribution_type"],
            "A1": {"start": compact["A1"][0], "end": compact["A1"][1], "reason": reason},
            "A2": {"start": compact["A2"][0], "end": compact["A2"][1], "reason": reason},
            "B1": {"start_equivalent": compact["B1"][0], "end_equivalent": compact["B1"][1], "grade": compact["B1"][2], "position": compact["B1"][3], "reason": b1_reason},
            "B2": {"grade": compact["B2"][0], "position": compact["B2"][1], "reason": b2_reason},
            "B4": {"grade": compact["B4"][0], "position": compact["B4"][1], "reason": b4_reason},
        }
        row["C"] = {
            "C1": compact["C"][0], "C2": compact["C"][1], "C3": compact["C"][2],
            "major_system_failure_group_refs": list(compact.get("C_failure_refs") or ()),
            "major_system_success_group_refs": list(compact.get("C_success_refs") or ()),
            "reason": str(compact.get("C_reason") or reason),
        }
    row_by_id = {str(row["ruler_id"]): row for row in rows}
    supplements = list(payload.get("large_rebellion_supplements") or ())
    if len({str(item["ruler_id"]) for item in supplements}) != len(supplements):
        raise ValueError("明朝大型叛乱补充裁决对象重复")
    for supplement in supplements:
        ruler_id = str(supplement["ruler_id"])
        if ruler_id not in row_by_id:
            raise ValueError(f"明朝大型叛乱补充裁决对象不存在: {ruler_id}")
        row = row_by_id[ruler_id]
        row["cycle_merges"] = list(row.get("cycle_merges") or ()) + list(
            supplement.get("cycle_merges") or ()
        )
        row["route_overrides"] = list(row.get("route_overrides") or ()) + list(
            supplement.get("route_overrides") or ()
        )
        row["admitted_large_rebellion_refs"] = list(dict.fromkeys(
            list(row.get("admitted_large_rebellion_refs") or ())
            + list(supplement.get("admitted_large_rebellion_refs") or ())
        ))
        row["reviewed_large_rebellion_exclusions"] = list(
            row.get("reviewed_large_rebellion_exclusions") or ()
        ) + list(supplement.get("reviewed_large_rebellion_exclusions") or ())
    return rows


def build_ming_cycle_admission_audit(workspace_root: Path) -> dict[str, Any]:
    registry = _north_song_consumer_view(
        workspace_root, load_battle_registry(workspace_root / REGISTRY_PATH)
    )
    first_by_name = _first_item_score_by_name(workspace_root)
    rows = []
    for decision in _load_adjudications(workspace_root):
        raw_cycles = iter_post_tang_bound_cycles(registry, str(decision["ruler_id"]))
        first_row = first_by_name.get(str(decision["ruler_name"]))
        obtained = bool(first_row and first_row.get("score_applicable") and float(first_row.get("first_item_score_points") or 0) > 0)
        admitted = []
        excluded = []
        for cycle in raw_cycles:
            should_exclude, _ = _is_first_item_cycle(cycle, decision["first_item_exclusion"])
            (excluded if obtained and should_exclude else admitted).append(cycle)
        audits = [_cycle_axis_audit(cycle) for cycle in admitted]
        rows.append({
            "ruler_id": decision["ruler_id"],
            "ruler_name": decision["ruler_name"],
            "actual_first_item_score_points": None if first_row is None else first_row.get("first_item_score_points"),
            "raw_bound_cycle_count": len(raw_cycles),
            "admitted_cycle_count": len(admitted),
            "excluded_first_item_cycle_count": len(excluded),
            "admitted_phase_count": sum(len(cycle["phases"]) for cycle in admitted),
            "material_cycle_count": sum(bool(audit["material"]) for audit in audits),
            "unknown_axis_cycle_count": sum(bool(audit["unknown_axes"]) for audit in audits),
        })
    return {
        "schema_version": "ming-third-item-cycle-admission-audit-v1",
        "source_registry": REGISTRY_PATH.as_posix(),
        "source_first_item_settlement": FIRST_ITEM_PATH.as_posix(),
        "source_adjudications": ADJUDICATION_PATH.as_posix(),
        "ruler_count": len(rows),
        "raw_bound_cycle_count": sum(row["raw_bound_cycle_count"] for row in rows),
        "admitted_cycle_count": sum(row["admitted_cycle_count"] for row in rows),
        "excluded_first_item_cycle_count": sum(row["excluded_first_item_cycle_count"] for row in rows),
        "admitted_phase_count": sum(row["admitted_phase_count"] for row in rows),
        "material_cycle_count": sum(row["material_cycle_count"] for row in rows),
        "unknown_axis_cycle_count": sum(row["unknown_axis_cycle_count"] for row in rows),
        "rulers": rows,
    }


def build_ming_parent_cycle_audit(workspace_root: Path) -> dict[str, Any]:
    registry = load_battle_registry(workspace_root / REGISTRY_PATH)
    rows = []
    all_phase_ids: list[str] = []
    for decision in _load_adjudications(workspace_root):
        raw, cycles, excluded = _reviewed_cycles(workspace_root, registry, decision)
        audits = [_aggregate_d_cycle(cycle) for cycle in cycles]
        phase_ids = [str(ref) for cycle in cycles for ref in cycle["phase_ids"]]
        all_phase_ids.extend(phase_ids)
        rows.append({
            "ruler_id": decision["ruler_id"],
            "ruler_name": decision["ruler_name"],
            "raw_bound_cycle_count": len(raw),
            "reviewed_parent_cycle_count": len(cycles),
            "excluded_first_item_cycle_count": len(excluded),
            "cycle_merge_count": len(decision.get("cycle_merges") or ()),
            "merged_member_cycle_count": sum(len(spec["member_campaign_group_refs"]) for spec in decision.get("cycle_merges") or ()),
            "route_counts": dict(sorted(Counter(str(audit["route"]) for audit in audits).items())),
            "material_parent_cycle_count": sum(bool(audit["material"]) for audit in audits),
            "unknown_axis_parent_cycle_count": sum(bool(audit["unknown_axes"]) for audit in audits),
            "consumed_phase_count": len(phase_ids),
        })
    if len(all_phase_ids) != len(set(all_phase_ids)):
        raise ValueError("明朝第三项父周期之间重复消费主体阶段")
    return {
        "schema_version": "ming-third-item-parent-cycle-audit-v1",
        "reviewed_parent_cycle_count": sum(row["reviewed_parent_cycle_count"] for row in rows),
        "excluded_first_item_cycle_count": sum(row["excluded_first_item_cycle_count"] for row in rows),
        "cycle_merge_count": sum(row["cycle_merge_count"] for row in rows),
        "merged_member_cycle_count": sum(row["merged_member_cycle_count"] for row in rows),
        "material_parent_cycle_count": sum(row["material_parent_cycle_count"] for row in rows),
        "unknown_axis_parent_cycle_count": sum(row["unknown_axis_parent_cycle_count"] for row in rows),
        "consumed_phase_count": len(all_phase_ids),
        "duplicate_consumed_phase_id_count": 0,
        "rulers": rows,
    }


def build_ming_d_preview(workspace_root: Path) -> dict[str, Any]:
    registry = load_battle_registry(workspace_root / REGISTRY_PATH)
    rows = []
    for decision in _load_adjudications(workspace_root):
        _, cycles, _ = _reviewed_cycles(workspace_root, registry, decision)
        aggregated = [_aggregate_d_cycle(cycle) for cycle in cycles]
        grade, score, metrics = _d_grade_and_score(aggregated)
        rows.append({
            "ruler_id": decision["ruler_id"],
            "ruler_name": decision["ruler_name"],
            "D_preview_grade": grade,
            "D_preview_score_points": score,
            "reviewed_parent_cycle_count": len(cycles),
            "material_parent_cycle_count": metrics["material_cycle_count"],
            "known_material_parent_cycle_count": metrics["known_material_cycle_count"],
            "material_return_closure_rate": metrics["material_return_closure_rate"],
            "portfolio_efficiency_index": metrics["portfolio_efficiency_index"],
            "return_class_counts": metrics["return_class_counts"],
            "material_unknown_cycle_refs": metrics["material_unknown_cycle_refs"],
        })
    return {"schema_version": "ming-third-item-d-preview-v1", "formal_score_write": False, "ruler_count": len(rows), "rulers": rows}


def build_ming_abc_preview(workspace_root: Path) -> dict[str, Any]:
    registry = load_battle_registry(workspace_root / REGISTRY_PATH)
    d_by_id = {row["ruler_id"]: row for row in build_ming_d_preview(workspace_root)["rulers"]}
    rows = []
    for decision in _load_adjudications(workspace_root):
        _, cycles, _ = _reviewed_cycles(workspace_root, registry, decision)
        ab = decision["AB"]
        axes = {
            axis: (_axis_a(axis, ab[axis]) if axis.startswith("A") else _axis_b(axis, ab[axis]))
            for axis in ("A1", "A2", "B1", "B2", "B4")
        }
        weighted = round(
            0.6 * (float(ab["B1"]["end_equivalent"]) - float(ab["B1"]["start_equivalent"]))
            + 0.4 * float(ab["B1"]["end_equivalent"]),
            3,
        )
        if int(ab["B1"]["grade"]) != _expected_b1_grade(weighted):
            raise ValueError(f"{decision['ruler_name']} B1档位不符合加权控制值{weighted}")
        cap = CONTROL_CONTRIBUTION_CAPS[str(ab["control_contribution_type"])]
        if any(int(ab[axis]["grade"]) > cap for axis in ("B2", "B4")):
            raise ValueError(f"{decision['ruler_name']} B2/B4超过归责上限{cap}")
        c1, c2, c3 = (int(decision["C"][key]) for key in ("C1", "C2", "C3"))
        ceiling = 3 if len(cycles) <= 1 else 4 if len(cycles) == 2 else 5
        if c1 > ceiling or c3 > ceiling:
            raise ValueError(f"{decision['ruler_name']} C1/C3超过证据任务上限{ceiling}")
        c_grade, _, c_points, c_surplus = _c_score(c1, c2, c3)
        ab_points = round(sum(axis["axis_points"] for axis in axes.values()), 2)
        d = d_by_id[decision["ruler_id"]]
        d_points = d["D_preview_score_points"]
        rows.append({
            "ruler_id": decision["ruler_id"], "ruler_name": decision["ruler_name"],
            "AB_preview_score_points": ab_points, "AB_axes": axes,
            "B1_weighted_control_value": weighted,
            "C_preview_grade": c_grade, "C_preview_score_points": c_points,
            "C_score_support_surplus": c_surplus,
            "D_preview_grade": d["D_preview_grade"], "D_preview_score_points": d_points,
            "third_item_preview_score_points": (
                round(ab_points + c_points + float(d_points), 2)
                if d_points is not None else None
            ),
        })
    return {
        "schema_version": "ming-third-item-abc-preview-v1", "formal_score_write": False,
        "ruler_count": len(rows), "rulers": rows,
    }


def _formal_decisions(workspace_root: Path, registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    first_by_name = _first_item_score_by_name(workspace_root)
    rows = []
    terminal_ids = {
        "RULER-MING-ZHU-YUNWEN", "RULER-MING-ZHU-YOUJIAN",
        "RULER-MING-ZHU-YOUSONG", "RULER-MING-ZHU-YUJIAN", "RULER-MING-ZHU-YOULANG",
    }
    for raw in _load_adjudications(workspace_root):
        consumer_registry = _north_song_consumer_view(workspace_root, registry)
        raw_cycles = iter_post_tang_bound_cycles(
            consumer_registry, str(raw["ruler_id"])
        )
        from emperor_v4.evaluation.yuan_third_item import _route_decision
        route = _route_decision(raw, raw_cycles, first_by_name.get(str(raw["ruler_name"])))
        route_overrides = {
            str(item["campaign_group_ref"]): dict(item)
            for item in route["third_item_route_overrides"]
        }
        excluded_refs = {
            str(item["campaign_group_ref"])
            for item in route["third_item_cycle_exclusions"]
        }
        for cycle in raw_cycles:
            ref = str(cycle["campaign_group_ref"])
            if ref in excluded_refs:
                continue
            if any(
                bool((phase.get("founding_startup_ledger") or {}).get("is_founding_process"))
                for phase in cycle["phases"]
            ):
                continue
            fallback = route_overrides.setdefault(ref, {"campaign_group_ref": ref})
            fallback["allow_explicit_phase_return_fallback"] = True
            fallback.setdefault(
                "reason", "明朝旧卡保留明确阶段净回报类别；父级未知轴不以0代填。"
            )
        decision = dict(raw)
        decision.update({
            "polity": "明", "third_item_cycle_merges": route["third_item_cycle_merges"],
            "third_item_route_overrides": list(route_overrides.values()),
            "third_item_cycle_exclusions": route["third_item_cycle_exclusions"],
            "admitted_large_rebellion_refs": route["admitted_large_rebellion_refs"],
            "terminal_polity_collapse": raw["ruler_id"] in terminal_ids,
        })
        rows.append(decision)
    return rows


def _north_song_consumer_view(
    workspace_root: Path, registry: Mapping[str, Any]
) -> dict[str, Any]:
    payload = json.loads(
        (workspace_root / ADJUDICATION_PATH).read_text(encoding="utf-8")
    )
    phase_adjudications = list(payload.get("consumer_phase_adjudications") or ())
    binding_by_phase = {
        str(item["phase_id"]): item
        for item in phase_adjudications
        if item.get("mode") == "BIND_EXISTING_PHASE"
    }
    binding_by_group_prefix = [
        item
        for item in phase_adjudications
        if item.get("mode") == "BIND_PHASES_BY_SUBJECT_PREFIX"
    ]
    supplemental_by_source = {
        str(item["source_target_ref"]): item
        for item in phase_adjudications
        if item.get("mode") == "CREATE_SUBJECT_PHASE_FROM_PUBLIC_CONTRACT"
    }
    records = []
    for raw in registry.get("records") or ():
        row = dict(raw)
        phases = [dict(phase) for phase in row.get("subject_phase_views") or ()]
        for phase in phases:
            adjudication = binding_by_phase.get(str(phase.get("phase_id")))
            if not adjudication:
                matching = [
                    item
                    for item in binding_by_group_prefix
                    if str(row.get("campaign_group_ref")) == str(item["campaign_group_ref"])
                    and any(
                        str(phase.get("evaluation_subject_phase") or "").startswith(prefix)
                        for prefix in item.get("subject_prefixes") or ()
                    )
                ]
                if len(matching) > 1:
                    raise ValueError(
                        f"明朝完整生涯阶段归责重复: {phase.get('phase_id')}"
                    )
                adjudication = matching[0] if matching else None
            if not adjudication:
                continue
            binding = dict(phase.get("ruler_binding") or {})
            candidates = set(binding.get("candidate_ruler_ids") or ())
            if candidates and str(adjudication["ruler_id"]) not in candidates:
                raise ValueError(
                    f"明朝阶段专属归责不在原候选窗口: {phase.get('phase_id')}"
                )
            phase["ruler_binding"] = {
                "polity": "ming",
                "ruler_id": adjudication["ruler_id"],
                "ruler_name": adjudication["ruler_name"],
                "status": "BOUND_EXCLUSIVE_GOVERNING_WINDOW",
                "basis": adjudication["reason"],
            }
        supplemental = supplemental_by_source.get(str(row.get("source_target_ref")))
        if supplemental:
            if not row.get("public_outcome_registered") or not row.get("contract_adjudication"):
                raise ValueError(
                    f"明朝补充主体阶段未经过公共战役正式登记: {row.get('source_target_ref')}"
                )
            if phases:
                raise ValueError(
                    f"明朝补充主体阶段目标已有阶段，不得重复创建: {row.get('source_target_ref')}"
                )
            row["campaign_group_ref"] = supplemental["campaign_group_ref"]
            row["third_item_phase_container"] = True
            phases = [dict(supplemental["subject_phase_view"])]
        if phases:
            row["subject_phase_views"] = phases
        has_ming_phase = any(
            str((phase.get("ruler_binding") or {}).get("ruler_id") or "").startswith("RULER-MING-")
            for phase in phases
        )
        if has_ming_phase and row.get("third_item_phase_container"):
            row["dynasty_partition"] = "north_song"
        records.append(row)
    return {**registry, "records": records}


def build_ming_formal_payloads(workspace_root: Path, registry: Mapping[str, Any]) -> dict[str, Any]:
    decisions = _formal_decisions(workspace_root, registry)
    consumer_registry = _north_song_consumer_view(workspace_root, registry)
    ab_rows = build_north_song_ab_records(consumer_registry, decisions)
    c_rows = build_north_song_c_records(consumer_registry, decisions)
    d_rows = build_north_song_d_records(consumer_registry, decisions, ab_rows, c_rows)
    for row in d_rows:
        if row["ruler_id"] in {
            "RULER-MING-ZHU-YOUSONG", "RULER-MING-ZHU-YUJIAN", "RULER-MING-ZHU-YOULANG"
        }:
            row["unresolved_source_refs"] = ["MING_CHRONICLE_PUBLIC_REGISTRY_COVERAGE_AFTER_1644"]
    combined_rows = _build_north_song_combined(decisions, ab_rows, c_rows, d_rows)
    for row in ab_rows:
        row.update({"polity": "明", "partition": "明"})
        row["rationale"] = "按明朝主体阶段卡、第一项显式取得窗口及D父战役裁决完成结算。"
    for row in c_rows:
        row.update({"polity": "明", "partition": "明"})
    for row in d_rows:
        row["polity"] = "明"
    for row in combined_rows:
        row.update({"polity": "明", "partition": "明"})

    ab = _replace_partition_records(json.loads((workspace_root / AB_PATH).read_text(encoding="utf-8")), ab_rows)
    c = _replace_partition_records(json.loads((workspace_root / C_PATH).read_text(encoding="utf-8")), c_rows)
    d = _replace_partition_records(json.loads((workspace_root / D_PATH).read_text(encoding="utf-8")), d_rows)
    combined = _replace_partition_records(json.loads((workspace_root / FORMAL_PATH).read_text(encoding="utf-8")), combined_rows)
    for row in c["records"]:
        row.pop("confidence", None)
    _normalize_qin_tang_bc_parent_cycles(workspace_root, ab["records"], c["records"])
    validate_ab_shared_handoffs(workspace_root, ab["records"])
    _validate_formal_abc_contracts(ab["records"], c["records"])
    _recalculate_qin_tang_d_records(workspace_root, d["records"], ab["records"], c["records"])
    _normalize_formal_d_records(d["records"])
    _align_bc_to_system_stress_parent_cycles(workspace_root, ab["records"], c["records"], d["records"])
    _validate_bc_parent_cycle_alignment(ab["records"], c["records"])
    _validate_formal_abc_contracts(ab["records"], c["records"])
    _validate_d_empirical_calibration(d["records"])
    _sync_formal_ab_into_combined(ab["records"], combined["records"])
    _sync_formal_c_into_combined(c["records"], combined["records"])
    _sync_formal_d_into_combined(d["records"], combined["records"])
    _assign_global_third_item_ranks(combined["records"])
    for row in combined["records"]:
        row["military_long_term_debt"] = {
            "status": "PENDING_ITEM_7_SETTLEMENT", "score_points": None,
            "included_in_third_item_total": False,
        }
    partition_records = [row for row in combined["records"] if row.get("partition") == "明"]
    return {"ab": ab, "c": c, "d": d, "combined": combined, "partition_records": partition_records}


def write_ming_third_item(workspace_root: Path) -> dict[str, Any]:
    registry = load_battle_registry(workspace_root / REGISTRY_PATH)
    payloads = build_ming_formal_payloads(workspace_root, registry)
    targets = (("AB", AB_PATH, payloads["ab"]), ("C", C_PATH, payloads["c"]), ("D", D_PATH, payloads["d"]))
    for kind, path, payload in targets:
        _write_text_atomic(workspace_root / path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        _write_text_atomic((workspace_root / path).with_suffix(".md"), _render_formal_markdown(kind, payload["records"]))
    _write_text_atomic(workspace_root / FORMAL_PATH, json.dumps(payloads["combined"], ensure_ascii=False, indent=2) + "\n")
    _write_text_atomic((workspace_root / FORMAL_PATH).with_suffix(".md"), _render_combined_markdown(payloads["combined"]["records"]))
    return {"records": payloads["partition_records"], "hashes": {
        key: sha256(json.dumps(payloads[key], ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        for key in ("ab", "c", "d", "combined")
    }}
