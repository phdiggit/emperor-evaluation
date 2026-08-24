from __future__ import annotations

import json
import re
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Sequence

from emperor_v4.evaluation.battle_registry_store import load_battle_registry
from emperor_v4.evaluation.five_dynasties_third_item import (
    AB_PATH,
    C_PATH,
    CONTROL_CONTRIBUTION_CAPS,
    D_PATH,
    FORMAL_PATH,
    _build_public_d_analysis,
    _partition_public_d_analysis,
    _sync_public_d_q_into_combined,
    _aggregate_parent_cycle_audit,
    _assign_global_third_item_ranks,
    _axis_a,
    _axis_b,
    _c_score,
    _expected_b1_grade,
    _normalize_qin_tang_bc_parent_cycles,
    _render_combined_markdown,
    _render_formal_markdown,
    _replace_partition_records,
    _sync_formal_ab_into_combined,
    _sync_formal_c_into_combined,
    _third_item_cycles,
    _validate_bc_parent_cycle_alignment,
    _validate_formal_abc_contracts,
    _write_text_atomic,
    write_third_item_d_formal_settlement,
)
from emperor_v4.evaluation.north_song_third_item import (
    _build_combined as _build_north_song_combined,
    build_north_song_ab_records,
    build_north_song_c_records,
)
from emperor_v4.evaluation.post_tang_third_item_consumption import (
    REGISTRY_PATH,
    iter_post_tang_bound_cycles,
)
from emperor_v4.evaluation.south_song_third_item import (
    FIRST_ITEM_PATH,
    _cycle_axis_audit,
    _has_founding_phase,
)


ADJUDICATION_PATH = Path("config/third-item/yuan-third-item-cycle-adjudications.json")


def _load_adjudications(workspace_root: Path) -> list[dict[str, Any]]:
    payload = json.loads((workspace_root / ADJUDICATION_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "yuan-third-item-cycle-adjudications-v1":
        raise ValueError("元朝第三项周期裁决schema错误")
    if payload.get("status") != "CURRENT":
        raise ValueError("元朝第三项周期裁决不是当前值")
    rows = [dict(row) for row in payload.get("rulers") or ()]
    exclusions_by_id = {
        str(item["ruler_id"]): list(item.get("exclusions") or ())
        for item in payload.get("reviewed_large_rebellion_exclusions") or ()
    }
    for row in rows:
        row["large_rebellion_audit_status"] = payload.get(
            "large_rebellion_audit_status"
        )
        row["reviewed_large_rebellion_exclusions"] = exclusions_by_id.get(
            str(row["ruler_id"]), []
        )
    if len(rows) != 8 or len({row["ruler_id"] for row in rows}) != 8:
        raise ValueError("元朝第三项裁决必须唯一覆盖8个主政窗口")
    return rows


def _cycle_years(cycle: Mapping[str, Any]) -> tuple[int, int] | None:
    years = [int(value) for value in re.findall(r"(?<!\d)(1[0-9]{3})(?!\d)", str(cycle["campaign_group_ref"]))]
    return (min(years), max(years)) if years else None


def _is_first_item_cycle(cycle: Mapping[str, Any], exclusion: Mapping[str, Any]) -> tuple[bool, str | None]:
    mode = str(exclusion["mode"])
    if mode == "NONE":
        return False, None
    if mode == "FOUNDING_FLAG_ONLY":
        return (
            (True, "FOUNDING_FLAG")
            if _has_founding_phase(cycle)
            else (False, None)
        )
    if mode != "FOUNDING_FLAG_PLUS_EXPLICIT_WINDOW":
        raise ValueError(f"元朝第一项排除模式非法: {mode}")
    ref = str(cycle["campaign_group_ref"])
    retained = {str(value) for value in exclusion.get("retain_campaign_group_refs") or ()}
    if ref in retained:
        return False, "EXPLICIT_NON_FIRST_ITEM_RETAIN"
    years = _cycle_years(cycle)
    if years and int(exclusion["start_year"]) <= years[0] and years[1] <= int(exclusion["end_year"]):
        return True, "EXPLICIT_FIRST_ITEM_WINDOW"
    if _has_founding_phase(cycle):
        return False, "FOUNDING_FLAG_OUTSIDE_EXPLICIT_WINDOW_RETAINED"
    return False, None


def build_yuan_cycle_admission_audit(workspace_root: Path) -> dict[str, Any]:
    registry = load_battle_registry(workspace_root / REGISTRY_PATH)
    first = json.loads((workspace_root / FIRST_ITEM_PATH).read_text(encoding="utf-8"))
    first_by_name = {str(row["ruler_name"]): row for row in first["records"]}
    rows = []
    for decision in _load_adjudications(workspace_root):
        raw_cycles = iter_post_tang_bound_cycles(
            registry,
            str(decision["ruler_id"]),
            ruler_name=str(decision["ruler_name"]),
            polity="yuan",
        )
        first_row = first_by_name.get(str(decision["ruler_name"]))
        obtained = bool(first_row and first_row.get("score_applicable") and float(first_row.get("first_item_score_points") or 0) > 0)
        admitted = []
        excluded = []
        retained_window = []
        for cycle in raw_cycles:
            should_exclude, basis = _is_first_item_cycle(cycle, decision["first_item_exclusion"])
            if obtained and should_exclude:
                excluded.append((cycle, basis))
            else:
                admitted.append(cycle)
                if basis == "EXPLICIT_NON_FIRST_ITEM_RETAIN":
                    retained_window.append(str(cycle["campaign_group_ref"]))
        audits = [_cycle_axis_audit(cycle) for cycle in admitted]
        rows.append({
            "ruler_id": decision["ruler_id"],
            "ruler_name": decision["ruler_name"],
            "actual_first_item_score_points": None if first_row is None else first_row.get("first_item_score_points"),
            "raw_bound_cycle_count": len(raw_cycles),
            "admitted_cycle_count": len(admitted),
            "excluded_first_item_cycle_count": len(excluded),
            "excluded_by_founding_flag_count": sum(basis == "FOUNDING_FLAG" for _, basis in excluded),
            "excluded_by_explicit_window_count": sum(basis == "EXPLICIT_FIRST_ITEM_WINDOW" for _, basis in excluded),
            "retained_explicit_non_first_item_refs": retained_window,
            "admitted_phase_count": sum(len(cycle["phases"]) for cycle in admitted),
            "material_cycle_count": sum(audit["material"] for audit in audits),
            "unknown_axis_cycle_count": sum(bool(audit["unknown_axes"]) for audit in audits),
        })
    return {
        "schema_version": "yuan-third-item-cycle-admission-audit-v1",
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


def _first_item_score_by_name(workspace_root: Path) -> dict[str, Mapping[str, Any]]:
    payload = json.loads((workspace_root / FIRST_ITEM_PATH).read_text(encoding="utf-8"))
    return {str(row["ruler_name"]): row for row in payload["records"]}


def _route_decision(
    decision: Mapping[str, Any],
    raw_cycles: Sequence[Mapping[str, Any]],
    first_item_row: Mapping[str, Any] | None,
) -> dict[str, Any]:
    obtained = bool(
        first_item_row
        and first_item_row.get("score_applicable")
        and float(first_item_row.get("first_item_score_points") or 0) > 0
    )
    exclusions = []
    generated_retain_overrides = []
    for cycle in raw_cycles:
        should_exclude, basis = _is_first_item_cycle(
            cycle, decision["first_item_exclusion"]
        )
        ref = str(cycle["campaign_group_ref"])
        if obtained and should_exclude and basis == "EXPLICIT_FIRST_ITEM_WINDOW":
            exclusions.append({
                "campaign_group_ref": ref,
                "reason": (
                    "第一项已取得正分，且本周期落入显式统一贡献窗口；"
                    "第三项不得机械重复消费。"
                ),
            })
        elif obtained and basis in {
            "FOUNDING_FLAG_OUTSIDE_EXPLICIT_WINDOW_RETAINED",
            "EXPLICIT_NON_FIRST_ITEM_RETAIN",
        }:
            generated_retain_overrides.append({
                "campaign_group_ref": ref,
                "d_route": "D_EXTERNAL_OR_FRONTIER",
                "reason": (
                    "本周期经显式裁决不属于第一项已消费结果；"
                    "第三项必须保留其成本收益，创业标记不得再次吞掉该周期。"
                ),
            })
        elif not obtained and _has_founding_phase(cycle):
            generated_retain_overrides.append({
                "campaign_group_ref": ref,
                "d_route": "D_EXTERNAL_OR_FRONTIER",
                "reason": "第一项未取得正分，创业标记不得导致该军事周期两项皆不计。",
            })
    configured_overrides = {
        str(row["campaign_group_ref"]): dict(row)
        for row in decision.get("route_overrides") or ()
    }
    for row in generated_retain_overrides:
        configured_overrides.setdefault(str(row["campaign_group_ref"]), row)
    return {
        "ruler_name": decision["ruler_name"],
        "third_item_cycle_merges": decision.get("cycle_merges") or [],
        "third_item_route_overrides": list(configured_overrides.values()),
        "third_item_cycle_exclusions": exclusions,
        "admitted_large_rebellion_refs": (
            decision.get("admitted_large_rebellion_refs") or []
        ),
    }


def _reviewed_cycles(
    workspace_root: Path,
    registry: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    raw_cycles = iter_post_tang_bound_cycles(
        registry,
        str(decision["ruler_id"]),
        ruler_name=str(decision["ruler_name"]),
        polity="yuan",
    )
    first_row = _first_item_score_by_name(workspace_root).get(
        str(decision["ruler_name"])
    )
    included, excluded = _third_item_cycles(
        _route_decision(decision, raw_cycles, first_row), raw_cycles
    )
    return raw_cycles, included, excluded


def build_yuan_parent_cycle_audit(workspace_root: Path) -> dict[str, Any]:
    registry = load_battle_registry(workspace_root / REGISTRY_PATH)
    rows = []
    all_phase_ids: list[str] = []
    for decision in _load_adjudications(workspace_root):
        raw, cycles, excluded = _reviewed_cycles(
            workspace_root, registry, decision
        )
        audits = [_aggregate_parent_cycle_audit(cycle) for cycle in cycles]
        phase_ids = [
            str(phase_id) for cycle in cycles for phase_id in cycle["phase_ids"]
        ]
        all_phase_ids.extend(phase_ids)
        rows.append({
            "ruler_id": decision["ruler_id"],
            "ruler_name": decision["ruler_name"],
            "raw_bound_cycle_count": len(raw),
            "reviewed_parent_cycle_count": len(cycles),
            "excluded_first_item_cycle_count": len(excluded),
            "cycle_merge_count": len(decision.get("cycle_merges") or ()),
            "merged_member_cycle_count": sum(
                len(spec["member_campaign_group_refs"])
                for spec in decision.get("cycle_merges") or ()
            ),
            "explicit_route_override_count": len(
                decision.get("route_overrides") or ()
            ),
            "route_counts": dict(sorted(Counter(
                str(audit["route"]) for audit in audits
            ).items())),
            "material_parent_cycle_count": sum(
                bool(audit["material"]) for audit in audits
            ),
            "unknown_axis_parent_cycle_count": sum(
                bool(audit["unknown_axes"]) for audit in audits
            ),
            "consumed_phase_count": len(phase_ids),
        })
    if len(all_phase_ids) != len(set(all_phase_ids)):
        raise ValueError("元朝第三项父周期之间重复消费主体阶段")
    return {
        "schema_version": "yuan-third-item-parent-cycle-audit-v1",
        "source_registry": REGISTRY_PATH.as_posix(),
        "source_adjudications": ADJUDICATION_PATH.as_posix(),
        "ruler_count": len(rows),
        "raw_bound_cycle_count": sum(row["raw_bound_cycle_count"] for row in rows),
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


def build_yuan_d_preview(workspace_root: Path) -> dict[str, Any]:
    payload = _partition_public_d_analysis(
        _build_public_d_analysis(workspace_root),
        (str(row["ruler_id"]) for row in _load_adjudications(workspace_root)),
    )
    payload["formal_score_write"] = False
    payload["preview_only"] = True
    return payload


def build_yuan_abc_preview(workspace_root: Path) -> dict[str, Any]:
    registry = load_battle_registry(workspace_root / REGISTRY_PATH)
    d_by_id = {
        row["subject_ruler_id"]: row
        for row in build_yuan_d_preview(workspace_root)["records"]
    }
    rows = []
    for decision in _load_adjudications(workspace_root):
        _, cycles, _ = _reviewed_cycles(workspace_root, registry, decision)
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

        c = decision["C"]
        c1, c2, c3 = (int(c[key]) for key in ("C1", "C2", "C3"))
        ceiling = 3 if len(cycles) <= 1 else 4 if len(cycles) == 2 else 5
        if c1 > ceiling or c3 > ceiling:
            raise ValueError(f"{decision['ruler_name']} C1/C3超过证据任务上限{ceiling}")
        failures = list(dict.fromkeys(
            str(ref) for ref in c.get("major_system_failure_group_refs") or ()
        ))
        successes = list(dict.fromkeys(
            str(ref) for ref in c.get("major_system_success_group_refs") or ()
        ))
        unknown_refs = sorted((set(failures) | set(successes)) - known_refs)
        if unknown_refs:
            raise ValueError(
                f"{decision['ruler_name']} C项重大胜负引用不属于本人父周期: {unknown_refs}"
            )
        if max(c1, c2, c3) >= 4 and not successes:
            raise ValueError(
                f"{decision['ruler_name']} 任一C子轴到4档必须引用至少一项重大体系成功"
            )
        c_grade, c_rate, c_points, c_surplus = _c_score(c1, c2, c3)
        if min(c1, c2, c3) >= 4 and len(successes) < max(1, len(failures)):
            raise ValueError(f"{decision['ruler_name']} C4/C5重大胜绩门禁未通过")
        d = d_by_id[decision["ruler_id"]]
        ab_points = round(sum(axis["axis_points"] for axis in axes.values()), 2)
        d_metrics = d["D_portfolio_metrics"]
        rows.append({
            "ruler_id": decision["ruler_id"],
            "ruler_name": decision["ruler_name"],
            "AB_preview_score_points": ab_points,
            "AB_axes": axes,
            "B1_weighted_control_value": weighted,
            "C_preview_grade": c_grade,
            "C_preview_score_points": c_points,
            "C_score_support_surplus": c_surplus,
            "D_preview_status": "PUBLIC_LINEAR_Q_CURRENT_SCORE_MAPPING_PENDING",
            "D_linear_Q": d_metrics["Q"],
            "D_linear_Q_mean": d_metrics["Q_mean"],
            "D_cycle_count": d_metrics["T"],
            "D_preview_score_points": None,
            "third_item_preview_score_points": None,
        })
    return {
        "schema_version": "yuan-third-item-abc-preview-v1",
        "formal_score_write": False,
        "ruler_count": len(rows),
        "rulers": rows,
    }


def _formal_decisions(
    workspace_root: Path, registry: Mapping[str, Any]
) -> list[dict[str, Any]]:
    first_by_name = _first_item_score_by_name(workspace_root)
    rows = []
    for raw in _load_adjudications(workspace_root):
        raw_cycles = iter_post_tang_bound_cycles(
            registry,
            str(raw["ruler_id"]),
            ruler_name=str(raw["ruler_name"]),
            polity="yuan",
        )
        route = _route_decision(
            raw, raw_cycles, first_by_name.get(str(raw["ruler_name"]))
        )
        decision = dict(raw)
        decision.update({
            "polity": "元",
            "third_item_cycle_merges": route["third_item_cycle_merges"],
            "third_item_route_overrides": route["third_item_route_overrides"],
            "third_item_cycle_exclusions": route["third_item_cycle_exclusions"],
            "admitted_large_rebellion_refs": route["admitted_large_rebellion_refs"],
            "terminal_polity_collapse": raw["ruler_id"] == "RULER-YUAN-TOGHON-TEMUR",
        })
        rows.append(decision)
    return rows


def _north_song_consumer_view(registry: Mapping[str, Any]) -> dict[str, Any]:
    records = []
    for raw in registry.get("records") or ():
        row = dict(raw)
        has_yuan_phase = any(
            str((phase.get("ruler_binding") or {}).get("ruler_id") or "").startswith(
                "RULER-YUAN-"
            )
            for phase in row.get("subject_phase_views") or ()
        )
        if has_yuan_phase and row.get("third_item_phase_container"):
            row["dynasty_partition"] = "north_song"
        records.append(row)
    return {**registry, "records": records}


def build_yuan_formal_payloads(
    workspace_root: Path, registry: Mapping[str, Any]
) -> dict[str, Any]:
    decisions = _formal_decisions(workspace_root, registry)
    consumer_registry = _north_song_consumer_view(registry)
    ab_rows = build_north_song_ab_records(consumer_registry, decisions)
    c_rows = build_north_song_c_records(consumer_registry, decisions)
    d = _build_public_d_analysis(workspace_root)
    decision_id_by_name = {
        str(row["ruler_name"]): str(row["ruler_id"]) for row in decisions
    }
    public_id_by_name = {
        str(row["ruler_name"]): str(row["subject_ruler_id"])
        for row in d["records"]
        if str(row.get("ruler_name") or "") in decision_id_by_name
    }
    partition_d = _partition_public_d_analysis(
        d, public_id_by_name.values()
    )
    for key in ("records", "ruler_summaries"):
        for row in partition_d[key]:
            row["subject_ruler_id"] = decision_id_by_name[str(row["ruler_name"])]
    combined_rows = _build_north_song_combined(
        decisions, ab_rows, c_rows, partition_d["records"]
    )
    for row in ab_rows:
        row.update({"polity": "元", "partition": "元"})
        row["rationale"] = "按元朝主体阶段卡、第一项显式统一窗口及D父周期裁决完成结算。"
    for row in c_rows:
        row.update({"polity": "元", "partition": "元"})
    for row in combined_rows:
        row.update({"polity": "元", "partition": "元"})

    ab = _replace_partition_records(
        json.loads((workspace_root / AB_PATH).read_text(encoding="utf-8")), ab_rows
    )
    c = _replace_partition_records(
        json.loads((workspace_root / C_PATH).read_text(encoding="utf-8")), c_rows
    )
    combined = _replace_partition_records(
        json.loads((workspace_root / FORMAL_PATH).read_text(encoding="utf-8")),
        combined_rows,
    )
    for row in c["records"]:
        row.pop("confidence", None)
    _normalize_qin_tang_bc_parent_cycles(workspace_root, ab["records"], c["records"])
    _validate_formal_abc_contracts(ab["records"], c["records"])
    _validate_bc_parent_cycle_alignment(ab["records"], c["records"])
    _validate_formal_abc_contracts(ab["records"], c["records"])
    _sync_formal_ab_into_combined(ab["records"], combined["records"])
    _sync_formal_c_into_combined(c["records"], combined["records"])
    _sync_public_d_q_into_combined(d, combined["records"])
    _assign_global_third_item_ranks(combined["records"])
    for row in combined["records"]:
        row["military_long_term_debt"] = {
            "status": "PENDING_ITEM_7_SETTLEMENT",
            "score_points": None,
            "included_in_third_item_total": False,
        }
    partition_ids = {str(row["ruler_id"]) for row in combined_rows}
    partition_rows = [
        row for row in combined["records"] if str(row.get("ruler_id")) in partition_ids
    ]
    for rank, row in enumerate(
        sorted(
            partition_rows,
            key=lambda item: (
                item["third_item_score_points"] is None,
                -float(item["third_item_score_points"] or 0),
            ),
        ),
        start=1,
    ):
        row["partition_rank"] = rank if row["third_item_score_points"] is not None else None
    total = len(combined["records"])
    for payload, count_key in ((ab, "ruler_count"), (c, "record_count"), (d, "record_count")):
        payload[count_key] = len(payload["records"])
        payload["scope"] = "秦至南宋123人当前结算 + 元朝8人当前结算"
        payload["yuan_parent_cycle_config"] = ADJUDICATION_PATH.as_posix()
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
    combined.update({
        "scope": f"秦至元{total}人统一第三项当前排名",
        "record_count": total,
        "score_ready_count": sum(row.get("third_item_score_points") is not None for row in combined["records"]),
        "D_zero_cycle_subject_count": sum(int(row.get("D_cycle_count") or 0) == 0 for row in combined["records"]),
        "D_pending_count": sum(row.get("D_score_points") is None for row in combined["records"]),
        "yuan_ready_count": sum(row.get("third_item_score_points") is not None for row in partition_rows),
        "yuan_pending_count": sum(row.get("third_item_score_points") is None for row in partition_rows),
        "yuan_parent_cycle_config": ADJUDICATION_PATH.as_posix(),
        "military_long_term_debt_policy": "PENDING_ITEM_7_NOT_INCLUDED_IN_THIRD_ITEM_STAGE_TOTAL",
        "D_q_source_policy": "PUBLIC_MILITARY_ACTION_COST_BENEFIT_REGISTRY_ONLY",
        "global_ranking_enabled": False,
        "rank_tie_policy": "COMPETITION_RANK",
        "shared_source_root": "docs/史料通读产物",
    })
    return {"AB": ab, "C": c, "D": d, "combined": combined, "partition_records": partition_rows}


def write_yuan_third_item(workspace_root: Path) -> dict[str, Any]:
    registry = load_battle_registry(workspace_root / REGISTRY_PATH)
    payloads = build_yuan_formal_payloads(workspace_root, registry)
    paths = {"AB": AB_PATH, "C": C_PATH}
    for kind, path in paths.items():
        _write_text_atomic(
            workspace_root / path,
            json.dumps(payloads[kind], ensure_ascii=False, indent=2) + "\n",
        )
        _write_text_atomic(
            workspace_root / path.with_suffix(".md"),
            _render_formal_markdown(kind, payloads[kind]["records"]),
        )
    write_third_item_d_formal_settlement(workspace_root)
    paths["D"] = D_PATH
    from emperor_v4.evaluation.third_item_current_settlement import (
        write_current_third_item_settlement,
    )

    current_payload = write_current_third_item_settlement(workspace_root)
    paths["combined"] = FORMAL_PATH
    partition_ids = {
        str(row["ruler_id"]) for row in payloads["partition_records"]
    }
    current_partition_records = [
        row for row in current_payload["records"]
        if str(row.get("ruler_id")) in partition_ids
    ]
    return {
        "formal_ready_count": sum(row["third_item_score_points"] is not None for row in current_partition_records),
        "formal_pending_count": sum(row["third_item_score_points"] is None for row in current_partition_records),
        "hashes": {kind: sha256((workspace_root / path).read_bytes()).hexdigest() for kind, path in paths.items()},
        "records": current_partition_records,
    }
