from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, median
from typing import Any, Mapping

from emperor_v4.evaluation.formal_json_store import load_json


POOL_PATH = "config/common/canonical-ruler-pool.json"
OUTPUT_JSON = "docs/评分结算/00-皇帝综合评价总榜.json"
OUTPUT_MARKDOWN = "docs/评分结算/00-皇帝综合评价总榜.md"

SETTLEMENT_SPECS = {
    "first_item": (
        "docs/评分结算/第一项创业与政权取得能力/01-第一项创业与政权取得能力正式结算.json",
        "first_item_score_points",
    ),
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
    "fifth_item": (
        "docs/评分结算/第五项统治者政治素质/04-第五项统治者政治素质正式结算.json",
        "fifth_item_score_points",
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

    records: list[dict[str, Any]] = []
    for pool_row in ready:
        source_ids = pool_row["source_item_ids"]
        first_source_id = source_ids.get("first_item")
        first_value = (
            indexed["first_item"][first_source_id].get("first_item_score_points")
            if first_source_id and first_source_id in indexed["first_item"]
            else None
        )
        first_applicable = first_value is not None
        first_score = float(first_value) if first_applicable else 0.0
        scores: dict[str, float] = {"first_item": first_score}
        for item, (_, score_field) in SETTLEMENT_SPECS.items():
            if item == "first_item":
                continue
            source_id = source_ids.get(item)
            if not source_id or source_id not in indexed[item]:
                raise ValueError(f"{pool_row['ruler_name']}缺少{item}正式记录")
            value = indexed[item][source_id].get(score_field)
            if value is None:
                raise ValueError(f"{pool_row['ruler_name']}的{item}正式分为空")
            scores[item] = float(value)

        first_add_on = (
            0.10 * 757 * (scores["first_item"] / 240) ** 1.25
            if scores["first_item"] > 0
            else 0.0
        )
        common_score = scores["second_item"] + scores["third_item"] + scores["fifth_item"]
        total_score = common_score + first_add_on + scores["fourth_item"]
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
                "fifth_item_score": round(scores["fifth_item"], 2),
                "common_score": round(common_score, 2),
                "total_score": round(total_score, 2),
            }
        )

    records.sort(key=lambda row: (-row["total_score"], row["ruler_id"]))
    scores = [float(row["total_score"]) for row in records]
    for index, row in enumerate(records):
        row["rank"] = _competition_rank(scores, index)

    pending.sort(key=lambda row: row["ruler_id"])
    return {
        "schema_id": "emperor-v4-composite-ranking-v1",
        "status": "FORMAL_CURRENT",
        "ranking_population": "COMPOSITE_READY",
        "formula": "T = S2 + S3 + S5 + 0.10 * 757 * (S1 / 240) ^ 1.25 + CIV4",
        "first_item_not_applicable_policy": "F=0; not treated as a zero-score failure",
        "rank_tie_policy": "competition_rank_then_ruler_id",
        "score_precision": "source scores retained; F and T rounded to 2 decimals",
        "record_count": len(records),
        "pending_second_item_count": len(pending),
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

    def summary(name: str) -> str:
        row = by_name[name]
        return (
            f"{name}第{row['rank']}（{row['total_score']:.2f}；"
            f"一项折算{row['first_item_add_on']:.2f}、二项{row['second_item_score']:.1f}、"
            f"三项{row['third_item_score']:.2f}、四项{row['fourth_item_adjustment']:+.1f}、"
            f"五项{row['fifth_item_score']:.2f}）"
        )

    leader = records[0]
    runner_up = records[1]
    lead = float(leader["total_score"]) - float(runner_up["total_score"])

    lines = [
        "# 皇帝综合评价总榜",
        "",
        (
            f"> 本榜只覆盖正式评价池中`COMPOSITE_READY`的{payload['record_count']}人；"
            f"另有{payload['pending_second_item_count']}人因第二项尚未正式结算而不入榜。"
            "排名是现行规则与现有正式分项快照的确定性合成，不以历史名望反推分数。"
        ),
        "",
        "## 口径",
        "",
        "综合分公式：`T = 第二项 + 第三项 + 第五项 + F + 第四项调整`，其中"
        "`F = 0.10 × 757 × (第一项原分 / 240)^1.25`。第一项不适用者是`F=0`，"
        "不是把“不适用”判成第一项零分。总分保留两位小数，采用竞争排名；同分记录按"
        "规范`ruler_id`稳定排序。",
        "",
        (
            f"当前均分{payload['mean_score']:.2f}，中位数{payload['median_score']:.2f}，"
            f"范围{payload['min_score']:.2f}—{payload['max_score']:.2f}。"
        ),
        "",
        "## 排名分析",
        "",
        "### 1. 榜首与头部结构",
        "",
        (
            f"{leader['ruler_name']}以{leader['total_score']:.2f}分居首，领先第二名"
            f"{runner_up['ruler_name']}{lead:.2f}分。其构成为：第一项折算"
            f"{leader['first_item_add_on']:.2f}、第二项{leader['second_item_score']:.1f}、"
            f"第三项{leader['third_item_score']:.2f}、第四项{leader['fourth_item_adjustment']:+.1f}、"
            f"第五项{leader['fifth_item_score']:.2f}。头部差距来自五项正式快照的共同合成，"
            "不是生成总榜时追加的主观修正。"
        ),
        "",
        "### 2. 排名解释",
        "",
        (
            "综合名次由第二、第三、第五项共同分、第一项条件附加分和第四项有符号调整共同决定。"
            "因此单一项目的高分不会自动转化为总榜高位；不同对象可以通过多项稳定、创业附加或"
            "文明调整形成不同的得分结构。"
        ),
        "",
        "### 3. 名望较高但总榜偏低的人物",
        "",
        (
            f"现行结果中，{summary('嬴政')}；{summary('刘彻')}；{summary('朱元璋')}；"
            f"{summary('刘邦')}；{summary('刘裕')}；{summary('拓跋焘')}。这些人的长板分散在"
            "第一项、第二项A制度建设或第三项，综合公式却以第二、三、五项共同净收益为主体，"
            "因此不会自动把统一、扩张或制度名望等同于总榜高位。"
        ),
        "",
        "朱棣与李渊属于另一类：朱棣的靖难主要表现军事能力，但不满足第一项政权奠基准入，"
        "且内战损害仍进入治国净收益；李渊在位与独立发挥窗口较短，创业成果又必须与李世民"
        "按阶段归责。扩大第一项到一般篡位或内战既不能稳定解决其排名，也会破坏“文明进步与"
        "政权奠基”边界，因此本榜不作此调整。",
        "",
        "### 4. 权重与边界",
        "",
        "本次只消费更新后的正式分项快照，没有改变综合公式、第一项准入边界或各项权重。"
        "如需调整权重，应另做全池敏感性检验，不能为少数对象的预期名次反向设计。",
        "",
        "## 完整总榜",
        "",
        "| 排名 | 人物 | 政权 | 第一项原分/240 | 第一项折算F | 第二项/387 | 第三项/250 | 第四项调整 | 第五项/120 | 综合分 |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in records:
        first_raw = (
            f"{row['first_item_raw_score']:.1f}"
            if row["first_item_status"] == "APPLICABLE"
            else "—"
        )
        lines.append(
            f"| {row['rank']} | {row['ruler_name']} | {row['polity']} | "
            f"{first_raw} | {row['first_item_add_on']:.2f} | "
            f"{row['second_item_score']:.1f} | {row['third_item_score']:.2f} | "
            f"{row['fourth_item_adjustment']:+.1f} | {row['fifth_item_score']:.2f} | "
            f"**{row['total_score']:.2f}** |"
        )

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
    lines.extend(
        [
            "",
            "## 数据来源与再现",
            "",
            "同值数据入口为[`00-皇帝综合评价总榜.json`](00-皇帝综合评价总榜.json)。"
            "本表由五项正式结算与规范评价池确定性生成；运行"
            "`codex-win run -- python v4.py composite-ranking --write`可重建JSON和Markdown。",
            "",
        ]
    )
    return "\n".join(lines)


def write_composite_ranking(workspace_root: Path) -> dict[str, Path]:
    payload = build_composite_ranking(workspace_root)
    json_path = workspace_root / OUTPUT_JSON
    markdown_path = workspace_root / OUTPUT_MARKDOWN
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(
        render_composite_ranking_markdown(payload), encoding="utf-8"
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
        "min_score": expected["min_score"],
        "max_score": expected["max_score"],
    }
