from __future__ import annotations

from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping


AXIS_RAW_MAX_POINTS = {"A": 100.0, "B": 60.0, "C": 80.0}
AXIS_FORMAL_WEIGHTS = {"A": 130.0, "B": 40.0, "C": 70.0}


def _weighted_axis_points(axis: str, raw_points: float) -> float:
    weighted = (
        Decimal(str(raw_points))
        * Decimal(str(AXIS_FORMAL_WEIGHTS[axis]))
        / Decimal(str(AXIS_RAW_MAX_POINTS[axis]))
    )
    return float(weighted.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _sum_weighted_axis_points(*values: float) -> float:
    total = sum((Decimal(str(value)) for value in values), start=Decimal("0"))
    return float(total.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return round(ordered[midpoint], 1)
    return round((ordered[midpoint - 1] + ordered[midpoint]) / 2, 1)


def build_first_item_formal_settlement(
    *,
    a_payload: Mapping[str, Any],
    b_payload: Mapping[str, Any],
    c_payload: Mapping[str, Any],
) -> dict[str, Any]:
    by_b = {str(row["ruler_id"]): row for row in b_payload.get("records") or ()}
    by_c = {str(row["ruler_id"]): row for row in c_payload.get("records") or ()}
    a_records = list(a_payload.get("records") or ())
    a_ids = {str(row["ruler_id"]) for row in a_records}
    if a_ids != set(by_b) or a_ids != set(by_c):
        raise ValueError("第一项A/B/C名册ruler_id集合不一致")

    records: list[dict[str, Any]] = []
    for a_row in a_records:
        ruler_id = str(a_row["ruler_id"])
        b_row = by_b[ruler_id]
        c_row = by_c[ruler_id]
        applicable = bool(a_row["score_applicable"])
        if applicable != bool(b_row["score_applicable"]) or applicable != bool(c_row["score_applicable"]):
            raise ValueError(f"第一项A/B/C适用状态不一致: {a_row['ruler_name']}")
        a_limitations = [
            f"A：{text}" for text in a_row.get("limitations") or ()
        ]
        b_limitations = [
            f"B：{text}" for text in b_row.get("limitations") or ()
        ]
        c_limitations = [
            f"C：{text}" for text in (
                list(c_row.get("unresolved_gaps") or ())
                or (
                    [str(c_row["default_basis"])]
                    if c_row.get("default_applied") and c_row.get("default_basis")
                    else []
                )
            )
        ]
        record: dict[str, Any] = {
            "ruler_id": ruler_id,
            "ruler_name": str(a_row["ruler_name"]),
            "polity": a_row.get("polity"),
            "reign_range": a_row.get("reign_range"),
            "scope_status": "ELIGIBLE_FOUNDER" if applicable else a_row["scope_status"],
            "score_applicable": applicable,
            "A_score_points": None,
            "B_score_points": None,
            "C_score_points": None,
            "A_weighted_points": None,
            "B_weighted_points": None,
            "C_weighted_points": None,
            "first_item_score_points": None,
            "canonical_rank": None,
            "coverage_status": c_row.get("coverage_status"),
            "evidence_lower_bound": bool(
                a_row.get("evidence_lower_bound")
                or b_limitations
                or c_row.get("default_applied")
                or c_limitations
            ),
            "limitations": a_limitations + b_limitations + c_limitations,
        }
        if applicable:
            a_points = float(a_row["A_score_points"])
            b_points = float(b_row["B_score_points"])
            c_points = float(c_row["C_score_points"])
            a_weighted = _weighted_axis_points("A", a_points)
            b_weighted = _weighted_axis_points("B", b_points)
            c_weighted = _weighted_axis_points("C", c_points)
            record.update(
                A1_points=float(a_row["A1"]["points"]),
                A2_points=float(a_row["A2"]["points"]),
                A_score_points=a_points,
                B1_points=float(b_row["B1"]["points"]),
                B2_points=float(b_row["B2"]["points"]),
                B_score_points=b_points,
                C1_points=float(c_row["C1"]["points"]),
                C2_points=float(c_row["C2"]["points"]),
                C_score_points=c_points,
                A_weighted_points=a_weighted,
                B_weighted_points=b_weighted,
                C_weighted_points=c_weighted,
                first_item_score_points=_sum_weighted_axis_points(
                    a_weighted, b_weighted, c_weighted
                ),
            )
        records.append(record)

    eligible = sorted(
        (row for row in records if row["score_applicable"]),
        key=lambda row: (-float(row["first_item_score_points"]), str(row["ruler_name"])),
    )
    previous_score: float | None = None
    current_rank = 0
    for position, row in enumerate(eligible, start=1):
        score = float(row["first_item_score_points"])
        if score != previous_score:
            current_rank = position
            previous_score = score
        row["canonical_rank"] = current_rank
    excluded = sorted(
        (row for row in records if not row["score_applicable"]),
        key=lambda row: str(row["ruler_name"]),
    )
    scores = [float(row["first_item_score_points"]) for row in eligible]
    bands = {
        "180_and_above": sum(score >= 180 for score in scores),
        "144_to_179_9": sum(144 <= score < 180 for score in scores),
        "108_to_143_9": sum(108 <= score < 144 for score in scores),
        "72_to_107_9": sum(72 <= score < 108 for score in scores),
        "below_72": sum(score < 72 for score in scores),
    }
    return {
        "schema_version": "first-item-formal-settlement-v3",
        "canonical_status": "CURRENT",
        "item": "第一项政权奠基与统一贡献及能力",
        "max_points": 240,
        "axis_weighting": {
            "raw_max_points": AXIS_RAW_MAX_POINTS,
            "formal_weights": AXIS_FORMAL_WEIGHTS,
            "formula": "S1 = round1(1.30 * A_raw) + round1((2/3) * B_raw) + round1(0.875 * C_raw)",
            "basis": "A作为战略与客观兑现主轴；B因成果切分、团队归责和组织等级的量化程度最低而取最低权重；C保留本人军事成果，但不让前线指挥压过总体创业战略。",
        },
        "scope": "秦至清全阶段总名册；仅统一或独立建国主链实际贡献者适用",
        "component_max_points": {"A": 100, "B": 60, "C": 80, "C1": 50, "C2": 30},
        "composite_integration": {
            "role": "CONDITIONAL_FOUNDER_ADD_ON",
            "common_score_scope": "items_2_3",
            "common_positive_denominator": 637,
            "raw_rate_formula": "r = first_item_score_points / 240",
            "add_on_formula": "F = 0.15 * M * r^1.25",
            "composite_formula": "T = S_common + F + CIV4",
            "non_founder_policy": "NOT_APPLICABLE; F = 0; do not convert to a zero-score denominator item",
        },
        "source_refs": {
            "A": "战略决策能力/01-第一项A战略决策能力结算.json",
            "B": "政治整合能力/01-第一项B政治整合能力结算.json",
            "C": "军事夺取能力/01-第一项C军事夺取能力结算.json",
        },
        "source_schema_versions": {
            "A": a_payload.get("schema_version"),
            "B": b_payload.get("schema_version"),
            "C": c_payload.get("schema_version"),
        },
        "record_count": len(records),
        "eligible_count": len(eligible),
        "excluded_count": len(excluded),
        "unresolved_count": 0,
        "evidence_lower_bound_count": sum(bool(row["evidence_lower_bound"]) for row in eligible),
        "score_range": {"minimum": min(scores), "maximum": max(scores)},
        "score_average": round(sum(scores) / len(scores), 1),
        "score_median": _median(scores),
        "score_band_counts": bands,
        "formal_database_write": False,
        "cross_item_ranking_write": False,
        "records": eligible + excluded,
    }


def render_first_item_formal_settlement_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# 第一项政权奠基与统一贡献及能力正式结算",
        "",
        "> 第一项不直接加入共同分母，而按评分总则的条件附加公式进入综合分。",
        "",
        f"- 总名册：{payload['record_count']}人",
        f"- 适用统一或建国主链贡献者：{payload['eligible_count']}人",
        f"- 非奠基者不适用：{payload['excluded_count']}人",
        f"- 证据下限：{payload['evidence_lower_bound_count']}人",
        f"- 得分范围：{payload['score_range']['minimum']:.1f}—{payload['score_range']['maximum']:.1f}；平均{payload['score_average']:.1f}；中位数{payload['score_median']:.1f}",
        "",
        "正式总分按A130、B40、C70聚合；分项原始值继续保留原量尺，便于核对各自合同。",
        "",
        "| 第一项序 | 对象 | 政权 | A原始/100→计入/130 | B原始/60→计入/40 | C原始/80→计入/70 | 第一项/240 |",
        "|---:|---|---|---:|---:|---:|---:|",
    ]
    for row in payload.get("records") or ():
        if not row["score_applicable"]:
            continue
        lines.append(
            f"| {row['canonical_rank']} | {row['ruler_name']} | {row.get('polity') or '—'} | "
            f"{row['A_score_points']:.1f}→{row['A_weighted_points']:.1f} | "
            f"{row['B_score_points']:.1f}→{row['B_weighted_points']:.1f} | "
            f"{row['C_score_points']:.1f}→{row['C_weighted_points']:.1f} | "
            f"{row['first_item_score_points']:.1f} |"
        )
    lower_bounds = [row for row in payload.get("records") or () if row.get("score_applicable") and row.get("evidence_lower_bound")]
    lines.extend(["", "## 证据下限", ""])
    if lower_bounds:
        for row in lower_bounds:
            detail = "；".join(row["limitations"]) or "C项按合同使用保守默认值"
            lines.append(f"- {row['ruler_name']}：{detail.rstrip('。.')}。")
    else:
        lines.append("- 无。")
    excluded = [row["ruler_name"] for row in payload.get("records") or () if not row["score_applicable"]]
    lines.extend(
        [
            "",
            "## 非奠基者不适用",
            "",
            "、".join(excluded) + "。",
            "",
            "## 分项入口",
            "",
            "- [A创业战略能力](战略决策能力/01-第一项A战略决策能力结算.md)",
            "- [B政治整合能力](政治整合能力/01-第一项B政治整合能力结算.md)",
            "- [C军事夺取能力](军事夺取能力/01-第一项C军事夺取能力结算.md)",
            "",
        ]
    )
    return "\n".join(lines)


def render_first_item_summary(
    *,
    formal_payload: Mapping[str, Any],
    a_payload: Mapping[str, Any],
    b_payload: Mapping[str, Any],
    c_payload: Mapping[str, Any],
) -> str:
    eligible = [row for row in formal_payload.get("records") or () if row["score_applicable"]]
    lower_bounds = [row["ruler_name"] for row in eligible if row["evidence_lower_bound"]]
    c_defaults = [
        str(row["ruler_name"])
        for row in c_payload.get("records") or ()
        if row.get("score_applicable") and row.get("default_applied")
    ]
    top_a = sorted(eligible, key=lambda row: (-row["A_score_points"], row["ruler_name"]))[:8]
    top_b = sorted(eligible, key=lambda row: (-row["B_score_points"], row["ruler_name"]))[:8]
    top_c = sorted(eligible, key=lambda row: (-row["C_score_points"], row["ruler_name"]))[:8]
    by_name = {row["ruler_name"]: row for row in eligible}
    bands = formal_payload["score_band_counts"]

    def names(rows: list[Mapping[str, Any]], field: str) -> str:
        return "、".join(f"{row['ruler_name']}（{row[field]:.1f}）" for row in rows)

    lines = [
        "# 第一项政权奠基与统一贡献及能力结算总结分析",
        "",
        "## 一、结算结论",
        "",
        f"第一项已经完成秦至清全阶段结算：总名册{formal_payload['record_count']}人，其中{formal_payload['eligible_count']}名统一或独立建国主链实际贡献者进入240分正式聚合，{formal_payload['excluded_count']}名普通继承者或非奠基者不适用。完整数值见[第一项正式结算](01-第一项政权奠基与统一贡献及能力正式结算.md)。A、B、C保留100/60/80原始量尺，分别折算为130/40/70计入；第一项总分不直接加入共同分母，综合榜按`F = 0.15 × M × (第一项总分/240)^1.25`计算奠基人条件附加分。",
        "",
        f"当前前三为{eligible[0]['ruler_name']}（{eligible[0]['first_item_score_points']:.1f}）、{eligible[1]['ruler_name']}（{eligible[1]['first_item_score_points']:.1f}）、{eligible[2]['ruler_name']}（{eligible[2]['first_item_score_points']:.1f}）。最高分{formal_payload['score_range']['maximum']:.1f}，中位数{formal_payload['score_median']:.1f}；第一项没有基础分，低分表示在严格贡献窗口和人物归责下可兑现成果较少，不是对其完整在位表现的总评价。",
        "",
        "## 二、模型结构与去重",
        "",
        "- A保留100分原始量尺，正式计入130分，评价创业路线、起点与对手难度、项目完成、控制量、速度、耐久以及重大正负决策。净控制量只进入A2，A1不重复读取。",
        "- B保留60分原始量尺，正式计入40分，评价非本人团队闭合的两个最强不重叠成果群，以及团队并行执行、连续替补和异质整合。B的成果切分、团队责任与组织等级量化程度最低，因此不承担主轴权重。",
        "- C保留80分原始量尺，正式计入70分，评价本人在创业战争中的实际成果和前线指挥能力。授权、名义统帅和他人独立战果不进入C。",
        "- 同一战役结果按人物实际责任分别进入B或C；C按同一父级战役与同一结果方向只消费一次，但保留分别有证据的正负结果；A只读取战略和项目结果，不再把战役档位或人物名望复制成分数。",
        "",
        "## 三、总分分布",
        "",
        f"- 180分及以上：{bands['180_and_above']}人；144—179.9分：{bands['144_to_179_9']}人；108—143.9分：{bands['108_to_143_9']}人；72—107.9分：{bands['72_to_107_9']}人；72分以下：{bands['below_72']}人。",
        f"- 平均分{formal_payload['score_average']:.1f}，中位数{formal_payload['score_median']:.1f}。高分段数量有限，说明A、B、C三项同时兑现仍有明显门槛。",
        "",
        "### 前十五名",
        "",
        "| 序 | 对象 | 政权 | A计入/130 | B计入/40 | C计入/70 | 总分 | 主要结构 |",
        "|---:|---|---|---:|---:|---:|---:|---|",
    ]
    for row in eligible[:15]:
        rates = {"战略": row["A_score_points"] / 100, "团队": row["B_score_points"] / 60, "军事": row["C_score_points"] / 80}
        strongest = max(rates, key=rates.get)
        weakest = min(rates, key=rates.get)
        structure = "三轴均衡" if max(rates.values()) - min(rates.values()) <= 0.15 else f"{strongest}突出、{weakest}相对较弱"
        lines.append(
            f"| {row['canonical_rank']} | {row['ruler_name']} | {row.get('polity') or '—'} | {row['A_weighted_points']:.1f} | {row['B_weighted_points']:.1f} | {row['C_weighted_points']:.1f} | {row['first_item_score_points']:.1f} | {structure} |"
        )
    lines.extend(
        [
            "",
            "## 四、三个维度分别在奖励什么",
            "",
            f"- A领先者：{names(top_a, 'A_score_points')}。这一组主要由高难度起点、强对手压力、较高完成度与战略净决策共同拉开。",
            f"- B领先者：{names(top_b, 'B_score_points')}。B高表示创业团队确有两个高质量独立成果且组织化程度高，不表示奠基人本人能力相同。",
            f"- C领先者：{names(top_c, 'C_score_points')}。这一组依赖本人可归责的创业战役成果与前线解题能力，不消费单纯授权。",
            "",
            "## 五、容易误读的名次",
            "",
            f"- 李世民以{by_name['李世民']['first_item_score_points']:.1f}列第{by_name['李世民']['canonical_rank']}，A原始值{by_name['李世民']['A_score_points']:.1f}与C原始值{by_name['李世民']['C_score_points']:.1f}同时顶尖；B原始值{by_name['李世民']['B_score_points']:.1f}较低，正是本人亲自承担大量主战结果后的归责边界。",
            f"- 朱元璋以{by_name['朱元璋']['first_item_score_points']:.1f}列第{by_name['朱元璋']['canonical_rank']}，A原始值{by_name['朱元璋']['A_score_points']:.1f}、B原始值{by_name['朱元璋']['B_score_points']:.1f}、C原始值{by_name['朱元璋']['C_score_points']:.1f}均处高位。",
            f"- 刘邦为A={by_name['刘邦']['A_score_points']:.1f}、B={by_name['刘邦']['B_score_points']:.1f}、C={by_name['刘邦']['C_score_points']:.1f}：战略和团队组织极强，本人前线军事并未被韩信等人的战果抬高。",
            f"- 嬴政与杨坚的B均为{by_name['嬴政']['B_score_points']:.1f}，但C为0。这不是认定二人没有军事能力，而是当前公共战役登记没有满足本人前线或一体化指挥门槛的可消费结果；团队完成统一战争仍可独立进入B。",
            f"- 多尔衮总分{by_name['多尔衮']['first_item_score_points']:.1f}，不能据此反推其是清朝全部创业贡献最大者。努尔哈赤主要创建军政机器，皇太极完成复合国家转型，多尔衮兑现入关后的大规模土地控制，三人的贡献窗口不能跨代回拨。",
            "- B高分段并不等同于历史声望排序。它只回答非本人团队实际完成了什么，以及团队是否形成可并行、可续接的组织；个人战略、亲征与制度建设分别由其他分项承担。",
            "",
            "## 六、证据边界与后续变化条件",
            "",
            f"- A未决0人，B计分成果缺锚0项；C有{len(c_defaults)}人因创业军事证据缺口采用保守值：{'、'.join(c_defaults) if c_defaults else '无'}。后续只有补成可归责的创业战役结果，才允许据此重算。",
            f"- 正式总表另有{len(lower_bounds)}人标记为证据下限。这是A、B、C任一环节仍保留证据限制的合并口径，不等同于C项保守默认人数。",
            "- 109名非奠基者属于第一项不适用，不是第一项零分；其综合评价不得把空值当作0分并入共同分母。",
            "- 后续若战役登记、人物归责或统一窗口发生实质变化，应先重建对应分项，再更新正式结算与本分析；不得仅在总结中手改分数。",
            "",
            "## 七、分项文档",
            "",
            "- [第一项正式结算](01-第一项政权奠基与统一贡献及能力正式结算.md)",
            "- [A创业战略能力](战略决策能力/01-第一项A战略决策能力结算.md)",
            "- [B政治整合能力](政治整合能力/01-第一项B政治整合能力结算.md)",
            "- [C军事夺取能力](军事夺取能力/01-第一项C军事夺取能力结算.md)",
            "",
        ]
    )
    return "\n".join(lines)
