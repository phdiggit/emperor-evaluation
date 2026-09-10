from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from emperor_v4.evaluation.formal_json_store import (
    load_json,
    load_ruler_polities,
    write_json,
)


SOURCE_PATH = Path("config/third-item/third-item-c-strategy-chain-adjudications.json")
C_PATH = Path(
    "docs/评分结算/第三项军事与边疆净收益/军事体系有效性/01-皇帝C项正式结算.json"
)

AXIS_FIELDS = {
    "C1": "combat_delivery_grade",
    "C2": "operational_sustainability_cap",
    "C3": "system_reliability_cap",
}
GRADE_RANGES = ((0, 29), (30, 44), (45, 59), (60, 74), (75, 89), (90, 100))


def _grade_number(value: object) -> int | None:
    match = re.search(r"(\d+)$", str(value or ""))
    return int(match.group(1)) if match else None


def _normalize_return_class(value: object) -> str:
    text = str(value or "UNKNOWN")
    return "PROPORTIONATE_RETURN" if text == "COMMENSURATE_RETURN" else text


def _chain_profile(chains: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    refs: dict[str, list[str]] = {}
    for chain in chains:
        chain_id = str(chain.get("chain_id") or "")
        outcome = _normalize_return_class(chain.get("terminal_result_class"))
        counts[outcome] += 1
        refs.setdefault(outcome, []).append(chain_id)
    known = sum(
        counts.get(outcome, 0)
        for outcome in (
            "HIGH_RETURN",
            "PROPORTIONATE_RETURN",
            "LOW_RETURN",
            "NEGATIVE_RETURN",
        )
    )
    return {
        "source": "CURRENT_STRATEGIC_CHAIN_RESULTS",
        "selected_chain_count": len(chains),
        "known_outcome_count": known,
        "return_class_counts": dict(sorted(counts.items())),
        "return_class_chain_refs": {
            key: refs[key] for key in sorted(refs)
        },
        "major_system_success_count": sum(
            bool(chain.get("major_system_success")) for chain in chains
        ),
        "major_system_failure_count": sum(
            bool(chain.get("major_system_failure")) for chain in chains
        ),
        "status": "QUANTIFIED" if known else "UNQUANTIFIED",
    }


def _records_by_id(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["ruler_id"]): row
        for row in payload.get("records") or ()
        if row.get("ruler_id")
    }


def _source_records_by_id(source: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    records = list(source.get("records") or ())
    indexed = {
        str(row["ruler_id"]): row
        for row in records
        if row.get("ruler_id")
    }
    if len(indexed) != len(records):
        raise ValueError("第三项C战略链正式源人物ID缺失或重复")
    return indexed


def load_strategy_chain_source(workspace_root: Path) -> dict[str, Any]:
    source = json.loads(
        (workspace_root / SOURCE_PATH).read_text(encoding="utf-8")
    )
    if source.get("schema_version") != "third-item-c-strategy-chain-adjudications-v1":
        raise ValueError("第三项C战略链正式源schema不合法")
    if source.get("canonical_status") != "FORMAL_SETTLEMENT_PATCH_SOURCE":
        raise ValueError("第三项C战略链正式源未声明为正式写回源")
    if source.get("status") != "CURRENT":
        raise ValueError("第三项C战略链正式源不是CURRENT")
    if source.get("primary_scoring_unit") != "STRATEGIC_CHAIN":
        raise ValueError("第三项C战略链正式源主评分颗粒错误")
    if source.get("parent_cycle_role") != "EVIDENCE_ONLY_AND_DISPUTE_DRILLDOWN":
        raise ValueError("第三项C战略链正式源父周期角色错误")
    records = list(source.get("records") or ())
    formal_ids = set(_records_by_id(load_json(workspace_root / C_PATH)))
    source_ids = set(_source_records_by_id(source))
    if source_ids != formal_ids:
        raise ValueError(
            f"第三项C战略链源与正式人物集合不一致：缺失{sorted(formal_ids - source_ids)}，"
            f"多余{sorted(source_ids - formal_ids)}"
        )
    for row in records:
        if not row.get("formal_writeback", {}).get("fields"):
            raise ValueError(f"{row.get('ruler_name')}缺少正式写回字段")
    return source


def apply_strategy_chain_writeback_to_payload(
    payload: Mapping[str, Any], source: Mapping[str, Any]
) -> dict[str, Any]:
    source_by_id = _source_records_by_id(source)
    output = deepcopy(dict(payload))
    output_records: list[dict[str, Any]] = []
    for row in payload.get("records") or ():
        updated = deepcopy(dict(row))
        source_row = source_by_id.get(str(row.get("ruler_id") or ""))
        if source_row is not None:
            fields = source_row["formal_writeback"]["fields"]
            for key, value in fields.items():
                updated[key] = deepcopy(value)
        output_records.append(updated)
    output["records"] = output_records
    metadata = source.get("formal_payload_metadata") or {}
    for key, value in metadata.items():
        if key != "records":
            output[key] = deepcopy(value)
    return output


def write_third_item_c_strategy_chain_settlement(
    workspace_root: Path,
) -> dict[str, Any]:
    source = load_strategy_chain_source(workspace_root)
    current = load_json(workspace_root / C_PATH)
    updated = apply_strategy_chain_writeback_to_payload(current, source)
    write_json(
        workspace_root / C_PATH,
        updated,
        ruler_polities=load_ruler_polities(workspace_root),
    )
    from emperor_v4.evaluation.five_dynasties_third_item import _render_formal_markdown

    (workspace_root / C_PATH).with_suffix(".md").write_text(
        _render_formal_markdown("C", updated["records"]),
        encoding="utf-8",
    )
    result = source.get("summary", {}).get("formal_writeback") or {}
    return {
        "status": "WRITTEN",
        "source": str(SOURCE_PATH).replace("\\", "/"),
        "record_count": len(updated.get("records") or ()),
        "final_grade_change_count": result.get("final_grade_change_count"),
        "formal_unknown_resolved_count": result.get("formal_unknown_resolved_count"),
        "remaining_unknown_names": result.get("remaining_unknown_names"),
    }


def _verify_inherited_system(row: Mapping[str, Any]) -> None:
    if row.get("final_grade") == "C-N":
        raise ValueError("C-N按零分合成已停用；须审核继承体系或保留UNKNOWN")
    if row.get("system_observation_status") != "INHERITED_UNTESTED":
        return
    evidence = row.get("inherited_system_assessment") or {}
    if evidence.get("status") != "EVIDENCE_SUPPORTED" or evidence.get("window_review") != "NO_ACTUAL_SYSTEM_STRESS":
        raise ValueError("继承体系缺少完整无实战窗口核查")
    for field in ("ruler_window", "baseline_window", "baseline_ruler_id", "baseline_source_refs", "counterevidence_review"):
        if not evidence.get(field):
            raise ValueError(f"继承体系缺少{field}")
    if evidence.get("continuity_status") != "SUPPORTED_WITH_LIMITS":
        raise ValueError("体系延续未闭合或存在断裂")
    for axis in AXIS_FIELDS:
        finding = (evidence.get("axis_continuity") or {}).get(axis) or {}
        if not all(finding.get(field) for field in ("baseline_basis", "continuity_basis", "source_refs", "grade_basis")):
            raise ValueError(f"继承体系{axis}证据不完整")
    for field in ("strategy_chains", "capability_only_strategy_chains", "current_item_task_refs", "capability_only_parent_refs",
                  "major_system_success_refs", "major_system_failure_refs", "major_system_success_chain_refs", "major_system_failure_chain_refs"):
        if row.get(field):
            raise ValueError("继承体系不得挪入他人任务或替代已有实战")
    if row.get("gate_cap") != 3 or _grade_number(row.get("final_grade")) is None:
        raise ValueError("继承体系须有事实档并执行总档上限3")
    if row.get("C_score_within_band_adjudication") is not None:
        raise ValueError("继承体系无本人战果，档内采用中性位置")


def _verify_grade_projection(row: Mapping[str, Any]) -> None:
    final = _grade_number(row.get("final_grade"))
    overall = row.get("C_overall_grade")
    if final is None:
        if overall != row.get("final_grade"):
            raise ValueError(f"{row.get('ruler_name')}最终档兼容字段未同步")
        return
    axes = {
        axis: _grade_number(row.get(field))
        for axis, field in AXIS_FIELDS.items()
    }
    if any(value is None for value in axes.values()):
        raise ValueError(f"{row.get('ruler_name')}三轴档位不完整")
    floor = min(axes.values())
    if _grade_number(row.get("axis_floor_grade")) != floor:
        raise ValueError(f"{row.get('ruler_name')}axis_floor_grade不闭合")
    if _grade_number(row.get("raw_grade")) != floor:
        raise ValueError(f"{row.get('ruler_name')}raw_grade不闭合")
    gate = _grade_number(row.get("gate_cap"))
    if gate is None or final != min(floor, gate):
        raise ValueError(f"{row.get('ruler_name')}final_grade与gate_cap不闭合")
    if overall != row.get("final_grade"):
        raise ValueError(f"{row.get('ruler_name')}C_overall_grade与final_grade不一致")


def _verify_score_fields(
    row: Mapping[str, Any], source_row: Mapping[str, Any] | None = None
) -> None:
    final = _grade_number(row.get("final_grade"))
    if row.get("final_grade") == "C-N":
        raise ValueError("C-N按零分合成已停用")
    if final is None:
        if row.get("C_score_points") is not None:
            raise ValueError(f"{row.get('ruler_name')}UNKNOWN仍有C分")
        return
    rate = float(row.get("C_score_rate"))
    points = float(row.get("C_score_points"))
    # C_score_rate is stored to two decimals while C_score_points is rounded
    # from the unrounded rate; checking the rounded rate alone creates a false
    # half-point failure at values such as 2.90% -> 1.5 points.
    if abs(points - 50 * rate / 100) > 0.051:
        raise ValueError(f"{row.get('ruler_name')}C分与得分率不一致")
    position = float(row.get("C_score_band_position"))
    if not 0 <= position <= 1:
        raise ValueError(f"{row.get('ruler_name')}档内位置越界")
    band = row.get("C_score_band") or {}
    if band != {
        "lower_rate": GRADE_RANGES[final][0],
        "upper_rate": GRADE_RANGES[final][1],
    }:
        raise ValueError(f"{row.get('ruler_name')}C档区间与最终档不一致")
    if source_row and source_row.get("formal_score_rate_snapshot") is not None and row.get("system_observation_status") != "INHERITED_UNTESTED":
        if rate != float(source_row["formal_score_rate_snapshot"]):
            raise ValueError(f"{row.get('ruler_name')}保留的正式得分率快照未同步")
        return
    if final == 5:
        if rate != 100.0 or position != 1.0:
            raise ValueError(f"{row.get('ruler_name')}C5分值未闭合")
        return

    axes = {
        axis: _grade_number(row.get(field))
        for axis, field in AXIS_FIELDS.items()
    }
    surplus = sum(int(value) - final for value in axes.values())
    expected_axis_position = surplus / (2 * (5 - final))
    profile = row.get("strategy_chain_outcome_profile") or {}
    counts = profile.get("return_class_counts") or {}
    known = sum(
        int(counts.get(outcome, 0))
        for outcome in (
            "HIGH_RETURN",
            "PROPORTIONATE_RETURN",
            "LOW_RETURN",
            "NEGATIVE_RETURN",
        )
    )
    if row.get("system_observation_status") == "INHERITED_UNTESTED":
        expected_outcome_position = 0.5
        if row.get("C_score_outcome_position") != expected_outcome_position:
            raise ValueError("继承体系结果位置必须中性，不能伪造战果")
    elif known:
        quality = (
            int(counts.get("HIGH_RETURN", 0))
            + 0.55 * int(counts.get("PROPORTIONATE_RETURN", 0))
            + 0.2 * int(counts.get("LOW_RETURN", 0))
        ) / known
        expected_outcome_position = 0.5 + (quality - 0.5) * min(1.0, known / 4)
    else:
        expected_outcome_position = expected_axis_position
    position_decision = row.get("C_score_within_band_adjudication") or {}
    explicit_position = {
        "LOW": 0.25,
        "MID": 0.5,
        "HIGH": 0.75,
    }.get(str(position_decision.get("position")))
    expected_position = max(
        expected_axis_position,
        explicit_position if explicit_position is not None else expected_outcome_position,
    )
    lower, upper = GRADE_RANGES[final]
    expected_rate = lower + (upper - lower) * expected_position
    if abs(position - round(expected_position, 4)) > 0.0001:
        raise ValueError(f"{row.get('ruler_name')}战略链档内位置未按合同派生")
    if abs(rate - round(expected_rate, 2)) > 0.001:
        raise ValueError(f"{row.get('ruler_name')}战略链得分率未按合同派生")


def verify_third_item_c_strategy_chain_settlement(
    workspace_root: Path,
) -> dict[str, Any]:
    source = load_strategy_chain_source(workspace_root)
    payload = load_json(workspace_root / C_PATH)
    formal_by_id = _records_by_id(payload)
    source_by_id = _source_records_by_id(source)
    if len(formal_by_id) != len(payload.get("records") or ()):
        raise ValueError("第三项C正式结果人物ID缺失或重复")
    missing = sorted(set(source_by_id) - set(formal_by_id))
    if missing:
        raise ValueError(f"第三项C战略链正式源人物不在正式结果：{missing}")

    all_chain_ids: set[str] = set()
    current_count = 0
    capability_count = 0
    final_changes = []
    for source_id, source_row in source_by_id.items():
        row = formal_by_id[source_id]
        if row.get("ruler_name") != source_row.get("ruler_name"):
            raise ValueError(f"第三项C人物身份漂移：{source_id}")
        if not str(row.get("polity") or "").strip():
            raise ValueError(f"{row.get('ruler_name')}第三项C缺少政权名称")
        fields = source_row["formal_writeback"]["fields"]
        for key, expected in fields.items():
            if row.get(key) != expected:
                raise ValueError(f"{row.get('ruler_name')}正式C字段未按源同步：{key}")
        current_chains = list(row.get("strategy_chains") or ())
        capability_chains = list(row.get("capability_only_strategy_chains") or ())
        if row.get("strategy_chain_count") != len(current_chains):
            raise ValueError(f"{row.get('ruler_name')}当前战略链计数不一致")
        if row.get("capability_only_strategy_chain_count") != len(capability_chains):
            raise ValueError(f"{row.get('ruler_name')}能力专用战略链计数不一致")
        current_ids = [str(chain.get("chain_id") or "") for chain in current_chains]
        capability_ids = [str(chain.get("chain_id") or "") for chain in capability_chains]
        if current_ids != list(row.get("strategy_chain_refs") or ()):
            raise ValueError(f"{row.get('ruler_name')}当前战略链索引不一致")
        if capability_ids != list(row.get("capability_only_strategy_chain_refs") or ()):
            raise ValueError(f"{row.get('ruler_name')}能力专用战略链索引不一致")
        if set(current_ids) & set(capability_ids):
            raise ValueError(f"{row.get('ruler_name')}当前与能力专用战略链重叠")
        for chain_id in [*current_ids, *capability_ids]:
            if not chain_id or chain_id in all_chain_ids:
                raise ValueError(f"第三项C战略链ID缺失或重复：{chain_id}")
            all_chain_ids.add(chain_id)
        if row.get("strategy_chain_outcome_profile") != _chain_profile(current_chains):
            raise ValueError(f"{row.get('ruler_name')}战略链回报剖面不一致")
        current_count += len(current_chains)
        capability_count += len(capability_chains)
        _verify_inherited_system(row)
        _verify_grade_projection(row)
        _verify_score_fields(row, source_row)
        before_grade = source_row["formal_writeback"].get("before_formal_overall_grade")
        if before_grade is None:
            raise ValueError(f"{row.get('ruler_name')}缺少正式写回前总档快照")
        if before_grade != row.get("C_overall_grade"):
            final_changes.append(row.get("ruler_name"))

    expected_summary = source.get("summary", {}).get("formal_writeback") or {}
    if expected_summary.get("current_strategy_chain_count") != current_count:
        raise ValueError("第三项C战略链总数与正式记录不一致")
    if expected_summary.get("capability_only_strategy_chain_count") != capability_count:
        raise ValueError("第三项C能力专用战略链总数与正式记录不一致")
    distribution = dict(sorted(Counter(
        str(row.get("C_overall_grade")) for row in payload["records"]
    ).items()))
    if payload.get("grade_distribution") != distribution:
        raise ValueError("第三项C档位分布摘要不一致")

    from emperor_v4.evaluation.five_dynasties_third_item import _render_formal_markdown

    markdown_path = (workspace_root / C_PATH).with_suffix(".md")
    if markdown_path.read_text(encoding="utf-8") != _render_formal_markdown("C", payload["records"]):
        raise ValueError("第三项C Markdown与正式C JSON渲染结果不一致")
    return {
        "status": "PASS",
        "formal_record_count": len(formal_by_id),
        "source_record_count": len(source_by_id),
        "strategy_chain_count": current_count,
        "capability_only_strategy_chain_count": capability_count,
        "final_grade_change_count": len(expected_summary.get("final_grade_changes_from_scored_records") or ()),
        "formal_status_transition_count": len(final_changes),
        "formal_unknown_resolved_count": expected_summary.get("formal_unknown_resolved_count"),
        "remaining_unknown_names": expected_summary.get("remaining_unknown_names"),
    }
