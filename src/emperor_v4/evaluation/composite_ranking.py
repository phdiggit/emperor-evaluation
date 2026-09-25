from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, median
from typing import Any, Mapping

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.canonical_ruler_pool import canonical_item_name
from emperor_v4.evaluation.composite_details import (
    component_details, load_detail_sources,
)
from emperor_v4.evaluation.first_item_markdown_settlement import (
    load_first_item_markdown_settlement,
)


POOL_PATH = "config/common/canonical-ruler-pool.json"
GOVERNANCE_CONTEXT = "config/common/composite-governance-context.json"
OUTPUT_JSON = "docs/评分结算/净收益/00-统治绩效综合评分榜.json"
OUTPUT_MARKDOWN = "docs/评分结算/净收益/00-统治绩效综合评分榜.md"
FIRST_ITEM_ADD_ON_COEFFICIENT = 0.20
FIRST_ITEM_SENSITIVITY_COEFFICIENTS = (0.18, 0.20, 0.22)

SETTLEMENT_SPECS = {
    "second_item": (
        "docs/评分结算/净收益/第二项治国净收益/01-第二项治国净收益正式结算.json",
        "second_item_score",
    ),
    "third_item": (
        "docs/评分结算/净收益/第三项军事与边疆净收益/02-第三项正式结算.json",
        "third_item_score_points",
    ),
    "fourth_item": (
        "docs/评分结算/净收益/第四项文明与国家整合收益/01-第四项文明与国家整合收益正式结算.json",
        "fourth_item_signed_adjustment",
    ),
}


def _read_json(path: Path) -> dict[str, Any]:
    return load_json(path)


def _competition_rank(scores: list[float], index: int) -> int:
    return scores.index(scores[index]) + 1


def _index_records(payload: Mapping[str, Any], label: str) -> dict[str, Mapping[str, Any]]:
    records = payload.get("records") or []
    indexed = {str(row["ruler_id"]): row for row in records}
    if len(indexed) != len(records):
        raise ValueError(f"{label}存在重复ruler_id")
    return indexed


def _weight_sensitivity(
    records: list[dict[str, Any]], inputs: Mapping[str, Mapping[str, float]]
) -> dict[str, Any]:
    """Evaluate a declared finite grid without changing the formal adjudications."""
    scenarios = []
    for tilt in (-0.2, 0.0, 0.2):
        normalizer = 637 / (387 * (1 + tilt) + 250 * (1 - tilt))
        for founder in FIRST_ITEM_SENSITIVITY_COEFFICIENTS:
            for civilization in (0.8, 1.0, 1.2):
                scenario_id = f"g{tilt:+.1f}_f{founder:.2f}_c{civilization:.1f}"
                scenarios.append({
                    "id": scenario_id,
                    "common_tilt": tilt,
                    "second_item_multiplier": (1 + tilt) * normalizer,
                    "third_item_multiplier": (1 - tilt) * normalizer,
                    "first_item_coefficient": founder,
                    "fourth_item_multiplier": civilization,
                })
    scenario_ranks: dict[str, dict[str, int]] = {}
    for scenario in scenarios:
        totals = {}
        for ruler_id, values in inputs.items():
            first = values["first_item"]
            addition = (
                scenario["first_item_coefficient"] * 637 * (first / 240) ** 1.25
                if first > 0 else 0.0
            )
            totals[ruler_id] = round(
                values["second_item"] * scenario["second_item_multiplier"]
                + values["third_item"] * scenario["third_item_multiplier"]
                + addition
                + values["fourth_item"] * scenario["fourth_item_multiplier"], 2
            )
        ordered = sorted(totals, key=lambda ruler_id: (-totals[ruler_id], ruler_id))
        ranks = {}
        last_score = None
        for position, ruler_id in enumerate(ordered, 1):
            if totals[ruler_id] != last_score:
                rank = position
            ranks[ruler_id] = rank
            last_score = totals[ruler_id]
        scenario_ranks[scenario["id"]] = ranks

    def extent(ruler_id: str, selected: list[dict[str, Any]]) -> dict[str, int]:
        ranks = [scenario_ranks[s["id"]][ruler_id] for s in selected]
        return {"best": min(ranks), "worst": max(ranks)}

    baseline = "g+0.0_f0.20_c1.0"
    for row in records:
        ruler_id = row["ruler_id"]
        if scenario_ranks[baseline][ruler_id] != row["rank"]:
            raise ValueError("权重情景基准与正式名次不一致")
        row["weight_sensitivity"] = {
            "all_scenarios": extent(ruler_id, scenarios),
            "add_ons_only": extent(ruler_id, [s for s in scenarios if s["common_tilt"] == 0]),
            "first_item_only": extent(ruler_id, [s for s in scenarios if s["common_tilt"] == 0 and s["fourth_item_multiplier"] == 1]),
            "fourth_item_only": extent(ruler_id, [s for s in scenarios if s["common_tilt"] == 0 and s["first_item_coefficient"] == FIRST_ITEM_ADD_ON_COEFFICIENT]),
            "common_items_only": extent(ruler_id, [s for s in scenarios if s["first_item_coefficient"] == FIRST_ITEM_ADD_ON_COEFFICIENT and s["fourth_item_multiplier"] == 1]),
            "scenario_ranks": {s["id"]: scenario_ranks[s["id"]][ruler_id] for s in scenarios},
        }
    return {
        "status": "FINITE_WEIGHT_GRID_EVALUATED",
        "baseline_scenario": baseline,
        "scenario_count": len(scenarios),
        "common_positive_denominator": 637,
        "common_weight_policy": "normalize (1+d, 1-d) so 387*w2 + 250*w3 = 637",
        "scope": "finite declared weight scenarios only; not a confidence interval or continuous bound; evidence and adjudications fixed",
        "scenarios": scenarios,
    }


def build_composite_ranking(workspace_root: Path) -> dict[str, Any]:
    pool_path = workspace_root / POOL_PATH
    pool = _read_json(pool_path)
    settlement_paths = {
        item: workspace_root / relative
        for item, (relative, _) in SETTLEMENT_SPECS.items()
    }
    payloads = {item: _read_json(path) for item, path in settlement_paths.items()}
    indexed = {
        item: _index_records(payload, item) for item, payload in payloads.items()
    }
    first_item_scores: dict[str, float] = {}
    for row in load_first_item_markdown_settlement(workspace_root):
        canonical_name = canonical_item_name("first_item", row["name"])
        if canonical_name in first_item_scores:
            raise ValueError(f"第一项别名归一后人物重复：{canonical_name}")
        first_item_scores[canonical_name] = row["total"]
    detail_sources = load_detail_sources(workspace_root)

    ready = [
        row
        for row in pool["records"]
        if row["settlement_readiness"] == "COMPOSITE_READY"
    ]
    context_payload = _read_json(workspace_root / GOVERNANCE_CONTEXT)
    if (context_payload.get("schema_version") != "composite-governance-context-v1"
            or context_payload.get("role") != "non_scoring_comparison_context"):
        raise ValueError("综合榜治理规模与复杂度入口无效")
    context_rows = {row["ruler_id"]: row for row in context_payload["records"]}
    if len(context_rows) != len(context_payload["records"]):
        raise ValueError("综合榜治理背景人物重复")
    ready_ids = {row["ruler_id"] for row in ready}
    if set(context_rows) != ready_ids:
        raise ValueError("综合榜治理背景未覆盖当前全部入榜对象")
    context_labels = context_payload["labels"]
    for pool_row in ready:
        context = context_rows[pool_row["ruler_id"]]
        second_id = pool_row["source_item_ids"]["second_item"]
        if (context["ruler_name"] != pool_row["ruler_name"]
                or context["actual_power_window"] != pool_row["actual_power_window"]
                or context["formal_polity"] != indexed["second_item"][second_id]["polity"]):
            raise ValueError(f"综合榜治理背景人物或窗口漂移：{pool_row['ruler_id']}")
        if (context["scale_band"] not in context_labels["scale"]
                or context["complexity_band"] not in context_labels["complexity"]
                or context["scale_label"] != context_labels["scale"][context["scale_band"]]
                or context["complexity_label"] != context_labels["complexity"][context["complexity_band"]]
                or not context.get("display_polity")
                or not context.get("basis") or not context.get("source_refs")):
            raise ValueError(f"综合榜治理背景档位或依据缺失：{pool_row['ruler_id']}")
        for ref in context["source_refs"]:
            if not ref.startswith(("https://", "http://")) and not (workspace_root / ref.split("#", 1)[0]).is_file():
                raise ValueError(f"综合榜治理背景来源不存在：{ref}")
    pending = [
        {
            "ruler_id": row["ruler_id"],
            "ruler_name": row["ruler_name"],
            "polity": row["polity"],
            "settlement_readiness": row["settlement_readiness"],
            "not_ranked_reason": (
                "PENDING_SECOND_ITEM_FORMAL_SETTLEMENT"
                if row["settlement_readiness"] == "PENDING_SECOND_ITEM_FORMAL_SETTLEMENT"
                else "PENDING_THIRD_ITEM_FORMAL_SETTLEMENT"
            ),
        }
        for row in pool["records"]
        if row["pool_status"] == "INCLUDED"
        and row["settlement_readiness"] != "COMPOSITE_READY"
    ]
    if len(ready) != pool["composite_ready_count"]:
        raise ValueError("综合就绪人数与正式池声明不一致")
    pending_second = [
        row for row in pending
        if row["not_ranked_reason"] == "PENDING_SECOND_ITEM_FORMAL_SETTLEMENT"
    ]
    pending_third = [
        row for row in pending
        if row["not_ranked_reason"] == "PENDING_THIRD_ITEM_FORMAL_SETTLEMENT"
    ]
    if len(pending_second) != pool["pending_second_item_count"]:
        raise ValueError("待第二项结算人数与正式池声明不一致")
    if len(pending_third) != pool.get("pending_third_item_count", 0):
        raise ValueError("待第三项结算人数与正式池声明不一致")

    pending_fourth: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    sensitivity_inputs: dict[str, dict[str, float]] = {}
    for pool_row in ready:
        source_ids = pool_row["source_item_ids"]
        fourth_row = indexed["fourth_item"].get(source_ids.get("fourth_item"))
        if fourth_row and fourth_row.get("status") == "UNRESOLVED_EVIDENCE_GAP":
            if fourth_row.get("fourth_item_signed_adjustment") is not None:
                raise ValueError(f"{pool_row['ruler_name']}第四项证据缺口仍有确定分值")
            pending_fourth.append({
                "ruler_id": pool_row["ruler_id"],
                "ruler_name": pool_row["ruler_name"],
                "polity": pool_row["polity"],
                "not_ranked_reason": "UNRESOLVED_FOURTH_ITEM_EVIDENCE_GAP",
            })
            continue
        first_source_name = (pool_row.get("source_item_names") or {}).get("first_item")
        first_lookup_name = canonical_item_name(
            "first_item", first_source_name or pool_row["ruler_name"]
        )
        first_value = first_item_scores.get(first_lookup_name)
        if first_source_name and first_value is None:
            raise ValueError(
                f"{pool_row['ruler_name']}的第一项来源“{first_source_name}”归一后未找到正式分"
            )
        first_applicable = first_value is not None
        first_score = float(first_value) if first_applicable else 0.0
        scores: dict[str, float] = {"first_item": first_score}
        for item, (_, score_field) in SETTLEMENT_SPECS.items():
            source_id = source_ids.get(item)
            if not source_id or source_id not in indexed[item]:
                raise ValueError(f"{pool_row['ruler_name']}缺少{item}正式记录")
            value = indexed[item][source_id].get(score_field)
            if value is None:
                raise ValueError(f"{pool_row['ruler_name']}的{item}正式分为空")
            scores[item] = float(value)

        first_add_on = (
            FIRST_ITEM_ADD_ON_COEFFICIENT * 637 * (scores["first_item"] / 240) ** 1.25
            if scores["first_item"] > 0
            else 0.0
        )
        common_score = scores["second_item"] + scores["third_item"]
        total_score = common_score + first_add_on + scores["fourth_item"]
        sensitivity_inputs[pool_row["ruler_id"]] = scores
        records.append(
            {
                "rank": None,
                "ruler_id": pool_row["ruler_id"],
                "ruler_name": pool_row["ruler_name"],
                "polity": pool_row["polity"],
                "governance_context": context_rows[pool_row["ruler_id"]],
                "first_item_status": (
                    "APPLICABLE" if first_applicable else "NOT_APPLICABLE"
                ),
                "first_item_raw_score": (
                    round(scores["first_item"], 1) if first_applicable else None
                ),
                "first_item_add_on": round(first_add_on, 2),
                "second_item_score": round(scores["second_item"], 1),
                "third_item_score": round(scores["third_item"], 2),
                "fourth_item_adjustment": round(scores["fourth_item"], 1),
                "common_score": round(common_score, 2),
                "total_score": round(total_score, 2),
            }
        )

    ready_by_id = {row["ruler_id"]: row for row in ready}
    for row in records:
        row["component_details"] = component_details(detail_sources, ready_by_id[row["ruler_id"]], row)
    records.sort(key=lambda row: (-row["total_score"], row["ruler_id"]))
    scores = [float(row["total_score"]) for row in records]
    for index, row in enumerate(records):
        row["rank"] = _competition_rank(scores, index)

    sensitivity = _weight_sensitivity(records, sensitivity_inputs)
    from emperor_v4.evaluation.evidence_sensitivity import annotate_ranking
    annotate_ranking(workspace_root, records, pool['records'], detail_sources)
    from emperor_v4.evaluation.prudent_score_intervals import attach as attach_prudent_intervals
    prudent_coverage = attach_prudent_intervals(workspace_root, records)
    pending.sort(key=lambda row: row["ruler_id"])
    fourth_review = {
        key: payloads["fourth_item"].get(key, {})
        for key in ("promotion_gate", "coverage_completion_gate")
    }
    fourth_review_complete = all(
        bool(gate) and all(value is True for value in gate.values())
        for gate in fourth_review.values()
    )
    return {
        "schema_id": "emperor-v4-composite-ranking-v1",
        "status": (
            "FORMAL_CURRENT" if fourth_review_complete
            else "CURRENT_SNAPSHOT_PENDING_FOURTH_ITEM_REVIEW"
        ),
        "fourth_item_semantic_review_complete": fourth_review_complete,
        "fourth_item_review_gates": fourth_review,
        "ranking_population": "COMPOSITE_READY",
        "formula": f"T = S2 + S3 + {FIRST_ITEM_ADD_ON_COEFFICIENT:.2f} * 637 * (S1 / 240) ^ 1.25 + CIV4",
        "first_item_not_applicable_policy": "F=0; not treated as a zero-score failure",
        "rank_tie_policy": "competition_rank_then_ruler_id",
        "governance_context_legend": {
            "labels": context_labels,
            "rules": context_payload["rules"],
        },
        "prudent_score_interval_coverage": prudent_coverage,
        "weight_sensitivity": sensitivity,
        "score_precision": "source scores retained; F and T rounded to 2 decimals",
        "record_count": len(records),
        "pending_second_item_count": len(pending_second),
        "pending_third_item_count": len(pending_third),
        "pending_fourth_item_count": len(pending_fourth),
        "pending_fourth_item_records": sorted(pending_fourth, key=lambda row: row["ruler_id"]),
        "mean_score": round(mean(scores), 2),
        "median_score": round(median(scores), 2),
        "min_score": min(scores),
        "max_score": max(scores),
        "pending_second_item_records": pending_second,
        "pending_third_item_records": pending_third,
        "records": records,
    }


def render_composite_ranking_markdown(payload: Mapping[str, Any]) -> str:
    records = payload["records"]
    context_labels = payload["governance_context_legend"]["labels"]
    by_name = {row["ruler_name"]: row for row in records}

    def rank_range(row: Mapping[str, Any], group: str = "all_scenarios") -> str:
        value = row["weight_sensitivity"][group]
        return f"{value['best']}—{value['worst']}"

    def summary(name: str) -> str:
        row = by_name[name]
        return (
            f"{name}第{row['rank']}（{row['total_score']:.2f}分）"
        )

    leader = records[0]
    runner_up = records[1]
    lead = float(leader["total_score"]) - float(runner_up["total_score"])
    stable_count = sum(
        row["weight_sensitivity"]["all_scenarios"]["best"]
        == row["weight_sensitivity"]["all_scenarios"]["worst"] for row in records
    )
    widest = sorted(records, key=lambda row: (
        -(row["weight_sensitivity"]["all_scenarios"]["worst"]
          - row["weight_sensitivity"]["all_scenarios"]["best"]), row["ruler_id"]
    ))[:5]
    sensitivity_examples = "；".join(
        f"{row['ruler_name']}：基准第{row['rank']}，全部情景{rank_range(row)}，"
        f"仅奠基调权{rank_range(row, 'first_item_only')}，"
        f"仅文明调权{rank_range(row, 'fourth_item_only')}，"
        f"仅共同项调权{rank_range(row, 'common_items_only')}"
        for row in widest
    )

    pending_notes = []
    if payload["pending_second_item_count"]:
        pending_notes.append(f"{payload['pending_second_item_count']}人待第二项正式结算")
    if payload["pending_third_item_count"]:
        pending_notes.append(f"{payload['pending_third_item_count']}人待第三项正式结算")
    if payload["pending_fourth_item_count"]:
        pending_notes.append(f"{payload['pending_fourth_item_count']}人存在第四项证据缺口")
    ranking_status = (
        f"> 本榜当前列出正式评价池中`COMPOSITE_READY`的{payload['record_count']}人。"
        + (("另有" + "；".join(pending_notes) + "；") if pending_notes else "")
        + "未结算或未闭合输入不按零分填补。排名只由现行合同与正式分项生成，不按历史名望或榜形反推。"
    )

    lines = [
        "# 皇帝统治绩效综合评分榜",
        "",
        "> 本榜由第一项条件附加分、第二项治国净收益、第三项军事与边疆净收益及第四项文明调整合成；"
        "人物画像与历史影响独立评价，不参与本榜。",
        "",
        "> 这里的统治绩效是带成本与损害修正的综合评价：包含政权奠基贡献、治理与军事手段及体系有效性、治理/安全/文明结果和可归责成本；不等同于人物画像的能力总评或历史影响。",
        "",
        ranking_status,
        "",
        "## 先读口径",
        "",
        "**史料不是按条数投票。** 本榜遵循最小充分证据：单一但可定位、窗口匹配、对象明确且直接闭合结果的宏观总评，可以承担主锚；多源互证是增强项，不是机械门槛。资料稀疏、史料篇幅短或低于HIGH的标签本身，不自动降档、降置信或制造浮动区间。",
        "",
        "**治理规模／复杂度只作比较背景。** 第二项绝对治理结果不按政权大小折扣。当前没有跨时代稳定且副作用可控的复杂度换算机制；强行加权容易重复奖励已在其他项目体现的规模与压力、反向奖励制度碎片化、二次压低小政权的真实绝对结果，并使排名过度依赖人为系数。",
        "",
        "**去重是去同一结果，不是禁止同一机制产生多个结果。** 同一制度或治理机制若分别产生已经闭合的行政、反馈、民生、财政、安全、军事或文明结果，各项可分别计入；禁止的是把同一最终收益或损害换名后重复换分。多个项目同时偏高或偏低、总分明显离群，都只能触发证据、归责、公式和去重复核，不能成为自动配平理由。",
        "",
        "本榜衡量现行规则下的统治绩效，不衡量收益总量、人均或年均收益，也不等同于王朝体量、历史功业总量或综合历史地位排名。",
        "",
        "## 计分与不确定性",
        "",
        "综合分公式：`T = 第二项 + 第三项 + F + 第四项调整`，其中"
        f"`F = {FIRST_ITEM_ADD_ON_COEFFICIENT:.2f} × 637 × (第一项净分 / 240)^1.25`。第一项不适用者是`F=0`，"
        "不是把“不适用”判成第一项零分。总分保留两位小数，采用竞争排名；同分记录按"
        "规范`ruler_id`稳定排序。",
        "",
        "总分小数表示规则计算精度，不代表史料与历史判断具有同等精度。名次为现行规则及"
        "正式裁决下的条件排序；微小分差不应直接解释为可辨识的历史优劣。表中范围是所列离散"
        "权重情景下的最好至最差名次，不是置信区间，也不是连续参数范围的严格界限。"
        "史料、归责、分项裁决及第一项指数均固定；与下列现有史料审慎分数区间是不同问题。",
        "",
        "正式综合分是已采信四项裁决按现行权重计算的基准点，审慎分数区间不取代该点。"
        "审慎区间固定权重，按现有史料中逐人复核的军事成本档与具名治理联动命题计算；"
        "不标统计覆盖率，也不保证未来新增史料不能重开。非单点区间可包含未被证实可同时达到的端点；"
        "单点表示本轮现有语料未留下有源异档，不表示历史真值已穷尽。",
        f"逐人区间已覆盖{payload['prudent_score_interval_coverage']['pool_count']}名入榜者；"
        f"其中{payload['prudent_score_interval_coverage']['nonpoint_count']}人为非单点。",
        "",
        "> 分差和离群只具有诊断意义。多项独立结果同向可以真实累积成明显领先或落后；"
        "复核只检查证据、归责、公式和去重，不以贴合名望、缩小分差或改变特定人物名次为目标。",
        "",
        (
            f"当前均分{payload['mean_score']:.2f}，中位数{payload['median_score']:.2f}，"
            f"范围{payload['min_score']:.2f}—{payload['max_score']:.2f}。"
        ),
        "",
        "## 完整总榜",
        "",
        ("治理规模／复杂度是非计分背景：规模按"
         + '、'.join(payload['governance_context_legend']['labels']['scale'].values())
         + "四档；复杂度按"
         + '、'.join(payload['governance_context_legend']['labels']['complexity'].values())
         + "四档。"),
        payload['governance_context_legend']['rules']['window']
        + payload['governance_context_legend']['rules']['scoring'],
        payload['governance_context_legend']['rules']['scale'],
        payload['governance_context_legend']['rules']['complexity'],
        "",
        "以下两组名次范围固定正式裁决，只改变权重：仅附加项覆盖9组，全部调权覆盖27组。"
        "它们不与审慎分数区间自动合成；条件端点未证明可达，不能据此生成名次。计算方法见下方折叠说明。",
        "",
        "| 正式名次 | 人物 | 政权 | 治理规模／复杂度 | 共同项合计 | 奠基附加F | 文明调整 | 正式综合分 | 现有史料审慎分数区间 | 仅附加项调权名次范围 | 全部调权情景名次范围 |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in records:
        context = row['governance_context']
        governance_display = (context_labels['scale'][context['scale_band']] + '／'
                              + context_labels['complexity'][context['complexity_band']])
        lines.append(
            f"| {row['rank']} | {row['ruler_name']} | {context['display_polity']} | {governance_display} | "
            f"{row['common_score']:.2f} | {row['first_item_add_on']:.2f} | "
            f"{row['fourth_item_adjustment']:+.1f} | **{row['total_score']:.2f}** | "
            f"{row['prudent_score_interval']['lower']:.2f}—{row['prudent_score_interval']['upper']:.2f} | "
            f"{rank_range(row, 'add_ons_only')} | {rank_range(row)} |"
        )


    coverage=payload['prudent_score_interval_coverage']
    lines.extend(['', '## 审慎区间', '',
                  '完整总榜逐人列出现有史料审慎分数区间。区间只纳入当前语料下具名、有源、可计价的档位或成本替代解释；'
                  '史料条数、材料稀疏、置信度标签和人物名望本身都不自动生成区间。正式综合分仍采用已采信裁决，审慎端点用于显示现有证据允许的条件波动。', '',
                  f'当前{coverage["nonpoint_count"]}人列非单点区间；单点仅表示本轮已登记语料没有留下可定位的有源异档，不表示历史真值已穷尽。', '',
                  '[逐人档位候选、触发事实及来源](综合分析/02-证据裁决敏感性.md)', ''])
    supported=[(row,alt) for row in records
               for alt in row['evidence_assessment']['public_projection']['supported_alternatives']]
    if supported:
        lines.extend(['### 已采信的其他合法解释', '',
                      '| 人物 | 解释 | 替代总分及分差 | 条件名次 |', '|---|---|---:|---:|'])
        for row,alt in supported:
            lines.append(f"| {row['ruler_name']} | {alt['question']} | {alt['total_score']:.2f}（{alt['delta']:+.2f}） | {alt['rank']} |")
        lines.append('')

    lines.extend(["",
        "## 排名分析",
        "",
        "### 榜首与得分结构",
        "",
        (
            f"在现行结算下，{leader['ruler_name']}以{leader['total_score']:.2f}分居首，结算分比第二名"
            f"{runner_up['ruler_name']}高{lead:.2f}分。其构成为：第一项折算"
            f"{leader['first_item_add_on']:.2f}、第二项{leader['second_item_score']:.1f}、"
            f"第三项{leader['third_item_score']:.2f}、第四项{leader['fourth_item_adjustment']:+.1f}。头部差距来自前四项正式结果的共同合成，"
            f"其权重情景名次范围为{rank_range(leader)}；第二名的范围为{rank_range(runner_up)}。"
        ),
        "",
        (
            "综合名次由第二、第三项共同分、第一项条件附加分和第四项有符号调整共同决定。"
            "因此单一项目的高分不会自动转化为总榜高位；不同对象可以通过多项稳定、创业附加或"
            "文明调整形成不同的得分结构。"
        ),
        "",
        "### 名望与名次的差异",
        "",
        (
            "现行结果中，"
            + "；".join(
                summary(name)
                for name in ("嬴政", "刘彻", "朱元璋", "刘邦", "刘裕", "拓跋焘")
                if name in by_name
            )
            + "。这些人的长板分散在第一项、第二项A制度建设或第三项，综合公式却以第二、三项共同净收益为主体，"
            "因此不会自动把统一、扩张或制度名望等同于总榜高位。"
        ),
        "",
        "朱棣的靖难不满足第一项政权奠基准入；其第二项按1402—1424年统治窗口结算，"
        "战后清洗及持续后果与后续主动成本分别归责，不把靖难战争本身的损害混入。"
        "李渊的创业成果则须与李世民按阶段归责。具体依据见分项结算。",
        "",
        "第一项按共同正向上限的20%及指数1.25折算，附加分最多127.4分；"
        "第一项净分、准入边界及跨项成果与成本去重规则继续按正式合同执行。"
        "该系数统一体现创业贡献，不按个别人物的去重减分补回。",
        "",
        "<details>",
        "<summary>权重情景：计算方法与观察例</summary>",
        "",
        "以下是诊断设置，不修改正式权重，也不根据人物名次选择参数：",
        "",
        "- 奠基附加系数取18%、20%、22%；文明调整倍数取0.8、1、1.2，正负端同步缩放。共同项固定时形成9种附加项组合。",
        "- 共同项倾斜参数d取-0.2、0、0.2，以(1+d, 1-d)分别乘第二、三项，再同乘637/[387×(1+d)+250×(1-d)]，保持共同正向上限637及奠基附加尺度一致。",
        f"- 三组参数全组合共{payload['weight_sensitivity']['scenario_count']}种情景，包含基准；总分仍保留两位小数并采用竞争排名。所有情景采用同一入榜池，未结算对象不参与。",
        "",
        f"当前{stable_count}人在全部所测情景中名次不变，{len(records) - stable_count}人发生变化。"
        "范围窄仅表示对这些权重情景较稳定；范围宽者应结合分项结构理解。范围重叠不直接判同档，也不据此新增分档。",
        "",
        f"范围跨度最大的五个观察例（按当前数据自动选取）：{sensitivity_examples}。"
        "单因素范围用于区分影响来源，各跨度不能相加；不能据此断言所有人的名次都大幅浮动。",
        "",
        "</details>",
        "",
    ])

    lines.extend(
        [
            "",
            "## 暂不入榜：待第二项正式结算",
            "",
            "以下对象已经通过正式评价池准入，但共同项不完整；不得把缺失第二项按零分处理。",
            "",
            "| 人物 | 政权 | 状态 |",
            "|---|---|---|",
        ]
    )
    for row in payload["pending_second_item_records"]:
        lines.append(
            f"| {row['ruler_name']} | {row['polity']} | `PENDING_SECOND_ITEM` |"
        )
    lines.extend(["", "## 暂不入榜：待第三项正式结算", "",
                  "以下对象的第三项实际权力窗口/归责或C父周期语义尚未闭合，不把旧分或未知按可排名正式分处理。", "",
                  "| 人物 | 政权 | 状态 |", "|---|---|---|"])
    for row in payload["pending_third_item_records"]:
        lines.append(f"| {row['ruler_name']} | {row['polity']} | `PENDING_THIRD_ITEM` |")
    lines.extend(["", "## 暂不入榜：第四项证据缺口", "",
                  "| 人物 | 政权 | 状态 |", "|---|---|---|"])
    for row in payload["pending_fourth_item_records"]:
        lines.append(f"| {row['ruler_name']} | {row['polity']} | `UNRESOLVED_EVIDENCE_GAP` |")
    lines.extend(
        [
            "",
            "## 分项入口与再现",
            "",
            "- [第一项：政权奠基与统一贡献及能力](第一项政权奠基与统一贡献及能力/01-第一项政权奠基与统一贡献及能力正式结算.md)",
            "- [第二项：治国净收益](第二项治国净收益/01-第二项治国净收益正式结算.md)",
            "- [第三项：军事与边疆净收益](第三项军事与边疆净收益/02-第三项正式结算.md)",
            "- [第四项：文明与国家整合收益](第四项文明与国家整合收益/02-第四项文明与国家整合收益正式总榜.md)",
            "",
            "同值数据入口为[`00-统治绩效综合评分榜.json`](00-统治绩效综合评分榜.json)。"
            "本表由前四项正式结果与规范评价池确定性生成；运行"
            "`codex-win run -- python v4.py composite-ranking --write`可重建JSON和Markdown。",
            "",
        ]
    )
    return "\n".join(lines)


def write_composite_ranking(workspace_root: Path) -> dict[str, Path]:
    from emperor_v4.evaluation.third_item_current_settlement import (
        verify_current_third_item_settlement,
        _write_text_atomic,
    )

    verify_current_third_item_settlement(workspace_root)
    payload = build_composite_ranking(workspace_root)
    json_path = workspace_root / OUTPUT_JSON
    markdown_path = workspace_root / OUTPUT_MARKDOWN
    _write_text_atomic(json_path,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )
    _write_text_atomic(markdown_path,
        render_composite_ranking_markdown(payload)
    )
    return {"json": json_path, "markdown": markdown_path}


def verify_composite_ranking(workspace_root: Path) -> dict[str, Any]:
    expected = build_composite_ranking(workspace_root)
    json_path = workspace_root / OUTPUT_JSON
    markdown_path = workspace_root / OUTPUT_MARKDOWN
    actual = _read_json(json_path)
    if actual != expected:
        raise ValueError("综合总榜JSON与当前正式分项重建结果不一致")
    expected_markdown = render_composite_ranking_markdown(expected)
    if markdown_path.read_text(encoding="utf-8") != expected_markdown:
        raise ValueError("综合总榜Markdown与机器结果不一致")
    return {
        "path": OUTPUT_JSON,
        "record_count": expected["record_count"],
        "pending_second_item_count": expected["pending_second_item_count"],
        "pending_third_item_count": expected["pending_third_item_count"],
        "pending_fourth_item_count": expected["pending_fourth_item_count"],
        "min_score": expected["min_score"],
        "max_score": expected["max_score"],
    }
