from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, median
from typing import Any, Mapping

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.composite_details import (
    component_details, load_detail_sources,
)
from emperor_v4.evaluation.first_item_markdown_settlement import (
    load_first_item_markdown_settlement,
)


POOL_PATH = "config/common/canonical-ruler-pool.json"
OUTPUT_JSON = "docs/评分结算/00-皇帝功业与治理净收益榜.json"
OUTPUT_MARKDOWN = "docs/评分结算/00-皇帝功业与治理净收益榜.md"

SETTLEMENT_SPECS = {
    "second_item": (
        "docs/评分结算/第二项治国净收益/01-第二项治国净收益正式结算.json",
        "second_item_score",
    ),
    "third_item": (
        "docs/评分结算/第三项军事与边疆净收益/02-第三项正式结算.json",
        "third_item_score_points",
    ),
    "fourth_item": (
        "docs/评分结算/第四项文明与国家整合收益/01-第四项文明与国家整合收益正式结算.json",
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
        for founder in (0.12, 0.15, 0.18):
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

    baseline = "g+0.0_f0.15_c1.0"
    for row in records:
        ruler_id = row["ruler_id"]
        if scenario_ranks[baseline][ruler_id] != row["rank"]:
            raise ValueError("权重情景基准与正式名次不一致")
        row["weight_sensitivity"] = {
            "all_scenarios": extent(ruler_id, scenarios),
            "add_ons_only": extent(ruler_id, [s for s in scenarios if s["common_tilt"] == 0]),
            "first_item_only": extent(ruler_id, [s for s in scenarios if s["common_tilt"] == 0 and s["fourth_item_multiplier"] == 1]),
            "fourth_item_only": extent(ruler_id, [s for s in scenarios if s["common_tilt"] == 0 and s["first_item_coefficient"] == 0.15]),
            "common_items_only": extent(ruler_id, [s for s in scenarios if s["first_item_coefficient"] == 0.15 and s["fourth_item_multiplier"] == 1]),
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
    first_item_scores = {
        row["name"]: row["total"]
        for row in load_first_item_markdown_settlement(workspace_root)
    }
    detail_sources = load_detail_sources(workspace_root)

    ready = [
        row
        for row in pool["records"]
        if row["settlement_readiness"] == "COMPOSITE_READY"
    ]
    pending = [
        {
            "ruler_id": row["ruler_id"],
            "ruler_name": row["ruler_name"],
            "polity": row["polity"],
            "settlement_readiness": row["settlement_readiness"],
            "not_ranked_reason": "PENDING_SECOND_ITEM_FORMAL_SETTLEMENT",
        }
        for row in pool["records"]
        if row["pool_status"] == "INCLUDED"
        and row["settlement_readiness"] != "COMPOSITE_READY"
    ]
    if len(ready) != pool["composite_ready_count"]:
        raise ValueError("综合就绪人数与正式池声明不一致")
    if len(pending) != pool["pending_second_item_count"]:
        raise ValueError("待第二项结算人数与正式池声明不一致")

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
        first_value = first_item_scores.get(pool_row["ruler_name"])
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
            0.15 * 637 * (scores["first_item"] / 240) ** 1.25
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
        "formula": "T = S2 + S3 + 0.15 * 637 * (S1 / 240) ^ 1.25 + CIV4",
        "first_item_not_applicable_policy": "F=0; not treated as a zero-score failure",
        "rank_tie_policy": "competition_rank_then_ruler_id",
        "weight_sensitivity": sensitivity,
        "score_precision": "source scores retained; F and T rounded to 2 decimals",
        "record_count": len(records),
        "pending_second_item_count": len(pending),
        "pending_fourth_item_count": len(pending_fourth),
        "pending_fourth_item_records": sorted(pending_fourth, key=lambda row: row["ruler_id"]),
        "mean_score": round(mean(scores), 2),
        "median_score": round(median(scores), 2),
        "min_score": min(scores),
        "max_score": max(scores),
        "pending_second_item_records": pending,
        "records": records,
    }


def render_composite_ranking_markdown(payload: Mapping[str, Any]) -> str:
    records = payload["records"]
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

    lines = [
        "# 皇帝功业与治理净收益榜",
        "",
        "> 本榜由第一项条件附加分、第二项治国净收益、第三项军事与边疆净收益及第四项文明调整合成；"
        "第五项政治素质暂不计入，独立人物画像不参与。",
        "",
        (
            "> 第四项语义复核门已闭合。"
            if payload["fourth_item_semantic_review_complete"]
            else "> **第四项全池语义复核尚未完成，本榜是当前快照的条件排序，不是复核终榜。**"
            "已确认改判已同步；未解决的证据、归责与空轴排漏仍可能改变分数和名次。"
        ),
        "",
        (
            f"> 本榜只覆盖正式评价池中`COMPOSITE_READY`的{payload['record_count']}人；"
            f"另有{payload['pending_second_item_count']}人因第二项尚未正式结算而不入榜。"
            f"另有{payload['pending_fourth_item_count']}名原综合就绪对象因第四项证据缺口暂不入榜，不把未知按零分处理。"
            "排名是现行规则与现有正式分项快照的确定性合成，不以历史名望反推分数。"
        ),
        "",
        "## 口径",
        "",
        "综合分公式：`T = 第二项 + 第三项 + F + 第四项调整`，其中"
        "`F = 0.15 × 637 × (第一项净分 / 240)^1.25`。第一项不适用者是`F=0`，"
        "不是把“不适用”判成第一项零分。总分保留两位小数，采用竞争排名；同分记录按"
        "规范`ruler_id`稳定排序。",
        "",
        "总分小数表示规则计算精度，不代表史料与历史判断具有同等精度。名次为现行规则及"
        "正式裁决下的条件排序；微小分差不应直接解释为可辨识的历史优劣。表中范围是所列离散"
        "权重情景下的最好至最差名次，不是置信区间，也不是连续参数范围的严格界限。"
        "史料、归责、分项裁决及第一项指数均固定；证据与裁决不确定性尚未评估。",
        "",
        (
            f"当前均分{payload['mean_score']:.2f}，中位数{payload['median_score']:.2f}，"
            f"范围{payload['min_score']:.2f}—{payload['max_score']:.2f}。"
        ),
        "",
        "## 完整总榜",
        "",
        "仅附加项范围覆盖9种情景，全部范围覆盖27种情景。范围两端均为名次；计算方法见下方折叠说明。",
        "",
        "| 基准名次 | 人物 | 政权 | 共同项合计 | 奠基附加F | 文明调整 | 综合分 | 仅附加项范围 | 全部情景范围 |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in records:
        lines.append(
            f"| {row['rank']} | {row['ruler_name']} | {row['polity']} | "
            f"{row['common_score']:.2f} | {row['first_item_add_on']:.2f} | "
            f"{row['fourth_item_adjustment']:+.1f} | **{row['total_score']:.2f}** | "
            f"{rank_range(row, 'add_ons_only')} | {rank_range(row)} |"
        )

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
            f"现行结果中，{summary('嬴政')}；{summary('刘彻')}；{summary('朱元璋')}；"
            f"{summary('刘邦')}；{summary('刘裕')}；{summary('拓跋焘')}。这些人的长板分散在"
            "第一项、第二项A制度建设或第三项，综合公式却以第二、三项共同净收益为主体，"
            "因此不会自动把统一、扩张或制度名望等同于总榜高位。"
        ),
        "",
        "朱棣的靖难不满足第一项政权奠基准入；其第二项按1402—1424年统治窗口结算，"
        "战后清洗及持续后果与后续主动成本分别归责，不把靖难战争本身的损害混入。"
        "李渊的创业成果则须与李世民按阶段归责。具体依据见分项结算。",
        "",
        "第一项按共同正向上限的15%及指数1.25折算，附加分最多95.55分；"
        "第一项净分、准入边界及跨项成果与成本去重规则继续按正式合同执行。"
        "该系数统一体现创业贡献，不按个别人物的去重减分补回。",
        "",
        "<details>",
        "<summary>权重情景：计算方法与观察例</summary>",
        "",
        "以下是诊断设置，不修改正式权重，也不根据人物名次选择参数：",
        "",
        "- 奠基附加系数取12%、15%、18%；文明调整倍数取0.8、1、1.2，正负端同步缩放。共同项固定时形成9种附加项组合。",
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
            "同值数据入口为[`00-皇帝功业与治理净收益榜.json`](00-皇帝功业与治理净收益榜.json)。"
            "本表由前四项正式结果与规范评价池确定性生成；运行"
            "`codex-win run -- python v4.py composite-ranking --write`可重建JSON和Markdown。",
            "",
        ]
    )
    return "\n".join(lines)


def write_composite_ranking(workspace_root: Path) -> dict[str, Path]:
    from emperor_v4.evaluation.third_item_current_settlement import (
        verify_current_third_item_settlement,
    )

    verify_current_third_item_settlement(workspace_root)
    payload = build_composite_ranking(workspace_root)
    json_path = workspace_root / OUTPUT_JSON
    markdown_path = workspace_root / OUTPUT_MARKDOWN
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    markdown_path.write_text(
        render_composite_ranking_markdown(payload), encoding="utf-8", newline="\n"
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
        "pending_fourth_item_count": expected["pending_fourth_item_count"],
        "min_score": expected["min_score"],
        "max_score": expected["max_score"],
    }
