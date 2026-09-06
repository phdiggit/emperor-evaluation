from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from emperor_v4.evaluation.formal_json_store import (
    load_json,
    load_ruler_polities,
    write_json,
)
from emperor_v4.evaluation.third_item_current_settlement import (
    AB_PATH,
    RESULT_CREDIT_ADJUDICATIONS_PATH,
    write_current_third_item_settlement,
)


REVIEW_DIR = Path(
    "docs/评分结算/第三项军事与边疆净收益/国防安全/B1重审数据"
)
FINAL_CLOSURE_NAME = "99-B1全量收口与剩余批次.json"
ANCHOR_REGISTRY_PATH = Path("config/third-item/third-item-b1-region-anchors.json")

RATE_TO_BAND = {
    0.0: (0, "LOW"), 15.0: (0, "MID"), 29.0: (0, "HIGH"),
    30.0: (1, "LOW"), 37.0: (1, "MID"), 44.0: (1, "HIGH"),
    45.0: (2, "LOW"), 52.0: (2, "MID"), 59.0: (2, "HIGH"),
    60.0: (3, "LOW"), 67.0: (3, "MID"), 74.0: (3, "HIGH"),
    75.0: (4, "LOW"), 82.0: (4, "MID"), 89.0: (4, "HIGH"),
    90.0: (5, "LOW"), 95.0: (5, "MID"), 100.0: (5, "HIGH"),
}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.b1-write-tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _detailed_rate(row: Mapping[str, Any]) -> float:
    for key in ("result", "third_item_effective_result", "effective_third_item_result"):
        value = row.get(key)
        if isinstance(value, Mapping) and value.get("rate") is not None:
            return float(value["rate"])
    if row.get("score_rate") is not None:
        return float(row["score_rate"])
    raise ValueError(f"B1重审记录缺少最终率：{row.get('ruler_name')}")


def _weighted_value(row: Mapping[str, Any]) -> float | None:
    basis = str(row.get("basis") or "")
    exact = re.search(r"weighted(?:恢复|=)(-?\d+(?:\.\d+)?)", basis)
    if exact:
        return round(float(exact.group(1)), 3)
    for key in ("third_item_effective_result", "effective_third_item_result"):
        value = row.get(key)
        if isinstance(value, Mapping):
            if (
                float(value.get("rate") or 0.0) == 0.0
                and str(value.get("status") or "").startswith("EXCLUDED_")
            ):
                return 0.0
            for field in ("weighted", "effective_weighted"):
                if value.get(field) is not None:
                    weighted = float(value[field])
                    restored = re.search(r"恢复(\d+(?:\.\d+)?)规模", basis)
                    if str(row.get("status") or "").startswith("OVERRIDE_") and restored:
                        weighted += float(restored.group(1))
                    return round(weighted, 3)
    totals = row.get("totals")
    if isinstance(totals, Mapping) and totals.get("weighted") is not None:
        return round(float(totals["weighted"]), 3)
    for field in ("weighted_control_value", "effective_weighted"):
        if row.get(field) is not None:
            return round(float(row[field]), 3)
    if row.get("objective_start") is not None and row.get("objective_end") is not None:
        value = (
            float(row["objective_end"])
            - 0.6 * float(row["objective_start"])
            - float(row.get("cross_item_excluded_net_gain") or 0.0)
        )
        return round(value, 3)
    return None


def _exact_totals(row: Mapping[str, Any]) -> tuple[float, float] | None:
    totals = row.get("totals")
    if isinstance(totals, Mapping) and totals.get("start") is not None and totals.get("end") is not None:
        return float(totals["start"]), float(totals["end"])
    if row.get("start_total") is not None and row.get("end_total") is not None:
        return float(row["start_total"]), float(row["end_total"])
    if row.get("objective_start") is not None and row.get("objective_end") is not None:
        return float(row["objective_start"]), float(row["objective_end"])
    objective = row.get("objective_totals")
    if isinstance(objective, Mapping) and objective.get("start") is not None and objective.get("end") is not None:
        return float(objective["start"]), float(objective["end"])
    return None


def _reason(row: Mapping[str, Any]) -> str:
    for field in ("basis", "reason", "legacy_resolution", "change_vs_old"):
        value = str(row.get(field) or "").strip()
        if value:
            return value
    for key in ("third_item_effective_result", "effective_third_item_result"):
        value = row.get(key)
        if isinstance(value, Mapping) and str(value.get("basis") or "").strip():
            return str(value["basis"]).strip()
    return "B1全量重审已确认最终档内率。"


def load_b1_reaudit_decisions(workspace_root: Path) -> dict[str, dict[str, Any]]:
    review_dir = workspace_root / REVIEW_DIR
    closure = _read(review_dir / FINAL_CLOSURE_NAME)
    if closure.get("canonical_status") != "FINAL_REAUDIT_CLOSURE" or closure.get("status") != "COMPLETE_201_OF_201":
        raise ValueError("B1最终收口文件未声明201人全量闭合")
    audit = closure.get("audit_summary") or {}
    if any(int(audit.get(key) or 0) for key in (
        "unresolved_record_count", "lower_bound_record_count",
        "unknown_anchor_count", "unknown_coverage_count",
        "terminal_override_required_count",
    )):
        raise ValueError("B1最终收口仍有未闭合裁决")

    ab = load_json(workspace_root / AB_PATH)
    name_to_id = {str(row["ruler_name"]): str(row["ruler_id"]) for row in ab["records"]}
    decisions: dict[str, dict[str, Any]] = {}
    for path in sorted(review_dir.glob("*.json")):
        if path.name == FINAL_CLOSURE_NAME:
            continue
        payload = _read(path)
        if payload.get("schema_id") != "third-item-b1-reaudit-data-v1":
            raise ValueError(f"B1重审批次schema不合法：{path.name}")
        for row in payload.get("records") or ():
            ruler_id = str(row["ruler_id"])
            if ruler_id in decisions:
                raise ValueError(f"B1重审重复人物：{ruler_id}")
            decisions[ruler_id] = {
                "ruler_id": ruler_id,
                "final_rate": _detailed_rate(row),
                "source": (REVIEW_DIR / path.name).as_posix(),
                "review_status": str(row.get("review_status") or "REVIEWED"),
                "decision": dict(row),
                "context": {"profiles": payload.get("profiles") or {}},
            }

    for polity, block in (closure.get("remaining_polities") or {}).items():
        for row in block.get("records") or ():
            name = str(row["ruler"])
            ruler_id = name_to_id.get(name)
            if ruler_id is None:
                raise ValueError(f"B1最终收口人物不在正式池：{name}")
            if ruler_id in decisions:
                raise ValueError(f"B1最终收口与前序批次重复：{name}")
            decisions[ruler_id] = {
                "ruler_id": ruler_id,
                "final_rate": float(row["final_rate"]),
                "source": (REVIEW_DIR / FINAL_CLOSURE_NAME).as_posix(),
                "review_status": str(row.get("status") or "REVIEWED"),
                "decision": dict(row),
                "closure_polity": str(polity),
            }

    for polity, block in (closure.get("prior_reaudit_overrides") or {}).items():
        for row in block.get("records") or ():
            name = str(row["ruler"])
            ruler_id = name_to_id.get(name)
            if ruler_id not in decisions:
                raise ValueError(f"B1最终覆盖没有前序人物：{name}")
            merged = dict(decisions[ruler_id]["decision"])
            merged.update(row)
            decisions[ruler_id].update(
                final_rate=float(row["final_rate"]),
                source=(REVIEW_DIR / FINAL_CLOSURE_NAME).as_posix(),
                review_status=str(row.get("status") or "REVIEWED"),
                decision=merged,
                closure_polity=str(polity),
            )

    expected = {str(row["ruler_id"]) for row in ab["records"]}
    if set(decisions) != expected or len(decisions) != int(closure["coverage"]["all_record_count"]):
        raise ValueError("B1重审裁决没有精确覆盖正式201人")
    for ruler_id, item in decisions.items():
        if float(item["final_rate"]) not in RATE_TO_BAND:
            raise ValueError(f"B1重审率不属于合同档内映射：{ruler_id}={item['final_rate']}")
    return decisions


def _apply_axis(
    row: dict[str, Any],
    item: Mapping[str, Any],
    region_display_names: Mapping[str, str],
) -> None:
    rate = float(item["final_rate"])
    grade, position = RATE_TO_BAND[rate]
    decision = item["decision"]
    axis = row["axes"]["B1"]
    previous_grade = int(str(axis["grade"]).split("-")[-1])
    axis.update(
        grade=f"B1-{grade}",
        band_position=position,
        score_rate=rate,
        axis_points=round(rate * 0.25, 2),
        reason=f"规模与控制强度：{_reason(decision)}",
    )
    canonical_regions = _canonical_region_ledger(
        decision,
        item.get("context") or {},
        region_display_names,
    )
    if canonical_regions is not None:
        control, ledger = canonical_regions
        row["b1_region_control"] = control
        row["b1_region_adjudications"] = ledger
        row["b1_region_ledger_status"] = "EXPLICIT_REGION_LEDGER_FINAL_REAUDIT"
    control = row.get("b1_region_control") or {}
    start_snapshot = control.get("start") if isinstance(control, Mapping) else {}
    end_snapshot = control.get("end") if isinstance(control, Mapping) else {}
    totals = row.setdefault("b1_control_equivalents", {})
    if isinstance(start_snapshot, Mapping) and isinstance(end_snapshot, Mapping):
        start = round(sum(float(value) for value in start_snapshot.values()), 3)
        end = round(sum(float(value) for value in end_snapshot.values()), 3)
        totals.update(start=start, end=end, net_change=round(end - start, 3))
        axis["raw_net_change"] = round(end - start, 3)
        objective_weighted = round(end - 0.6 * start, 3)
    else:
        objective_weighted = float(totals.get("weighted_value") or 0.0)

    weighted = _weighted_value(decision)
    if weighted is None:
        weighted = float(totals.get("weighted_value") or 0.0)
        if previous_grade != grade and grade == 0:
            weighted = 0.0
    axis["weighted_control_value"] = round(weighted, 3)
    totals["weighted_value"] = round(weighted, 3)
    exclusion = round(objective_weighted - weighted, 3)
    if exclusion:
        row["b1_cross_item_excluded_weighted_value"] = exclusion
    else:
        row.pop("b1_cross_item_excluded_weighted_value", None)

    row["b1_reaudit"] = {
        "status": "FINAL_201_OF_201",
        "decision_status": str(item["review_status"]),
        "source": str(item["source"]),
        "final_B1_rate": rate,
    }


def _canonical_region_ledger(
    decision: Mapping[str, Any],
    context: Mapping[str, Any],
    region_display_names: Mapping[str, str],
) -> tuple[dict[str, dict[str, float]], list[dict[str, Any]]] | None:
    region_rows = decision.get("regions") or decision.get("objective_regions")
    normalized: dict[str, dict[str, Any]] = {}
    if isinstance(region_rows, Mapping):
        for region_id, value in region_rows.items():
            if not isinstance(value, Mapping):
                continue
            normalized[str(region_id)] = {
                "weight": float(value["w"]),
                "start_coverage": float(value["s"]),
                "end_coverage": float(value["e"]),
                "start": float(value["se"]),
                "end": float(value["ee"]),
                "reason": str(value.get("reason") or "逐区域全量重审确认。"),
                "evidence": list(value.get("evidence") or ()),
            }
    elif isinstance(decision.get("start_regions"), Mapping) and isinstance(decision.get("end_regions"), Mapping):
        start_regions = decision["start_regions"]
        end_regions = decision["end_regions"]
        for region_id in set(start_regions) | set(end_regions):
            start_value = start_regions.get(region_id) or {}
            end_value = end_regions.get(region_id) or {}
            start_equivalent = float(start_value.get("equivalent") or 0.0)
            end_equivalent = float(end_value.get("equivalent") or 0.0)
            start_coverage = float(start_value.get("coverage") or 0.0)
            end_coverage = float(end_value.get("coverage") or 0.0)
            coverages = [
                equivalent / coverage
                for equivalent, coverage in (
                    (start_equivalent, start_coverage),
                    (end_equivalent, end_coverage),
                )
                if coverage
            ]
            if not coverages:
                continue
            normalized[str(region_id)] = {
                "weight": coverages[0],
                "start_coverage": start_coverage,
                "end_coverage": end_coverage,
                "start": start_equivalent,
                "end": end_equivalent,
                "reason": str(decision.get("reason") or "逐区域全量重审确认。"),
                "evidence": [],
            }
    elif decision.get("start_profile") is not None and decision.get("end_profile") is not None:
        profiles = context.get("profiles") or {}
        start_profile = profiles.get(str(decision["start_profile"])) or {}
        end_profile = profiles.get(str(decision["end_profile"])) or {}
        start_regions = start_profile.get("regions") or {}
        end_regions = end_profile.get("regions") or {}
        for region_id in set(start_regions) | set(end_regions):
            start_value = start_regions.get(region_id) or {}
            end_value = end_regions.get(region_id) or {}
            weight = float((start_value or end_value)["spatial_weight"])
            normalized[str(region_id)] = {
                "weight": weight,
                "start_coverage": float(start_value.get("coverage") or 0.0),
                "end_coverage": float(end_value.get("coverage") or 0.0),
                "start": float(start_value.get("equivalent") or 0.0),
                "end": float(end_value.get("equivalent") or 0.0),
                "reason": str(decision.get("reason") or "逐区域全量重审确认。"),
                "evidence": list(dict.fromkeys(
                    [*(start_profile.get("evidence") or ()), *(end_profile.get("evidence") or ())]
                )),
            }
    else:
        return None

    control = {"start": {}, "end": {}}
    ledger: list[dict[str, Any]] = []
    for region_id, value in sorted(normalized.items()):
        if value["start"]:
            control["start"][region_id] = round(float(value["start"]), 3)
        if value["end"]:
            control["end"][region_id] = round(float(value["end"]), 3)
        ledger.append({
            "object_id": region_id,
            "object_name": region_display_names.get(region_id, region_id),
            "spatial_weight": round(float(value["weight"]), 3),
            "start_coverage": float(value["start_coverage"]),
            "end_coverage": float(value["end_coverage"]),
            "anchors": ["start", "end"],
            "counted": True,
            "control_equivalent": {
                "start": round(float(value["start"]), 3),
                "end": round(float(value["end"]), 3),
            },
            "evidence_refs": [str(ref) for ref in value["evidence"]],
            "reason": str(value["reason"]),
        })
    return control, ledger


def _recalculate_b80(adjudication: dict[str, Any], b1_rate: float) -> float:
    b2_rate = float(adjudication["adjudicated_B2_rate"])
    b4_rate = float(adjudication["adjudicated_B4_rate"])
    points = round(
        80.0
        * (0.55 * b1_rate / 100.0 + 0.45 * b2_rate / 100.0)
        * (0.70 + 0.30 * b4_rate / 100.0),
        2,
    )
    adjudication["formal_B1_rate"] = b1_rate
    adjudication["adjudicated_B1_rate"] = b1_rate
    adjudication["B80_points"] = points
    return points


def rebuild_third_item_b1(workspace_root: Path, *, write: bool = False) -> dict[str, Any]:
    decisions = load_b1_reaudit_decisions(workspace_root)
    anchor_registry = _read(workspace_root / ANCHOR_REGISTRY_PATH)
    region_display_names = {
        str(item["region_id"]): str(item["display_name"])
        for item in anchor_registry.get("anchors") or ()
    }
    ab_path = workspace_root / AB_PATH
    credit_path = workspace_root / RESULT_CREDIT_ADJUDICATIONS_PATH
    ab_payload = deepcopy(load_json(ab_path))
    credit_payload = deepcopy(_read(credit_path))
    ab_by_id = {str(row["ruler_id"]): row for row in ab_payload["records"]}
    credit_by_id = {str(row["ruler_id"]): row for row in credit_payload["records"]}
    if set(ab_by_id) != set(decisions) or set(credit_by_id) != set(decisions):
        raise ValueError("B1重审、AB正式表与结果信用裁决人物集合不一致")

    rate_changes = 0
    axis_changes = 0
    b80_changes = 0
    for ruler_id, item in decisions.items():
        ab_row = ab_by_id[ruler_id]
        credit_row = credit_by_id[ruler_id]
        rate = float(item["final_rate"])
        old_axis_rate = float(ab_row["axes"]["B1"]["score_rate"])
        old_formal_rate = float(credit_row["B80_adjudication"]["formal_B1_rate"])
        old_b80 = float(credit_row["B80_adjudication"]["B80_points"])
        axis_changes += old_axis_rate != rate
        rate_changes += old_formal_rate != rate
        _apply_axis(ab_row, item, region_display_names)
        points = _recalculate_b80(credit_row["B80_adjudication"], rate)
        b80_changes += old_b80 != points
        ab_row["B80_adjudication"] = deepcopy(credit_row["B80_adjudication"])
        ab_row["B80_score_points"] = points
        ab_row["AB200_score_points"] = round(float(ab_row["A120_score_points"]) + points, 2)
        ab_row["AB_score_points"] = round(
            sum(float(axis["axis_points"]) for axis in ab_row["axes"].values()), 2
        )

    report: dict[str, Any] = {
        "status": "READY_TO_WRITE" if not write else "WRITTEN",
        "record_count": len(decisions),
        "formal_B1_rate_change_count": rate_changes,
        "atomic_B1_rate_change_count": axis_changes,
        "B80_change_count": b80_changes,
    }
    if not write:
        return report

    _write_atomic(credit_path, credit_payload)
    write_json(
        ab_path,
        ab_payload,
        ruler_polities=load_ruler_polities(workspace_root),
    )
    third = write_current_third_item_settlement(workspace_root)
    report.update(
        third_item_score_ready_count=int(third["score_ready_count"]),
        third_item_score_range=third["score_range"],
    )
    return report
