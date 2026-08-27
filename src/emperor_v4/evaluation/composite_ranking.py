from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import mean, median
from typing import Any, Mapping


POOL_PATH = "config/common/canonical-ruler-pool.json"
OUTPUT_JSON = "docs/评分结算/00-皇帝综合评价总榜.json"
OUTPUT_MARKDOWN = "docs/评分结算/00-皇帝综合评价总榜.md"

SETTLEMENT_SPECS = {
    "first_item": (
        "docs/评分结算/第一项创业与政权取得能力/01-第一项创业与政权取得能力正式结算.json",
        "first_item_score_points",
    ),
    "second_item": (
        "docs/评分结算/第二项治国净收益/01-第二项治国净收益405分正式结算.json",
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
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _records_hash(records: list[dict[str, Any]]) -> str:
    serialized = json.dumps(
        records, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


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
            0.10 * 775 * (scores["first_item"] / 240) ** 1.25
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
        "formula": "T = S2 + S3 + S5 + 0.10 * 775 * (S1 / 240) ^ 1.25 + CIV4",
        "first_item_not_applicable_policy": "F=0; not treated as a zero-score failure",
        "rank_tie_policy": "competition_rank_then_ruler_id",
        "score_precision": "source scores retained; F and T rounded to 2 decimals",
        "record_count": len(records),
        "pending_second_item_count": len(pending),
        "mean_score": round(mean(scores), 2),
        "median_score": round(median(scores), 2),
        "min_score": min(scores),
        "max_score": max(scores),
        "source_sha256": {
            POOL_PATH: _sha256(pool_path),
            **{
                SETTLEMENT_SPECS[item][0]: _sha256(path)
                for item, path in settlement_paths.items()
            },
        },
        "records_sha256": _records_hash(records),
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
        "`F = 0.10 × 775 × (第一项原分 / 240)^1.25`。第一项不适用者是`F=0`，"
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
            "李世民以829.81分居首，领先第二名玄烨227.79分。这个断层不是单个附加项造成的："
            "李世民同时拥有第二项359.4、第三项231.69、第五项112.6和第四项+58.5，"
            "第一项又折算67.62分，是当前唯一接近全维度高位的对象。第二至第二十名则明显"
            "形成密集区，更多依靠多项中高分而非单项极值。"
        ),
        "",
        "### 2. 头部黑马如何形成",
        "",
        (
            "完颜雍、萧绰、赵恒、耶律隆绪等人的高位主要属于“无明显短板”型：第二项较高，"
            "第三、五项继续提供稳定分值。耶律阿保机则是“多入口叠加”型，第一项、第三项和"
            "第四项同时有显著贡献。黑马本身不构成错误；真正需要复核的是各分项是否在小国"
            "治理难度、军事授权归责、未量化结果门槛和跨项重复计分上系统性偏宽。"
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
        "### 4. 当前榜单的系统性敏感点",
        "",
        "- 第二项尚未显式计入治理大国与小国的复杂度差异，小型政权的中高治理分可能与大一统帝国等价计价。",
        "",
        "- 第三项C轴部分高分对象仍存在结果量化状态与得分脱节的审计问题，共同或接续成果的归责也可能偏宽。",
        "",
        "- 第四项部分加减分包的直接史源、待裁决字段与跨项去重仍需收口；耶律阿保机的相关正向包尤其敏感。",
        "",
        "- 第五项B4对结果、团队执行和统治者本人授权的区分仍可能偏松，会抬高一部分军事型人物。",
        "",
        "这些是正式分项快照的后续整改事项，不在生成总榜时偷偷改分。因而本榜是“当前正式"
        "数据的唯一合成结果”，不是对上述敏感点已经消除的声明。",
        "",
        "### 5. 权重结论",
        "",
        "此前敏感性比较表明：单独大幅提高第二项A、第一项或第三项，分别只能抬升不同类型的"
        "雄主，同时会成批抬升本来就在相同长板上占优的人物；通用长板奖励也主要奖励现有单项"
        "领跑者。为了让少数名望人物进入前十而倒推权重，会把综合榜改造成制度榜、创业榜或"
        "军事榜。因此当前先保持权重和第一项准入边界，待上述系统性问题整改并全池重算后，"
        "再讨论幅度有限、可由规则原则解释的权重调整。",
        "",
        "## 完整总榜",
        "",
        "| 排名 | 人物 | 政权 | 第一项原分/240 | 第一项折算F | 第二项/405 | 第三项/250 | 第四项调整 | 第五项/120 | 综合分 |",
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
