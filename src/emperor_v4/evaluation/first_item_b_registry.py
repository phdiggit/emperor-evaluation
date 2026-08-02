from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


ELIGIBLE_STATUS = "ELIGIBLE_DYNASTY_FOUNDER"
EXCLUDED_STATUS = "NOT_APPLICABLE_NON_FOUNDER"


def build_first_item_b_registry(
    *, adjudications: Mapping[str, Any], roster: Mapping[str, Any]
) -> dict[str, Any]:
    if adjudications.get("schema_version") != "first-item-b-team-contribution-adjudications-v3":
        raise ValueError("第一项B团队贡献输入schema_version不正确")
    if adjudications.get("status") != "CURRENT":
        raise ValueError("第一项B团队贡献输入不是当前值")
    outcome_points = {
        str(level): float(points)
        for level, points in dict(adjudications.get("outcome_level_points") or {}).items()
    }
    contribution_credits = {
        str(level): float(points)
        for level, points in dict(adjudications.get("contribution_credit") or {}).items()
    }
    completion_factors = {
        str(level): float(points)
        for level, points in dict(adjudications.get("completion_factor") or {}).items()
    }
    if outcome_points != {
        "SUPPORTING": 2.0, "IMPORTANT": 4.0, "MAJOR": 6.0,
        "DECISIVE": 8.0, "FOUNDATION_PILLAR": 10.0,
    }:
        raise ValueError("第一项B成果量级映射不正确")
    if contribution_credits != {"SUPPORT": 0.75, "JOINT": 0.9, "PRIMARY": 1.0}:
        raise ValueError("第一项B团队贡献信用映射不正确")
    if completion_factors != {"PARTIAL": 0.5, "SUBSTANTIAL": 0.8, "COMPLETE": 1.0}:
        raise ValueError("第一项B完成度映射不正确")
    b1_scale = float(adjudications.get("B1_scale") or 0)
    b1_cap = float(adjudications.get("B1_cap") or 0)
    b2_max = float(adjudications.get("B2_max") or 0)
    if (b1_scale, b1_cap, b2_max) != (0.75, 30.0, 30.0):
        raise ValueError("第一项B分项缩放或上限不正确")
    profile_points = {
        str(level): float(points)
        for level, points in dict(adjudications.get("profile_level_points") or {}).items()
    }
    if profile_points != {
        "SUPPORTING": 3.0, "IMPORTANT_SPECIALIST": 6.0,
        "MAJOR_INDEPENDENT": 9.0, "TOP_DECISIVE": 12.0,
        "PILLAR_MULTIDOMAIN": 15.0,
    }:
        raise ValueError("第一项B人才贡献档位映射不正确")
    profile_weights = [float(value) for value in adjudications.get("profile_position_weights") or ()]
    if profile_weights != [1.0, 0.7, 0.5, 0.3]:
        raise ValueError("第一项B人才贡献位次权重不正确")
    profiles_by_name = dict(adjudications.get("contributor_profiles") or {})

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
    if set(profiles_by_name) != set(input_by_name):
        raise ValueError("第一项B人才贡献画像必须与奠基者裁决一一对应")

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
                "trial_rank": None,
                "basis": "普通继承、守成扩张或未在本名册所属政权中承担奠基责任",
            })
            continue
        if not str(source.get("basis") or "").strip():
            raise ValueError(f"第一项B缺少总体裁决依据: {ruler_name}")
        if "team_project_share" in source:
            raise ValueError(f"第一项B不得保留已废弃的非本人承载率: {ruler_name}")
        source_chains = list(source.get("contribution_chains") or ())
        if not source_chains:
            raise ValueError(f"第一项B缺少团队成果责任链: {ruler_name}")
        chains = []
        seen_names: set[str] = set()
        for source_chain in source_chains:
            if not isinstance(source_chain, list) or len(source_chain) != 5:
                raise ValueError(f"第一项B成果责任链格式非法: {ruler_name}")
            chain_name, actors, outcome_level, responsibility, completion = source_chain
            chain_name = str(chain_name).strip()
            actors = [str(actor).strip() for actor in actors if str(actor).strip()]
            outcome_level = str(outcome_level)
            responsibility = str(responsibility)
            completion = str(completion)
            if not chain_name or chain_name in seen_names:
                raise ValueError(f"第一项B成果责任链名称缺失或重复: {ruler_name}")
            if not actors or ruler_name in actors:
                raise ValueError(f"第一项B成果责任链必须由非本人承担: {ruler_name}/{chain_name}")
            if outcome_level not in outcome_points:
                raise ValueError(f"第一项B成果量级非法: {ruler_name}/{chain_name}")
            if responsibility not in contribution_credits:
                raise ValueError(f"第一项B责任份额非法: {ruler_name}/{chain_name}")
            if completion not in completion_factors:
                raise ValueError(f"第一项B完成度非法: {ruler_name}/{chain_name}")
            seen_names.add(chain_name)
            points = (
                outcome_points[outcome_level]
                * contribution_credits[responsibility]
                * completion_factors[completion]
                * b1_scale
            )
            chains.append({
                "chain": chain_name,
                "actors": actors,
                "outcome_level": outcome_level,
                "outcome_base_points": outcome_points[outcome_level],
                "non_founder_responsibility": responsibility,
                "contribution_credit": contribution_credits[responsibility],
                "completion": completion,
                "completion_factor": completion_factors[completion],
                "points": round(points, 2),
            })
        raw_contribution = round(sum(chain["points"] for chain in chains), 2)
        b1_points = round(min(b1_cap, raw_contribution), 1)
        source_profiles = list(profiles_by_name[ruler_name])
        if not 1 <= len(source_profiles) <= len(profile_weights):
            raise ValueError(f"第一项B人才贡献画像数量非法: {ruler_name}")
        parsed_profiles = []
        seen_contributors: set[str] = set()
        for source_profile in source_profiles:
            if not isinstance(source_profile, list) or len(source_profile) != 2:
                raise ValueError(f"第一项B人才贡献画像格式非法: {ruler_name}")
            contributor, level = (str(value).strip() for value in source_profile)
            if not contributor or contributor in seen_contributors or contributor == ruler_name:
                raise ValueError(f"第一项B人才贡献画像人物非法: {ruler_name}")
            if level not in profile_points:
                raise ValueError(f"第一项B人才贡献档位非法: {ruler_name}/{contributor}")
            seen_contributors.add(contributor)
            parsed_profiles.append((contributor, level, profile_points[level]))
        parsed_profiles.sort(key=lambda item: (-item[2], item[0]))
        profiles = []
        for position, ((contributor, level, base_points), weight) in enumerate(
            zip(parsed_profiles, profile_weights), start=1
        ):
            profiles.append({
                "position": position,
                "contributor": contributor,
                "level": level,
                "base_points": base_points,
                "position_weight": weight,
                "points": round(base_points * weight, 2),
            })
        b2_raw = round(sum(profile["points"] for profile in profiles), 2)
        b2_points = round(min(b2_max, b2_raw), 1)
        records.append({
            **common,
            "scope_status": ELIGIBLE_STATUS,
            "score_applicable": True,
            "B1": {
                "name": "非本人团队关键成果贡献",
                "max_points": b1_cap,
                "raw_points": raw_contribution,
                "cap_applied": raw_contribution > b1_cap,
                "points": b1_points,
                "contribution_chains": chains,
            },
            "B2": {
                "name": "开国人才贡献质量",
                "max_points": b2_max,
                "raw_points": b2_raw,
                "cap_applied": b2_raw > b2_max,
                "points": b2_points,
                "contributor_profiles": profiles,
            },
            "B_score_points": round(b1_points + b2_points, 1),
            "trial_rank": None,
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
        row["trial_rank"] = current_rank
    excluded = sorted(
        (row for row in records if not row["score_applicable"]),
        key=lambda row: str(row["ruler_name"]),
    )
    records = eligible + excluded
    return {
        "schema_version": "first-item-b-registry-v1",
        "canonical_status": "CURRENT",
        "item": "第一项B政治整合能力",
        "max_points": 60,
        "method": {
            "eligibility_gate": "第一项只评价王朝或独立政权奠基人",
            "B1": "逐条结算不重复的非本人开国成果链：成果量级乘团队贡献信用乘完成度再按0.75缩放，累计后30分封顶",
            "B2": "按创业窗口实际成果裁定贡献者个人档位，前四位依次按1、0.7、0.5、0.3衰减，30分封顶",
            "multi_role_boundary": "同一成员可以凭不同且不重叠的成果链累计，一人多职不按人数折扣",
            "founder_boundary": "奠基人本人不进入团队人才画像；但其参与同一结果不反向压低成员已经形成的实际贡献",
            "failure_boundary": "团队责任链发生失败时降低该链完成度；已经在A或C结算的结果损失不在B重复扣分",
        },
        "source_refs": {
            "adjudications": "config/first-item-b-team-contribution-adjudications.json",
            "roster": "docs/评分结算/第三项军事与边疆净收益/02-秦至唐第三项正式结算.json",
        },
        "record_count": len(records),
        "eligible_count": len(eligible),
        "excluded_count": len(excluded),
        "score_ready_count": len(records),
        "unresolved_count": 0,
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
        "# 秦至唐第一项B政治整合能力结算",
        "",
        "> B只结算非奠基人团队在创业窗口内实际完成的成果，不再按职能格子或人头评分。",
        "> 同一成员可凭多个不重叠成果累计；奠基人本人承担的部分归A或C，不回填B。",
        "",
        f"- 名册对象：{payload['record_count']} 人",
        f"- 奠基者完整结算：{payload['eligible_count']} 人",
        f"- 非奠基者不适用：{payload['excluded_count']} 人",
        f"- 未决：{payload['unresolved_count']} 人",
        "",
        "| B项序 | 对象 | 政权 | 团队成果B1/30 | 人才质量B2/30 | B/60 |",
        "|---:|---|---|---:|---:|---:|",
    ]
    eligible = [row for row in payload["records"] if row["score_applicable"]]
    for row in eligible:
        lines.append(
            f"| {row['trial_rank']} | {row['ruler_name']} | {row.get('polity') or '—'} | "
            f"{row['B1']['points']:g} | {row['B2']['points']:g} | {row['B_score_points']:g} |"
        )
    lines.extend(["", "## 逐人裁决", ""])
    for row in eligible:
        lines.extend([f"### {row['trial_rank']}. {row['ruler_name']}", ""])
        for chain in row["B1"]["contribution_chains"]:
            actors = "、".join(chain["actors"])
            lines.append(
                f"- {chain['chain']}：{chain['points']:g}分（{chain['outcome_level']} × "
                f"{chain['non_founder_responsibility']} × {chain['completion']}），承担者：{actors}。"
            )
        lines.extend([
            f"- B1：原始{row['B1']['raw_points']:g}，封顶后{row['B1']['points']:g}/30。",
            "- B2贡献者：" + "；".join(
                f"{profile['contributor']} {profile['level']}×{profile['position_weight']:g}={profile['points']:g}"
                for profile in row["B2"]["contributor_profiles"]
            ) + "。",
            f"- B2：原始{row['B2']['raw_points']:g}，封顶后{row['B2']['points']:g}/30。",
            f"- 裁决：{row['basis']}",
        ])
        if row["limitations"]:
            lines.append("- 限制：" + "；".join(row["limitations"]) + "。")
        lines.append("")
    excluded = [row for row in payload["records"] if not row["score_applicable"]]
    lines.extend([
        "## 非奠基者不适用", "", "、".join(row["ruler_name"] for row in excluded) + "。", "",
        "## 机器读取", "", "同目录JSON是唯一机器读取源；本文件仅为同值阅读视图。", "",
    ])
    return "\n".join(lines)


def write_first_item_b_registry(workspace_root: Path) -> dict[str, Path]:
    def load(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    payload = build_first_item_b_registry(
        adjudications=load(workspace_root / "config/first-item-b-team-contribution-adjudications.json"),
        roster=load(workspace_root / "docs/评分结算/第三项军事与边疆净收益/02-秦至唐第三项正式结算.json"),
    )
    output_dir = workspace_root / "docs/评分结算/第一项创业与政权取得能力/政治整合能力"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "01-秦至唐第一项B政治整合能力结算.json"
    markdown_path = output_dir / "01-秦至唐第一项B政治整合能力结算.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_first_item_b_registry_markdown(payload), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}
