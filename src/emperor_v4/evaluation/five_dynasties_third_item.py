"""Shared current third-item reading and handoff checks.

The former dynasty-specific import, rebuilding and write commands are retired;
current settlement entrypoints are registered in config/project.yml.
"""

from __future__ import annotations

import json

from emperor_v4.evaluation.third_item_b_control_depth import render_control_depth_packages

from pathlib import Path

import re

from typing import Any, Iterable, Mapping, Sequence

AB_HANDOFF_ADJUDICATION_PATH = Path("config/third-item/third-item-ab-handoff-adjudications.json")

A_STATE_NAMES = {
    "A1": (
        "A1S0_EXISTENTIAL_CRISIS", "A1S1_SEVERE_THREAT", "A1S2_STRATEGIC_DISADVANTAGE",
        "A1S3_CONTESTED_BALANCE", "A1S4_STABLE_ADVANTAGE", "A1S5_DOMINANT_ORDER",
    ),
    "A2": (
        "A2S0_CORE_EXPOSED", "A2S1_BROKEN_BOUNDARY", "A2S2_LOCAL_DEFENSIBLE_POINTS",
        "A2S3_EFFECTIVE_MAIN_BOUNDARY", "A2S4_OVERALL_SECURE_WITH_GAPS", "A2S5_SECURE_STRATEGIC_SYSTEM",
    ),
}

def validate_ab_shared_handoffs(
    workspace_root: Path, records: Sequence[Mapping[str, Any]], *, check_b1: bool = True
) -> None:
    payload = json.loads(
        (workspace_root / AB_HANDOFF_ADJUDICATION_PATH).read_text(encoding="utf-8")
    )
    if payload.get("schema_version") != "third-item-ab-handoff-adjudications-v1":
        raise ValueError("AB共享交班裁决schema错误")
    if payload.get("status") != "CURRENT":
        raise ValueError("AB共享交班裁决不是当前值")
    rows_by_name: dict[str, Mapping[str, Any]] = {}
    for row in records:
        name = str(row["ruler_name"])
        if name in rows_by_name:
            raise ValueError(f"AB共享交班不能按重名主体定位：{name}")
        rows_by_name[name] = row

    declared_pairs: set[tuple[str, str]] = set()
    for sequence in payload.get("direct_sequences") or ():
        names = [str(value) for value in sequence]
        if len(names) < 2:
            raise ValueError("AB直接交班序列至少需要两位主体")
        missing = [name for name in names if name not in rows_by_name]
        if missing:
            raise ValueError("AB直接交班主体缺失：" + ",".join(missing))
        for left_name, right_name in zip(names, names[1:]):
            pair = (left_name, right_name)
            if pair in declared_pairs:
                raise ValueError(f"AB直接交班重复声明：{left_name}->{right_name}")
            declared_pairs.add(pair)
            left = rows_by_name[left_name]
            right = rows_by_name[right_name]
            mismatches: list[str] = []
            for axis in ("A1", "A2"):
                left_end = str(left["axes"][axis]["end"])
                right_start = str(right["axes"][axis]["start"])
                if left_end != right_start:
                    mismatches.append(f"{axis}:{left_end}->{right_start}")
            if check_b1:
                left_control = float(left["b1_control_equivalents"]["end"])
                right_control = float(right["b1_control_equivalents"]["start"])
                if abs(left_control - right_control) > 1e-9:
                    mismatches.append(f"B1:{left_control}->{right_control}")
            if mismatches:
                raise ValueError(
                    f"AB直接交班快照不一致：{left_name}->{right_name}；"
                    + "；".join(mismatches)
                )

    bridge_pairs: set[tuple[str, str]] = set()
    for bridge in payload.get("state_bridges") or ():
        left_name = str(bridge.get("left_ruler") or "")
        right_name = str(bridge.get("right_ruler") or "")
        pair = (left_name, right_name)
        if not left_name or not right_name or pair in bridge_pairs:
            raise ValueError("AB状态桥主体为空或重复")
        if left_name not in rows_by_name or right_name not in rows_by_name:
            raise ValueError(f"AB状态桥主体缺失：{left_name}->{right_name}")
        if pair in declared_pairs:
            raise ValueError(f"AB交班不得同时声明直接与状态桥：{left_name}->{right_name}")
        if not str(bridge.get("bridge_type") or "").strip() or not str(
            bridge.get("rationale") or ""
        ).strip():
            raise ValueError(f"AB状态桥缺少类型或理由：{left_name}->{right_name}")
        bridge_pairs.add(pair)

def _competition_ranked_records(
    records: Sequence[Mapping[str, Any]], score_key: str
) -> list[tuple[int, Mapping[str, Any]]]:
    eligible = sorted(
        (row for row in records if row.get(score_key) is not None),
        key=lambda row: (-float(row[score_key]), str(row["ruler_name"])),
    )
    ranked: list[tuple[int, Mapping[str, Any]]] = []
    previous_score: float | None = None
    current_rank = 0
    for position, row in enumerate(eligible, start=1):
        score = float(row[score_key])
        if previous_score is None or score != previous_score:
            current_rank = position
            previous_score = score
        ranked.append((current_rank, row))
    return ranked

def _markdown_cell(value: object) -> str:
    return " ".join(str(value).replace("|", "／").splitlines()).strip()

def _reign_range_label(value: object) -> str:
    if isinstance(value, (list, tuple)):
        if len(value) == 2 and all(isinstance(item, int) for item in value):
            return f"{value[0]}-{value[1]}"
        return "；".join(str(item) for item in value)
    return str(value)

def _joined_reasons(values: Iterable[object]) -> str:
    reasons = [str(value).strip().rstrip("。；") for value in values if str(value).strip()]
    return "；".join(reasons) + ("。" if reasons else "")

def _trajectory_label(axis: Mapping[str, Any], prefix: str) -> str:
    def label(value: object) -> str:
        match = re.search(rf"{prefix}S(\d+)", str(value))
        return f"{prefix}-{match.group(1)}" if match else str(value)

    return f"{label(axis.get('start'))}→{label(axis.get('end'))}"

B_GRADE_MEANINGS = {
    "B2": {
        0: "没有可识别战略价值的实际控制成果",
        1: "价值有限且主要改善单点态势",
        2: "对局部交通、防御、资源或贸易有明确作用",
        3: "对主要区域的门户、走廊、缓冲、补给或强敌压制有重要作用",
        4: "对一个主要战略方向有关键作用并显著改变攻防条件",
        5: "对国家存续、核心区安全或整体战略格局有决定性价值",
    },
    "B4": {
        0: "交班前主要成果已经丧失或始终只有名义控制",
        1: "交班时仍处战时占领、围困或随时可能失控状态",
        2: "成果结构尚未完备并明显依赖临时投入",
        3: "已有常态运行成果但仍存在脆弱包、结构缺口或较高维持压力",
        4: "必要制度、驻防、指挥、补给或地方安排已经闭合，仅余次要缺口",
        5: "主要成果能够正常移交且不依赖异常资源或个人临时维持",
    },
}

def _reader_region_list(items: Sequence[Mapping[str, Any]], relation: str) -> str:
    region_totals: dict[str, list[float]] = {}
    for item in items:
        control = item.get("control_equivalent") or {}
        if isinstance(control, Mapping):
            start = float(
                control.get("start")
                if control.get("start") is not None
                else item.get("start_equivalent") or 0.0
            )
            end = float(
                control.get("end")
                if control.get("end") is not None
                else item.get("end_equivalent") or 0.0
            )
        else:
            anchors = {str(anchor) for anchor in item.get("anchors") or ()}
            start = float(control) if "start" in anchors else 0.0
            end = float(control) if "end" in anchors else 0.0
        name = str(
            item.get("object_name")
            or item.get("region_name")
            or item.get("object_id")
            or item.get("region_id")
            or "未命名控制区"
        )
        totals = region_totals.setdefault(name, [0.0, 0.0])
        totals[0] += start
        totals[1] += end
    return "、".join(
        name
        for name, (start, end) in region_totals.items()
        if {
            "expanded": end > start,
            "contracted": end < start,
            "retained": end > 0,
        }[relation]
    )

def _b1_region_change_reader_text(row: Mapping[str, Any]) -> str:
    ledger = row.get("b1_region_adjudications") or []
    expanded = _reader_region_list(ledger, "expanded")
    contracted = _reader_region_list(ledger, "contracted")
    if not ledger:
        display_names = {
            "GUANZHONG_LONGYOU": "关中—陇右主要控制带",
            "HUAI_RIVER_FRONTIER": "淮河边疆",
            "LINGNAN_SOUTH": "岭南边疆控制带",
            "NORTHERN_STEPPE": "北方草原控制空间",
            "NORTHWEST_FRONTIER": "西北边疆控制空间",
            "SHANDONG_HEBEI": "山东—河北主要控制带",
            "SOUTHWEST": "西南边疆主要控制空间",
        }
        control = row.get("b1_region_control") or {}
        start = control.get("start") if isinstance(control, Mapping) else {}
        end = control.get("end") if isinstance(control, Mapping) else {}
        if isinstance(start, Mapping) and isinstance(end, Mapping):
            expanded_names = [
                display_names.get(str(region_id), str(region_id))
                for region_id in sorted(set(start) | set(end))
                if float(end.get(region_id) or 0.0) > float(start.get(region_id) or 0.0)
            ]
            contracted_names = [
                display_names.get(str(region_id), str(region_id))
                for region_id in sorted(set(start) | set(end))
                if float(end.get(region_id) or 0.0) < float(start.get(region_id) or 0.0)
            ]
            expanded = "、".join(expanded_names)
            contracted = "、".join(contracted_names)
    if not expanded and not contracted:
        return "控制规模净变化区域：无"
    parts: list[str] = []
    if expanded:
        parts.append(f"控制规模增加区域：{expanded}")
    if contracted:
        parts.append(f"控制规模减少区域：{contracted}")
    return "；".join(parts)

def _b_control_reader_basis(row: Mapping[str, Any], axis_code: str, meaning: str) -> str:
    ledger = row.get("b1_region_adjudications") or []
    retained = _reader_region_list(ledger, "retained")
    contribution_type = str(row.get("control_contribution_type") or "")
    contribution_basis = {
        "NEW_RECOVERED_REBUILT": "本人信用来自新增、恢复或重建的控制成果",
        "SAVED_UNDER_MAJOR_PRESSURE": "本人信用来自重大失控压力下的保全或恢复，不按新增领土理解",
        "ROUTINE_MAINTENANCE": "本人信用仅来自既有控制的常规维护，不按新增领土理解",
        "INHERITED_ONLY": "交班存量只作客观背景；因仅属继承，不生成本人控制成果信用",
    }.get(contribution_type, "现有正式裁决未闭合本人可归责的正向控制成果")
    parts = [meaning, contribution_basis]
    primary = set(row.get("primary_control_package_refs") or [])
    matched = [
        item for item in ledger
        if item.get("object_id") in primary
        or primary.intersection(item.get("evidence_refs") or [])
    ]
    facts = [str(item.get("reason") or "").strip() for item in matched]
    facts = list(dict.fromkeys(fact for fact in facts if fact))
    if facts:
        parts.append("相关控制记录：" + "；".join(facts))
    elif retained:
        parts.append("交班空间背景：" + retained)
        if contribution_type != "INHERITED_ONLY":
            parts.append("本轴具体成果包理由尚未单列，空间存量不代替本人贡献依据")
    elif contribution_type != "INHERITED_ONLY":
        parts.append("本轴具体成果包理由尚未单列")
    return _markdown_cell(_reader_state_notation("；".join(parts) + "。"))

def _grade_from_rate(axis_code: str, rate: float) -> str:
    grade = 0 if rate < 30 else 1 if rate < 45 else 2 if rate < 60 else 3 if rate < 75 else 4 if rate < 90 else 5
    return f"{axis_code}-{grade}"

def _b_reader_grade(row: Mapping[str, Any], axis_code: str) -> str:
    axis = row["axes"][axis_code]
    adjudication = row["B80_adjudication"]
    original_grade = str(axis.get("grade") or axis_code)
    original_rate = float(axis.get("score_rate") or 0.0)
    effective_rate = float(adjudication[f"adjudicated_{axis_code}_rate"])
    effective_grade = _grade_from_rate(axis_code, effective_rate)
    if original_grade == effective_grade and original_rate == effective_rate:
        return f"{original_grade}（{effective_rate:.0f}%）"
    basis = str(adjudication.get("consistency_basis") or "跨项一致性裁决调整").rstrip("；。")
    return _markdown_cell(
        f"原始{original_grade}（{original_rate:.0f}%），有效{effective_grade}（{effective_rate:.0f}%）；调整依据：{basis}"
    )

def _b_reader_basis(row: Mapping[str, Any], axis_code: str) -> str:
    axis = row["axes"][axis_code]
    text = str(axis.get("reason") or axis.get("rationale") or "").strip()
    adjudication = row.get("B80_adjudication") or {}
    original_rate = float(axis.get("score_rate") or 0.0)
    effective_rate = float(adjudication.get(f"adjudicated_{axis_code}_rate") or 0.0)
    adjusted = original_rate != effective_rate
    generic = (
        f"裁为{axis_code}-" in text
        or "按本人统治窗口" in text
        or "安全结果={" in text
        or "只消费本窗口实际保全、恢复或新形成的控制成果" in text
        or "只消费本窗口实际恢复、保全或新形成的控制成果" in text
        or "只读取本人交班时的闭合状态" in text
        or "仅按本人交班时的制度、驻防、和议或防务闭合度裁定" in text
        or "现有材料未闭合本人可计分的新增、恢复、救危保全或维护控制成果" in text
        or not text
    )
    if text.startswith(("规模与控制强度：", "规模与控制强度:")):
        text = text.split("：", 1)[-1].split(":", 1)[-1].strip()
    if not generic:
        prefix = "原始档位依据（已被上述调整覆盖）：" if adjusted else ""
        return _markdown_cell(_reader_state_notation(prefix + text))
    match = re.search(r"-(\d+)$", str(axis.get("grade") or ""))
    grade = int(match.group(1)) if match else -1
    meaning = B_GRADE_MEANINGS[axis_code].get(grade, "按该轴正式合同档义落档")
    if row.get("b1_region_adjudications") is not None:
        basis = _b_control_reader_basis(row, axis_code, meaning)
        return (
            _markdown_cell("原始档位依据（已被上述调整覆盖）：" + basis)
            if adjusted
            else basis
        )
    b1 = row["axes"]["B1"]
    row_basis = str(row.get("rationale") or "").strip()
    row_basis_is_generic = any(
        marker in row_basis
        for marker in (
            "按本人统治窗口", "安全结果={", "按明朝主体阶段卡",
            "战略链可支持A1/A2",
        )
    )
    control_basis = row_basis if row_basis and not row_basis_is_generic else str(
        b1.get("reason") or b1.get("rationale") or ""
    ).strip()
    for prefix in ("规模与控制强度：", "规模与控制强度:"):
        if control_basis.startswith(prefix):
            control_basis = control_basis[len(prefix):].strip()
    if not control_basis:
        control_basis = str(row.get("rationale") or "").strip()
    if axis_code == "B2":
        detail = f"对应成果边界：{control_basis}" if control_basis else ""
    else:
        control = row.get("b1_control_equivalents") or {}
        end = control.get("end")
        end_text = f"交班控制量{float(end):g}；" if end is not None else ""
        detail = f"{end_text}交班成果边界：{control_basis}" if control_basis else end_text.rstrip("；")
    basis = f"{meaning}；{detail}" if detail else meaning
    if adjusted:
        basis = "原始档位依据（已被上述调整覆盖）：" + basis
    return _markdown_cell(_reader_state_notation(basis))

def _reader_state_notation(text: str) -> str:
    text = re.sub(
        r"(?<![A-Za-z0-9_])(A1|A2)S([0-5])(?![A-Za-z0-9_])",
        lambda match: f"{match.group(1)}-{match.group(2)}档",
        text,
    )
    return re.sub(
        r"(?<![A-Za-z0-9_])S([0-5])(?![A-Za-z0-9_])",
        lambda match: f"{match.group(1)}档",
        text,
    )

def _ab_settlement_basis(row: Mapping[str, Any]) -> str:
    axes = row["axes"]
    grades = "、".join(str(axes[key].get("grade") or key) for key in ("B1", "B2", "B4"))
    prefix = f"{_trajectory_label(axes['A1'], 'A1')}，{_trajectory_label(axes['A2'], 'A2')}；{grades}。"
    rationale = str(row.get("rationale") or "").strip()
    generic = rationale.startswith(
        ("分区实审已完成", "按32卷主体阶段卡", "按97卷主体阶段卡")
    )
    if not rationale or generic:
        reasons = [
            str(axes[key].get("reason") or "").strip()
            for key in ("A1", "A2", "B1", "B2", "B4")
        ]
        rationale = _joined_reasons(reason for reason in reasons if reason)
        if not rationale:
            rationale = (
                f"威胁证据{len(row.get('primary_threat_refs') or [])}项、"
                f"控制证据{len(row.get('primary_control_package_refs') or [])}项；"
                f"边界阶段{row.get('boundary_stage_review_status') or '已复核'}。"
            )
    return _markdown_cell(prefix + rationale)

def _render_formal_markdown(
    kind: str, records: Sequence[Mapping[str, Any]], *,
    credit_rows: Mapping[str, Mapping[str, Any]] | None = None,
    c_review_context=None,
) -> str:
    human_status = {
        "NOT_APPLICABLE": "不适用",
        "NOT_APPLICABLE_NO_SYSTEM_STRESS": "无体系压力任务",
        "NONE": "无额外守成难度",
        "TESTED": "经受压力检验",
        "SEVERE": "严重守成",
        "HISTORIC": "历史级守成",
        "HIGH": "高位",
        "MID": "中位",
        "LOW": "低位",
    }

    def human_label(value: object) -> str:
        text = str(value)
        return human_status.get(text, text)

    if kind not in {"AB", "C"}:
        raise ValueError("正式分项Markdown仅支持AB或C；D由军事行动成本和收益登记专用renderer生成")
    current_ab = kind == "AB" and all("AB200_score_points" in row for row in records)
    score_key = "AB200_score_points" if current_ab else {"AB": "AB_atomic_diagnostic_points", "C": "C_score_points"}[kind]
    ranked = _competition_ranked_records(records, score_key)
    unscored = [row for row in records if row.get(score_key) is None]
    values = [float(row[score_key]) for _, row in ranked]
    scope_label = (
        "秦至清"
        if any(str(row.get("polity", "")) in {"清", "后金（清前身）"} for row in records)
        else "秦至明"
        if any(str(row.get("ruler_id", "")).startswith("RULER-MING-") for row in records)
        else "秦至元"
        if any(str(row.get("ruler_id", "")).startswith("RULER-YUAN-") for row in records)
        else "秦至南宋"
        if any(str(row.get("ruler_id", "")).startswith("RULER-SS-") for row in records)
        else "秦至北宋"
    )
    definitions = {
        "AB": {
            "title": f"# {scope_label}第三项A/B国防安全正式结算",
            "rule": "[A/B规则与结算合同](../../../../分项规则/第三项军事与边疆净收益/国防安全/00-规则与结算合同.md)",
            "description": "A战略安全结果120分与B边疆控制结果80分" if current_ab else "A战略安全收益80分与B边疆控制净收益80分",
        },
        "C": {
            "title": f"# {scope_label}第三项C军事体系有效性正式结算",
            "rule": "[C规则与计分合同](../../../../分项规则/第三项军事与边疆净收益/军事体系有效性/00-规则与计分合同.md)",
            "description": "C军事体系有效性50分",
        },
    }
    definition = definitions[kind]
    range_text = (
        f"得分范围{min(values):.1f}—{max(values):.1f}"
        if values else "暂无已计分主体"
    )
    display_note = (
        "当前总值统一显示两位小数，原子率显示整数百分比"
        if current_ab
        else "所有分值统一显示一位小数"
    )
    lines = [
        definition["title"],
        "",
        f"规则见{definition['rule']}。本表按{definition['description']}正式值从高到低排列。",
        "",
        f"共{len(ranked)}位评价主体已计分，{range_text}；另有{len(unscored)}位保持未结算。同分并列，后一名次按竞赛排名顺延；{display_note}。",
        "",
    ]
    if kind == "AB":
        if current_ab:
            lines += [
                "A1/A2与B1/B2/B4原子档用于解释；当前计分只读取A120和非线性合成的B80。成本尚未在本表折算，最终分见第三项总榜。",
                "",
                "| 排名 | 皇帝 | 政权 | 在位 | A客观锚 | A正向信用 | A120 | B1率 | B2率 | B4率 | B80 | A+B/200 |",
                "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        else:
            lines += [
                "| 排名 | 皇帝 | 政权 | 在位 | A1/40 | A2/40 | A/80 | B1/25 | B2/30 | B4/25 | B/80 | A/B总分/160 |",
                "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        for rank, row in ranked:
            axes = row["axes"]
            if current_ab:
                b_current = row["B80_adjudication"]
                lines.append(
                    f"| {rank} | {row['ruler_name']} | {row['polity']} | {_reign_range_label(row['reign_range'])} | "
                    f"{float(row['A120_non_cost_anchor_points']):.2f} | {float(row['A120_positive_result_credit_points']):.2f} | "
                    f"{float(row['A120_score_points']):.2f} | {float(b_current['adjudicated_B1_rate']):.0f}% | "
                    f"{float(b_current['adjudicated_B2_rate']):.0f}% | {float(b_current['adjudicated_B4_rate']):.0f}% | "
                    f"{float(row['B80_score_points']):.2f} | {float(row[score_key]):.2f} |"
                )
            else:
                a1 = float(axes["A1"]["axis_points"])
                a2 = float(axes["A2"]["axis_points"])
                b1 = float(axes["B1"]["axis_points"])
                b2 = float(axes["B2"]["axis_points"])
                b4 = float(axes["B4"]["axis_points"])
                lines.append(
                    f"| {rank} | {row['ruler_name']} | {row['polity']} | {_reign_range_label(row['reign_range'])} | "
                    f"{a1:.1f} | {a2:.1f} | {a1 + a2:.1f} | {b1:.1f} | {b2:.1f} | "
                    f"{b4:.1f} | {b1 + b2 + b4:.1f} | {float(row[score_key]):.1f} |"
                )
    else:
        lines += [
            "| 排名 | 皇帝 | 政权 | 在位 | C1 | C2 | C3 | C总体 | 得分率 | C/50 | 当前战略链 | 父周期证据 |",
            "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for rank, row in ranked:
            lines.append(
                f"| {rank} | {row['ruler_name']} | {row['polity']} | {_reign_range_label(row['reign_range'])} | "
                f"{human_label(row['combat_delivery_grade'])} | {human_label(row['operational_sustainability_cap'])} | "
                f"{human_label(row['system_reliability_cap'])} | {row['final_grade']} | "
                f"{float(row['C_score_rate']):.1f}% | {float(row[score_key]):.1f} | "
                f"{int(row.get('strategy_chain_count') or 0)} | {int(row.get('independent_task_count') or 0)} |"
            )
    lines += ["", "## 逐人结算依据", ""]
    if current_ab:
        lines += [
            "先看五轴结果，再读各轴事实与归责。A轴计分行均为最终分数；B轴百分比用于合成B总分，不能直接相加。逐档归责、去重边界及来源可展开查看。",
            "",
        ]
    for rank, row in ranked:
        score_text = f"{float(row[score_key]):.2f}" if current_ab else f"{float(row[score_key]):.1f}"
        lines += [f"### {rank}. {row['ruler_name']}（{score_text}）", ""]
        if kind == "AB":
            if current_ab:
                from emperor_v4.evaluation.third_item_ab_reading import render_person
                lines += render_person(
                    row, a_readings=credit_rows[row['ruler_id']]['axes'],
                    b_basis=_b_reader_basis, b_grade=_b_reader_grade,
                    b_regions=_b1_region_change_reader_text,
                    depth_lines=render_control_depth_packages,
                )
            else:
                lines += [f"- 裁决：{_ab_settlement_basis(row)}", ""]
            continue
        if row.get('public_reading'):
            from emperor_v4.evaluation.third_item_c_public import markdown as c_public_markdown
            lines += [c_public_markdown(row, context=c_review_context), '']
            continue
        if row.get("final_grade") == "C-N":
            lines += [
                f"- 裁决：{_markdown_cell(_joined_reasons(row.get('cap_reasons') or []))}",
                "",
            ]
            continue
        if row.get("system_observation_status") == "INHERITED_UNTESTED":
            lines += ["- 观察状态：继承体系能力；未受任内实战检验，总档上限C3。", ""]
        c_basis = _joined_reasons(row.get("cap_reasons") or []) or "按C1、C2、C3短板门槛与体系压力父任务暴露定档。"
        position = row.get("C_score_within_band_adjudication") or {}
        position_line = (
            f"- 档内位置：{human_label(position['position'])}；{_markdown_cell(str(position['reason']))}"
            if position else
            ("- 档内位置：无本人战果，按中性位置与三轴差值取高。"
             if row.get("system_observation_status") == "INHERITED_UNTESTED" else
             f"- 档内位置：按三轴差值计算，位置系数{float(row.get('C_score_band_position', 0)):.2f}。")
        )
        lines += [
            position_line,
            f"- 裁决：{_markdown_cell(c_basis)}",
            "",
        ]
    if kind == 'C' and unscored:
        from emperor_v4.evaluation.third_item_c_public import markdown as c_public_markdown
        lines += ['## 必要证据不足，暂不计分', '']
        for row in unscored:
            lines += [f"### {row['ruler_name']}（暂不计分）", '']
            if row.get('public_reading'):
                lines += [c_public_markdown(row, context=c_review_context), '']
            else:
                lines += [_markdown_cell(_joined_reasons(row.get('cap_reasons') or [])), '']
    return "\n".join(lines).rstrip() + "\n"
