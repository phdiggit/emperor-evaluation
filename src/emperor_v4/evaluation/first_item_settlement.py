from __future__ import annotations

from collections import Counter
from typing import Any, Mapping


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
            "first_item_score_points": None,
            "canonical_rank": None,
            "coverage_status": c_row.get("coverage_status"),
            "evidence_lower_bound": bool(c_row.get("default_applied")),
            "limitations": list(c_row.get("unresolved_gaps") or ()),
        }
        if applicable:
            a_points = float(a_row["A_score_points"])
            b_points = float(b_row["B_score_points"])
            c_points = float(c_row["C_score_points"])
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
                first_item_score_points=round(a_points + b_points + c_points, 1),
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
        "200_and_above": sum(score >= 200 for score in scores),
        "160_to_199_9": sum(160 <= score < 200 for score in scores),
        "120_to_159_9": sum(120 <= score < 160 for score in scores),
        "80_to_119_9": sum(80 <= score < 120 for score in scores),
        "below_80": sum(score < 80 for score in scores),
    }
    return {
        "schema_version": "first-item-formal-settlement-v1",
        "canonical_status": "CURRENT",
        "item": "第一项创业与政权取得能力",
        "max_points": 260,
        "scope": "秦至清全阶段总名册；仅统一或独立建国主链实际贡献者适用",
        "component_max_points": {"A": 100, "B": 60, "C": 100},
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
        "# 第一项创业与政权取得能力正式结算",
        "",
        "> 本文件是第一项260分的当前正式阅读视图；同名JSON是唯一机器读取源。正式表示第一项内部A/B/C已经闭合，不表示已写入评分数据库或形成跨七大项总排名。",
        "",
        f"- 总名册：{payload['record_count']}人",
        f"- 适用统一或建国主链贡献者：{payload['eligible_count']}人",
        f"- 非奠基者不适用：{payload['excluded_count']}人",
        f"- 证据下限：{payload['evidence_lower_bound_count']}人；未决：{payload['unresolved_count']}人",
        f"- 得分范围：{payload['score_range']['minimum']:.1f}—{payload['score_range']['maximum']:.1f}；平均{payload['score_average']:.1f}；中位数{payload['score_median']:.1f}",
        "",
        "| 第一项序 | 对象 | 政权 | A1/A2→A（100） | B1/B2→B（60） | C1/C2→C（100） | 第一项/260 | 证据状态 |",
        "|---:|---|---|---:|---:|---:|---:|---|",
    ]
    for row in payload.get("records") or ():
        if not row["score_applicable"]:
            continue
        evidence = "证据下限" if row["evidence_lower_bound"] else str(row["coverage_status"])
        lines.append(
            f"| {row['canonical_rank']} | {row['ruler_name']} | {row.get('polity') or '—'} | "
            f"{row['A1_points']:.1f}/{row['A2_points']:.1f}→{row['A_score_points']:.1f} | "
            f"{row['B1_points']:.1f}/{row['B2_points']:.1f}→{row['B_score_points']:.1f} | "
            f"{row['C1_points']:.1f}/{row['C2_points']:.1f}→{row['C_score_points']:.1f} | "
            f"{row['first_item_score_points']:.1f} | {evidence} |"
        )
    lower_bounds = [row for row in payload.get("records") or () if row.get("score_applicable") and row.get("evidence_lower_bound")]
    lines.extend(["", "## 证据下限", ""])
    if lower_bounds:
        for row in lower_bounds:
            detail = "；".join(row["limitations"]) or "C项按合同使用保守默认值"
            lines.append(f"- {row['ruler_name']}：{detail}。")
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
    defaults = [row["ruler_name"] for row in eligible if row["evidence_lower_bound"]]
    top_a = sorted(eligible, key=lambda row: (-row["A_score_points"], row["ruler_name"]))[:8]
    top_b = sorted(eligible, key=lambda row: (-row["B_score_points"], row["ruler_name"]))[:8]
    top_c = sorted(eligible, key=lambda row: (-row["C_score_points"], row["ruler_name"]))[:8]
    by_name = {row["ruler_name"]: row for row in eligible}
    bands = formal_payload["score_band_counts"]

    def names(rows: list[Mapping[str, Any]], field: str) -> str:
        return "、".join(f"{row['ruler_name']}（{row[field]:.1f}）" for row in rows)

    lines = [
        "# 第一项创业与政权取得能力结算总结分析",
        "",
        "## 一、结算结论",
        "",
        f"第一项已经完成秦至清全阶段结算：总名册{formal_payload['record_count']}人，其中{formal_payload['eligible_count']}名统一或独立建国主链实际贡献者进入260分结算，{formal_payload['excluded_count']}名普通继承者或非奠基者不适用。完整数值见[第一项正式结算](01-第一项创业与政权取得能力正式结算.md)。",
        "",
        f"当前前三为{eligible[0]['ruler_name']}（{eligible[0]['first_item_score_points']:.1f}）、{eligible[1]['ruler_name']}（{eligible[1]['first_item_score_points']:.1f}）、{eligible[2]['ruler_name']}（{eligible[2]['first_item_score_points']:.1f}）。最高分{formal_payload['score_range']['maximum']:.1f}，中位数{formal_payload['score_median']:.1f}；第一项没有基础分，低分表示在严格贡献窗口和人物归责下可兑现成果较少，不是对其完整在位表现的总评价。",
        "",
        "## 二、模型结构与去重",
        "",
        "- A（100）评价创业路线、起点与对手难度、项目完成、控制量、速度、耐久以及重大正负决策。净控制量只进入A2，A1不重复读取。",
        "- B（60）评价非本人团队闭合的两个最强不重叠成果群，以及团队并行执行、连续替补和异质整合。人名数量、官位和全生涯声望不换分。",
        "- C（100）评价本人在创业战争中的实际成果和前线指挥能力。授权、名义统帅和他人独立战果不进入C。",
        "- 同一战役结果按人物实际责任分别进入B或C；A只读取战略和项目结果，不再把战役档位或人物名望复制成分数。",
        "",
        "## 三、总分分布",
        "",
        f"- 200分及以上：{bands['200_and_above']}人；160—199.9分：{bands['160_to_199_9']}人；120—159.9分：{bands['120_to_159_9']}人；80—119.9分：{bands['80_to_119_9']}人；80分以下：{bands['below_80']}人。",
        f"- 平均分{formal_payload['score_average']:.1f}，中位数{formal_payload['score_median']:.1f}。高分段数量有限，说明A、B、C三项同时兑现仍有明显门槛。",
        "",
        "### 前十五名",
        "",
        "| 序 | 对象 | 政权 | A | B | C | 总分 | 主要结构 |",
        "|---:|---|---|---:|---:|---:|---:|---|",
    ]
    for row in eligible[:15]:
        rates = {"战略": row["A_score_points"] / 100, "团队": row["B_score_points"] / 60, "军事": row["C_score_points"] / 100}
        strongest = max(rates, key=rates.get)
        weakest = min(rates, key=rates.get)
        structure = "三轴均衡" if max(rates.values()) - min(rates.values()) <= 0.15 else f"{strongest}突出、{weakest}相对较弱"
        lines.append(
            f"| {row['canonical_rank']} | {row['ruler_name']} | {row.get('polity') or '—'} | {row['A_score_points']:.1f} | {row['B_score_points']:.1f} | {row['C_score_points']:.1f} | {row['first_item_score_points']:.1f} | {structure} |"
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
            f"- 李世民以{by_name['李世民']['first_item_score_points']:.1f}居首，来源是A={by_name['李世民']['A_score_points']:.1f}与C={by_name['李世民']['C_score_points']:.1f}同时顶尖；B={by_name['李世民']['B_score_points']:.1f}较低，正是本人亲自承担大量主战结果后的边界表现。",
            f"- 刘邦为A={by_name['刘邦']['A_score_points']:.1f}、B={by_name['刘邦']['B_score_points']:.1f}、C={by_name['刘邦']['C_score_points']:.1f}：战略和团队组织极强，本人前线军事并未被韩信等人的战果抬高。",
            f"- 嬴政与杨坚的B均为{by_name['嬴政']['B_score_points']:.1f}，但C为0。这不是认定二人没有军事能力，而是当前公共战役登记没有满足本人前线或一体化指挥门槛的可消费结果；团队完成统一战争仍可独立进入B。",
            f"- 多尔衮总分{by_name['多尔衮']['first_item_score_points']:.1f}，不能据此反推其是清朝全部创业贡献最大者。努尔哈赤主要创建军政机器，皇太极完成复合国家转型，多尔衮兑现入关后的大规模土地控制，三人的贡献窗口不能跨代回拨。",
            "- B高分段并不等同于历史声望排序。它只回答非本人团队实际完成了什么，以及团队是否形成可并行、可续接的组织；个人战略、亲征与制度建设分别由其他分项承担。",
            "",
            "## 六、证据边界与后续变化条件",
            "",
            f"- A未决0人，B计分成果缺锚0项；C有{c_payload['default_count']}人按证据下限结算：{'、'.join(defaults) if defaults else '无'}。这些对象后续补成可归责创业战役时允许上调，不得用常识直接补分。",
            "- 第一项内部结算已经闭合，但仍不写正式评分数据库，也不形成跨七大项总排名。后续战役登记、人物归责或统一窗口若发生实质变化，必须先重建A/B/C，再重建正式结算与本分析。",
            "- 本文只解释当前结果；完整逐人分值、适用状态和证据下限以正式结算JSON及三个分项JSON为准。",
            "",
            "## 七、读取入口",
            "",
            "- [第一项正式结算](01-第一项创业与政权取得能力正式结算.md)",
            "- [A创业战略能力](战略决策能力/01-第一项A战略决策能力结算.md)",
            "- [B政治整合能力](政治整合能力/01-第一项B政治整合能力结算.md)",
            "- [C军事夺取能力](军事夺取能力/01-第一项C军事夺取能力结算.md)",
            "",
        ]
    )
    return "\n".join(lines)
