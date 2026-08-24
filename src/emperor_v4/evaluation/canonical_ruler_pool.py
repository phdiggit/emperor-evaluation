from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


POOL_JSON = "config/common/canonical-ruler-pool.json"
POOL_MARKDOWN = "docs/项目总纲/正式评价对象范围.md"

SETTLEMENT_PATHS = {
    "first_item": "docs/评分结算/第一项创业与政权取得能力/01-第一项创业与政权取得能力正式结算.json",
    "second_item": "docs/评分结算/第二项治国净收益/01-第二项治国净收益405分正式结算.json",
    "third_item": "docs/评分结算/第三项军事与边疆净收益/02-第三项正式结算.json",
    "fourth_item": "docs/评分结算/第四项文明与国家整合收益/01-第四项文明与国家整合收益正式结算.json",
    "fifth_item": "docs/评分结算/第五项统治者政治素质/04-第五项统治者政治素质正式结算.json",
}

NO_EFFECTIVE_POWER = {
    "溥仪": "清帝在本项目时段内没有可持续、独立的最高决策权；复辟窗口亦不足一年。",
}

LIMITED_INDEPENDENT_POWER = {
    "司马炽": "实际权力长期受司马越制约，现有材料只能辨认有限本人选择，不足以支撑统一尺度的最高统治者评价。",
    "刘盈": "吕后强势主政下仅保留有限本人选择，不能把政权运行结果稳定归为本人最高决策。",
}

SHORT_EFFECTIVE_POWER = {
    "陈霸先": "557—559年实际最高统治不足3年。",
    "司马绍": "323—325年实际最高统治不足3年。",
    "朱聿键": "1645—1646年实际最高统治不足3年。",
    "司马懿": "249—251年高平陵政变后实际最高统治不足3年。",
    "述律平": "926—927年临朝窗口不足3年。",
    "刘知远": "947—948年实际最高统治不足3年。",
    "载淳": "1873—1875年亲政窗口不足3年。",
    "朱由崧": "1644—1645年实际最高统治不足3年。",
    "刘玄": "23—25年实际最高统治不足3年。",
    "萧绎": "552—554年称帝主政窗口不足3年。",
    "李旦": "710—712年复位窗口不足3年，且太平公主强势制约。",
    "赵桓": "1126—1127年实际最高统治不足3年。",
    "冉闵": "350—352年实际最高统治不足3年。",
    "李睍": "1226—1227年实际最高统治不足3年。",
}

FIRST_ITEM_NOT_APPLICABLE_ALLOWLIST = {
    "赵佶": "非奠基者；第一项源快照未收录不影响F=0。",
    "完颜永济": "非奠基者；没有可归责的建国或统一主链贡献，第一项明确不适用，F=0。",
    "载湉": "非奠基者；没有可归责的建国或统一主链贡献，第一项明确不适用，F=0。",
    "拓跋弘": "非奠基者；没有可归责的建国或统一主链贡献，第一项明确不适用，F=0。",
    "李安全": "非奠基者；没有可归责的建国或统一主链贡献，第一项明确不适用，F=0。",
    "李秉常": "非奠基者；没有可归责的建国或统一主链贡献，第一项明确不适用，F=0。",
    "李德旺": "非奠基者；没有可归责的建国或统一主链贡献，第一项明确不适用，F=0。",
}

FIRST_ITEM_PENDING_FORMAL_SETTLEMENT = {
    "刘崇": "北汉建国主链实际贡献者；第一项适用。",
    "孟知祥": "后蜀建国主链实际贡献者；第一项适用。",
    "李克用": "晋政权奠基主链实际贡献者；第一项适用。",
    "杨行密": "吴政权奠基主链实际贡献者；第一项适用。",
    "钱镠": "吴越建国主链实际贡献者；第一项适用。",
    "马殷": "楚政权建国主链实际贡献者；第一项适用。",
    "高季兴": "荆南建国主链实际贡献者；第一项适用。",
    "李德明": "西夏国家形成主链实际贡献者；第一项适用。",
}

# 已结算分项保留历史姓名和ID作为lineage；评价池统一消费右侧规范姓名和母池ID。
ITEM_NAME_ALIASES = {
    "first_item": {
        "完颜吴乞买": "完颜晟",
    },
}

CANONICAL_LEGACY_ID_REFS = {
    "RULER-JIN-TAIZONG": [
        "RULER-JIN-WANYAN-SHENG",
        "RULER-ROSTER-6FB8C85A5180DFB2",
    ],
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _index_by_name(payload: Mapping[str, Any], item: str) -> dict[str, Mapping[str, Any]]:
    records = payload.get("records") or ()
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in records:
        source_name = str(row.get("ruler_name") or "")
        name = ITEM_NAME_ALIASES.get(item, {}).get(source_name, source_name)
        if not name or name in indexed:
            raise ValueError(f"{item}存在空姓名或重复姓名：{name}")
        indexed[name] = row
    return indexed


def _fifth_evidence_counts(row: Mapping[str, Any]) -> tuple[int, int]:
    factual = 0
    baseline = 0
    for axis in ("A", "B", "C"):
        detail = (row.get("axes") or {}).get(axis)
        if not detail:
            continue
        if "客观皇帝基线" in str(detail.get("grade_reason") or ""):
            baseline += 1
        else:
            factual += 1
    return factual, baseline


def build_canonical_ruler_pool(workspace_root: Path) -> dict[str, Any]:
    paths = {key: workspace_root / relative for key, relative in SETTLEMENT_PATHS.items()}
    payloads = {key: _read_json(path) for key, path in paths.items()}
    indexed = {key: _index_by_name(payload, key) for key, payload in payloads.items()}

    master_records = list(payloads["fifth_item"].get("records") or ())
    master_ids = [str(row.get("ruler_id") or "") for row in master_records]
    if len(master_records) != 201 or any(not value for value in master_ids) or len(set(master_ids)) != 201:
        raise ValueError("第五项候选母池必须是201个唯一ruler_id")
    for item in ("third_item", "fourth_item"):
        ids = {str(row.get("ruler_id") or "") for row in payloads[item].get("records") or ()}
        if ids != set(master_ids):
            raise ValueError(f"{item}与201人候选母池ruler_id集合不一致")

    master_names = {str(row["ruler_name"]) for row in master_records}
    first_item_outside_candidate_pool = sorted(
        (
            {
                "ruler_id": str(row["ruler_id"]),
                "ruler_name": str(row["ruler_name"]),
                "pool_relation": "OUTSIDE_CANONICAL_CANDIDATE_POOL",
            }
            for canonical_name, row in indexed["first_item"].items()
            if canonical_name not in master_names
        ),
        key=lambda row: (row["ruler_name"], row["ruler_id"]),
    )
    outside_names = {row["ruler_name"] for row in first_item_outside_candidate_pool}
    expected_outside_names = {"塔不烟", "洪秀全", "耶律璟", "萧普速完", "黄巢"}
    if outside_names != expected_outside_names:
        raise ValueError(f"第一项池外记录集合漂移：{sorted(outside_names)}")

    records: list[dict[str, Any]] = []
    for master in master_records:
        name = str(master["ruler_name"])
        reason_code = None
        reason = None
        if name in NO_EFFECTIVE_POWER:
            reason_code = "EXCLUDED_NO_EFFECTIVE_POWER"
            reason = NO_EFFECTIVE_POWER[name]
        elif name in LIMITED_INDEPENDENT_POWER:
            reason_code = "EXCLUDED_LIMITED_INDEPENDENT_POWER"
            reason = LIMITED_INDEPENDENT_POWER[name]
        elif name in SHORT_EFFECTIVE_POWER:
            reason_code = "EXCLUDED_EFFECTIVE_POWER_LT_3_YEARS"
            reason = SHORT_EFFECTIVE_POWER[name]
        source_rows = {item: by_name.get(name) for item, by_name in indexed.items()}
        if reason_code is None:
            missing = [
                item
                for item in ("third_item", "fourth_item", "fifth_item")
                if source_rows[item] is None
            ]
            if missing:
                raise ValueError(f"正式池候选{name}缺少共同项：{missing}")
            if (
                source_rows["second_item"] is not None
                and source_rows["second_item"].get("second_item_score") is None
            ):
                raise ValueError(f"正式池候选{name}已有第二项记录但无分")
            if source_rows["third_item"].get("third_item_score_points") is None:
                raise ValueError(f"正式池候选{name}第三项无分")
            if source_rows["fourth_item"].get("fourth_item_signed_adjustment") is None:
                raise ValueError(f"正式池候选{name}第四项未闭合")
            if source_rows["fifth_item"].get("fifth_item_score_points") is None:
                raise ValueError(f"正式池候选{name}第五项无分")
            if (
                source_rows["second_item"] is not None
                and source_rows["first_item"] is None
                and name not in FIRST_ITEM_NOT_APPLICABLE_ALLOWLIST
            ):
                raise ValueError(f"正式池候选{name}缺少第一项记录且没有不适用裁决")
            if (
                source_rows["first_item"] is None
                and name not in FIRST_ITEM_NOT_APPLICABLE_ALLOWLIST
                and name not in FIRST_ITEM_PENDING_FORMAL_SETTLEMENT
            ):
                raise ValueError(f"正式池候选{name}缺少第一项适用性裁决")

        factual_axes, baseline_axes = _fifth_evidence_counts(master)
        records.append(
            {
                "ruler_id": master["ruler_id"],
                "ruler_name": name,
                "polity": master.get("polity"),
                "actual_power_window": master.get("actual_power_window"),
                "pool_status": "INCLUDED" if reason_code is None else "EXCLUDED",
                "settlement_readiness": (
                    "COMPOSITE_READY"
                    if reason_code is None and source_rows["second_item"] is not None
                    else (
                        "PENDING_SECOND_ITEM_FORMAL_SETTLEMENT"
                        if reason_code is None
                        else "NOT_APPLICABLE_EXCLUDED"
                    )
                ),
                "exclusion_reason_code": reason_code,
                "exclusion_reason": reason,
                "evidence_feasibility": {
                    "second_item_formal": source_rows["second_item"] is not None,
                    "third_item_formal": source_rows["third_item"] is not None,
                    "fourth_item_formal": source_rows["fourth_item"] is not None,
                    "fifth_item_formal": master.get("fifth_item_score_points") is not None,
                    "fifth_factual_axis_count": factual_axes,
                    "fifth_verified_baseline_axis_count": baseline_axes,
                },
                "source_item_ids": {
                    item: row.get("ruler_id") if row else None for item, row in source_rows.items()
                },
                "source_item_names": {
                    item: row.get("ruler_name") if row else None for item, row in source_rows.items()
                },
                "identity_resolution": {
                    "canonical_ruler_id": master["ruler_id"],
                    "canonical_name": name,
                    "matched_aliases": sorted(
                        {
                            str(row.get("ruler_name"))
                            for row in source_rows.values()
                            if row and str(row.get("ruler_name")) != name
                        }
                    ),
                    "legacy_id_refs": CANONICAL_LEGACY_ID_REFS.get(
                        str(master["ruler_id"]), []
                    ),
                },
                "first_item_scope_note": (
                    "对象未通过评价池准入，不进入第一项池内缺口统计。"
                    if reason_code is not None
                    else (
                        FIRST_ITEM_NOT_APPLICABLE_ALLOWLIST.get(name)
                        or FIRST_ITEM_PENDING_FORMAL_SETTLEMENT.get(name)
                    )
                ),
                "first_item_readiness": (
                    "NOT_APPLICABLE_EXCLUDED"
                    if reason_code is not None
                    else (
                        (
                            "FORMAL_RECORD_PRESENT_ALIAS_NORMALIZED"
                            if str(source_rows["first_item"].get("ruler_name")) != name
                            else "FORMAL_RECORD_PRESENT"
                        )
                        if source_rows["first_item"] is not None
                        else (
                            "EXPLICIT_NOT_APPLICABLE_F0"
                            if name in FIRST_ITEM_NOT_APPLICABLE_ALLOWLIST
                            else "PENDING_FIRST_ITEM_FORMAL_SETTLEMENT"
                        )
                    )
                ),
            }
        )

    records.sort(key=lambda row: str(row["ruler_id"]))
    included_count = sum(row["pool_status"] == "INCLUDED" for row in records)
    composite_ready_count = sum(row["settlement_readiness"] == "COMPOSITE_READY" for row in records)
    pending_second_item_count = sum(
        row["settlement_readiness"] == "PENDING_SECOND_ITEM_FORMAL_SETTLEMENT"
        for row in records
    )
    pending_first_item_scope_count = sum(
        row["pool_status"] == "INCLUDED"
        and row["first_item_readiness"] == "PENDING_SCOPE_REVIEW_BEFORE_COMPOSITE"
        for row in records
    )
    pending_first_item_formal_settlement_count = sum(
        row["pool_status"] == "INCLUDED"
        and row["first_item_readiness"] == "PENDING_FIRST_ITEM_FORMAL_SETTLEMENT"
        for row in records
    )
    reason_counts = Counter(
        row["exclusion_reason_code"] for row in records if row["pool_status"] == "EXCLUDED"
    )
    if (
        included_count != 184
        or len(records) - included_count != 17
        or composite_ready_count != 148
        or pending_second_item_count != 36
        or pending_first_item_scope_count != 0
        or pending_first_item_formal_settlement_count != 0
    ):
        raise ValueError(
            "正式池预期184人/排除17人/综合就绪148人/第二项待结算36人/第一项范围待复核0人/第一项待结算0人，"
            f"实际{included_count}/{len(records) - included_count}/{composite_ready_count}/"
            f"{pending_second_item_count}/{pending_first_item_scope_count}/"
            f"{pending_first_item_formal_settlement_count}"
        )
    expected_reason_counts = {
        "EXCLUDED_NO_EFFECTIVE_POWER": 1,
        "EXCLUDED_LIMITED_INDEPENDENT_POWER": 2,
        "EXCLUDED_EFFECTIVE_POWER_LT_3_YEARS": 14,
    }
    if dict(reason_counts) != expected_reason_counts:
        raise ValueError(f"排除理由计数漂移：{dict(reason_counts)}")

    return {
        "schema_version": "canonical-ruler-pool-v2",
        "status": "CURRENT",
        "candidate_pool_count": 201,
        "included_count": included_count,
        "composite_ready_count": composite_ready_count,
        "pending_second_item_count": pending_second_item_count,
        "pending_first_item_scope_count": pending_first_item_scope_count,
        "pending_first_item_formal_settlement_count": pending_first_item_formal_settlement_count,
        "first_item_outside_candidate_pool_count": len(first_item_outside_candidate_pool),
        "excluded_count": len(records) - included_count,
        "selection_policy": {
            "minimum_effective_power_years": 3,
            "requires_independent_highest_decision_power": True,
            "requires_formal_scores_for_admission": ["third_item", "fifth_item"],
            "requires_closed_signed_adjustment": "fourth_item",
            "second_item_policy": "local evidence availability permits admission; missing formal score blocks composite readiness and ranking only",
            "first_item_policy": "conditional_add_on_only; every absent record must be adjudicated as explicit F=0 or pending formal A/B/C settlement",
            "feasibility_policy": "admit rulers with sufficient local reading products and historical sources even when second-item settlement is pending",
            "exclusion_precedence": [
                "NO_EFFECTIVE_POWER",
                "LIMITED_INDEPENDENT_POWER",
                "EFFECTIVE_POWER_LT_3_YEARS",
            ],
        },
        "exclusion_reason_counts": expected_reason_counts,
        "source_sha256": {item: _sha256(path) for item, path in paths.items()},
        "item_name_aliases": ITEM_NAME_ALIASES,
        "first_item_outside_candidate_pool": first_item_outside_candidate_pool,
        "records": records,
    }


def render_canonical_ruler_pool_markdown(payload: Mapping[str, Any]) -> str:
    records = list(payload.get("records") or ())
    included = [row for row in records if row["pool_status"] == "INCLUDED"]
    excluded = [row for row in records if row["pool_status"] == "EXCLUDED"]
    by_polity: dict[str, list[str]] = defaultdict(list)
    for row in included:
        by_polity[str(row.get("polity") or "未标明")].append(str(row["ruler_name"]))

    lines = [
        "# 正式评价对象范围",
        "",
        "> 本文件是当前正式评价池的阅读视图；机器入口为 `config/common/canonical-ruler-pool.json`。`INCLUDED`表示通过对象准入，`COMPOSITE_READY`表示共同项已经齐备；综合分、总体统计与未来总排名只能消费后者。",
        "",
        "## 准入口径",
        "",
        "- 以第三、第四、第五项共同的201人全集为候选母池。",
        "- 实际、独立的最高决策权窗口至少3年；无实权、仅有有限本人选择或短期名义在位者排除。",
        "- 第三、第五项必须已有正式分，第四项必须已闭合有符号调整；第一项只决定奠基人附加分，不作为共同准入门。",
        "- 第二项无正式结算但本地通读产物和史料足以支持结算者仍纳入正式池，状态记为待结算；在补齐前不得进入综合分与总排名。",
        "",
        "## 结论",
        "",
        f"- 候选母池：{payload['candidate_pool_count']}人。",
        f"- 正式评价池：{payload['included_count']}人。",
        f"- 当前综合计算就绪：{payload['composite_ready_count']}人。",
        f"- 池内第二项待正式结算：{payload['pending_second_item_count']}人。",
        f"- 池内第一项适用范围待复核：{payload['pending_first_item_scope_count']}人。",
        f"- 池内第一项已判定适用、待正式结算：{payload['pending_first_item_formal_settlement_count']}人。",
        f"- 第一项历史快照中不属201人候选母池：{payload['first_item_outside_candidate_pool_count']}人；保留分项lineage，不进入本池。",
        f"- 排除：{payload['excluded_count']}人。",
        "",
        "## 排除对象",
        "",
        "| 对象 | 政权 | 实权窗口 | 排除理由 |",
        "|---|---|---|---|",
    ]
    reason_order = {
        "EXCLUDED_NO_EFFECTIVE_POWER": 0,
        "EXCLUDED_LIMITED_INDEPENDENT_POWER": 1,
        "EXCLUDED_EFFECTIVE_POWER_LT_3_YEARS": 2,
        "EXCLUDED_INCOMPLETE_COMMON_ITEM_COVERAGE": 3,
    }
    for row in sorted(
        excluded,
        key=lambda value: (reason_order[str(value["exclusion_reason_code"])], str(value["ruler_id"])),
    ):
        lines.append(
            f"| {row['ruler_name']} | {row.get('polity') or '—'} | {row.get('actual_power_window') or '—'} | {row['exclusion_reason']} |"
        )
    pending_second = [
        row for row in included if row["settlement_readiness"] == "PENDING_SECOND_ITEM_FORMAL_SETTLEMENT"
    ]
    lines.extend(
        [
            "",
            "## 池内第二项待正式结算",
            "",
            "以下对象已经通过实权、时长和材料可行性门，但在第二项补齐前不得计算综合分或进入总排名：",
            "",
            "| 对象 | 政权 | 实权窗口 | 第一项状态 |",
            "|---|---|---|---|",
        ]
    )
    for row in sorted(pending_second, key=lambda value: str(value["ruler_id"])):
        lines.append(
            f"| {row['ruler_name']} | {row.get('polity') or '—'} | {row.get('actual_power_window') or '—'} | {row['first_item_readiness']} |"
        )
    pending_first = [
        row for row in included
        if row["first_item_readiness"] == "PENDING_FIRST_ITEM_FORMAL_SETTLEMENT"
    ]
    lines.extend(["", "## 池内第一项正式结算状态", ""])
    if pending_first:
        for row in sorted(pending_first, key=lambda value: str(value["ruler_id"])):
            lines.append(f"- {row['ruler_name']}：{row['first_item_scope_note']}")
    else:
        lines.append("池内第一项适用范围与A/B/C正式结算均已闭合，待正式结算0人。")
    lines.extend(["", "## 第一项池外历史记录", ""])
    lines.append(
        "、".join(row["ruler_name"] for row in payload["first_item_outside_candidate_pool"])
        + "。这些记录保留在第一项正式快照中作为既有结算，但不得被当前评价池或综合计算消费。"
    )
    lines.extend(["", "## 正式池名单", ""])
    for polity in sorted(by_polity):
        names = "、".join(sorted(by_polity[polity]))
        lines.append(f"- {polity}（{len(by_polity[polity])}）：{names}。")
    lines.append("")
    return "\n".join(lines)


def write_canonical_ruler_pool(workspace_root: Path) -> dict[str, Path]:
    payload = build_canonical_ruler_pool(workspace_root)
    json_path = workspace_root / POOL_JSON
    markdown_path = workspace_root / POOL_MARKDOWN
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_canonical_ruler_pool_markdown(payload), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def verify_canonical_ruler_pool(workspace_root: Path) -> dict[str, Any]:
    path = workspace_root / POOL_JSON
    checked_in = _read_json(path)
    rebuilt = build_canonical_ruler_pool(workspace_root)
    if checked_in != rebuilt:
        raise ValueError("正式评价池与当前五项入口重建结果不一致")
    markdown_path = workspace_root / POOL_MARKDOWN
    expected_markdown = render_canonical_ruler_pool_markdown(rebuilt)
    if markdown_path.read_text(encoding="utf-8") != expected_markdown:
        raise ValueError("正式评价池Markdown与机器入口不一致")
    return {
        "path": POOL_JSON,
        "candidate_pool_count": rebuilt["candidate_pool_count"],
        "included_count": rebuilt["included_count"],
        "composite_ready_count": rebuilt["composite_ready_count"],
        "pending_second_item_count": rebuilt["pending_second_item_count"],
        "pending_first_item_scope_count": rebuilt["pending_first_item_scope_count"],
        "pending_first_item_formal_settlement_count": rebuilt[
            "pending_first_item_formal_settlement_count"
        ],
        "first_item_outside_candidate_pool_count": rebuilt[
            "first_item_outside_candidate_pool_count"
        ],
        "excluded_count": rebuilt["excluded_count"],
        "exclusion_reason_counts": rebuilt["exclusion_reason_counts"],
    }
