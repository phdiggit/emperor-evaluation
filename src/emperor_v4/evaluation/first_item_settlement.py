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
