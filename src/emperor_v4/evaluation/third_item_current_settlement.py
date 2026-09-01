from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from emperor_v4.evaluation.third_item_d_settlement import (
    FORMAL_SETTLEMENT_JSON_PATH as FORMAL_D_PATH,
)


AB_PATH = Path("docs/评分结算/第三项军事与边疆净收益/国防安全/01-皇帝AB项正式结算.json")
C_PATH = Path("docs/评分结算/第三项军事与边疆净收益/军事体系有效性/01-皇帝C项正式结算.json")
FORMAL_PATH = Path("docs/评分结算/第三项军事与边疆净收益/02-第三项正式结算.json")
RESULT_CREDIT_ADJUDICATIONS_PATH = Path("config/third-item/third-item-result-credit-adjudications.json")
COST_CREDIT_FACTORS_PATH = Path("config/third-item/third-item-cost-credit-factors.json")
MILITARY_NET_LOSS_PENALTIES_PATH = Path("config/third-item/third-item-military-net-loss-penalties.json")
C_OUTCOME_ADJUDICATIONS_PATH = Path("config/third-item/third-item-c-outcome-adjudications.json")
AB_HANDOFF_ADJUDICATIONS_PATH = Path("config/third-item/third-item-ab-handoff-adjudications.json")


def _reign_range_label(value: object) -> str:
    if isinstance(value, (list, tuple)):
        if len(value) == 2 and all(isinstance(item, int) for item in value):
            return f"{value[0]}-{value[1]}"
        return "；".join(str(item) for item in value)
    return str(value)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _index(records: Sequence[Mapping[str, Any]], component: str) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in records:
        name = str(row["ruler_name"])
        if name in indexed:
            raise ValueError(f"{component}存在重复评价主体：{name}")
        indexed[name] = row
    return indexed


def _component_identity(
    name: str,
    rows: Sequence[Mapping[str, Any] | None],
) -> str:
    ids = {str(row["ruler_id"]) for row in rows if row is not None}
    if len(ids) != 1:
        raise ValueError(f"{name}跨组件人物ID不一致：{sorted(ids)}")
    return ids.pop()


def _rank(records: Sequence[dict[str, Any]]) -> None:
    ready = sorted(
        (row for row in records if row["third_item_score_points"] is not None),
        key=lambda row: (-float(row["third_item_score_points"]), str(row["ruler_id"])),
    )
    previous: float | None = None
    rank = 0
    for index, row in enumerate(ready, 1):
        score = float(row["third_item_score_points"])
        if score != previous:
            rank = index
            previous = score
        row["rank"] = rank
        row["rank_status"] = "GLOBAL_CURRENT_READY_POOL"
    for row in records:
        if row["third_item_score_points"] is None:
            row["rank"] = None
            row["rank_status"] = "PENDING_COMPONENT_SCORE"


def _clamp(low: float, high: float, value: float) -> float:
    return max(low, min(high, value))


def _decompose_a120_axis(axis: Mapping[str, Any]) -> tuple[float, float]:
    end_grade = int(axis["end_grade"])
    attributable_delta = float(axis["attributable_delta"])
    positive_raw = 10 * max(0.0, attributable_delta) + max(
        float(axis.get("ceiling_progress_bonus") or 0),
        float(axis.get("maintenance_bonus") or 0),
    )
    anchor_raw = (
        12 * end_grade
        + 10 * min(0.0, attributable_delta)
        - float(axis.get("negative_adjustment") or 0)
    )
    anchor = _clamp(0.0, 100.0, anchor_raw)
    with_positive = _clamp(0.0, 100.0, anchor_raw + positive_raw)
    return round(anchor * 0.6, 2), round((with_positive - anchor) * 0.6, 2)


def _validate_cost_factor_contract(payload: Mapping[str, Any]) -> None:
    factors = payload["factor_by_global_cost_band_and_position"]
    ordered = [
        ("C1", "LOW"), ("C1", "MID"), ("C1", "HIGH"),
        ("C2", "LOW"), ("C2", "MID"), ("C2", "HIGH"),
        ("C3", "LOW"), ("C3", "MID"), ("C3", "HIGH"),
        ("C4", "LOW"), ("C4", "MID"), ("C4", "HIGH"),
        ("C5", "LOW"), ("C5", "MID"), ("C5", "HIGH"),
        ("C6", "LOW"), ("C6", "MID"), ("C6", "HIGH"),
        ("C7", "LOW"), ("C7", "MID"), ("C7", "HIGH"), ("C7", "HIGHEST"),
    ]
    values = [float(factors[band][position]) for band, position in ordered]
    if any(left <= right for left, right in zip(values, values[1:])):
        raise ValueError("成本成果信用系数必须按成本严重度严格递减")
    if float(factors["C0"]["LOW"]) != 1.0:
        raise ValueError("C0-LOW必须保持1.0")


def _render_current_weighted_markdown(records: Sequence[Mapping[str, Any]]) -> str:
    human_status = {
        "NOT_APPLICABLE": "不适用",
        "NONE": "无",
        "HIGH": "高位",
        "MID": "中位",
        "LOW": "低位",
    }

    def human_label(value: object) -> str:
        return human_status.get(str(value), str(value))

    def human_basis(value: object) -> str:
        return (
            str(value)
            .replace(
                "NOT_APPLICABLE does not mean low cost. The whole founding/unification campaign, including reversals and costs, is excluded under the corrected hard gate.",
                "不适用不等于低成本；创业统一整链及其反转与成本已按跨项去重规则排除。",
            )
            .replace("LOWER_BOUND", "证据下限")
            .replace("PROVISIONAL", "暂定")
            .replace("CONFIRMED", "已确认")
        )

    eligible = sorted(
        (row for row in records if row.get("third_item_score_points") is not None),
        key=lambda row: (int(row["rank"]), str(row["ruler_id"])),
    )
    lines = [
        "# 秦至清第三项军事与边疆正式结算",
        "",
        "本表按A120战略安全结果、B80边疆控制结果、C50军事体系能力合并；成本先折算A正向成果信用和B成果信用。只有第三项自身闭合EN2/EN3、C5以上本方军事成本和本人责任时，才另加0至-40分军事净毁损尾部。",
        "",
        "| 排名 | 皇帝 | 政权 | 在位 | A120 | B80 | C50 | 全局成本 | 系数 | 净毁损 | 总分 |",
        "|---:|---|---|---|---:|---:|---:|---|---:|---:|---:|",
    ]
    for row in eligible:
        profile = row["global_cost_credit_profile"]
        lines.append(
            f"| {row['rank']} | {row['ruler_name']} | {row['polity']} | {_reign_range_label(row['reign_range'])} | "
            f"{float(row['A120_score_points']):.2f} | {float(row['B80_score_points']):.2f} | "
            f"{float(row['C50_score_points']):.2f} | {human_label(profile['cost_band'])}-{human_label(profile['position'])} | "
            f"{float(row['cost_credit_factor']):.3f} | {float(row['military_net_loss_penalty']):.2f} | {float(row['third_item_score_points']):.2f} |"
        )
    lines += ["", "## 逐人结算依据", ""]
    for row in eligible:
        profile = row["global_cost_credit_profile"]
        lines += [
            f"### {row['rank']}. {row['ruler_name']}（{float(row['third_item_score_points']):.2f}）",
            "",
            f"- 成本依据：{human_basis(profile['basis'])}",
            f"- 军事净毁损：{float(row['military_net_loss_penalty']):.2f}分。{human_basis(row['military_net_loss_basis'])}",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def build_current_third_item_settlement(workspace_root: Path) -> dict[str, Any]:
    paths = {
        "AB": workspace_root / AB_PATH,
        "C": workspace_root / C_PATH,
        "D": workspace_root / FORMAL_D_PATH,
        "combined": workspace_root / FORMAL_PATH,
        "result_credit": workspace_root / RESULT_CREDIT_ADJUDICATIONS_PATH,
        "cost_credit": workspace_root / COST_CREDIT_FACTORS_PATH,
        "military_net_loss": workspace_root / MILITARY_NET_LOSS_PENALTIES_PATH,
    }
    payloads = {key: _load(path) for key, path in paths.items()}
    _validate_cost_factor_contract(payloads["cost_credit"])
    indexed = {
        key: _index(payloads[key]["records"], key)
        for key in ("AB", "C", "D", "result_credit")
    }
    cost_overrides = _index(
        payloads["cost_credit"]["global_cost_overrides"], "global_cost_overrides"
    )
    military_net_loss_policy = payloads["military_net_loss"]["policy"]
    expected_penalties = {"ML0": 0, "ML1": -10, "ML2": -20, "ML3": -30, "ML4": -40}
    if military_net_loss_policy != expected_penalties:
        raise ValueError("军事净毁损档位映射与合同不一致")
    military_net_loss_by_name = _index(
        payloads["military_net_loss"]["records"], "military_net_loss"
    )
    attribution_policy = payloads["military_net_loss"]["attribution_policy"]
    if attribution_policy.get("default") != "FULL":
        raise ValueError("军事净毁损默认归责必须为FULL")
    material_attribution_ids = {str(value) for value in attribution_policy.get("material_ruler_ids") or ()}
    configured_net_loss_ids = {str(item["ruler_id"]) for item in military_net_loss_by_name.values()}
    if not material_attribution_ids.issubset(configured_net_loss_ids):
        raise ValueError("军事净毁损MATERIAL归责名单包含未裁决人物")
    for name, item in military_net_loss_by_name.items():
        if item["grade"] not in expected_penalties:
            raise ValueError(f"{name}军事净毁损档位非法")
        d_row = indexed["D"].get(name)
        if d_row is None or str(d_row["ruler_id"]) != str(item["ruler_id"]):
            raise ValueError(f"{name}军事净毁损裁决与D人物不一致")
        cost_override = cost_overrides.get(name)
        cost_band_label = (
            cost_override["global_cost_band"]
            if cost_override is not None
            else d_row["attributable_cost_profile"]["cost_band"]
        )
        cost_band = int(str(cost_band_label)[1:])
        if cost_band < 5:
            raise ValueError(f"{name}军事净毁损未通过C5成本门")
        chains = list(d_row.get("external_strategic_chains") or ()) + list(d_row.get("strategic_internal_chains") or ())
        if not any(
            str(chain.get("security_result_grade") or chain.get("achievement_grade") or "").startswith(("EN2", "EN3"))
            for chain in chains
        ):
            raise ValueError(f"{name}军事净毁损未通过EN2/EN3门")
    c_consumed_by_name = {
        name: {
            str(chain["chain_id"])
            for chain in row.get("cross_item_excluded_chains", [])
            if "THIRD_ITEM_C" in str(chain.get("result_type") or "")
        }
        for name, row in indexed["D"].items()
    }
    c_consumed_by_name = {
        name: chain_ids for name, chain_ids in c_consumed_by_name.items() if chain_ids
    }
    if set(c_consumed_by_name) != set(cost_overrides):
        raise ValueError(
            "第三项C消费者退出人物与全局成本恢复人物不一致："
            f"excluded={sorted(c_consumed_by_name)} overrides={sorted(cost_overrides)}"
        )
    for name, chain_ids in c_consumed_by_name.items():
        restored = set(cost_overrides[name]["restored_third_item_c_chain_ids"])
        if chain_ids != restored:
            raise ValueError(f"{name}第三项C消费者退出链未完整恢复：{chain_ids} != {restored}")
    existing = _index(payloads["combined"]["records"], "combined")
    ordered_names = list(indexed["AB"])
    ordered_names.extend(name for name in indexed["C"] if name not in indexed["AB"])
    ordered_names.extend(
        name
        for name in indexed["D"]
        if name not in indexed["AB"] and name not in indexed["C"]
    )
    ordered_names.extend(
        name
        for name in indexed["result_credit"]
        if name not in indexed["AB"] and name not in indexed["C"] and name not in indexed["D"]
    )

    records: list[dict[str, Any]] = []
    for name in ordered_names:
        ab_row = indexed["AB"].get(name)
        c_row = indexed["C"].get(name)
        d_row = indexed["D"].get(name)
        credit_row = indexed["result_credit"].get(name)
        ruler_id = _component_identity(name, (ab_row, c_row, d_row, credit_row))
        base = dict(existing.get(name) or {})
        for stale_key in (
            "A_score_points",
            "B_score_points",
            "AB_score_points",
            "C_score_points",
            "D_score_points",
            "D_score_status",
            "axes",
            "military_long_term_debt",
        ):
            base.pop(stale_key, None)

        c50_points = (
            float(c_row["C_score_points"])
            if c_row is not None and c_row.get("C_score_points") is not None
            else None
        )
        a120_points: float | None = None
        a120_anchor: float | None = None
        a120_positive: float | None = None
        b80_points: float | None = None
        local_cost_profile: dict[str, Any] | None = None
        global_cost_profile: dict[str, Any] | None = None
        cost_factor: float | None = None
        if credit_row is not None:
            axis_parts = [_decompose_a120_axis(credit_row["axes"][axis]) for axis in ("A1", "A2")]
            a120_anchor = round(sum(part[0] for part in axis_parts), 2)
            a120_positive = round(sum(part[1] for part in axis_parts), 2)
            a120_points = round(float(credit_row["A120_points"]), 2)
            if round(a120_anchor + a120_positive, 2) != a120_points:
                raise ValueError(f"{name} A120正向信用拆分不闭合")
            b80_points = round(float(credit_row["B80_adjudication"]["B80_points"]), 2)
        if d_row is not None:
            profile = d_row["attributable_cost_profile"]
            local_cost_profile = {
                "cost_band": profile["cost_band"],
                "position": profile["position"],
                "status": profile["status"],
                "basis": profile.get("basis") or profile.get("admission_fact") or "正式D局部成本画像未另列依据。",
            }
            override = cost_overrides.get(name)
            if override is None:
                global_cost_profile = dict(local_cost_profile)
                global_cost_profile["source"] = "D_LOCAL_COST_VIEW"
                global_cost_profile["restored_third_item_c_chain_ids"] = []
            else:
                if str(override["ruler_id"]) != ruler_id:
                    raise ValueError(f"{name}全局成本覆盖人物ID不一致")
                global_cost_profile = {
                    "cost_band": override["global_cost_band"],
                    "position": override["global_cost_position"],
                    "status": "CONFIRMED_GLOBAL_COST_VIEW",
                    "basis": override["basis"],
                    "source": "D_LOCAL_PLUS_RESTORED_THIRD_ITEM_C_CHAINS",
                    "restored_third_item_c_chain_ids": list(override["restored_third_item_c_chain_ids"]),
                }
            factor_table = payloads["cost_credit"]["factor_by_global_cost_band_and_position"]
            cost_factor = float(
                factor_table[global_cost_profile["cost_band"]][global_cost_profile["position"]]
            )
        net_loss = military_net_loss_by_name.get(name)
        net_loss_grade = str(net_loss["grade"]) if net_loss else "ML0"
        net_loss_penalty = float(expected_penalties[net_loss_grade])
        net_loss_basis = str(net_loss["basis"]) if net_loss else "未同时通过EN2/EN3、C5以上本方成本和本人责任门，不生成负向尾部。"
        net_loss_attribution = (
            "NONE"
            if net_loss is None
            else "MATERIAL"
            if ruler_id in material_attribution_ids
            else "FULL"
        )
        total = None
        if None not in (a120_anchor, a120_positive, b80_points, c50_points, cost_factor):
            total = round(
                float(a120_anchor)
                + float(cost_factor) * (float(a120_positive) + float(b80_points))
                + float(c50_points)
                + net_loss_penalty,
                2,
            )
        missing = []
        if ab_row is None:
            missing.append("AB_SOURCE")
        if credit_row is None or a120_points is None or b80_points is None:
            missing.append("A120/B80_ADJUDICATION")
        if c50_points is None:
            missing.append("C")
        if d_row is None or global_cost_profile is None or cost_factor is None:
            missing.append("GLOBAL_COST_VIEW")

        polity_source = ab_row or c_row or d_row or {}
        reign_source = ab_row or c_row or d_row or {}
        base.update({
            "ruler_id": ruler_id,
            "ruler_name": name,
            "polity": polity_source.get("polity") or "—",
            "reign_range": reign_source.get("reign_range"),
            "A120_score_points": a120_points,
            "A120_non_cost_anchor_points": a120_anchor,
            "A120_positive_result_credit_points": a120_positive,
            "B80_score_points": b80_points,
            "C50_score_points": c50_points,
            "D_local_cost_profile": local_cost_profile,
            "global_cost_credit_profile": global_cost_profile,
            "cost_credit_factor": cost_factor,
            "score_formula": "A120_non_cost_anchor + factor * (A120_positive_result_credit + B80) + C50 + military_net_loss_penalty",
            "military_net_loss_grade": net_loss_grade,
            "military_net_loss_attribution": net_loss_attribution,
            "military_net_loss_penalty": net_loss_penalty,
            "military_net_loss_basis": net_loss_basis,
            "third_item_score_points": total,
            "third_item_score_rate": None if total is None else round(total / 250 * 100, 2),
            "coverage_status": {
                "AB": ab_row.get("coverage_status") if ab_row else "NO_AB_RECORD",
                "C": c_row.get("coverage_status") if c_row else "NO_C_RECORD",
                "D": d_row.get("coverage_status") if d_row else "NO_D_RECORD",
                "result_credit": "FORMAL_CURRENT" if credit_row else "NO_RESULT_CREDIT_ADJUDICATION",
            },
            "component_join_status": "READY" if not missing else "PENDING_" + "_".join(missing),
            "formal_score_write": total is not None,
            "pending_reason": None if not missing else f"缺少{'、'.join(missing)}闭合结果，第三项不赋中性总分。",
        })
        records.append(base)

    _rank(records)
    records.sort(
        key=lambda row: (
            row["third_item_score_points"] is None,
            -float(row["third_item_score_points"] or 0),
            str(row["ruler_id"]),
        )
    )
    scores = [float(row["third_item_score_points"]) for row in records if row["third_item_score_points"] is not None]
    old = payloads["combined"]
    result = {
        **{
            key: value
            for key, value in old.items()
            if key not in {"records", "score_recalculation_policy"}
        },
        "schema_id": "emperor-v4-third-item-formal-settlement-v6-current-only",
        "record_count": len(records),
        "score_ready_count": len(scores),
        "C_unassessed_count": sum(row["C50_score_points"] is None for row in records),
        "scope": "当前AB/C/D组件与A120/B80裁决并集；A120非成本锚加成本折算后的A正向及B成果信用，再加C50与军事净毁损尾部",
        "score_contract": {
            "maximum_points": 250,
            "minimum_points": -40,
            "A120_maximum": 120,
            "B80_maximum": 80,
            "C50_maximum": 50,
            "D_cost_role": "GLOBAL_COST_CREDIT_FACTOR_SOURCE_NOT_ADDITIVE",
            "military_net_loss_penalty_range": [-40, 0],
            "formula": "A120_non_cost_anchor + factor * (A120_positive_result_credit + B80) + C50 + military_net_loss_penalty",
            "rounding": "ROUND_FINAL_SCORE_TO_2_DECIMALS",
        },
        "score_recalculation_policy": "A120_CURRENT_PLUS_B80_COST_CREDIT_PLUS_C50_PLUS_MILITARY_NET_LOSS",
        "score_range": {"minimum": min(scores), "maximum": max(scores)},
        "component_coverage_counts": {
            "AB": len(indexed["AB"]),
            "C": len(indexed["C"]),
            "D": len(indexed["D"]),
            "result_credit": len(indexed["result_credit"]),
            "union": len(records),
            "ready": len(scores),
            "pending": len(records) - len(scores),
        },
        "records": records,
    }
    return result


def _write_text_atomic(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.current-third-item-write-tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    temporary.replace(path)


def verify_current_third_item_settlement(workspace_root: Path) -> dict[str, Any]:
    """Validate the formal combined snapshot without rebuilding its components."""
    payload = _load(workspace_root / FORMAL_PATH)
    records = list(payload.get("records") or ())
    if payload.get("schema_id") != "emperor-v4-third-item-formal-settlement-v6-current-only":
        raise ValueError("第三项正式结算schema不合法")
    if payload.get("record_count") != len(records) or len(records) != 201:
        raise ValueError("第三项正式结算覆盖不闭合")
    if len({row.get("ruler_id") for row in records}) != len(records):
        raise ValueError("第三项正式结算存在重复人物ID")

    ready = []
    for row in records:
        score = row.get("third_item_score_points")
        if score is None:
            if row.get("formal_score_write") or not row.get("pending_reason"):
                raise ValueError(f"第三项待结算状态不完整：{row.get('ruler_name')}")
            continue
        components = (
            row.get("A120_non_cost_anchor_points"),
            row.get("A120_positive_result_credit_points"),
            row.get("B80_score_points"),
            row.get("C50_score_points"),
            row.get("cost_credit_factor"),
            row.get("military_net_loss_penalty"),
        )
        if any(value is None for value in components):
            raise ValueError(f"第三项机械计分字段不完整：{row.get('ruler_name')}")
        anchor, positive, b80, c50, factor, penalty = map(float, components)
        expected = round(anchor + factor * (positive + b80) + c50 + penalty, 2)
        if float(score) != expected:
            raise ValueError(f"第三项正式分数与给定裁决不一致：{row.get('ruler_name')}")
        if not row.get("formal_score_write") or row.get("component_join_status") != "READY":
            raise ValueError(f"第三项正式写入状态不闭合：{row.get('ruler_name')}")
        ready.append(row)

    expected_order = sorted(ready, key=lambda row: (-float(row["third_item_score_points"]), str(row["ruler_id"])))
    prior_score: float | None = None
    expected_rank = 0
    for index, row in enumerate(expected_order, 1):
        score = float(row["third_item_score_points"])
        if score != prior_score:
            expected_rank = index
            prior_score = score
        if row.get("rank") != expected_rank:
            raise ValueError(f"第三项正式排名不一致：{row.get('ruler_name')}")
    if records != sorted(
        records,
        key=lambda row: (
            row.get("third_item_score_points") is None,
            -float(row.get("third_item_score_points") or 0),
            str(row["ruler_id"]),
        ),
    ):
        raise ValueError("第三项正式记录顺序不稳定")

    scores = [float(row["third_item_score_points"]) for row in ready]
    coverage = payload.get("component_coverage_counts") or {}
    if coverage.get("union") != len(records) or coverage.get("ready") != len(ready):
        raise ValueError("第三项组件覆盖摘要与正式记录不一致")
    if payload.get("score_ready_count") != len(ready):
        raise ValueError("第三项就绪计数不一致")
    if payload.get("score_range") != {"minimum": min(scores), "maximum": max(scores)}:
        raise ValueError("第三项分数范围不一致")
    return {
        "status": "PASS", "record_count": len(records),
        "score_ready_count": len(ready), "pending_count": len(records) - len(ready),
        "score_range": payload["score_range"],
    }


def _synchronize_current_ab_view(workspace_root: Path) -> None:
    """Put the current A120/B80 values beside the atomic AB adjudications."""
    from emperor_v4.evaluation.five_dynasties_third_item import _render_formal_markdown

    ab_path = workspace_root / AB_PATH
    credit_path = workspace_root / RESULT_CREDIT_ADJUDICATIONS_PATH
    ab_payload = _load(ab_path)
    credit_payload = _load(credit_path)
    handoff_payload = _load(workspace_root / AB_HANDOFF_ADJUDICATIONS_PATH)
    credits = _index(credit_payload["records"], "result_credit")
    threat_supplements = {
        str(item["ruler_id"]): item
        for item in handoff_payload.get("primary_threat_supplements") or ()
    }
    for row in ab_payload["records"]:
        name = str(row["ruler_name"])
        credit = credits.get(name)
        if credit is None or str(credit["ruler_id"]) != str(row["ruler_id"]):
            raise ValueError(f"{name}缺少同主体A120/B80当前裁决")
        parts = [_decompose_a120_axis(credit["axes"][axis]) for axis in ("A1", "A2")]
        anchor = round(sum(part[0] for part in parts), 2)
        positive = round(sum(part[1] for part in parts), 2)
        a120 = round(float(credit["A120_points"]), 2)
        b80 = round(float(credit["B80_adjudication"]["B80_points"]), 2)
        if round(anchor + positive, 2) != a120:
            raise ValueError(f"{name} A120当前拆分不闭合")
        row.update(
            {
                "A120_non_cost_anchor_points": anchor,
                "A120_positive_result_credit_points": positive,
                "A120_score_points": a120,
                "B80_score_points": b80,
                "AB200_score_points": round(a120 + b80, 2),
                "A120_axis_adjudications": credit["axes"],
                "B80_adjudication": credit["B80_adjudication"],
            }
        )
        threat_supplement = threat_supplements.get(str(row["ruler_id"]))
        if threat_supplement:
            refs = list(dict.fromkeys(
                str(ref)
                for ref in threat_supplement.get("primary_threat_refs") or ()
            ))
            allowed_refs = {
                str(ref) for ref in row.get("parent_cycle_refs") or ()
            } | {
                str(ref) for ref in row.get("evidence_event_refs") or ()
            }
            if not refs or not set(refs).issubset(allowed_refs):
                raise ValueError(f"{name}的AB主压力补充引用越界")
            if not str(threat_supplement.get("reason") or "").strip():
                raise ValueError(f"{name}的AB主压力补充缺少理由")
            row["primary_threat_refs"] = refs
            row["primary_threat_basis"] = str(threat_supplement["reason"])
    ab_payload.update(
        {
            "schema_id": "emperor-v4-third-item-ab-formal-settlement-v2-current-a120-b80",
            "score_contract": {
                "maximum_points": 200,
                "A120_maximum": 120,
                "B80_maximum": 80,
                "AB200_formula": "A120 + B80",
                "A120_formula": "sum(0.6*clamp(0,100,12*end+10*attributable_delta+max(ceiling_bonus,maintenance_bonus)-max(reversal_penalty,within_band_deterioration_penalty)))",
                "B80_formula": "80*(0.55*B1_rate+0.45*B2_rate)*(0.70+0.30*B4_rate)",
                "legacy_AB_score_points": "ATOMIC_AXIS_DIAGNOSTIC_ONLY_NOT_CURRENT_AB_TOTAL",
            },
        }
    )
    _write_text_atomic(ab_path, json.dumps(ab_payload, ensure_ascii=False, indent=2) + "\n")
    _write_text_atomic(ab_path.with_suffix(".md"), _render_formal_markdown("AB", ab_payload["records"]))


def _synchronize_current_c_outcome_view(workspace_root: Path) -> None:
    from emperor_v4.evaluation.five_dynasties_third_item import _render_formal_markdown

    """Keep every current C task visible without inventing missing outcomes."""
    c_path = workspace_root / C_PATH
    payload = _load(c_path)
    adjudication_payload = _load(workspace_root / C_OUTCOME_ADJUDICATIONS_PATH)
    adjudications = {
        str(item["ruler_id"]): item
        for item in adjudication_payload.get("adjudications") or ()
    }
    shared_binding_adjudications = {
        str(item["parent_cycle_ref"]): item
        for item in adjudication_payload.get(
            "shared_parent_ruler_binding_adjudications", ()
        )
    }
    if len(shared_binding_adjudications) != len(
        adjudication_payload.get("shared_parent_ruler_binding_adjudications", ())
    ):
        raise ValueError("C共享父任务人物绑定裁决存在重复父任务")
    for row in payload["records"]:
        adjudication = adjudications.get(str(row["ruler_id"])) or {}
        excluded_out_of_window = {
            str(ref)
            for ref in adjudication.get("excluded_out_of_window_parent_refs") or ()
        }
        capability_only = {
            str(ref) for ref in row.get("capability_only_parent_refs") or ()
        }
        current_refs = [
            str(ref)
            for ref in row.get("current_item_task_refs") or ()
            if str(ref) not in excluded_out_of_window
        ]
        if not current_refs:
            current_refs = [
                str(ref)
                for ref in row.get("independent_task_groups") or ()
                if (
                    isinstance(ref, str)
                    and str(ref) not in capability_only
                    and str(ref) not in excluded_out_of_window
                )
            ]
        current_refs = list(dict.fromkeys(current_refs))
        independent_cross_item_refs = list(dict.fromkeys(
            str(ref)
            for ref in adjudication.get(
                "cross_item_independent_information_refs", ()
            )
        ))
        if independent_cross_item_refs:
            current_or_capability = set(current_refs) | capability_only
            if not set(independent_cross_item_refs).issubset(current_or_capability):
                raise ValueError(
                    f"{row['ruler_name']}的C跨项独立信息引用越界"
                )
            row["cross_item_independent_information_refs"] = (
                independent_cross_item_refs
            )
        else:
            row.pop("cross_item_independent_information_refs", None)
        if excluded_out_of_window:
            existing_refs = {
                str(ref)
                for ref in row.get("independent_task_groups") or ()
            } | {
                str(ref)
                for ref in row.get("major_system_success_refs") or ()
            } | {
                str(ref)
                for ref in row.get("major_system_failure_refs") or ()
            } | {
                str(ref)
                for ref in row.get("excluded_out_of_window_parent_refs") or ()
            }
            if not excluded_out_of_window.issubset(existing_refs):
                unknown = sorted(excluded_out_of_window - existing_refs)
                raise ValueError(
                    f"{row['ruler_name']}的C越窗排除引用不属于当前任务: {unknown}"
                )
            row["independent_task_groups"] = [
                ref for ref in row.get("independent_task_groups") or ()
                if str(ref) not in excluded_out_of_window
            ]
            row["independent_task_count"] = len(row["independent_task_groups"])
            row["major_system_success_refs"] = [
                ref for ref in row.get("major_system_success_refs") or ()
                if str(ref) not in excluded_out_of_window
            ]
            row["major_system_failure_refs"] = [
                ref for ref in row.get("major_system_failure_refs") or ()
                if str(ref) not in excluded_out_of_window
            ]
            row["excluded_out_of_window_parent_refs"] = sorted(
                excluded_out_of_window
            )
            row["cap_reasons"] = [str(adjudication["reason"])]
        else:
            row.pop("excluded_out_of_window_parent_refs", None)
        previous = dict(row.get("task_outcome_profile") or {})
        class_by_ref = {
            str(ref): str(outcome)
            for outcome, outcome_refs in dict(
                previous.get("return_class_refs") or {}
            ).items()
            for ref in outcome_refs or ()
        }
        resolved = [
            (ref, class_by_ref.get(ref, "UNKNOWN")) for ref in current_refs
        ]
        counts: dict[str, int] = {}
        outcome_refs: dict[str, list[str]] = {}
        for ref, outcome in resolved:
            counts[outcome] = counts.get(outcome, 0) + 1
            outcome_refs.setdefault(outcome, []).append(ref)
        counts = dict(sorted(counts.items()))
        outcome_refs = dict(sorted(outcome_refs.items()))
        known = sum(count for outcome, count in counts.items() if outcome != "UNKNOWN")
        profile_source = str(previous.get("source") or "CURRENT_C_TASKS")
        if (
            any(outcome == "UNKNOWN" for _, outcome in resolved)
            and not profile_source.endswith("_WITH_EXPLICIT_UNKNOWN_CLOSURE")
        ):
            profile_source += "_WITH_EXPLICIT_UNKNOWN_CLOSURE"
        row["current_item_task_count"] = len(current_refs)
        row["current_item_task_refs"] = current_refs
        row["task_outcome_profile"] = {
            **previous,
            "source": profile_source,
            "selected_task_count": len(current_refs),
            "known_outcome_count": known,
            "return_class_counts": counts,
            "return_class_refs": outcome_refs,
            "status": "QUANTIFIED" if known else (
                "UNQUANTIFIED" if current_refs else "NOT_APPLICABLE"
            ),
        }
        row["current_task_basis_reason"] = (
            f"当前第三项独立体系压力父周期{len(current_refs)}项，已知结果{known}项，"
            f"回报剖面={counts}；重大体系胜绩"
            f"{len(row.get('major_system_success_refs') or ())}项、重大体系失败"
            f"{len(row.get('major_system_failure_refs') or ())}项。"
        )
    shared_owners: dict[str, list[tuple[str, str]]] = {}
    for row in payload["records"]:
        capability_only = {
            str(ref) for ref in row.get("capability_only_parent_refs") or ()
        }
        for ref in row.get("independent_task_groups") or ():
            ref = str(ref)
            shared_owners.setdefault(ref, []).append((
                str(row["ruler_id"]),
                (
                    "AUTHORIZED_CAPABILITY_ONLY_VIEW"
                    if ref in capability_only
                    else "CURRENT_RULER_WINDOW_VIEW"
                ),
            ))
    duplicated = {
        ref: sorted(bindings)
        for ref, bindings in shared_owners.items()
        if len(bindings) > 1
    }
    if set(duplicated) != set(shared_binding_adjudications):
        raise ValueError("C共享父任务人物绑定裁决没有精确覆盖当前重复父任务集合")
    for ref, expected in duplicated.items():
        decision = shared_binding_adjudications[ref]
        actual = sorted(
            (
                str(binding["ruler_id"]),
                str(binding["consumption_scope"]),
            )
            for binding in decision.get("ruler_bindings") or ()
        )
        if actual != expected:
            raise ValueError(f"C共享父任务人物绑定与当前消费范围不一致: {ref}")
        if (
            decision.get("binding_status")
            != "EXPLICIT_LEGACY_PARENT_RULER_SCOPE_CLOSED"
            or not str(decision.get("reason") or "").strip()
        ):
            raise ValueError(f"C共享父任务人物绑定裁决未闭合: {ref}")
    payload["shared_parent_ruler_binding_contract"] = {
        "status": "CLOSED",
        "shared_parent_count": len(duplicated),
        "binding_count": sum(len(bindings) for bindings in duplicated.values()),
        "source": str(C_OUTCOME_ADJUDICATIONS_PATH).replace("\\", "/"),
        "rule": "同一父任务按显式ruler_id与CURRENT/CAPABILITY_ONLY范围分别消费，不复制另一人物行动、结果或成本。",
    }
    _write_text_atomic(c_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    _write_text_atomic(
        c_path.with_suffix(".md"),
        _render_formal_markdown("C", payload["records"]),
    )


def write_current_third_item_settlement(workspace_root: Path) -> dict[str, Any]:
    _synchronize_current_ab_view(workspace_root)
    _synchronize_current_c_outcome_view(workspace_root)
    payload = build_current_third_item_settlement(workspace_root)
    json_path = workspace_root / FORMAL_PATH
    markdown_path = json_path.with_suffix(".md")
    _write_text_atomic(
        json_path,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )
    _write_text_atomic(markdown_path, _render_current_weighted_markdown(payload["records"]))
    return payload
