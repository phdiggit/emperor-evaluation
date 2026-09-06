from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from emperor_v4.evaluation.first_item_a_registry import load_qin_qing_first_item_roster
from emperor_v4.evaluation.battle_registry_store import load_battle_registry
from emperor_v4.evaluation.talent_registry_store import load_talent_registry


ELIGIBLE_STATUS = "ELIGIBLE_DYNASTY_FOUNDER"
EXCLUDED_STATUS = "NOT_APPLICABLE_NON_FOUNDER"


def build_first_item_b_registry(
    *,
    adjudications: Mapping[str, Any],
    roster: Mapping[str, Any],
    battle_registry: Mapping[str, Any] | None = None,
    talent_registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if adjudications.get("schema_version") != "first-item-b-team-contribution-adjudications-v7":
        raise ValueError("第一项B团队贡献输入schema_version不正确")
    if adjudications.get("status") != "CURRENT":
        raise ValueError("第一项B团队贡献输入不是当前值")
    b1_max = float(adjudications.get("B1_max") or 0)
    b2_max = float(adjudications.get("B2_max") or 0)
    if (b1_max, b2_max) != (30.0, 30.0):
        raise ValueError("第一项B分项上限不正确")
    outcome_points = {
        str(level): float(points)
        for level, points in dict(adjudications.get("outcome_level_points") or {}).items()
    }
    if outcome_points != {
        "SUPPORTING": 4.0, "IMPORTANT": 8.0, "MAJOR": 13.0,
        "DECISIVE": 17.0, "FOUNDATION_PILLAR": 20.0,
    }:
        raise ValueError("第一项B成果量级映射不正确")
    contribution_credits = {
        str(level): float(value)
        for level, value in dict(adjudications.get("contribution_credit") or {}).items()
    }
    if contribution_credits != {"SUPPORT": 0.65, "JOINT": 0.85, "PRIMARY": 1.0}:
        raise ValueError("第一项B团队贡献信用映射不正确")
    completion_factors = {
        str(level): float(value)
        for level, value in dict(adjudications.get("completion_factor") or {}).items()
    }
    if completion_factors != {"PARTIAL": 0.5, "SUBSTANTIAL": 0.8, "COMPLETE": 1.0}:
        raise ValueError("第一项B完成度映射不正确")
    outcome_position_weights = [
        float(value) for value in adjudications.get("outcome_position_weights") or ()
    ]
    if outcome_position_weights != [1.0, 0.5]:
        raise ValueError("第一项B成果组合权重不正确")
    axis_points = {
        int(level): float(points)
        for level, points in dict(adjudications.get("organization_axis_level_points") or {}).items()
    }
    if axis_points != {0: 0.0, 1: 2.0, 2: 4.0, 3: 6.0, 4: 8.0, 5: 10.0}:
        raise ValueError("第一项B组织轴映射不正确")
    axis_contract = dict(adjudications.get("organization_axis_contract") or {})
    axis_names = (
        "parallel_execution",
        "continuity_resilience",
        "heterogeneous_integration",
    )
    if tuple(axis_contract) != axis_names or any(
        not str(axis_contract[name]).strip() for name in axis_names
    ):
        raise ValueError("第一项B组织轴合同不完整")

    roster_rows = list(roster.get("records") or ())
    roster_by_name = {str(row["ruler_name"]): row for row in roster_rows}
    if len(roster_by_name) != len(roster_rows):
        raise ValueError("第一项B名册存在重复ruler_name")
    input_rows = list(adjudications.get("records") or ())
    input_by_name = {str(row["ruler_name"]): row for row in input_rows}
    if len(input_by_name) != len(input_rows):
        raise ValueError("第一项B裁决存在重复ruler_name")
    unknown = set(input_by_name) - set(roster_by_name)
    if unknown:
        raise ValueError(f"第一项B包含名册外对象: {sorted(unknown)}")

    records: list[dict[str, Any]] = []
    for ruler_name, roster_row in roster_by_name.items():
        common = {
            "ruler_id": roster_row.get("ruler_id"),
            "ruler_name": ruler_name,
            "polity": roster_row.get("polity"),
            "reign_range": roster_row.get("reign_range"),
        }
        source = input_by_name.get(ruler_name)
        if source is None:
            records.append({
                **common,
                "scope_status": EXCLUDED_STATUS,
                "score_applicable": False,
                "B1": None,
                "B2": None,
                "B_score_points": None,
                "canonical_rank": None,
                "basis": "普通继承、守成扩张或未在本名册所属政权中承担奠基责任",
            })
            continue
        if not str(source.get("basis") or "").strip():
            raise ValueError(f"第一项B缺少总体裁决依据: {ruler_name}")
        adjudication_status = str(
            source.get("adjudication_status") or "CURRENT_ACCEPTED"
        )
        if adjudication_status not in {
            "CURRENT_ACCEPTED",
            "TRIAL_EVIDENCE_LOWER_BOUND",
        }:
            raise ValueError(f"第一项B裁决状态非法: {ruler_name}")
        source_chains = list(source.get("outcome_evidence") or ())
        if not source_chains:
            raise ValueError(f"第一项B缺少团队成果证据: {ruler_name}")
        chains: list[dict[str, Any]] = []
        seen_refs: set[str] = set()
        for source_chain in source_chains:
            if not isinstance(source_chain, dict):
                raise ValueError(f"第一项B成果证据格式非法: {ruler_name}")
            outcome_ref = str(source_chain.get("outcome_ref") or "").strip()
            chain_name = str(source_chain.get("outcome") or "").strip()
            actors = [
                str(actor).strip() for actor in source_chain.get("actors") or ()
                if str(actor).strip()
            ]
            outcome_level = str(source_chain.get("outcome_level") or "").strip()
            responsibility = str(source_chain.get("non_founder_responsibility") or "").strip()
            completion = str(source_chain.get("completion") or "").strip()
            if not outcome_ref or outcome_ref in seen_refs or not chain_name:
                raise ValueError(f"第一项B成果证据ref或名称缺失、重复: {ruler_name}")
            if not actors or ruler_name in actors:
                raise ValueError(f"第一项B成果证据必须由非本人承担: {ruler_name}/{chain_name}")
            if outcome_level not in outcome_points:
                raise ValueError(f"第一项B成果量级非法: {ruler_name}/{chain_name}")
            if responsibility not in contribution_credits:
                raise ValueError(f"第一项B团队责任非法: {ruler_name}/{chain_name}")
            if completion not in completion_factors:
                raise ValueError(f"第一项B完成度非法: {ruler_name}/{chain_name}")
            seen_refs.add(outcome_ref)
            chains.append({
                "outcome_ref": outcome_ref,
                "chain": chain_name,
                "actors": actors,
                "outcome_level": outcome_level,
                "non_founder_responsibility": responsibility,
                "completion": completion,
                "source_refs": [
                    str(ref).strip() for ref in source_chain.get("source_refs") or ()
                    if str(ref).strip()
                ],
            })
        scoring_refs = [str(value) for value in source.get("scoring_outcome_refs") or ()]
        if not 1 <= len(scoring_refs) <= 2 or len(scoring_refs) != len(set(scoring_refs)):
            raise ValueError(f"第一项B计分成果组合数量或ref重复: {ruler_name}")
        chain_by_ref = {chain["outcome_ref"]: chain for chain in chains}
        if any(ref not in chain_by_ref for ref in scoring_refs):
            raise ValueError(f"第一项B计分成果ref不存在: {ruler_name}")
        scoring_outcomes = []
        for position, (ref, position_weight) in enumerate(
            zip(scoring_refs, outcome_position_weights), start=1
        ):
            chain = chain_by_ref[ref]
            if not chain["source_refs"]:
                raise ValueError(f"第一项B计分成果缺少来源锚: {ruler_name}/{ref}")
            base_value = (
                outcome_points[chain["outcome_level"]]
                * contribution_credits[chain["non_founder_responsibility"]]
                * completion_factors[chain["completion"]]
            )
            scoring_outcomes.append({
                **chain,
                "position": position,
                "outcome_base_points": outcome_points[chain["outcome_level"]],
                "contribution_credit": contribution_credits[chain["non_founder_responsibility"]],
                "completion_factor": completion_factors[chain["completion"]],
                "position_weight": position_weight,
                "points": round(base_value * position_weight, 2),
            })
        b1_raw = round(sum(item["points"] for item in scoring_outcomes), 2)
        b1_points = round(min(b1_max, b1_raw), 1)
        source_axes = dict(source.get("organization_axes") or {})
        if tuple(source_axes) != axis_names:
            raise ValueError(f"第一项B组织轴不完整或顺序错误: {ruler_name}")
        axes = []
        for axis_name in axis_names:
            level = int(source_axes[axis_name])
            if level not in axis_points:
                raise ValueError(f"第一项B组织轴档位非法: {ruler_name}/{axis_name}")
            axes.append({
                "axis": axis_name,
                "level": level,
                "points": axis_points[level],
                "contract": axis_contract[axis_name],
            })
        b2_points = round(sum(axis["points"] for axis in axes), 1)
        records.append({
            **common,
            "scope_status": ELIGIBLE_STATUS,
            "score_applicable": True,
            "B1": {
                "name": "团队关键成果组合",
                "max_points": b1_max,
                "raw_points": b1_raw,
                "cap_applied": b1_raw > b1_max,
                "points": b1_points,
                "scoring_outcomes": scoring_outcomes,
                "outcome_evidence": chains,
            },
            "B2": {
                "name": "创业团队组织化能力",
                "max_points": b2_max,
                "points": b2_points,
                "organization_axes": axes,
            },
            "B_score_points": round(b1_points + b2_points, 1),
            "canonical_rank": None,
            "adjudication_status": adjudication_status,
            "evidence_lower_bound": adjudication_status != "CURRENT_ACCEPTED",
            "basis": source["basis"],
            "limitations": list(source.get("limitations") or ()),
        })

    eligible = sorted(
        (row for row in records if row["score_applicable"]),
        key=lambda row: (-float(row["B_score_points"]), str(row["ruler_name"])),
    )
    previous_score = None
    current_rank = 0
    for position, row in enumerate(eligible, start=1):
        if row["B_score_points"] != previous_score:
            current_rank = position
            previous_score = row["B_score_points"]
        row["canonical_rank"] = current_rank
    excluded = sorted(
        (row for row in records if not row["score_applicable"]),
        key=lambda row: str(row["ruler_name"]),
    )
    records = eligible + excluded
    trial_count = sum(
        row["adjudication_status"] == "TRIAL_EVIDENCE_LOWER_BOUND"
        for row in eligible
    )
    return {
        "schema_version": "first-item-b-registry-v4",
        "canonical_status": (
            "CURRENT" if not trial_count else "CURRENT_TRIAL_WITH_PENDING_FOUNDERS"
        ),
        "item": "第一项B政治整合能力",
        "max_points": 60,
        "method": {
            "eligibility_gate": "第一项只评价王朝或独立政权奠基人",
            "B1": "取非本人团队最强的两个不重叠成果群，按成果量级、团队责任和完成度结算；第一成果全值、第二成果50%，30分封顶",
            "B2": "并行执行、连续替补、异质整合三个组织轴各0至5级、各10分，三轴合计30分",
            "multi_role_boundary": "一人跨多个真实结果可以形成两个成果群；多人参与同一结果仍只形成一个成果群，均不按名字数量换分",
            "founder_boundary": "B1评价团队已兑现成果的绝对质量，不以团队占比反向扣减奠基人本人贡献；本人C高低不改变同一团队成果的B1价值",
            "failure_boundary": "团队责任链发生失败时降低该链完成度；已经在A或C结算的结果损失不在B重复扣分",
            "military_profile_boundary": "最新军事人才档只作身份、战役缺漏和明显越界复核；人物名望、全生涯档位和贡献者名单长度均不进入B分数",
        },
        "source_refs": {
            "adjudications": "config/first-item/first-item-b-team-contribution-adjudications.json",
            "roster": "秦至清总名册与第一项A奠基人元数据",
            "battle_registry": "docs/公共成果/军事/01-战役登记.json",
            "talent_registry": "docs/公共成果/军事/02-武将人才等级.json",
        },
        "record_count": len(records),
        "eligible_count": len(eligible),
        "excluded_count": len(excluded),
        "score_ready_count": len(records),
        "unresolved_count": sum(
            row["adjudication_status"] != "CURRENT_ACCEPTED" for row in eligible
        ),
        "trial_count": trial_count,
        "anchored_outcome_count": sum(
            bool(chain["source_refs"])
            for row in eligible for chain in row["B1"]["outcome_evidence"]
        ),
        "unanchored_context_outcome_count": sum(
            not chain["source_refs"]
            for row in eligible for chain in row["B1"]["outcome_evidence"]
        ),
        "unanchored_scoring_outcome_count": sum(
            not chain["source_refs"]
            for row in eligible for chain in row["B1"]["scoring_outcomes"]
        ),
        "scope_status_counts": dict(sorted(Counter(row["scope_status"] for row in records).items())),
        "formal_score_write": False,
        "database_write": False,
        "ranking_write": False,
        "score_range": {
            "minimum": min(row["B_score_points"] for row in eligible),
            "maximum": max(row["B_score_points"] for row in eligible),
        },
        "records": records,
    }


def render_first_item_b_registry_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# 第一项B政治整合能力结算",
        "",
        "> B1结算非奠基人团队最强的两个不重叠成果群；本人军事贡献不构成团队成果的反向扣分。",
        "> B2只评价并行执行、连续替补与异质整合三项组织能力，不再制作前四名贡献者榜单。",
        "",
        f"- 名册对象：{payload['record_count']} 人",
        f"- 奠基者完整结算：{payload['eligible_count']} 人",
        f"- 非奠基者不适用：{payload['excluded_count']} 人",
        "",
        "| B项序 | 对象 | 政权 | 团队成果B1/30 | 组织能力B2/30 | B/60 |",
        "|---:|---|---|---:|---:|---:|",
    ]
    eligible = [row for row in payload["records"] if row["score_applicable"]]
    for row in eligible:
        lines.append(
            f"| {row['canonical_rank']} | {row['ruler_name']} | {row.get('polity') or '—'} | "
            f"{row['B1']['points']:g} | {row['B2']['points']:g} | {row['B_score_points']:g} |"
        )
    lines.extend(["", "## 逐人结算依据", ""])
    for row in eligible:
        lines.extend([f"### {row['canonical_rank']}. {row['ruler_name']}", ""])
        for chain in row["B1"]["outcome_evidence"]:
            actors = "、".join(chain["actors"])
            refs = "；".join(chain["source_refs"]) if chain["source_refs"] else "待补（不参与计分）"
            lines.append(
                f"- 成果证据：{chain['chain']}（{chain['outcome_level']} / "
                f"{chain['non_founder_responsibility']} / {chain['completion']}），承担者：{actors}；来源：{refs}。"
            )
        scoring_text = "；".join(
            f"{item['chain']} {item['outcome_level']}×{item['non_founder_responsibility']}×"
            f"{item['completion']}×{item['position_weight']:g}={item['points']:g}"
            for item in row["B1"]["scoring_outcomes"]
        )
        axis_text = "；".join(
            f"{axis['axis']} L{axis['level']}={axis['points']:g}"
            for axis in row["B2"]["organization_axes"]
        )
        lines.extend([
            f"- B1计分成果：{scoring_text}；合计{row['B1']['points']:g}/30。",
            f"- B2：{axis_text}，合计{row['B2']['points']:g}/30。",
            f"- 裁决：{row['basis']}",
        ])
        if row["limitations"]:
            lines.append("- 限制：" + "；".join(row["limitations"]) + "。")
        lines.append("")
    excluded = [row for row in payload["records"] if not row["score_applicable"]]
    lines.extend([
        "## 非奠基者不适用", "", "、".join(row["ruler_name"] for row in excluded) + "。", "",
    ])
    return "\n".join(lines)


def write_first_item_b_registry(workspace_root: Path) -> dict[str, Path]:
    def load(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    payload = build_first_item_b_registry(
        adjudications=load(workspace_root / "config/first-item/first-item-b-team-contribution-adjudications.json"),
        roster=load_qin_qing_first_item_roster(
            workspace_root,
            load(workspace_root / "config/first-item/first-item-a-strategic-efficiency-inputs.json"),
            include_current_pending_founders=True,
        ),
        battle_registry=load_battle_registry(
            workspace_root / "docs/公共成果/军事/01-战役登记.json"
        ),
        talent_registry=load_talent_registry(
            workspace_root / "docs/公共成果/军事/02-武将人才等级.json"
        ),
    )
    output_dir = workspace_root / "docs/评分结算/第一项政权奠基与统一贡献及能力/政治整合能力"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "01-第一项B政治整合能力结算.json"
    markdown_path = output_dir / "01-第一项B政治整合能力结算.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_first_item_b_registry_markdown(payload), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}
