from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Any, Mapping

from emperor_v4.evaluation.formal_json_store import load_json


FORMAL_SETTLEMENT_JSON_PATH = Path(
    "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
)
FORMAL_SETTLEMENT_MARKDOWN_PATH = FORMAL_SETTLEMENT_JSON_PATH.with_suffix(".md")

D_SCORE_POINTS = {
    "D0": {"LOW": 0.0, "MID": 3.0, "HIGH": 6.0},
    "D1": {"LOW": 10.0, "MID": 12.0, "HIGH": 14.0},
    "D2": {"LOW": 18.0, "MID": 20.0, "HIGH": 22.0},
    "D3": {"LOW": 24.0, "MID": 26.0, "HIGH": 28.0},
    "D4": {"LOW": 30.0, "MID": 32.0, "HIGH": 34.0},
    "D5": {"LOW": 36.0, "MID": 38.0, "HIGH": 40.0},
    "D-N": {"NOT_APPLICABLE": 0.0},
}


def _load(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"UTF-8 BOM forbidden: {path}")
    return load_json(path)


def _assert_no_duplicate_json_keys(path: Path) -> None:
    targets = [path]
    shard_root = path.with_suffix("")
    if shard_root.is_dir():
        targets.extend(sorted(shard_root.glob("*.json")))
    for target in targets:
        duplicates: list[str] = []

        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    duplicates.append(key)
                result[key] = value
            return result

        json.loads(target.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
        if duplicates:
            raise ValueError(f"D正式JSON存在重复键：{target} {sorted(set(duplicates))}")


def _distribution(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row[key]) for row in records).items()))


def _reader_text(value: object) -> str:
    if value is None or value == "" or value == [] or value == {}:
        return "未另列"
    if isinstance(value, Mapping):
        return "；".join(
            f"{key}：{_reader_text(item)}" for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return "；".join(_reader_text(item) for item in value)
    return (
        str(value)
        .replace("LOWER_BOUND", "证据下限")
        .replace("PROVISIONAL", "暂定")
        .replace("CONFIRMED", "已确认")
        .replace("NOT_APPLICABLE", "不适用")
        .replace(
            "Territorial and unification gains consumed elsewhere are removed; D retains security change, adverse phases, mobilization, and own-side costs.",
            "领土与统一收益已由其他分项消费；D仅保留安全变化、负向阶段、动员和本方成本。",
        )
        .replace(
            "C5 rests only on the merged Song chain M5 burden. No F3 is inferred and no separate chain is combined; therefore not C6.",
            "C5仅由合并后的攻宋链M5负担准入；不推定F3，也不拼接其他独立链，因此不进C6。",
        )
    )


def _reign_label(value: object) -> str:
    if isinstance(value, (list, tuple)):
        return "；".join(str(item) for item in value)
    return str(value)


def _chain_name(chain: Mapping[str, Any]) -> str:
    return str(chain.get("chain_name") or chain.get("name") or chain["chain_id"])


_CHALLENGE_LABELS = {
    "O1_LOCAL_PRESSURE": "局部武装或地方压力",
    "O2_BORDER_RAIDING": "可持续袭扰边境或争夺有限区域的压力",
    "O3_MAJOR_DIRECTION_THREAT": "一个主要战略方向的持续压力",
    "O4_MULTI_DIRECTION_OR_CORE_REGION_THREAT": "多方向或核心区域威胁",
    "O5_CORE_DEFENSE_SYSTEM_THREAT": "迫使核心防务体系系统响应的威胁",
    "O6_EXISTENTIAL_MILITARY_THREAT": "威胁政权军事生存的压力",
}

_RESULT_LABELS = {
    "E0": "未形成净安全改善",
    "E1": "止损、击退或恢复原线",
    "E2": "稳定或恢复一个区域性方向",
    "E3_MAJOR_STAGE": "取得重大阶段成果，但战略目标未闭合",
    "E3_REGIONAL_TERMINAL": "终结区域对手或使单一区域方向永久稳定",
    "E4_MAJOR_STRATEGIC": "终结主要威胁或长期重构主要国防方向",
    "E5A": "终结或不可逆降级全国防务级外部体系",
    "E5B": "长期重构多个重要方向的战略体系",
    "EN1": "局部方向净恶化",
    "EN2": "一个或多个主要方向耐久恶化",
    "EN3": "全国或多数核心防务体系崩溃",
    "NOT_CLOSED": "终点材料不足，未作结果裁决",
    "NOT_APPLICABLE": "仅作成本或过程证据",
}

_CHANGE_LABELS = {
    "OPPONENT_SYSTEM_TERMINATED": "对手体系终结",
    "LARGE_STRATEGIC_SYSTEM_RECONSTRUCTED": "大型战略体系重构",
    "MAJOR_THREAT_TERMINATED_OR_DIRECTION_RESTRUCTURED": "主要威胁终结或方向重构",
    "REGIONAL_THREAT_TERMINATED": "区域威胁终结",
    "REGIONAL_CONTROL_STABILIZED": "区域控制稳定",
    "THREAT_CONTAINED_WITHOUT_DURABLE_CLOSURE": "威胁受遏制，但未形成耐久闭合",
    "MAJOR_STAGE_GAIN_TARGET_NOT_CLOSED": "取得重大阶段成果，但目标未闭合",
    "NOT_CLOSED": "材料未闭合",
    "NOT_CLOSED_IN_CURRENT_SOURCE": "现有材料未闭合",
}

_DURABILITY_LABELS = {
    "STRUCTURAL_OR_LONG": "结构性或长期",
    "LIMITED_OR_NOT_CLOSED": "有限或尚未闭合",
    "NOT_CLOSED": "尚未闭合",
}


def _label(value: object, labels: Mapping[str, str]) -> str:
    text = str(value)
    return labels.get(text, _reader_text(text))


def _chain_result(chain: Mapping[str, Any]) -> str:
    raw = (
        chain.get("security_result_grade")
        or chain.get("achievement_grade_detail")
        or chain.get("achievement_grade")
        or chain.get("result_type")
        or "仅作成本或过程证据"
    )
    return _label(raw, _RESULT_LABELS)


def _chain_basis(chain: Mapping[str, Any]) -> str:
    basis = (
        chain.get("security_change_basis")
        or chain.get("basis")
        or chain.get("terminal_result_profile")
    )
    if not isinstance(basis, Mapping):
        return _reader_text(basis)

    parts: list[str] = []
    threat_change = basis.get("threat_change")
    if threat_change:
        parts.append(f"安全变化：{_label(threat_change, _CHANGE_LABELS)}")
    control_change = basis.get("control_change")
    if control_change and control_change != "NOT_CLOSED_IN_CURRENT_SOURCE":
        parts.append(f"控制变化：{_label(control_change, _CHANGE_LABELS)}")
    material_return = basis.get("material_return")
    if material_return and material_return != "NOT_CLOSED_IN_CURRENT_SOURCE":
        parts.append(f"资源回收：{_label(material_return, _CHANGE_LABELS)}")
    durability = basis.get("durability")
    if durability:
        parts.append(f"持续性：{_label(durability, _DURABILITY_LABELS)}")
    aggregation = basis.get("aggregation_basis")
    standard_aggregation = "同一对手、同一战略目标和连续授权合链；终点成果只消费一次。"
    if aggregation and str(aggregation) != standard_aggregation:
        parts.append(f"归并依据：{_reader_text(aggregation)}")
    return "；".join(parts) if parts else "未另列链级结果说明。"


def _compact_challenge_grade(chain: Mapping[str, Any]) -> str:
    value = str(chain.get("effective_opponent_challenge_grade") or "")
    match = re.match(r"(O[1-6])(?:_|$)", value)
    return match.group(1) if match else "不适用"


def _chain_terminal_summary(chain: Mapping[str, Any]) -> str:
    raw = str(
        chain.get("headline")
        or chain.get("final_control_result")
        or (chain.get("chain_security_profile") or {}).get("terminal_security_state")
        or ""
    )
    axes = re.search(r"终点\s*(SB\d+/SN\d+/BCP\d+/BCN\d+)", raw)
    if axes:
        summary = raw[axes.end():].lstrip("；;。 ")
        return f"终点{axes.group(1)}" + (f"；{summary}" if summary else "。")
    return _reader_text(raw) if raw else "终点四轴未单列。"


def _chain_evidence_line(chain: Mapping[str, Any]) -> str:
    grade = str(
        chain.get("achievement_grade")
        or chain.get("security_result_grade")
        or chain.get("achievement_grade_detail")
        or "NOT_APPLICABLE"
    )
    position = {
        "LOW": "低位",
        "MID": "中位",
        "HIGH": "高位",
        "HIGHEST": "最高位",
        "NOT_APPLICABLE": "不适用",
    }.get(str(chain.get("within_grade_position") or "NOT_APPLICABLE"), "不适用")
    return (
        f"**{_chain_name(chain)}**：{_compact_challenge_grade(chain)}；"
        f"{grade}·{position}。{_chain_terminal_summary(chain)}"
    )


def _cost_structure_lines(profile: Mapping[str, Any]) -> list[str]:
    signature = (profile.get("cost_summary") or {}).get("comparative_cost_signature")
    if not isinstance(signature, Mapping):
        admission = (
            profile.get("single_admission_fact")
            or profile.get("admission_fact")
            or profile.get("basis")
            or "正式JSON未另列更细的成本拆分。"
        )
        lines = [f"  - **成本准入**：{_reader_text(admission)}"]
        if profile.get("major_force_losses"):
            lines.append(
                f"  - **单链峰值与毁损**：{_reader_text(profile['major_force_losses'])}"
            )
        return lines
    labels = {
        "single_chain_highest_structure": "单链峰值与毁损",
        "full_reign_cumulative_force_loss": "全期累计毁损",
        "full_reign_mobilization_and_repetition": "动员与反复投入",
        "same_or_continuous_chain_post_disaster_remobilization": "灾后再动员",
        "ruler_personal_responsibility": "本人责任",
        "evidence_coverage": "证据覆盖",
    }
    return [
        f"  - **{label}**：{_reader_text(signature[key])}"
        for key, label in labels.items()
        if signature.get(key)
    ]


def _ordinary_summary(value: object) -> str:
    if not isinstance(value, Mapping):
        return _reader_text(value)
    labels = {
        "count": "普通链",
        "presumed_or_explicit_success_count": "已收束",
        "explicit_failure_or_unresolved_count": "失败或未决",
        "abnormal_cost_chain_count": "异常成本链",
        "abnormal_process_chain_count": "异常过程链",
        "excluded_nonconsumable_count": "排除链",
    }
    parts = [
        f"{label}{value[key]}条"
        for key, label in labels.items()
        if isinstance(value.get(key), int) and int(value[key]) != 0
    ]
    notes = value.get("notes")
    if notes:
        parts.append(str(notes))
    return "；".join(parts) if parts else "无另需展开的普通平乱成本。"


def render_third_item_d_markdown(payload: Mapping[str, Any]) -> str:
    records = sorted(
        payload["records"],
        key=lambda row: (-float(row["D_score_points"]), str(row["ruler_id"])),
    )
    position_labels = {
        "LOW": "低位",
        "MID": "中位",
        "HIGH": "高位",
        "HIGHEST": "最高位",
        "NOT_APPLICABLE": "不适用",
    }
    status_labels = {
        "CONFIRMED": "确认",
        "LOWER_BOUND": "下界",
        "PROVISIONAL": "暂定",
        "CEILING": "上界",
        "NOT_APPLICABLE": "不适用",
    }
    grade_meanings = {
        "D5": "变革性净改善",
        "D4": "强主要战略净改善",
        "D3": "明确主要方向净改善",
        "D2": "有限但清楚的净改善",
        "D1": "接近中性、止损或无可重复主链",
        "D0": "明显恶化或被高成本压至最低档",
        "D-N": "跨项整链去重后不适用",
    }
    grade_counts = Counter(str(row["D_grade"]) for row in records)
    cost_counts = Counter(
        str(row["attributable_cost_profile"]["cost_band"]) for row in records
    )
    lines = [
        "# 秦至清第三项D军事成本收益比正式结算",
        "",
        "规则见[`D规则与结算合同`](../../../分项规则/第三项军事与边疆净收益/军事成本收益比/00-规则与结算合同.md)及[军事成本评估合同](../../../证据规则/军事成本评估合同.md)。",
        "",
        f"本次共结算{len(records)}位评价主体。下表及逐人依据均由同名正式JSON当前值生成；第三项总分和排名见第三项正式结算。",
        "",
        "## 阅读口径",
        "",
        "- D先看统治窗口内对外战略链和异常内部战略链造成的安全态势净变化，正向E与负向EN同权。",
        "- 军事成本按独立合同裁决，只记录本方实际投入与毁损；归责决定消费窗口，不改变损害严重度，敌军、叛军和平民损失不计入。",
        "- 第一项创业统一链及第三项C独占任务整链退出D局部结算，并在逐人段落的“跨项排除链”中明示。",
        "",
        "## 档位分布",
        "",
        "| D档 | 人数 | 当前含义 |",
        "|---:|---:|---|",
    ]
    for grade in ("D5", "D4", "D3", "D2", "D1", "D0", "D-N"):
        lines.append(f"| {grade} | {grade_counts[grade]} | {grade_meanings[grade]}。 |")
    cost_summary = "、".join(
        f"{grade}={cost_counts[grade]}"
        for grade in ("C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "NOT_APPLICABLE")
        if cost_counts[grade]
    )
    lines += [
        "",
        f"成本档分布：{cost_summary}。C档用于成果相近人物的负担比较和高成本修正，不与D档机械一一对应。",
        "",
        "## 正式结算总表",
        "",
        "| 序 | 皇帝 | 政权 | 在位 | D档 | 档内 | D/40 | C档 |",
        "|---:|---|---|---|---:|---|---:|---:|",
    ]
    for index, row in enumerate(records, 1):
        profile = row["attributable_cost_profile"]
        lines.append(
            f"| {index} | {row['ruler_name']} | {row['polity']} | {_reign_label(row['reign_range'])} | "
            f"{row['D_grade']} | {position_labels[str(row['D_within_grade_position'])]} | "
            f"{float(row['D_score_points']):.1f} | {profile['cost_band']} |"
        )
    lines += ["", "## 逐人结算依据", ""]
    prior_grade = None
    for index, row in enumerate(records, 1):
        grade = str(row["D_grade"])
        if grade != prior_grade:
            lines += [f"## {grade}档", ""]
            prior_grade = grade
        profile = row["attributable_cost_profile"]
        cost_status = status_labels.get(str(profile["status"]), _reader_text(profile["status"]))
        cost_position = position_labels.get(str(profile["position"]), _reader_text(profile["position"]))
        lines += [
            f"### {index}. {row['ruler_name']}（{grade}·{position_labels[str(row['D_within_grade_position'])]}；{profile['cost_band']}·{cost_status}/{cost_position}）",
            "",
            "- **对外战略链**：",
        ]
        external = list(row.get("external_strategic_chains") or ())
        if not external:
            lines.append("  - 无合格独立链。")
        for chain in external:
            lines.append(f"  - {_chain_evidence_line(chain)}")
        lines.append("- **异常内部链**：")
        internal = list(row.get("strategic_internal_chains") or ())
        if not internal:
            lines.append("  - 无。")
        for chain in internal:
            lines.append(f"  - {_chain_evidence_line(chain)}")
        excluded = list(row.get("cross_item_excluded_chains") or ())
        lines.append("- **跨项排除链**：")
        if not excluded:
            lines.append("  - 无。")
        for chain in excluded:
            reason = chain.get("reason") or chain.get("basis") or "整链退出D，不参与成果或成本计算。"
            lines.append(f"  - `{chain['chain_id']}`：{_reader_text(reason)}")
        lines.append(
            f"- **可归责成本**：{profile['cost_band']}（{cost_status}，{cost_position}）。"
        )
        cost_structure = _cost_structure_lines(profile)
        lines += ["- **成本结构**：", *cost_structure]
        exclusions = list(row.get("non_military_loss_cost_exclusions") or ())
        if exclusions:
            lines.append(f"- **非本方军事成本排除**：{_reader_text(exclusions)}")
        ordinary = row.get("ordinary_suppression_summary")
        if ordinary not in (None, "", [], {}):
            lines.append(f"- **普通平乱摘要**：{_ordinary_summary(ordinary)}")
        lines += [f"- **最终裁决**：{_reader_text(row['adjudication_basis'])}", ""]
    return "\n".join(lines).rstrip() + "\n"


def _validate_markdown(payload: Mapping[str, Any], markdown: str) -> None:
    expected = render_third_item_d_markdown(payload)
    if markdown != expected:
        raise ValueError("D Markdown与正式JSON完整渲染结果不一致")
    position_labels = {"低位": "LOW", "中位": "MID", "高位": "HIGH", "不适用": "NOT_APPLICABLE"}
    rows: dict[str, tuple[str, str, float]] = {}
    in_table = False
    for line in markdown.splitlines():
        if line == "## 正式结算总表":
            in_table = True
            continue
        if in_table and line.startswith("## "):
            break
        if not in_table or not line.startswith("| "):
            continue
        cells = [cell.strip() for cell in line[1:-1].split("|")]
        if not cells[0].isdigit():
            continue
        rows[cells[1]] = (cells[4], position_labels[cells[5]], float(cells[6]))
    if len(rows) != len(payload["records"]):
        raise ValueError("D Markdown总表未覆盖全部正式人物")
    for record in payload["records"]:
        expected = (
            record["D_grade"], record["D_within_grade_position"],
            float(record["D_score_points"]),
        )
        if rows.get(record["ruler_name"]) != expected:
            raise ValueError(f"D Markdown与JSON不一致：{record['ruler_name']}")


def validate_third_item_d_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_id") != "emperor-v4-d-strategy-chain-formal-settlement-batch-v2":
        raise ValueError("第三项D正式schema不合法")
    if payload.get("canonical_status") != "FORMAL_CURRENT":
        raise ValueError("第三项D不是当前正式结算")
    if payload.get("authority_mode") != "FORMAL_SETTLEMENT_PATCH_SOURCE":
        raise ValueError("第三项D正式JSON未声明为patch权威")
    if not payload.get("formal_grade_write") or not payload.get("formal_score_write"):
        raise ValueError("第三项D正式档位或点值未闭合")
    if payload.get("database_write") or payload.get("third_item_total_and_ranking_written"):
        raise ValueError("第三项D写入边界不合法")

    records = list(payload.get("records") or ())
    if payload.get("record_count") != len(records) or len(records) != 201:
        raise ValueError("第三项D正式覆盖必须为201人")
    if len({row.get("ruler_id") for row in records}) != len(records):
        raise ValueError("第三项D存在重复人物ID")
    if len({row.get("ruler_name") for row in records}) != len(records):
        raise ValueError("第三项D存在重复人物名")

    chain_count = 0
    excluded_chain_count = 0
    for row in records:
        grade = str(row.get("D_grade"))
        position = str(row.get("D_within_grade_position"))
        try:
            expected = D_SCORE_POINTS[grade][position]
        except KeyError as exc:
            raise ValueError(f"D点值映射未闭合：{row.get('ruler_name')} {grade}/{position}") from exc
        if float(row.get("D_score_points")) != expected:
            raise ValueError(f"D正式点值与档位不一致：{row.get('ruler_name')}")
        if row.get("D_score_status") != "DIRECT_D_SCORE_ASSIGNED":
            raise ValueError(f"D正式点值状态未闭合：{row.get('ruler_name')}")
        if not row.get("coverage_status") or not row.get("adjudication_basis"):
            raise ValueError(f"D正式裁决依据不完整：{row.get('ruler_name')}")
        if not row.get("formal_grade_write") or not row.get("formal_score_write") or row.get("database_write"):
            raise ValueError(f"D人物写入边界不合法：{row.get('ruler_name')}")
        profile = row.get("attributable_cost_profile") or {}
        if not profile.get("cost_band") or not profile.get("position") or not profile.get("status"):
            raise ValueError(f"D成本画像不完整：{row.get('ruler_name')}")

        chains = [
            *(row.get("external_strategic_chains") or ()),
            *(row.get("strategic_internal_chains") or ()),
        ]
        chain_ids = [chain.get("chain_id") for chain in chains]
        if len(chain_ids) != len(set(chain_ids)) or any(not value for value in chain_ids):
            raise ValueError(f"D计分战略链ID重复或缺失：{row.get('ruler_name')}")
        for chain in chains:
            if not chain.get("source_refs") or not (
                chain.get("security_change_basis")
                or chain.get("basis")
                or chain.get("terminal_result_profile")
            ):
                raise ValueError(f"D战略链证据不完整：{row.get('ruler_name')} {chain.get('chain_id')}")
        for chain in row.get("strategic_internal_chains") or ():
            result = chain.get("security_result_grade")
            if result not in {"E0", "E1", "E2", "E3_MAJOR_STAGE", "E3_REGIONAL_TERMINAL", "E4_MAJOR_STRATEGIC", "E5A", "E5B", "EN1", "EN2", "EN3", "NOT_APPLICABLE", "NOT_CLOSED"}:
                raise ValueError(f"内部链缺少合法安全终点：{chain.get('chain_id')}")
            excluded = result in {"NOT_APPLICABLE", "NOT_CLOSED"}
            if excluded and not chain.get("security_result_exclusion_basis"):
                raise ValueError(f"内部链未闭合或排除须说明具体理由：{chain.get('chain_id')}")
            if not excluded and (chain.get("main_security_evaluation") is False or chain.get("security_result_exclusion_basis")):
                raise ValueError(f"内部链已有结果却被排除收益：{chain.get('chain_id')}")
        results = dict(sorted(Counter(chain.get("security_result_grade", "NOT_APPLICABLE") for chain in chains).items()))
        if row.get("security_result_distribution") != results:
            raise ValueError(f"安全结果分布与逐链裁决不一致：{row.get('ruler_name')}")
        chain_count += len(chains)
        excluded_chain_count += len(row.get("cross_item_excluded_chains") or ())

    grade_distribution = _distribution(records, "D_grade")
    position_distribution = dict(sorted(Counter(
        f"{row['D_grade']}-{row['D_within_grade_position']}" for row in records
    ).items()))
    score_distribution = dict(sorted(Counter(
        str(float(row["D_score_points"])) for row in records
    ).items(), key=lambda item: float(item[0])))
    if payload.get("grade_distribution") != grade_distribution:
        raise ValueError("D档位分布与正式记录不一致")
    if payload.get("grade_position_distribution") != position_distribution:
        raise ValueError("D档内位置分布与正式记录不一致")
    if payload.get("score_distribution") != score_distribution:
        raise ValueError("D点值分布与正式记录不一致")
    if (payload.get("score_mapping") or {}).get("points") != D_SCORE_POINTS:
        raise ValueError("D点值映射合同不一致")
    if (payload.get("score_mapping") or {}).get("legacy_Q_consumed") is not False:
        raise ValueError("旧线性Q不得成为当前D正式裁决来源")
    if (payload.get("cross_item_deduplication") or {}).get("excluded_chain_count") != excluded_chain_count:
        raise ValueError("D跨项排除链计数不一致")
    if (payload.get("cross_item_deduplication") or {}).get("leaked_into_scoring_arrays") != 0:
        raise ValueError("D跨项排除链泄漏到计分数组")
    return {
        "status": "PASS", "record_count": len(records),
        "strategic_chain_count": chain_count,
        "excluded_chain_count": excluded_chain_count,
        "grade_distribution": grade_distribution,
    }


def verify_third_item_d_formal_settlement(repo_root: Path) -> dict[str, Any]:
    json_path = repo_root / FORMAL_SETTLEMENT_JSON_PATH
    markdown_path = repo_root / FORMAL_SETTLEMENT_MARKDOWN_PATH
    _assert_no_duplicate_json_keys(json_path)
    payload = _load(json_path)
    result = validate_third_item_d_payload(payload)
    _validate_markdown(payload, markdown_path.read_text(encoding="utf-8"))
    return result


if __name__ == "__main__":
    print(json.dumps(verify_third_item_d_formal_settlement(Path.cwd()), ensure_ascii=False, indent=2))
